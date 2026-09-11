"""Deterministic, recorded Sudoku placements using only Naked and Hidden Singles.

Priority is Naked Singles in row-major order, then Hidden Singles in rows,
columns, and boxes. Units are visited in increasing index (boxes row-major),
and digits in ascending order within a unit. Candidates are recomputed after
each placement; no search, guessing, or stored solution is used.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from sudoku_gen.candidates import candidates
from sudoku_gen.exceptions import InvalidGridError
from sudoku_gen.models import Grid
from sudoku_gen.validation import (
    box_coordinates,
    cell_value,
    empty_cells,
    is_complete,
    is_valid_grid,
)

type _Cell = tuple[int, int]
type _CandidateMap = dict[_Cell, frozenset[int]]


class Technique(Enum):
    """Logical placement techniques supported by this phase."""

    NAKED_SINGLE = "naked_single"
    HIDDEN_SINGLE = "hidden_single"


@dataclass(frozen=True, slots=True)
class SolveStep:
    """One placement, with zero-based coordinates and a built-in digit 1..9.

    Construction checks types and ranges. Whether the placement is justified
    on a particular grid is checked by apply_step().
    """

    technique: Technique
    row: int
    column: int
    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.technique, Technique):
            raise TypeError("technique must be a Technique.")
        box_coordinates(self.row, self.column)
        if type(self.value) is not int:
            raise TypeError("value must be a built-in integer.")
        if not 1 <= self.value <= 9:
            raise ValueError("value must be between 1 and 9.")


class LogicalSolveStatus(Enum):
    """Why logical solving stopped; STUCK does not establish solvability."""

    SOLVED = "solved"
    STUCK = "stuck"
    CONTRADICTION = "contradiction"


@dataclass(frozen=True, slots=True)
class LogicalSolveResult:
    """Final grid, successful placements in application order, and stop status."""

    grid: Grid
    steps: tuple[SolveStep, ...]
    status: LogicalSolveStatus

    def __post_init__(self) -> None:
        if not isinstance(self.grid, Grid):
            raise TypeError("grid must be a Grid.")
        if not isinstance(self.steps, tuple) or any(
            not isinstance(step, SolveStep) for step in self.steps
        ):
            raise TypeError("steps must be a tuple of SolveStep instances.")
        if not isinstance(self.status, LogicalSolveStatus):
            raise TypeError("status must be a LogicalSolveStatus.")

    @property
    def solved(self) -> bool:
        """Whether logical solving reached a valid completed grid."""
        return self.status is LogicalSolveStatus.SOLVED


def _candidate_map(grid: Grid) -> _CandidateMap:
    """Reject evident contradictions before considering any placement."""
    if not is_valid_grid(grid):
        raise InvalidGridError("Grid contains conflicting Sudoku clues.")
    options = {
        (row, column): candidates(grid, row, column)
        for row, column in empty_cells(grid)
    }
    if any(not values for values in options.values()):
        raise InvalidGridError("An empty cell has no legal candidates.")
    return options


def _naked_singles(options: _CandidateMap) -> Iterator[SolveStep]:
    for (row, column), values in options.items():
        if len(values) == 1:
            yield SolveStep(Technique.NAKED_SINGLE, row, column, next(iter(values)))


def _units() -> Iterator[tuple[_Cell, ...]]:
    """Enumerate cell coordinates in row, column, then box priority order."""
    for row in range(9):
        yield tuple((row, column) for column in range(9))
    for column in range(9):
        yield tuple((row, column) for row in range(9))
    for box_row in range(3):
        for box_column in range(3):
            yield tuple(
                (box_row * 3 + row, box_column * 3 + column)
                for row in range(3)
                for column in range(3)
            )


def _hidden_singles(options: _CandidateMap) -> Iterator[SolveStep]:
    for unit in _units():
        for value in range(1, 10):
            # candidates() already excludes every digit present in the unit,
            # so a digit occurring here must be missing from that unit.
            positions = [
                cell for cell in unit if cell in options and value in options[cell]
            ]
            if len(positions) == 1:
                row, column = positions[0]
                yield SolveStep(Technique.HIDDEN_SINGLE, row, column, value)


def next_step(grid: Grid) -> SolveStep | None:
    """Find the first justified placement, or None if solved or stuck.

    Raise InvalidGridError for Sudoku rule conflicts or an empty cell with no
    candidates, even if another cell has a single. This is a local contradiction
    check, not a complete test of satisfiability.
    """
    options = _candidate_map(grid)
    naked = next(_naked_singles(options), None)
    if naked is not None:
        return naked
    return next(_hidden_singles(options), None)


def apply_step(grid: Grid, step: SolveStep) -> Grid:
    """Apply a locally legal placement justified by its declared technique.

    Any justified step is allowed, regardless of detection priority. A Hidden
    Single must be unique in at least one containing unit; it may also be naked.
    Raise ValueError for an occupied target, illegal digit, or unjustified
    technique. Invalid starting grids raise InvalidGridError as in next_step().
    SolveStep construction validates coordinate and digit types and ranges.
    """
    if not isinstance(step, SolveStep):
        raise TypeError("step must be a SolveStep.")
    target = cell_value(grid, step.row, step.column)
    options = _candidate_map(grid)
    if target != 0:
        raise ValueError("The target cell must be empty.")
    values = options[step.row, step.column]
    if step.value not in values:
        raise ValueError("The value is not a legal candidate for the target cell.")
    if step.technique is Technique.NAKED_SINGLE:
        justified = len(values) == 1
    else:
        justified = step in _hidden_singles(options)
    if not justified:
        raise ValueError("The declared technique does not justify this placement.")
    index = step.row * 9 + step.column
    return Grid(grid.cells[:index] + (step.value,) + grid.cells[index + 1 :])


def solve_logically(grid: Grid) -> LogicalSolveResult:
    """Apply singles until solved, stuck, or an evident contradiction is found.

    Conflicting clues and zero-candidate empty cells return CONTRADICTION with
    the current grid and all successful steps. SOLVED means complete and valid.
    STUCK means neither supported technique can progress; an unsatisfiable grid
    without an evident contradiction can also be STUCK. No search is performed.
    """
    current = grid
    steps: list[SolveStep] = []
    while True:
        try:
            step = next_step(current)
        except InvalidGridError:
            return LogicalSolveResult(
                current, tuple(steps), LogicalSolveStatus.CONTRADICTION
            )
        if step is None:
            status = (
                LogicalSolveStatus.SOLVED
                if is_complete(current)
                else LogicalSolveStatus.STUCK
            )
            return LogicalSolveResult(current, tuple(steps), status)
        current = apply_step(current, step)
        steps.append(step)
