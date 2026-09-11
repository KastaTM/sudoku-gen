"""Cell and unit access, and pure Sudoku rule checks for validated representations.

Rows and columns use indices 0 through 8. Boxes use (box_row, box_column)
coordinates, each from 0 through 2. Extracted units are immutable tuples.
"""

from collections.abc import Iterable

from sudoku_gen.models import Grid

_UNIT_SIZE = 9
_BOX_SIZE = 3


def _check_index(index: int, size: int, name: str) -> None:
    """Reject implicit conversions and Python's negative-index wrapping."""
    if type(index) is not int:
        raise TypeError(f"{name} must be a built-in integer; got {index!r}.")
    if not 0 <= index < size:
        raise IndexError(f"{name} must be between 0 and {size - 1}; got {index}.")


def cell_value(grid: Grid, row: int, column: int) -> int:
    """Read a cell using built-in integer coordinates from 0 through 8.

    Raise TypeError for other types (including bool), or IndexError for an
    out-of-range coordinate, consistently with unit access.
    """
    _check_index(row, _UNIT_SIZE, "row")
    _check_index(column, _UNIT_SIZE, "column")
    return grid.cells[row * _UNIT_SIZE + column]


def box_coordinates(row: int, column: int) -> tuple[int, int]:
    """Return the (box_row, box_column) containing a cell, each from 0 through 2.

    Cell coordinates must be built-in integers from 0 through 8. Raise TypeError
    for other types (including bool), or IndexError for an out-of-range value.
    """
    _check_index(row, _UNIT_SIZE, "row")
    _check_index(column, _UNIT_SIZE, "column")
    return row // _BOX_SIZE, column // _BOX_SIZE


def empty_cells(grid: Grid) -> tuple[tuple[int, int], ...]:
    """Return coordinates of all empty cells in deterministic row-major order."""
    return tuple(
        divmod(index, _UNIT_SIZE)
        for index, value in enumerate(grid.cells)
        if value == 0
    )


def clue_count(grid: Grid) -> int:
    """Return the number of non-zero cells, independently of Sudoku validity."""
    return sum(value != 0 for value in grid.cells)


def row_values(grid: Grid, row: int) -> tuple[int, ...]:
    """Return a row left to right; row must be an integer from 0 through 8.

    Raise TypeError for a non-integer (including bool), or IndexError if outside
    the allowed range.
    """
    _check_index(row, _UNIT_SIZE, "row")
    start = row * _UNIT_SIZE
    return grid.cells[start : start + _UNIT_SIZE]


def column_values(grid: Grid, column: int) -> tuple[int, ...]:
    """Return a column top to bottom; column must be an integer from 0 through 8.

    Raise TypeError for a non-integer (including bool), or IndexError if outside
    the allowed range.
    """
    _check_index(column, _UNIT_SIZE, "column")
    return grid.cells[column::_UNIT_SIZE]


def box_values(grid: Grid, box_row: int, box_column: int) -> tuple[int, ...]:
    """Return a 3x3 box in row-major order, using box coordinates 0 through 2.

    Raise TypeError for a non-integer (including bool), or IndexError if either
    coordinate is outside the allowed range.
    """
    _check_index(box_row, _BOX_SIZE, "box_row")
    _check_index(box_column, _BOX_SIZE, "box_column")
    start_row = box_row * _BOX_SIZE
    start_column = box_column * _BOX_SIZE
    return tuple(
        grid.cells[row * _UNIT_SIZE + column]
        for row in range(start_row, start_row + _BOX_SIZE)
        for column in range(start_column, start_column + _BOX_SIZE)
    )


def has_nonzero_duplicates(values: Iterable[int]) -> bool:
    """Return whether any non-zero value repeats in a unit.

    Values are expected to be Sudoku cells, as supplied by Grid. This helper
    checks only duplicates; it does not revalidate cell types or ranges.
    """
    filled_values = tuple(value for value in values if value != 0)
    return len(filled_values) != len(set(filled_values))


def is_valid_grid(grid: Grid) -> bool:
    """Return whether every row, column, and box has unique non-zero values.

    Empty and partially filled grids may be valid. This does not establish
    solvability or uniqueness of a solution.
    """
    return (
        all(
            not has_nonzero_duplicates(row_values(grid, row))
            for row in range(_UNIT_SIZE)
        )
        and all(
            not has_nonzero_duplicates(column_values(grid, column))
            for column in range(_UNIT_SIZE)
        )
        and all(
            not has_nonzero_duplicates(box_values(grid, box_row, box_column))
            for box_row in range(_BOX_SIZE)
            for box_column in range(_BOX_SIZE)
        )
    )


def is_complete(grid: Grid) -> bool:
    """Return whether every cell is filled, independently of Sudoku conflicts."""
    return 0 not in grid.cells


def is_valid_solution(grid: Grid) -> bool:
    """Return whether the grid is complete and satisfies all Sudoku rules.

    Grid limits values to 0 through 9, so a full unit with no duplicates must
    contain each digit from 1 through 9 exactly once.
    """
    return is_complete(grid) and is_valid_grid(grid)
