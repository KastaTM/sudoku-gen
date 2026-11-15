"""Persistent registry of published editions (decision D-006).

Puzzles are exclusive per SKU across editions and languages. The registry is
an append-only JSON Lines file kept in the repository (``catalog/``). It
stores, per edition, the seed and the puzzle fingerprints that must never be
reused. It is validated on load: an inconsistent file cannot be read.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from sudoku_gen.exceptions import PublicationError
from sudoku_gen.fingerprint import FingerprintMode

_EDITION_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class RegistryConflictError(PublicationError):
    """A seed, edition id, fingerprint or mode conflicts with the registry."""

    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class EditionRecord:
    """The identity of one edition that reserves its seed and puzzles."""

    edition_id: str
    title: str
    locale: str
    seed: int
    deduplication_mode: FingerprintMode
    puzzle_fingerprints: tuple[str, ...]
    interior_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.edition_id, str) or not _EDITION_ID.match(
            self.edition_id
        ):
            raise ValueError("edition_id must be 3-64 chars of [a-z0-9._-].")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must be a nonempty string.")
        if not isinstance(self.locale, str) or not self.locale:
            raise ValueError("locale must be a nonempty string.")
        if type(self.seed) is not int:
            raise TypeError("seed must be a built-in integer.")
        if not isinstance(self.deduplication_mode, FingerprintMode):
            raise TypeError("deduplication_mode must be a FingerprintMode.")
        if not isinstance(self.puzzle_fingerprints, tuple):
            raise TypeError("puzzle_fingerprints must be a tuple.")
        if not self.puzzle_fingerprints:
            raise ValueError("An edition must register at least one puzzle.")
        if not all(
            isinstance(value, str) and _SHA256.match(value)
            for value in self.puzzle_fingerprints
        ):
            raise ValueError("puzzle_fingerprints must be SHA-256 hex digests.")
        if len(set(self.puzzle_fingerprints)) != len(self.puzzle_fingerprints):
            raise ValueError("An edition must not repeat a puzzle fingerprint.")
        if not isinstance(self.interior_sha256, str) or not _SHA256.match(
            self.interior_sha256
        ):
            raise ValueError("interior_sha256 must be a SHA-256 hex digest.")

    def as_dict(self) -> dict[str, object]:
        return {
            "edition_id": self.edition_id,
            "title": self.title,
            "locale": self.locale,
            "seed": self.seed,
            "deduplication_mode": self.deduplication_mode.value,
            "puzzle_fingerprints": list(self.puzzle_fingerprints),
            "interior_sha256": self.interior_sha256,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> EditionRecord:
        try:
            fingerprints = data["puzzle_fingerprints"]
            if not isinstance(fingerprints, list):
                raise TypeError("puzzle_fingerprints must be a list.")
            return cls(
                edition_id=str(data["edition_id"]),
                title=str(data["title"]),
                locale=str(data["locale"]),
                seed=data["seed"],  # type: ignore[arg-type]
                deduplication_mode=FingerprintMode(data["deduplication_mode"]),
                puzzle_fingerprints=tuple(fingerprints),
                interior_sha256=str(data["interior_sha256"]),
            )
        except KeyError as error:
            raise ValueError(f"Registry record lacks field {error}.") from None


def record_from_manifest(
    manifest: Mapping[str, object], edition_id: str
) -> EditionRecord:
    """Build a record from a schema-v2 manifest of an approved edition."""
    if manifest.get("schema_version") != 2:
        raise ValueError("Only schema_version 2 manifests can be registered.")
    sections = manifest["sections"]
    if not isinstance(sections, list):
        raise TypeError("manifest sections must be a list.")
    fingerprints = tuple(
        value for section in sections for value in section["puzzle_fingerprints"]
    )
    return EditionRecord(
        edition_id=edition_id,
        title=str(manifest["title"]),
        locale=str(manifest["locale"]),
        seed=manifest["seed"],  # type: ignore[arg-type]
        deduplication_mode=FingerprintMode(manifest["deduplication_mode"]),
        puzzle_fingerprints=fingerprints,
        interior_sha256=str(manifest["interior_sha256"]),
    )


@dataclass(frozen=True, slots=True)
class EditionRegistry:
    """Immutable, internally consistent set of registered editions."""

    editions: tuple[EditionRecord, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.editions, tuple):
            raise TypeError("editions must be a tuple of EditionRecord.")
        ids: set[str] = set()
        seeds: set[int] = set()
        seen: set[str] = set()
        modes = {edition.deduplication_mode for edition in self.editions}
        if len(modes) > 1:
            raise RegistryConflictError(
                "deduplication_mode", "Registry mixes fingerprint modes."
            )
        for edition in self.editions:
            if not isinstance(edition, EditionRecord):
                raise TypeError("editions must contain only EditionRecord.")
            if edition.edition_id in ids:
                raise RegistryConflictError(
                    "edition_id", f"Duplicate edition id {edition.edition_id!r}."
                )
            if edition.seed in seeds:
                raise RegistryConflictError(
                    "seed", f"Seed {edition.seed} is used by two editions."
                )
            if seen.intersection(edition.puzzle_fingerprints):
                raise RegistryConflictError(
                    "fingerprint",
                    f"Edition {edition.edition_id!r} reuses a registered puzzle.",
                )
            ids.add(edition.edition_id)
            seeds.add(edition.seed)
            seen.update(edition.puzzle_fingerprints)

    def check_job(self, seed: int, mode: FingerprintMode) -> None:
        """Reject a job whose base seed or fingerprint mode cannot be compared."""
        for edition in self.editions:
            if edition.seed == seed:
                raise RegistryConflictError(
                    "seed",
                    f"Seed {seed} is already used by edition {edition.edition_id!r}.",
                )
            if edition.deduplication_mode is not mode:
                raise RegistryConflictError(
                    "deduplication_mode",
                    "Job fingerprint mode differs from the registry's mode.",
                )

    def ensure_disjoint(self, fingerprints: Iterable[str]) -> None:
        """Raise if any fingerprint already belongs to a registered edition."""
        wanted = set(fingerprints)
        for edition in self.editions:
            if wanted.intersection(edition.puzzle_fingerprints):
                raise RegistryConflictError(
                    "fingerprint",
                    f"A puzzle is already used by edition {edition.edition_id!r}.",
                )

    def register(self, record: EditionRecord) -> EditionRegistry:
        """Return a new registry with ``record`` added, or raise on conflict."""
        return EditionRegistry(self.editions + (record,))

    def to_jsonl(self) -> str:
        return "".join(
            json.dumps(edition.as_dict(), sort_keys=True, separators=(",", ":")) + "\n"
            for edition in self.editions
        )

    @classmethod
    def from_jsonl(cls, text: str) -> EditionRegistry:
        records = tuple(
            EditionRecord.from_dict(json.loads(line))
            for line in text.splitlines()
            if line.strip()
        )
        return cls(records)


def load_registry(path: Path) -> EditionRegistry:
    """Read and validate a registry file; a missing file is an error."""
    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path.")
    return EditionRegistry.from_jsonl(path.read_text(encoding="utf-8"))


def append_edition(path: Path, record: EditionRecord) -> EditionRegistry:
    """Validate and persist ``record``; on conflict the file is untouched."""
    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path.")
    current = load_registry(path) if path.exists() else EditionRegistry()
    updated = current.register(record)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(updated.to_jsonl(), encoding="utf-8", newline="\n")
    os.replace(temporary, path)
    return updated
