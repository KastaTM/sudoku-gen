"""Editorial front-matter and complete-interior integration tests."""

from dataclasses import FrozenInstanceError
from io import BytesIO

import pytest
from pypdf import PdfReader

from sudoku_gen.difficulty import Difficulty, DifficultyReport
from sudoku_gen.fingerprint import FingerprintMode, fingerprint_puzzle
from sudoku_gen.human_solver import LogicalSolveStatus
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.publication import (
    BookPlan,
    BookPuzzle,
    BookSection,
    ContentsPage,
    CopyrightPage,
    FrontMatterConfig,
    InstructionsPage,
    PageLayoutProfile,
    PrintProfile,
    PublicationMetadata,
    TitlePage,
    plan_book_pages,
    plan_interior,
    preflight_pdf,
    render_interior_drawings,
    render_interior_pdf,
)

SOLUTION = Grid.from_string(
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)


def entry(number: int) -> BookPuzzle:
    puzzle = SudokuPuzzle(
        Grid(
            tuple(
                value if index == number - 1 else 0
                for index, value in enumerate(SOLUTION.cells)
            )
        ),
        SOLUTION,
    )
    report = DifficultyReport(
        Difficulty.EASY, 0, None, 0, 0, 0, 0, LogicalSolveStatus.SOLVED
    )
    return BookPuzzle(
        number, puzzle, report, fingerprint_puzzle(puzzle, FingerprintMode.EXACT)
    )


def pages(count: int = 36):
    book = BookPlan(
        (
            BookSection(
                "Fácil", Difficulty.EASY, tuple(entry(i) for i in range(1, count + 1))
            ),
        ),
        FingerprintMode.EXACT,
    )
    return plan_book_pages(book, layout=PageLayoutProfile(2, 6, 11))


def metadata() -> PublicationMetadata:
    return PublicationMetadata(
        "Sudokus de prueba",
        subtitle="Edición práctica",
        author="Autora",
        copyright_notice="© 2026 Autora",
        instructions=(
            "Completa cada cuadrícula usando los dígitos del uno al nueve.\n\n"
            "No repitas un dígito en una fila, columna o caja."
        ),
    )


def test_metadata_and_config_validate_content_and_are_immutable() -> None:
    with pytest.raises(ValueError):
        PublicationMetadata(" ")
    with pytest.raises(ValueError):
        PublicationMetadata("Title", author=" ")
    with pytest.raises(TypeError):
        FrontMatterConfig(include_title_page=1)  # type: ignore[arg-type]
    item = metadata()
    with pytest.raises(FrozenInstanceError):
        item.title = "Changed"  # type: ignore[misc]


def test_planning_orders_front_matter_without_renumbering_editorial_pages() -> None:
    plan = pages(4)
    interior = plan_interior(
        metadata(),
        plan,
        config=FrontMatterConfig(True, True, True, True),
    )

    assert tuple(type(page) for page in interior.front_matter) == (
        TitlePage,
        CopyrightPage,
        InstructionsPage,
        ContentsPage,
    )
    assert interior.physical_page_count == len(plan.pages) + 4
    assert interior.pages[4:] == plan.pages
    assert interior.front_matter[-1].entries[0].editorial_page_number == 11
    with pytest.raises(ValueError, match="copyright"):
        plan_interior(
            PublicationMetadata("Title"), plan, config=FrontMatterConfig(False, True)
        )
    with pytest.raises(ValueError, match="instructions"):
        plan_interior(
            PublicationMetadata("Title"),
            plan,
            config=FrontMatterConfig(False, False, True),
        )


def test_complete_interior_embeds_metadata_and_passes_print_preflight() -> None:
    interior = plan_interior(
        metadata(), pages(), config=FrontMatterConfig(True, True, True, True)
    )
    profile = PrintProfile()
    drawings = render_interior_drawings(interior, print_profile=profile)
    pdf = render_interior_pdf(interior, print_profile=profile)
    reader = PdfReader(BytesIO(pdf))
    report = preflight_pdf(pdf, drawings=drawings, interior_plan=interior)

    assert len(reader.pages) == interior.physical_page_count == 28
    assert reader.metadata.title == "Sudokus de prueba"
    assert reader.metadata.author == "Autora"
    assert "Instrucciones" in reader.pages[2].extract_text()
    assert not report.has_blocking_issues and not report.issues
    assert drawings[0].primitives[0].position.x > drawings[1].primitives[0].position.x
