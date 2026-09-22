"""Stable clue-grid fingerprints and order-preserving deduplication tests."""

from dataclasses import FrozenInstanceError

import pytest

from sudoku_gen.fingerprint import (
    FingerprintMode,
    GridFingerprint,
    deduplicate_puzzles,
    fingerprint_grid,
    fingerprint_puzzle,
)
from sudoku_gen.models import Grid, SudokuPuzzle

GRID_TEXT = (
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
)
SOLUTION_TEXT = (
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)


def relabel(grid: Grid, mapping: dict[int, int]) -> Grid:
    return Grid(tuple(mapping.get(value, 0) if value else 0 for value in grid.cells))


def move_first_clue(grid: Grid) -> Grid:
    cells = list(grid.cells)
    source = next(index for index, value in enumerate(cells) if value != 0)
    destination = next(index for index, value in enumerate(cells) if value == 0)
    cells[destination] = cells[source]
    cells[source] = 0
    return Grid(tuple(cells))


def test_exact_fingerprints_are_stable_and_change_with_every_cell_change() -> None:
    grid = Grid.from_string(GRID_TEXT)
    changed = Grid((4,) + grid.cells[1:])

    first = fingerprint_grid(grid)

    assert first == fingerprint_grid(grid)
    assert first != fingerprint_grid(changed)
    assert first.mode is FingerprintMode.EXACT
    assert (
        first.value
        == "0f7eda078fcd05ea330b4d8a3214419db52ad44325a9c37e1e59a3d5269e5bdb"
    )


def test_fingerprint_value_object_is_immutable_and_hashable() -> None:
    fingerprint = fingerprint_grid(Grid.from_string(GRID_TEXT))

    with pytest.raises(FrozenInstanceError):
        fingerprint.value = "changed"

    assert isinstance(fingerprint, GridFingerprint)
    assert hash(fingerprint) == hash(fingerprint_grid(Grid.from_string(GRID_TEXT)))


def test_digit_normalization_equates_global_relabelings_and_preserves_zeros() -> None:
    grid = Grid.from_string(GRID_TEXT)
    relabeled_once = relabel(
        grid, {1: 7, 2: 1, 3: 9, 4: 2, 5: 8, 6: 3, 7: 6, 8: 4, 9: 5}
    )
    relabeled_twice = relabel(
        grid, {1: 4, 2: 9, 3: 2, 4: 6, 5: 1, 6: 7, 7: 3, 8: 5, 9: 8}
    )

    assert fingerprint_grid(grid, FingerprintMode.DIGIT_NORMALIZED) == fingerprint_grid(
        relabeled_once, FingerprintMode.DIGIT_NORMALIZED
    )
    assert fingerprint_grid(grid, FingerprintMode.DIGIT_NORMALIZED) == fingerprint_grid(
        relabeled_twice, FingerprintMode.DIGIT_NORMALIZED
    )
    assert all(
        original != 0 or normalized == 0
        for original, normalized in zip(grid.cells, relabeled_once.cells, strict=True)
    )


def test_digit_normalization_keeps_cell_positions_significant() -> None:
    grid = Grid.from_string(GRID_TEXT)

    assert fingerprint_grid(grid, FingerprintMode.DIGIT_NORMALIZED) != fingerprint_grid(
        move_first_clue(grid), FingerprintMode.DIGIT_NORMALIZED
    )


def test_clue_pattern_ignores_values_but_not_positions() -> None:
    grid = Grid.from_string(GRID_TEXT)
    relabeled_grid = relabel(
        grid, {1: 7, 2: 1, 3: 9, 4: 2, 5: 8, 6: 3, 7: 6, 8: 4, 9: 5}
    )

    assert fingerprint_grid(grid, FingerprintMode.CLUE_PATTERN) == fingerprint_grid(
        relabeled_grid, FingerprintMode.CLUE_PATTERN
    )
    assert fingerprint_grid(grid, FingerprintMode.CLUE_PATTERN) != fingerprint_grid(
        move_first_clue(grid), FingerprintMode.CLUE_PATTERN
    )


def test_fingerprints_are_distinct_between_modes() -> None:
    grid = Grid.from_string(GRID_TEXT)

    assert fingerprint_grid(grid, FingerprintMode.EXACT) != fingerprint_grid(
        grid, FingerprintMode.DIGIT_NORMALIZED
    )
    assert fingerprint_grid(grid, FingerprintMode.DIGIT_NORMALIZED) != fingerprint_grid(
        grid, FingerprintMode.CLUE_PATTERN
    )


def test_puzzle_fingerprint_uses_only_published_clue_grid() -> None:
    grid = Grid.from_string(GRID_TEXT)
    solution = Grid.from_string(SOLUTION_TEXT)

    assert fingerprint_puzzle(SudokuPuzzle(grid)) == fingerprint_puzzle(
        SudokuPuzzle(grid, solution)
    )


def test_deduplication_keeps_first_puzzle_and_input_order_for_exact_identity() -> None:
    first = SudokuPuzzle(Grid.from_string(GRID_TEXT))
    duplicate = SudokuPuzzle(
        Grid.from_string(GRID_TEXT), Grid.from_string(SOLUTION_TEXT)
    )
    distinct = SudokuPuzzle(move_first_clue(first.grid))

    result = deduplicate_puzzles([first, duplicate, distinct, first])

    assert result == (first, distinct)
    assert isinstance(result, tuple)


def test_deduplication_uses_requested_digit_normalized_or_clue_pattern_identity() -> (
    None
):
    grid = Grid.from_string(GRID_TEXT)
    first = SudokuPuzzle(grid)
    relabeled_puzzle = SudokuPuzzle(
        relabel(grid, {1: 7, 2: 1, 3: 9, 4: 2, 5: 8, 6: 3, 7: 6, 8: 4, 9: 5})
    )
    moved_puzzle = SudokuPuzzle(move_first_clue(grid))

    assert deduplicate_puzzles([first, relabeled_puzzle]) == (first, relabeled_puzzle)
    assert deduplicate_puzzles(
        [first, relabeled_puzzle], mode=FingerprintMode.DIGIT_NORMALIZED
    ) == (first,)
    assert deduplicate_puzzles(
        [first, relabeled_puzzle], mode=FingerprintMode.CLUE_PATTERN
    ) == (first,)
    assert deduplicate_puzzles(
        [first, moved_puzzle], mode=FingerprintMode.CLUE_PATTERN
    ) == (first, moved_puzzle)


def test_deduplication_handles_empty_and_single_inputs() -> None:
    puzzle = SudokuPuzzle(Grid.from_string(GRID_TEXT))

    assert deduplicate_puzzles([]) == ()
    assert deduplicate_puzzles([puzzle]) == (puzzle,)


@pytest.mark.parametrize("mode", [None, "exact", 0, True])
def test_modes_must_be_typed(mode: object) -> None:
    grid = Grid.from_string(GRID_TEXT)
    puzzle = SudokuPuzzle(grid)

    with pytest.raises(TypeError):
        fingerprint_grid(grid, mode)
    with pytest.raises(TypeError):
        fingerprint_puzzle(puzzle, mode)
    with pytest.raises(TypeError):
        deduplicate_puzzles([puzzle], mode=mode)


@pytest.mark.parametrize("value", [None, Grid.from_string(GRID_TEXT), "puzzle"])
def test_puzzle_apis_reject_invalid_puzzle_types(value: object) -> None:
    with pytest.raises(TypeError):
        fingerprint_puzzle(value)
    with pytest.raises(TypeError):
        deduplicate_puzzles([value])
