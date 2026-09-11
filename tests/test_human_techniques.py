"""Independent fixtures for single detection, unit boundaries, and priority."""

from collections.abc import Iterable

import pytest

from sudoku_gen.candidates import candidates
from sudoku_gen.human_solver import SolveStep, Technique, apply_step, next_step
from sudoku_gen.models import Grid
from sudoku_gen.validation import empty_cells, is_valid_grid

SOLVED_TEXT = (
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)
# Each fixture has no naked singles. The indicated move is hidden in exactly
# one unit class, so a row-only implementation cannot pass the column/box tests.
ROW_HIDDEN_TEXT = (
    "000008010000000300090302060809060000006003000000020000001030084080010030300080070"
)
COLUMN_HIDDEN_TEXT = (
    "030600000670000300000002007000060003400053701000004806001000080207000035000006100"
)
BOX_HIDDEN_TEXT = (
    "000000900000095000090340500050000400020000000000020006000000080200009035000006079"
)
DIGIT_PRIORITY_TEXT = (
    "004008900000000048198002007000700423426803000703000000000000200080010000005206100"
)
NAKED_PRIORITY_TEXT = (
    "000008010000000300098302060809060000006003000000920000901530084087010035300080070"
)


def positions_for(
    grid: Grid, value: int, unit: Iterable[tuple[int, int]]
) -> tuple[tuple[int, int], ...]:
    """Expose candidate occurrences to verify the reasoning of each fixture."""
    return tuple(cell for cell in unit if value in candidates(grid, *cell))


def assert_no_naked_singles(grid: Grid) -> None:
    assert is_valid_grid(grid)
    assert all(len(candidates(grid, *cell)) > 1 for cell in empty_cells(grid))


def assert_no_hidden_singles(
    grid: Grid, units: Iterable[Iterable[tuple[int, int]]]
) -> None:
    for unit in units:
        cells = tuple(unit)
        for value in range(1, 10):
            assert len(positions_for(grid, value, cells)) != 1


@pytest.mark.parametrize("index", [0, 8, 40, 72, 80])
def test_a_naked_single_restores_a_missing_cell_at_boundaries(index: int) -> None:
    solved = Grid.from_string(SOLVED_TEXT)
    grid = Grid(solved.cells[:index] + (0,) + solved.cells[index + 1 :])
    row, column = divmod(index, 9)
    value = solved.cells[index]

    assert candidates(grid, row, column) == frozenset({value})
    step = next_step(grid)

    # This cell is also hidden in all three containing units; naked wins.
    assert step == SolveStep(Technique.NAKED_SINGLE, row, column, value)
    updated = apply_step(grid, step)
    assert updated == solved
    assert is_valid_grid(updated)
    assert updated is not grid
    assert grid.cells[index] == 0


def test_several_naked_singles_choose_row_major_order() -> None:
    solved = Grid.from_string(SOLVED_TEXT)
    holes = {0, 8, 40, 72, 80}
    grid = Grid(tuple(0 if i in holes else v for i, v in enumerate(solved.cells)))
    assert all(len(candidates(grid, *divmod(i, 9))) == 1 for i in holes)

    assert next_step(grid) == SolveStep(Technique.NAKED_SINGLE, 0, 0, 5)
    assert next_step(Grid(grid.cells)) == next_step(grid)


