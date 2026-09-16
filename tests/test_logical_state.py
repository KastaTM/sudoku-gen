"""Candidate-state invariants, typed actions, and replay compatibility."""

from dataclasses import FrozenInstanceError

import pytest

from sudoku_gen.candidates import candidates
from sudoku_gen.exceptions import InvalidGridError
from sudoku_gen.human_solver import (
    CandidateElimination,
    EliminationStep,
    LogicalSolveResult,
    LogicalSolveStatus,
    LogicalState,
    PlacementStep,
    SolveStep,
    Technique,
    apply_step,
    next_step,
    solve_logically,
)
from sudoku_gen.models import Grid

EMPTY = Grid((0,) * 81)
DIGITS = frozenset(range(1, 10))
SOLVED_TEXT = (
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)


def test_initial_state_uses_only_existing_mathematical_candidates() -> None:
    grid = Grid.from_string("5" + "0" * 80)
    state = LogicalState.from_grid(grid)

    assert state.grid == grid
    assert state.candidates == tuple(candidates(grid, *divmod(i, 9)) for i in range(81))
    assert state.candidates[0] == frozenset()
    assert state.candidates[1] == DIGITS - {5}
    assert state.candidates[80] == DIGITS


def test_state_accepts_reduced_subsets_without_changing_mathematical_candidates() -> (
    None
):
    state = LogicalState(EMPTY, (frozenset({1, 2}),) + (DIGITS,) * 80)

    assert state.candidates[0] == frozenset({1, 2})
    assert candidates(state.grid, 0, 0) == DIGITS


@pytest.mark.parametrize("size", [0, 80, 82])
def test_candidate_state_requires_exactly_81_cells(size: int) -> None:
    with pytest.raises(ValueError):
        LogicalState(EMPTY, (DIGITS,) * size)


@pytest.mark.parametrize("values", [[DIGITS] * 81, None])
def test_candidate_container_must_be_immutable(values: object) -> None:
    with pytest.raises(TypeError):
        LogicalState(EMPTY, values)


@pytest.mark.parametrize("values", [{1, 2}, (1, 2), [1, 2], None])
def test_candidate_cells_must_be_frozensets(values: object) -> None:
    with pytest.raises(TypeError):
        LogicalState(EMPTY, (values,) + (DIGITS,) * 80)


@pytest.mark.parametrize("value", [True, False, 1.0, "1", None])
def test_candidate_digits_must_be_builtin_integers(value: object) -> None:
    with pytest.raises(TypeError):
        LogicalState(EMPTY, (frozenset({value}),) + (DIGITS,) * 80)


@pytest.mark.parametrize("value", [-1, 0, 10])
def test_candidate_digits_must_be_in_range(value: int) -> None:
    with pytest.raises(ValueError):
        LogicalState(EMPTY, (frozenset({value}),) + (DIGITS,) * 80)


def test_filled_cells_cannot_have_candidates() -> None:
    grid = Grid.from_string("5" + "0" * 80)
    options = LogicalState.from_grid(grid).candidates

    with pytest.raises(ValueError, match="Filled"):
        LogicalState(grid, (frozenset({5}),) + options[1:])


def test_logical_candidates_cannot_include_a_digit_excluded_by_the_grid() -> None:
    grid = Grid.from_string("5" + "0" * 80)
    options = LogicalState.from_grid(grid).candidates

    with pytest.raises(ValueError, match="allowed"):
        LogicalState(grid, options[:1] + (DIGITS,) + options[2:])


def test_zero_candidate_state_is_preserved_and_reported_as_a_contradiction() -> None:
    state = LogicalState(EMPTY, (frozenset(),) + (DIGITS,) * 80)

    with pytest.raises(InvalidGridError):
        next_step(state)
    with pytest.raises(InvalidGridError):
        apply_step(state, SolveStep(Technique.NAKED_SINGLE, 8, 8, 9))
    result = solve_logically(state)

    assert result.state == state
    assert result.grid == EMPTY
    assert result.steps == ()
    assert result.status is LogicalSolveStatus.CONTRADICTION
    assert not result.solved


