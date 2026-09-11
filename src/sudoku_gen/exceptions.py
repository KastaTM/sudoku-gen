"""Exceptions raised when Sudoku domain inputs are invalid."""


class SudokuError(Exception):
    """Base exception for Sudoku Gen domain errors."""


class InvalidGridError(SudokuError, ValueError):
    """A grid has a malformed representation or a detected Sudoku contradiction."""
