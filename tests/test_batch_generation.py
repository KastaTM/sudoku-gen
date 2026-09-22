"""Bounded, deterministic batch generation orchestration tests."""

import random
from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import pytest

from sudoku_gen import generator
from sudoku_gen.difficulty import Difficulty, DifficultyReport
from sudoku_gen.exceptions import PuzzleBatchGenerationError, SudokuError
from sudoku_gen.fingerprint import FingerprintMode, fingerprint_puzzle
from sudoku_gen.generator import PuzzleBatch, generate_puzzle_batch
from sudoku_gen.human_solver import LogicalSolveStatus
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.pattern import Symmetry
from sudoku_gen.solver import has_unique_solution
from sudoku_gen.validation import is_valid_grid, is_valid_solution

GRID_TEXT = (
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
)


class IntSubclass(int):
    """Batch counts use the existing built-in integer convention."""


def report_for(difficulty: Difficulty) -> DifficultyReport:
    return DifficultyReport(difficulty, 0, None, 0, 0, 0, 0, LogicalSolveStatus.SOLVED)


def relabel(grid: Grid) -> Grid:
    mapping = {1: 7, 2: 1, 3: 9, 4: 2, 5: 8, 6: 3, 7: 6, 8: 4, 9: 5}
    return Grid(tuple(mapping.get(value, 0) if value else 0 for value in grid.cells))


def move_first_clue(grid: Grid) -> Grid:
    cells = list(grid.cells)
    source = next(index for index, value in enumerate(cells) if value != 0)
    destination = next(index for index, value in enumerate(cells) if value == 0)
    cells[destination] = cells[source]
    cells[source] = 0
    return Grid(tuple(cells))


def install_candidates(
    monkeypatch: pytest.MonkeyPatch,
    puzzles: list[SudokuPuzzle],
    reports: list[DifficultyReport],
) -> tuple[list[int | None], list[Grid]]:
    puzzle_iterator: Iterator[SudokuPuzzle] = iter(puzzles)
    report_iterator: Iterator[DifficultyReport] = iter(reports)
    seeds: list[int | None] = []
    rated: list[Grid] = []

    def generate_candidate(
        *, seed: int | None, target_clues: int, symmetry: Symmetry
    ) -> SudokuPuzzle:
        assert target_clues == 30
        assert symmetry is Symmetry.NONE
        seeds.append(seed)
        return next(puzzle_iterator)

    def rate_candidate(grid: Grid) -> DifficultyReport:
        rated.append(grid)
        return next(report_iterator)

    monkeypatch.setattr(generator, "generate_puzzle", generate_candidate)
    monkeypatch.setattr(generator, "rate_difficulty", rate_candidate)
    return seeds, rated


def test_batch_continues_after_difficulty_and_duplicate_rejections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = SudokuPuzzle(Grid.from_string(GRID_TEXT))
    relabeled_puzzle = SudokuPuzzle(relabel(base.grid))
    distinct = SudokuPuzzle(move_first_clue(base.grid))
    seeds, rated = install_candidates(
        monkeypatch,
        [base, base, relabeled_puzzle, distinct],
        [
            report_for(Difficulty.MEDIUM),
            report_for(Difficulty.EASY),
            report_for(Difficulty.EASY),
            report_for(Difficulty.EASY),
        ],
    )
    fingerprinted: list[SudokuPuzzle] = []
    real_fingerprint = fingerprint_puzzle

    def record_fingerprint(puzzle: SudokuPuzzle, mode: FingerprintMode) -> object:
        fingerprinted.append(puzzle)
        return real_fingerprint(puzzle, mode)

    monkeypatch.setattr(generator, "fingerprint_puzzle", record_fingerprint)

    batch = generate_puzzle_batch(2, Difficulty.EASY, seed=13, max_attempts=4)

    assert tuple(item.puzzle for item in batch.items) == (base, distinct)
    assert batch.attempts == len(seeds) == len(rated) == 4
    assert batch.difficulty_rejections == 1
    assert batch.duplicate_rejections == 1
    assert batch.accepted_count == 2
    assert fingerprinted == [base, relabeled_puzzle, distinct]
    assert len({seed for seed in seeds if seed is not None}) == 4


