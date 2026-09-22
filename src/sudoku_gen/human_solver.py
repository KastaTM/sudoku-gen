"""Deterministic logical Sudoku solving with persistent candidate eliminations.

Priority: Naked Single, Hidden Single, Naked Pair, Hidden Pair, Pointing,
Box-Line Reduction, Naked Triple, Hidden Triple, X-Wing, XY-Wing, Swordfish.
Every step restarts this priority. No guessing or search.
"""

from collections.abc import Iterator
from typing import overload

from sudoku_gen import _logical_techniques as techniques
from sudoku_gen._logical_models import CandidateElimination as CandidateElimination
from sudoku_gen._logical_models import EliminationStep as EliminationStep
from sudoku_gen._logical_models import LogicalSolveResult as LogicalSolveResult
from sudoku_gen._logical_models import LogicalSolveStatus as LogicalSolveStatus
from sudoku_gen._logical_models import LogicalState as LogicalState
from sudoku_gen._logical_models import LogicalStep as LogicalStep
from sudoku_gen._logical_models import PlacementStep as PlacementStep
from sudoku_gen._logical_models import SolveStep as SolveStep
from sudoku_gen._logical_models import Technique as Technique
from sudoku_gen.candidates import candidates
from sudoku_gen.exceptions import InvalidGridError
from sudoku_gen.models import Grid
from sudoku_gen.validation import cell_value, is_complete, is_valid_grid


def _as_state(grid: Grid | LogicalState) -> LogicalState:
    if isinstance(grid, LogicalState):
        return grid
    return LogicalState.from_grid(grid)


def _check_consistency(state: LogicalState) -> None:
    """Detect local contradictions before considering any logical move."""
    if not is_valid_grid(state.grid):
        raise InvalidGridError("Grid contains conflicting Sudoku clues.")
    if any(
        value == 0 and not options
        for value, options in zip(state.grid.cells, state.candidates, strict=True)
    ):
        raise InvalidGridError("An empty cell has no legal logical candidates.")


def _steps_for(state: LogicalState, technique: Technique) -> Iterator[LogicalStep]:
    """Dispatch one technique without imposing priority on explicit replay."""
    match technique:
        case Technique.NAKED_SINGLE:
            yield from techniques.naked_singles(state)
        case Technique.HIDDEN_SINGLE:
            yield from techniques.hidden_singles(state)
        case Technique.NAKED_PAIR:
            yield from techniques.naked_pairs(state)
        case Technique.HIDDEN_PAIR:
            yield from techniques.hidden_pairs(state)
        case Technique.POINTING:
            yield from techniques.pointing(state)
        case Technique.BOX_LINE_REDUCTION:
            yield from techniques.box_line_reductions(state)
        case Technique.NAKED_TRIPLE:
            yield from techniques.naked_triples(state)
        case Technique.HIDDEN_TRIPLE:
            yield from techniques.hidden_triples(state)
        case Technique.X_WING:
            yield from techniques.x_wings(state)
        case Technique.XY_WING:
            yield from techniques.xy_wings(state)
        case Technique.SWORDFISH:
            yield from techniques.swordfish(state)


def next_step(grid: Grid | LogicalState) -> LogicalStep | None:
    """Return the first justified move, or None if solved or stuck.

    A Grid starts with fresh rule-based candidates. Pass LogicalState to retain
    eliminations. Raise InvalidGridError for conflicts or zero-candidate empty
    cells, even if another move exists. This does not test full satisfiability.

    Singles retain Phase 1.7 order. Pairs scan rows, columns, then boxes, each
    by ascending index and digit pair. Pointing scans boxes then digits, testing
    rows before columns. Box-Line Reduction scans rows then columns and digits.
    Triples visit rows, columns, then boxes; Naked Triples scan cell combinations
    and Hidden Triples digit combinations in ascending order. X-Wing scans
    row-based then column-based patterns, digits ascending and source lines
    ascending. XY-Wing scans pivots and pincers row-major. Swordfish scans
    row-based then column-based, digits and source triples ascending. All
    eliminations within a step are sorted by row, column, then digit.
    """
    state = _as_state(grid)
    _check_consistency(state)
    for technique in Technique:
        step = next(_steps_for(state, technique), None)
        if step is not None:
            return step
    return None


@overload
def apply_step(grid: Grid, step: SolveStep) -> Grid: ...


@overload
def apply_step(grid: LogicalState, step: LogicalStep) -> LogicalState: ...


def apply_step(grid: Grid | LogicalState, step: LogicalStep) -> Grid | LogicalState:
    """Apply a complete, justified deduction, regardless of detection priority.

    Grid + placement retains the Phase 1.7 Grid return type. Eliminations require
    LogicalState; supplying a Grid raises TypeError rather than losing candidate
    state. Invalid moves raise ValueError; contradictory starts InvalidGridError.

    Placements intersect old logical candidates with new grid-based candidates,
    preserving earlier eliminations. Eliminations change only candidate sets.
    A justified move may reveal a contradiction: retain its resulting state and
    let the next check (or solve_logically) report it, without losing the log.
    """
    if not isinstance(step, (SolveStep, EliminationStep)):
        raise TypeError("step must be a SolveStep or EliminationStep.")
    if isinstance(grid, Grid) and isinstance(step, EliminationStep):
        raise TypeError("Elimination steps require LogicalState.from_grid(grid).")
    state = _as_state(grid)
    _check_consistency(state)
    if isinstance(step, SolveStep):
        if cell_value(state.grid, step.row, step.column) != 0:
            raise ValueError("The target cell must be empty.")
        if step.value not in state.candidates[step.row * 9 + step.column]:
            raise ValueError("The value is not a legal logical candidate.")
    else:
        for removal in step.eliminations:
            if removal.value not in state.candidates[removal.row * 9 + removal.column]:
                raise ValueError("An eliminated candidate must exist in an empty cell.")
    if step not in _steps_for(state, step.technique):
        raise ValueError("The declared technique does not justify this complete step.")

    if isinstance(step, SolveStep):
        index = step.row * 9 + step.column
        updated = Grid(
            state.grid.cells[:index] + (step.value,) + state.grid.cells[index + 1 :]
        )
        options = tuple(
            old & candidates(updated, *divmod(i, 9))
            for i, old in enumerate(state.candidates)
        )
        result = LogicalState(updated, options)
    else:
        reduced = list(state.candidates)
        for removal in step.eliminations:
            index = removal.row * 9 + removal.column
            reduced[index] = reduced[index] - {removal.value}
        result = LogicalState(state.grid, tuple(reduced))
    return result.grid if isinstance(grid, Grid) else result


def solve_logically(grid: Grid | LogicalState) -> LogicalSolveResult:
    """Apply supported logic until solved, stuck, or locally contradictory.

    Grid is the usual entry point; LogicalState also allows resuming a reduced
    state. The final state and mixed log support exact replay. A STUCK result
    does not establish mathematical solvability. No search is performed.
    """
    state = _as_state(grid)
    steps: list[LogicalStep] = []
    while True:
        try:
            step = next_step(state)
        except InvalidGridError:
            status = LogicalSolveStatus.CONTRADICTION
            break
        if step is None:
            status = (
                LogicalSolveStatus.SOLVED
                if is_complete(state.grid)
                else LogicalSolveStatus.STUCK
            )
            break
        state = apply_step(state, step)
        steps.append(step)
    return LogicalSolveResult(state.grid, tuple(steps), status, state=state)
