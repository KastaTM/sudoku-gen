"""Observational benchmark arithmetic without machine-specific timing assertions."""

from sudoku_gen import benchmark
from sudoku_gen.benchmark import (
    BenchmarkConfig,
    benchmark_batch,
    representative_benchmark_configs,
)
from sudoku_gen.difficulty import Difficulty, rate_difficulty
from sudoku_gen.fingerprint import FingerprintMode, fingerprint_puzzle
from sudoku_gen.generator import PuzzleBatch, PuzzleBatchItem
from sudoku_gen.models import Grid, SudokuPuzzle

SOLUTION_TEXT = (
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)


def benchmark_fixture_batch() -> PuzzleBatch:
    solution = Grid.from_string(SOLUTION_TEXT)
    puzzle = SudokuPuzzle(solution, solution)
    return PuzzleBatch(
        items=(
            PuzzleBatchItem(
                puzzle,
                rate_difficulty(solution),
                fingerprint_puzzle(puzzle, FingerprintMode.EXACT),
            ),
        ),
        difficulty=Difficulty.EASY,
        deduplication_mode=FingerprintMode.EXACT,
        attempts=2,
        difficulty_rejections=1,
        duplicate_rejections=0,
    )


def test_benchmark_uses_perf_counter_and_calculates_derived_rates(
    monkeypatch: object,
) -> None:
    batch = benchmark_fixture_batch()
    clock_values = iter((10.0, 12.5))
    monkeypatch.setattr(benchmark, "perf_counter", lambda: next(clock_values))
    monkeypatch.setattr(
        benchmark, "generate_puzzle_batch", lambda *args, **kwargs: batch
    )

    result = benchmark_batch(BenchmarkConfig(1, Difficulty.EASY, max_attempts=2))

    assert result.elapsed_seconds == 2.5
    assert result.accepted_count == 1
    assert result.candidate_attempts == 2
    assert result.attempts_per_accepted_puzzle == 2.0
    assert result.accepted_puzzles_per_second == 0.4
    assert result.candidate_attempts_per_second == 0.8
    assert result.quality_report.attempts == 2


def test_representative_configs_cover_every_normal_difficulty() -> None:
    configs = representative_benchmark_configs(seed=40, max_attempts=7)

    assert tuple(config.difficulty for config in configs) == (
        Difficulty.EASY,
        Difficulty.MEDIUM,
        Difficulty.HARD,
        Difficulty.EXPERT,
    )
    assert tuple(config.seed for config in configs) == (40, 41, 42, 43)
    assert all(config.count == 1 and config.max_attempts == 7 for config in configs)
