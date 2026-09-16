"""Replay real mixed-technique puzzles and preserve known Sudoku solutions."""

from itertools import pairwise

import pytest
from hypothesis import given, seed, settings
from hypothesis import strategies as st

from sudoku_gen.candidates import candidates
from sudoku_gen.human_solver import (
    EliminationStep,
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
from sudoku_gen.validation import is_valid_grid

SOLVED_TEXT = (
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)
# Fixed clue subsets of SOLVED_TEXT, discovered with Random(1808). Each reaches
# its named elimination only after its initially available singles are applied.
NAKED_PAIR_TEXT = (
    "504078910600090000100040067800060420020050000000920000901537280000010005040086070"
)
HIDDEN_PAIR_TEXT = (
    "500000910670100040090000000009701000000050001013000050000530000200409000005000000"
)
POINTING_TEXT = (
    "504608002670000040000040067050761003000000091000000000000007200000000000345000000"
)
CLAIMING_TEXT = (
    "500070902600000348098300000809001400400800000703920000900500004207009035305080000"
)
PAIR_CASCADE_TEXT = (
    "000600910600190000100000567000700023420850000000900850001037200007000030005000070"
)
POINTING_CASCADE_TEXT = (
    "034000012602005000008340060859000423000053701000004000000000084007000630040080170"
)


def assert_solution_preserving_replay(
    original: Grid, result: LogicalSolveResult
) -> bool:
    """Replay every state; return whether a placement retained prior reductions."""
    solved = Grid.from_string(SOLVED_TEXT)
    current = LogicalState.from_grid(original)
    preserved_reduction_after_placement = False

    assert result.status is not LogicalSolveStatus.CONTRADICTION
    for step in result.steps:
        assert next_step(current) == step
        previous = current
        current = apply_step(current, step)
        assert is_valid_grid(current.grid)
        if isinstance(step, EliminationStep):
            assert current.grid == previous.grid
            assert current.candidates != previous.candidates
        else:
            assert previous.grid.cells[step.row * 9 + step.column] == 0
            assert current.grid.cells[step.row * 9 + step.column] == step.value

        for index, (before, after) in enumerate(
            zip(previous.candidates, current.candidates, strict=True)
        ):
            row, column = divmod(index, 9)
            allowed = candidates(current.grid, row, column)
            assert after <= before
            assert after <= allowed
            if current.grid.cells[index] == 0:
                assert solved.cells[index] in after
            else:
                assert after == frozenset()
                assert current.grid.cells[index] == solved.cells[index]
            if original.cells[index] != 0:
                assert current.grid.cells[index] == original.cells[index]
            if isinstance(step, SolveStep):
                eliminated = candidates(previous.grid, row, column) - before
                if eliminated & allowed:
                    # These exclusions still need logical history: the new
                    # grid alone would allow the candidates to return.
                    assert eliminated.isdisjoint(after)
                    preserved_reduction_after_placement = True

    assert current == result.state
    assert current.grid == result.grid
    stopped = solve_logically(current)
    assert stopped.steps == ()
    assert stopped.state == result.state
    assert stopped.status is result.status
    return preserved_reduction_after_placement


@pytest.mark.parametrize(
    ("text", "first_elimination"),
    [
        pytest.param(NAKED_PAIR_TEXT, Technique.NAKED_PAIR, id="naked-pair"),
        pytest.param(HIDDEN_PAIR_TEXT, Technique.HIDDEN_PAIR, id="hidden-pair"),
        pytest.param(POINTING_TEXT, Technique.POINTING, id="pointing"),
        pytest.param(CLAIMING_TEXT, Technique.BOX_LINE_REDUCTION, id="claiming"),
    ],
)
def test_real_puzzles_replay_placements_and_eliminations_exactly(
    text: str, first_elimination: Technique
) -> None:
    original = Grid.from_string(text)
    initial = LogicalState.from_grid(original)
    original_hash = hash(original)
    initial_hash = hash(initial)

    result = solve_logically(original)

    assert any(isinstance(step, SolveStep) for step in result.steps)
    eliminations = [step for step in result.steps if isinstance(step, EliminationStep)]
    assert eliminations[0].technique is first_elimination
    assert result.status is LogicalSolveStatus.STUCK
    assert_solution_preserving_replay(original, result)
    assert solve_logically(original) == result
    assert solve_logically(initial) == result
    assert original.to_string() == text
    assert hash(original) == original_hash
    assert initial == LogicalState.from_grid(original)
    assert hash(initial) == initial_hash


@pytest.mark.parametrize(
    ("text", "elimination", "placement"),
    [
        pytest.param(
            PAIR_CASCADE_TEXT,
            Technique.NAKED_PAIR,
            Technique.NAKED_SINGLE,
            id="pair-then-naked-single",
        ),
        pytest.param(
            POINTING_CASCADE_TEXT,
            Technique.POINTING,
            Technique.HIDDEN_SINGLE,
            id="pointing-then-hidden-single",
        ),
    ],
)
def test_real_puzzle_cascades_preserve_eliminations_after_placements(
    text: str, elimination: Technique, placement: Technique
) -> None:
    original = Grid.from_string(text)

    result = solve_logically(original)

    assert any(
        first.technique is elimination and second.technique is placement
        for first, second in pairwise(result.steps)
    )
    assert assert_solution_preserving_replay(original, result)


def test_resuming_after_an_elimination_reproduces_the_remaining_log_and_state() -> None:
    original = Grid.from_string(HIDDEN_PAIR_TEXT)
    result = solve_logically(original)
    current = LogicalState.from_grid(original)

    resume_at = next(
        index + 1
        for index, step in enumerate(result.steps)
        if isinstance(step, EliminationStep)
    )
    for step in result.steps[:resume_at]:
        current = apply_step(current, step)
    assert current.candidates != LogicalState.from_grid(current.grid).candidates

    resumed = solve_logically(current)

    assert resumed.steps == result.steps[resume_at:]
    assert resumed.steps
    assert resumed.state == result.state
    assert resumed.grid == result.grid
    assert resumed.status is result.status


@seed(1808)
@settings(max_examples=25, deadline=None)
@given(kept=st.sets(st.integers(min_value=0, max_value=80), min_size=17, max_size=40))
def test_logical_deductions_preserve_a_known_solution_for_clue_subsets(
    kept: set[int],
) -> None:
    solved = Grid.from_string(SOLVED_TEXT)
    original = Grid(
        tuple(value if index in kept else 0 for index, value in enumerate(solved.cells))
    )

    result = solve_logically(original)

    assert_solution_preserving_replay(original, result)
    assert original.cells == tuple(
        value if index in kept else 0 for index, value in enumerate(solved.cells)
    )
