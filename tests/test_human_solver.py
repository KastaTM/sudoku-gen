"""Logical solving, validated moves, immutable results, and replay invariants."""

from dataclasses import FrozenInstanceError

import pytest
from hypothesis import example, given, seed, settings
from hypothesis import strategies as st

from sudoku_gen.candidates import candidates
from sudoku_gen.exceptions import InvalidGridError
from sudoku_gen.human_solver import (
    LogicalSolveResult,
    LogicalSolveStatus,
    LogicalState,
    SolveStep,
    Technique,
    apply_step,
    next_step,
    solve_logically,
)
from sudoku_gen.models import Grid
from sudoku_gen.solver import solve
from sudoku_gen.validation import empty_cells, is_valid_grid, is_valid_solution

SOLVED_TEXT = (
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)
NAKED_ONLY_TEXT = (
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
)
HIDDEN_NEEDED_TEXT = (
    "000070902672000000000300560800760023400803700713004850000507080080400035305006170"
)
STRONGER_TECHNIQUES_TEXT = (
    "100007090030020008009400500005300900010080002400006000300000010060000007007000300"
)
BLOCKED_TEXT = "012345678" + "0" * 18 + "900000000" + "0" * 45
# Both leading cells need 1: placing the first leaves the second with no digit.
LATER_CONTRADICTION_TEXT = "003456789" + "002000000" + "0" * 63
LATE_BLOCKED_CELL_TEXT = "123456708" + "0" * 36 + "000000009" + "0" * 18 + "876543210"


def without_clues(*indices: int) -> Grid:
    """Remove named clues from the fixed solution without changing other cells."""
    solved = Grid.from_string(SOLVED_TEXT)
    return Grid(
        tuple(
            0 if index in indices else value for index, value in enumerate(solved.cells)
        )
    )


def test_an_already_solved_grid_needs_no_steps() -> None:
    grid = Grid.from_string(SOLVED_TEXT)

    assert next_step(grid) is None
    assert solve_logically(grid) == LogicalSolveResult(
        grid, (), LogicalSolveStatus.SOLVED
    )
    assert solve_logically(grid).solved


def test_an_empty_grid_is_stuck_without_guessing() -> None:
    grid = Grid((0,) * 81)

    assert next_step(grid) is None
    result = solve_logically(grid)

    assert result == LogicalSolveResult(grid, (), LogicalSolveStatus.STUCK)
    assert not result.solved


def test_a_puzzle_can_be_completed_using_only_naked_singles() -> None:
    result = solve_logically(Grid.from_string(NAKED_ONLY_TEXT))

    assert result.solved
    assert result.status is LogicalSolveStatus.SOLVED
    assert result.grid == Grid.from_string(SOLVED_TEXT)
    assert len(result.steps) == 51
    assert all(step.technique is Technique.NAKED_SINGLE for step in result.steps)


def test_hidden_singles_allow_progress_after_naked_singles_are_exhausted() -> None:
    puzzle = Grid.from_string(HIDDEN_NEEDED_TEXT)
    result = solve_logically(puzzle)

    assert result.solved
    assert result.grid == Grid.from_string(SOLVED_TEXT)
    assert len(result.steps) == 45
    current = puzzle
    for step in result.steps:
        if step.technique is Technique.HIDDEN_SINGLE:
            assert all(
                len(candidates(current, row, column)) > 1
                for row, column in empty_cells(current)
            )
            assert step == SolveStep(Technique.HIDDEN_SINGLE, 0, 1, 3)
            break
        current = apply_step(current, step)
    else:
        pytest.fail("This puzzle must require a Hidden Single to make progress.")


def test_a_harder_puzzle_stops_after_recording_its_available_single() -> None:
    puzzle = Grid.from_string(STRONGER_TECHNIQUES_TEXT)

    result = solve_logically(puzzle)

    assert result.status is LogicalSolveStatus.STUCK
    assert not result.solved
    assert result.steps == (SolveStep(Technique.HIDDEN_SINGLE, 7, 2, 1),)
    assert result.grid != puzzle
    assert is_valid_grid(result.grid)
    assert not is_valid_solution(result.grid)
    assert next_step(result.grid) is None


