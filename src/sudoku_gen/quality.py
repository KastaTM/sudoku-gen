"""Deterministic descriptive statistics and correctness audits for batches."""

from dataclasses import dataclass
from statistics import mean, median

from sudoku_gen.difficulty import Difficulty, rate_difficulty
from sudoku_gen.fingerprint import (
    FingerprintMode,
    deduplicate_puzzles,
    fingerprint_puzzle,
)
from sudoku_gen.generator import PuzzleBatch, PuzzleBatchItem
from sudoku_gen.human_solver import Technique
from sudoku_gen.pattern import Symmetry, is_symmetric
from sudoku_gen.solver import has_unique_solution, solve
from sudoku_gen.validation import clue_count, is_valid_grid, is_valid_solution

_TECHNIQUE_ORDER: tuple[Technique | None, ...] = (
    None,
    Technique.NAKED_SINGLE,
    Technique.HIDDEN_SINGLE,
    Technique.NAKED_PAIR,
    Technique.HIDDEN_PAIR,
    Technique.POINTING,
    Technique.BOX_LINE_REDUCTION,
)


@dataclass(frozen=True, slots=True)
class BatchQualityReport:
    """Deterministic descriptive metrics derived from accepted batch items."""

    accepted_count: int
    attempts: int
    difficulty_rejections: int
    duplicate_rejections: int
    acceptance_rate: float
    difficulty_rejection_rate: float
    duplicate_rejection_rate: float
    clue_count_minimum: int
    clue_count_maximum: int
    clue_count_mean: float
    clue_count_median: float
    difficulty_score_minimum: int
    difficulty_score_maximum: int
    difficulty_score_mean: float
    difficulty_score_median: float
    hardest_technique_counts: tuple[tuple[Technique | None, int], ...]


@dataclass(frozen=True, slots=True)
class AuditIssue:
    """One deterministic diagnostic from a puzzle or its containing batch."""

    puzzle_index: int | None
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class PuzzleAuditReport:
    """Invariant diagnostics for one batch item without raising on failures."""

    passed: bool
    issues: tuple[AuditIssue, ...]


@dataclass(frozen=True, slots=True)
class BatchAuditReport:
    """Invariant diagnostics for all accepted batch items and their identities."""

    passed: bool
    checked_puzzle_count: int
    issues: tuple[AuditIssue, ...]


def analyze_batch(batch: PuzzleBatch) -> BatchQualityReport:
    """Return reproducible descriptive statistics for a successful batch."""
    if not isinstance(batch, PuzzleBatch):
        raise TypeError("batch must be a PuzzleBatch.")
    clue_counts = tuple(clue_count(item.puzzle.grid) for item in batch.items)
    scores = tuple(item.difficulty_report.score for item in batch.items)
    technique_counts = tuple(
        (
            technique,
            sum(
                item.difficulty_report.hardest_technique is technique
                for item in batch.items
            ),
        )
        for technique in _TECHNIQUE_ORDER
        if any(
            item.difficulty_report.hardest_technique is technique
            for item in batch.items
        )
    )
    return BatchQualityReport(
        accepted_count=batch.accepted_count,
        attempts=batch.attempts,
        difficulty_rejections=batch.difficulty_rejections,
        duplicate_rejections=batch.duplicate_rejections,
        acceptance_rate=batch.accepted_count / batch.attempts,
        difficulty_rejection_rate=batch.difficulty_rejections / batch.attempts,
        duplicate_rejection_rate=batch.duplicate_rejections / batch.attempts,
        clue_count_minimum=min(clue_counts),
        clue_count_maximum=max(clue_counts),
        clue_count_mean=float(mean(clue_counts)),
        clue_count_median=float(median(clue_counts)),
        difficulty_score_minimum=min(scores),
        difficulty_score_maximum=max(scores),
        difficulty_score_mean=float(mean(scores)),
        difficulty_score_median=float(median(scores)),
        hardest_technique_counts=technique_counts,
    )


