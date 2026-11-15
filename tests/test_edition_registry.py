"""Edition registry: integrity, persistence and cross-edition exclusivity."""

import json
from pathlib import Path

import pytest

from sudoku_gen.fingerprint import FingerprintMode
from sudoku_gen.publication import (
    EditionRecord,
    EditionRegistry,
    PublicationJob,
    PublicationResult,
    RegistryConflictError,
    append_edition,
    edition_record,
    load_registry,
    record_from_manifest,
    run_publication,
)

MODE = FingerprintMode.DIGIT_NORMALIZED


def digest(character: str) -> str:
    return character * 64


def record(
    edition_id: str = "pilot-es-001",
    seed: int = 1,
    fingerprints: tuple[str, ...] = (digest("a"), digest("b")),
    mode: FingerprintMode = MODE,
) -> EditionRecord:
    return EditionRecord(
        edition_id, "Libro", "es-ES", seed, mode, fingerprints, digest("c")
    )


def test_record_validation() -> None:
    for kwargs in (
        {"edition_id": "A"},
        {"edition_id": "no spaces allowed"},
        {"fingerprints": ()},
        {"fingerprints": (digest("a"), digest("a"))},
        {"fingerprints": ("short",)},
    ):
        with pytest.raises(ValueError):
            record(**kwargs)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        record(seed=True)


def test_registry_rejects_duplicate_id_seed_and_fingerprint() -> None:
    first = record()
    cases = {
        "edition_id": record(seed=2, fingerprints=(digest("d"),)),
        "seed": record("pilot-es-002", seed=1, fingerprints=(digest("d"),)),
        "fingerprint": record("pilot-es-002", seed=2, fingerprints=(digest("b"),)),
    }
    for reason, other in cases.items():
        with pytest.raises(RegistryConflictError) as error:
            EditionRegistry((first, other))
        assert error.value.reason == reason


def test_registry_rejects_mixed_modes() -> None:
    other = record("pilot-es-002", 2, (digest("d"),), mode=FingerprintMode.CLUE_PATTERN)
    with pytest.raises(RegistryConflictError) as error:
        EditionRegistry((record(), other))
    assert error.value.reason == "deduplication_mode"


def test_check_job_and_disjointness() -> None:
    registry = EditionRegistry((record(),))

    registry.check_job(2, MODE)
    registry.ensure_disjoint([digest("z")])
    with pytest.raises(RegistryConflictError, match="Seed 1"):
        registry.check_job(1, MODE)
    with pytest.raises(RegistryConflictError, match="mode"):
        registry.check_job(2, FingerprintMode.EXACT)
    with pytest.raises(RegistryConflictError, match="pilot-es-001"):
        registry.ensure_disjoint([digest("z"), digest("a")])
    EditionRegistry().check_job(1, FingerprintMode.EXACT)


def test_jsonl_round_trip_is_deterministic_and_validated() -> None:
    registry = EditionRegistry((record(), record("pilot-es-002", 2, (digest("d"),))))
    text = registry.to_jsonl()

    assert EditionRegistry.from_jsonl(text) == registry
    assert text == EditionRegistry.from_jsonl(text).to_jsonl()
    assert text.count("\n") == 2
    broken = json.loads(text.splitlines()[0])
    del broken["seed"]
    with pytest.raises(ValueError, match="seed"):
        EditionRegistry.from_jsonl(json.dumps(broken))


def test_append_edition_persists_and_conflict_leaves_file_untouched(
    tmp_path: Path,
) -> None:
    path = tmp_path / "editions.jsonl"
    append_edition(path, record())
    before = path.read_bytes()

    with pytest.raises(RegistryConflictError):
        append_edition(path, record("pilot-es-002", 1, (digest("d"),)))

    assert path.read_bytes() == before
    assert not (tmp_path / "editions.jsonl.tmp").exists()
    assert load_registry(path).editions == (record(),)
    append_edition(path, record("pilot-es-002", 2, (digest("d"),)))
    assert len(load_registry(path).editions) == 2


def test_committed_catalogue_is_valid() -> None:
    path = Path(__file__).resolve().parents[1] / "catalog" / "editions.jsonl"

    assert isinstance(load_registry(path), EditionRegistry)


def test_record_from_real_manifest_and_reused_seed_is_rejected(
    reference_result: PublicationResult,
) -> None:
    edition = edition_record(reference_result, "dev-example-001")

    assert len(edition.puzzle_fingerprints) == 36
    assert edition.seed == reference_result.job.seed
    assert edition.locale == "es-ES"
    registry = EditionRegistry((edition,))
    reused = PublicationJob(
        reference_result.job.metadata,
        reference_result.job.sections,
        reference_result.job.seed,
        registry=registry,
    )
    with pytest.raises(RegistryConflictError, match="Seed"):
        run_publication(reused)


def test_manifest_v1_cannot_be_registered() -> None:
    with pytest.raises(ValueError, match="schema_version 2"):
        record_from_manifest({"schema_version": 1}, "old-edition")
