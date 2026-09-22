"""Seeded solution construction, carving, and bounded difficulty targeting."""

from dataclasses import dataclass
from random import Random

from sudoku_gen.candidates import candidates
from sudoku_gen.difficulty import Difficulty, DifficultyReport, rate_difficulty
from sudoku_gen.exceptions import DifficultyGenerationError, SudokuError
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.pattern import Symmetry
from sudoku_gen.solver import has_unique_solution
from sudoku_gen.validation import empty_cells, is_valid_solution


@dataclass(frozen=True, slots=True)
class DifficultyGeneratedPuzzle:
    """A uniquely solvable generated puzzle accepted by its exact difficulty."""

    puzzle: SudokuPuzzle
    difficulty_report: DifficultyReport
    attempts: int

    def __post_init__(self) -> None:
        if not isinstance(self.puzzle, SudokuPuzzle):
            raise TypeError("puzzle must be a SudokuPuzzle.")
        if not isinstance(self.difficulty_report, DifficultyReport):
            raise TypeError("difficulty_report must be a DifficultyReport.")
        if type(self.attempts) is not int:
            raise TypeError("attempts must be a built-in integer.")
        if self.attempts < 1:
            raise ValueError("attempts must be at least 1.")


def generate_solution(seed: int | None = None) -> Grid:
    """Construct a valid completed grid through randomized MRV backtracking.

    An explicit integer seed reproduces the same result for this generator
    version. None uses nondeterministic local seeding. Global random state is
    neither used nor modified.
    """
    return _generate_solution(_local_rng(seed))


def generate_puzzle(
    *,
    seed: int | None = None,
    target_clues: int = 30,
    symmetry: Symmetry = Symmetry.NONE,
) -> SudokuPuzzle:
    """Return a uniquely solvable puzzle together with its completed solution.

    target_clues must be a built-in integer from 17 through 81. Other types
    (including bool) raise TypeError; out-of-range values raise ValueError.
    One shuffled removal pass is made, accepting only uniquely solvable states.
    The result may have more clues than requested when the pass is exhausted,
    but never fewer. Clue count is not a difficulty rating or minimality claim.

    symmetry is a Symmetry. NONE retains the original individual-cell carving
    order. ROTATIONAL_180 removes complementary clue pairs (and the center cell)
    atomically, preserving the same lower-bound target semantics. Symmetry never
    breaks to reach an exact target.

    The same seed, target, and symmetry reproduce both solution and clue pattern
    for this generator version. One local RNG supplies all generation randomness.
    """
    if type(target_clues) is not int:
        raise TypeError("target_clues must be a built-in integer.")
    if not 17 <= target_clues <= 81:
        raise ValueError("target_clues must be between 17 and 81.")
    _validate_symmetry(symmetry)

    rng = _local_rng(seed)
    solution = _generate_solution(rng)
    grid = solution
    remaining = 81
    if symmetry is Symmetry.NONE:
        positions = list(range(81))
        rng.shuffle(positions)
        for index in positions:
            if remaining == target_clues:
                break
            tentative = Grid(grid.cells[:index] + (0,) + grid.cells[index + 1 :])
            if has_unique_solution(tentative):
                grid = tentative
                remaining -= 1
    else:
        orbits = _rotational_orbits()
        rng.shuffle(orbits)
        for orbit in orbits:
            if remaining - len(orbit) < target_clues:
                continue
            cells = list(grid.cells)
            for index in orbit:
                cells[index] = 0
            tentative = Grid(tuple(cells))
            if has_unique_solution(tentative):
                grid = tentative
                remaining -= len(orbit)
    return SudokuPuzzle(grid=grid, solution=solution)


def generate_puzzle_for_difficulty(
    difficulty: Difficulty,
    *,
    seed: int | None = None,
    target_clues: int = 30,
    max_attempts: int = 100,
    symmetry: Symmetry = Symmetry.NONE,
) -> DifficultyGeneratedPuzzle:
    """Return a uniquely solvable puzzle with an exactly matching rating.

    Each attempt uses a distinct seed derived from one local Random(seed), then
    delegates carving to generate_puzzle() and rates that one candidate once.
    The same explicit arguments therefore traverse the same candidate sequence.
    UNRATED candidates simply do not match. No fallback, guessing, or unbounded
    retry is used; DifficultyGenerationError reports a fully exhausted bound.
    """
    if not isinstance(difficulty, Difficulty):
        raise TypeError("difficulty must be a Difficulty.")
    if difficulty is Difficulty.UNRATED:
        raise ValueError("UNRATED cannot be requested for puzzle generation.")
    if type(max_attempts) is not int:
        raise TypeError("max_attempts must be a built-in integer.")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")
    _validate_symmetry(symmetry)

    rng = _local_rng(seed)
    for attempt in range(1, max_attempts + 1):
        # The remainder uniquely identifies the one-based attempt under this
        # bound, so even identical random draws cannot repeat a candidate seed.
        attempt_seed = rng.getrandbits(128) * max_attempts + attempt - 1
        puzzle = generate_puzzle(
            seed=attempt_seed, target_clues=target_clues, symmetry=symmetry
        )
        report = rate_difficulty(puzzle.grid)
        if report.difficulty is difficulty:
            return DifficultyGeneratedPuzzle(puzzle, report, attempt)
    raise DifficultyGenerationError(
        f"Could not generate a {difficulty.value} puzzle after {max_attempts} attempts."
    )


def _local_rng(seed: int | None) -> Random:
    if seed is not None and type(seed) is not int:
        raise TypeError("seed must be a built-in integer or None.")
    return Random(seed)


def _validate_symmetry(symmetry: Symmetry) -> None:
    if not isinstance(symmetry, Symmetry):
        raise TypeError("symmetry must be a Symmetry.")


def _rotational_orbits() -> list[tuple[int, ...]]:
    """Return the 40 paired and one center clue-position orbit exactly once."""
    return [(index, 80 - index) for index in range(40)] + [(40,)]


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
