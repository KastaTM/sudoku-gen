"""Physical layout and vector rendering for abstract puzzle pages only.

The layout reserves every configured vertical slot even when a final abstract
page is partial. Unused slots therefore remain below the rendered puzzles and
existing one-based slot numbers retain stable physical positions.
"""

from dataclasses import dataclass
from math import isfinite

from sudoku_gen.publication.geometry import (
    PhysicalPageSize,
    Point,
    Rect,
    layout_sudoku,
)
from sudoku_gen.publication.locale import ES_ES, BookLocale
from sudoku_gen.publication.pages import PuzzlePage, PuzzlePageItem
from sudoku_gen.publication.preflight import PageMargins
from sudoku_gen.publication.render import (
    SudokuRenderStyle,
    Text,
    VectorDrawing,
    VectorPrimitive,
    render_sudoku,
)

_DEFAULT_PAGE_SIZE = PhysicalPageSize.six_by_nine_inches()
_HEADER_FONT_SIZE = 14.0
_PUZZLE_TITLE_FONT_SIZE = 12.0
_DIFFICULTY_FONT_SIZE = 9.0
_FOOTER_FONT_SIZE = 10.0


def _non_negative_points(value: float | int, name: str) -> float:
    if type(value) not in (int, float):
        raise TypeError(f"{name} must be a built-in finite number.")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{name} must be finite.")
    if result < 0:
        raise ValueError(f"{name} must not be negative.")
    return result


def _positive_points(value: float | int, name: str) -> float:
    result = _non_negative_points(value, name)
    if result <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return result


@dataclass(frozen=True, slots=True)
class PhysicalPageLayout:
    """Physical points-based rules for vertically stacked Sudoku puzzle slots."""

    page_size: PhysicalPageSize = _DEFAULT_PAGE_SIZE
    top_margin: float = 24.0
    bottom_margin: float = 24.0
    left_margin: float = 36.0
    right_margin: float = 36.0
    header_height: float = 18.0
    footer_height: float = 18.0
    minimum_vertical_spacing: float = 12.0
    puzzle_title_spacing: float = 3.0
    show_difficulty_labels: bool = True
    minimum_grid_size: float = 96.0
    puzzles_per_page: int = 2

    def __post_init__(self) -> None:
        if not isinstance(self.page_size, PhysicalPageSize):
            raise TypeError("page_size must be a PhysicalPageSize.")
        for name in (
            "top_margin",
            "bottom_margin",
            "left_margin",
            "right_margin",
            "header_height",
            "footer_height",
            "minimum_vertical_spacing",
            "puzzle_title_spacing",
        ):
            object.__setattr__(
                self, name, _non_negative_points(getattr(self, name), name)
            )
        object.__setattr__(
            self,
            "minimum_grid_size",
            _positive_points(self.minimum_grid_size, "minimum_grid_size"),
        )
        if type(self.show_difficulty_labels) is not bool:
            raise TypeError("show_difficulty_labels must be a bool.")
        if type(self.puzzles_per_page) is not int:
            raise TypeError("puzzles_per_page must be a built-in integer.")
        if self.puzzles_per_page < 1:
            raise ValueError("puzzles_per_page must be at least 1.")
        if self.left_margin + self.right_margin >= self.page_size.width:
            raise ValueError("Horizontal margins leave no drawable page width.")
        if self.top_margin + self.bottom_margin >= self.page_size.height:
            raise ValueError("Vertical margins leave no drawable page height.")
        if self.header_height + self.footer_height >= self.usable_rect.height:
            raise ValueError("Header and footer leave no puzzle content height.")

    @property
    def page_bounds(self) -> Rect:
        return Rect(0, 0, self.page_size.width, self.page_size.height)

    @property
    def usable_rect(self) -> Rect:
        """Return the legacy symmetric drawable rectangle for standalone rendering."""
        return Rect(
            self.left_margin,
            self.top_margin,
            self.page_size.width - self.left_margin - self.right_margin,
            self.page_size.height - self.top_margin - self.bottom_margin,
        )

    def usable_rect_for(self, margins: PageMargins | None = None) -> Rect:
        """Return a drawable rectangle using optional physical recto/verso margins."""
        if margins is None:
            return self.usable_rect
        if not isinstance(margins, PageMargins):
            raise TypeError("margins must be a PageMargins or None.")
        width = self.page_size.width - margins.left - margins.right
        height = self.page_size.height - margins.top - margins.bottom
        if width <= 0 or height <= 0:
            raise ValueError("Physical margins leave no drawable page area.")
        return Rect(margins.left, margins.top, width, height)


