"""Independent persistent-candidate fixtures for triples and X-Wings."""

from collections.abc import Iterable
from unittest.mock import patch

import pytest

from sudoku_gen import _logical_techniques as techniques
from sudoku_gen.human_solver import (
    CandidateElimination,
    EliminationStep,
    LogicalState,
    SolveStep,
    Technique,
    apply_step,
    next_step,
    solve_logically,
)
from sudoku_gen.models import Grid

type Cell = tuple[int, int]

DIGITS = frozenset(range(1, 10))
EMPTY_GRID = Grid((0,) * 81)


def state_with(overrides: dict[Cell, Iterable[int]]) -> LogicalState:
    values = [DIGITS] * 81
    for (row, column), options in overrides.items():
        values[row * 9 + column] = frozenset(options)
    return LogicalState(EMPTY_GRID, tuple(values))


def row_cells(row: int) -> tuple[Cell, ...]:
    return tuple((row, column) for column in range(9))


def column_cells(column: int) -> tuple[Cell, ...]:
    return tuple((row, column) for row in range(9))


def box_cells(box_row: int, box_column: int) -> tuple[Cell, ...]:
    return tuple(
        (row, column)
        for row in range(box_row * 3, box_row * 3 + 3)
        for column in range(box_column * 3, box_column * 3 + 3)
    )


def expected_step(
    technique: Technique, removals: Iterable[tuple[Cell, int]]
) -> EliminationStep:
    return EliminationStep(
        technique,
        tuple(CandidateElimination(*cell, value) for cell, value in removals),
    )


TRIPLE_UNITS = (
    pytest.param(row_cells(0), ((0, 0), (0, 1), (0, 2)), id="row"),
    pytest.param(column_cells(8), ((0, 8), (3, 8), (8, 8)), id="column"),
    pytest.param(box_cells(2, 2), ((6, 6), (6, 7), (7, 6)), id="boundary-box"),
)
HIDDEN_TRIPLE_UNITS = (
    pytest.param(row_cells(0), ((0, 0), (0, 3), (0, 6)), id="row"),
    pytest.param(column_cells(8), ((0, 8), (3, 8), (6, 8)), id="column"),
    pytest.param(box_cells(2, 2), ((6, 6), (7, 7), (8, 8)), id="boundary-box"),
)


@pytest.mark.parametrize(("unit", "cells"), TRIPLE_UNITS)
@pytest.mark.parametrize(
    "options", [({1, 2}, {1, 3}, {2, 3}), ({1, 2, 3}, {1, 2}, {2, 3})]
)
def test_naked_triple_removes_its_three_digits_in_every_unit(
    unit: tuple[Cell, ...],
    cells: tuple[Cell, Cell, Cell],
    options: tuple[set[int], ...],
) -> None:
    state = state_with(dict(zip(cells, options, strict=True)))
    expected = expected_step(
        Technique.NAKED_TRIPLE,
        ((cell, value) for cell in unit if cell not in cells for value in (1, 2, 3)),
    )

    assert next_step(state) == expected
    updated = apply_step(state, expected)

    assert isinstance(updated, LogicalState)
    assert all(
        updated.candidates[row * 9 + column] == frozenset(options[index])
        for index, (row, column) in enumerate(cells)
    )


def test_naked_triple_requires_exactly_three_confined_cells_and_real_removals() -> None:
    four_cells = state_with(
        {
            (0, column): options
            for column, options in enumerate(({1, 2}, {1, 3}, {2, 3}, {1, 2, 3}))
        }
    )
    no_removal = state_with(
        {
            **{(0, column): DIGITS - {1, 2, 3} for column in range(3, 9)},
            (0, 0): {1, 2},
            (0, 1): {1, 3},
            (0, 2): {2, 3},
        }
    )

    assert not any(
        removal.row == 0
        and removal.column in range(4, 9)
        and removal.value in (1, 2, 3)
        for step in techniques.naked_triples(four_cells)
        for removal in step.eliminations
    )
    assert not any(
        removal.row == 0
        and removal.column in range(3, 9)
        and removal.value in (1, 2, 3)
        for step in techniques.naked_triples(no_removal)
        for removal in step.eliminations
    )


