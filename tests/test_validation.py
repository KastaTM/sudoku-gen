"""Sudoku unit access and rule validation without solving or mutating grids."""

from collections.abc import Callable

import pytest
from hypothesis import example, given, seed
from hypothesis import strategies as st

from sudoku_gen.models import Grid
from sudoku_gen.validation import (
    box_values,
    column_values,
    has_nonzero_duplicates,
    is_complete,
    is_valid_grid,
    is_valid_solution,
    row_values,
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
PARTIAL_TEXT = (
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
)


class IntSubclass(int):
    """Coordinates require built-in integers, matching the cell type convention."""


@pytest.mark.parametrize(("row", "expected"), tuple(enumerate(SOLVED_ROWS)))
def test_row_values_returns_each_row_left_to_right(row: int, expected: str) -> None:
    grid = Grid.from_string(SOLVED_TEXT)

    assert row_values(grid, row) == tuple(int(value) for value in expected)


@pytest.mark.parametrize(
    ("column", "expected"),
    [
        (0, "561847923"),
        (1, "379521684"),
        (2, "428963175"),
        (3, "613789542"),
        (4, "794652318"),
        (5, "852134796"),
        (6, "935478261"),
        (7, "146295837"),
        (8, "287316459"),
    ],
)
def test_column_values_returns_each_column_top_to_bottom(
    column: int, expected: str
) -> None:
    grid = Grid.from_string(SOLVED_TEXT)

    assert column_values(grid, column) == tuple(int(value) for value in expected)


@pytest.mark.parametrize(
    ("box_row", "box_column", "expected"),
    [
        (0, 0, "534672198"),
        (0, 1, "678195342"),
        (0, 2, "912348567"),
        (1, 0, "859426713"),
        (1, 1, "761853924"),
        (1, 2, "423791856"),
        (2, 0, "961287345"),
        (2, 1, "537419286"),
        (2, 2, "284635179"),
    ],
)
def test_box_values_returns_each_box_in_row_major_order(
    box_row: int, box_column: int, expected: str
) -> None:
    grid = Grid.from_string(SOLVED_TEXT)

    assert box_values(grid, box_row, box_column) == tuple(
        int(value) for value in expected
    )


def test_unit_extraction_preserves_empty_cells() -> None:
    grid = Grid.from_string(PARTIAL_TEXT)

    assert row_values(grid, 0) == (5, 3, 0, 0, 7, 0, 0, 0, 0)
    assert column_values(grid, 8) == (0, 0, 0, 3, 1, 6, 0, 5, 9)
    assert box_values(grid, 2, 1) == (0, 0, 0, 4, 1, 9, 0, 8, 0)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ((), False),
        ((0,) * 9, False),
        (tuple(range(1, 10)), False),
        ((0, 1, 0, 2, 0, 3, 0, 4, 0), False),
        ((1, 1), True),
        ((0, 9, 0, 9), True),
        ((1, 2, 3, 4, 5, 6, 7, 8, 1), True),
    ],
)
def test_duplicate_detection_ignores_zeroes(
    values: tuple[int, ...], expected: bool
) -> None:
    assert has_nonzero_duplicates(values) is expected


@pytest.mark.parametrize(
    ("values", "expected"),
    [((0, 1, 0, 2, 0), False), ((0, 1, 0, 2, 1), True)],
)
def test_duplicate_detection_accepts_a_one_shot_iterable(
    values: tuple[int, ...], expected: bool
) -> None:
    assert has_nonzero_duplicates(iter(values)) is expected


@pytest.mark.parametrize(
    ("text", "valid", "complete", "solution"),
    [
        pytest.param("0" * 81, True, False, False, id="empty"),
        pytest.param(PARTIAL_TEXT, True, False, False, id="valid-partial"),
        pytest.param(SOLVED_TEXT, True, True, True, id="solved"),
        pytest.param("1" * 81, False, True, False, id="complete-with-conflicts"),
        pytest.param(
            "11" + "0" * 79, False, False, False, id="incomplete-with-conflicts"
        ),
    ],
)
def test_validity_completeness_and_solution_are_distinct(
    text: str, valid: bool, complete: bool, solution: bool
) -> None:
    grid = Grid.from_string(text)

    assert is_valid_grid(grid) is valid
    assert is_complete(grid) is complete
    assert is_valid_solution(grid) is solution