def test_stuck_does_not_claim_an_unsatisfiable_puzzle_has_a_solution() -> None:
    # This legal but wrong branch of the harder fixture needs search to refute.
    grid = Grid.from_string(
        STRONGER_TECHNIQUES_TEXT[:11] + "4" + STRONGER_TECHNIQUES_TEXT[12:]
    )
    assert is_valid_grid(grid)
    assert solve(grid) is None

    result = solve_logically(grid)

    assert result.status is LogicalSolveStatus.STUCK
    assert not result.solved
    assert result.steps == (SolveStep(Technique.HIDDEN_SINGLE, 7, 2, 1),)
    assert all(
        candidates(result.grid, row, column) for row, column in empty_cells(result.grid)
    )


def test_step_log_records_exact_application_order_across_grid_boundaries() -> None:
    puzzle = without_clues(0, 8, 40, 72, 80)

    result = solve_logically(puzzle)

    assert result.steps == (
        SolveStep(Technique.NAKED_SINGLE, 0, 0, 5),
        SolveStep(Technique.NAKED_SINGLE, 0, 8, 2),
        SolveStep(Technique.NAKED_SINGLE, 4, 4, 5),
        SolveStep(Technique.NAKED_SINGLE, 8, 0, 3),
        SolveStep(Technique.NAKED_SINGLE, 8, 8, 9),
    )
    assert result.grid == Grid.from_string(SOLVED_TEXT)


@pytest.mark.parametrize(
    "text",
    [
        NAKED_ONLY_TEXT,
        HIDDEN_NEEDED_TEXT,
        STRONGER_TECHNIQUES_TEXT,
        LATER_CONTRADICTION_TEXT,
    ],
)
def test_replaying_the_recorded_steps_reproduces_the_result(text: str) -> None:
    original = Grid.from_string(text)
    result = solve_logically(original)
    replayed = original

    for step in result.steps:
        assert next_step(replayed) == step
        assert replayed.cells[step.row * 9 + step.column] == 0
        assert step.value in candidates(replayed, step.row, step.column)
        replayed = apply_step(replayed, step)
        assert is_valid_grid(replayed)

    assert replayed == result.grid
    assert original.to_string() == text


@pytest.mark.parametrize(
    "text",
    [
        SOLVED_TEXT,
        NAKED_ONLY_TEXT,
        HIDDEN_NEEDED_TEXT,
        STRONGER_TECHNIQUES_TEXT,
        "0" * 81,
        "11" + "0" * 79,
        BLOCKED_TEXT,
        LATER_CONTRADICTION_TEXT,
    ],
)
def test_repeated_logical_solving_is_identical_and_does_not_mutate_input(
    text: str,
) -> None:
    grid = Grid.from_string(text)
    original_cells = grid.cells
    original_hash = hash(grid)

    assert solve_logically(grid) == solve_logically(grid)
    assert grid.cells == original_cells
    assert grid.to_string() == text
    assert hash(grid) == original_hash


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("11" + "0" * 79, id="row-conflict"),
        pytest.param("1" + "0" * 26 + "1" + "0" * 53, id="column-conflict"),
        pytest.param("1" + "0" * 9 + "1" + "0" * 70, id="box-conflict"),
        pytest.param("1" * 81, id="complete-invalid-grid"),
        pytest.param(BLOCKED_TEXT, id="zero-candidate-empty-cell"),
    ],
)
def test_invalid_or_blocked_starting_grids_report_a_contradiction(text: str) -> None:
    grid = Grid.from_string(text)

    with pytest.raises(InvalidGridError):
        next_step(grid)
    with pytest.raises(InvalidGridError):
        apply_step(grid, SolveStep(Technique.NAKED_SINGLE, 8, 8, 9))

    result = solve_logically(grid)

    assert result == LogicalSolveResult(grid, (), LogicalSolveStatus.CONTRADICTION)
    assert not result.solved


