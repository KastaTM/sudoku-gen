"""Physical layout and vector rendering tests for abstract puzzle pages."""

from dataclasses import FrozenInstanceError
from xml.etree import ElementTree

import pytest

from sudoku_gen.difficulty import Difficulty, DifficultyReport
from sudoku_gen.fingerprint import fingerprint_puzzle
from sudoku_gen.human_solver import LogicalSolveStatus
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.publication import (
    Line,
    PhysicalPageLayout,
    PhysicalPageSize,
    PuzzlePage,
    PuzzlePageItem,
    Rect,
    Text,
    layout_puzzle_page,
    render_puzzle_page,
    render_svg,
)
from sudoku_gen.publication.models import BookPuzzle

SOLUTION = Grid.from_string(
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)
SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"


def make_entry(number: int, difficulty: Difficulty = Difficulty.EASY) -> BookPuzzle:
    grid = Grid(
        tuple(
            value if index == number - 1 else 0
            for index, value in enumerate(SOLUTION.cells)
        )
    )
    puzzle = SudokuPuzzle(grid, SOLUTION)
    report = DifficultyReport(
        difficulty, 0, None, 0, 0, 0, 0, LogicalSolveStatus.SOLVED
    )
    return BookPuzzle(number, puzzle, report, fingerprint_puzzle(puzzle))


