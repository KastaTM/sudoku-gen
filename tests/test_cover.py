"""Focused deterministic paperback-cover tests."""

from io import BytesIO

import pytest
from pypdf import PdfReader

from sudoku_gen.publication import (
    CoverContent,
    PublicationMetadata,
    cover_geometry,
    plan_cover,
    render_cover_pdf,
    validate_cover_pdf,
)


def metadata() -> PublicationMetadata:
    return PublicationMetadata(
        "Sudokus en español", subtitle="Práctica", author="Autora"
    )


def test_twenty_eight_page_cover_geometry_uses_current_formula() -> None:
    geometry = cover_geometry(28)

    assert geometry.effective_page_count == 28
    assert geometry.canvas.width / 72 == pytest.approx(12.313056)
    assert geometry.canvas.height / 72 == pytest.approx(9.25)
    assert geometry.back_trim.right == geometry.spine.left
    assert geometry.spine.right == geometry.front_trim.left
    assert geometry.barcode_exclusion.width == 144


def test_odd_counts_and_spine_text_limits_are_explicit() -> None:
    assert cover_geometry(27).effective_page_count == 28
    with pytest.raises(ValueError, match="80"):
        plan_cover(28, metadata(), content=CoverContent(spine_text="Título"))
    assert plan_cover(300, metadata(), content=CoverContent(spine_text="Título"))


def test_cover_pdf_is_single_page_embedded_font_and_deterministic() -> None:
    plan = plan_cover(
        28, metadata(), content=CoverContent(back_cover_copy="Texto breve.")
    )
    first = render_cover_pdf(plan)
    second = render_cover_pdf(plan)
    reader = PdfReader(BytesIO(first))

    assert first == second
    assert len(reader.pages) == 1
    assert float(reader.pages[0].mediabox.width) == pytest.approx(
        plan.geometry.canvas.width
    )
    assert "español" in reader.pages[0].extract_text()
    assert not validate_cover_pdf(first, plan).has_blocking_issues
