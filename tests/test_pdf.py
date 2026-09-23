"""Vector PDF backend and complete book-interior export tests."""

from io import BytesIO

import pytest
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics

from sudoku_gen.difficulty import Difficulty, DifficultyReport
from sudoku_gen.fingerprint import FingerprintMode, fingerprint_puzzle
from sudoku_gen.human_solver import LogicalSolveStatus
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.publication import (
    BookPlan,
    BookPuzzle,
    BookSection,
    Line,
    PageLayoutProfile,
    PhysicalPageLayout,
    PhysicalPageSize,
    Point,
    Rect,
    SolutionPageLayout,
    Text,
    VectorDrawing,
    plan_book_pages,
    render_book_pdf,
    render_pdf,
)

SOLUTION = Grid.from_string(
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)


def make_entry(number: int) -> BookPuzzle:
    grid = Grid(
        tuple(
            value if index == number - 1 else 0
            for index, value in enumerate(SOLUTION.cells)
        )
    )
    puzzle = SudokuPuzzle(grid, SOLUTION)
    report = DifficultyReport(
        Difficulty.EASY, 0, None, 0, 0, 0, 0, LogicalSolveStatus.SOLVED
    )
    return BookPuzzle(
        number,
        puzzle,
        report,
        fingerprint_puzzle(puzzle, FingerprintMode.EXACT),
    )


def make_book(count: int) -> BookPlan:
    entries = tuple(make_entry(number) for number in range(1, count + 1))
    return BookPlan(
        (BookSection("Puzzles", Difficulty.EASY, entries),), FingerprintMode.EXACT
    )


def make_page_plan(count: int = 4, *, first_page_number: int = 7):
    return plan_book_pages(
        make_book(count),
        layout=PageLayoutProfile(2, 6, first_page_number),
    )


def pdf_reader(data: bytes) -> PdfReader:
    return PdfReader(BytesIO(data))


def test_render_pdf_creates_one_vector_page_with_metadata_and_dimensions() -> None:
    drawing = VectorDrawing(
        Rect(0, 0, 100, 200),
        (
            Line(Point(10, 20), Point(20, 30), 2, True),
            Text("Centered", Point(50, 40), 12),
        ),
    )
    reader = pdf_reader(
        render_pdf((drawing,), title="Test Book", producer="Sudoku Gen Tests")
    )

    assert len(reader.pages) == 1
    assert float(reader.pages[0].mediabox.width) == 100
    assert float(reader.pages[0].mediabox.height) == 200
    assert reader.pages[0].extract_text().strip() == "Centered"
    assert reader.metadata.title == "Test Book"
    assert reader.metadata.producer == "Sudoku Gen Tests"


def test_pdf_coordinate_transform_keeps_lines_and_text_upright_and_centered() -> None:
    drawing = VectorDrawing(
        Rect(0, 0, 100, 200),
        (
            Line(Point(10, 20), Point(20, 30), 2, True),
            Text("AB", Point(50, 40), 12),
        ),
    )
    page = pdf_reader(render_pdf((drawing,))).pages[0]
    content = page.get_contents().get_data().decode("latin-1")
    observations: list[tuple[str, list[float], float]] = []
    page.extract_text(
        visitor_text=lambda text, _cm, tm, _font, size: observations.append(
            (text, tm, size)
        )
    )
    text, matrix, size = next(item for item in observations if item[0].strip())
    ascent, descent = pdfmetrics.getAscentDescent("Helvetica", 12)

    assert "10 180 m 20 170 l S" in content
    assert text.strip() == "AB"
    assert size == 12
    assert matrix[4] == pytest.approx(
        50 - pdfmetrics.stringWidth("AB", "Helvetica", 12) / 2
    )
    assert matrix[5] == pytest.approx(160 - (ascent + descent) / 2, abs=0.001)


def test_render_pdf_supports_multiple_custom_page_sizes_without_blank_pages() -> None:
    drawings = (
        VectorDrawing(Rect(0, 0, 100, 200), (Text("First", Point(50, 50), 10),)),
        VectorDrawing(Rect(0, 0, 300, 400), (Text("Second", Point(50, 50), 10),)),
    )
    reader = pdf_reader(render_pdf(drawings))

    assert len(reader.pages) == 2
    assert tuple(float(page.mediabox.width) for page in reader.pages) == (100, 300)
    assert tuple(float(page.mediabox.height) for page in reader.pages) == (200, 400)
    assert tuple(page.extract_text().strip() for page in reader.pages) == (
        "First",
        "Second",
    )


def test_render_pdf_is_byte_deterministic_and_preserves_input() -> None:
    drawing = VectorDrawing(Rect(0, 0, 100, 100), (Text("Stable", Point(50, 50), 10),))

    first = render_pdf((drawing,))
    second = render_pdf((drawing,))

    assert first == second
    assert drawing == VectorDrawing(
        Rect(0, 0, 100, 100), (Text("Stable", Point(50, 50), 10),)
    )


def test_pdf_backend_rejects_empty_pages_and_unsupported_primitives() -> None:
    with pytest.raises(ValueError, match="at least one"):
        render_pdf(())

    drawing = VectorDrawing(Rect(0, 0, 10, 10), ())
    object.__setattr__(drawing, "primitives", (object(),))
    with pytest.raises(TypeError, match="Unsupported vector primitive"):
        render_pdf((drawing,))


def test_book_pdf_preserves_planned_order_numbering_and_spanish_text() -> None:
    plan = make_page_plan()
    reader = pdf_reader(
        render_book_pdf(plan, title="Four Sudokus", author="Test Author")
    )
    texts = tuple(page.extract_text() for page in reader.pages)

    assert len(reader.pages) == len(plan.pages) == 3
    assert "SUDOKUS" in texts[0] and "Sudoku #1" in texts[0] and "7" in texts[0]
    assert "SUDOKUS" in texts[1] and "Sudoku #3" in texts[1] and "8" in texts[1]
    assert "SOLUCIONES" in texts[2]
    assert "Solución #1" in texts[2] and "Solución #4" in texts[2]
    assert "9" in texts[2]
    assert reader.metadata.title == "Four Sudokus"
    assert reader.metadata.author == "Test Author"


def test_book_pdf_uses_configured_custom_physical_page_size() -> None:
    plan = make_page_plan(2)
    size = PhysicalPageSize(500, 700)
    data = render_book_pdf(
        plan,
        puzzle_layout=PhysicalPageLayout(page_size=size, puzzles_per_page=2),
        solution_layout=SolutionPageLayout(
            page_size=size, solutions_per_page=6, columns=2
        ),
    )

    assert all(
        float(page.mediabox.width) == 500 and float(page.mediabox.height) == 700
        for page in pdf_reader(data).pages
    )


def test_book_pdf_rejects_mismatched_physical_sizes_and_capacities() -> None:
    plan = make_page_plan()
    with pytest.raises(ValueError, match="same page size"):
        render_book_pdf(
            plan,
            solution_layout=SolutionPageLayout(
                page_size=PhysicalPageSize(500, 700), solutions_per_page=6
            ),
        )
    with pytest.raises(ValueError, match="Puzzle physical capacity"):
        render_book_pdf(plan, puzzle_layout=PhysicalPageLayout(puzzles_per_page=1))
    with pytest.raises(ValueError, match="Solution physical capacity"):
        render_book_pdf(plan, solution_layout=SolutionPageLayout(solutions_per_page=4))
