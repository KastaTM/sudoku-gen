"""Physical points-based geometry, independent of any rendering backend.

Coordinates use a top-left origin with x increasing rightward and y increasing
downward. This matches SVG directly and can be translated by a later PDF backend.
"""

from dataclasses import dataclass
from math import isclose, isfinite
from typing import Self

POINTS_PER_INCH = 72.0
MILLIMETRES_PER_INCH = 25.4


def _finite_number(value: float | int, name: str) -> float:
    if type(value) not in (int, float):
        raise TypeError(f"{name} must be a built-in finite number.")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


def _non_negative_number(value: float | int, name: str) -> float:
    result = _finite_number(value, name)
    if result < 0:
        raise ValueError(f"{name} must not be negative.")
    return result


def _positive_number(value: float | int, name: str) -> float:
    result = _finite_number(value, name)
    if result <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return result


def inches_to_points(inches: float | int) -> float:
    """Convert a finite physical inch measurement to PostScript points."""
    return _finite_number(inches, "inches") * POINTS_PER_INCH


def millimetres_to_points(millimetres: float | int) -> float:
    """Convert a finite physical millimetre measurement to PostScript points."""
    return (
        _finite_number(millimetres, "millimetres")
        * POINTS_PER_INCH
        / MILLIMETRES_PER_INCH
    )


@dataclass(frozen=True, slots=True)
class Point:
    """One finite physical coordinate in points."""

    x: float
    y: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _finite_number(self.x, "x"))
        object.__setattr__(self, "y", _finite_number(self.y, "y"))


@dataclass(frozen=True, slots=True)
class Size:
    """A non-negative physical extent in points."""

    width: float
    height: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "width", _non_negative_number(self.width, "width"))
        object.__setattr__(self, "height", _non_negative_number(self.height, "height"))


@dataclass(frozen=True, slots=True)
class Rect:
    """A points-based rectangle; zero-sized generic rectangles are permitted."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _finite_number(self.x, "x"))
        object.__setattr__(self, "y", _finite_number(self.y, "y"))
        object.__setattr__(self, "width", _non_negative_number(self.width, "width"))
        object.__setattr__(self, "height", _non_negative_number(self.height, "height"))

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def center(self) -> Point:
        return Point(self.x + self.width / 2, self.y + self.height / 2)


@dataclass(frozen=True, slots=True)
class PhysicalPageSize:
    """A strictly positive physical page size in PostScript points."""

    width: float
    height: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "width", _positive_number(self.width, "width"))
        object.__setattr__(self, "height", _positive_number(self.height, "height"))

    @classmethod
    def from_inches(cls, width: float | int, height: float | int) -> Self:
        return cls(inches_to_points(width), inches_to_points(height))

    @classmethod
    def from_millimetres(cls, width: float | int, height: float | int) -> Self:
        return cls(millimetres_to_points(width), millimetres_to_points(height))

    @classmethod
    def six_by_nine_inches(cls) -> Self:
        return cls.from_inches(6, 9)

    @classmethod
    def us_letter(cls) -> Self:
        return cls.from_inches(8.5, 11)

    @classmethod
    def a4(cls) -> Self:
        return cls.from_millimetres(210, 297)

    @property
    def size(self) -> Size:
        return Size(self.width, self.height)


def _validate_grid_coordinate(value: int, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be a built-in integer.")
    if not 0 <= value <= 8:
        raise ValueError(f"{name} must be between 0 and 8.")


@dataclass(frozen=True, slots=True)
class SudokuGridGeometry:
    """Derived square geometry for a 9-by-9 Sudoku grid."""

    outer_square: Rect
    cell_size: float

    def __post_init__(self) -> None:
        if not isinstance(self.outer_square, Rect):
            raise TypeError("outer_square must be a Rect.")
        if self.outer_square.width <= 0 or self.outer_square.height <= 0:
            raise ValueError("outer_square must have positive width and height.")
        if not isclose(
            self.outer_square.width,
            self.outer_square.height,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("outer_square must be square.")
        cell_size = _positive_number(self.cell_size, "cell_size")
        if not isclose(
            cell_size * 9,
            self.outer_square.width,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("cell_size must divide the outer square into nine cells.")
        object.__setattr__(self, "cell_size", cell_size)

    @property
    def vertical_line_positions(self) -> tuple[float, ...]:
        return tuple(
            self.outer_square.left + division * self.cell_size for division in range(10)
        )

    @property
    def horizontal_line_positions(self) -> tuple[float, ...]:
        return tuple(
            self.outer_square.top + division * self.cell_size for division in range(10)
        )

    def cell_rect(self, row: int, column: int) -> Rect:
        """Return the bounds of the zero-based row and column cell."""
        _validate_grid_coordinate(row, "row")
        _validate_grid_coordinate(column, "column")
        return Rect(
            self.outer_square.left + column * self.cell_size,
            self.outer_square.top + row * self.cell_size,
            self.cell_size,
            self.cell_size,
        )

    def cell_center(self, row: int, column: int) -> Point:
        """Return the center of the zero-based row and column cell."""
        return self.cell_rect(row, column).center

    @staticmethod
    def is_major_division(division: int) -> bool:
        if type(division) is not int:
            raise TypeError("division must be a built-in integer.")
        if not 0 <= division <= 9:
            raise ValueError("division must be between 0 and 9.")
        return division % 3 == 0


def layout_sudoku(rect: Rect) -> SudokuGridGeometry:
    """Fit the largest centered 9-by-9 Sudoku square inside a positive rectangle."""
    if not isinstance(rect, Rect):
        raise TypeError("rect must be a Rect.")
    if rect.width <= 0 or rect.height <= 0:
        raise ValueError("A Sudoku rendering target must have positive dimensions.")
    side = min(rect.width, rect.height)
    outer_square = Rect(
        rect.left + (rect.width - side) / 2,
        rect.top + (rect.height - side) / 2,
        side,
        side,
    )
    return SudokuGridGeometry(outer_square, side / 9)
