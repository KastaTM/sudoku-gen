"""Seeded solution construction and puzzle carving with preserved uniqueness."""

from random import Random

from sudoku_gen.candidates import candidates
from sudoku_gen.exceptions import SudokuError
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.solver import has_unique_solution
from sudoku_gen.validation import empty_cells, is_valid_solution


def generate_solution(seed: int | None = None) -> Grid:
    """Construct a valid completed grid through randomized MRV backtracking.

    An explicit integer seed reproduces the same result for this generator
    version. None uses nondeterministic local seeding. Global random state is
    neither used nor modified.
    """
    return _generate_solution(_local_rng(seed))


def generate_puzzle(*, seed: int | None = None, target_clues: int = 30) -> SudokuPuzzle:
    """Return a uniquely solvable puzzle together with its completed solution.

    target_clues must be a built-in integer from 17 through 81. Other types
    (including bool) raise TypeError; out-of-range values raise ValueError.
    One shuffled removal pass is made, accepting only uniquely solvable states.
    The result may have more clues than requested when the pass is exhausted,
    but never fewer. Clue count is not a difficulty rating or minimality claim.

    The same seed and target reproduce both the solution and clue pattern for
    this generator version. One local RNG supplies all generation randomness.
    """
    if type(target_clues) is not int:
        raise TypeError("target_clues must be a built-in integer.")
    if not 17 <= target_clues <= 81:
        raise ValueError("target_clues must be between 17 and 81.")

    rng = _local_rng(seed)
    solution = _generate_solution(rng)
    grid = solution
    remaining = 81
    positions = list(range(81))
    rng.shuffle(positions)
    for index in positions:
        if remaining == target_clues:
            break
        tentative = Grid(grid.cells[:index] + (0,) + grid.cells[index + 1 :])
        if has_unique_solution(tentative):
            grid = tentative
            remaining -= 1
    return SudokuPuzzle(grid=grid, solution=solution)


def _local_rng(seed: int | None) -> Random:
    if seed is not None and type(seed) is not int:
        raise TypeError("seed must be a built-in integer or None.")
    return Random(seed)


def _generate_solution(rng: Random) -> Grid:
    solution = _fill(Grid((0,) * 81), rng)
    if solution is None:
        # Exhaustive search from an empty Sudoku must find a valid completion.
        raise SudokuError("Could not construct a completed Sudoku solution.")
    return solution


def _fill(grid: Grid, rng: Random) -> Grid | None:
    """Preserve constraints while randomizing tied MRV cells and candidate order."""
    choices: list[tuple[int, int, frozenset[int]]] = []
    smallest_count = 10
    for row, column in empty_cells(grid):
        options = candidates(grid, row, column)
        if not options:
            return None
        if len(options) < smallest_count:
            choices = [(row, column, options)]
            smallest_count = len(options)
        elif len(options) == smallest_count:
            choices.append((row, column, options))

    if not choices:
        return grid if is_valid_solution(grid) else None

    row, column, options = rng.choice(choices)
    # Sort first so the seeded shuffle never depends on set iteration order.
    digits = sorted(options)
    rng.shuffle(digits)
    index = row * 9 + column
    for digit in digits:
        next_grid = Grid(grid.cells[:index] + (digit,) + grid.cells[index + 1 :])
        result = _fill(next_grid, rng)
        if result is not None:
            return result
    return None
