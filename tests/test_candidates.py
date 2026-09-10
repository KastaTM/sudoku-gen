"""Cell access and local candidate derivation without solving or mutation."""

from collections.abc import Callable

import pytest
from hypothesis import example, given, seed
from hypothesis import strategies as st

from sudoku_gen.candidates import candidates
from sudoku_gen.models import Grid
from sudoku_gen.validation import (
    box_coordinates,
    cell_value,
    empty_cells,
    is_valid_grid,
)

SOLVED_ROWS = (
    "534678912",
    "672195348",
    "198342567",
    "859761423",
    "426853791",
    "713924856",
    "961537284",
    "287419635",
    "345286179",
)
SOLVED_TEXT = "".join(SOLVED_ROWS)
DIGITS = frozenset(range(1, 10))
CORNERS_AND_CENTER = [(0, 0), (0, 8), (4, 4), (8, 0), (8, 8)]
BOX_MEMBERS = [
    ((0, 0), (0, 1, 2), (0, 1, 2)),
    ((0, 1), (0, 1, 2), (3, 4, 5)),
    ((0, 2), (0, 1, 2), (6, 7, 8)),
    ((1, 0), (3, 4, 5), (0, 1, 2)),
    ((1, 1), (3, 4, 5), (3, 4, 5)),
    ((1, 2), (3, 4, 5), (6, 7, 8)),
    ((2, 0), (6, 7, 8), (0, 1, 2)),
    ((2, 1), (6, 7, 8), (3, 4, 5)),
    ((2, 2), (6, 7, 8), (6, 7, 8)),
]


class IntSubclass(int):
    """Coordinates require built-in integers, as in Phase 1.2."""


def grid_with_clues(clues: dict[tuple[int, int], int]) -> Grid:
    """Build a fixed test position from explicitly specified clues."""
    cells = [0] * 81
    for (row, column), digit in clues.items():
        cells[row * 9 + column] = digit
    return Grid(tuple(cells))


@pytest.mark.parametrize(
    ("row", "column", "expected"),
    [
        (row, column, int(character))
        for row, text in enumerate(SOLVED_ROWS)
        for column, character in enumerate(text)
    ],
)
def test_cell_value_reads_each_cell_in_row_major_order(
    row: int, column: int, expected: int
) -> None:
    assert cell_value(Grid.from_string(SOLVED_TEXT), row, column) == expected


def test_cell_value_preserves_zero_for_an_empty_cell() -> None:
    assert cell_value(Grid((0,) * 81), 8, 8) == 0


@pytest.mark.parametrize(
    ("row", "column", "expected"),
    [
        (row, column, box)
        for box, rows, columns in BOX_MEMBERS
        for row in rows
        for column in columns
    ],
)
def test_box_coordinates_maps_every_cell_including_box_boundaries(
    row: int, column: int, expected: tuple[int, int]
) -> None:
    result = box_coordinates(row, column)

    assert isinstance(result, tuple)
    assert result == expected


def test_empty_grid_lists_all_cells_in_row_major_order() -> None:
    result = empty_cells(Grid((0,) * 81))

    assert result == tuple((row, column) for row in range(9) for column in range(9))
    assert isinstance(result, tuple)
    assert all(isinstance(coordinate, tuple) for coordinate in result)


def test_solved_grid_has_no_empty_cells() -> None:
    assert empty_cells(Grid.from_string(SOLVED_TEXT)) == ()


def test_empty_cells_skips_clues_and_preserves_order_across_row_boundaries() -> None:
    removed = ((0, 0), (0, 8), (1, 0), (2, 8), (3, 0), (4, 4), (8, 8))
    cells = list(Grid.from_string(SOLVED_TEXT).cells)
    for row, column in removed:
        cells[row * 9 + column] = 0

    assert empty_cells(Grid(tuple(cells))) == removed


def test_empty_cells_does_not_require_a_valid_sudoku_state() -> None:
    grid = Grid.from_string("11" + "0" * 78 + "2")

    assert not is_valid_grid(grid)
    assert empty_cells(grid) == tuple(divmod(index, 9) for index in range(2, 80))


@pytest.mark.parametrize(("row", "column"), CORNERS_AND_CENTER)
def test_empty_grid_allows_every_digit_at_corners_and_center(
    row: int, column: int
) -> None:
    result = candidates(Grid((0,) * 81), row, column)

    assert isinstance(result, frozenset)
    assert result == DIGITS


def test_candidates_exclude_row_digits_even_outside_the_cells_box() -> None:
    grid = grid_with_clues({(4, 0): 1, (4, 8): 2})

    assert candidates(grid, 4, 4) == frozenset({3, 4, 5, 6, 7, 8, 9})


def test_candidates_exclude_column_digits_even_outside_the_cells_box() -> None:
    grid = grid_with_clues({(0, 4): 3, (8, 4): 4})

    assert candidates(grid, 4, 4) == frozenset({1, 2, 5, 6, 7, 8, 9})


def test_candidates_exclude_box_digits_outside_the_cells_row_and_column() -> None:
    grid = grid_with_clues({(3, 3): 5, (5, 5): 6})

    assert candidates(grid, 4, 4) == frozenset({1, 2, 3, 4, 7, 8, 9})


def test_candidates_combine_row_column_and_box_constraints() -> None:
    grid = grid_with_clues(
        {(4, 0): 1, (4, 8): 2, (0, 4): 3, (8, 4): 4, (3, 3): 5, (5, 5): 6}
    )

    assert candidates(grid, 4, 4) == frozenset({7, 8, 9})


def test_only_nine_remains_when_one_through_eight_are_used() -> None:
    grid = grid_with_clues({(0, column): column for column in range(1, 9)})

    assert candidates(grid, 0, 0) == frozenset({9})


