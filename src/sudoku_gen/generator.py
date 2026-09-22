"""Seeded construction, carving, and bounded difficulty-targeted generation."""

from dataclasses import dataclass
from enum import Enum
from random import Random

from sudoku_gen.candidates import candidates
from sudoku_gen.difficulty import Difficulty, DifficultyReport, rate_difficulty
from sudoku_gen.exceptions import (
    DifficultyGenerationError,
    PuzzleBatchGenerationError,
    SudokuError,
)
from sudoku_gen.fingerprint import (
    FingerprintMode,
    GridFingerprint,
    deduplicate_puzzles,
    fingerprint_puzzle,
)
from sudoku_gen.human_solver import Technique
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.pattern import Symmetry
from sudoku_gen.solver import has_unique_solution
from sudoku_gen.validation import empty_cells, is_valid_solution


class DifficultyGenerationStrategy(Enum):
    """How difficulty-targeted candidates are carved.

    RANDOM_RETRY preserves the historical endpoint-only generation path.
    GUIDED_CARVING uses bounded logical feedback while carving one solution.
    """

    RANDOM_RETRY = "random_retry"
    GUIDED_CARVING = "guided_carving"


@dataclass(frozen=True, slots=True)
class GenerationWork:
    """Immutable bounded work counters, separate from candidate attempts."""

    outer_attempts: int = 0
    tentative_removal_evaluations: int = 0
    uniqueness_checks: int = 0
    difficulty_rating_evaluations: int = 0
    committed_removals: int = 0
    exact_difficulty_states: int = 0

    def __post_init__(self) -> None:
        for name, value in (
            ("outer_attempts", self.outer_attempts),
            ("tentative_removal_evaluations", self.tentative_removal_evaluations),
            ("uniqueness_checks", self.uniqueness_checks),
            ("difficulty_rating_evaluations", self.difficulty_rating_evaluations),
            ("committed_removals", self.committed_removals),
            ("exact_difficulty_states", self.exact_difficulty_states),
        ):
            if type(value) is not int:
                raise TypeError(f"{name} must be a built-in integer.")
            if value < 0:
                raise ValueError(f"{name} must not be negative.")

    def combined_with(self, other: "GenerationWork") -> "GenerationWork":
        """Return component-wise work totals without mutating either input."""
        if not isinstance(other, GenerationWork):
            raise TypeError("other must be a GenerationWork.")
        return GenerationWork(
            self.outer_attempts + other.outer_attempts,
            self.tentative_removal_evaluations + other.tentative_removal_evaluations,
            self.uniqueness_checks + other.uniqueness_checks,
            self.difficulty_rating_evaluations + other.difficulty_rating_evaluations,
            self.committed_removals + other.committed_removals,
            self.exact_difficulty_states + other.exact_difficulty_states,
        )


@dataclass(frozen=True, slots=True)
class DifficultyGeneratedPuzzle:
    """A uniquely solvable generated puzzle accepted by its exact difficulty."""

    puzzle: SudokuPuzzle
    difficulty_report: DifficultyReport
    attempts: int
    work: GenerationWork | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.puzzle, SudokuPuzzle):
            raise TypeError("puzzle must be a SudokuPuzzle.")
        if not isinstance(self.difficulty_report, DifficultyReport):
            raise TypeError("difficulty_report must be a DifficultyReport.")
        if type(self.attempts) is not int:
            raise TypeError("attempts must be a built-in integer.")
        if self.attempts < 1:
            raise ValueError("attempts must be at least 1.")
        if self.work is not None and not isinstance(self.work, GenerationWork):
            raise TypeError("work must be a GenerationWork or None.")


@dataclass(frozen=True, slots=True)
class PuzzleBatchItem:
    """One accepted puzzle, its exact rating, and selected identity."""

    puzzle: SudokuPuzzle
    difficulty_report: DifficultyReport
    fingerprint: GridFingerprint

    def __post_init__(self) -> None:
        if not isinstance(self.puzzle, SudokuPuzzle):
            raise TypeError("puzzle must be a SudokuPuzzle.")
        if not isinstance(self.difficulty_report, DifficultyReport):
            raise TypeError("difficulty_report must be a DifficultyReport.")
        if not isinstance(self.fingerprint, GridFingerprint):
            raise TypeError("fingerprint must be a GridFingerprint.")