def test_a_contradiction_after_a_move_preserves_the_successful_step_log() -> None:
    grid = Grid.from_string(LATER_CONTRADICTION_TEXT)
    assert is_valid_grid(grid)
    assert all(candidates(grid, row, column) for row, column in empty_cells(grid))

    result = solve_logically(grid)

    assert result.status is LogicalSolveStatus.CONTRADICTION
    assert not result.solved
    assert result.steps == (SolveStep(Technique.NAKED_SINGLE, 0, 0, 1),)
    assert result.grid == apply_step(grid, result.steps[0])
    assert is_valid_grid(result.grid)
    assert candidates(result.grid, 0, 1) == frozenset()
    with pytest.raises(InvalidGridError):
        next_step(result.grid)


def test_a_later_zero_candidate_cell_prevents_an_earlier_single_being_applied() -> None:
    grid = Grid.from_string(LATE_BLOCKED_CELL_TEXT)
    assert is_valid_grid(grid)
    assert candidates(grid, 0, 7) == frozenset({9})
    assert candidates(grid, 8, 8) == frozenset()

    with pytest.raises(InvalidGridError):
        next_step(grid)
    with pytest.raises(InvalidGridError):
        apply_step(grid, SolveStep(Technique.NAKED_SINGLE, 0, 7, 9))
    assert solve_logically(grid) == LogicalSolveResult(
        grid, (), LogicalSolveStatus.CONTRADICTION
    )


def test_applying_a_step_creates_a_new_grid_and_preserves_other_cells() -> None:
    original = without_clues(0, 80)

    result = apply_step(original, SolveStep(Technique.NAKED_SINGLE, 0, 0, 5))

    assert result is not original
    assert result.cells == (5,) + original.cells[1:]
    assert original.cells[0] == 0
    assert is_valid_grid(result)


@pytest.mark.parametrize("technique", [Technique.NAKED_SINGLE, Technique.HIDDEN_SINGLE])
def test_apply_accepts_a_justified_step_even_when_another_move_has_priority(
    technique: Technique,
) -> None:
    grid = without_clues(0, 80)
    step = SolveStep(technique, 8, 8, 9)

    assert next_step(grid) == SolveStep(Technique.NAKED_SINGLE, 0, 0, 5)
    assert apply_step(grid, step) == without_clues(0)


def test_apply_rejects_an_occupied_target_even_when_the_digit_matches() -> None:
    with pytest.raises(ValueError, match="empty"):
        apply_step(
            Grid.from_string(SOLVED_TEXT), SolveStep(Technique.NAKED_SINGLE, 0, 0, 5)
        )


@pytest.mark.parametrize("technique", [Technique.NAKED_SINGLE, Technique.HIDDEN_SINGLE])
def test_apply_rejects_a_digit_that_is_not_a_legal_candidate(
    technique: Technique,
) -> None:
    with pytest.raises(ValueError, match="candidate"):
        apply_step(without_clues(0), SolveStep(technique, 0, 0, 3))


@pytest.mark.parametrize("technique", [Technique.NAKED_SINGLE, Technique.HIDDEN_SINGLE])
def test_apply_rejects_legal_candidates_without_the_declared_logical_justification(
    technique: Technique,
) -> None:
    empty = Grid((0,) * 81)
    assert 1 in candidates(empty, 0, 0)

    with pytest.raises(ValueError, match="technique"):
        apply_step(empty, SolveStep(technique, 0, 0, 1))


@pytest.mark.parametrize("step", [None, (Technique.NAKED_SINGLE, 0, 0, 1)])
def test_apply_requires_a_solve_step(step: object) -> None:
    with pytest.raises(TypeError, match="SolveStep"):
        apply_step(Grid((0,) * 81), step)