def test_state_and_result_require_grid_instances() -> None:
    with pytest.raises(TypeError):
        LogicalState(None, (DIGITS,) * 81)
    with pytest.raises(TypeError):
        LogicalState.from_grid(None)


@pytest.mark.parametrize("coordinate", ["row", "column"])
@pytest.mark.parametrize("value", [-1, 9])
def test_elimination_coordinates_are_checked(coordinate: str, value: int) -> None:
    fields = {"row": 0, "column": 0, "value": 1, coordinate: value}
    with pytest.raises(IndexError):
        CandidateElimination(**fields)


@pytest.mark.parametrize("field", ["row", "column", "value"])
@pytest.mark.parametrize("value", [True, 1.0, "1", None])
def test_elimination_fields_reject_implicit_conversions(
    field: str, value: object
) -> None:
    fields = {"row": 0, "column": 0, "value": 1, field: value}
    with pytest.raises(TypeError):
        CandidateElimination(**fields)


@pytest.mark.parametrize("value", [0, 10])
def test_elimination_values_must_be_digits(value: int) -> None:
    with pytest.raises(ValueError):
        CandidateElimination(0, 0, value)


@pytest.mark.parametrize("technique", [Technique.NAKED_SINGLE, Technique.HIDDEN_SINGLE])
def test_placement_and_elimination_techniques_cannot_be_confused(
    technique: Technique,
) -> None:
    with pytest.raises(ValueError):
        EliminationStep(technique, (CandidateElimination(0, 0, 1),))


@pytest.mark.parametrize(
    "technique",
    [
        Technique.NAKED_PAIR,
        Technique.HIDDEN_PAIR,
        Technique.POINTING,
        Technique.BOX_LINE_REDUCTION,
    ],
)
def test_elimination_techniques_cannot_be_used_as_placement_records(
    technique: Technique,
) -> None:
    with pytest.raises(ValueError):
        SolveStep(technique, 0, 0, 1)


@pytest.mark.parametrize("technique", ["naked_pair", None, 1])
def test_elimination_technique_must_be_typed(technique: object) -> None:
    with pytest.raises(TypeError):
        EliminationStep(technique, (CandidateElimination(0, 0, 1),))


@pytest.mark.parametrize("removals", [[], (None,), ((0, 0, 1),)])
def test_elimination_actions_must_be_an_immutable_tuple_of_records(
    removals: object,
) -> None:
    with pytest.raises(TypeError):
        EliminationStep(Technique.NAKED_PAIR, removals)


def test_elimination_step_rejects_empty_and_duplicate_removals() -> None:
    with pytest.raises(ValueError):
        EliminationStep(Technique.NAKED_PAIR, ())
    removal = CandidateElimination(0, 0, 1)
    with pytest.raises(ValueError):
        EliminationStep(Technique.NAKED_PAIR, (removal, removal))


def test_elimination_records_are_canonical_immutable_and_hashable() -> None:
    first = CandidateElimination(0, 8, 7)
    second = CandidateElimination(8, 0, 2)
    step = EliminationStep(Technique.NAKED_PAIR, (second, first))
    equivalent = EliminationStep(Technique.NAKED_PAIR, (first, second))

    assert step.eliminations == (first, second)
    assert step == equivalent
    assert hash(step) == hash(equivalent)
    with pytest.raises(FrozenInstanceError):
        first.value = 9
    with pytest.raises(FrozenInstanceError):
        step.eliminations = ()


def pair_state() -> LogicalState:
    options = list((DIGITS,) * 81)
    options[0] = options[8] = frozenset({2, 7})
    return LogicalState(EMPTY, tuple(options))


def test_state_immutability_and_result_preserve_eliminations() -> None:
    state = pair_state()
    step = next_step(state)
    assert isinstance(step, EliminationStep)
    updated = apply_step(state, step)
    result = LogicalSolveResult(
        updated.grid, (step,), LogicalSolveStatus.STUCK, state=updated
    )

    assert result.state == updated
    assert result.state.candidates[1] == DIGITS - {2, 7}
    assert state.candidates[1] == DIGITS
    assert hash(updated) == hash(LogicalState(updated.grid, updated.candidates))
    assert hash(result) == hash(
        LogicalSolveResult(
            updated.grid, (step,), LogicalSolveStatus.STUCK, state=updated
        )
    )
    with pytest.raises(FrozenInstanceError):
        updated.candidates = (DIGITS,) * 81
    with pytest.raises(FrozenInstanceError):
        updated.grid = EMPTY
    with pytest.raises(FrozenInstanceError):
        result.state = state


