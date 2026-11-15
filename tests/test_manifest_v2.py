"""Manifest schema v2: reproducibility inputs, fingerprints and environment."""

import json
import platform
import subprocess
from dataclasses import replace
from hashlib import sha256
from importlib.resources import files

import pytest

import sudoku_gen.publication.manifest as manifest_module
from sudoku_gen.publication import (
    EN_US,
    CoverContent,
    ManifestEnvironment,
    PageLayoutProfile,
    PublicationResult,
    collect_environment,
    font_identity,
    job_digest,
    job_from_dict,
    job_to_dict,
    publication_manifest,
    run_publication,
)


def environment(sha: str | None = "a" * 40) -> ManifestEnvironment:
    return ManifestEnvironment(
        generator_version="0.2.0",
        git_sha=sha,
        git_dirty=False,
        python_version="3.12.0",
        platform="test-platform",
        dependencies=(("pypdf", "1.0"), ("reportlab", "2.0")),
    )


def test_manifest_v2_records_inputs_fingerprints_and_font(
    reference_result: PublicationResult,
) -> None:
    manifest = json.loads(publication_manifest(reference_result, environment()))

    assert manifest["schema_version"] == 2
    assert manifest["locale"] == "es-ES"
    assert manifest["deduplication_mode"] == "digit_normalized"
    assert manifest["print_profile"] == {
        "trim_width_points": 432.0,
        "trim_height_points": 648.0,
        "bleed": False,
        "minimum_page_count": 24,
        "maximum_page_count": 828,
    }
    vera = files("sudoku_gen.publication").joinpath("assets", "Vera.ttf").read_bytes()
    assert manifest["font"]["sha256"] == sha256(vera).hexdigest()
    fingerprints = manifest["sections"][0]["puzzle_fingerprints"]
    assert fingerprints == [
        puzzle.fingerprint.value
        for puzzle in reference_result.book_plan.sections[0].puzzles
    ]
    assert len(fingerprints) == len(set(fingerprints)) == 36
    assert all(len(value) == 64 for value in fingerprints)
    assert (
        manifest["interior_sha256"] == sha256(reference_result.interior_pdf).hexdigest()
    )


def test_manifest_is_deterministic_and_environment_is_separate(
    reference_result: PublicationResult,
) -> None:
    first = publication_manifest(reference_result, environment("a" * 40))
    assert first == publication_manifest(reference_result, environment("a" * 40))

    other = json.loads(publication_manifest(reference_result, environment("b" * 40)))
    base = json.loads(first)
    assert other["environment"]["git_sha"] != base["environment"]["git_sha"]
    other.pop("environment")
    base.pop("environment")
    assert other == base


def test_default_environment_is_collected(reference_result: PublicationResult) -> None:
    recorded = json.loads(publication_manifest(reference_result))["environment"]

    assert recorded["python_version"] == platform.python_version()
    assert set(recorded["dependencies"]) == {"reportlab", "pypdf"}
    assert recorded["dependencies"]["reportlab"] is not None


def test_git_sha_env_var_wins_and_leaves_dirty_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(manifest_module.GIT_SHA_ENV_VAR, "c" * 40)

    collected = collect_environment()

    assert collected.git_sha == "c" * 40
    assert collected.git_dirty is None


def test_missing_git_never_breaks_the_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(manifest_module.GIT_SHA_ENV_VAR, raising=False)

    def broken(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", broken)

    collected = collect_environment()

    assert collected.git_sha is None
    assert collected.git_dirty is None
    assert collected.as_dict()["python_version"]


def test_font_identity_is_stable() -> None:
    assert font_identity() == font_identity()
    assert font_identity()["name"] == "Bitstream Vera Sans"


def test_manifest_records_every_job_input_and_rebuilds_the_same_edition(
    reference_result: PublicationResult,
) -> None:
    manifest = json.loads(publication_manifest(reference_result, environment()))
    job = manifest["job"]

    assert job["target_clues"] == 30
    assert job["symmetry"] == "rotational_180"
    assert job["strategy"] == "random_retry"
    assert job["page_layout"] == {
        "puzzles_per_page": 2,
        "solutions_per_page": 6,
        "first_page_number": 1,
    }
    assert job["metadata"]["copyright_notice"] == "Aviso"
    assert job["cover_content"]["back_cover_copy"] == "Texto"
    assert job["front_matter"]["include_contents_page"] is True
    assert manifest["job_sha256"] == job_digest(reference_result.job)

    rebuilt_job = job_from_dict(job)
    assert job_to_dict(rebuilt_job) == job
    rebuilt = run_publication(rebuilt_job)
    assert sha256(rebuilt.interior_pdf).hexdigest() == manifest["interior_sha256"]
    assert sha256(rebuilt.cover_pdf).hexdigest() == manifest["cover_sha256"]


def test_job_digest_changes_with_any_input(
    reference_result: PublicationResult,
) -> None:
    job = reference_result.job
    base = job_digest(job)

    assert job_digest(replace(job, target_clues=26)) != base
    assert job_digest(replace(job, page_layout=PageLayoutProfile(1, 4, 1))) != base
    assert job_digest(replace(job, cover_content=CoverContent("Otro"))) != base
    assert job_digest(replace(job, locale=EN_US)) != base
    assert job_digest(job) == base


def test_manifest_records_registry_digest(reference_result: PublicationResult) -> None:
    manifest = json.loads(publication_manifest(reference_result, environment()))

    assert manifest["registry"] == {
        "sha256": sha256(b"").hexdigest(),
        "edition_count": 0,
    }


def test_invalid_git_sha_env_var_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(manifest_module.GIT_SHA_ENV_VAR, "not-a-sha")
    monkeypatch.setattr(manifest_module, "_git", lambda *_a, **_k: None)

    assert collect_environment().git_sha is None
