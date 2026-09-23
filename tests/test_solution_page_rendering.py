"""Physical layout and vector rendering tests for abstract solution pages."""

from dataclasses import FrozenInstanceError
from xml.etree import ElementTree

import pytest

from sudoku_gen.difficulty import Difficulty, DifficultyReport
from sudoku_gen.fingerprint import fingerprint_puzzle
from sudoku_gen.human_solver import LogicalSolveStatus
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.publication import (
    Line,
    PhysicalPageSize,
    Rect,
    SolutionPage,
    SolutionPageItem,
    SolutionPageLayout,
    Text,
    layout_solution_page,
    render_solution_page,
    render_svg,
)
from sudoku_gen.publication.models import BookPuzzle

SOLUTION = Grid.from_string(
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)
SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"


def make_entry(number: int) -> BookPuzzle:
    grid = Grid(
        tuple(
            value if index == number % 81 else 0
            for index, value in enumerate(SOLUTION.cells)
        )
    )
    puzzle = SudokuPuzzle(grid, SOLUTION)
    report = DifficultyReport(
        Difficulty.EASY, 0, None, 0, 0, 0, 0, LogicalSolveStatus.SOLVED
    )
    return BookPuzzle(number, puzzle, report, fingerprint_puzzle(puzzle))


def make_page(
    count: int, *, page_number: int = 10, first_number: int = 1
) -> SolutionPage:
    return SolutionPage(
        page_number,
        tuple(
            SolutionPageItem(slot, make_entry(first_number + slot - 1))
            for slot in range(1, count + 1)
        ),
    )


def contains(outer: Rect, inner: Rect) -> bool:
    return (
        outer.left <= inner.left
        and inner.right <= outer.right
        and outer.top <= inner.top
        and inner.bottom <= outer.bottom
    )


def test_default_layout_is_six_solutions_in_two_columns_and_three_rows() -> None:
    layout = SolutionPageLayout()
    geometry = layout_solution_page(make_page(6), layout)

    assert layout.page_size == PhysicalPageSize.six_by_nine_inches()
    assert layout.columns == 2
    assert layout.solutions_per_page == 6
    assert layout.row_count == 3
    assert geometry.page_bounds == Rect(0, 0, 432, 648)
    assert tuple((slot.row, slot.column) for slot in geometry.slots) == (
        (0, 0),
        (0, 1),
        (1, 0),
        (1, 1),
        (2, 0),
        (2, 1),
    )


def test_row_major_slot_order_and_centered_square_grids() -> None:
    geometry = layout_solution_page(make_page(6), SolutionPageLayout())

    assert tuple(slot.item.slot for slot in geometry.slots) == (1, 2, 3, 4, 5, 6)
    assert geometry.slots[0].slot_rect.top == geometry.slots[1].slot_rect.top
    assert geometry.slots[0].slot_rect.left < geometry.slots[1].slot_rect.left
    assert geometry.slots[0].slot_rect.top < geometry.slots[2].slot_rect.top
    assert all(slot.grid_rect.width == slot.grid_rect.height for slot in geometry.slots)
    assert all(
        slot.grid_rect.center.x == slot.slot_rect.center.x for slot in geometry.slots
    )


def test_custom_columns_size_margins_and_spacing() -> None:
    layout = SolutionPageLayout(
        page_size=PhysicalPageSize(600, 700),
        top_margin=20,
        bottom_margin=30,
        left_margin=40,
        right_margin=50,
        header_height=20,
        footer_height=25,
        columns=1,
        solutions_per_page=3,
        row_spacing=15,
        solution_title_spacing=4,
        minimum_grid_size=100,
    )
    geometry = layout_solution_page(make_page(3), layout)

    assert geometry.usable_rect == Rect(40, 20, 510, 650)
    assert tuple((slot.row, slot.column) for slot in geometry.slots) == (
        (0, 0),
        (1, 0),
        (2, 0),
    )
    assert geometry.slots[1].slot_rect.top - geometry.slots[0].slot_rect.bottom == 15


