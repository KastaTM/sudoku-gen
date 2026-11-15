"""Edition registry: integrity, persistence and cross-edition exclusivity."""

import json
import os
from pathlib import Path

import pytest

from sudoku_gen.fingerprint import FingerprintMode
from sudoku_gen.publication import (
    EditionRecord,
    EditionRegistry,
    ManifestEnvironment,
    PublicationJob,
    PublicationResult,
    RegistryConflictError,
    append_edition,
    edition_record,
    load_registry,
    publication_manifest,
    record_from_manifest,
    register_manifest,
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


def test_loader_rejects_bad_values_with_line_numbers() -> None:
    good = json.dumps(record().as_dict())
    cases = {
        "not json": "{",
        "not an object": "[1, 2]",
        "null title": json.dumps({**record().as_dict(), "title": None}),
        "numeric id": json.dumps({**record().as_dict(), "edition_id": 7}),
        "bad locale": json.dumps({**record().as_dict(), "locale": "spanish"}),
        "bool seed": json.dumps({**record().as_dict(), "seed": True}),
    }
    for label, line in cases.items():
        with pytest.raises(ValueError, match="Registry line 2") as error:
            EditionRegistry.from_jsonl(good + "\n" + line)
        assert "None" not in str(error.value) or label != "null title", label


def test_locked_registry_is_refused_and_untouched(tmp_path: Path) -> None:
    path = tmp_path / "editions.jsonl"
    append_edition(path, record())
    before = path.read_bytes()
    lock = tmp_path / "editions.jsonl.lock"
    lock.write_text("")

    with pytest.raises(RegistryConflictError) as error:
        append_edition(path, record("pilot-es-002", 2, (digest("d"),)))

    assert error.value.reason == "locked"
    assert path.read_bytes() == before and lock.exists()
    lock.unlink()
    append_edition(path, record("pilot-es-002", 2, (digest("d"),)))


def test_failed_replace_leaves_no_temp_or_lock_and_keeps_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "editions.jsonl"
    append_edition(path, record())
    before = path.read_bytes()

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("target is open elsewhere")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(PermissionError):
        append_edition(path, record("pilot-es-002", 2, (digest("d"),)))

    assert path.read_bytes() == before
    assert sorted(item.name for item in tmp_path.iterdir()) == ["editions.jsonl"]


def release_manifest(
    result: PublicationResult, **environment_changes: object
) -> dict[str, object]:
    environment = ManifestEnvironment(
        generator_version="0.2.0",
        git_sha=environment_changes.get("git_sha", "a" * 40),  # type: ignore[arg-type]
        git_dirty=environment_changes.get("git_dirty", False),  # type: ignore[arg-type]
        python_version="3.12.0",
        platform="test",
        dependencies=(),
    )
    return json.loads(publication_manifest(result, environment))


def test_register_manifest_enforces_the_release_checks(
    reference_result: PublicationResult, tmp_path: Path
) -> None:
    path = tmp_path / "editions.jsonl"
    pdf = reference_result.interior_pdf

    for changes, message in (
        ({"git_sha": None}, "40-hex"),
        ({"git_sha": "abc"}, "40-hex"),
        ({"git_dirty": True}, "clean"),
        ({"git_dirty": None}, "clean"),
    ):
        with pytest.raises(ValueError, match=message):
            register_manifest(
                path, release_manifest(reference_result, **changes), "ed-001", pdf
            )
    with pytest.raises(ValueError, match="does not match"):
        register_manifest(path, release_manifest(reference_result), "ed-001", b"x")
    blocked = release_manifest(reference_result) | {"preflight_blocking": True}
    with pytest.raises(ValueError, match="preflight"):
        register_manifest(path, blocked, "ed-001", pdf)
    assert not path.exists()

    registry = register_manifest(
        path, release_manifest(reference_result), "ed-001", pdf
    )
    assert len(registry.editions) == 1
    assert load_registry(path) == registry


def test_register_manifest_rejects_an_edition_built_against_a_stale_registry(
    reference_result: PublicationResult, tmp_path: Path
) -> None:
    path = tmp_path / "editions.jsonl"
    append_edition(path, record())
    manifest = release_manifest(reference_result)

    with pytest.raises(RegistryConflictError) as error:
        register_manifest(path, manifest, "ed-001", reference_result.interior_pdf)

    assert error.value.reason == "stale_registry"
    assert len(load_registry(path).editions) == 1
