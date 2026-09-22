"""Immutable logical-solver records, re-exported by human_solver."""

from dataclasses import dataclass
from enum import Enum
from typing import Self

from sudoku_gen.candidates import candidates as base_candidates
from sudoku_gen.models import Grid
from sudoku_gen.validation import box_coordinates


class Technique(Enum):
    """Supported logical placement and candidate-elimination techniques."""

    NAKED_SINGLE = "naked_single"
    HIDDEN_SINGLE = "hidden_single"
    NAKED_PAIR = "naked_pair"
    HIDDEN_PAIR = "hidden_pair"
    POINTING = "pointing"
    BOX_LINE_REDUCTION = "box_line_reduction"
    NAKED_TRIPLE = "naked_triple"
    HIDDEN_TRIPLE = "hidden_triple"
    X_WING = "x_wing"


def _check_digit(value: int) -> None:
    if type(value) is not int:
        raise TypeError("value must be a built-in integer.")
    if not 1 <= value <= 9:
        raise ValueError("value must be between 1 and 9.")


@dataclass(frozen=True, slots=True)
class SolveStep:
    """A single placement; the Phase 1.7 constructor remains supported."""

    technique: Technique
    row: int
    column: int
    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.technique, Technique):
            raise TypeError("technique must be a Technique.")
        if self.technique not in (Technique.NAKED_SINGLE, Technique.HIDDEN_SINGLE):
            raise ValueError("A placement must use a single technique.")
        box_coordinates(self.row, self.column)
        _check_digit(self.value)


PlacementStep = SolveStep


@dataclass(frozen=True, slots=True, order=True)
class CandidateElimination:
    """Remove one digit from one empty cell's logical candidates."""

    row: int
    column: int
    value: int

    def __post_init__(self) -> None:
        box_coordinates(self.row, self.column)
        _check_digit(self.value)


@dataclass(frozen=True, slots=True)
class EliminationStep:
    """One complete deduction, with removals sorted by row, column, then digit."""

    technique: Technique
    eliminations: tuple[CandidateElimination, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.technique, Technique):
            raise TypeError("technique must be a Technique.")
        if self.technique in (Technique.NAKED_SINGLE, Technique.HIDDEN_SINGLE):
            raise ValueError("An elimination must use an elimination technique.")
        if not isinstance(self.eliminations, tuple) or any(
            not isinstance(item, CandidateElimination) for item in self.eliminations
        ):
            raise TypeError("eliminations must be a tuple of CandidateElimination.")
        if not self.eliminations:
            raise ValueError("An elimination step must remove at least one candidate.")
        if len(set(self.eliminations)) != len(self.eliminations):
            raise ValueError("An elimination step cannot contain duplicate removals.")
        object.__setattr__(self, "eliminations", tuple(sorted(self.eliminations)))


type LogicalStep = SolveStep | EliminationStep


@dataclass(frozen=True, slots=True)
class LogicalState:
    """Grid and 81 row-major candidate sets, including prior logical reductions.

    Filled cells have empty sets; empty cells contain subsets of candidates()
    allowed by the grid. Empty sets on empty cells represent contradictions.
    Construction checks this local consistency, not the history of deductions
    used to obtain a supplied subset. Use from_grid() to start from a puzzle.
    """

    grid: Grid
    candidates: tuple[frozenset[int], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.grid, Grid):
            raise TypeError("grid must be a Grid.")
        if not isinstance(self.candidates, tuple):
            raise TypeError("candidates must be an immutable tuple.")
        if len(self.candidates) != 81:
            raise ValueError("Logical state must contain exactly 81 candidate sets.")
        for index, values in enumerate(self.candidates):
            if not isinstance(values, frozenset):
                raise TypeError("Each candidate set must be a frozenset.")
            for value in values:
                _check_digit(value)
            if self.grid.cells[index] != 0:
                if values:
                    raise ValueError("Filled cells must have empty candidate sets.")
            elif not values <= base_candidates(self.grid, *divmod(index, 9)):
                raise ValueError("Logical candidates must be allowed by the grid.")

    @classmethod
    def from_grid(cls, grid: Grid) -> Self:
        """Initialize candidates from Sudoku rules, without logical eliminations."""
        if not isinstance(grid, Grid):
            raise TypeError("grid must be a Grid.")
        return cls(
            grid, tuple(base_candidates(grid, *divmod(index, 9)) for index in range(81))
        )


class LogicalSolveStatus(Enum):
    """Why solving stopped; STUCK does not establish solvability or uniqueness."""

    SOLVED = "solved"
    STUCK = "stuck"
    CONTRADICTION = "contradiction"


@dataclass(frozen=True, init=False)
class LogicalSolveResult:
    """Final logical state, immutable ordered log, and stop status.

    The original (grid, steps, status) constructor remains available. Supplying
    state also preserves candidate reductions; grid is derived from that state.
    """

    state: LogicalState
    steps: tuple[LogicalStep, ...]
    status: LogicalSolveStatus

    def __init__(
        self,
        grid: Grid,
        steps: tuple[LogicalStep, ...],
        status: LogicalSolveStatus,
        *,
        state: LogicalState | None = None,
    ) -> None:
        if not isinstance(grid, Grid):
            raise TypeError("grid must be a Grid.")
        if not isinstance(steps, tuple) or any(
            not isinstance(step, (SolveStep, EliminationStep)) for step in steps
        ):
            raise TypeError("steps must be a tuple of logical steps.")
        if not isinstance(status, LogicalSolveStatus):
            raise TypeError("status must be a LogicalSolveStatus.")
        if state is None:
            if any(isinstance(step, EliminationStep) for step in steps):
                raise ValueError("A result with eliminations requires its final state.")
            state = LogicalState.from_grid(grid)
        elif not isinstance(state, LogicalState):
            raise TypeError("state must be a LogicalState.")
        elif state.grid != grid:
            raise ValueError("The result grid must agree with its logical state.")
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "steps", steps)
        object.__setattr__(self, "status", status)

    @property
    def grid(self) -> Grid:
        """Final grid, including placements but not candidate eliminations."""
        return self.state.grid

    @property
    def solved(self) -> bool:
        """Whether the solver reached a valid completed grid."""
        return self.status is LogicalSolveStatus.SOLVED
