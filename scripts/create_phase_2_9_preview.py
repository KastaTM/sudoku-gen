"""Create the controlled Phase 2.9 editorial paperback preview and SVG pages."""

from pathlib import Path

from sudoku_gen.difficulty import Difficulty, DifficultyReport
from sudoku_gen.fingerprint import FingerprintMode, fingerprint_puzzle
from sudoku_gen.human_solver import LogicalSolveStatus
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.publication import (
    BookPlan,
    BookPuzzle,
    BookSection,
    FrontMatterConfig,
    PageLayoutProfile,
    PrintProfile,
    PublicationMetadata,
    plan_book_pages,
    plan_interior,
    preflight_pdf,
    render_interior_drawings,
    render_interior_pdf,
    render_svg,
)

_SOLUTION = Grid.from_string(
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)


def _entry(number: int) -> BookPuzzle:
    puzzle = SudokuPuzzle(
        Grid(
            tuple(
                value if index == number - 1 else 0
                for index, value in enumerate(_SOLUTION.cells)
            )
        ),
        _SOLUTION,
    )
    report = DifficultyReport(
        Difficulty.EASY, 0, None, 0, 0, 0, 0, LogicalSolveStatus.SOLVED
    )
    return BookPuzzle(
        number,
        puzzle,
        report,
        fingerprint_puzzle(puzzle, FingerprintMode.EXACT),
    )


def build_preview() -> tuple[bytes, tuple[str, ...], int]:
    """Build a preflight-clean 28-page interior and visual page previews."""
    entries = tuple(_entry(number) for number in range(1, 37))
    book = BookPlan(
        (BookSection("Fácil", Difficulty.EASY, entries),), FingerprintMode.EXACT
    )
    pages = plan_book_pages(book, layout=PageLayoutProfile(2, 6, 1))
    metadata = PublicationMetadata(
        "Sudokus de ejemplo",
        subtitle="Edición de práctica",
        author="Sudoku Gen",
        copyright_notice="© 2026 Sudoku Gen",
        instructions=(
            "Completa cada cuadrícula usando los dígitos del uno al nueve.\n\n"
            "No repitas un dígito en una fila, columna o caja."
        ),
    )
    interior = plan_interior(
        metadata,
        pages,
        config=FrontMatterConfig(True, True, True, True),
    )
    profile = PrintProfile()
    drawings = render_interior_drawings(interior, print_profile=profile)
    pdf = render_interior_pdf(interior, print_profile=profile)
    report = preflight_pdf(pdf, drawings=drawings, interior_plan=interior)
    if report.has_blocking_issues:
        details = ", ".join(issue.code for issue in report.issues)
        raise RuntimeError(f"Print preflight failed: {details}")
    return pdf, tuple(render_svg(drawing) for drawing in drawings[:5]), len(drawings)


if __name__ == "__main__":
    output = Path("dev-output")
    output.mkdir(exist_ok=True)
    pdf, previews, page_count = build_preview()
    (output / "phase-2.9-editorial-preview.pdf").write_bytes(pdf)
    for number, preview in enumerate(previews, start=1):
        (output / f"phase-2.9-preview-page-{number}.svg").write_text(
            preview, encoding="utf-8"
        )
    print(f"Wrote Phase 2.9 preview ({page_count} pages).")
