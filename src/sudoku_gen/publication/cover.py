"""Deterministic single-page paperback-cover planning, rendering, and validation."""

from dataclasses import dataclass
from io import BytesIO
from textwrap import wrap

from pypdf import PdfReader

from sudoku_gen.publication.geometry import Point, Rect
from sudoku_gen.publication.interior import PublicationMetadata
from sudoku_gen.publication.pdf import render_pdf
from sudoku_gen.publication.preflight import PrintProfile
from sudoku_gen.publication.render import Line, Text, VectorDrawing

_BLEED = 9.0
_SPINE_INCHES_PER_PAGE = 0.002252
_MIN_SPINE_PAGES = 80
_MIN_TEXT_SIZE = 7.0


@dataclass(frozen=True, slots=True)
class CoverContent:
    """Optional caller-authored back-cover and spine content."""

    back_cover_copy: str | None = None
    spine_text: str | None = None

    def __post_init__(self) -> None:
        for name in ("back_cover_copy", "spine_text"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a nonempty string or None.")


@dataclass(frozen=True, slots=True)
class CoverStyle:
    """Restrained black-and-white cover typography and motif sizing."""

    title_size: float = 26.0
    subtitle_size: float = 14.0
    author_size: float = 12.0
    body_size: float = 9.0
    spine_size: float = 7.0

    def __post_init__(self) -> None:
        for name in (
            "title_size",
            "subtitle_size",
            "author_size",
            "body_size",
            "spine_size",
        ):
            value = getattr(self, name)
            if type(value) not in (int, float) or isinstance(value, bool):
                raise TypeError(f"{name} must be a built-in positive number.")
            if value < _MIN_TEXT_SIZE:
                raise ValueError(f"{name} must be at least {_MIN_TEXT_SIZE} points.")
            object.__setattr__(self, name, float(value))


_DEFAULT_CONTENT = CoverContent()
_DEFAULT_PROFILE = PrintProfile()
_DEFAULT_STYLE = CoverStyle()


@dataclass(frozen=True, slots=True)
class CoverGeometry:
    """Top-left physical regions for a continuous left-to-right paperback cover."""

    canvas: Rect
    back_trim: Rect
    spine: Rect
    front_trim: Rect
    back_safe: Rect
    front_safe: Rect
    barcode_exclusion: Rect
    effective_page_count: int

    @property
    def spine_width_inches(self) -> float:
        return self.spine.width / 72.0


@dataclass(frozen=True, slots=True)
class CoverPlan:
    """A finalized cover references metadata and exact geometry, not book content."""

    metadata: PublicationMetadata
    content: CoverContent
    geometry: CoverGeometry


@dataclass(frozen=True, slots=True)
class CoverIssue:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class CoverReport:
    issues: tuple[CoverIssue, ...]

    @property
    def has_blocking_issues(self) -> bool:
        return bool(self.issues)


def cover_geometry(
    page_count: int, profile: PrintProfile = _DEFAULT_PROFILE
) -> CoverGeometry:
    """Calculate KDP's supported white-paper black-and-white cover dimensions."""
    if type(page_count) is not int or page_count < 1:
        raise ValueError("page_count must be a positive built-in integer.")
    if not isinstance(profile, PrintProfile):
        raise TypeError("profile must be a PrintProfile.")
    effective = profile.effective_page_count(page_count)
    trim = profile.trim_size
    spine = effective * _SPINE_INCHES_PER_PAGE * 72.0
    width = trim.width * 2 + spine + _BLEED * 2
    height = trim.height + _BLEED * 2
    canvas = Rect(0, 0, width, height)
    back = Rect(_BLEED, _BLEED, trim.width, trim.height)
    spine_rect = Rect(back.right, _BLEED, spine, trim.height)
    front = Rect(spine_rect.right, _BLEED, trim.width, trim.height)
    safe_inset = 18.0
    back_safe = Rect(
        back.left + safe_inset, back.top + safe_inset, back.width - 36, back.height - 36
    )
    front_safe = Rect(
        front.left + safe_inset,
        front.top + safe_inset,
        front.width - 36,
        front.height - 36,
    )
    barcode = Rect(back.right - 18 - 144, back.bottom - 18 - 86.4, 144, 86.4)
    return CoverGeometry(
        canvas, back, spine_rect, front, back_safe, front_safe, barcode, effective
    )


def plan_cover(
    page_count: int,
    metadata: PublicationMetadata,
    *,
    content: CoverContent = _DEFAULT_CONTENT,
    profile: PrintProfile = _DEFAULT_PROFILE,
    style: CoverStyle = _DEFAULT_STYLE,
) -> CoverPlan:
    """Plan a cover from an explicit final interior count for focused callers/tests."""
    if not isinstance(metadata, PublicationMetadata):
        raise TypeError("metadata must be a PublicationMetadata.")
    if not isinstance(content, CoverContent) or not isinstance(style, CoverStyle):
        raise TypeError("content and style must be CoverContent and CoverStyle.")
    geometry = cover_geometry(page_count, profile)
    if len(wrap(metadata.title, 28, break_long_words=False)) > 3:
        raise ValueError("title does not fit the supported front-cover template.")
    if content.spine_text is not None:
        if geometry.effective_page_count < _MIN_SPINE_PAGES:
            raise ValueError("spine text requires at least 80 effective pages.")
        if geometry.spine.width < style.spine_size + 6:
            raise ValueError("spine text does not fit the measured spine width.")
    return CoverPlan(metadata, content, geometry)


def plan_paperback_cover(
    interior_pdf: bytes,
    metadata: PublicationMetadata,
    *,
    content: CoverContent = _DEFAULT_CONTENT,
    print_profile: PrintProfile = _DEFAULT_PROFILE,
    style: CoverStyle = _DEFAULT_STYLE,
) -> CoverPlan:
    """Inspect a finalized interior PDF before calculating its matching cover."""
    if not isinstance(interior_pdf, bytes):
        raise TypeError("interior_pdf must be bytes.")
    reader = PdfReader(BytesIO(interior_pdf))
    if reader.is_encrypted or not reader.pages:
        raise ValueError("interior_pdf must be a readable, unencrypted PDF with pages.")
    for page in reader.pages:
        if (float(page.mediabox.width), float(page.mediabox.height)) != (
            print_profile.trim_size.width,
            print_profile.trim_size.height,
        ):
            raise ValueError(
                "interior_pdf pages must match the supported trim dimensions."
            )
    return plan_cover(
        len(reader.pages), metadata, content=content, profile=print_profile, style=style
    )


def _text_lines(text: str, width: int) -> tuple[str, ...]:
    return tuple(
        line
        for paragraph in text.splitlines()
        for line in wrap(paragraph, width=width, break_long_words=False)
    )


def render_cover_drawing(
    plan: CoverPlan, *, style: CoverStyle = _DEFAULT_STYLE
) -> VectorDrawing:
    """Render a black-and-white cover without construction guides or barcode marks."""
    if not isinstance(plan, CoverPlan) or not isinstance(style, CoverStyle):
        raise TypeError("plan and style must be CoverPlan and CoverStyle.")
    g = plan.geometry
    texts: list[Text | Line] = []
    title_lines = _text_lines(plan.metadata.title, 28)
    if len(title_lines) > 3:
        raise ValueError("title does not fit the supported front-cover template.")
    for index, line in enumerate(title_lines):
        texts.append(
            Text(
                line,
                Point(g.front_safe.center.x, g.front_safe.top + 100 + index * 34),
                style.title_size,
            )
        )
    if plan.metadata.subtitle is not None:
        subtitle = _text_lines(plan.metadata.subtitle, 38)
        if len(subtitle) > 2:
            raise ValueError(
                "subtitle does not fit the supported front-cover template."
            )
        texts.extend(
            Text(
                line,
                Point(g.front_safe.center.x, g.front_safe.top + 210 + index * 18),
                style.subtitle_size,
            )
            for index, line in enumerate(subtitle)
        )
    if plan.metadata.author is not None:
        texts.append(
            Text(
                plan.metadata.author,
                Point(g.front_safe.center.x, g.front_safe.bottom - 48),
                style.author_size,
            )
        )
    motif = Rect(g.front_safe.center.x - 54, g.front_safe.bottom - 190, 108, 108)
    for index in range(10):
        major = index % 3 == 0
        width = 1.5 if major else 0.75
        texts.append(
            Line(
                Point(motif.left + index * 12, motif.top),
                Point(motif.left + index * 12, motif.bottom),
                width,
                major,
            )
        )
        texts.append(
            Line(
                Point(motif.left, motif.top + index * 12),
                Point(motif.right, motif.top + index * 12),
                width,
                major,
            )
        )
    if plan.content.back_cover_copy is not None:
        lines = _text_lines(plan.content.back_cover_copy, 42)
        if len(lines) > 22:
            raise ValueError("back-cover copy does not fit the supported template.")
        texts.extend(
            Text(
                line,
                Point(g.back_safe.center.x, g.back_safe.top + 30 + index * 14),
                style.body_size,
            )
            for index, line in enumerate(lines)
        )
    if plan.content.spine_text is not None:
        start = g.spine.center.y - len(plan.content.spine_text) * 5
        texts.extend(
            Text(letter, Point(g.spine.center.x, start + index * 10), style.spine_size)
            for index, letter in enumerate(plan.content.spine_text)
        )
    return VectorDrawing(g.canvas, tuple(texts))


def render_cover_pdf(plan: CoverPlan, *, style: CoverStyle = _DEFAULT_STYLE) -> bytes:
    """Produce one continuous embedded-font vector cover PDF."""
    return render_pdf(
        (render_cover_drawing(plan, style=style),),
        title=plan.metadata.title,
        author=plan.metadata.author,
        producer="Sudoku Gen",
    )


def validate_cover_pdf(pdf: bytes, plan: CoverPlan) -> CoverReport:
    """Perform focused non-KDP-guaranteeing checks on a generated cover PDF."""
    issues: list[CoverIssue] = []
    try:
        reader = PdfReader(BytesIO(pdf))
    except Exception:
        return CoverReport(
            (CoverIssue("PDF_UNREADABLE", "Cover PDF cannot be opened."),)
        )
    if reader.is_encrypted:
        issues.append(CoverIssue("PDF_ENCRYPTED", "Cover PDF is encrypted."))
    if len(reader.pages) != 1:
        issues.append(CoverIssue("PAGE_COUNT", "Cover PDF must contain one page."))
    elif (
        abs(float(reader.pages[0].mediabox.width) - plan.geometry.canvas.width) > 0.01
        or abs(float(reader.pages[0].mediabox.height) - plan.geometry.canvas.height)
        > 0.01
    ):
        issues.append(
            CoverIssue("PAGE_SIZE", "Cover PDF dimensions do not match the plan.")
        )
    if len(reader.pages) == 1:
        fonts = reader.pages[0].get("/Resources", {}).get("/Font", {})
        for name, font_ref in fonts.items():
            descriptor = font_ref.get_object().get("/FontDescriptor")
            if not descriptor or not any(
                key in descriptor.get_object()
                for key in ("/FontFile", "/FontFile2", "/FontFile3")
            ):
                issues.append(
                    CoverIssue("FONT_NOT_EMBEDDED", f"Font {name} is not embedded.")
                )
    return CoverReport(tuple(issues))