@pytest.mark.parametrize(
    ("text", "row", "column", "value", "options", "occurrence_counts"),
    [
        pytest.param(ROW_HIDDEN_TEXT, 2, 0, 1, {1, 4, 5, 7}, (1, 4, 3), id="row"),
        pytest.param(COLUMN_HIDDEN_TEXT, 4, 2, 6, {2, 6, 8, 9}, (2, 1, 2), id="column"),
        pytest.param(BOX_HIDDEN_TEXT, 6, 8, 4, {1, 2, 4}, (6, 3, 1), id="box"),
    ],
)
def test_hidden_single_is_justified_by_its_independent_unit(
    text: str,
    row: int,
    column: int,
    value: int,
    options: set[int],
    occurrence_counts: tuple[int, int, int],
) -> None:
    grid = Grid.from_string(text)
    assert_no_naked_singles(grid)
    assert candidates(grid, row, column) == frozenset(options)
    row_cells = [(row, c) for c in range(9)]
    column_cells = [(r, column) for r in range(9)]
    box_cells = [
        (r, c)
        for r in range(row // 3 * 3, row // 3 * 3 + 3)
        for c in range(column // 3 * 3, column // 3 * 3 + 3)
    ]
    assert (
        tuple(
            len(positions_for(grid, value, unit))
            for unit in (row_cells, column_cells, box_cells)
        )
        == occurrence_counts
    )
    if occurrence_counts[0] != 1:
        assert_no_hidden_singles(grid, ([(r, c) for c in range(9)] for r in range(9)))
    if occurrence_counts[2] == 1:
        assert_no_hidden_singles(grid, ([(r, c) for r in range(9)] for c in range(9)))

    step = next_step(grid)

    assert step == SolveStep(Technique.HIDDEN_SINGLE, row, column, value)
    updated = apply_step(grid, step)
    assert is_valid_grid(updated)
    assert updated.cells[row * 9 + column] == value
    assert sum(a != b for a, b in zip(grid.cells, updated.cells, strict=True)) == 1
    assert grid.to_string() == text


@pytest.mark.parametrize("box_row", range(3))
@pytest.mark.parametrize("box_column", range(3))
def test_box_hidden_detection_respects_each_box_boundary(
    box_row: int, box_column: int
) -> None:
    original = Grid.from_string(BOX_HIDDEN_TEXT)
    # Rotate whole bands/stacks to move the sole hidden single from box (2, 2)
    # to each box, preserving every Sudoku constraint and candidate relation.
    row_shift = (box_row - 2) * 3
    column_shift = (box_column - 2) * 3
    grid = Grid(
        tuple(
            original.cells[((r - row_shift) % 9) * 9 + (c - column_shift) % 9]
            for r in range(9)
            for c in range(9)
        )
    )
    assert_no_naked_singles(grid)
    expected = SolveStep(Technique.HIDDEN_SINGLE, box_row * 3, box_column * 3 + 2, 4)

    assert next_step(grid) == expected
    assert is_valid_grid(apply_step(grid, expected))


def test_hidden_column_priority_uses_unit_order_before_cell_order() -> None:
    grid = Grid.from_string(COLUMN_HIDDEN_TEXT)
    assert positions_for(grid, 6, [(r, 2) for r in range(9)]) == ((4, 2),)
    assert positions_for(grid, 6, [(r, 7) for r in range(9)]) == ((2, 7),)
    assert positions_for(grid, 7, [(r, 7) for r in range(9)]) == ((8, 7),)

    # Column 2 wins even though the other 6 is in an earlier row.
    expected = SolveStep(Technique.HIDDEN_SINGLE, 4, 2, 6)
    assert next_step(grid) == expected
    assert next_step(Grid(grid.cells)) == expected


def test_hidden_priority_uses_unit_then_digit_before_target_cell_order() -> None:
    grid = Grid.from_string(DIGIT_PRIORITY_TEXT)
    assert_no_naked_singles(grid)
    assert positions_for(grid, 6, [(3, c) for c in range(9)]) == ((3, 4),)
    assert positions_for(grid, 8, [(3, c) for c in range(9)]) == ((3, 0),)
    assert positions_for(grid, 2, [(5, c) for c in range(9)]) == ((5, 4),)
    assert positions_for(grid, 2, [(r, 8) for r in range(9)]) == ((0, 8),)

    # Row 3 precedes row 5 and all columns; digit 6 precedes digit 8 in row 3.
    assert next_step(grid) == SolveStep(Technique.HIDDEN_SINGLE, 3, 4, 6)


def test_a_naked_single_precedes_a_distinct_earlier_hidden_single() -> None:
    grid = Grid.from_string(NAKED_PRIORITY_TEXT)
    assert candidates(grid, 2, 0) == frozenset({1, 4, 5, 7})
    assert positions_for(grid, 1, [(2, c) for c in range(9)]) == ((2, 0),)
    assert candidates(grid, 2, 8) == frozenset({7})

    assert next_step(grid) == SolveStep(Technique.NAKED_SINGLE, 2, 8, 7)
    # Detection priority does not prohibit explicitly applying a justified move.
    assert is_valid_grid(apply_step(grid, SolveStep(Technique.HIDDEN_SINGLE, 2, 0, 1)))


def test_two_candidate_occurrences_do_not_make_a_hidden_or_naked_single() -> None:
    solved = Grid.from_string(SOLVED_TEXT)
    holes = {3, 4, 30, 31}
    grid = Grid(tuple(0 if i in holes else v for i, v in enumerate(solved.cells)))
    assert all(candidates(grid, *divmod(i, 9)) == frozenset({6, 7}) for i in holes)
    assert positions_for(grid, 6, [(0, c) for c in range(9)]) == ((0, 3), (0, 4))
    assert positions_for(grid, 7, [(r, 3) for r in range(9)]) == ((0, 3), (3, 3))

    assert next_step(grid) is None


def test_empty_grid_has_no_singles() -> None:
    grid = Grid((0,) * 81)

    assert next_step(grid) is None


def test_a_hidden_single_with_other_candidates_cannot_be_declared_naked() -> None:
    grid = Grid.from_string(ROW_HIDDEN_TEXT)
    assert candidates(grid, 2, 0) == frozenset({1, 4, 5, 7})

    with pytest.raises(ValueError, match="technique"):
        apply_step(grid, SolveStep(Technique.NAKED_SINGLE, 2, 0, 1))