@dataclass(frozen=True, slots=True)
class PuzzleBatch:
    """A completed, bounded batch of uniquely identified matching puzzles."""

    items: tuple[PuzzleBatchItem, ...]
    difficulty: Difficulty
    deduplication_mode: FingerprintMode
    attempts: int
    difficulty_rejections: int
    duplicate_rejections: int
    work: GenerationWork | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple):
            raise TypeError("items must be a tuple of PuzzleBatchItem instances.")
        if not all(isinstance(item, PuzzleBatchItem) for item in self.items):
            raise TypeError("items must contain only PuzzleBatchItem instances.")
        if not self.items:
            raise ValueError("items must contain at least one accepted puzzle.")
        _validate_requested_difficulty(self.difficulty)
        _validate_fingerprint_mode(self.deduplication_mode)
        for name, value in (
            ("attempts", self.attempts),
            ("difficulty_rejections", self.difficulty_rejections),
            ("duplicate_rejections", self.duplicate_rejections),
        ):
            if type(value) is not int:
                raise TypeError(f"{name} must be a built-in integer.")
            if value < 0:
                raise ValueError(f"{name} must not be negative.")
        if self.attempts < 1:
            raise ValueError("attempts must be at least 1.")
        if self.attempts != (
            len(self.items) + self.difficulty_rejections + self.duplicate_rejections
        ):
            raise ValueError("attempts must equal accepted and rejected candidates.")
        if any(
            item.difficulty_report.difficulty is not self.difficulty
            for item in self.items
        ):
            raise ValueError("Every item must match the batch difficulty.")
        if any(
            item.fingerprint.mode is not self.deduplication_mode for item in self.items
        ):
            raise ValueError("Every item fingerprint must use the batch mode.")
        if len(
            deduplicate_puzzles(
                (item.puzzle for item in self.items), mode=self.deduplication_mode
            )
        ) != len(self.items):
            raise ValueError("Batch items must have unique canonical identities.")
        if self.work is not None:
            if not isinstance(self.work, GenerationWork):
                raise TypeError("work must be a GenerationWork or None.")
            if self.work.outer_attempts != self.attempts:
                raise ValueError("work outer_attempts must equal batch attempts.")

    @property
    def accepted_count(self) -> int:
        """Return the number of accepted puzzles."""
        return len(self.items)


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
    _validate_target_clues(target_clues)
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
    strategy: DifficultyGenerationStrategy = DifficultyGenerationStrategy.RANDOM_RETRY,
    guided_width: int = 4,
) -> DifficultyGeneratedPuzzle:
    """Return a uniquely solvable puzzle with an exactly matching rating.

    RANDOM_RETRY preserves the historical endpoint-only path. GUIDED_CARVING
    evaluates a bounded local pool of unique clue removals while carving one
    solution per outer attempt. Both accept only an exact final rating.
    """
    _validate_requested_difficulty(difficulty)
    _validate_max_attempts(max_attempts)
    _validate_symmetry(symmetry)
    _validate_strategy(strategy)
    _validate_guided_width(guided_width)

    rng = _local_rng(seed)
    total_work = GenerationWork()
    for attempt in range(1, max_attempts + 1):
        puzzle, report, work = _generate_and_rate_candidate(
            rng,
            attempt,
            target_clues,
            symmetry,
            difficulty,
            strategy,
            guided_width,
        )
        total_work = total_work.combined_with(work)
        if report.difficulty is difficulty:
            return DifficultyGeneratedPuzzle(puzzle, report, attempt, total_work)
    raise DifficultyGenerationError(
        f"Could not generate a {difficulty.value} puzzle after {max_attempts} attempts."
    )


def generate_puzzle_batch(
    count: int,
    difficulty: Difficulty,
    *,
    seed: int | None = None,
    target_clues: int = 30,
    symmetry: Symmetry = Symmetry.NONE,
    deduplication_mode: FingerprintMode = FingerprintMode.DIGIT_NORMALIZED,
    max_attempts: int = 100,
    strategy: DifficultyGenerationStrategy = DifficultyGenerationStrategy.RANDOM_RETRY,
    guided_width: int = 4,
) -> PuzzleBatch:
    """Collect a bounded number of unique puzzles with one exact difficulty.

    A single local RNG derives one distinct candidate seed per global attempt.
    Candidates are rated once, then only exact difficulty matches are
    fingerprinted and deduplicated. The process stops at count acceptances or
    max_attempts total candidates; it has no per-puzzle retry loop.
    """
    _validate_count(count)
    _validate_requested_difficulty(difficulty)
    _validate_max_attempts(max_attempts)
    if max_attempts < count:
        raise ValueError("max_attempts must be at least count.")
    _validate_target_clues(target_clues)
    _validate_symmetry(symmetry)
    _validate_fingerprint_mode(deduplication_mode)
    _validate_strategy(strategy)
    _validate_guided_width(guided_width)

    rng = _local_rng(seed)
    items: list[PuzzleBatchItem] = []
    difficulty_rejections = 0
    duplicate_rejections = 0
    total_work = GenerationWork()
    for attempt in range(1, max_attempts + 1):
        puzzle, report, work = _generate_and_rate_candidate(
            rng,
            attempt,
            target_clues,
            symmetry,
            difficulty,
            strategy,
            guided_width,
        )
        total_work = total_work.combined_with(work)
        if report.difficulty is not difficulty:
            difficulty_rejections += 1
            continue
        fingerprint = fingerprint_puzzle(puzzle, deduplication_mode)
        accepted_puzzles = tuple(item.puzzle for item in items)
        if len(
            deduplicate_puzzles((*accepted_puzzles, puzzle), mode=deduplication_mode)
        ) < (len(items) + 1):
            duplicate_rejections += 1
            continue
        items.append(PuzzleBatchItem(puzzle, report, fingerprint))
        if len(items) == count:
            return PuzzleBatch(
                items=tuple(items),
                difficulty=difficulty,
                deduplication_mode=deduplication_mode,
                attempts=attempt,
                difficulty_rejections=difficulty_rejections,
                duplicate_rejections=duplicate_rejections,
                work=total_work,
            )
    raise PuzzleBatchGenerationError(
        "Could not generate the requested puzzle batch: "
        f"requested count={count}, accepted count={len(items)}, "
        f"difficulty={difficulty.value}, attempts={max_attempts}, "
        f"duplicate rejections={duplicate_rejections}."
    )