_DEFAULT_PHYSICAL_PAGE_LAYOUT = PhysicalPageLayout()


@dataclass(frozen=True, slots=True)
class PuzzleSlotGeometry:
    """One abstract page item with its physical label and Sudoku grid geometry."""

    item: PuzzlePageItem
    slot_rect: Rect
    grid_rect: Rect
    title_position: Point
    difficulty_position: Point | None

    def __post_init__(self) -> None:
        if not isinstance(self.item, PuzzlePageItem):
            raise TypeError("item must be a PuzzlePageItem.")
        if not isinstance(self.slot_rect, Rect):
            raise TypeError("slot_rect must be a Rect.")
        if not isinstance(self.grid_rect, Rect):
            raise TypeError("grid_rect must be a Rect.")
        if not isinstance(self.title_position, Point):
            raise TypeError("title_position must be a Point.")
        if self.difficulty_position is not None and not isinstance(
            self.difficulty_position, Point
        ):
            raise TypeError("difficulty_position must be a Point or None.")
        if self.grid_rect.width <= 0 or self.grid_rect.height <= 0:
            raise ValueError("grid_rect must have positive dimensions.")
        if self.grid_rect.width != self.grid_rect.height:
            raise ValueError("grid_rect must be square.")


@dataclass(frozen=True, slots=True)
class PuzzlePageGeometry:
    """Complete physical geometry for one abstract PuzzlePage."""

    page: PuzzlePage
    page_bounds: Rect
    usable_rect: Rect
    header_rect: Rect
    footer_rect: Rect
    puzzle_area_rect: Rect
    slots: tuple[PuzzleSlotGeometry, ...]
    margins: PageMargins | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.page, PuzzlePage):
            raise TypeError("page must be a PuzzlePage.")
        for name in (
            "page_bounds",
            "usable_rect",
            "header_rect",
            "footer_rect",
            "puzzle_area_rect",
        ):
            if not isinstance(getattr(self, name), Rect):
                raise TypeError(f"{name} must be a Rect.")
        if not isinstance(self.slots, tuple):
            raise TypeError("slots must be a tuple of PuzzleSlotGeometry instances.")
        if not all(isinstance(slot, PuzzleSlotGeometry) for slot in self.slots):
            raise TypeError("slots must contain only PuzzleSlotGeometry instances.")
        if tuple(slot.item for slot in self.slots) != self.page.items:
            raise ValueError("Slot geometry must preserve the page's item order.")
        if self.margins is not None and not isinstance(self.margins, PageMargins):
            raise TypeError("margins must be a PageMargins or None.")

    def slot_for_number(self, number: int) -> PuzzleSlotGeometry:
        """Return the physical slot for one page-local global puzzle number."""
        if type(number) is not int:
            raise TypeError("puzzle number must be a built-in integer.")
        for slot in self.slots:
            if slot.item.puzzle.number == number:
                return slot
        raise ValueError("puzzle number does not appear on this page.")


def _label_height(layout: PhysicalPageLayout) -> float:
    height = _PUZZLE_TITLE_FONT_SIZE + layout.puzzle_title_spacing
    if layout.show_difficulty_labels:
        height += _DIFFICULTY_FONT_SIZE + layout.puzzle_title_spacing
    return height


def _contains(outer: Rect, inner: Rect) -> bool:
    return (
        outer.left <= inner.left
        and inner.right <= outer.right
        and outer.top <= inner.top
        and inner.bottom <= outer.bottom
    )