def test_a_valid_partial_grid_can_have_an_empty_cell_with_no_candidates() -> None:
    clues = {(0, column): column for column in range(1, 9)}
    clues[3, 0] = 9
    grid = grid_with_clues(clues)

    assert is_valid_grid(grid)
    assert cell_value(grid, 0, 0) == 0
    assert candidates(grid, 0, 0) == frozenset()


def test_a_digit_constrained_by_multiple_units_is_excluded_once() -> None:
    grid = grid_with_clues({(4, 0): 7, (0, 4): 7, (3, 3): 7})

    assert is_valid_grid(grid)
    assert candidates(grid, 4, 4) == frozenset({1, 2, 3, 4, 5, 6, 8, 9})


def test_duplicate_clues_in_a_unit_still_define_local_candidates() -> None:
    grid = grid_with_clues({(4, 0): 7, (4, 8): 7})

    assert not is_valid_grid(grid)
    assert candidates(grid, 4, 4) == frozenset({1, 2, 3, 4, 5, 6, 8, 9})


def test_an_unrelated_conflict_does_not_reject_or_constrain_the_cell() -> None:
    grid = grid_with_clues({(0, 0): 1, (0, 1): 1})

    assert not is_valid_grid(grid)
    assert candidates(grid, 8, 8) == DIGITS


@pytest.mark.parametrize(("row", "column"), CORNERS_AND_CENTER)
def test_removing_a_solution_digit_leaves_exactly_that_candidate(
    row: int, column: int
) -> None:
    cells = list(Grid.from_string(SOLVED_TEXT).cells)
    digit = cells[row * 9 + column]
    cells[row * 9 + column] = 0

    assert candidates(Grid(tuple(cells)), row, column) == frozenset({digit})


@pytest.mark.parametrize("digit", range(1, 10))
def test_a_filled_cell_returns_an_empty_frozenset(digit: int) -> None:
    grid = grid_with_clues({(4, 4): digit})

    result = candidates(grid, 4, 4)

    assert isinstance(result, frozenset)
    assert result == frozenset()


@pytest.mark.parametrize("index", [-10, -1, 9, 10, 81])
@pytest.mark.parametrize("access", [cell_value, candidates])
def test_each_cell_coordinate_outside_zero_through_eight_raises_index_error(
    access: Callable[[Grid, int, int], int | frozenset[int]], index: int
) -> None:
    # All cells are filled, so candidate requests must validate before returning.
    grid = Grid.from_string(SOLVED_TEXT)

    with pytest.raises(IndexError):
        access(grid, index, 0)
    with pytest.raises(IndexError):
        access(grid, 0, index)


@pytest.mark.parametrize("index", [-10, -1, 9, 10, 81])
def test_box_determination_rejects_out_of_range_cell_coordinates(index: int) -> None:
    with pytest.raises(IndexError):
        box_coordinates(index, 0)
    with pytest.raises(IndexError):
        box_coordinates(0, index)


@pytest.mark.parametrize("index", [True, False, 1.0, "1", None, IntSubclass(1)])
@pytest.mark.parametrize("access", [cell_value, candidates])
def test_each_cell_coordinate_requires_a_builtin_integer(
    access: Callable[[Grid, int, int], int | frozenset[int]], index: object
) -> None:
    grid = Grid.from_string(SOLVED_TEXT)

    with pytest.raises(TypeError):
        access(grid, index, 0)
    with pytest.raises(TypeError):
        access(grid, 0, index)


@pytest.mark.parametrize("index", [True, False, 1.0, "1", None, IntSubclass(1)])
def test_box_determination_requires_builtin_integer_cell_coordinates(
    index: object,
) -> None:
    with pytest.raises(TypeError):
        box_coordinates(index, 0)
    with pytest.raises(TypeError):
        box_coordinates(0, index)


def test_candidate_and_cell_queries_are_repeatable_and_do_not_mutate_the_grid() -> None:
    grid = grid_with_clues({(4, 0): 1, (0, 4): 2, (3, 3): 3})
    original_cells = grid.cells
    original_text = grid.to_string()
    original_hash = hash(grid)
    locations = empty_cells(grid)

    for _ in range(2):
        assert cell_value(grid, 4, 4) == 0
        assert box_coordinates(4, 4) == (1, 1)
        assert empty_cells(grid) == locations
        assert candidates(grid, 4, 4) == frozenset({4, 5, 6, 7, 8, 9})

    with pytest.raises(TypeError):
        locations[0] = (8, 8)
    with pytest.raises(TypeError):
        locations[0][0] = 8
    result = candidates(grid, 4, 4)
    with pytest.raises(AttributeError):
        result.add(1)

    assert grid.cells == original_cells
    assert grid.to_string() == original_text
    assert hash(grid) == original_hash


@seed(1301)
@given(
    removed=st.sets(st.integers(min_value=0, max_value=80)),
    target=st.integers(min_value=0, max_value=80),
)
@example(removed=set(), target=0)
@example(removed=set(range(81)), target=80)
def test_candidates_are_exactly_the_digits_that_preserve_partial_grid_validity(
    removed: set[int], target: int
) -> None:
    solved = Grid.from_string(SOLVED_TEXT)
    cells = tuple(
        0 if index == target or index in removed else digit
        for index, digit in enumerate(solved.cells)
    )
    grid = Grid(cells)
    row, column = divmod(target, 9)

    result = candidates(grid, row, column)

    assert result <= DIGITS
    assert solved.cells[target] in result
    for digit in range(1, 10):
        placed = Grid(cells[:target] + (digit,) + cells[target + 1 :])
        assert (digit in result) is is_valid_grid(placed)
