"""Manifest schema v2: reproducibility inputs, fingerprints and environment."""

import json
import platform
import subprocess
from hashlib import sha256
from importlib.resources import files

import pytest

import sudoku_gen.publication.manifest as manifest_module
from sudoku_gen.publication import (
    ManifestEnvironment,
    PublicationResult,
    collect_environment,
    font_identity,
    publication_manifest,
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