def test_naked_triple_cell_combination_order_is_deterministic() -> None:
    state = state_with(
        {
            (0, 0): {4, 5},
            (0, 3): {4, 6},
            (0, 6): {5, 6},
            (1, 0): {1, 2},
            (1, 3): {1, 3},
            (1, 6): {2, 3},
        }
    )
    expected = expected_step(
        Technique.NAKED_TRIPLE,
        (((0, column), value) for column in (1, 2, 4, 5, 7, 8) for value in (4, 5, 6)),
    )

    assert next_step(state) == expected


@pytest.mark.parametrize(("unit", "cells"), HIDDEN_TRIPLE_UNITS)
def test_hidden_triple_removes_extra_candidates_in_every_unit(
    unit: tuple[Cell, ...], cells: tuple[Cell, Cell, Cell]
) -> None:
    overrides: dict[Cell, Iterable[int]] = {cell: DIGITS - {1, 2, 3} for cell in unit}
    overrides.update({cells[0]: {1, 2, 4, 5}, cells[1]: {1, 3, 6}, cells[2]: {2, 3, 7}})
    state = state_with(overrides)
    expected = expected_step(
        Technique.HIDDEN_TRIPLE,
        [(cells[0], value) for value in (4, 5)] + [(cells[1], 6), (cells[2], 7)],
    )

    assert next_step(state) == expected
    updated = apply_step(state, expected)
    assert isinstance(updated, LogicalState)
    assert updated.candidates[cells[0][0] * 9 + cells[0][1]] == frozenset({1, 2})
    assert updated.candidates[cells[1][0] * 9 + cells[1][1]] == frozenset({1, 3})
    assert updated.candidates[cells[2][0] * 9 + cells[2][1]] == frozenset({2, 3})


def test_hidden_triple_rejects_a_fourth_digit_position_and_no_progress() -> None:
    unit = row_cells(0)
    base = {cell: DIGITS - {1, 2, 3} for cell in unit}
    base.update({(0, 0): {1, 2, 4}, (0, 1): {1, 3, 5}, (0, 2): {2, 3, 6}})
    fourth = state_with(base | {(0, 4): {1, 4, 5, 6, 7, 8, 9}})
    no_progress = state_with(
        {
            **{cell: DIGITS - {1, 2, 3} for cell in unit},
            (0, 0): {1, 2},
            (0, 1): {1, 3},
            (0, 2): {2, 3},
        }
    )

    assert not any(
        removal.row == 0 and removal.column in (0, 1, 2) and removal.value in (4, 5, 6)
        for step in techniques.hidden_triples(fourth)
        for removal in step.eliminations
    )
    assert next(techniques.hidden_triples(no_progress), None) is None


def x_wing_rows(
    digit: int, rows: tuple[int, int], columns: tuple[int, int]
) -> dict[Cell, Iterable[int]]:
    return {
        (row, column): DIGITS - {digit}
        for row in rows
        for column in range(9)
        if column not in columns
    }


def x_wing_columns(
    digit: int, columns: tuple[int, int], rows: tuple[int, int]
) -> dict[Cell, Iterable[int]]:
    return {
        (row, column): DIGITS - {digit}
        for column in columns
        for row in range(9)
        if row not in rows
    }


def test_row_based_x_wing_eliminates_from_other_rows_only() -> None:
    state = state_with(x_wing_rows(5, (0, 3), (1, 7)))
    expected = expected_step(
        Technique.X_WING,
        (
            ((row, column), 5)
            for row in range(9)
            if row not in (0, 3)
            for column in (1, 7)
        ),
    )

    assert next_step(state) == expected
    updated = apply_step(state, expected)
    assert isinstance(updated, LogicalState)
    assert all(
        updated.candidates[row * 9 + column] == state.candidates[row * 9 + column]
        for row in (0, 3)
        for column in (1, 7)
    )


