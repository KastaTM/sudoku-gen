"""Geometry and single-grid vector/SVG rendering tests."""

from dataclasses import FrozenInstanceError
from math import isclose, nan
from xml.etree import ElementTree

import pytest

from sudoku_gen.models import Grid
from sudoku_gen.publication import (
    Line,
    PhysicalPageSize,
    Point,
    Rect,
    Size,
    SudokuRenderStyle,
    Text,
    VectorDrawing,
    inches_to_points,
    layout_sudoku,
    millimetres_to_points,
    render_sudoku,
    render_svg,
)

SOLUTION = Grid.from_string(
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)
SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"


def drawing_primitives(
    drawing: VectorDrawing, kind: type[Line] | type[Text]
) -> tuple[Line | Text, ...]:
    return tuple(
        primitive for primitive in drawing.primitives if isinstance(primitive, kind)
    )


def test_physical_unit_conversions_and_standard_page_sizes() -> None:
    assert inches_to_points(1) == 72.0
    assert millimetres_to_points(25.4) == 72.0
    assert PhysicalPageSize.six_by_nine_inches() == PhysicalPageSize(432, 648)
    assert PhysicalPageSize.us_letter() == PhysicalPageSize(612, 792)
    assert PhysicalPageSize.a4() == PhysicalPageSize.from_millimetres(210, 297)


