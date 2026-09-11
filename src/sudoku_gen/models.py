"""Immutable Sudoku domain objects and their canonical text representation."""

from dataclasses import dataclass
from typing import Self

from sudoku_gen.exceptions import InvalidGridError

_CELL_COUNT = 81
_DIGITS = "0123456789"


@dataclass(frozen=True, slots=True)
class Grid:
    """Exactly 81 integer cells in row-major order; zero denotes an empty cell.

    The constructor requires a tuple to keep the stored representation immutable.
    Only built-in integers are accepted, including when parsing ASCII digits.
    Row, column, and box constraints are outside this representation's scope.
    """

    cells: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.cells, tuple):
            raise InvalidGridError("Grid cells must be a tuple of 81 integers.")
        if len(self.cells) != _CELL_COUNT:
            raise InvalidGridError(
                f"Grid must contain exactly {_CELL_COUNT} cells; got {len(self.cells)}."
            )
        for index, cell in enumerate(self.cells):
            # bool is an int subclass, but is not a Sudoku cell value.
            if type(cell) is not int or not 0 <= cell <= 9:
                raise InvalidGridError(
                    f"Cell at index {index} must be an integer from 0 through 9; "
                    f"got {cell!r}."
                )

    @classmethod
    def from_string(cls, text: str) -> Self:
        """Parse exactly 81 ASCII digits, without separators or whitespace."""
        if not isinstance(text, str):
            raise InvalidGridError("Grid text must be a string of 81 ASCII digits.")
        if len(text) != _CELL_COUNT:
            raise InvalidGridError(
                f"Grid text must contain exactly {_CELL_COUNT} characters; "
                f"got {len(text)}."
            )
        for index, character in enumerate(text):
            if character not in _DIGITS:
                raise InvalidGridError(
                    f"Character at index {index} must be an ASCII digit (0-9); "
                    f"got {character!r}."
                )
        return cls(tuple(int(character) for character in text))

    def to_string(self) -> str:
        """Return the canonical 81 ASCII digits in row-major order."""
        return "".join(str(cell) for cell in self.cells)


@dataclass(frozen=True, slots=True)
class SudokuPuzzle:
    """A puzzle grid and optional associated solution with matching clues.

    The solution remains optional for callers that only have a puzzle grid.
    This model checks types and clue agreement, not Sudoku rules or uniqueness.
    Generation supplies a complete solution and guarantees unique solvability.
    """

    grid: Grid
    solution: Grid | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.grid, Grid):
            raise TypeError("SudokuPuzzle grid must be a Grid.")
        if self.solution is not None:
            if not isinstance(self.solution, Grid):
                raise TypeError("SudokuPuzzle solution must be a Grid or None.")
            for index, (clue, answer) in enumerate(
                zip(self.grid.cells, self.solution.cells, strict=True)
            ):
                if clue != 0 and clue != answer:
                    raise ValueError(
                        f"Puzzle clue at index {index} does not match its solution."
                    )