def _local_rng(seed: int | None) -> Random:
    if seed is not None and type(seed) is not int:
        raise TypeError("seed must be a built-in integer or None.")
    return Random(seed)


def _generate_and_rate_candidate(
    rng: Random,
    attempt: int,
    target_clues: int,
    symmetry: Symmetry,
    difficulty: Difficulty,
    strategy: DifficultyGenerationStrategy,
    guided_width: int,
) -> tuple[SudokuPuzzle, DifficultyReport, GenerationWork]:
    candidate_seed = _candidate_seed(rng, attempt)
    if strategy is DifficultyGenerationStrategy.RANDOM_RETRY:
        puzzle = generate_puzzle(
            seed=candidate_seed, target_clues=target_clues, symmetry=symmetry
        )
        report = rate_difficulty(puzzle.grid)
        return (
            puzzle,
            report,
            GenerationWork(
                outer_attempts=1,
                difficulty_rating_evaluations=1,
                exact_difficulty_states=int(report.difficulty is difficulty),
            ),
        )
    return _guided_candidate(
        candidate_seed, target_clues, symmetry, difficulty, guided_width
    )


def _candidate_seed(rng: Random, attempt: int) -> int:
    """Pair random bits and an attempt index injectively without a bound input."""
    random_component = rng.getrandbits(128)
    paired_sum = random_component + attempt
    return paired_sum * (paired_sum + 1) // 2 + attempt


def _guided_candidate(
    seed: int,
    target_clues: int,
    symmetry: Symmetry,
    requested: Difficulty,
    guided_width: int,
) -> tuple[SudokuPuzzle, DifficultyReport, GenerationWork]:
    """Carve one solution through bounded, target-aware logical feedback.

    Every iteration samples at most ``guided_width`` remaining clue groups from
    a local seeded RNG. It rates only unique tentative grids, commits the best
    deterministic guidance key, and never revisits a committed group. Exact
    ratings are retained along the trajectory by lowest clue count.
    """
    rng = _local_rng(seed)
    solution = _generate_solution(rng)
    current = solution
    current_report = rate_difficulty(current)
    remaining = 81
    groups = _removal_groups(symmetry)
    rng.shuffle(groups)
    available = groups.copy()
    tentative_evaluations = 0
    uniqueness_checks = 0
    rating_evaluations = 1
    committed_removals = 0
    exact_states = int(current_report.difficulty is requested)
    best_match: tuple[Grid, DifficultyReport, int] | None = (
        (current, current_report, remaining)
        if current_report.difficulty is requested
        else None
    )

    while available:
        eligible = [
            group for group in available if remaining - len(group) >= target_clues
        ]
        if not eligible:
            break
        pool = rng.sample(eligible, min(guided_width, len(eligible)))
        best: (
            tuple[
                tuple[int, int, int, int, int], tuple[int, ...], Grid, DifficultyReport
            ]
            | None
        ) = None
        permanently_rejected: list[tuple[int, ...]] = []
        for group in pool:
            tentative_evaluations += 1
            tentative = _remove_group(current, group)
            uniqueness_checks += 1
            if not has_unique_solution(tentative):
                permanently_rejected.append(group)
                continue
            report = rate_difficulty(tentative)
            rating_evaluations += 1
            if report.difficulty is requested:
                exact_states += 1
                clues = remaining - len(group)
                if best_match is None or clues < best_match[2]:
                    best_match = tentative, report, clues
            candidate = (_guidance_key(requested, report), group, tentative, report)
            if best is None or candidate[:2] < best[:2]:
                best = candidate
        if permanently_rejected:
            rejected = set(permanently_rejected)
            available = [group for group in available if group not in rejected]
        if best is None:
            continue
        _, chosen_group, current, current_report = best
        available.remove(chosen_group)
        remaining -= len(chosen_group)
        committed_removals += len(chosen_group)

    if best_match is not None:
        grid, report, _ = best_match
    else:
        grid, report = current, current_report
    work = GenerationWork(
        outer_attempts=1,
        tentative_removal_evaluations=tentative_evaluations,
        uniqueness_checks=uniqueness_checks,
        difficulty_rating_evaluations=rating_evaluations,
        committed_removals=committed_removals,
        exact_difficulty_states=exact_states,
    )
    return SudokuPuzzle(grid, solution), report, work


