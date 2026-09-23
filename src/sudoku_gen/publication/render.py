"""Backend-neutral Sudoku drawing primitives and deterministic SVG rendering."""

from dataclasses import dataclass
from html import escape
from math import isfinite

from sudoku_gen.models import Grid
from sudoku_gen.publication.geometry import Point, Rect, layout_sudoku


def _positive_number(value: float | int, name: str) -> float:
    if type(value) not in (int, float):
        raise TypeError(f"{name} must be a built-in finite number.")
    result = float(value)
    if result <= 0 or not isfinite(result):
        raise ValueError(f"{name} must be finite and greater than zero.")
    return result


@dataclass(frozen=True, slots=True)
class Line:
    """A black vector line with a backend-neutral major/minor classification."""

    start: Point
    end: Point
    stroke_width: float
    is_major: bool

    def __post_init__(self) -> None:
        if not isinstance(self.start, Point):
            raise TypeError("start must be a Point.")
        if not isinstance(self.end, Point):
            raise TypeError("end must be a Point.")
        object.__setattr__(
            self, "stroke_width", _positive_number(self.stroke_width, "stroke_width")
        )
        if type(self.is_major) is not bool:
            raise TypeError("is_major must be a bool.")


@dataclass(frozen=True, slots=True)
class Text:
    """Centered vector text; backends choose their own baseline implementation."""

    content: str
    position: Point
    font_size: float
    horizontal_alignment: str = "center"
    vertical_alignment: str = "center"

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise TypeError("content must be a string.")
        if not isinstance(self.position, Point):
            raise TypeError("position must be a Point.")
        object.__setattr__(
            self, "font_size", _positive_number(self.font_size, "font_size")
        )
        if self.horizontal_alignment != "center":
            raise ValueError("horizontal_alignment must be 'center'.")
        if self.vertical_alignment != "center":
            raise ValueError("vertical_alignment must be 'center'.")


type VectorPrimitive = Line | Text


@dataclass(frozen=True, slots=True)
class VectorDrawing:
    """An ordered collection of backend-neutral vector primitives in one bounds rect."""

    bounds: Rect
    primitives: tuple[VectorPrimitive, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.bounds, Rect):
            raise TypeError("bounds must be a Rect.")
        if self.bounds.width <= 0 or self.bounds.height <= 0:
            raise ValueError("bounds must have positive width and height.")
        if not isinstance(self.primitives, tuple):
            raise TypeError("primitives must be a tuple of vector primitives.")
        if not all(
            isinstance(primitive, (Line, Text)) for primitive in self.primitives
        ):
            raise TypeError("primitives must contain only Line or Text instances.")


@dataclass(frozen=True, slots=True)
class SudokuRenderStyle:
    """Cell-relative black-and-white line and digit sizing for one Sudoku grid.

    Every value is a ratio of the calculated cell size, so all visual proportions
    scale together at every physical rendering size.
    """

    minor_line_width_ratio: float = 0.025
    major_line_width_ratio: float = 0.06
    digit_font_size_ratio: float = 0.6

    def __post_init__(self) -> None:
        minor = _positive_number(self.minor_line_width_ratio, "minor_line_width_ratio")
        major = _positive_number(self.major_line_width_ratio, "major_line_width_ratio")
        digit = _positive_number(self.digit_font_size_ratio, "digit_font_size_ratio")
        if major <= minor:
            raise ValueError(
                "major_line_width_ratio must exceed minor_line_width_ratio."
            )
        object.__setattr__(self, "minor_line_width_ratio", minor)
        object.__setattr__(self, "major_line_width_ratio", major)
        object.__setattr__(self, "digit_font_size_ratio", digit)


_DEFAULT_SUDOKU_RENDER_STYLE = SudokuRenderStyle()


def render_sudoku(
    grid: Grid,
    rect: Rect,
    *,
    style: SudokuRenderStyle = _DEFAULT_SUDOKU_RENDER_STYLE,
) -> VectorDrawing:
    """Render a Grid into ordered lines followed by centered non-zero digit text."""
    if not isinstance(grid, Grid):
        raise TypeError("grid must be a Grid.")
    if not isinstance(rect, Rect):
        raise TypeError("rect must be a Rect.")
    if not isinstance(style, SudokuRenderStyle):
        raise TypeError("style must be a SudokuRenderStyle.")

    geometry = layout_sudoku(rect)
    primitives: list[VectorPrimitive] = []
    for division, x in enumerate(geometry.vertical_line_positions):
        is_major = geometry.is_major_division(division)
        primitives.append(
            Line(
                Point(x, geometry.outer_square.top),
                Point(x, geometry.outer_square.bottom),
                (
                    geometry.cell_size * style.major_line_width_ratio
                    if is_major
                    else geometry.cell_size * style.minor_line_width_ratio
                ),
                is_major,
            )
        )
    for division, y in enumerate(geometry.horizontal_line_positions):
        is_major = geometry.is_major_division(division)
        primitives.append(
            Line(
                Point(geometry.outer_square.left, y),
                Point(geometry.outer_square.right, y),
                (
                    geometry.cell_size * style.major_line_width_ratio
                    if is_major
                    else geometry.cell_size * style.minor_line_width_ratio
                ),
                is_major,
            )
        )
    font_size = geometry.cell_size * style.digit_font_size_ratio
    for index, value in enumerate(grid.cells):
        if value != 0:
            row, column = divmod(index, 9)
            primitives.append(
                Text(str(value), geometry.cell_center(row, column), font_size)
            )
    return VectorDrawing(rect, tuple(primitives))


def _format_number(value: float) -> str:
    """Format finite coordinates consistently without binary floating-point noise."""
    if value == 0:
        return "0"
    return format(value, ".12g")


def render_svg(drawing: VectorDrawing) -> str:
    """Translate a backend-neutral drawing to deterministic, self-contained SVG."""
    if not isinstance(drawing, VectorDrawing):
        raise TypeError("drawing must be a VectorDrawing.")
    bounds = drawing.bounds
    width = _format_number(bounds.width)
    height = _format_number(bounds.height)
    view_box = " ".join(
        _format_number(value)
        for value in (bounds.x, bounds.y, bounds.width, bounds.height)
    )
    elements = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}pt" '
            f'height="{height}pt" viewBox="{view_box}">'
        ),
    ]
    for primitive in drawing.primitives:
        if isinstance(primitive, Line):
            elements.append(
                "<line "
                f'x1="{_format_number(primitive.start.x)}" '
                f'y1="{_format_number(primitive.start.y)}" '
                f'x2="{_format_number(primitive.end.x)}" '
                f'y2="{_format_number(primitive.end.y)}" '
                'stroke="black" '
                f'stroke-width="{_format_number(primitive.stroke_width)}"/>'
            )
        else:
            elements.append(
                "<text "
                f'x="{_format_number(primitive.position.x)}" '
                f'y="{_format_number(primitive.position.y)}" '
                'font-family="sans-serif" '
                f'font-size="{_format_number(primitive.font_size)}" '
                'text-anchor="middle" dominant-baseline="middle">'
                f"{escape(primitive.content)}</text>"
            )
    elements.append("</svg>")
    return "\n".join(elements) + "\n"
