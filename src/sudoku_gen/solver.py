"""Deterministic backtracking for solving, capped counting, and uniqueness."""

from collections.abc import Iterator

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
    return next(_search(grid), None)


def count_solutions(grid: Grid, limit: int = 2) -> int:
    """Count solutions up to limit; conflicting or unsatisfiable grids count as 0.

    The limit must be a built-in integer, excluding bool, and at least 1.
    Invalid types raise TypeError; non-positive values raise ValueError. Limit
    validation precedes Sudoku rule validation.

    A result equal to limit means at least that many solutions exist. Search
    stops at that point without exploring further solutions or mutating grid.
    """
    if type(limit) is not int:
        raise TypeError("limit must be a built-in integer.")
    if limit < 1:
        raise ValueError("limit must be at least 1.")
    if not is_valid_grid(grid):
        return 0

    count = 0
    for _ in _search(grid):
        count += 1
        if count == limit:
            break
    return count


def has_unique_solution(grid: Grid) -> bool:
    """Return whether exactly one solution exists, stopping at a second solution."""
    return count_solutions(grid, limit=2) == 1


def _search(grid: Grid) -> Iterator[Grid]:
    """Yield solutions of a consistent state in deterministic search order.

    Candidate placements preserve Sudoku constraints. Yielding each solution
    suspends traversal so callers can stop without exploring another branch.
    """
    selected: tuple[int, int, frozenset[int]] | None = None
    # Inspect every empty cell, even after a singleton, to catch dead ends.
    for row, column in empty_cells(grid):
        options = candidates(grid, row, column)
        if not options:
            return
        # Strict comparison retains the first (row-major) cell on an MRV tie.
        if selected is None or len(options) < len(selected[2]):
            selected = row, column, options

    if selected is None:
        if is_valid_solution(grid):
            yield grid
        return

    row, column, options = selected
    index = row * 9 + column
    for digit in sorted(options):
        # Only tentative placements create new immutable grid states.
        next_grid = Grid(grid.cells[:index] + (digit,) + grid.cells[index + 1 :])
        yield from _search(next_grid)
