"""Environment and font identity recorded in the publication manifest (v2).

The ``environment`` block is informational: it explains where an edition was
built but is not an input of reproduction. Missing facts are recorded as
``None`` instead of raising, so a manifest can always be written.
"""

from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from importlib import metadata
from importlib.resources import files
from pathlib import Path

FONT_NAME = "Bitstream Vera Sans"
FONT_FILE = "Vera.ttf"
GIT_SHA_ENV_VAR = "SUDOKU_GEN_GIT_SHA"
_DEPENDENCIES = ("reportlab", "pypdf")
_GIT_TIMEOUT_SECONDS = 5


@dataclass(frozen=True, slots=True)
class ManifestEnvironment:
    """Where and with what a publication was built."""

    generator_version: str | None
    git_sha: str | None
    git_dirty: bool | None
    python_version: str
    platform: str
    dependencies: tuple[tuple[str, str | None], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "generator_version": self.generator_version,
            "git_sha": self.git_sha,
            "git_dirty": self.git_dirty,
            "python_version": self.python_version,
            "platform": self.platform,
            "dependencies": dict(self.dependencies),
        }


def font_identity() -> dict[str, str]:
    """Name, file and SHA-256 of the embedded font (an input of the PDF bytes)."""
    data = files("sudoku_gen.publication").joinpath("assets", FONT_FILE).read_bytes()
    return {"name": FONT_NAME, "file": FONT_FILE, "sha256": sha256(data).hexdigest()}


def _package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _git(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def _git_state() -> tuple[str | None, bool | None]:
    """Commit SHA and dirty flag; the env var wins and leaves dirty unknown."""
    from_env = os.environ.get(GIT_SHA_ENV_VAR)
    if from_env:
        return from_env.strip(), None
    root = Path(__file__).resolve().parents[3]
    if not (root / ".git").exists():
        return None, None
    sha = _git(root, "rev-parse", "HEAD")
    status = _git(root, "status", "--porcelain")
    return sha, (None if status is None else bool(status))


def collect_environment() -> ManifestEnvironment:
    """Gather build facts; never raises when a fact is unavailable."""
    git_sha, git_dirty = _git_state()
    return ManifestEnvironment(
        generator_version=_package_version("sudoku-gen"),
        git_sha=git_sha,
        git_dirty=git_dirty,
        python_version=platform.python_version(),
        platform=platform.platform(),
        dependencies=tuple((name, _package_version(name)) for name in _DEPENDENCIES),
    )
