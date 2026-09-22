"""Real puzzle ratings, diagnostics, and conservative treatment of partial solves."""

import pytest

from sudoku_gen.difficulty import (
    Difficulty,
    DifficultyReport,
    rate_difficulty,
    rate_logical_result,
)
from sudoku_gen.human_solver import LogicalSolveStatus, Technique, solve_logically
from sudoku_gen.models import Grid
from sudoku_gen.validation import clue_count, is_valid_solution

SOLVED_TEXT = (
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)
# Fixed, verified completed traces: runtime tests do not generate puzzles.
NAKED_SINGLE_TEXT = (
    "100000050000108900070000600067030509020009070000200038039670000080000300000400000"
)
HIDDEN_SINGLE_TEXT = (
    "000070902672000000000300560800760023400803700713004850000507080080400035305006170"
)
NAKED_PAIR_TEXT = (
    "700000090000090008301020000100034000000100040000000083600005000074903605210000070"
)
HIDDEN_PAIR_TEXT = (
    "040080105050900002600000000300002000708300000520000301800209070000000006200850000"
)
POINTING_TEXT = (
    "000000800040006150001000047067130080000070500900600000038000020000203000620490000"
)
CLAIMING_TEXT = (
    "004607000003000900600000000700806109000900640010020050000142080008500004000080000"
)
STUCK_TEXT = (
    "100007090030020008009400500005300900010080002400006000300000010060000007007000300"
)
BLOCKED_TEXT = "012345678" + "0" * 18 + "900000000" + "0" * 45
LATER_CONTRADICTION_TEXT = "003456789" + "002000000" + "0" * 63


@pytest.mark.parametrize(
    ("text", "difficulty", "hardest", "score", "steps", "placements", "removals"),
    [
        pytest.param(
            NAKED_SINGLE_TEXT,
            Difficulty.EASY,
            Technique.NAKED_SINGLE,
            56,
            56,
            56,
            0,
            id="naked-singles-only",
        ),
        pytest.param(
            HIDDEN_SINGLE_TEXT,
            Difficulty.EASY,
            Technique.HIDDEN_SINGLE,
            60,
            45,
            45,
            0,
            id="modest-hidden-singles",
        ),
        pytest.param(
            NAKED_PAIR_TEXT,
            Difficulty.MEDIUM,
            Technique.NAKED_PAIR,
            73,
            57,
            56,
            5,
            id="naked-pair",
        ),
        pytest.param(
            HIDDEN_PAIR_TEXT,
            Difficulty.HARD,
            Technique.HIDDEN_PAIR,
            96,
            60,
            56,
            11,
            id="hidden-pair",
        ),
        pytest.param(
            POINTING_TEXT,
            Difficulty.HARD,
            Technique.POINTING,
            130,
            63,
            55,
            22,
            id="pointing",
        ),
        pytest.param(
            CLAIMING_TEXT,
            Difficulty.EXPERT,
            Technique.BOX_LINE_REDUCTION,
            87,
            58,
            56,
            6,
            id="box-line-reduction",
        ),
    ],
)
def test_completed_puzzles_receive_exact_trace_based_reports(
    text: str,
    difficulty: Difficulty,
    hardest: Technique,
    score: int,
    steps: int,
    placements: int,
    removals: int,
) -> None:
    grid = Grid.from_string(text)
    original_hash = hash(grid)
    logical = solve_logically(grid)

    report = rate_difficulty(grid)

    assert logical.solved
    assert is_valid_solution(logical.grid)
    assert any(step.technique is hardest for step in logical.steps)
    assert report == DifficultyReport(
        difficulty=difficulty,
        score=score,
        hardest_technique=hardest,
        step_count=steps,
        placement_count=placements,
        elimination_step_count=steps - placements,
        candidate_elimination_count=removals,
        logical_status=LogicalSolveStatus.SOLVED,
    )
    assert report == rate_logical_result(logical)
    assert report == rate_difficulty(Grid.from_string(text))
    assert solve_logically(grid) == logical
    assert grid.to_string() == text
    assert hash(grid) == original_hash


def test_equal_clue_counts_can_receive_every_supported_difficulty() -> None:
    puzzles = [
        Grid.from_string(text)
        for text in (
            NAKED_SINGLE_TEXT,
            NAKED_PAIR_TEXT,
            HIDDEN_PAIR_TEXT,
            CLAIMING_TEXT,
        )
    ]

    assert {clue_count(grid) for grid in puzzles} == {25}
    assert [rate_difficulty(grid).difficulty for grid in puzzles] == [
        Difficulty.EASY,
        Difficulty.MEDIUM,
        Difficulty.HARD,
        Difficulty.EXPERT,
    ]


def test_a_shorter_advanced_trace_keeps_its_higher_band_despite_a_lower_score() -> None:
    hard = rate_difficulty(Grid.from_string(POINTING_TEXT))
    expert = rate_difficulty(Grid.from_string(CLAIMING_TEXT))

    assert expert.step_count < hard.step_count
    assert expert.score < hard.score
    assert hard.difficulty is Difficulty.HARD
    assert expert.difficulty is Difficulty.EXPERT


def test_completed_valid_grid_has_zero_effort() -> None:
    report = rate_difficulty(Grid.from_string(SOLVED_TEXT))

    assert report == DifficultyReport(
        Difficulty.EASY, 0, None, 0, 0, 0, 0, LogicalSolveStatus.SOLVED
    )


@pytest.mark.parametrize(
    ("text", "status", "score", "hardest", "steps"),
    [
        pytest.param("0" * 81, LogicalSolveStatus.STUCK, 0, None, 0, id="empty-stuck"),
        pytest.param(
            STUCK_TEXT,
            LogicalSolveStatus.STUCK,
            2,
            Technique.HIDDEN_SINGLE,
            1,
            id="unsupported-solvable-puzzle",
        ),
        pytest.param(
            STUCK_TEXT[:11] + "4" + STUCK_TEXT[12:],
            LogicalSolveStatus.STUCK,
            2,
            Technique.HIDDEN_SINGLE,
            1,
            id="unsatisfiable-but-not-locally-detected",
        ),
        pytest.param(
            "11" + "0" * 79,
            LogicalSolveStatus.CONTRADICTION,
            0,
            None,
            0,
            id="conflicting-clues",
        ),
        pytest.param(
            "1" * 81,
            LogicalSolveStatus.CONTRADICTION,
            0,
            None,
            0,
            id="complete-invalid-grid",
        ),
        pytest.param(
            BLOCKED_TEXT,
            LogicalSolveStatus.CONTRADICTION,
            0,
            None,
            0,
            id="zero-candidate-cell",
        ),
        pytest.param(
            LATER_CONTRADICTION_TEXT,
            LogicalSolveStatus.CONTRADICTION,
            1,
            Technique.NAKED_SINGLE,
            1,
            id="contradiction-after-progress",
        ),
    ],
)
def test_unfinished_puzzles_are_unrated_with_exact_partial_metrics(
    text: str,
    status: LogicalSolveStatus,
    score: int,
    hardest: Technique | None,
    steps: int,
) -> None:
    grid = Grid.from_string(text)

    report = rate_difficulty(grid)

    assert report == DifficultyReport(
        Difficulty.UNRATED, score, hardest, steps, steps, 0, 0, status
    )
    assert rate_difficulty(grid) == report
    assert grid.to_string() == text