def make_page(
    count: int,
    *,
    page_number: int = 1,
    difficulties: tuple[Difficulty, ...] | None = None,
) -> PuzzlePage:
    resolved_difficulties = difficulties or (Difficulty.EASY,) * count
    return PuzzlePage(
        page_number,
        tuple(
            PuzzlePageItem(slot, make_entry(slot, resolved_difficulties[slot - 1]))
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


def test_default_layout_is_a_6_by_9_inch_two_puzzle_page() -> None:
    layout = PhysicalPageLayout()
    geometry = layout_puzzle_page(make_page(2), layout)

    assert layout.page_size == PhysicalPageSize.six_by_nine_inches()
    assert layout.puzzles_per_page == 2
    assert geometry.page_bounds == Rect(0, 0, 432, 648)
    assert geometry.usable_rect == Rect(36, 24, 360, 600)
    assert geometry.header_rect == Rect(36, 24, 360, 18)
    assert geometry.footer_rect == Rect(36, 606, 360, 18)
    assert len(geometry.slots) == 2


def test_custom_page_margins_header_and_footer_reserve_content_area() -> None:
    layout = PhysicalPageLayout(
        page_size=PhysicalPageSize(400, 600),
        top_margin=10,
        bottom_margin=20,
        left_margin=30,
        right_margin=40,
        header_height=25,
        footer_height=30,
        minimum_grid_size=80,
    )
    geometry = layout_puzzle_page(make_page(2), layout)

    assert geometry.usable_rect == Rect(30, 10, 330, 570)
    assert geometry.header_rect == Rect(30, 10, 330, 25)
    assert geometry.footer_rect == Rect(30, 550, 330, 30)
    assert geometry.puzzle_area_rect == Rect(30, 35, 330, 515)
    assert contains(geometry.page_bounds, geometry.usable_rect)


@pytest.mark.parametrize("capacity", [1, 2, 4])
def test_vertical_slot_algorithm_supports_one_two_and_four_puzzles(
    capacity: int,
) -> None:
    layout = PhysicalPageLayout(
        page_size=PhysicalPageSize(500, 800),
        top_margin=20,
        bottom_margin=20,
        left_margin=20,
        right_margin=20,
        header_height=20,
        footer_height=20,
        minimum_vertical_spacing=10,
        minimum_grid_size=80,
        puzzles_per_page=capacity,
    )
    geometry = layout_puzzle_page(make_page(capacity), layout)

    assert tuple(slot.item.slot for slot in geometry.slots) == tuple(
        range(1, capacity + 1)
    )
    assert tuple(slot.slot_rect.top for slot in geometry.slots) == tuple(
        sorted(slot.slot_rect.top for slot in geometry.slots)
    )
    assert all(
        slot.grid_rect.center.x == slot.slot_rect.center.x for slot in geometry.slots
    )
    assert all(slot.grid_rect.width == slot.grid_rect.height for slot in geometry.slots)
    assert all(
        slot.grid_rect.width >= layout.minimum_grid_size for slot in geometry.slots
    )


def test_slot_spacing_and_partial_page_policy_preserve_slot_positions() -> None:
    layout = PhysicalPageLayout(minimum_vertical_spacing=20)
    full = layout_puzzle_page(make_page(2), layout)
    partial = layout_puzzle_page(make_page(1), layout)

    assert full.slots[1].slot_rect.top - full.slots[0].slot_rect.bottom == 20
    assert partial.slots[0].slot_rect == full.slots[0].slot_rect
    assert partial.slots[0].slot_rect.bottom < partial.puzzle_area_rect.bottom


def test_slot_geometry_respects_margins_and_does_not_overlap() -> None:
    geometry = layout_puzzle_page(make_page(2), PhysicalPageLayout())
    first, second = geometry.slots

    assert all(
        contains(geometry.usable_rect, slot.slot_rect) for slot in geometry.slots
    )
    assert all(contains(slot.slot_rect, slot.grid_rect) for slot in geometry.slots)
    assert first.slot_rect.bottom < second.slot_rect.top
    assert geometry.header_rect.bottom <= geometry.puzzle_area_rect.top
    assert geometry.puzzle_area_rect.bottom <= geometry.footer_rect.top


def test_layout_rejects_capacity_overflow_and_impossible_minimum_grid_size() -> None:
    with pytest.raises(ValueError, match="capacity"):
        layout_puzzle_page(make_page(3), PhysicalPageLayout(puzzles_per_page=2))
    with pytest.raises(ValueError, match="minimum acceptable"):
        layout_puzzle_page(
            make_page(4),
            PhysicalPageLayout(puzzles_per_page=4, minimum_grid_size=200),
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"top_margin": -1},
        {"left_margin": True},
        {"minimum_grid_size": 0},
        {"puzzles_per_page": False},
        {"puzzles_per_page": 0},
        {"left_margin": 300, "right_margin": 200},
        {"header_height": 500, "footer_height": 500},
    ],
)
def test_physical_layout_rejects_invalid_or_impossible_configuration(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        PhysicalPageLayout(**kwargs)  # type: ignore[arg-type]


def test_page_geometry_lookup_and_immutable_records() -> None:
    geometry = layout_puzzle_page(make_page(2, page_number=17), PhysicalPageLayout())

    assert geometry.slot_for_number(2) == geometry.slots[1]
    with pytest.raises(ValueError):
        geometry.slot_for_number(3)
    with pytest.raises(TypeError):
        geometry.slot_for_number(True)
    assert hash(geometry) == hash(layout_puzzle_page(make_page(2, page_number=17)))
    with pytest.raises(FrozenInstanceError):
        geometry.page_bounds = Rect(0, 0, 1, 1)  # type: ignore[misc]


def test_page_renderer_draws_header_labels_grids_and_existing_page_number() -> None:
    page = make_page(
        2,
        page_number=17,
        difficulties=(Difficulty.EASY, Difficulty.HARD),
    )
    drawing = render_puzzle_page(page, PhysicalPageLayout())
    text = tuple(item for item in drawing.primitives if isinstance(item, Text))
    lines = tuple(item for item in drawing.primitives if isinstance(item, Line))

    assert drawing.bounds == Rect(0, 0, 432, 648)
    assert len(lines) == 40
    assert tuple(item.content for item in text) == (
        "SUDOKUS",
        "Sudoku #1",
        "Fácil",
        "5",
        "Sudoku #2",
        "Difícil",
        "3",
        "17",
    )


def test_optional_difficulty_labels_are_not_rendered_when_disabled() -> None:
    drawing = render_puzzle_page(
        make_page(2, difficulties=(Difficulty.EASY, Difficulty.EXPERT)),
        PhysicalPageLayout(show_difficulty_labels=False),
    )

    assert tuple(
        item.content for item in drawing.primitives if isinstance(item, Text)
    ) == ("SUDOKUS", "Sudoku #1", "5", "Sudoku #2", "3", "1")


def test_page_renderer_is_deterministic_and_preserves_inputs_and_grid_behavior() -> (
    None
):
    page = make_page(1)
    layout = PhysicalPageLayout(puzzles_per_page=1)
    first = render_puzzle_page(page, layout)
    second = render_puzzle_page(page, layout)

    assert first == second
    assert page.items[0].puzzle.puzzle.grid.cells[0] == SOLUTION.cells[0]
    assert len(tuple(item for item in first.primitives if isinstance(item, Line))) == 20


def test_complete_page_svg_is_valid_and_has_expected_page_elements() -> None:
    drawing = render_puzzle_page(make_page(2, page_number=9), PhysicalPageLayout())
    svg = render_svg(drawing)
    root = ElementTree.fromstring(svg)

    assert root.tag == f"{SVG_NAMESPACE}svg"
    assert root.attrib["width"] == "432pt"
    assert root.attrib["height"] == "648pt"
    assert len(root.findall(f"{SVG_NAMESPACE}line")) == 40
    assert tuple(text.text for text in root.findall(f"{SVG_NAMESPACE}text")) == (
        "SUDOKUS",
        "Sudoku #1",
        "Fácil",
        "5",
        "Sudoku #2",
        "Fácil",
        "3",
        "9",
    )