def test_deduplication_modes_control_which_matching_candidates_are_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = SudokuPuzzle(Grid.from_string(GRID_TEXT))
    relabeled_puzzle = SudokuPuzzle(relabel(base.grid))
    shifted = SudokuPuzzle(move_first_clue(base.grid))

    exact_seeds, _ = install_candidates(
        monkeypatch,
        [base, relabeled_puzzle],
        [report_for(Difficulty.EASY), report_for(Difficulty.EASY)],
    )
    exact = generate_puzzle_batch(
        2,
        Difficulty.EASY,
        seed=14,
        deduplication_mode=FingerprintMode.EXACT,
        max_attempts=2,
    )
    assert tuple(item.puzzle for item in exact.items) == (base, relabeled_puzzle)
    assert exact.duplicate_rejections == 0
    assert len(exact_seeds) == 2

    normalized_seeds, _ = install_candidates(
        monkeypatch,
        [base, relabeled_puzzle, shifted],
        [report_for(Difficulty.EASY)] * 3,
    )
    normalized = generate_puzzle_batch(2, Difficulty.EASY, seed=14, max_attempts=3)
    assert tuple(item.puzzle for item in normalized.items) == (base, shifted)
    assert normalized.deduplication_mode is FingerprintMode.DIGIT_NORMALIZED
    assert normalized.duplicate_rejections == 1
    assert len(normalized_seeds) == 3

    pattern_seeds, _ = install_candidates(
        monkeypatch,
        [base, relabeled_puzzle, shifted],
        [report_for(Difficulty.EASY)] * 3,
    )
    pattern = generate_puzzle_batch(
        2,
        Difficulty.EASY,
        seed=14,
        deduplication_mode=FingerprintMode.CLUE_PATTERN,
        max_attempts=3,
    )
    assert tuple(item.puzzle for item in pattern.items) == (base, shifted)
    assert pattern.duplicate_rejections == 1
    assert len(pattern_seeds) == 3


def test_candidate_seed_prefix_is_repeatable_and_independent_of_attempt_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    puzzle = SudokuPuzzle(Grid.from_string(GRID_TEXT))
    seed_sequences: list[list[int | None]] = []

    def run(max_attempts: int) -> PuzzleBatch:
        seeds, _ = install_candidates(
            monkeypatch,
            [puzzle, puzzle],
            [report_for(Difficulty.MEDIUM), report_for(Difficulty.EASY)],
        )
        batch = generate_puzzle_batch(
            1, Difficulty.EASY, seed=15, max_attempts=max_attempts
        )
        seed_sequences.append(seeds)
        return batch

    assert run(2) == run(3)
    assert seed_sequences[0] == seed_sequences[1][:2]
    assert len(set(seed_sequences[0])) == 2


def test_final_attempt_success_and_early_completion_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    puzzle = SudokuPuzzle(Grid.from_string(GRID_TEXT))
    final_seeds, final_ratings = install_candidates(
        monkeypatch,
        [puzzle, puzzle, puzzle],
        [
            report_for(Difficulty.MEDIUM),
            report_for(Difficulty.HARD),
            report_for(Difficulty.EASY),
        ],
    )
    final = generate_puzzle_batch(1, Difficulty.EASY, seed=16, max_attempts=3)
    assert final.attempts == len(final_seeds) == len(final_ratings) == 3

    early_seeds, early_ratings = install_candidates(
        monkeypatch,
        [puzzle, puzzle],
        [report_for(Difficulty.EASY), report_for(Difficulty.EASY)],
    )
    early = generate_puzzle_batch(1, Difficulty.EASY, seed=16, max_attempts=2)
    assert early.attempts == len(early_seeds) == len(early_ratings) == 1


def test_exhaustion_reports_complete_accounting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    puzzle = SudokuPuzzle(Grid.from_string(GRID_TEXT))
    seeds, ratings = install_candidates(
        monkeypatch,
        [puzzle, puzzle, puzzle],
        [report_for(Difficulty.UNRATED)] * 3,
    )

    with pytest.raises(PuzzleBatchGenerationError) as error:
        generate_puzzle_batch(2, Difficulty.HARD, seed=17, max_attempts=3)

    assert isinstance(error.value, SudokuError)
    assert "requested count=2" in str(error.value)
    assert "accepted count=0" in str(error.value)
    assert "difficulty=hard" in str(error.value)
    assert "attempts=3" in str(error.value)
    assert "duplicate rejections=0" in str(error.value)
    assert len(seeds) == len(ratings) == 3


