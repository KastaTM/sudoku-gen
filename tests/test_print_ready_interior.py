"""Print-safe interior rendering tests for the supported KDP paperback profile."""

from io import BytesIO

from pypdf import PdfReader

from sudoku_gen.difficulty import Difficulty, DifficultyReport
from sudoku_gen.fingerprint import FingerprintMode, fingerprint_puzzle
from sudoku_gen.human_solver import LogicalSolveStatus
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.publication import (
    PDF_FONT_NAME,
    BookPlan,
    BookPuzzle,
    BookSection,
    Line,
    PageLayoutProfile,
    PhysicalPageLayout,
    PrintProfile,
    SolutionPageLayout,
    SudokuRenderStyle,
    plan_book_pages,
    preflight_pdf,
    render_book_drawings,
    render_book_pdf,
    render_puzzle_page,
    render_solution_page,
)
from sudoku_gen.publication.pages import (
    PuzzlePage,
    PuzzlePageItem,
    SolutionPage,
    SolutionPageItem,
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
        (BookSection("Easy", Difficulty.EASY, entries),), FingerprintMode.EXACT
    )


def test_default_grid_style_is_print_safe_at_smallest_supported_page_grids() -> None:
    puzzle = PuzzlePage(1, (PuzzlePageItem(1, make_entry(1)),))
    solution = SolutionPage(2, (SolutionPageItem(1, make_entry(1)),))
    puzzle_drawing = render_puzzle_page(
        puzzle,
        PhysicalPageLayout(puzzles_per_page=2, minimum_grid_size=96),
    )
    solution_drawing = render_solution_page(
        solution,
        SolutionPageLayout(solutions_per_page=6, minimum_grid_size=120),
    )
    style = SudokuRenderStyle()

    for drawing in (puzzle_drawing, solution_drawing):
        lines = tuple(item for item in drawing.primitives if isinstance(item, Line))
        assert (
            min(line.stroke_width for line in lines) >= style.minimum_minor_line_width
        )
        assert (
            min(line.stroke_width for line in lines if line.is_major)
            >= style.minimum_major_line_width
        )
        assert all(
            major.stroke_width > minor.stroke_width
            for major in lines
            if major.is_major
            for minor in lines
            if not minor.is_major
        )


def test_print_profile_mirrors_recto_verso_margins_at_all_policy_boundaries() -> None:
    profile = PrintProfile()

    assert tuple(
        profile.inside_margin(count)
        for count in (24, 150, 151, 300, 301, 500, 501, 700, 701)
    ) == (
        27,
        27,
        36,
        36,
        45,
        45,
        54,
        54,
        63,
    )
    recto = profile.page_margins(24, 1)
    verso = profile.page_margins(24, 2)

    assert recto.is_recto and not verso.is_recto
    assert (recto.left, recto.right) == (27, 18)
    assert (verso.left, verso.right) == (18, 27)
    assert profile.effective_page_count(25) == 26


def test_complete_print_ready_interior_has_embedded_fonts_and_clean_preflight() -> None:
    profile = PrintProfile()
    plan = plan_book_pages(
        make_book(36),
        layout=PageLayoutProfile(2, 6, first_page_number=47),
    )
    drawings = render_book_drawings(plan, print_profile=profile)
    pdf = render_book_pdf(
        plan,
        print_profile=profile,
        title="Print Ready Sudokus",
    )
    reader = PdfReader(BytesIO(pdf))
    report = preflight_pdf(pdf, drawings=drawings, page_plan=plan)

    assert len(plan.pages) == len(drawings) == len(reader.pages) == 24
    assert not report.has_blocking_issues
    assert not any(issue.code == "FONT_NOT_EMBEDDED" for issue in report.issues)
    assert "Solución #1" in reader.pages[18].extract_text()
    assert all(
        float(page.mediabox.width) == 432 and float(page.mediabox.height) == 648
        for page in reader.pages
    )
    for page in reader.pages:
        fonts = page["/Resources"]["/Font"]
        assert fonts
        for font in fonts.values():
            descriptor = font.get_object()["/FontDescriptor"].get_object()
            assert any(
                key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3")
            )

    first_header_x = next(
        text.position.x
        for text in drawings[0].primitives
        if getattr(text, "content", None) == "SUDOKUS"
    )
    second_header_x = next(
        text.position.x
        for text in drawings[1].primitives
        if getattr(text, "content", None) == "SUDOKUS"
    )
    assert first_header_x > second_header_x
    assert PDF_FONT_NAME
