"""Create the controlled Phase 2.8 KDP print-readiness preview PDF."""

from pathlib import Path

from sudoku_gen.difficulty import Difficulty, DifficultyReport
from sudoku_gen.fingerprint import FingerprintMode, fingerprint_puzzle
from sudoku_gen.human_solver import LogicalSolveStatus
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.publication import (
    BookPlan,
    BookPuzzle,
    BookSection,
    PageLayoutProfile,
    PrintProfile,
    plan_book_pages,
    preflight_pdf,
    render_book_drawings,
    render_book_pdf,
)

_SOLUTION = Grid.from_string(
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)


def _entry(number: int) -> BookPuzzle:
    grid = Grid(
        tuple(
            value if index == number - 1 else 0
            for index, value in enumerate(_SOLUTION.cells)
        )
    )
    puzzle = SudokuPuzzle(grid, _SOLUTION)
    report = DifficultyReport(
        Difficulty.EASY, 0, None, 0, 0, 0, 0, LogicalSolveStatus.SOLVED
    )
    return BookPuzzle(
        number,
        puzzle,
        report,
        fingerprint_puzzle(puzzle, FingerprintMode.EXACT),
    )


def build_preview() -> tuple[bytes, int]:
    """Build and independently preflight a 24-page controlled paperback interior."""
    entries = tuple(_entry(number) for number in range(1, 37))
    book = BookPlan(
        (BookSection("Easy", Difficulty.EASY, entries),), FingerprintMode.EXACT
    )
    page_plan = plan_book_pages(
        book,
        layout=PageLayoutProfile(
            puzzles_per_page=2,
            solutions_per_page=6,
            first_page_number=1,
        ),
    )
    profile = PrintProfile()
    drawings = render_book_drawings(page_plan, print_profile=profile)
    pdf = render_book_pdf(
        page_plan,
        print_profile=profile,
        title="Sudoku Gen Phase 2.8 Print Preview",
    )
    report = preflight_pdf(pdf, drawings=drawings, page_plan=page_plan)
    if report.has_blocking_issues:
        details = ", ".join(issue.code for issue in report.issues)
        raise RuntimeError(f"Print preflight failed: {details}")
    return pdf, len(page_plan.pages)


if __name__ == "__main__":
    output = Path("dev-output/phase-2.8-print-ready-preview.pdf")
    output.parent.mkdir(exist_ok=True)
    contents, page_count = build_preview()
    output.write_bytes(contents)
    print(f"Wrote {output} ({page_count} pages).")
