"""Lightweight observational timing for bounded puzzle batch generation."""

from dataclasses import dataclass
from time import perf_counter

from sudoku_gen.difficulty import Difficulty
from sudoku_gen.fingerprint import FingerprintMode
from sudoku_gen.generator import PuzzleBatch, generate_puzzle_batch
from sudoku_gen.pattern import Symmetry
from sudoku_gen.quality import BatchQualityReport, analyze_batch


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    """Explicit configuration for one real batch-generation timing run."""

    count: int
    difficulty: Difficulty
    seed: int | None = None
    target_clues: int = 30
    symmetry: Symmetry = Symmetry.NONE
    deduplication_mode: FingerprintMode = FingerprintMode.DIGIT_NORMALIZED
    max_attempts: int = 100


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Machine-dependent timing and deterministic metadata from one successful run."""

    elapsed_seconds: float
    accepted_count: int
    candidate_attempts: int
    attempts_per_accepted_puzzle: float
    accepted_puzzles_per_second: float
    candidate_attempts_per_second: float
    quality_report: BatchQualityReport


def benchmark_batch(config: BenchmarkConfig) -> BenchmarkResult:
    """Time one batch generation run with perf_counter without automatic retries."""
    if not isinstance(config, BenchmarkConfig):
        raise TypeError("config must be a BenchmarkConfig.")
    started = perf_counter()
    batch = generate_puzzle_batch(
        config.count,
        config.difficulty,
        seed=config.seed,
        target_clues=config.target_clues,
        symmetry=config.symmetry,
        deduplication_mode=config.deduplication_mode,
        max_attempts=config.max_attempts,
    )
    elapsed_seconds = perf_counter() - started
    return _benchmark_result(batch, elapsed_seconds)


def representative_benchmark_configs(
    *, seed: int = 1, max_attempts: int = 20
) -> tuple[BenchmarkConfig, ...]:
    """Return modest manual configurations for each supported normal difficulty."""
    if type(seed) is not int:
        raise TypeError("seed must be a built-in integer.")
    if type(max_attempts) is not int:
        raise TypeError("max_attempts must be a built-in integer.")
    return tuple(
        BenchmarkConfig(
            count=1,
            difficulty=difficulty,
            seed=seed + index,
            target_clues=30,
            max_attempts=max_attempts,
        )
        for index, difficulty in enumerate(
            (Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD, Difficulty.EXPERT)
        )
    )


def run_representative_benchmarks(
    *, seed: int = 1, max_attempts: int = 20
) -> tuple[BenchmarkResult, ...]:
    """Run representative configurations, propagating any bounded failure cleanly."""
    return tuple(
        benchmark_batch(config)
        for config in representative_benchmark_configs(
            seed=seed, max_attempts=max_attempts
        )
    )


def _benchmark_result(batch: PuzzleBatch, elapsed_seconds: float) -> BenchmarkResult:
    if elapsed_seconds < 0:
        raise ValueError("perf_counter elapsed time must not be negative.")
    accepted_per_second = _per_second(batch.accepted_count, elapsed_seconds)
    attempts_per_second = _per_second(batch.attempts, elapsed_seconds)
    return BenchmarkResult(
        elapsed_seconds=elapsed_seconds,
        accepted_count=batch.accepted_count,
        candidate_attempts=batch.attempts,
        attempts_per_accepted_puzzle=batch.attempts / batch.accepted_count,
        accepted_puzzles_per_second=accepted_per_second,
        candidate_attempts_per_second=attempts_per_second,
        quality_report=analyze_batch(batch),
    )


def _per_second(quantity: int, elapsed_seconds: float) -> float:
    if elapsed_seconds == 0:
        return float("inf")
    return quantity / elapsed_seconds