def test_partial_page_preserves_its_first_abstract_slots() -> None:
    geometry = layout_solution_page(make_page(4), SolutionPageLayout())

    assert tuple(
        (slot.item.slot, slot.row, slot.column) for slot in geometry.slots
    ) == (
        (1, 0, 0),
        (2, 0, 1),
        (3, 1, 0),
        (4, 1, 1),
    )
    assert geometry.slots[-1].slot_rect.bottom < geometry.solution_area_rect.bottom


def test_solution_slots_stay_inside_margins_without_overlapping() -> None:
    geometry = layout_solution_page(make_page(6), SolutionPageLayout())

    assert all(
        contains(geometry.usable_rect, slot.slot_rect) for slot in geometry.slots
    )
    assert all(contains(slot.slot_rect, slot.grid_rect) for slot in geometry.slots)
    assert geometry.slots[0].slot_rect.right < geometry.slots[1].slot_rect.left
    assert geometry.slots[0].slot_rect.bottom < geometry.slots[2].slot_rect.top
    assert geometry.header_rect.bottom <= geometry.solution_area_rect.top
    assert geometry.solution_area_rect.bottom <= geometry.footer_rect.top


def test_layout_rejects_overflow_and_unreadable_or_impossible_configurations() -> None:
    with pytest.raises(ValueError, match="capacity"):
        layout_solution_page(make_page(7), SolutionPageLayout())
    with pytest.raises(ValueError, match="minimum acceptable"):
        layout_solution_page(make_page(6), SolutionPageLayout(minimum_grid_size=200))
    with pytest.raises(ValueError, match="columns"):
        SolutionPageLayout(columns=7, solutions_per_page=6)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"row_spacing": -1},
        {"column_spacing": True},
        {"minimum_grid_size": 0},
        {"columns": False},
        {"solutions_per_page": 0},
        {"left_margin": 300, "right_margin": 200},
        {"header_height": 500, "footer_height": 500},
    ],
)
def test_solution_layout_validates_configuration(kwargs: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        SolutionPageLayout(**kwargs)  # type: ignore[arg-type]


def test_solution_renderer_uses_completed_solutions_and_global_numbers() -> None:
    page = make_page(2, page_number=27, first_number=37)
    drawing = render_solution_page(
        page,
        SolutionPageLayout(solutions_per_page=2, columns=2, minimum_grid_size=100),
    )
    lines = tuple(item for item in drawing.primitives if isinstance(item, Line))
    text = tuple(item for item in drawing.primitives if isinstance(item, Text))

    assert len(lines) == 40
    assert len(text) == 1 + 2 + 81 * 2 + 1
    assert tuple(item.content for item in text[:3]) == (
        "SOLUCIONES",
        "Solución #37",
        "5",
    )
    assert "Solución #38" in tuple(item.content for item in text)
    assert text[-1].content == "27"


def test_solution_geometry_lookup_and_immutable_records() -> None:
    geometry = layout_solution_page(make_page(2, first_number=37), SolutionPageLayout())

    assert geometry.slot_for_number(38) == geometry.slots[1]
    with pytest.raises(ValueError):
        geometry.slot_for_number(99)
    with pytest.raises(TypeError):
        geometry.slot_for_number(True)
    with pytest.raises(FrozenInstanceError):
        geometry.slots = ()  # type: ignore[misc]


def test_solution_page_rendering_is_deterministic_and_svg_is_valid() -> None:
    page = make_page(6, page_number=14)
    first = render_solution_page(page, SolutionPageLayout())
    second = render_solution_page(page, SolutionPageLayout())
    svg = render_svg(first)
    root = ElementTree.fromstring(svg)

    assert first == second
    assert root.tag == f"{SVG_NAMESPACE}svg"
    assert root.attrib["width"] == "432pt"
    assert root.attrib["height"] == "648pt"
    assert len(root.findall(f"{SVG_NAMESPACE}line")) == 120
    assert len(root.findall(f"{SVG_NAMESPACE}text")) == 494
