"""Deterministic backtracking to find one Sudoku solution."""

from sudoku_gen.candidates import candidates
from sudoku_gen.models import Grid
from sudoku_gen.validation import empty_cells, is_valid_grid, is_valid_solution


def solve(grid: Grid) -> Grid | None:
    """Return one valid solution, or None for a conflicting or unsatisfiable grid.

    The input is never mutated. A valid completed grid is returned unchanged.
    Minimum Remaining Values (MRV), row-major tie-breaking, and ascending digits
    make the chosen solution deterministic, including for ambiguous puzzles.
    This function does not count solutions or establish uniqueness.
    """
    if not is_valid_grid(grid):
        return None
    return _search(grid)


def _search(grid: Grid) -> Grid | None:
    """Search a consistent state; candidate placements preserve its constraints."""
    selected: tuple[int, int, frozenset[int]] | None = None
    # Inspect every empty cell, even after a singleton, to catch dead ends.
    for row, column in empty_cells(grid):
        options = candidates(grid, row, column)
        if not options:
            return None
        # Strict comparison retains the first (row-major) cell on an MRV tie.
        if selected is None or len(options) < len(selected[2]):
            selected = row, column, options

    if selected is None:
        return grid if is_valid_solution(grid) else None

    row, column, options = selected
    index = row * 9 + column
    for digit in sorted(options):
        # Only tentative placements create new immutable grid states.
        next_grid = Grid(grid.cells[:index] + (digit,) + grid.cells[index + 1 :])
        result = _search(next_grid)
        if result is not None:
            return result
    return None
