"""Bounded, deterministic orchestration for difficulty-targeted generation."""

import random
from dataclasses import FrozenInstanceError

import pytest

from sudoku_gen import generator
from sudoku_gen.difficulty import Difficulty, DifficultyReport, rate_difficulty
from sudoku_gen.exceptions import DifficultyGenerationError, SudokuError
from sudoku_gen.generator import (
    DifficultyGeneratedPuzzle,
    generate_puzzle_for_difficulty,
)
from sudoku_gen.human_solver import LogicalSolveStatus
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.solver import has_unique_solution, solve
from sudoku_gen.validation import clue_count, is_valid_grid, is_valid_solution

SOLVED_TEXT = (
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)
DIFFICULTY_FIXTURES = {
    Difficulty.EASY: (
        "100000050000108900070000600067030509020009070000200038039670000080000300000400000"
    ),
    Difficulty.MEDIUM: (
        "700000090000090008301020000100034000000100040000000083600005000074903605210000070"
    ),
    Difficulty.HARD: (
        "040080105050900002600000000300002000708300000520000301800209070000000006200850000"
    ),
    Difficulty.EXPERT: (
        "004607000003000900600000000700806109000900640010020050000142080008500004000080000"
    ),
}


class IntSubclass(int):
    """Targeted parameters follow the existing built-in integer convention."""


def report_for(difficulty: Difficulty) -> DifficultyReport:
    return DifficultyReport(difficulty, 0, None, 0, 0, 0, 0, LogicalSolveStatus.SOLVED)


def puzzle_for(text: str) -> SudokuPuzzle:
    grid = Grid.from_string(text)
    solution = solve(grid)
    assert isinstance(solution, Grid)
    return SudokuPuzzle(grid, solution)


def test_real_target_eighty_one_easy_generation_is_valid_unique_and_repeatable() -> (
    None
):
    first = generate_puzzle_for_difficulty(
        Difficulty.EASY, seed=1710, target_clues=81, max_attempts=1
    )
    second = generate_puzzle_for_difficulty(
        Difficulty.EASY, seed=1710, target_clues=81, max_attempts=1
    )

    assert first == second
    assert first.attempts == 1
    assert first.difficulty_report == rate_difficulty(first.puzzle.grid)
    assert first.difficulty_report.difficulty is Difficulty.EASY
    assert first.puzzle.grid == first.puzzle.solution
    assert clue_count(first.puzzle.grid) == 81
    assert is_valid_solution(first.puzzle.grid)
    assert has_unique_solution(first.puzzle.grid)


@pytest.mark.parametrize("requested", list(DIFFICULTY_FIXTURES))
def test_each_normal_difficulty_accepts_an_exactly_matching_candidate(
    monkeypatch: pytest.MonkeyPatch, requested: Difficulty
) -> None:
    puzzle = puzzle_for(DIFFICULTY_FIXTURES[requested])
    generated: list[int | None] = []
    rated: list[Grid] = []

    def generate_candidate(*, seed: int | None, target_clues: int) -> SudokuPuzzle:
        generated.append(seed)
        assert target_clues == 25
        return puzzle

    def rate_candidate(grid: Grid) -> DifficultyReport:
        rated.append(grid)
        return rate_difficulty(grid)

    monkeypatch.setattr(generator, "generate_puzzle", generate_candidate)
    monkeypatch.setattr(generator, "rate_difficulty", rate_candidate)

    result = generate_puzzle_for_difficulty(
        requested, seed=1711, target_clues=25, max_attempts=3
    )

    assert result.puzzle is puzzle
    assert result.difficulty_report == rate_difficulty(puzzle.grid)
    assert result.difficulty_report.difficulty is requested
    assert result.attempts == 1
    assert len(generated) == len(rated) == 1
    assert type(generated[0]) is int
    assert is_valid_grid(result.puzzle.grid)
    assert has_unique_solution(result.puzzle.grid)
    assert clue_count(result.puzzle.grid) >= 25


