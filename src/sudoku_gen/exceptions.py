"""Exceptions raised when Sudoku domain inputs are invalid."""


class SudokuError(Exception):
    """Base exception for Sudoku Gen domain errors."""


class InvalidGridError(SudokuError, ValueError):
    """A grid has a malformed representation or a detected Sudoku contradiction."""


class DifficultyGenerationError(SudokuError):
    """Bounded generation could not find a puzzle at the requested difficulty."""


class PuzzleBatchGenerationError(SudokuError):
    """A bounded puzzle batch could not collect all requested unique puzzles."""
