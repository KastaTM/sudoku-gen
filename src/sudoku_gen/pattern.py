"""Clue-position symmetry and descriptive Sudoku pattern analysis."""

from dataclasses import dataclass
from enum import Enum

from sudoku_gen.models import Grid
from sudoku_gen.validation import box_values, clue_count, column_values, row_values


class Symmetry(Enum):
    """Supported clue-position symmetry constraints."""

    NONE = "none"
    ROTATIONAL_180 = "rotational_180"


@dataclass(frozen=True, slots=True)
class PuzzlePatternReport:
    """Immutable description of clue layout without a subjective quality score."""

    clue_count: int
    symmetry: Symmetry
    row_clue_counts: tuple[int, ...]
    column_clue_counts: tuple[int, ...]
    box_clue_counts: tuple[int, ...]


def is_symmetric(grid: Grid, symmetry: Symmetry) -> bool:
    """Return whether clue positions meet the requested supported symmetry.

    NONE places no constraint and therefore returns True for every Grid. Values
    themselves are ignored: only whether each cell is empty or contains a clue
    participates in the comparison.
    """
    if not isinstance(grid, Grid):
        raise TypeError("grid must be a Grid.")
    if not isinstance(symmetry, Symmetry):
        raise TypeError("symmetry must be a Symmetry.")
    if symmetry is Symmetry.NONE:
        return True
    return all(
        (grid.cells[index] == 0) is (grid.cells[80 - index] == 0) for index in range(41)
    )


def analyze_pattern(grid: Grid) -> PuzzlePatternReport:
    """Describe clue counts and report rotational symmetry when it is present."""
    if not isinstance(grid, Grid):
        raise TypeError("grid must be a Grid.")
    symmetry = (
        Symmetry.ROTATIONAL_180
        if is_symmetric(grid, Symmetry.ROTATIONAL_180)
        else Symmetry.NONE
    )
    return PuzzlePatternReport(
        clue_count=clue_count(grid),
        symmetry=symmetry,
        row_clue_counts=tuple(
            sum(value != 0 for value in row_values(grid, row)) for row in range(9)
        ),
        column_clue_counts=tuple(
            sum(value != 0 for value in column_values(grid, column))
            for column in range(9)
        ),
        box_clue_counts=tuple(
            sum(value != 0 for value in box_values(grid, box_row, box_column))
            for box_row in range(3)
            for box_column in range(3)
        ),
    )