@pytest.mark.parametrize(
    ("first", "second"),
    [
        *[
            pytest.param((row, 2), (row, 3), id=f"row-{row}-box-boundary")
            for row in range(9)
        ],
        *[
            pytest.param((2, column), (3, column), id=f"column-{column}-box-boundary")
            for column in range(9)
        ],
        *[
            pytest.param(
                (box_row * 3, box_column * 3),
                (box_row * 3 + 2, box_column * 3 + 2),
                id=f"box-{box_row}-{box_column}-only",
            )
            for box_row in range(3)
            for box_column in range(3)
        ],
        pytest.param((4, 5), (4, 6), id="middle-row-box-boundary"),
        pytest.param((8, 0), (8, 8), id="last-row-edges"),
        pytest.param((5, 4), (6, 4), id="middle-column-box-boundary"),
        pytest.param((0, 8), (8, 8), id="last-column-edges"),
    ],
)
def test_a_conflict_in_any_single_unit_makes_the_grid_invalid(
    first: tuple[int, int], second: tuple[int, int]
) -> None:
    cells = [0] * 81
    for row, column in (first, second):
        cells[row * 9 + column] = 7
    grid = Grid(tuple(cells))

    assert not is_valid_grid(grid)
    assert not is_valid_solution(grid)


@pytest.mark.parametrize(
    ("first", "second"),
    [((2, 2), (3, 3)), ((5, 5), (6, 6)), ((0, 8), (8, 0))],
)
def test_a_repeated_digit_in_distinct_units_is_valid(
    first: tuple[int, int], second: tuple[int, int]
) -> None:
    cells = [0] * 81
    for row, column in (first, second):
        cells[row * 9 + column] = 9

    assert is_valid_grid(Grid(tuple(cells)))


@pytest.mark.parametrize("index", [-10, -1, 9, 10])
@pytest.mark.parametrize("extract", [row_values, column_values])
def test_row_and_column_indices_outside_the_grid_raise_index_error(
    extract: Callable[[Grid, int], tuple[int, ...]], index: int
) -> None:
    grid = Grid.from_string(SOLVED_TEXT)

    with pytest.raises(IndexError):
        extract(grid, index)


@pytest.mark.parametrize("index", [-10, -1, 3, 9])
def test_each_box_coordinate_outside_zero_through_two_raises_index_error(
    index: int,
) -> None:
    grid = Grid.from_string(SOLVED_TEXT)

    with pytest.raises(IndexError):
        box_values(grid, index, 0)
    with pytest.raises(IndexError):
        box_values(grid, 0, index)


@pytest.mark.parametrize("index", [True, False, 1.0, "1", None, IntSubclass(1)])
@pytest.mark.parametrize("extract", [row_values, column_values])
def test_row_and_column_indices_require_builtin_integers(
    extract: Callable[[Grid, int], tuple[int, ...]], index: object
) -> None:
    grid = Grid.from_string(SOLVED_TEXT)

    with pytest.raises(TypeError):
        extract(grid, index)


@pytest.mark.parametrize("index", [True, False, 1.0, "1", None, IntSubclass(1)])
def test_each_box_coordinate_requires_a_builtin_integer(index: object) -> None:
    grid = Grid.from_string(SOLVED_TEXT)

    with pytest.raises(TypeError):
        box_values(grid, index, 0)
    with pytest.raises(TypeError):
        box_values(grid, 0, index)


def test_unit_access_and_validation_are_repeatable_and_leave_the_grid_unchanged() -> (
    None
):
    grid = Grid.from_string(PARTIAL_TEXT)
    original_cells = grid.cells
    original_hash = hash(grid)

    for _ in range(2):
        assert row_values(grid, 0) == (5, 3, 0, 0, 7, 0, 0, 0, 0)
        assert column_values(grid, 8) == (0, 0, 0, 3, 1, 6, 0, 5, 9)
        assert box_values(grid, 2, 1) == (0, 0, 0, 4, 1, 9, 0, 8, 0)
        assert is_valid_grid(grid)
        assert not is_complete(grid)
        assert not is_valid_solution(grid)

    assert grid.cells == original_cells
    assert grid.to_string() == PARTIAL_TEXT
    assert hash(grid) == original_hash


@seed(1201)
@given(removed=st.sets(st.integers(min_value=0, max_value=80)))
@example(removed=set())
@example(removed=set(range(81)))
def test_removing_any_clues_from_a_solution_preserves_validity(
    removed: set[int],
) -> None:
    solved = Grid.from_string(SOLVED_TEXT)
    grid = Grid(
        tuple(
            0 if index in removed else value for index, value in enumerate(solved.cells)
        )
    )

    assert is_valid_grid(grid)
    assert is_complete(grid) is (not removed)
    assert is_valid_solution(grid) is (not removed)