def layout_puzzle_page(
    page: PuzzlePage,
    physical_layout: PhysicalPageLayout = _DEFAULT_PHYSICAL_PAGE_LAYOUT,
    *,
    margins: PageMargins | None = None,
) -> PuzzlePageGeometry:
    """Map an abstract PuzzlePage to fixed vertical physical slots in points."""
    if not isinstance(page, PuzzlePage):
        raise TypeError("page must be a PuzzlePage.")
    if not isinstance(physical_layout, PhysicalPageLayout):
        raise TypeError("physical_layout must be a PhysicalPageLayout.")
    if len(page.items) > physical_layout.puzzles_per_page:
        raise ValueError(
            "Puzzle page exceeds the configured puzzles_per_page capacity."
        )

    page_bounds = physical_layout.page_bounds
    usable_rect = physical_layout.usable_rect_for(margins)
    header_rect = Rect(
        usable_rect.left,
        usable_rect.top,
        usable_rect.width,
        physical_layout.header_height,
    )
    footer_rect = Rect(
        usable_rect.left,
        usable_rect.bottom - physical_layout.footer_height,
        usable_rect.width,
        physical_layout.footer_height,
    )
    puzzle_area_rect = Rect(
        usable_rect.left,
        header_rect.bottom,
        usable_rect.width,
        footer_rect.top - header_rect.bottom,
    )
    total_spacing = (
        physical_layout.puzzles_per_page - 1
    ) * physical_layout.minimum_vertical_spacing
    slot_height = (
        puzzle_area_rect.height - total_spacing
    ) / physical_layout.puzzles_per_page
    if slot_height <= 0:
        raise ValueError("Configured spacing leaves no height for puzzle slots.")

    slots: list[PuzzleSlotGeometry] = []
    label_height = _label_height(physical_layout)
    for item in page.items:
        slot_top = puzzle_area_rect.top + (item.slot - 1) * (
            slot_height + physical_layout.minimum_vertical_spacing
        )
        slot_rect = Rect(
            puzzle_area_rect.left,
            slot_top,
            puzzle_area_rect.width,
            slot_height,
        )
        if label_height >= slot_rect.height:
            raise ValueError("Puzzle labels leave no height for a Sudoku grid.")
        title_position = Point(
            slot_rect.center.x,
            slot_rect.top + _PUZZLE_TITLE_FONT_SIZE / 2,
        )
        difficulty_position = (
            Point(
                slot_rect.center.x,
                slot_rect.top
                + _PUZZLE_TITLE_FONT_SIZE
                + physical_layout.puzzle_title_spacing
                + _DIFFICULTY_FONT_SIZE / 2,
            )
            if physical_layout.show_difficulty_labels
            else None
        )
        grid_target = Rect(
            slot_rect.left,
            slot_rect.top + label_height,
            slot_rect.width,
            slot_rect.height - label_height,
        )
        grid_rect = layout_sudoku(grid_target).outer_square
        if grid_rect.width < physical_layout.minimum_grid_size:
            raise ValueError(
                "Configured page cannot fit the minimum acceptable Sudoku grid size."
            )
        if not _contains(slot_rect, grid_rect):
            raise ValueError(
                "Sudoku grid must remain inside its allocated puzzle slot."
            )
        slots.append(
            PuzzleSlotGeometry(
                item,
                slot_rect,
                grid_rect,
                title_position,
                difficulty_position,
            )
        )
    return PuzzlePageGeometry(
        page,
        page_bounds,
        usable_rect,
        header_rect,
        footer_rect,
        puzzle_area_rect,
        tuple(slots),
        margins,
    )


def render_puzzle_page(
    page: PuzzlePage,
    physical_layout: PhysicalPageLayout = _DEFAULT_PHYSICAL_PAGE_LAYOUT,
    *,
    sudoku_style: SudokuRenderStyle | None = None,
    margins: PageMargins | None = None,
    locale: BookLocale = ES_ES,
) -> VectorDrawing:
    """Render a complete physical puzzle page using the single-grid renderer."""
    geometry = layout_puzzle_page(page, physical_layout, margins=margins)
    primitives: list[VectorPrimitive] = [
        Text(locale.puzzle_page_header, geometry.header_rect.center, _HEADER_FONT_SIZE)
    ]
    for slot in geometry.slots:
        primitives.append(
            Text(
                locale.puzzle_label(slot.item.puzzle.number),
                slot.title_position,
                _PUZZLE_TITLE_FONT_SIZE,
            )
        )
        if slot.difficulty_position is not None:
            primitives.append(
                Text(
                    locale.difficulty_label(
                        slot.item.puzzle.difficulty_report.difficulty
                    ),
                    slot.difficulty_position,
                    _DIFFICULTY_FONT_SIZE,
                )
            )
        if sudoku_style is None:
            grid_drawing = render_sudoku(slot.item.puzzle.puzzle.grid, slot.grid_rect)
        else:
            if not isinstance(sudoku_style, SudokuRenderStyle):
                raise TypeError("sudoku_style must be a SudokuRenderStyle or None.")
            grid_drawing = render_sudoku(
                slot.item.puzzle.puzzle.grid,
                slot.grid_rect,
                style=sudoku_style,
            )
        primitives.extend(grid_drawing.primitives)
    primitives.append(
        Text(str(page.page_number), geometry.footer_rect.center, _FOOTER_FONT_SIZE)
    )
    return VectorDrawing(geometry.page_bounds, tuple(primitives))
