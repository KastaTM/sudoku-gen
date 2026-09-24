"""Complete interior rendering with distinct physical and editorial page numbers."""

from sudoku_gen.publication.front_render import render_front_matter_page
from sudoku_gen.publication.interior import (
    ContentsPage,
    CopyrightPage,
    InstructionsPage,
    InteriorPlan,
    TitlePage,
)
from sudoku_gen.publication.page_render import PhysicalPageLayout, render_puzzle_page
from sudoku_gen.publication.pages import PuzzlePage, SolutionPage
from sudoku_gen.publication.pdf import render_pdf
from sudoku_gen.publication.preflight import PrintProfile
from sudoku_gen.publication.render import SudokuRenderStyle, VectorDrawing
from sudoku_gen.publication.solution_render import (
    SolutionPageLayout,
    render_solution_page,
)

_DEFAULT_PUZZLE_LAYOUT = PhysicalPageLayout()
_DEFAULT_SOLUTION_LAYOUT = SolutionPageLayout()


def render_interior_drawings(
    interior: InteriorPlan,
    *,
    puzzle_layout: PhysicalPageLayout = _DEFAULT_PUZZLE_LAYOUT,
    solution_layout: SolutionPageLayout = _DEFAULT_SOLUTION_LAYOUT,
    sudoku_style: SudokuRenderStyle | None = None,
    print_profile: PrintProfile | None = None,
) -> tuple[VectorDrawing, ...]:
    """Render an InteriorPlan with margins based on complete physical page position."""
    if not isinstance(interior, InteriorPlan):
        raise TypeError("interior must be an InteriorPlan.")
    if puzzle_layout.page_size != solution_layout.page_size:
        raise ValueError("Puzzle and solution layouts must use the same page size.")
    if puzzle_layout.puzzles_per_page != interior.page_plan.layout.puzzles_per_page:
        raise ValueError("Puzzle physical capacity must match the PagePlan capacity.")
    if (
        solution_layout.solutions_per_page
        != interior.page_plan.layout.solutions_per_page
    ):
        raise ValueError("Solution physical capacity must match the PagePlan capacity.")
    if print_profile is not None and puzzle_layout.page_size != print_profile.trim_size:
        raise ValueError("Print profile trim size must match the physical page size.")
    style = sudoku_style or SudokuRenderStyle()
    total = interior.physical_page_count
    effective = print_profile.effective_page_count(total) if print_profile else None
    clearance = style.maximum_line_width(puzzle_layout.page_size.width / 9)
    drawings: list[VectorDrawing] = []
    for physical_number, page in enumerate(interior.pages, start=1):
        margins = (
            print_profile.page_margins(
                effective, physical_number
            ).with_stroke_clearance(clearance)
            if print_profile is not None and effective is not None
            else None
        )
        if isinstance(page, (TitlePage, CopyrightPage, InstructionsPage, ContentsPage)):
            if margins is None:
                drawings.append(render_front_matter_page(page, interior.metadata))
            else:
                drawings.append(
                    render_front_matter_page(page, interior.metadata, margins=margins)
                )
        elif isinstance(page, PuzzlePage):
            drawings.append(
                render_puzzle_page(
                    page, puzzle_layout, sudoku_style=style, margins=margins
                )
            )
        elif isinstance(page, SolutionPage):
            drawings.append(
                render_solution_page(
                    page, solution_layout, sudoku_style=style, margins=margins
                )
            )
        else:
            raise TypeError(f"Unsupported interior page: {type(page).__name__}.")
    return tuple(drawings)


def render_interior_pdf(
    interior: InteriorPlan,
    *,
    puzzle_layout: PhysicalPageLayout = _DEFAULT_PUZZLE_LAYOUT,
    solution_layout: SolutionPageLayout = _DEFAULT_SOLUTION_LAYOUT,
    sudoku_style: SudokuRenderStyle | None = None,
    print_profile: PrintProfile | None = None,
) -> bytes:
    """Render a complete editorial interior and carry caller metadata into the PDF."""
    if not isinstance(interior, InteriorPlan):
        raise TypeError("interior must be an InteriorPlan.")
    return render_pdf(
        render_interior_drawings(
            interior,
            puzzle_layout=puzzle_layout,
            solution_layout=solution_layout,
            sudoku_style=sudoku_style,
            print_profile=print_profile,
        ),
        title=interior.metadata.title,
        author=interior.metadata.author,
        producer="Sudoku Gen",
    )
