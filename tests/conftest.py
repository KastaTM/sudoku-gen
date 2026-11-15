"""Shared fixtures: one real publication run reused by several test modules."""

import pytest

from sudoku_gen.difficulty import Difficulty
from sudoku_gen.pattern import Symmetry
from sudoku_gen.publication import (
    ES_ES,
    BookLocale,
    CoverContent,
    FrontMatterConfig,
    PageLayoutProfile,
    PublicationJob,
    PublicationMetadata,
    PublicationResult,
    PublicationSectionSpec,
    run_publication,
)


def small_job(locale: BookLocale = ES_ES) -> PublicationJob:
    """A real 36-puzzle, 28-page Spanish job (about 7 seconds to generate)."""
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


@pytest.fixture(scope="session")
def reference_result() -> PublicationResult:
    return run_publication(small_job())
