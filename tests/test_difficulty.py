"""Explicit rating policy and accounting for controlled, trusted logical traces.

These result fixtures isolate rating rules from technique detection. Their logs
are accounting inputs, not claimed deduction histories; real-puzzle integration
is covered separately.
"""

from dataclasses import FrozenInstanceError, fields

import pytest
from hypothesis import given, seed, settings
from hypothesis import strategies as st

from sudoku_gen import difficulty
from sudoku_gen.difficulty import (
    Difficulty,
    DifficultyReport,
    rate_difficulty,
    rate_logical_result,
)
from sudoku_gen.human_solver import (
    CandidateElimination,
    EliminationStep,
    LogicalSolveResult,
    LogicalSolveStatus,
    LogicalState,
    LogicalStep,
    SolveStep,
    Technique,
)
from sudoku_gen.models import Grid

SOLVED_TEXT = (
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)
SEVERITY = {
    Technique.NAKED_SINGLE: 1,
    Technique.HIDDEN_SINGLE: 2,
    Technique.NAKED_PAIR: 3,
    Technique.HIDDEN_PAIR: 4,
    Technique.POINTING: 5,
    Technique.BOX_LINE_REDUCTION: 6,
    Technique.NAKED_TRIPLE: 7,
    Technique.HIDDEN_TRIPLE: 8,
    Technique.X_WING: 9,
}
SINGLE_TECHNIQUES = (Technique.NAKED_SINGLE, Technique.HIDDEN_SINGLE)
ELIMINATION_TECHNIQUES = (
    Technique.NAKED_PAIR,
    Technique.HIDDEN_PAIR,
    Technique.POINTING,
    Technique.BOX_LINE_REDUCTION,
    Technique.NAKED_TRIPLE,
    Technique.HIDDEN_TRIPLE,
    Technique.X_WING,
)


def step_for(technique: Technique, removals: int = 1) -> LogicalStep:
    """Build one typed action, with independently countable candidate removals."""
    if technique in SINGLE_TECHNIQUES:
        return SolveStep(technique, 0, 0, 5)
    return EliminationStep(
        technique,
        tuple(CandidateElimination(0, 0, digit) for digit in range(1, removals + 1)),
    )


def logical_result(
    steps: tuple[LogicalStep, ...],
    status: LogicalSolveStatus = LogicalSolveStatus.SOLVED,
) -> LogicalSolveResult:
    """Supply final state explicitly, as required for elimination traces."""
    grid = (
        Grid.from_string(SOLVED_TEXT)
        if status is LogicalSolveStatus.SOLVED
        else Grid((0,) * 81)
    )
    return LogicalSolveResult(grid, steps, status, state=LogicalState.from_grid(grid))


def test_solved_zero_step_result_has_zero_effort_and_no_hardest_technique() -> None:
    report = rate_logical_result(logical_result(()))

    assert report == DifficultyReport(
        difficulty=Difficulty.EASY,
        score=0,
        hardest_technique=None,
        step_count=0,
        placement_count=0,
        elimination_step_count=0,
        candidate_elimination_count=0,
        logical_status=LogicalSolveStatus.SOLVED,
    )


@pytest.mark.parametrize(
    ("technique", "score", "label", "placements", "elimination_steps", "removals"),
    [
        (Technique.NAKED_SINGLE, 1, Difficulty.EASY, 1, 0, 0),
        (Technique.HIDDEN_SINGLE, 2, Difficulty.EASY, 1, 0, 0),
        (Technique.NAKED_PAIR, 7, Difficulty.MEDIUM, 0, 1, 3),
        (Technique.HIDDEN_PAIR, 8, Difficulty.HARD, 0, 1, 3),
        (Technique.POINTING, 9, Difficulty.HARD, 0, 1, 3),
        (Technique.BOX_LINE_REDUCTION, 10, Difficulty.EXPERT, 0, 1, 3),
        (Technique.NAKED_TRIPLE, 11, Difficulty.EXPERT, 0, 1, 3),
        (Technique.HIDDEN_TRIPLE, 12, Difficulty.EXPERT, 0, 1, 3),
        (Technique.X_WING, 13, Difficulty.EXPERT, 0, 1, 3),
    ],
)
def test_each_technique_has_an_explicit_weight_and_classification(
    technique: Technique,
    score: int,
    label: Difficulty,
    placements: int,
    elimination_steps: int,
    removals: int,
) -> None:
    report = rate_logical_result(logical_result((step_for(technique, 3),)))

    assert report == DifficultyReport(
        difficulty=label,
        score=score,
        hardest_technique=technique,
        step_count=1,
        placement_count=placements,
        elimination_step_count=elimination_steps,
        candidate_elimination_count=removals,
        logical_status=LogicalSolveStatus.SOLVED,
    )


