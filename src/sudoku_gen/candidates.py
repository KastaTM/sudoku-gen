"""Local candidate derivation without solving or whole-grid validation."""

from sudoku_gen.models import Grid
from sudoku_gen.validation import (
    box_coordinates,
    box_values,
    cell_value,
    column_values,
    row_values,
)

_DIGITS = frozenset(range(1, 10))


def candidates(grid: Grid, row: int, column: int) -> frozenset[int]:
    """Return digits absent from an empty cell's row, column, and box.

    Filled cells return an empty frozenset. An empty cell with no legal digits
    also returns an empty frozenset; use cell_value or empty_cells to distinguish
    the two cases.

    Only current unit values constrain candidates, even if the grid has conflicts
    elsewhere or within those units. No global validity or solvability check is
    performed. Zeroes never remove a candidate because candidates are in 1..9.

    Coordinates follow validation's zero-based convention: non-built-in integers
    raise TypeError, and values outside 0..8 raise IndexError.
    """
    if cell_value(grid, row, column) != 0:
        return frozenset()
    box_row, box_column = box_coordinates(row, column)
    return _DIGITS.difference(
        row_values(grid, row),
        column_values(grid, column),
        box_values(grid, box_row, box_column),
    )