def audit_puzzle(
    item: PuzzleBatchItem,
    *,
    expected_difficulty: Difficulty | None = None,
    symmetry: Symmetry | None = None,
) -> PuzzleAuditReport:
    """Independently verify one accepted item using existing public APIs."""
    if not isinstance(item, PuzzleBatchItem):
        raise TypeError("item must be a PuzzleBatchItem.")
    if expected_difficulty is not None and not isinstance(
        expected_difficulty, Difficulty
    ):
        raise TypeError("expected_difficulty must be a Difficulty or None.")
    if symmetry is not None and not isinstance(symmetry, Symmetry):
        raise TypeError("symmetry must be a Symmetry or None.")

    issues: list[AuditIssue] = []
    puzzle = item.puzzle
    grid = puzzle.grid
    solution = puzzle.solution
    if not is_valid_grid(grid):
        issues.append(
            _issue("invalid_grid", "Puzzle grid violates Sudoku constraints.")
        )
    if solution is None:
        issues.append(_issue("missing_solution", "Puzzle has no stored solution."))
    else:
        if not is_valid_solution(solution):
            issues.append(_issue("invalid_solution", "Stored solution is not valid."))
        if any(
            clue != 0 and clue != answer
            for clue, answer in zip(grid.cells, solution.cells, strict=True)
        ):
            issues.append(
                _issue("clue_mismatch", "Puzzle clues disagree with solution.")
            )
    if not has_unique_solution(grid):
        issues.append(
            _issue("not_unique", "Puzzle does not have exactly one solution.")
        )
    if solution is not None and solve(grid) != solution:
        issues.append(
            _issue(
                "solution_not_recovered",
                "Mathematical solve does not recover solution.",
            )
        )
    if rate_difficulty(grid) != item.difficulty_report:
        issues.append(
            _issue(
                "difficulty_report_mismatch",
                "Stored difficulty report is stale or wrong.",
            )
        )
    if (
        expected_difficulty is not None
        and item.difficulty_report.difficulty is not expected_difficulty
    ):
        issues.append(
            _issue(
                "difficulty_mismatch", "Puzzle difficulty does not match the request."
            )
        )
    if symmetry is not None and not is_symmetric(grid, symmetry):
        issues.append(
            _issue("symmetry_mismatch", "Puzzle does not meet requested symmetry.")
        )
    if fingerprint_puzzle(puzzle, item.fingerprint.mode) != item.fingerprint:
        issues.append(
            _issue("fingerprint_mismatch", "Stored fingerprint does not match puzzle.")
        )
    return PuzzleAuditReport(passed=not issues, issues=tuple(issues))


def audit_batch(
    batch: PuzzleBatch,
    *,
    symmetry: Symmetry | None = None,
) -> BatchAuditReport:
    """Audit accepted items plus their canonical uniqueness in stable order."""
    if not isinstance(batch, PuzzleBatch):
        raise TypeError("batch must be a PuzzleBatch.")
    if symmetry is not None and not isinstance(symmetry, Symmetry):
        raise TypeError("symmetry must be a Symmetry or None.")
    issues: list[AuditIssue] = []
    seen_identities: set[tuple[FingerprintMode, str]] = set()
    for index, item in enumerate(batch.items):
        puzzle_audit = audit_puzzle(
            item, expected_difficulty=batch.difficulty, symmetry=symmetry
        )
        issues.extend(
            AuditIssue(index, issue.code, issue.message)
            for issue in puzzle_audit.issues
        )
        if item.fingerprint.mode is not batch.deduplication_mode:
            issues.append(
                AuditIssue(
                    index,
                    "fingerprint_mode_mismatch",
                    "Item fingerprint mode differs from the batch mode.",
                )
            )
        identity = item.fingerprint.mode, item.fingerprint.value
        if identity in seen_identities:
            issues.append(
                AuditIssue(
                    index,
                    "duplicate_fingerprint",
                    "Accepted items share a fingerprint identity.",
                )
            )
        seen_identities.add(identity)
    if (
        len(
            deduplicate_puzzles(
                (item.puzzle for item in batch.items), mode=batch.deduplication_mode
            )
        )
        != batch.accepted_count
    ):
        issues.append(
            AuditIssue(
                None,
                "duplicate_canonical_identity",
                "Accepted items are not canonically unique for the batch mode.",
            )
        )
    return BatchAuditReport(
        passed=not issues,
        checked_puzzle_count=batch.accepted_count,
        issues=tuple(issues),
    )


def _issue(code: str, message: str) -> AuditIssue:
    return AuditIssue(puzzle_index=None, code=code, message=message)
