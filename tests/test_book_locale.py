"""BookLocale resources and the absence of mixed-language text in a book."""

from dataclasses import replace
from io import BytesIO

import pytest
from pypdf import PdfReader

from sudoku_gen.difficulty import Difficulty
from sudoku_gen.pattern import Symmetry
from sudoku_gen.publication import (
    EN_US,
    ES_ES,
    BookLocale,
    CoverContent,
    FrontMatterConfig,
    PageLayoutProfile,
    PublicationJob,
    PublicationMetadata,
    PublicationResult,
    PublicationSectionSpec,
    UnknownLocaleError,
    available_book_locales,
    get_book_locale,
    render_interior_pdf,
    run_publication,
)

ENGLISH_WORDS = ("Easy", "Medium", "Hard", "Expert", "Solution", "Contents")


def test_registry_lookup_and_unknown_locale_does_not_fall_back() -> None:
    assert get_book_locale("es-ES") is ES_ES
    assert available_book_locales() == ("en-US", "es-ES")
    with pytest.raises(UnknownLocaleError):
        get_book_locale("fr-FR")
    with pytest.raises(UnknownLocaleError):
        get_book_locale(None)  # type: ignore[arg-type]


def test_every_publishable_difficulty_has_a_label_and_unrated_does_not() -> None:
    for locale in (ES_ES, EN_US):
        for difficulty in (
            Difficulty.EASY,
            Difficulty.MEDIUM,
            Difficulty.HARD,
            Difficulty.EXPERT,
        ):
            assert locale.difficulty_label(difficulty)
        with pytest.raises(ValueError):
            locale.difficulty_label(Difficulty.UNRATED)


def test_incomplete_locale_cannot_be_constructed() -> None:
    with pytest.raises(ValueError):
        replace(ES_ES, difficulty_labels=ES_ES.difficulty_labels[:3])
    with pytest.raises(ValueError):
        replace(ES_ES, puzzle_title="Sudoku")
    with pytest.raises(ValueError):
        replace(ES_ES, puzzle_title="Sudoku #{number} {extra}")
    with pytest.raises(ValueError):
        replace(ES_ES, contents_heading=" ")
    with pytest.raises(ValueError):
        replace(ES_ES, code="spanish")


def test_labels_format_numbers() -> None:
    assert ES_ES.puzzle_label(7) == "Sudoku #7"
    assert ES_ES.solution_label(7) == "Solución #7"
    assert isinstance(ES_ES, BookLocale)


def _small_job(locale: BookLocale) -> PublicationJob:
    return PublicationJob(
        metadata=PublicationMetadata(
            "Libro de prueba",
            author="Sudoku Gen",
            copyright_notice="Aviso",
            instructions="Completa cada cuadrícula.",
        ),
        sections=(PublicationSectionSpec("Fácil", Difficulty.EASY, 36),),
        seed=202611,
        front_matter=FrontMatterConfig(True, True, True, True),
        symmetry=Symmetry.ROTATIONAL_180,
        page_layout=PageLayoutProfile(2, 6, 1),
        cover_content=CoverContent(back_cover_copy="Texto"),
        locale=locale,
    )


@pytest.fixture(scope="module")
def spanish_result() -> PublicationResult:
    return run_publication(_small_job(ES_ES))


def _text(pdf: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)


def test_spanish_book_contains_no_english_editorial_text(
    spanish_result: PublicationResult,
) -> None:
    text = _text(spanish_result.interior_pdf)

    for word in ("SUDOKUS", "SOLUCIONES", "Fácil", "Contenido", "Instrucciones"):
        assert word in text
    for word in ENGLISH_WORDS:
        assert word not in text


def test_test_locale_changes_only_editorial_text(
    spanish_result: PublicationResult,
) -> None:
    english_pdf = render_interior_pdf(
        spanish_result.interior_plan,
        print_profile=spanish_result.job.print_profile,
        locale=EN_US,
    )
    english_text = _text(english_pdf)

    assert "SOLUTIONS" in english_text and "Contents" in english_text
    assert "Easy" in english_text
    assert "SOLUCIONES" not in english_text
    assert english_pdf != spanish_result.interior_pdf
