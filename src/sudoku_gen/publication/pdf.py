"""Vector PDF backend and complete PagePlan book-interior export."""

from collections.abc import Iterable
from io import BytesIO

from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfgen import canvas as reportlab_canvas  # type: ignore[import-untyped]

from sudoku_gen.publication.page_render import (
    PhysicalPageLayout,
    render_puzzle_page,
)
from sudoku_gen.publication.pages import PagePlan, PuzzlePage, SolutionPage
from sudoku_gen.publication.render import (
    Line,
    SudokuRenderStyle,
    Text,
    VectorDrawing,
)
from sudoku_gen.publication.solution_render import (
    SolutionPageLayout,
    render_solution_page,
)

_PDF_FONT = "Helvetica"
_DEFAULT_PUZZLE_LAYOUT = PhysicalPageLayout()
_DEFAULT_SOLUTION_LAYOUT = SolutionPageLayout()


def _validate_metadata(value: str | None, name: str, *, optional: bool) -> None:
    if value is None and optional:
        return
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string{' or None' if optional else ''}.")
    if not value.strip():
        raise ValueError(f"{name} must not be empty or whitespace.")


def _pdf_x(drawing: VectorDrawing, x: float) -> float:
    return x - drawing.bounds.left


def _pdf_y(drawing: VectorDrawing, y: float) -> float:
    return drawing.bounds.bottom - y


def _draw_line(pdf_canvas: object, drawing: VectorDrawing, line: Line) -> None:
    pdf_canvas.setStrokeColorRGB(0, 0, 0)  # type: ignore[attr-defined]
    pdf_canvas.setLineWidth(line.stroke_width)  # type: ignore[attr-defined]
    pdf_canvas.line(  # type: ignore[attr-defined]
        _pdf_x(drawing, line.start.x),
        _pdf_y(drawing, line.start.y),
        _pdf_x(drawing, line.end.x),
        _pdf_y(drawing, line.end.y),
    )


def _draw_text(pdf_canvas: object, drawing: VectorDrawing, text: Text) -> None:
    pdf_canvas.setFillColorRGB(0, 0, 0)  # type: ignore[attr-defined]
    pdf_canvas.setFont(_PDF_FONT, text.font_size)  # type: ignore[attr-defined]
    ascent, descent = pdfmetrics.getAscentDescent(_PDF_FONT, text.font_size)
    baseline = _pdf_y(drawing, text.position.y) - (ascent + descent) / 2
    pdf_canvas.drawCentredString(  # type: ignore[attr-defined]
        _pdf_x(drawing, text.position.x), baseline, text.content
    )


def render_pdf(
    drawings: Iterable[VectorDrawing],
    *,
    title: str = "Sudoku Gen",
    producer: str = "Sudoku Gen",
    author: str | None = None,
) -> bytes:
    """Render ordered backend-neutral vector pages directly to PDF bytes."""
    _validate_metadata(title, "title", optional=False)
    _validate_metadata(producer, "producer", optional=False)
    _validate_metadata(author, "author", optional=True)
    pages = tuple(drawings)
    if not pages:
        raise ValueError("drawings must contain at least one VectorDrawing.")
    if not all(isinstance(drawing, VectorDrawing) for drawing in pages):
        raise TypeError("drawings must contain only VectorDrawing instances.")

    buffer = BytesIO()
    first = pages[0].bounds
    pdf_canvas = reportlab_canvas.Canvas(
        buffer,
        pagesize=(first.width, first.height),
        bottomup=1,
        pageCompression=0,
        invariant=1,
    )
    pdf_canvas.setTitle(title)
    pdf_canvas.setProducer(producer)
    if author is not None:
        pdf_canvas.setAuthor(author)
    for drawing in pages:
        pdf_canvas.setPageSize((drawing.bounds.width, drawing.bounds.height))
        for primitive in drawing.primitives:
            if isinstance(primitive, Line):
                _draw_line(pdf_canvas, drawing, primitive)
            elif isinstance(primitive, Text):
                _draw_text(pdf_canvas, drawing, primitive)
            else:
                raise TypeError(
                    f"Unsupported vector primitive: {type(primitive).__name__}."
                )
        pdf_canvas.showPage()
    pdf_canvas.save()
    return buffer.getvalue()


def render_book_pdf(
    page_plan: PagePlan,
    *,
    puzzle_layout: PhysicalPageLayout = _DEFAULT_PUZZLE_LAYOUT,
    solution_layout: SolutionPageLayout = _DEFAULT_SOLUTION_LAYOUT,
    sudoku_style: SudokuRenderStyle | None = None,
    title: str = "Sudoku Gen",
    author: str | None = None,
) -> bytes:
    """Render every planned puzzle and solution page in exact PagePlan order."""
    if not isinstance(page_plan, PagePlan):
        raise TypeError("page_plan must be a PagePlan.")
    if not isinstance(puzzle_layout, PhysicalPageLayout):
        raise TypeError("puzzle_layout must be a PhysicalPageLayout.")
    if not isinstance(solution_layout, SolutionPageLayout):
        raise TypeError("solution_layout must be a SolutionPageLayout.")
    if sudoku_style is not None and not isinstance(sudoku_style, SudokuRenderStyle):
        raise TypeError("sudoku_style must be a SudokuRenderStyle or None.")
    if puzzle_layout.page_size != solution_layout.page_size:
        raise ValueError("Puzzle and solution layouts must use the same page size.")
    if puzzle_layout.puzzles_per_page != page_plan.layout.puzzles_per_page:
        raise ValueError("Puzzle physical capacity must match the PagePlan capacity.")
    if solution_layout.solutions_per_page != page_plan.layout.solutions_per_page:
        raise ValueError("Solution physical capacity must match the PagePlan capacity.")

    drawings: list[VectorDrawing] = []
    for page in page_plan.pages:
        if isinstance(page, PuzzlePage):
            drawings.append(
                render_puzzle_page(
                    page,
                    puzzle_layout,
                    sudoku_style=sudoku_style,
                )
            )
        elif isinstance(page, SolutionPage):
            drawings.append(
                render_solution_page(
                    page,
                    solution_layout,
                    sudoku_style=sudoku_style,
                )
            )
        else:
            raise TypeError(f"Unsupported planned page: {type(page).__name__}.")
    return render_pdf(drawings, title=title, author=author, producer="Sudoku Gen")