def test_result_checks_state_type_and_grid_agreement() -> None:
    with pytest.raises(TypeError):
        LogicalSolveResult(EMPTY, (), LogicalSolveStatus.STUCK, state=EMPTY)
    with pytest.raises(ValueError):
        LogicalSolveResult(
            Grid.from_string(SOLVED_TEXT),
            (),
            LogicalSolveStatus.STUCK,
            state=LogicalState.from_grid(EMPTY),
        )


def test_result_cannot_discard_candidate_state_for_an_elimination_log() -> None:
    step = next_step(pair_state())
    assert isinstance(step, EliminationStep)

    with pytest.raises(ValueError, match="final state"):
        LogicalSolveResult(EMPTY, (step,), LogicalSolveStatus.STUCK)


def test_grid_placement_replay_remains_compatible() -> None:
    solved = Grid.from_string(SOLVED_TEXT)
    grid = Grid((0,) + solved.cells[1:])
    step = next_step(grid)

    assert PlacementStep is SolveStep
    assert step == PlacementStep(Technique.NAKED_SINGLE, 0, 0, 5)
    assert apply_step(grid, step) == solved
    updated = apply_step(LogicalState.from_grid(grid), step)
    assert updated == LogicalState.from_grid(solved)
    assert solve_logically(grid) == LogicalSolveResult(
        solved, (step,), LogicalSolveStatus.SOLVED
    )


def test_elimination_cannot_be_replayed_on_a_grid_without_candidate_state() -> None:
    step = next_step(pair_state())
    assert isinstance(step, EliminationStep)

    with pytest.raises(TypeError, match="LogicalState"):
        apply_step(EMPTY, step)


def test_partial_or_overextended_elimination_cannot_impersonate_a_full_deduction() -> (
    None
):
    state = pair_state()
    step = next_step(state)
    assert isinstance(step, EliminationStep)
    partial = EliminationStep(step.technique, step.eliminations[:1])
    overextended = EliminationStep(
        step.technique, step.eliminations + (CandidateElimination(8, 8, 2),)
    )
    for invalid in (partial, overextended):
        with pytest.raises(ValueError, match="technique"):
            apply_step(state, invalid)


def test_stale_elimination_cannot_remove_candidates_twice() -> None:
    state = pair_state()
    step = next_step(state)
    assert isinstance(step, EliminationStep)
    updated = apply_step(state, step)

    with pytest.raises(ValueError, match="exist"):
        apply_step(updated, step)


def test_eliminations_never_target_a_filled_cell() -> None:
    state = LogicalState.from_grid(Grid.from_string(SOLVED_TEXT))
    step = EliminationStep(Technique.POINTING, (CandidateElimination(0, 0, 5),))

    with pytest.raises(ValueError, match="empty cell"):
        apply_step(state, step)


def test_placement_never_resurrects_earlier_logical_eliminations() -> None:
    state = pair_state()
    options = list(state.candidates)
    options[4] = frozenset({2, 7, 9})
    state = LogicalState(state.grid, tuple(options))
    elimination = next_step(state)
    assert isinstance(elimination, EliminationStep)
    reduced = apply_step(state, elimination)
    placement = next_step(reduced)
    assert placement == SolveStep(Technique.NAKED_SINGLE, 0, 4, 9)

    updated = apply_step(reduced, placement)

    assert updated.candidates[4] == frozenset()
    assert {2, 7} <= candidates(updated.grid, 0, 1)
    assert not updated.candidates[1] & {2, 7, 9}
    for i, values in enumerate(updated.candidates):
        assert values == reduced.candidates[i] & candidates(updated.grid, *divmod(i, 9))
    assert state.grid == EMPTY
