"""Exceptions raised when Sudoku domain inputs are malformed."""


class SudokuError(Exception):
    """Base exception for Sudoku Gen domain errors."""


class InvalidGridError(SudokuError, ValueError):
    """A grid has an invalid representation, cell count, or cell value."""