def test_column_based_x_wing_eliminates_from_other_columns_only() -> None:
    state = state_with(x_wing_columns(6, (0, 4), (2, 7)))
    expected = expected_step(
        Technique.X_WING,
        (
            ((row, column), 6)
            for row in (2, 7)
            for column in range(9)
            if column not in (0, 4)
        ),
    )

    assert next_step(state) == expected


def test_x_wing_requires_two_matching_positions_and_real_eliminations() -> None:
    too_many = state_with(x_wing_rows(5, (0, 3), (1, 7)) | {(0, 4): DIGITS})
    mismatched = state_with(x_wing_rows(5, (0,), (1, 7)) | x_wing_rows(5, (3,), (1, 8)))
    no_removal = state_with(
        x_wing_rows(5, (0, 3), (1, 7))
        | {
            (row, column): DIGITS - {5}
            for row in range(9)
            if row not in (0, 3)
            for column in (1, 7)
        }
    )

    assert next(techniques.x_wings(too_many), None) is None
    assert next(techniques.x_wings(mismatched), None) is None
    assert next(techniques.x_wings(no_removal), None) is None


def test_x_wing_row_orientation_digit_and_source_order_are_deterministic() -> None:
    state = state_with(x_wing_rows(7, (0, 4), (2, 6)) | x_wing_rows(2, (1, 5), (3, 8)))
    expected = expected_step(
        Technique.X_WING,
        (
            ((row, column), 2)
            for row in range(9)
            if row not in (1, 5)
            for column in (3, 8)
        ),
    )

    assert next_step(state) == expected


def test_triple_and_x_wing_restart_priority_and_replay_mixed_steps() -> None:
    triple_state = state_with(
        {(0, 0): {1, 2}, (0, 1): {1, 3}, (0, 2): {2, 3}, (0, 4): {1, 2, 3, 9}}
    )
    triple = next_step(triple_state)
    assert isinstance(triple, EliminationStep)
    assert triple.technique is Technique.NAKED_TRIPLE
    after_triple = apply_step(triple_state, triple)
    assert next_step(after_triple) == SolveStep(Technique.NAKED_SINGLE, 0, 4, 9)

    x_wing_state = state_with(
        x_wing_rows(5, (0, 3), (1, 7))
        | {(4, column): DIGITS - {5} for column in range(9) if column not in (1, 4)}
    )
    x_wing = next_step(x_wing_state)
    assert isinstance(x_wing, EliminationStep)
    assert x_wing.technique is Technique.X_WING
    after_x_wing = apply_step(x_wing_state, x_wing)
    assert next_step(after_x_wing) == SolveStep(Technique.HIDDEN_SINGLE, 4, 4, 5)

    result = solve_logically(triple_state)
    replay = triple_state
    for step in result.steps:
        replay = apply_step(replay, step)
    assert replay == result.state


@pytest.mark.parametrize(
    "technique",
    (Technique.NAKED_TRIPLE, Technique.HIDDEN_TRIPLE, Technique.X_WING),
)
def test_new_techniques_reject_fabricated_eliminations(technique: Technique) -> None:
    fabricated = expected_step(technique, [((0, 0), 1)])

    with pytest.raises(ValueError):
        apply_step(LogicalState.from_grid(EMPTY_GRID), fabricated)


def test_real_generated_fixture_previously_stuck_now_solves_with_x_wing() -> None:
    """Seed 100003 from the Phase 1 diagnostic population at target 30."""
    grid = Grid.from_string(
        "509400006000700209000020054650078000800000002000130078780060000903007000100002907"
    )

    def empty(state: LogicalState) -> Iterable[EliminationStep]:
        return iter(())

    with (
        patch.object(techniques, "naked_triples", empty),
        patch.object(techniques, "hidden_triples", empty),
        patch.object(techniques, "x_wings", empty),
    ):
        previous = solve_logically(grid)
    current = solve_logically(grid)

    assert previous.status.name == "STUCK"
    assert len(previous.steps) == 25
    assert current.status.name == "SOLVED"
    assert len(current.steps) == 53
    assert any(step.technique is Technique.X_WING for step in current.steps)
