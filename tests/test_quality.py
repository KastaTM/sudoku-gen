"""Deterministic batch statistics and correctness-audit tests."""

from sudoku_gen.difficulty import Difficulty, DifficultyReport, rate_difficulty
from sudoku_gen.fingerprint import FingerprintMode, GridFingerprint, fingerprint_puzzle
from sudoku_gen.generator import PuzzleBatch, PuzzleBatchItem, generate_puzzle_batch
from sudoku_gen.human_solver import LogicalSolveStatus, Technique
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.pattern import Symmetry
from sudoku_gen.quality import analyze_batch, audit_batch, audit_puzzle

SOLUTION_TEXT = (
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)


def quality_fixture_batch() -> PuzzleBatch:
    first = SudokuPuzzle(Grid((1,) * 10 + (0,) * 71))
    second = SudokuPuzzle(Grid((2,) * 20 + (0,) * 61))
    first_report = DifficultyReport(
        Difficulty.EASY,
        10,
        Technique.NAKED_SINGLE,
        10,
        10,
        0,
        0,
        LogicalSolveStatus.SOLVED,
    )
    second_report = DifficultyReport(
        Difficulty.EASY,
        20,
        None,
        0,
        0,
        0,
        0,
        LogicalSolveStatus.SOLVED,
    )
    return PuzzleBatch(
        items=(
            PuzzleBatchItem(
                first,
                first_report,
                fingerprint_puzzle(first, FingerprintMode.EXACT),
            ),
            PuzzleBatchItem(
                second,
                second_report,
                fingerprint_puzzle(second, FingerprintMode.EXACT),
            ),
        ),
        difficulty=Difficulty.EASY,
        deduplication_mode=FingerprintMode.EXACT,
        attempts=4,
        difficulty_rejections=1,
        duplicate_rejections=1,
    )


def test_batch_quality_reports_exact_deterministic_statistics() -> None:
    batch = quality_fixture_batch()

    report = analyze_batch(batch)

    assert report == analyze_batch(batch)
    assert report.accepted_count == 2
    assert report.attempts == 4
    assert report.difficulty_rejections == report.duplicate_rejections == 1
    assert report.acceptance_rate == 0.5
    assert report.difficulty_rejection_rate == report.duplicate_rejection_rate == 0.25
    assert (
        report.acceptance_rate
        + report.difficulty_rejection_rate
        + report.duplicate_rejection_rate
        == 1.0
    )
    assert (
        report.clue_count_minimum,
        report.clue_count_maximum,
        report.clue_count_mean,
        report.clue_count_median,
    ) == (10, 20, 15.0, 15.0)
    assert (
        report.difficulty_score_minimum,
        report.difficulty_score_maximum,
        report.difficulty_score_mean,
        report.difficulty_score_median,
    ) == (10, 20, 15.0, 15.0)
    assert report.hardest_technique_counts == (
        (None, 1),
        (Technique.NAKED_SINGLE, 1),
    )


def test_batch_quality_handles_zero_duplicate_rejections() -> None:
    solution = Grid.from_string(SOLUTION_TEXT)
    puzzle = SudokuPuzzle(solution, solution)
    report = rate_difficulty(solution)
    batch = PuzzleBatch(
        items=(
            PuzzleBatchItem(
                puzzle, report, fingerprint_puzzle(puzzle, FingerprintMode.EXACT)
            ),
        ),
        difficulty=Difficulty.EASY,
        deduplication_mode=FingerprintMode.EXACT,
        attempts=1,
        difficulty_rejections=0,
        duplicate_rejections=0,
    )

    quality = analyze_batch(batch)

    assert quality.acceptance_rate == 1.0
    assert quality.difficulty_rejection_rate == quality.duplicate_rejection_rate == 0.0
    assert quality.hardest_technique_counts == ((None, 1),)


def test_audit_succeeds_for_a_real_generated_batch_and_is_repeatable() -> None:
    batch = generate_puzzle_batch(
        1, Difficulty.EASY, seed=2030, target_clues=81, max_attempts=1
    )

    first = audit_batch(batch, symmetry=Symmetry.ROTATIONAL_180)

    assert first == audit_batch(batch, symmetry=Symmetry.ROTATIONAL_180)
    assert first.passed
    assert first.checked_puzzle_count == 1
    assert first.issues == ()


def test_audit_reports_stale_difficulty_and_fingerprint_deterministically() -> None:
    solution = Grid.from_string(SOLUTION_TEXT)
    puzzle = SudokuPuzzle(solution, solution)
    stale_report = DifficultyReport(
        Difficulty.EASY,
        1,
        None,
        0,
        0,
        0,
        0,
        LogicalSolveStatus.SOLVED,
    )
    incorrect_fingerprint = GridFingerprint(FingerprintMode.EXACT, "not-a-digest")
    item = PuzzleBatchItem(puzzle, stale_report, incorrect_fingerprint)

    audit = audit_puzzle(item, expected_difficulty=Difficulty.EASY)

    assert not audit.passed
    assert tuple(issue.code for issue in audit.issues) == (
        "difficulty_report_mismatch",
        "fingerprint_mismatch",
    )


def test_audit_reports_missing_solution_and_requested_symmetry_failure() -> None:
    solution = Grid.from_string(SOLUTION_TEXT)
    asymmetric_cells = list(solution.cells)
    asymmetric_cells[0] = 0
    asymmetric = SudokuPuzzle(Grid(tuple(asymmetric_cells)))
    item = PuzzleBatchItem(
        asymmetric,
        rate_difficulty(asymmetric.grid),
        fingerprint_puzzle(asymmetric, FingerprintMode.EXACT),
    )

    audit = audit_puzzle(item, symmetry=Symmetry.ROTATIONAL_180)

    assert not audit.passed
    assert tuple(issue.code for issue in audit.issues) == (
        "missing_solution",
        "symmetry_mismatch",
    )