def test_mixed_trace_counts_steps_and_individual_candidate_removals_separately() -> (
    None
):
    steps = (
        step_for(Technique.NAKED_SINGLE),
        step_for(Technique.HIDDEN_SINGLE),
        step_for(Technique.NAKED_PAIR, 4),
        step_for(Technique.HIDDEN_PAIR, 2),
        step_for(Technique.POINTING, 1),
        step_for(Technique.BOX_LINE_REDUCTION, 3),
    )

    report = rate_logical_result(logical_result(steps))

    assert report == DifficultyReport(
        difficulty=Difficulty.EXPERT,
        score=35,  # Weights 1 + 2 + 4 + 5 + 6 + 7, plus ten removals.
        hardest_technique=Technique.BOX_LINE_REDUCTION,
        step_count=6,
        placement_count=2,
        elimination_step_count=4,
        candidate_elimination_count=10,
        logical_status=LogicalSolveStatus.SOLVED,
    )


def test_one_pair_step_removing_four_candidates_is_one_solving_step() -> None:
    report = rate_logical_result(logical_result((step_for(Technique.NAKED_PAIR, 4),)))

    assert report.step_count == 1
    assert report.elimination_step_count == 1
    assert report.candidate_elimination_count == 4
    assert report.placement_count == 0
    assert report.score == 8


@pytest.mark.parametrize(
    ("hidden_singles", "naked_singles", "score", "label"),
    [
        (40, 0, 80, Difficulty.EASY),
        (40, 1, 81, Difficulty.EASY),
        (41, 0, 82, Difficulty.MEDIUM),
    ],
)
def test_singles_complexity_boundary_is_inclusive_at_81(
    hidden_singles: int, naked_singles: int, score: int, label: Difficulty
) -> None:
    steps = (step_for(Technique.HIDDEN_SINGLE),) * hidden_singles + (
        step_for(Technique.NAKED_SINGLE),
    ) * naked_singles

    report = rate_logical_result(logical_result(steps))

    assert report.score == score
    assert report.difficulty is label
    assert report.hardest_technique is Technique.HIDDEN_SINGLE
    assert report.step_count == hidden_singles + naked_singles
    assert report.placement_count == report.step_count
    assert report.elimination_step_count == report.candidate_elimination_count == 0


@pytest.mark.parametrize(
    ("technique", "label"),
    [
        (Technique.NAKED_PAIR, Difficulty.MEDIUM),
        (Technique.HIDDEN_PAIR, Difficulty.HARD),
        (Technique.POINTING, Difficulty.HARD),
        (Technique.BOX_LINE_REDUCTION, Difficulty.EXPERT),
    ],
)
def test_advanced_technique_classification_dominates_trace_length(
    technique: Technique, label: Difficulty
) -> None:
    short = rate_logical_result(logical_result((step_for(technique),)))
    long = rate_logical_result(
        logical_result(
            (step_for(technique),) + (step_for(Technique.HIDDEN_SINGLE),) * 60
        )
    )

    assert short.score < 81 < long.score
    assert short.difficulty is long.difficulty is label
    assert short.hardest_technique is long.hardest_technique is technique


@pytest.mark.parametrize("technique", tuple(SEVERITY))
def test_hardest_technique_uses_severity_not_the_last_step(
    technique: Technique,
) -> None:
    lower_steps = tuple(
        step_for(other)
        for other, rank in SEVERITY.items()
        if rank < SEVERITY[technique]
    )
    steps = (step_for(technique),) + tuple(reversed(lower_steps))

    forward = rate_logical_result(logical_result(steps))
    backward = rate_logical_result(logical_result(tuple(reversed(steps))))

    assert forward.hardest_technique is technique
    assert backward == forward


@pytest.mark.parametrize(
    "status", (LogicalSolveStatus.STUCK, LogicalSolveStatus.CONTRADICTION)
)
@pytest.mark.parametrize("has_steps", (False, True))
def test_unfinished_results_are_unrated_and_retain_partial_metrics(
    status: LogicalSolveStatus, has_steps: bool
) -> None:
    steps = (
        (step_for(Technique.HIDDEN_SINGLE), step_for(Technique.BOX_LINE_REDUCTION, 4))
        if has_steps
        else ()
    )

    report = rate_logical_result(logical_result(steps, status))

    assert report == DifficultyReport(
        difficulty=Difficulty.UNRATED,
        score=13 if has_steps else 0,
        hardest_technique=Technique.BOX_LINE_REDUCTION if has_steps else None,
        step_count=2 if has_steps else 0,
        placement_count=1 if has_steps else 0,
        elimination_step_count=1 if has_steps else 0,
        candidate_elimination_count=4 if has_steps else 0,
        logical_status=status,
    )


def test_reports_are_frozen_hashable_and_repeatable_without_mutating_results() -> None:
    result = logical_result(
        (step_for(Technique.NAKED_SINGLE), step_for(Technique.POINTING, 4))
    )
    original_hash = hash(result)
    original_steps = result.steps

    first = rate_logical_result(result)
    second = rate_logical_result(result)

    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1
    assert hash(result) == original_hash
    assert result.steps is original_steps
    for field in fields(first):
        with pytest.raises(FrozenInstanceError):
            setattr(first, field.name, None)


