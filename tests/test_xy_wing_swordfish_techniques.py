"""Synthetic persistent-candidate fixtures for XY-Wing and Swordfish."""

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


def expected_step(
    technique: Technique, removals: Iterable[tuple[Cell, int]]
) -> EliminationStep:
    return EliminationStep(
        technique,
        tuple(CandidateElimination(*cell, value) for cell, value in removals),
    )


def peers(cell: Cell) -> set[Cell]:
    row, column = cell
    return {
        (other_row, other_column)
        for other_row in range(9)
        for other_column in range(9)
        if (other_row, other_column) != cell
        and (
            other_row == row
            or other_column == column
            or (other_row // 3, other_column // 3) == (row // 3, column // 3)
        )
    }


def xy_wing_state(
    pivot: Cell,
    first_pincer: Cell,
    second_pincer: Cell,
    targets: dict[Cell, Iterable[int]],
) -> LogicalState:
    """Build {1,2}, {1,3}, {2,3} with only named external 3 candidates."""
    overrides: dict[Cell, Iterable[int]] = {
        (row, column): DIGITS - {3} for row in range(9) for column in range(9)
    }
    overrides.update(
        {
            pivot: {1, 2},
            first_pincer: {1, 3},
            second_pincer: {2, 3},
            **targets,
        }
    )
    return state_with(overrides)


@pytest.mark.parametrize(
    ("pivot", "first_pincer", "second_pincer", "target"),
    [
        pytest.param((1, 1), (1, 5), (5, 1), (5, 5), id="row-column"),
        pytest.param((1, 1), (1, 5), (2, 2), (2, 5), id="row-box"),
        pytest.param((4, 4), (0, 4), (5, 5), (0, 5), id="column-box"),
    ],
)
def test_xy_wing_supports_each_pivot_peer_combination(
    pivot: Cell, first_pincer: Cell, second_pincer: Cell, target: Cell
) -> None:
    state = xy_wing_state(pivot, first_pincer, second_pincer, {target: {3, 4, 5}})

    assert first_pincer in peers(pivot)
    assert second_pincer in peers(pivot)
    assert second_pincer not in peers(first_pincer)
    assert target in peers(first_pincer) & peers(second_pincer)
    assert next(techniques.xy_wings(state), None) == expected_step(
        Technique.XY_WING, [(target, 3)]
    )


def test_xy_wing_can_remove_many_common_peer_candidates() -> None:
    pivot, first_pincer, second_pincer = (1, 1), (1, 5), (1, 7)
    targets = {(1, 3): {3, 4}, (1, 4): {3, 6}, (1, 8): {3, 7}}
    state = xy_wing_state(pivot, first_pincer, second_pincer, targets)

    assert next(techniques.xy_wings(state), None) == expected_step(
        Technique.XY_WING, ((cell, 3) for cell in targets)
    )


def test_xy_wing_requires_common_peer_exact_bivalue_cells_and_three_digits() -> None:
    pivot, first_pincer, second_pincer = (1, 1), (1, 5), (5, 1)
    no_target = xy_wing_state(pivot, first_pincer, second_pincer, {})
    non_bivalue_pivot = xy_wing_state(
        pivot, first_pincer, second_pincer, {(5, 5): {3, 4}}
    )
    non_bivalue_first = xy_wing_state(
        pivot, first_pincer, second_pincer, {(5, 5): {3, 4}}
    )
    invalid_relation = xy_wing_state(
        pivot, first_pincer, second_pincer, {(5, 5): {3, 4}}
    )

    pivot_values = list(non_bivalue_pivot.candidates)
    pivot_values[1 * 9 + 1] = frozenset({1, 2, 4})
    non_bivalue_pivot = LogicalState(EMPTY_GRID, tuple(pivot_values))
    first_values = list(non_bivalue_first.candidates)
    first_values[1 * 9 + 5] = frozenset({1, 3, 4})
    non_bivalue_first = LogicalState(EMPTY_GRID, tuple(first_values))
    relation_values = list(invalid_relation.candidates)
    relation_values[5 * 9 + 1] = frozenset({1, 3})
    invalid_relation = LogicalState(EMPTY_GRID, tuple(relation_values))

    assert next(techniques.xy_wings(no_target), None) is None
    assert next(techniques.xy_wings(non_bivalue_pivot), None) is None
    assert next(techniques.xy_wings(non_bivalue_first), None) is None
    assert next(techniques.xy_wings(invalid_relation), None) is None


def test_xy_wing_is_deterministic_preserves_participants_and_rejects_fabrication() -> (
    None
):
    state = xy_wing_state((1, 1), (1, 5), (5, 1), {(5, 5): {3, 4}, (4, 4): {3, 6}})
    step = next(techniques.xy_wings(state))
    updated = apply_step(state, step)

    assert step.eliminations == tuple(sorted(step.eliminations))
    assert updated.candidates[1 * 9 + 1] == frozenset({1, 2})
    assert updated.candidates[1 * 9 + 5] == frozenset({1, 3})
    assert updated.candidates[5 * 9 + 1] == frozenset({2, 3})
    with pytest.raises(ValueError):
        apply_step(state, expected_step(Technique.XY_WING, [((5, 5), 4)]))


def test_xy_wing_pivot_order_selects_the_first_available_pattern() -> None:
    state = state_with(
        {
            **{
                (row, column): DIGITS - {3, 6}
                for row in range(9)
                for column in range(9)
            },
            (1, 1): {1, 2},
            (1, 5): {1, 3},
            (5, 1): {2, 3},
            (5, 5): {3, 4},
            (6, 6): {4, 5},
            (6, 8): {4, 6},
            (8, 6): {5, 6},
            (8, 8): {6, 7},
        }
    )

    assert next(techniques.xy_wings(state), None) == expected_step(
        Technique.XY_WING, [((5, 5), 3)]
    )


def swordfish_state(
    digit: int,
    sources: dict[int, tuple[int, ...]],
    targets: Iterable[Cell],
    *,
    column_based: bool = False,
) -> LogicalState:
    overrides: dict[Cell, Iterable[int]] = {
        (row, column): DIGITS - {digit} for row in range(9) for column in range(9)
    }
    for line, positions in sources.items():
        for position in positions:
            cell = (position, line) if column_based else (line, position)
            overrides[cell] = DIGITS
    for cell in targets:
        overrides[cell] = DIGITS
    return state_with(overrides)


def test_row_swordfish_supports_mixed_two_and_three_position_sources() -> None:
    sources = {0: (1, 4), 3: (1, 7), 6: (1, 4, 7)}
    targets = ((4, 7), (1, 1), (2, 4))
    state = swordfish_state(5, sources, targets)

    step = next(techniques.swordfish(state))

    assert step == expected_step(Technique.SWORDFISH, ((cell, 5) for cell in targets))
    updated = apply_step(state, step)
    assert all(
        5 in updated.candidates[row * 9 + column]
        for row in sources
        for column in sources[row]
    )


def test_column_swordfish_eliminates_only_outside_source_columns() -> None:
    sources = {0: (2, 6), 3: (2, 7), 8: (2, 6, 7)}
    targets = ((2, 1), (6, 4), (7, 5))
    state = swordfish_state(6, sources, targets, column_based=True)

    assert next(techniques.swordfish(state), None) == expected_step(
        Technique.SWORDFISH, ((cell, 6) for cell in targets)
    )


@pytest.mark.parametrize(
    "sources",
    [
        {0: (1, 4), 3: (1, 7), 6: (1, 4, 7, 8)},
        {0: (1, 4), 3: (1, 7), 6: (1, 4, 8)},
        {0: (1, 4), 3: (1, 4)},
    ],
)
def test_swordfish_rejects_invalid_source_shapes(
    sources: dict[int, tuple[int, ...]],
) -> None:
    state = swordfish_state(5, sources, ((1, 1),))

    assert next(techniques.swordfish(state), None) is None


def test_swordfish_requires_external_elimination_and_is_deterministic() -> None:
    sources = {0: (1, 4), 3: (1, 7), 6: (4, 7)}
    no_targets = swordfish_state(5, sources, ())
    first = swordfish_state(7, {0: (1, 4), 3: (1, 7), 6: (4, 7)}, ((2, 1),))
    second = swordfish_state(2, {1: (2, 5), 4: (2, 8), 7: (5, 8)}, ((0, 2),))
    combined = state_with(
        {
            **{
                (row, column): DIGITS - {2, 7}
                for row in range(9)
                for column in range(9)
            },
            **{
                (row, column): values
                for state in (first, second)
                for row in range(9)
                for column in range(9)
                if (values := state.candidates[row * 9 + column]) != DIGITS - {2, 7}
            },
        }
    )

    assert next(techniques.swordfish(no_targets), None) is None
    assert next(techniques.swordfish(combined), None) == expected_step(
        Technique.SWORDFISH, [((0, 2), 2)]
    )


def test_xy_wing_and_swordfish_restart_at_global_single_priority() -> None:
    xy_state = xy_wing_state((1, 1), (1, 5), (5, 1), {(5, 5): {3, 9}})
    xy_step = next(techniques.xy_wings(xy_state))
    after_xy = apply_step(xy_state, xy_step)
    assert next_step(after_xy) == SolveStep(Technique.NAKED_SINGLE, 5, 5, 9)

    sword_state = swordfish_state(5, {0: (1, 4), 3: (1, 7), 6: (4, 7)}, ((1, 1),))
    with (
        patch.object(techniques, "naked_singles", lambda state: iter(())),
        patch.object(techniques, "hidden_singles", lambda state: iter(())),
        patch.object(techniques, "naked_pairs", lambda state: iter(())),
        patch.object(techniques, "hidden_pairs", lambda state: iter(())),
        patch.object(techniques, "pointing", lambda state: iter(())),
        patch.object(techniques, "box_line_reductions", lambda state: iter(())),
        patch.object(techniques, "naked_triples", lambda state: iter(())),
        patch.object(techniques, "hidden_triples", lambda state: iter(())),
        patch.object(techniques, "x_wings", lambda state: iter(())),
        patch.object(techniques, "xy_wings", lambda state: iter(())),
    ):
        sword_step = next_step(sword_state)
    assert isinstance(sword_step, EliminationStep)
    assert sword_step.technique is Technique.SWORDFISH
    after_sword = apply_step(sword_state, sword_step)
    assert next_step(after_sword).technique is Technique.HIDDEN_SINGLE


@pytest.mark.parametrize("technique", (Technique.XY_WING, Technique.SWORDFISH))
def test_new_techniques_reject_fabricated_eliminations(technique: Technique) -> None:
    with pytest.raises(ValueError):
        apply_step(
            LogicalState.from_grid(EMPTY_GRID),
            expected_step(technique, [((0, 0), 1)]),
        )


def test_mixed_new_elimination_trace_replays_candidate_state() -> None:
    state = xy_wing_state((1, 1), (1, 5), (5, 1), {(5, 5): {3, 9}})
    result = solve_logically(state)
    replay = state
    for step in result.steps:
        assert next_step(replay) == step
        replay = apply_step(replay, step)

    assert replay == result.state


@pytest.mark.parametrize(
    ("text", "expected_status", "expected_new_technique"),
    [
        pytest.param(
            "601080000908502001000000080807905240000000000042708106060000000200103709000070408",
            "SOLVED",
            Technique.XY_WING,
            id="xy-wing-seed-100064",
        ),
        pytest.param(
            "000109503000030070200600809000700908310000057907008000509007001080020000602901000",
            "STUCK",
            Technique.SWORDFISH,
            id="swordfish-seed-100425",
        ),
    ],
)
def test_real_phase_115_stuck_fixtures_progress_with_new_techniques(
    text: str, expected_status: str, expected_new_technique: Technique
) -> None:
    """Fixed target-30 rotational candidates from the Phase 1.15 population."""
    grid = Grid.from_string(text)

    with (
        patch.object(techniques, "xy_wings", lambda state: iter(())),
        patch.object(techniques, "swordfish", lambda state: iter(())),
    ):
        previous = solve_logically(grid)
    current = solve_logically(grid)

    assert previous.status.name == "STUCK"
    assert current.status.name == expected_status
    assert len(current.steps) > len(previous.steps)
    assert any(step.technique is expected_new_technique for step in current.steps)


@pytest.mark.parametrize(
    "text",
    [
        "530070000600195000098000060800060003400803001700020006060000280000419005000080079",
        "509400006000700209000020054650078000800000002000130078780060000903007000100002907",
    ],
)
def test_previously_completed_solves_are_exactly_unchanged(text: str) -> None:
    grid = Grid.from_string(text)

    with (
        patch.object(techniques, "xy_wings", lambda state: iter(())),
        patch.object(techniques, "swordfish", lambda state: iter(())),
    ):
        previous = solve_logically(grid)
    current = solve_logically(grid)

    assert previous.status.name == "SOLVED"
    assert current == previous
