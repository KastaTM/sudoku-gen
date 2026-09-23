"""Restrained vector rendering for one planned editorial front-matter page."""

from textwrap import wrap

from sudoku_gen.publication.geometry import PhysicalPageSize, Point, Rect
from sudoku_gen.publication.interior import (
    ContentsPage,
    CopyrightPage,
    FrontMatterPage,
    InstructionsPage,
    PublicationMetadata,
    TitlePage,
)
from sudoku_gen.publication.preflight import PageMargins
from sudoku_gen.publication.render import Text, VectorDrawing

_PAGE_SIZE = PhysicalPageSize.six_by_nine_inches()
_DEFAULT_MARGINS = PageMargins(36, 36, 24, 24, True)


def _usable_rect(margins: PageMargins) -> Rect:
    return Rect(
        margins.left,
        margins.top,
        _PAGE_SIZE.width - margins.left - margins.right,
        _PAGE_SIZE.height - margins.top - margins.bottom,
    )


def _wrapped_lines(text: str, *, width: int = 48) -> tuple[str, ...]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [text]:
        if not paragraph.strip():
            lines.append("")
        else:
            lines.extend(wrap(paragraph, width=width, break_long_words=False))
    return tuple(lines)


def _body_text(content: str, rect: Rect, *, heading: str) -> tuple[Text, ...]:
    lines = _wrapped_lines(content)
    line_height = 14.0
    if len(lines) > 30:
        raise ValueError("Editorial text does not fit on one front-matter page.")
    start = rect.top + 72.0
    if start + 24.0 + len(lines) * line_height > rect.bottom:
        raise ValueError("Editorial text does not fit inside the printable page area.")
    result = [Text(heading, Point(rect.center.x, rect.top + 24), 16)]
    result.extend(
        Text(line, Point(rect.center.x, start + index * line_height), 9)
        for index, line in enumerate(lines)
        if line
    )
    return tuple(result)


def render_front_matter_page(
    page: FrontMatterPage,
    metadata: PublicationMetadata,
    *,
    margins: PageMargins = _DEFAULT_MARGINS,
) -> VectorDrawing:
    """Render an explicit front-matter page with no inferred editorial content."""
    if not isinstance(page, (TitlePage, CopyrightPage, InstructionsPage, ContentsPage)):
        raise TypeError("page must be a front-matter page.")
    if not isinstance(metadata, PublicationMetadata):
        raise TypeError("metadata must be a PublicationMetadata.")
    if not isinstance(margins, PageMargins):
        raise TypeError("margins must be a PageMargins.")
    rect = _usable_rect(margins)
    if rect.width <= 0 or rect.height <= 0:
        raise ValueError("Margins leave no drawable front-matter area.")
    if isinstance(page, TitlePage):
        texts = [Text(metadata.title, Point(rect.center.x, rect.center.y - 36), 24)]
        if metadata.subtitle is not None:
            texts.append(
                Text(metadata.subtitle, Point(rect.center.x, rect.center.y), 14)
            )
        if metadata.author is not None:
            texts.append(
                Text(metadata.author, Point(rect.center.x, rect.center.y + 48), 12)
            )
    elif isinstance(page, CopyrightPage):
        if metadata.copyright_notice is None:
            raise ValueError("A copyright page requires copyright_notice content.")
        texts = list(_body_text(metadata.copyright_notice, rect, heading="Información"))
    elif isinstance(page, InstructionsPage):
        if metadata.instructions is None:
            raise ValueError("An instructions page requires instructions content.")
        texts = list(_body_text(metadata.instructions, rect, heading="Instrucciones"))
    else:
        if len(page.entries) > 24:
            raise ValueError("Table of contents does not fit on one page.")
        texts = [Text("Contenido", Point(rect.center.x, rect.top + 24), 16)]
        texts.extend(
            Text(
                f"{entry.title}  {entry.editorial_page_number}",
                Point(rect.center.x, rect.top + 72 + index * 16),
                10,
            )
            for index, entry in enumerate(page.entries)
        )
    return VectorDrawing(Rect(0, 0, _PAGE_SIZE.width, _PAGE_SIZE.height), tuple(texts))
