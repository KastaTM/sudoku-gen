"""Bounded target-aware carving without changing legacy retry behavior."""

import random

import pytest

from sudoku_gen import generator
from sudoku_gen.benchmark import BenchmarkConfig, benchmark_batch
from sudoku_gen.difficulty import Difficulty, DifficultyReport
from sudoku_gen.exceptions import DifficultyGenerationError
from sudoku_gen.generator import (
    DifficultyGenerationStrategy,
    GenerationWork,
    generate_puzzle,
    generate_puzzle_batch,
    generate_puzzle_for_difficulty,
)
from sudoku_gen.human_solver import LogicalSolveStatus
from sudoku_gen.models import Grid
from sudoku_gen.pattern import Symmetry, is_symmetric
from sudoku_gen.solver import has_unique_solution
from sudoku_gen.validation import clue_count, is_valid_solution

SOLVED = Grid.from_string(
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)


def report(
    difficulty: Difficulty,
    *,
    score: int = 0,
    status: LogicalSolveStatus = LogicalSolveStatus.SOLVED,
) -> DifficultyReport:
    return DifficultyReport(difficulty, score, None, score, score, 0, 0, status)


def install_controlled_guided_carve(
    monkeypatch: pytest.MonkeyPatch,
    reports_by_empty_count: dict[int, DifficultyReport],
) -> None:
    monkeypatch.setattr(generator, "_generate_solution", lambda rng: SOLVED)
    monkeypatch.setattr(generator, "_removal_groups", lambda symmetry: [(0,), (1,)])
    monkeypatch.setattr(generator, "has_unique_solution", lambda grid: True)
    monkeypatch.setattr(
        generator,
        "rate_difficulty",
        lambda grid: reports_by_empty_count[grid.cells.count(0)],
    )


def test_guidance_prefers_exact_then_closer_solved_profiles() -> None:
    medium = report(Difficulty.MEDIUM, score=20)
    hard = report(Difficulty.HARD, score=30)
    unrated = report(Difficulty.UNRATED, score=100, status=LogicalSolveStatus.STUCK)

    assert generator._guidance_key(Difficulty.MEDIUM, medium) < generator._guidance_key(
        Difficulty.MEDIUM, hard
    )
    assert generator._guidance_key(
        Difficulty.MEDIUM, report(Difficulty.EASY)
    ) < generator._guidance_key(Difficulty.MEDIUM, hard)
    assert generator._guidance_key(Difficulty.EXPERT, hard) < generator._guidance_key(
        Difficulty.EXPERT, unrated
    )


def test_guided_carving_retains_lowest_clue_earlier_exact_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_controlled_guided_carve(
        monkeypatch,
        {
            0: report(Difficulty.EASY),
            1: report(Difficulty.MEDIUM, score=20),
            2: report(Difficulty.HARD, score=30),
        },
    )

    result = generate_puzzle_for_difficulty(
        Difficulty.MEDIUM,
        seed=12,
        target_clues=79,
        max_attempts=1,
        strategy=DifficultyGenerationStrategy.GUIDED_CARVING,
        guided_width=2,
    )

    assert result.difficulty_report.difficulty is Difficulty.MEDIUM
    assert clue_count(result.puzzle.grid) == 80
    assert result.work == GenerationWork(1, 3, 3, 4, 2, 2)


def test_guided_carving_checks_uniqueness_before_rating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generator, "_generate_solution", lambda rng: SOLVED)
    monkeypatch.setattr(generator, "_removal_groups", lambda symmetry: [(0,)])
    monkeypatch.setattr(generator, "has_unique_solution", lambda grid: False)

    def rate(grid: Grid) -> DifficultyReport:
        assert grid == SOLVED
        return report(Difficulty.EASY)

    monkeypatch.setattr(generator, "rate_difficulty", rate)

    result = generator._guided_candidate(13, 80, Symmetry.NONE, Difficulty.MEDIUM, 1)

    assert result[1].difficulty is Difficulty.EASY
    assert result[2].uniqueness_checks == result[2].tentative_removal_evaluations == 1
    assert result[2].difficulty_rating_evaluations == 1