def _remove_group(grid: Grid, group: tuple[int, ...]) -> Grid:
    cells = list(grid.cells)
    for index in group:
        cells[index] = 0
    return Grid(tuple(cells))


def _removal_groups(symmetry: Symmetry) -> list[tuple[int, ...]]:
    if symmetry is Symmetry.NONE:
        return [(index,) for index in range(81)]
    return _rotational_orbits()


def _guidance_key(
    requested: Difficulty, report: DifficultyReport
) -> tuple[int, int, int, int, int]:
    """Rank one unique tentative state for a requested difficulty.

    Exact solved matches lead. Medium and Hard prefer solved lower bands before
    overshooting; Expert prefers solved advanced traces, then lower solved
    bands. UNRATED always ranks last, where its partial metrics only break ties.
    Within a tier, more recorded logical work is preferred to encourage carving
    complexity without using clue count as the primary signal.
    """
    if report.difficulty is Difficulty.UNRATED:
        tier = 4
    else:
        tiers = {
            Difficulty.EASY: {
                Difficulty.EASY: 0,
                Difficulty.MEDIUM: 1,
                Difficulty.HARD: 2,
                Difficulty.EXPERT: 3,
            },
            Difficulty.MEDIUM: {
                Difficulty.MEDIUM: 0,
                Difficulty.EASY: 1,
                Difficulty.HARD: 2,
                Difficulty.EXPERT: 3,
            },
            Difficulty.HARD: {
                Difficulty.HARD: 0,
                Difficulty.MEDIUM: 1,
                Difficulty.EASY: 2,
                Difficulty.EXPERT: 3,
            },
            Difficulty.EXPERT: {
                Difficulty.EXPERT: 0,
                Difficulty.HARD: 1,
                Difficulty.MEDIUM: 2,
                Difficulty.EASY: 3,
            },
        }
        tier = tiers[requested][report.difficulty]
    hardest_rank = (
        list(Technique).index(report.hardest_technique) + 1
        if report.hardest_technique is not None
        else 0
    )
    return (
        tier,
        -hardest_rank,
        -report.score,
        -report.candidate_elimination_count,
        -report.step_count,
    )


def _validate_count(count: int) -> None:
    if type(count) is not int:
        raise TypeError("count must be a built-in integer.")
    if count < 1:
        raise ValueError("count must be at least 1.")


def _validate_max_attempts(max_attempts: int) -> None:
    if type(max_attempts) is not int:
        raise TypeError("max_attempts must be a built-in integer.")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")


def _validate_target_clues(target_clues: int) -> None:
    if type(target_clues) is not int:
        raise TypeError("target_clues must be a built-in integer.")
    if not 17 <= target_clues <= 81:
        raise ValueError("target_clues must be between 17 and 81.")


def _validate_requested_difficulty(difficulty: Difficulty) -> None:
    if not isinstance(difficulty, Difficulty):
        raise TypeError("difficulty must be a Difficulty.")
    if difficulty is Difficulty.UNRATED:
        raise ValueError("UNRATED cannot be requested for puzzle generation.")


def _validate_fingerprint_mode(mode: FingerprintMode) -> None:
    if not isinstance(mode, FingerprintMode):
        raise TypeError("deduplication_mode must be a FingerprintMode.")


def _validate_symmetry(symmetry: Symmetry) -> None:
    if not isinstance(symmetry, Symmetry):
        raise TypeError("symmetry must be a Symmetry.")


def _validate_strategy(strategy: DifficultyGenerationStrategy) -> None:
    if not isinstance(strategy, DifficultyGenerationStrategy):
        raise TypeError("strategy must be a DifficultyGenerationStrategy.")


def _validate_guided_width(guided_width: int) -> None:
    if type(guided_width) is not int:
        raise TypeError("guided_width must be a built-in integer.")
    if guided_width < 1:
        raise ValueError("guided_width must be at least 1.")


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