def test_result_models_are_immutable_hashable_and_account_for_every_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    puzzle = SudokuPuzzle(Grid.from_string(GRID_TEXT))
    install_candidates(monkeypatch, [puzzle], [report_for(Difficulty.EASY)])

    batch = generate_puzzle_batch(1, Difficulty.EASY, seed=18, max_attempts=1)

    assert hash(batch) == hash(batch)
    assert batch.items[0].fingerprint == fingerprint_puzzle(
        puzzle, batch.deduplication_mode
    )
    with pytest.raises(FrozenInstanceError):
        batch.items = ()
    with pytest.raises(FrozenInstanceError):
        batch.items[0].puzzle = puzzle


@pytest.mark.parametrize("count", [None, True, False, 1.0, "1", IntSubclass(1)])
def test_count_requires_a_builtin_positive_integer(count: object) -> None:
    with pytest.raises(TypeError):
        generate_puzzle_batch(count, Difficulty.EASY)


@pytest.mark.parametrize("count", [0, -1])
def test_count_must_be_positive(count: int) -> None:
    with pytest.raises(ValueError):
        generate_puzzle_batch(count, Difficulty.EASY)


@pytest.mark.parametrize("max_attempts", [None, True, 1.0, "1", IntSubclass(1)])
def test_max_attempts_requires_a_builtin_integer(max_attempts: object) -> None:
    with pytest.raises(TypeError):
        generate_puzzle_batch(1, Difficulty.EASY, max_attempts=max_attempts)


@pytest.mark.parametrize("max_attempts", [0, -1])
def test_max_attempts_must_be_positive(max_attempts: int) -> None:
    with pytest.raises(ValueError):
        generate_puzzle_batch(1, Difficulty.EASY, max_attempts=max_attempts)


def test_max_attempts_below_count_is_rejected_before_generation() -> None:
    with pytest.raises(ValueError, match="at least count"):
        generate_puzzle_batch(2, Difficulty.EASY, max_attempts=1)


@pytest.mark.parametrize("difficulty", [None, True, "easy", Difficulty.UNRATED])
def test_batch_difficulty_is_limited_to_normal_enum_values(difficulty: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        generate_puzzle_batch(1, difficulty)


@pytest.mark.parametrize("symmetry", [None, "none", True])
@pytest.mark.parametrize("mode", [None, "exact", True])
@pytest.mark.parametrize("target_clues", [True, 16, 82])
def test_batch_rejects_invalid_existing_generation_options(
    symmetry: object, mode: object, target_clues: object
) -> None:
    with pytest.raises((TypeError, ValueError)):
        generate_puzzle_batch(
            1,
            Difficulty.EASY,
            target_clues=target_clues,
            symmetry=symmetry,
            deduplication_mode=mode,
        )


def test_real_easy_batch_is_repeatable_valid_and_unique() -> None:
    first = generate_puzzle_batch(
        2, Difficulty.EASY, seed=2027, target_clues=81, max_attempts=2
    )
    second = generate_puzzle_batch(
        2, Difficulty.EASY, seed=2027, target_clues=81, max_attempts=2
    )

    assert first == second
    assert first.attempts == first.accepted_count == 2
    assert first.difficulty_rejections == first.duplicate_rejections == 0
    for item in first.items:
        assert item.difficulty_report.difficulty is Difficulty.EASY
        assert item.puzzle.solution is not None
        assert is_valid_grid(item.puzzle.grid)
        assert is_valid_solution(item.puzzle.solution)
        assert has_unique_solution(item.puzzle.grid)


def test_batch_generation_preserves_global_random_state() -> None:
    original_state = random.getstate()
    try:
        random.seed(2028)
        expected = random.Random(2028)
        assert random.random() == expected.random()

        generate_puzzle_batch(
            2, Difficulty.EASY, seed=2029, target_clues=81, max_attempts=2
        )

        assert random.getstate() == expected.getstate()
        assert [random.random() for _ in range(5)] == [
            expected.random() for _ in range(5)
        ]
    finally:
        random.setstate(original_state)
