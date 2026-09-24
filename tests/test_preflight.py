"""KDP paperback PDF preflight tests with controlled vector/PDF fixtures."""

from dataclasses import FrozenInstanceError
from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject

from sudoku_gen.publication import (
    Line,
    Point,
    PreflightIssue,
    PreflightReport,
    PreflightSeverity,
    PrintProfile,
    Rect,
    Text,
    VectorDrawing,
    preflight_pdf,
    render_pdf,
)


def safe_drawing() -> VectorDrawing:
    return VectorDrawing(
        Rect(0, 0, 432, 648),
        (
            Line(Point(40, 40), Point(100, 40), 1, False),
            Text("Safe", Point(100, 100), 8),
        ),
    )


def pdf_with_pages(drawings: tuple[VectorDrawing, ...]) -> bytes:
    return render_pdf(drawings)


def test_supported_profile_has_published_inside_margin_bands() -> None:
    profile = PrintProfile()

    assert profile.inside_margin(24) == 27
    assert profile.inside_margin(151) == 36
    assert profile.inside_margin(301) == 45
    assert profile.inside_margin(501) == 54
    assert profile.inside_margin(701) == 63


def test_valid_even_length_controlled_pdf_has_no_blocking_issues() -> None:
    drawings = (safe_drawing(),) * 24
    report = preflight_pdf(pdf_with_pages(drawings), drawings=drawings)

    assert report.actual_page_count == 24
    assert report.effective_page_count == 24
    assert not report.has_blocking_issues
    assert all(issue.code != "PAGE_COUNT" for issue in report.issues)
    assert not any(issue.code == "FONT_NOT_EMBEDDED" for issue in report.issues)


def test_unreadable_and_encrypted_pdfs_produce_blocking_diagnostics() -> None:
    unreadable = preflight_pdf(b"not a PDF")
    writer = PdfWriter()
    writer.add_blank_page(432, 648)
    writer.encrypt("secret")
    encrypted_buffer = BytesIO()
    writer.write(encrypted_buffer)
    encrypted = preflight_pdf(encrypted_buffer.getvalue())

    assert unreadable.issues[0].code == "PDF_UNREADABLE"
    assert encrypted.issues[0].code == "PDF_ENCRYPTED"
    assert unreadable.has_blocking_issues and encrypted.has_blocking_issues


def test_page_size_odd_count_and_blank_page_diagnostics_are_reported() -> None:
    drawing = VectorDrawing(Rect(0, 0, 400, 600), (Text("Wrong", Point(100, 100), 8),))
    report = preflight_pdf(render_pdf((drawing,)))

    assert report.actual_page_count == 1
    assert report.effective_page_count == 2
    assert {issue.code for issue in report.issues} >= {
        "PAGE_COUNT",
        "ODD_PAGE_COUNT",
        "PAGE_SIZE",
        "DRAWING_GEOMETRY_REQUIRED",
    }


def test_vector_geometry_detects_stroke_text_and_safe_area_failures() -> None:
    drawing = VectorDrawing(
        Rect(0, 0, 432, 648),
        (
            Line(Point(10, 40), Point(100, 40), 0.5, False),
            Text("Tiny", Point(20, 20), 6),
        ),
    )
    report = preflight_pdf(render_pdf((drawing,)), drawings=(drawing,))

    assert {issue.code for issue in report.issues} >= {
        "LINE_WIDTH",
        "TEXT_SIZE",
        "CONTENT_SAFE_AREA",
    }


def test_recto_verso_inside_margin_is_checked_on_opposite_sides() -> None:
    first = safe_drawing()
    second = VectorDrawing(
        Rect(0, 0, 432, 648),
        (Line(Point(410, 40), Point(410, 100), 1, False),),
    )
    report = preflight_pdf(render_pdf((first, second)), drawings=(first, second))

    assert any(
        issue.code == "CONTENT_SAFE_AREA" and issue.page_number == 2
        for issue in report.issues
    )


def test_annotations_and_report_ordering_are_deterministic() -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(432, 648)
    page[NameObject("/Annots")] = ArrayObject((DictionaryObject(),))
    buffer = BytesIO()
    writer.write(buffer)
    report = preflight_pdf(buffer.getvalue())

    assert any(issue.code == "ANNOTATIONS" for issue in report.issues)
    first = PreflightIssue("Z", PreflightSeverity.WARNING, "z", 2)
    second = PreflightIssue("A", PreflightSeverity.ERROR, "a", 1)
    ordered = PreflightReport(PrintProfile(), 2, 2, (first, second))
    assert ordered.issues == (second, first)
    with pytest.raises(FrozenInstanceError):
        ordered.issues = ()  # type: ignore[misc]
