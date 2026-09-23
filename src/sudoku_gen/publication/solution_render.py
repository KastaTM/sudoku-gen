"""Physical layout and vector rendering for abstract solution pages only."""

from dataclasses import dataclass
from math import ceil, isfinite

from sudoku_gen.models import Grid
from sudoku_gen.publication.geometry import (
    PhysicalPageSize,
    Point,
    Rect,
    layout_sudoku,
)
from sudoku_gen.publication.pages import SolutionPage, SolutionPageItem
from sudoku_gen.publication.render import (
    SudokuRenderStyle,
    Text,
    VectorDrawing,
    VectorPrimitive,
    render_sudoku,
)

_DEFAULT_PAGE_SIZE = PhysicalPageSize.six_by_nine_inches()
_HEADER_FONT_SIZE = 14.0
_SOLUTION_TITLE_FONT_SIZE = 12.0
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
class SolutionPageLayout:
    """Physical points-based rules for a row-major solution-grid page."""

    page_size: PhysicalPageSize = _DEFAULT_PAGE_SIZE
    top_margin: float = 24.0
    bottom_margin: float = 24.0
    left_margin: float = 36.0
    right_margin: float = 36.0
    header_height: float = 18.0
    footer_height: float = 18.0
    columns: int = 2
    solutions_per_page: int = 6
    row_spacing: float = 12.0
    column_spacing: float = 12.0
    solution_title_spacing: float = 3.0
    minimum_grid_size: float = 120.0

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
            "row_spacing",
            "column_spacing",
            "solution_title_spacing",
        ):
            object.__setattr__(
                self, name, _non_negative_points(getattr(self, name), name)
            )
        object.__setattr__(
            self,
            "minimum_grid_size",
            _positive_points(self.minimum_grid_size, "minimum_grid_size"),
        )
        for name in ("columns", "solutions_per_page"):
            if type(getattr(self, name)) is not int:
                raise TypeError(f"{name} must be a built-in integer.")
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1.")
        if self.columns > self.solutions_per_page:
            raise ValueError("columns must not exceed solutions_per_page.")
        if self.left_margin + self.right_margin >= self.page_size.width:
            raise ValueError("Horizontal margins leave no drawable page width.")
        if self.top_margin + self.bottom_margin >= self.page_size.height:
            raise ValueError("Vertical margins leave no drawable page height.")
        if self.header_height + self.footer_height >= self.usable_rect.height:
            raise ValueError("Header and footer leave no solution content height.")

    @property
    def row_count(self) -> int:
        return ceil(self.solutions_per_page / self.columns)

    @property
    def page_bounds(self) -> Rect:
        return Rect(0, 0, self.page_size.width, self.page_size.height)

    @property
    def usable_rect(self) -> Rect:
        return Rect(
            self.left_margin,
            self.top_margin,
            self.page_size.width - self.left_margin - self.right_margin,
            self.page_size.height - self.top_margin - self.bottom_margin,
        )


_DEFAULT_SOLUTION_PAGE_LAYOUT = SolutionPageLayout()


@dataclass(frozen=True, slots=True)
class SolutionSlotGeometry:
    """One abstract solution item assigned to a physical row-major slot."""

    item: SolutionPageItem
    row: int
    column: int
    slot_rect: Rect
    grid_rect: Rect
    title_position: Point

    def __post_init__(self) -> None:
        if not isinstance(self.item, SolutionPageItem):
            raise TypeError("item must be a SolutionPageItem.")
        if type(self.row) is not int or type(self.column) is not int:
            raise TypeError("row and column must be built-in integers.")
        if self.row < 0 or self.column < 0:
            raise ValueError("row and column must not be negative.")
        if not isinstance(self.slot_rect, Rect) or not isinstance(self.grid_rect, Rect):
            raise TypeError("slot_rect and grid_rect must be Rect instances.")
        if not isinstance(self.title_position, Point):
            raise TypeError("title_position must be a Point.")
        if self.grid_rect.width <= 0 or self.grid_rect.width != self.grid_rect.height:
            raise ValueError("grid_rect must be a positive square.")


@dataclass(frozen=True, slots=True)
class SolutionPageGeometry:
    """Complete physical geometry for one abstract SolutionPage."""

    page: SolutionPage
    page_bounds: Rect
    usable_rect: Rect
    header_rect: Rect
    footer_rect: Rect
    solution_area_rect: Rect
    slots: tuple[SolutionSlotGeometry, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.page, SolutionPage):
            raise TypeError("page must be a SolutionPage.")
        if not isinstance(self.slots, tuple) or not all(
            isinstance(slot, SolutionSlotGeometry) for slot in self.slots
        ):
            raise TypeError("slots must be a tuple of SolutionSlotGeometry instances.")
        if tuple(slot.item for slot in self.slots) != self.page.items:
            raise ValueError("Slot geometry must preserve the page's item order.")

    def slot_for_number(self, number: int) -> SolutionSlotGeometry:
        """Return the physical slot for a global puzzle number on this page."""
        if type(number) is not int:
            raise TypeError("puzzle number must be a built-in integer.")
        for slot in self.slots:
            if slot.item.puzzle.number == number:
                return slot
        raise ValueError("puzzle number does not appear on this page.")