def test_guided_rotational_groups_are_atomic_and_solution_is_preserved() -> None:
    result = generate_puzzle_for_difficulty(
        Difficulty.EASY,
        seed=14,
        target_clues=80,
        max_attempts=1,
        symmetry=Symmetry.ROTATIONAL_180,
        strategy=DifficultyGenerationStrategy.GUIDED_CARVING,
    )

    assert clue_count(result.puzzle.grid) >= 80
    assert is_symmetric(result.puzzle.grid, Symmetry.ROTATIONAL_180)
    assert result.puzzle.solution is not None
    assert is_valid_solution(result.puzzle.solution)
    assert has_unique_solution(result.puzzle.grid)


def test_guided_strategy_is_repeatable_and_isolates_global_rng() -> None:
    original = random.getstate()
    try:
        random.seed(19)
        expected = random.Random(19)
        assert random.random() == expected.random()
        first = generate_puzzle_for_difficulty(
            Difficulty.EASY,
            seed=20,
            target_clues=81,
            max_attempts=1,
            strategy=DifficultyGenerationStrategy.GUIDED_CARVING,
        )
        second = generate_puzzle_for_difficulty(
            Difficulty.EASY,
            seed=20,
            target_clues=81,
            max_attempts=1,
            strategy=DifficultyGenerationStrategy.GUIDED_CARVING,
        )
        assert first == second
        assert random.getstate() == expected.getstate()
    finally:
        random.setstate(original)


@pytest.mark.parametrize("strategy", [None, "guided", True])
@pytest.mark.parametrize("guided_width", [True, 1.0, "4", 0, -1])
def test_guided_options_are_strictly_validated(
    strategy: object, guided_width: object
) -> None:
    with pytest.raises((TypeError, ValueError)):
        generate_puzzle_for_difficulty(
            Difficulty.EASY, strategy=strategy, guided_width=guided_width
        )


def test_legacy_strategy_and_plain_generation_are_unchanged() -> None:
    assert generate_puzzle(seed=21, target_clues=30) == generate_puzzle(
        seed=21, target_clues=30
    )
    assert generate_puzzle_for_difficulty(
        Difficulty.EASY, seed=22, target_clues=81, max_attempts=1
    ) == generate_puzzle_for_difficulty(
        Difficulty.EASY,
        seed=22,
        target_clues=81,
        max_attempts=1,
        strategy=DifficultyGenerationStrategy.RANDOM_RETRY,
    )


def test_guided_batch_and_benchmark_forward_strategy_and_work() -> None:
    batch = generate_puzzle_batch(
        1,
        Difficulty.EASY,
        seed=23,
        target_clues=81,
        max_attempts=1,
        strategy=DifficultyGenerationStrategy.GUIDED_CARVING,
    )
    assert batch.work is not None
    assert batch.work.outer_attempts == batch.attempts == 1

    benchmark = benchmark_batch(
        BenchmarkConfig(
            1,
            Difficulty.EASY,
            seed=24,
            target_clues=81,
            max_attempts=1,
            strategy=DifficultyGenerationStrategy.GUIDED_CARVING,
        )
    )
    assert benchmark.work is not None
    assert benchmark.work.outer_attempts == benchmark.candidate_attempts


def test_guided_hard_fixture_succeeds_where_legacy_endpoint_retry_exhausts() -> None:
    """A fixed rotational target-30 configuration found during Phase 1.17."""
    arguments = dict(
        seed=3102,
        target_clues=30,
        symmetry=Symmetry.ROTATIONAL_180,
        max_attempts=5,
    )
    with pytest.raises(DifficultyGenerationError):
        generate_puzzle_for_difficulty(Difficulty.HARD, **arguments)

    result = generate_puzzle_for_difficulty(
        Difficulty.HARD,
        strategy=DifficultyGenerationStrategy.GUIDED_CARVING,
        **arguments,
    )

    assert result.attempts == 5
    assert result.difficulty_report.difficulty is Difficulty.HARD
    assert result.puzzle.solution is not None
    assert has_unique_solution(result.puzzle.grid)
