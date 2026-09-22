"""Initial, deterministic difficulty policy based only on human-solving traces.

Technique severity determines the main band. Score is the sum of step weights
plus individual, explicitly recorded candidate removals. Singles-only traces
with score above 81 move from EASY to MEDIUM; all other bands use the technique
ceiling. This is an internal policy, not a calibrated publisher rating scale.
"""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from sudoku_gen.human_solver import (
    EliminationStep,
    LogicalSolveResult,
    LogicalSolveStatus,
    Technique,
    solve_logically,
)
from sudoku_gen.models import Grid


class Difficulty(Enum):
    """Supported internal ratings; UNRATED means logical solving did not finish."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"
    UNRATED = "unrated"


@dataclass(frozen=True, slots=True)
class DifficultyReport:
    """Trace metrics and classification, including partial metrics when unrated.

    Candidate eliminations count explicit EliminationStep removals only, not
    routine peer updates after a placement. One elimination step can remove
    several candidates, but still contributes just one to step_count.
    """

    difficulty: Difficulty
    score: int
    hardest_technique: Technique | None
    step_count: int
    placement_count: int
    elimination_step_count: int
    candidate_elimination_count: int
    logical_status: LogicalSolveStatus


# Severity is explicit and separate from detection priority and score weights.
# Adding a technique requires a deliberate entry in every policy table.
_TECHNIQUE_RANK = MappingProxyType(
    {
        Technique.NAKED_SINGLE: 1,
        Technique.HIDDEN_SINGLE: 2,
        Technique.NAKED_PAIR: 3,
        Technique.HIDDEN_PAIR: 4,
        Technique.POINTING: 5,
        Technique.BOX_LINE_REDUCTION: 6,
        Technique.NAKED_TRIPLE: 7,
        Technique.HIDDEN_TRIPLE: 8,
        Technique.X_WING: 9,
        Technique.XY_WING: 10,
        Technique.SWORDFISH: 11,
    }
)
_STEP_WEIGHT = MappingProxyType(
    {
        Technique.NAKED_SINGLE: 1,
        Technique.HIDDEN_SINGLE: 2,
        Technique.NAKED_PAIR: 4,
        Technique.HIDDEN_PAIR: 5,
        Technique.POINTING: 6,
        Technique.BOX_LINE_REDUCTION: 7,
        Technique.NAKED_TRIPLE: 8,
        Technique.HIDDEN_TRIPLE: 9,
        Technique.X_WING: 10,
        Technique.XY_WING: 11,
        Technique.SWORDFISH: 12,
    }
)
_TECHNIQUE_BAND = MappingProxyType(
    {
        Technique.NAKED_SINGLE: Difficulty.EASY,
        Technique.HIDDEN_SINGLE: Difficulty.EASY,
        Technique.NAKED_PAIR: Difficulty.MEDIUM,
        Technique.HIDDEN_PAIR: Difficulty.HARD,
        Technique.POINTING: Difficulty.HARD,
        Technique.BOX_LINE_REDUCTION: Difficulty.EXPERT,
        Technique.NAKED_TRIPLE: Difficulty.EXPERT,
        Technique.HIDDEN_TRIPLE: Difficulty.EXPERT,
        Technique.X_WING: Difficulty.EXPERT,
        Technique.XY_WING: Difficulty.EXPERT,
        Technique.SWORDFISH: Difficulty.EXPERT,
    }
)
# One weight point per board cell: every all-Naked-Single trace fits this budget.
# Hidden Singles cost two, so longer traces relying on them can exceed it.
_SINGLES_EASY_MAX_SCORE = 81


def _classify(
    status: LogicalSolveStatus, hardest: Technique | None, score: int
) -> Difficulty:
    if status is not LogicalSolveStatus.SOLVED:
        return Difficulty.UNRATED
    if hardest is None:
        return Difficulty.EASY
    band = _TECHNIQUE_BAND[hardest]
    if band is Difficulty.EASY and score > _SINGLES_EASY_MAX_SCORE:
        return Difficulty.MEDIUM
    return band


def rate_logical_result(result: LogicalSolveResult) -> DifficultyReport:
    """Analyze an existing, trusted logical trace without solving or replaying it.

    The supplied status and recorded steps are authoritative. A result from a
    resumed logical state describes only its recorded suffix, not earlier work;
    use rate_difficulty(original_grid) to rate the full puzzle.

    STUCK and CONTRADICTION return UNRATED while retaining partial metrics.
    Score summarizes trace effort; it is not a global ordering across difficulty
    bands, which primarily reflect the highest-severity technique actually used.
    """
    if not isinstance(result, LogicalSolveResult):
        raise TypeError("result must be a LogicalSolveResult.")
    hardest: Technique | None = None
    score = 0
    placement_count = 0
    elimination_step_count = 0
    candidate_elimination_count = 0
    for step in result.steps:
        score += _STEP_WEIGHT[step.technique]
        if (
            hardest is None
            or _TECHNIQUE_RANK[step.technique] > _TECHNIQUE_RANK[hardest]
        ):
            hardest = step.technique
        if isinstance(step, EliminationStep):
            elimination_step_count += 1
            candidate_elimination_count += len(step.eliminations)
        else:
            placement_count += 1
    score += candidate_elimination_count
    return DifficultyReport(
        difficulty=_classify(result.status, hardest, score),
        score=score,
        hardest_technique=hardest,
        step_count=len(result.steps),
        placement_count=placement_count,
        elimination_step_count=elimination_step_count,
        candidate_elimination_count=candidate_elimination_count,
        logical_status=result.status,
    )


def rate_difficulty(grid: Grid) -> DifficultyReport:
    """Rate a grid using exactly one human logical solve and no mathematical search.

    A completed valid grid is EASY with zero score and no hardest technique.
    Conflicting or locally contradictory grids are UNRATED. An unsupported or
    undetected unsatisfiable puzzle can remain STUCK and is likewise UNRATED.
    Neither clue count nor solution uniqueness contributes to this policy.
    """
    if not isinstance(grid, Grid):
        raise TypeError("grid must be a Grid.")
    return rate_logical_result(solve_logically(grid))