def _contains(outer: Rect, inner: Rect) -> bool:
    return (
        outer.left <= inner.left
        and inner.right <= outer.right
        and outer.top <= inner.top
        and inner.bottom <= outer.bottom
    )


def layout_solution_page(
    page: SolutionPage,
    physical_layout: SolutionPageLayout = _DEFAULT_SOLUTION_PAGE_LAYOUT,
) -> SolutionPageGeometry:
    """Map abstract solution slots to a fixed row-major physical grid."""
    if not isinstance(page, SolutionPage):
        raise TypeError("page must be a SolutionPage.")
    if not isinstance(physical_layout, SolutionPageLayout):
        raise TypeError("physical_layout must be a SolutionPageLayout.")
    if len(page.items) > physical_layout.solutions_per_page:
        raise ValueError(
            "Solution page exceeds the configured solutions_per_page capacity."
        )

    usable_rect = physical_layout.usable_rect
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
    solution_area_rect = Rect(
        usable_rect.left,
        header_rect.bottom,
        usable_rect.width,
        footer_rect.top - header_rect.bottom,
    )
    row_count = physical_layout.row_count
    slot_width = (
        solution_area_rect.width
        - (physical_layout.columns - 1) * physical_layout.column_spacing
    ) / physical_layout.columns
    slot_height = (
        solution_area_rect.height - (row_count - 1) * physical_layout.row_spacing
    ) / row_count
    if slot_width <= 0 or slot_height <= 0:
        raise ValueError("Configured spacing leaves no room for solution slots.")
    label_height = _SOLUTION_TITLE_FONT_SIZE + physical_layout.solution_title_spacing
    if label_height >= slot_height:
        raise ValueError("Solution titles leave no height for Sudoku grids.")

    slots: list[SolutionSlotGeometry] = []
    for item in page.items:
        position = item.slot - 1
        row, column = divmod(position, physical_layout.columns)
        slot_rect = Rect(
            solution_area_rect.left
            + column * (slot_width + physical_layout.column_spacing),
            solution_area_rect.top + row * (slot_height + physical_layout.row_spacing),
            slot_width,
            slot_height,
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
                "Configured page cannot fit the minimum acceptable solution grid size."
            )
        if not _contains(slot_rect, grid_rect):
            raise ValueError("Solution grid must remain inside its allocated slot.")
        slots.append(
            SolutionSlotGeometry(
                item,
                row,
                column,
                slot_rect,
                grid_rect,
                Point(
                    slot_rect.center.x,
                    slot_rect.top + _SOLUTION_TITLE_FONT_SIZE / 2,
                ),
            )
        )
    return SolutionPageGeometry(
        page,
        physical_layout.page_bounds,
        usable_rect,
        header_rect,
        footer_rect,
        solution_area_rect,
        tuple(slots),
    )


def _solution_for(item: SolutionPageItem) -> Grid:
    solution = item.puzzle.puzzle.solution
    if solution is None:
        raise ValueError("A solution page item must have an associated solution.")
    return solution


def render_solution_page(
    page: SolutionPage,
    physical_layout: SolutionPageLayout = _DEFAULT_SOLUTION_PAGE_LAYOUT,
    *,
    sudoku_style: SudokuRenderStyle | None = None,
) -> VectorDrawing:
    """Render a complete physical solution page with solved Sudoku grids."""
    geometry = layout_solution_page(page, physical_layout)
    if sudoku_style is not None and not isinstance(sudoku_style, SudokuRenderStyle):
        raise TypeError("sudoku_style must be a SudokuRenderStyle or None.")
    primitives: list[VectorPrimitive] = [
        Text("SOLUCIONES", geometry.header_rect.center, _HEADER_FONT_SIZE)
    ]
    for slot in geometry.slots:
        primitives.append(
            Text(
                f"Solución #{slot.item.puzzle.number}",
                slot.title_position,
                _SOLUTION_TITLE_FONT_SIZE,
            )
        )
        solution = _solution_for(slot.item)
        grid_drawing = (
            render_sudoku(solution, slot.grid_rect)
            if sudoku_style is None
            else render_sudoku(solution, slot.grid_rect, style=sudoku_style)
        )
        primitives.extend(grid_drawing.primitives)
    primitives.append(
        Text(str(page.page_number), geometry.footer_rect.center, _FOOTER_FONT_SIZE)
    )
    return VectorDrawing(geometry.page_bounds, tuple(primitives))