def test_mismatches_advance_to_distinct_seeded_candidates_and_final_attempt_can_win(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    puzzle = puzzle_for(DIFFICULTY_FIXTURES[Difficulty.EASY])
    seeds: list[int | None] = []
    ratings = iter((Difficulty.MEDIUM, Difficulty.UNRATED, Difficulty.HARD))
    calls = 0

    def generate_candidate(*, seed: int | None, target_clues: int) -> SudokuPuzzle:
        seeds.append(seed)
        return puzzle

    def rate_candidate(grid: Grid) -> DifficultyReport:
        nonlocal calls
        calls += 1
        return report_for(next(ratings))

    monkeypatch.setattr(generator, "generate_puzzle", generate_candidate)
    monkeypatch.setattr(generator, "rate_difficulty", rate_candidate)

    result = generate_puzzle_for_difficulty(
        Difficulty.HARD, seed=1712, target_clues=25, max_attempts=3
    )

    assert result.puzzle is puzzle
    assert result.difficulty_report.difficulty is Difficulty.HARD
    assert result.attempts == 3
    assert calls == len(seeds) == 3
    assert all(type(seed) is int for seed in seeds)
    assert len(set(seeds)) == 3


def test_seeded_attempt_sequence_and_result_are_repeatable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    puzzle = puzzle_for(DIFFICULTY_FIXTURES[Difficulty.EASY])
    seed_sequences: list[list[int | None]] = []

    def run_once() -> DifficultyGeneratedPuzzle:
        seeds: list[int | None] = []
        reports = iter((report_for(Difficulty.MEDIUM), report_for(Difficulty.EASY)))

        def generate_candidate(*, seed: int | None, target_clues: int) -> SudokuPuzzle:
            seeds.append(seed)
            return puzzle

        monkeypatch.setattr(generator, "generate_puzzle", generate_candidate)
        monkeypatch.setattr(generator, "rate_difficulty", lambda grid: next(reports))
        result = generate_puzzle_for_difficulty(
            Difficulty.EASY, seed=1713, target_clues=25, max_attempts=2
        )
        seed_sequences.append(seeds)
        return result

    assert run_once() == run_once()
    assert seed_sequences[0] == seed_sequences[1]
    assert len(set(seed_sequences[0])) == 2


def test_exhaustion_rates_and_generates_exactly_the_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    puzzle = puzzle_for(DIFFICULTY_FIXTURES[Difficulty.EASY])
    seeds: list[int | None] = []
    ratings: list[Grid] = []

    def generate_candidate(*, seed: int | None, target_clues: int) -> SudokuPuzzle:
        seeds.append(seed)
        return puzzle

    def rate_candidate(grid: Grid) -> DifficultyReport:
        ratings.append(grid)
        return report_for(Difficulty.UNRATED)

    monkeypatch.setattr(generator, "generate_puzzle", generate_candidate)
    monkeypatch.setattr(generator, "rate_difficulty", rate_candidate)

    with pytest.raises(DifficultyGenerationError, match="hard.*3 attempts") as error:
        generate_puzzle_for_difficulty(
            Difficulty.HARD, seed=1714, target_clues=25, max_attempts=3
        )

    assert isinstance(error.value, SudokuError)
    assert len(seeds) == len(ratings) == 3
    assert len(set(seeds)) == 3


def test_early_success_generates_and_rates_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    puzzle = puzzle_for(DIFFICULTY_FIXTURES[Difficulty.EASY])
    generated = 0
    rated = 0

    def generate_candidate(*, seed: int | None, target_clues: int) -> SudokuPuzzle:
        nonlocal generated
        generated += 1
        return puzzle

    def rate_candidate(grid: Grid) -> DifficultyReport:
        nonlocal rated
        rated += 1
        return report_for(Difficulty.EASY)

    monkeypatch.setattr(generator, "generate_puzzle", generate_candidate)
    monkeypatch.setattr(generator, "rate_difficulty", rate_candidate)

    result = generate_puzzle_for_difficulty(
        Difficulty.EASY, seed=1715, target_clues=25, max_attempts=100
    )

    assert result.attempts == generated == rated == 1


@pytest.mark.parametrize("difficulty", [None, True, False, "easy", 1])
def test_requested_difficulty_must_be_an_enum(difficulty: object) -> None:
    with pytest.raises(TypeError):
        generate_puzzle_for_difficulty(difficulty)


def test_unrated_cannot_be_requested() -> None:
    with pytest.raises(ValueError, match="UNRATED"):
        generate_puzzle_for_difficulty(Difficulty.UNRATED)


@pytest.mark.parametrize("max_attempts", [None, True, False, 1.0, "1", IntSubclass(1)])
def test_max_attempts_requires_a_builtin_integer(max_attempts: object) -> None:
    with pytest.raises(TypeError):
        generate_puzzle_for_difficulty(Difficulty.EASY, max_attempts=max_attempts)


@pytest.mark.parametrize("max_attempts", [0, -1, -10])
def test_max_attempts_must_be_positive(max_attempts: int) -> None:
    with pytest.raises(ValueError):
        generate_puzzle_for_difficulty(Difficulty.EASY, max_attempts=max_attempts)


@pytest.mark.parametrize("target_clues", [True, 30.0, "30", 16, 82])
def test_target_clue_validation_is_delegated_to_the_base_generator(
    target_clues: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        generate_puzzle_for_difficulty(
            Difficulty.EASY, seed=1716, target_clues=target_clues, max_attempts=1
        )


def test_targeted_generation_preserves_global_random_state() -> None:
    original_state = random.getstate()
    try:
        random.seed(1717)
        expected = random.Random(1717)
        assert random.random() == expected.random()

        generate_puzzle_for_difficulty(
            Difficulty.EASY, seed=1718, target_clues=81, max_attempts=1
        )

        assert random.getstate() == expected.getstate()
        assert [random.random() for _ in range(5)] == [
            expected.random() for _ in range(5)
        ]
    finally:
        random.setstate(original_state)


def test_result_is_immutable_hashable_and_requires_typed_fields() -> None:
    puzzle = puzzle_for(DIFFICULTY_FIXTURES[Difficulty.EASY])
    report = rate_difficulty(puzzle.grid)
    result = DifficultyGeneratedPuzzle(puzzle, report, 1)

    assert result == DifficultyGeneratedPuzzle(puzzle, report, 1)
    assert hash(result) == hash(DifficultyGeneratedPuzzle(puzzle, report, 1))
    with pytest.raises(FrozenInstanceError):
        result.puzzle = puzzle
    with pytest.raises(FrozenInstanceError):
        result.difficulty_report = report
    with pytest.raises(FrozenInstanceError):
        result.attempts = 2
    for bad_puzzle, bad_report, bad_attempts, exception in (
        (None, report, 1, TypeError),
        (puzzle, None, 1, TypeError),
        (puzzle, report, True, TypeError),
        (puzzle, report, 0, ValueError),
    ):
        with pytest.raises(exception):
            DifficultyGeneratedPuzzle(bad_puzzle, bad_report, bad_attempts)
