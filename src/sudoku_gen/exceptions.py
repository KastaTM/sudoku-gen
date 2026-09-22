"""Exceptions raised when Sudoku domain inputs are invalid."""


class SudokuError(Exception):
    """Base exception for Sudoku Gen domain errors."""


class InvalidGridError(SudokuError, ValueError):
    """A grid has a malformed representation or a detected Sudoku contradiction."""


class DifficultyGenerationError(SudokuError):
    """Bounded generation could not find a puzzle at the requested difficulty."""


class PuzzleBatchGenerationError(SudokuError):
    """A bounded puzzle batch could not collect all requested unique puzzles."""


class PublicationError(SudokuError):
    """Publication content cannot satisfy an editorial invariant."""


class DuplicatePublicationPuzzleError(PublicationError):
    """Two editorial entries share a forbidden publication identity."""

    def __init__(
        self,
        first_section: int,
        first_position: int,
        duplicate_section: int,
        duplicate_position: int,
    ) -> None:
        self.first_section = first_section
        self.first_position = first_position
        self.duplicate_section = duplicate_section
        self.duplicate_position = duplicate_position
        super().__init__(
            "Duplicate publication puzzle identity between "
            f"section {first_section}, position {first_position} and "
            f"section {duplicate_section}, position {duplicate_position}."
        )
