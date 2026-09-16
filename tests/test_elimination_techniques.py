"""Independent candidate-state fixtures for the four elimination techniques."""

from collections.abc import Iterable

import pytest

from sudoku_gen.human_solver import (
    CandidateElimination,
    EliminationStep,
    LogicalSolveStatus,
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
    """Supply previously reduced candidates without changing any grid clues."""
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


def assert_exact_eliminations(
    state: LogicalState, expected: EliminationStep
) -> LogicalState:
    """Check detection, every changed candidate, and the untouched grid."""
    assert next_step(state) == expected
    assert next_step(state) == expected
    updated = apply_step(state, expected)
    assert isinstance(updated, LogicalState)
    assert updated.grid == state.grid
    for index, options in enumerate(state.candidates):
        row, column = divmod(index, 9)
        removed = {
            item.value
            for item in expected.eliminations
            if (item.row, item.column) == (row, column)
        }
        assert updated.candidates[index] == options - removed
    return updated


PAIR_UNITS = [
    pytest.param(row_cells(8), ((8, 0), (8, 8)), id="row-across-box-boundaries"),
    pytest.param(column_cells(8), ((0, 8), (8, 8)), id="column-across-box-boundaries"),
    pytest.param(box_cells(2, 2), ((6, 6), (8, 8)), id="bottom-right-box-diagonal"),
]


@pytest.mark.parametrize(("unit", "pair"), PAIR_UNITS)
def test_naked_pair_removes_both_digits_only_from_other_cells_in_its_unit(
    unit: tuple[Cell, ...], pair: tuple[Cell, Cell]
) -> None:
    state = state_with({cell: {2, 7} for cell in pair})
    expected = expected_step(
        Technique.NAKED_PAIR,
        ((cell, digit) for cell in unit if cell not in pair for digit in (2, 7)),
    )

    updated = assert_exact_eliminations(state, expected)

    for row, column in pair:
        assert updated.candidates[row * 9 + column] == frozenset({2, 7})


@pytest.mark.parametrize(("unit", "pair"), PAIR_UNITS)
def test_naked_pair_without_any_actual_removal_is_not_reported(
    unit: tuple[Cell, ...], pair: tuple[Cell, Cell]
) -> None:
    state = state_with(
        {cell: {2, 7} if cell in pair else DIGITS - {2, 7} for cell in unit}
    )

    assert next_step(state) is None


@pytest.mark.parametrize(
    "cells",
    [
        pytest.param(((8, 0), (8, 3), (8, 8)), id="row"),
        pytest.param(((0, 8), (3, 8), (8, 8)), id="column"),
        pytest.param(((6, 6), (7, 7), (8, 8)), id="box"),
    ],
)
def test_three_identical_two_candidate_cells_are_not_a_naked_pair(
    cells: tuple[Cell, ...],
) -> None:
    state = state_with({cell: {2, 7} for cell in cells})

    assert next_step(state) is None


def test_naked_pair_digit_order_precedes_pair_cell_order() -> None:
    state = state_with({(0, 0): {4, 6}, (0, 2): {4, 6}, (0, 6): {2, 8}, (0, 8): {2, 8}})
    expected = expected_step(
        Technique.NAKED_PAIR,
        (
            (cell, digit)
            for cell in ((0, 1), (0, 3), (0, 4), (0, 5), (0, 7))
            for digit in (2, 8)
        ),
    )

    assert_exact_eliminations(state, expected)


def test_naked_pair_row_priority_precedes_column_and_digit_priority() -> None:
    state = state_with({(8, 0): {7, 9}, (8, 8): {7, 9}, (0, 1): {1, 2}, (3, 1): {1, 2}})
    expected = expected_step(
        Technique.NAKED_PAIR,
        (((8, column), digit) for column in range(1, 8) for digit in (7, 9)),
    )

    assert_exact_eliminations(state, expected)


def hidden_pair_overrides(
    unit: tuple[Cell, ...], pair: tuple[Cell, Cell]
) -> dict[Cell, Iterable[int]]:
    overrides: dict[Cell, Iterable[int]] = {cell: DIGITS - {4, 6} for cell in unit}
    overrides[pair[0]] = {1, 4, 6}
    overrides[pair[1]] = {2, 4, 6, 8}
    return overrides


@pytest.mark.parametrize(("unit", "pair"), PAIR_UNITS)
def test_hidden_pair_removes_only_the_extra_candidates_in_its_two_cells(
    unit: tuple[Cell, ...], pair: tuple[Cell, Cell]
) -> None:
    state = state_with(hidden_pair_overrides(unit, pair))
    for digit in (4, 6):
        assert (
            tuple(
                cell
                for cell in unit
                if digit in state.candidates[cell[0] * 9 + cell[1]]
            )
            == pair
        )
    expected = expected_step(
        Technique.HIDDEN_PAIR, [(pair[0], 1), (pair[1], 2), (pair[1], 8)]
    )

    updated = assert_exact_eliminations(state, expected)

    assert all(updated.candidates[r * 9 + c] == frozenset({4, 6}) for r, c in pair)


@pytest.mark.parametrize(("unit", "pair"), PAIR_UNITS)
def test_hidden_pair_requires_both_digits_to_be_absent_from_every_third_cell(
    unit: tuple[Cell, ...], pair: tuple[Cell, Cell]
) -> None:
    overrides = hidden_pair_overrides(unit, pair)
    third = unit[4]
    overrides[third] = DIGITS - {6}
    state = state_with(overrides)

    assert next_step(state) is None


def test_hidden_pair_digit_order_precedes_cell_order() -> None:
    overrides: dict[Cell, Iterable[int]] = {
        cell: DIGITS - {3, 4, 6, 8} for cell in row_cells(0)
    }
    overrides.update(
        {(0, 0): {1, 4, 6}, (0, 2): {2, 4, 6}, (0, 6): {1, 3, 8}, (0, 8): {2, 3, 8}}
    )
    state = state_with(overrides)
    expected = expected_step(Technique.HIDDEN_PAIR, [((0, 6), 1), ((0, 8), 2)])

    assert_exact_eliminations(state, expected)


@pytest.mark.parametrize("box_row", range(3))
@pytest.mark.parametrize("box_column", range(3))
def test_box_hidden_pair_respects_all_box_boundaries(
    box_row: int, box_column: int
) -> None:
    unit = box_cells(box_row, box_column)
    pair = (unit[0], unit[-1])
    state = state_with(hidden_pair_overrides(unit, pair))
    expected = expected_step(
        Technique.HIDDEN_PAIR, [(pair[0], 1), (pair[1], 2), (pair[1], 8)]
    )

    assert_exact_eliminations(state, expected)


def restrict_digit(
    unit: Iterable[Cell], source: Iterable[Cell], digit: int
) -> dict[Cell, Iterable[int]]:
    remaining = set(source)
    return {cell: DIGITS - {digit} for cell in unit if cell not in remaining}


@pytest.mark.parametrize(
    ("source", "targets"),
    [
        pytest.param(((8, 6), (8, 8)), row_cells(8)[:6], id="row-pair"),
        pytest.param(((6, 8), (8, 8)), column_cells(8)[:6], id="column-pair"),
        pytest.param(((8, 6), (8, 7), (8, 8)), row_cells(8)[:6], id="row-triple"),
        pytest.param(((6, 8), (7, 8), (8, 8)), column_cells(8)[:6], id="column-triple"),
    ],
)
def test_pointing_removes_digit_only_outside_the_source_box(
    source: tuple[Cell, ...], targets: tuple[Cell, ...]
) -> None:
    unit = box_cells(2, 2)
    state = state_with(restrict_digit(unit, source, 5))
    assert tuple(
        cell for cell in unit if 5 in state.candidates[cell[0] * 9 + cell[1]]
    ) == (source)
    expected = expected_step(Technique.POINTING, ((cell, 5) for cell in targets))

    assert_exact_eliminations(state, expected)


def test_pointing_requires_box_candidates_to_share_one_row_or_column() -> None:
    state = state_with(restrict_digit(box_cells(2, 2), ((6, 6), (6, 8), (8, 6)), 5))

    assert next_step(state) is None


def test_pointing_without_any_outside_candidate_to_remove_is_not_reported() -> None:
    overrides = restrict_digit(box_cells(2, 2), ((8, 6), (8, 8)), 5)
    overrides.update({cell: DIGITS - {5} for cell in row_cells(8)[:6]})
    state = state_with(overrides)

    assert next_step(state) is None


def test_pointing_scans_box_index_before_digit() -> None:
    overrides = restrict_digit(box_cells(0, 0), ((0, 0), (0, 2)), 8)
    overrides.update(restrict_digit(box_cells(2, 2), ((8, 6), (8, 8)), 2))
    state = state_with(overrides)
    expected = expected_step(
        Technique.POINTING, ((cell, 8) for cell in row_cells(0)[3:])
    )

    assert_exact_eliminations(state, expected)


def test_pointing_scans_digits_before_source_line_order() -> None:
    overrides: dict[Cell, Iterable[int]] = {}
    for digit, source in [(2, ((2, 0), (2, 2))), (8, ((0, 0), (0, 2)))]:
        for cell, options in restrict_digit(box_cells(0, 0), source, digit).items():
            overrides[cell] = frozenset(overrides.get(cell, DIGITS)) & frozenset(
                options
            )
    state = state_with(overrides)
    expected = expected_step(
        Technique.POINTING, ((cell, 2) for cell in row_cells(2)[3:])
    )

    assert_exact_eliminations(state, expected)


@pytest.mark.parametrize(
    ("line", "source", "targets"),
    [
        pytest.param(row_cells(8), ((8, 6), (8, 8)), box_cells(2, 2)[:6], id="row"),
        pytest.param(
            column_cells(8),
            ((6, 8), (8, 8)),
            tuple(cell for cell in box_cells(2, 2) if cell[1] != 8),
            id="column",
        ),
    ],
)
def test_claiming_removes_digit_only_inside_box_and_outside_source_line(
    line: tuple[Cell, ...], source: tuple[Cell, ...], targets: tuple[Cell, ...]
) -> None:
    state = state_with(restrict_digit(line, source, 5))
    expected = expected_step(
        Technique.BOX_LINE_REDUCTION, ((cell, 5) for cell in targets)
    )

    assert_exact_eliminations(state, expected)


@pytest.mark.parametrize(
    ("line", "source"),
    [
        pytest.param(row_cells(8), ((8, 0), (8, 4), (8, 8)), id="row"),
        pytest.param(column_cells(8), ((0, 8), (4, 8), (8, 8)), id="column"),
    ],
)
def test_claiming_requires_all_line_candidates_to_share_a_box(
    line: tuple[Cell, ...], source: tuple[Cell, ...]
) -> None:
    state = state_with(restrict_digit(line, source, 5))

    assert next_step(state) is None


def test_claiming_without_any_candidate_to_remove_is_not_reported() -> None:
    overrides = restrict_digit(row_cells(8), ((8, 6), (8, 8)), 5)
    overrides.update({cell: DIGITS - {5} for cell in box_cells(2, 2)[:6]})
    state = state_with(overrides)

    assert next_step(state) is None


def test_claiming_rows_precede_columns_even_when_the_column_digit_is_lower() -> None:
    overrides = restrict_digit(row_cells(8), ((8, 6), (8, 8)), 8)
    for cell, options in restrict_digit(column_cells(0), ((3, 0), (5, 0)), 2).items():
        overrides[cell] = frozenset(overrides.get(cell, DIGITS)) & frozenset(options)
    state = state_with(overrides)
    expected = expected_step(
        Technique.BOX_LINE_REDUCTION, ((cell, 8) for cell in box_cells(2, 2)[:6])
    )

    assert_exact_eliminations(state, expected)


def test_claiming_scans_digits_before_source_box_order() -> None:
    overrides: dict[Cell, Iterable[int]] = {}
    for digit, source in [(2, ((8, 6), (8, 8))), (8, ((8, 0), (8, 2)))]:
        for cell, options in restrict_digit(row_cells(8), source, digit).items():
            overrides[cell] = frozenset(overrides.get(cell, DIGITS)) & frozenset(
                options
            )
    state = state_with(overrides)
    expected = expected_step(
        Technique.BOX_LINE_REDUCTION, ((cell, 2) for cell in box_cells(2, 2)[:6])
    )

    assert_exact_eliminations(state, expected)


def test_naked_pair_elimination_immediately_yields_to_the_naked_single_it_creates() -> (
    None
):
    state = state_with({(0, 0): {2, 7}, (0, 8): {2, 7}, (0, 4): {2, 7, 9}})
    first = next_step(state)
    assert isinstance(first, EliminationStep)
    assert first.technique is Technique.NAKED_PAIR
    updated = apply_step(state, first)

    assert next_step(updated) == SolveStep(Technique.NAKED_SINGLE, 0, 4, 9)
    result = solve_logically(state)
    assert result.steps[:2] == (first, SolveStep(Technique.NAKED_SINGLE, 0, 4, 9))


def test_pointing_elimination_immediately_yields_to_the_hidden_single_it_creates() -> (
    None
):
    overrides = restrict_digit(box_cells(0, 0), ((0, 0), (0, 2)), 5)
    overrides.update(restrict_digit(column_cells(3), ((0, 3), (4, 3)), 5))
    state = state_with(overrides)
    first = next_step(state)
    assert isinstance(first, EliminationStep)
    assert first.technique is Technique.POINTING
    updated = apply_step(state, first)

    assert len(updated.candidates[4 * 9 + 3]) > 1
    assert next_step(updated) == SolveStep(Technique.HIDDEN_SINGLE, 4, 3, 5)
    result = solve_logically(state)
    assert result.steps[:2] == (first, SolveStep(Technique.HIDDEN_SINGLE, 4, 3, 5))


def test_a_justified_elimination_can_expose_a_zero_candidate_contradiction() -> None:
    state = state_with({(0, 0): {2, 7}, (0, 8): {2, 7}, (0, 4): {2}})
    step = expected_step(
        Technique.NAKED_PAIR,
        (
            ((0, column), digit)
            for column in range(1, 8)
            for digit in (2, 7)
            if digit in state.candidates[column]
        ),
    )

    updated = apply_step(state, step)

    assert updated.candidates[4] == frozenset()
    assert updated.grid == state.grid
    result = solve_logically(updated)
    assert result.status is LogicalSolveStatus.CONTRADICTION
    assert result.steps == ()


@pytest.mark.parametrize(
    "technique",
    [
        Technique.NAKED_PAIR,
        Technique.HIDDEN_PAIR,
        Technique.POINTING,
        Technique.BOX_LINE_REDUCTION,
    ],
)
def test_a_candidate_cannot_be_removed_without_the_declared_pattern(
    technique: Technique,
) -> None:
    state = LogicalState.from_grid(EMPTY_GRID)
    step = expected_step(technique, [((0, 0), 1)])

    with pytest.raises(ValueError):
        apply_step(state, step)


def test_naked_pair_cannot_be_used_to_remove_a_digit_outside_its_unit() -> None:
    state = state_with({(0, 0): {2, 7}, (0, 8): {2, 7}})
    step = expected_step(Technique.NAKED_PAIR, [((8, 4), 2)])

    with pytest.raises(ValueError):
        apply_step(state, step)