@pytest.mark.parametrize(
    ("constructor", "args"),
    [
        (Point, (True, 0)),
        (Size, (-1, 1)),
        (Rect, (0, 0, -1, 1)),
        (Rect, (0, 0, nan, 1)),
        (PhysicalPageSize, (0, 1)),
        (PhysicalPageSize, (1, False)),
    ],
)
def test_geometry_rejects_invalid_measurements(
    constructor: type[Point] | type[Size] | type[Rect] | type[PhysicalPageSize],
    args: tuple[object, ...],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        constructor(*args)  # type: ignore[call-arg]


def test_rect_zero_size_and_derived_properties() -> None:
    rect = Rect(10, 20, 0, 0)

    assert rect.left == 10
    assert rect.right == 10
    assert rect.top == 20
    assert rect.bottom == 20
    assert rect.center == Point(10, 20)


def test_sudoku_layout_fits_a_centered_square_and_exposes_all_cells() -> None:
    geometry = layout_sudoku(Rect(10, 20, 300, 180))

    assert geometry.outer_square == Rect(70, 20, 180, 180)
    assert geometry.cell_size == 20
    assert geometry.vertical_line_positions == tuple(range(70, 251, 20))
    assert geometry.horizontal_line_positions == tuple(range(20, 201, 20))
    cells = tuple(
        geometry.cell_rect(row, column) for row in range(9) for column in range(9)
    )
    assert len(cells) == 81
    assert len(set(cells)) == 81
    assert cells[0] == Rect(70, 20, 20, 20)
    assert cells[-1] == Rect(230, 180, 20, 20)
    assert geometry.cell_center(8, 8) == Point(240, 190)


def test_sudoku_layout_has_exact_major_divisions_and_outer_borders() -> None:
    geometry = layout_sudoku(Rect(0, 0, 180, 180))

    major_vertical = tuple(
        position
        for division, position in enumerate(geometry.vertical_line_positions)
        if geometry.is_major_division(division)
    )
    major_horizontal = tuple(
        position
        for division, position in enumerate(geometry.horizontal_line_positions)
        if geometry.is_major_division(division)
    )
    assert major_vertical == (0, 60, 120, 180)
    assert major_horizontal == (0, 60, 120, 180)


@pytest.mark.parametrize("row,column", [(-1, 0), (0, -1), (9, 0), (0, 9), (True, 0)])
def test_sudoku_layout_rejects_invalid_cell_coordinates(row: int, column: int) -> None:
    with pytest.raises((TypeError, ValueError)):
        layout_sudoku(Rect(0, 0, 180, 180)).cell_rect(row, column)


def test_sudoku_layout_requires_positive_target_and_is_immutable_deterministic() -> (
    None
):
    with pytest.raises(ValueError, match="positive dimensions"):
        layout_sudoku(Rect(0, 0, 0, 180))

    first = layout_sudoku(Rect(0, 0, 180, 180))
    second = layout_sudoku(Rect(0, 0, 180, 180))
    assert first == second
    assert hash(first) == hash(second)
    with pytest.raises(FrozenInstanceError):
        first.cell_size = 10  # type: ignore[misc]


def test_empty_grid_renders_only_twenty_ordered_grid_lines() -> None:
    drawing = render_sudoku(Grid((0,) * 81), Rect(0, 0, 180, 180))
    lines = drawing_primitives(drawing, Line)

    assert len(lines) == 20
    assert not drawing_primitives(drawing, Text)
    assert tuple((line.start, line.end) for line in lines[:10]) == tuple(
        (Point(x, 0), Point(x, 180)) for x in range(0, 181, 20)
    )
    assert tuple((line.start, line.end) for line in lines[10:]) == tuple(
        (Point(0, y), Point(180, y)) for y in range(0, 181, 20)
    )


def test_rendered_grid_lines_use_major_box_boundaries_and_outer_border() -> None:
    drawing = render_sudoku(Grid((0,) * 81), Rect(0, 0, 180, 180))
    lines = drawing_primitives(drawing, Line)

    assert sum(line.is_major for line in lines) == 8
    assert all(line.is_major for line in (lines[0], lines[3], lines[6], lines[9]))
    assert all(line.is_major for line in (lines[10], lines[13], lines[16], lines[19]))
    assert all(not line.is_major for line in (lines[1], lines[2], lines[4], lines[5]))
    assert lines[0].stroke_width == lines[3].stroke_width
    assert lines[1].stroke_width < lines[0].stroke_width


def test_digits_are_centered_and_zeroes_are_not_rendered() -> None:
    grid = Grid((5,) + (0,) * 79 + (9,))
    drawing = render_sudoku(grid, Rect(10, 20, 180, 180))
    text = drawing_primitives(drawing, Text)

    assert text == (
        Text("5", Point(20, 30), 12),
        Text("9", Point(180, 190), 12),
    )


def test_full_grid_has_one_text_primitive_per_cell_and_preserves_grid() -> None:
    original_cells = SOLUTION.cells
    drawing = render_sudoku(SOLUTION, Rect(0, 0, 180, 180))

    assert len(drawing_primitives(drawing, Text)) == 81
    assert SOLUTION.cells == original_cells


def test_rendering_scales_proportional_measurements_above_print_safe_floors() -> None:
    small = render_sudoku(Grid((0,) * 81), Rect(0, 0, 180, 180))
    large = render_sudoku(Grid((0,) * 81), Rect(0, 0, 360, 360))
    small_lines = drawing_primitives(small, Line)
    large_lines = drawing_primitives(large, Line)
    style = SudokuRenderStyle()

    assert large_lines[1].start.x == small_lines[1].start.x * 2
    assert small_lines[0].stroke_width == style.minimum_major_line_width
    assert small_lines[1].stroke_width == style.minimum_minor_line_width
    assert large_lines[0].stroke_width == 2.4
    assert large_lines[1].stroke_width == 1.0


@pytest.mark.parametrize(
    "style",
    [
        None,
        object(),
    ],
)
def test_renderer_rejects_invalid_style_type(style: object) -> None:
    with pytest.raises(TypeError):
        render_sudoku(Grid((0,) * 81), Rect(0, 0, 180, 180), style=style)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"minor_line_width_ratio": 0},
        {"minor_line_width_ratio": 0.1, "major_line_width_ratio": 0.1},
        {"digit_font_size_ratio": False},
    ],
)
def test_render_style_validates_ratios(kwargs: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        SudokuRenderStyle(**kwargs)  # type: ignore[arg-type]


def test_vector_drawing_and_svg_are_deterministic_and_valid_xml() -> None:
    drawing = render_sudoku(Grid((0,) * 81), Rect(0, 0, 180, 180))
    first = render_svg(drawing)
    second = render_svg(drawing)
    root = ElementTree.fromstring(first)

    assert first == second
    assert root.tag == f"{SVG_NAMESPACE}svg"
    assert len(root.findall(f"{SVG_NAMESPACE}line")) == 20
    assert not root.findall(f"{SVG_NAMESPACE}text")
    assert root.attrib["width"] == "180pt"
    assert root.attrib["viewBox"] == "0 0 180 180"
    assert "<image" not in first
    assert "href=" not in first


def test_svg_serializes_digits_and_major_minor_widths_with_stable_numbers() -> None:
    drawing = render_sudoku(Grid((5,) + (0,) * 80), Rect(0, 0, 112, 112))
    svg = render_svg(drawing)
    root = ElementTree.fromstring(svg)
    lines = root.findall(f"{SVG_NAMESPACE}line")
    text = root.findall(f"{SVG_NAMESPACE}text")

    assert len(lines) == 20
    assert len(text) == 1
    assert text[0].text == "5"
    assert text[0].attrib["font-family"] == "sans-serif"
    assert lines[0].attrib["stroke-width"] != lines[1].attrib["stroke-width"]
    assert "37.333333333333336" not in svg
    assert "37.3333333333" in svg


def test_svg_escapes_generic_text_content() -> None:
    drawing = VectorDrawing(
        Rect(0, 0, 10, 10),
        (Text("<&", Point(5, 5), 4),),
    )

    svg = render_svg(drawing)
    assert "&lt;&amp;" in svg
    assert ElementTree.fromstring(svg).find(f"{SVG_NAMESPACE}text").text == "<&"  # type: ignore[union-attr]


def test_physical_page_size_and_layout_are_proportionally_precise() -> None:
    page = PhysicalPageSize.from_inches(8.5, 11)
    geometry = layout_sudoku(Rect(0, 0, page.width, page.width))

    assert isclose(geometry.cell_size, 68)
