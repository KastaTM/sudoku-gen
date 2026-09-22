"""Stable puzzle identities and order-preserving deduplication utilities."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256

from sudoku_gen.models import Grid, SudokuPuzzle

_FINGERPRINT_DOMAIN = "sudoku_gen:grid_fingerprint:v1"


class FingerprintMode(Enum):
    """Supported equivalence relations for published Sudoku clue grids."""

    EXACT = "exact"
    DIGIT_NORMALIZED = "digit_normalized"
    CLUE_PATTERN = "clue_pattern"


@dataclass(frozen=True, slots=True)
class GridFingerprint:
    """A mode-tagged, SHA-256 identity for a canonicalized clue grid."""

    mode: FingerprintMode
    value: str


def fingerprint_grid(
    grid: Grid,
    mode: FingerprintMode = FingerprintMode.EXACT,
) -> GridFingerprint:
    """Return the stable fingerprint of a grid under the requested equivalence.

    DIGIT_NORMALIZED accounts only for a global digit relabeling. It does not
    account for geometric Sudoku transformations such as row permutations.
    """
    canonical_key = _canonical_key(grid, mode)
    digest_input = f"{_FINGERPRINT_DOMAIN}:{mode.value}:{canonical_key}".encode("ascii")
    return GridFingerprint(mode=mode, value=sha256(digest_input).hexdigest())


def fingerprint_puzzle(
    puzzle: SudokuPuzzle,
    mode: FingerprintMode = FingerprintMode.EXACT,
) -> GridFingerprint:
    """Return a fingerprint for a puzzle's clue grid, ignoring its solution."""
    if not isinstance(puzzle, SudokuPuzzle):
        raise TypeError("puzzle must be a SudokuPuzzle.")
    return fingerprint_grid(puzzle.grid, mode)


def deduplicate_puzzles(
    puzzles: Iterable[SudokuPuzzle],
    *,
    mode: FingerprintMode = FingerprintMode.EXACT,
) -> tuple[SudokuPuzzle, ...]:
    """Keep the first puzzle of every selected canonical identity in order.

    Canonical keys, rather than digests alone, determine duplicates so a
    theoretical SHA-256 collision cannot discard a distinct puzzle.
    """
    _validate_mode(mode)
    seen_keys: set[str] = set()
    unique_puzzles: list[SudokuPuzzle] = []
    for puzzle in puzzles:
        if not isinstance(puzzle, SudokuPuzzle):
            raise TypeError("puzzles must contain only SudokuPuzzle instances.")
        canonical_key = _canonical_key(puzzle.grid, mode)
        if canonical_key not in seen_keys:
            seen_keys.add(canonical_key)
            unique_puzzles.append(puzzle)
    return tuple(unique_puzzles)


def _canonical_key(grid: Grid, mode: FingerprintMode) -> str:
    _validate_grid(grid)
    _validate_mode(mode)
    if mode is FingerprintMode.EXACT:
        return grid.to_string()
    if mode is FingerprintMode.DIGIT_NORMALIZED:
        return _digit_normalized_key(grid)
    return "".join("0" if value == 0 else "1" for value in grid.cells)


def _digit_normalized_key(grid: Grid) -> str:
    digit_mapping: dict[int, int] = {}
    next_digit = 1
    normalized_cells: list[str] = []
    for value in grid.cells:
        if value == 0:
            normalized_cells.append("0")
            continue
        if value not in digit_mapping:
            digit_mapping[value] = next_digit
            next_digit += 1
        normalized_cells.append(str(digit_mapping[value]))
    return "".join(normalized_cells)


def _validate_grid(grid: Grid) -> None:
    if not isinstance(grid, Grid):
        raise TypeError("grid must be a Grid.")


def _validate_mode(mode: FingerprintMode) -> None:
    if not isinstance(mode, FingerprintMode):
        raise TypeError("mode must be a FingerprintMode.")