@pytest.mark.parametrize("coordinate", ["row", "column"])
@pytest.mark.parametrize("value", [-1, 9])
def test_step_coordinates_reject_out_of_bounds_indices(
    coordinate: str, value: int
) -> None:
    coordinates = {"row": 0, "column": 0, coordinate: value}

    with pytest.raises(IndexError):
        SolveStep(Technique.NAKED_SINGLE, value=1, **coordinates)


class IntegerSubclass(int):
    """Values must follow the domain's exact built-in integer convention."""


@pytest.mark.parametrize("field", ["row", "column", "value"])
@pytest.mark.parametrize("value", [True, False, 1.0, "1", None, IntegerSubclass(1)])
def test_step_coordinates_and_digit_reject_non_builtin_integers(
    field: str, value: object
) -> None:
    fields = {"row": 0, "column": 0, "value": 1, field: value}

    with pytest.raises(TypeError):
        SolveStep(Technique.NAKED_SINGLE, **fields)


@pytest.mark.parametrize("value", [-1, 0, 10])
def test_step_value_must_be_a_filled_sudoku_digit(value: int) -> None:
    with pytest.raises(ValueError):
        SolveStep(Technique.NAKED_SINGLE, 0, 0, value)


@pytest.mark.parametrize("technique", ["naked_single", None, 1])
def test_step_requires_a_technique_enum(technique: object) -> None:
    with pytest.raises(TypeError):
        SolveStep(technique, 0, 0, 1)


def test_steps_and_results_are_immutable_hashable_value_objects() -> None:
    first = SolveStep(Technique.NAKED_SINGLE, 0, 0, 5)
    equivalent = SolveStep(Technique.NAKED_SINGLE, 0, 0, 5)
    result = solve_logically(without_clues(0))
    equivalent_result = LogicalSolveResult(
        Grid.from_string(SOLVED_TEXT), (equivalent,), LogicalSolveStatus.SOLVED
    )

    assert first == equivalent
    assert hash(first) == hash(equivalent)
    assert result == equivalent_result
    assert hash(result) == hash(equivalent_result)
    assert isinstance(result.steps, tuple)
    with pytest.raises(FrozenInstanceError):
        first.value = 6
    with pytest.raises(FrozenInstanceError):
        result.grid = Grid((0,) * 81)
    with pytest.raises(FrozenInstanceError):
        result.steps = ()
    with pytest.raises(FrozenInstanceError):
        result.status = LogicalSolveStatus.STUCK


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("grid", None),
        ("steps", []),
        ("steps", (None,)),
        ("status", "solved"),
        ("status", None),
    ],
)
def test_result_requires_typed_immutable_fields(field: str, value: object) -> None:
    fields = {
        "grid": Grid((0,) * 81),
        "steps": (),
        "status": LogicalSolveStatus.STUCK,
        field: value,
    }

    with pytest.raises(TypeError):
        LogicalSolveResult(**fields)


@seed(1707)
@settings(max_examples=20, deadline=None)
@given(removed=st.sets(st.integers(min_value=0, max_value=80)))
@example(removed=set())
@example(removed=set(range(81)))
def test_logical_moves_preserve_candidates_clues_and_validity(
    removed: set[int],
) -> None:
    solved = Grid.from_string(SOLVED_TEXT)
    original = without_clues(*removed)
    result = solve_logically(original)
    current = LogicalState.from_grid(original)

    assert result.status is not LogicalSolveStatus.CONTRADICTION
    for step in result.steps:
        if isinstance(step, SolveStep):
            assert current.grid.cells[step.row * 9 + step.column] == 0
            assert step.value in candidates(current.grid, step.row, step.column)
        else:
            assert all(
                item.value in current.candidates[item.row * 9 + item.column]
                for item in step.eliminations
            )
        current = apply_step(current, step)
        assert is_valid_grid(current.grid)
        assert all(
            clue == 0 or clue == value
            for clue, value in zip(original.cells, current.grid.cells, strict=True)
        )

    assert current == result.state
    assert current.grid == result.grid
    assert all(
        value == 0 or value == answer
        for value, answer in zip(result.grid.cells, solved.cells, strict=True)
    )
    assert original == without_clues(*removed)