def test_grid_rating_derives_all_metrics_from_one_logical_solve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Grid((0,) * 81)
    result = logical_result(
        (step_for(Technique.NAKED_SINGLE), step_for(Technique.POINTING, 4))
    )
    calls: list[Grid] = []

    def solve_once(grid: Grid) -> LogicalSolveResult:
        calls.append(grid)
        return result

    monkeypatch.setattr(difficulty, "solve_logically", solve_once)

    report = rate_difficulty(original)

    assert len(calls) == 1
    assert calls[0] is original
    assert report == DifficultyReport(
        difficulty=Difficulty.HARD,
        score=11,
        hardest_technique=Technique.POINTING,
        step_count=2,
        placement_count=1,
        elimination_step_count=1,
        candidate_elimination_count=4,
        logical_status=LogicalSolveStatus.SOLVED,
    )


def test_existing_result_rating_does_not_solve_search_or_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = logical_result((step_for(Technique.NAKED_PAIR, 4),))

    def unexpected_work(*args: object, **kwargs: object) -> None:
        pytest.fail("Rating a supplied result must only analyze its trace and status.")

    monkeypatch.setattr(difficulty, "solve_logically", unexpected_work)
    for path in (
        "sudoku_gen.human_solver.solve_logically",
        "sudoku_gen.human_solver.next_step",
        "sudoku_gen.human_solver.apply_step",
        "sudoku_gen.solver.solve",
        "sudoku_gen.solver.count_solutions",
        "sudoku_gen.solver.has_unique_solution",
    ):
        monkeypatch.setattr(path, unexpected_work)

    report = rate_logical_result(result)

    assert report.difficulty is Difficulty.MEDIUM
    assert report.score == 8


@pytest.mark.parametrize("value", (None, False, 0, "0" * 81, (0,) * 81, [0] * 81))
def test_grid_rating_rejects_non_grid_inputs(value: object) -> None:
    with pytest.raises(TypeError):
        rate_difficulty(value)


def test_grid_rating_requires_grid_instead_of_candidate_state() -> None:
    with pytest.raises(TypeError):
        rate_difficulty(LogicalState.from_grid(Grid((0,) * 81)))


@pytest.mark.parametrize("value", (None, False, 0, "solved", (), Grid((0,) * 81)))
def test_result_rating_rejects_non_result_inputs(value: object) -> None:
    with pytest.raises(TypeError):
        rate_logical_result(value)


@seed(1909)
@settings(max_examples=30, deadline=None)
@given(
    technique=st.sampled_from(tuple(SEVERITY)),
    original_count=st.integers(min_value=0, max_value=20),
    extra_count=st.integers(min_value=1, max_value=20),
)
def test_additional_steps_of_the_same_technique_increase_score(
    technique: Technique, original_count: int, extra_count: int
) -> None:
    step = step_for(technique)
    before = rate_logical_result(logical_result((step,) * original_count))
    after = rate_logical_result(
        logical_result((step,) * (original_count + extra_count))
    )

    assert after.score > before.score
    assert after.step_count == before.step_count + extra_count
    assert after.hardest_technique is technique


@seed(1910)
@settings(max_examples=30, deadline=None)
@given(
    technique=st.sampled_from(ELIMINATION_TECHNIQUES),
    original_removals=st.integers(min_value=1, max_value=8),
    data=st.data(),
)
def test_additional_candidate_removals_increase_score_without_adding_steps(
    technique: Technique, original_removals: int, data: st.DataObject
) -> None:
    extra = data.draw(st.integers(min_value=1, max_value=9 - original_removals))
    before = rate_logical_result(
        logical_result((step_for(technique, original_removals),))
    )
    after = rate_logical_result(
        logical_result((step_for(technique, original_removals + extra),))
    )

    assert after.score == before.score + extra
    assert (
        after.candidate_elimination_count == before.candidate_elimination_count + extra
    )
    assert after.step_count == before.step_count == 1
    assert after.elimination_step_count == before.elimination_step_count == 1
    assert after.difficulty is before.difficulty


@seed(1911)
@settings(max_examples=30, deadline=None)
@given(
    previous=st.lists(st.sampled_from(tuple(SEVERITY)), max_size=15),
    added=st.sampled_from(tuple(SEVERITY)),
)
def test_adding_a_step_cannot_reduce_the_hardest_technique(
    previous: list[Technique], added: Technique
) -> None:
    steps = tuple(step_for(technique) for technique in previous)
    before = rate_logical_result(logical_result(steps))
    after = rate_logical_result(logical_result(steps + (step_for(added),)))

    assert after.hardest_technique is not None
    previous_rank = (
        SEVERITY[before.hardest_technique] if before.hardest_technique else 0
    )
    assert SEVERITY[after.hardest_technique] == max(previous_rank, SEVERITY[added])
    assert after.score > before.score
