"""Diagnostic KDP paperback preflight for existing PDF interiors."""

from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from math import isfinite

from pypdf import PdfReader

from sudoku_gen.publication.geometry import PhysicalPageSize
from sudoku_gen.publication.interior import InteriorPlan
from sudoku_gen.publication.pages import PagePlan
from sudoku_gen.publication.render import Line, Text, VectorDrawing


class PreflightSeverity(Enum):
    """Severity for a deterministic preflight diagnostic."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class PageMargins:
    """Physical safe margins for one recto or verso interior page."""

    left: float
    right: float
    top: float
    bottom: float
    is_recto: bool

    def __post_init__(self) -> None:
        for name in ("left", "right", "top", "bottom"):
            value = getattr(self, name)
            if type(value) not in (int, float) or isinstance(value, bool):
                raise TypeError(f"{name} must be a built-in non-negative number.")
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and not negative.")
            object.__setattr__(self, name, float(value))
        if type(self.is_recto) is not bool:
            raise TypeError("is_recto must be a bool.")

    def with_stroke_clearance(self, stroke_width: float) -> "PageMargins":
        """Inset all safe edges by half a stroke so vector extents remain safe."""
        if type(stroke_width) not in (int, float) or isinstance(stroke_width, bool):
            raise TypeError("stroke_width must be a built-in positive number.")
        if not isfinite(stroke_width) or stroke_width <= 0:
            raise ValueError("stroke_width must be finite and greater than zero.")
        clearance = float(stroke_width) / 2
        return PageMargins(
            self.left + clearance,
            self.right + clearance,
            self.top + clearance,
            self.bottom + clearance,
            self.is_recto,
        )


@dataclass(frozen=True, slots=True)
class PrintProfile:
    """The supported 6-by-9-inch KDP paperback, no-bleed policy values."""

    trim_size: PhysicalPageSize = PhysicalPageSize.six_by_nine_inches()
    bleed: bool = False
    minimum_page_count: int = 24
    maximum_page_count: int = 828
    page_size_tolerance: float = 0.5
    outside_margin: float = 18.0
    top_margin: float = 18.0
    bottom_margin: float = 18.0
    minimum_line_width: float = 0.75
    minimum_text_size: float = 7.0

    def __post_init__(self) -> None:
        if not isinstance(self.trim_size, PhysicalPageSize):
            raise TypeError("trim_size must be a PhysicalPageSize.")
        if self.trim_size != PhysicalPageSize.six_by_nine_inches():
            raise ValueError("Only the 6 by 9 inch paperback trim is supported.")
        if type(self.bleed) is not bool:
            raise TypeError("bleed must be a bool.")
        if self.bleed:
            raise ValueError("Bleed preflight is not implemented.")
        for name in ("minimum_page_count", "maximum_page_count"):
            value = getattr(self, name)
            if type(value) is not int:
                raise TypeError(f"{name} must be a built-in integer.")
            if value < 1:
                raise ValueError(f"{name} must be positive.")
        if self.minimum_page_count > self.maximum_page_count:
            raise ValueError("minimum_page_count must not exceed maximum_page_count.")
        for name in (
            "page_size_tolerance",
            "outside_margin",
            "top_margin",
            "bottom_margin",
            "minimum_line_width",
            "minimum_text_size",
        ):
            value = getattr(self, name)
            if type(value) not in (int, float) or isinstance(value, bool):
                raise TypeError(f"{name} must be a built-in positive number.")
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero.")

    def inside_margin(self, effective_page_count: int) -> float:
        """Return KDP's published no-bleed inside margin in points."""
        if type(effective_page_count) is not int:
            raise TypeError("effective_page_count must be a built-in integer.")
        if (
            not self.minimum_page_count
            <= effective_page_count
            <= self.maximum_page_count
        ):
            raise ValueError("effective_page_count is outside the supported range.")
        if effective_page_count <= 150:
            return 27.0
        if effective_page_count <= 300:
            return 36.0
        if effective_page_count <= 500:
            return 45.0
        if effective_page_count <= 700:
            return 54.0
        return 63.0

    def effective_page_count(self, actual_page_count: int) -> int:
        """Return the even physical page count used for bound-margin policy."""
        if type(actual_page_count) is not int:
            raise TypeError("actual_page_count must be a built-in integer.")
        if actual_page_count < 1:
            raise ValueError("actual_page_count must be positive.")
        return (
            actual_page_count if actual_page_count % 2 == 0 else actual_page_count + 1
        )

    def page_margins(
        self, effective_page_count: int, physical_page_number: int
    ) -> PageMargins:
        """Return KDP safe margins for physical page position, not printed numbering."""
        if type(physical_page_number) is not int:
            raise TypeError("physical_page_number must be a built-in integer.")
        if physical_page_number < 1:
            raise ValueError("physical_page_number must be positive.")
        inside = self.inside_margin(effective_page_count)
        is_recto = physical_page_number % 2 == 1
        return PageMargins(
            inside if is_recto else self.outside_margin,
            self.outside_margin if is_recto else inside,
            self.top_margin,
            self.bottom_margin,
            is_recto,
        )


_DEFAULT_PRINT_PROFILE = PrintProfile()


@dataclass(frozen=True, slots=True)
class PreflightIssue:
    """One stable, non-mutating PDF preflight diagnostic."""

    code: str
    severity: PreflightSeverity
    message: str
    page_number: int | None = None
    actual: str | None = None
    required: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code:
            raise ValueError("code must be a nonempty string.")
        if not isinstance(self.severity, PreflightSeverity):
            raise TypeError("severity must be a PreflightSeverity.")
        if not isinstance(self.message, str) or not self.message:
            raise ValueError("message must be a nonempty string.")
        if self.page_number is not None and (
            type(self.page_number) is not int or self.page_number < 1
        ):
            raise ValueError("page_number must be a positive built-in integer or None.")


@dataclass(frozen=True, slots=True)
class PreflightReport:
    """An immutable preflight result with deterministic issue ordering."""

    profile: PrintProfile
    actual_page_count: int | None
    effective_page_count: int | None
    issues: tuple[PreflightIssue, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.profile, PrintProfile):
            raise TypeError("profile must be a PrintProfile.")
        if not isinstance(self.issues, tuple) or not all(
            isinstance(issue, PreflightIssue) for issue in self.issues
        ):
            raise TypeError("issues must be a tuple of PreflightIssue instances.")
        ordered = tuple(sorted(self.issues, key=_issue_key))
        object.__setattr__(self, "issues", ordered)

    @property
    def has_blocking_issues(self) -> bool:
        return any(issue.severity is PreflightSeverity.ERROR for issue in self.issues)


def _issue_key(issue: PreflightIssue) -> tuple[int, int, str, str]:
    return (
        issue.page_number is None,
        issue.page_number or 0,
        issue.code,
        issue.message,
    )


def _issue(
    code: str,
    severity: PreflightSeverity,
    message: str,
    page_number: int | None = None,
    actual: str | None = None,
    required: str | None = None,
) -> PreflightIssue:
    return PreflightIssue(code, severity, message, page_number, actual, required)


def _effective_page_count(actual_page_count: int) -> int:
    return _DEFAULT_PRINT_PROFILE.effective_page_count(actual_page_count)


def _preflight_drawings(
    drawings: tuple[VectorDrawing, ...],
    profile: PrintProfile,
    effective_page_count: int,
) -> list[PreflightIssue]:
    issues: list[PreflightIssue] = []
    for page_number, drawing in enumerate(drawings, start=1):
        if not isinstance(drawing, VectorDrawing):
            raise TypeError("drawings must contain only VectorDrawing instances.")
        if (
            drawing.bounds.width != profile.trim_size.width
            or drawing.bounds.height != profile.trim_size.height
        ):
            issues.append(
                _issue(
                    "DRAWING_PAGE_SIZE",
                    PreflightSeverity.ERROR,
                    "Drawing bounds do not match the supported trim size.",
                    page_number,
                )
            )
        margin_page_count = min(
            max(effective_page_count, profile.minimum_page_count),
            profile.maximum_page_count,
        )
        margins = profile.page_margins(margin_page_count, page_number)
        for primitive in drawing.primitives:
            if isinstance(primitive, Line):
                if primitive.stroke_width < profile.minimum_line_width:
                    issues.append(
                        _issue(
                            "LINE_WIDTH",
                            PreflightSeverity.ERROR,
                            "Line width is below the configured KDP minimum.",
                            page_number,
                            str(primitive.stroke_width),
                            str(profile.minimum_line_width),
                        )
                    )
                half = primitive.stroke_width / 2
                left = min(primitive.start.x, primitive.end.x) - half
                right = max(primitive.start.x, primitive.end.x) + half
                top = min(primitive.start.y, primitive.end.y) - half
                bottom = max(primitive.start.y, primitive.end.y) + half
            elif isinstance(primitive, Text):
                if primitive.font_size < profile.minimum_text_size:
                    issues.append(
                        _issue(
                            "TEXT_SIZE",
                            PreflightSeverity.ERROR,
                            "Text size is below the configured minimum.",
                            page_number,
                            str(primitive.font_size),
                            str(profile.minimum_text_size),
                        )
                    )
                half = primitive.font_size / 2
                left = primitive.position.x - half
                right = primitive.position.x + half
                top = primitive.position.y - half
                bottom = primitive.position.y + half
            else:
                issues.append(
                    _issue(
                        "UNSUPPORTED_PRIMITIVE",
                        PreflightSeverity.ERROR,
                        "Drawing contains an unsupported vector primitive.",
                        page_number,
                    )
                )
                continue
            if (
                left < margins.left
                or right > drawing.bounds.width - margins.right
                or top < margins.top
                or bottom > drawing.bounds.height - margins.bottom
            ):
                issues.append(
                    _issue(
                        "CONTENT_SAFE_AREA",
                        PreflightSeverity.ERROR,
                        "Content extends into the required physical safe area.",
                        page_number,
                    )
                )
    return issues


def preflight_pdf(
    pdf_bytes: bytes,
    *,
    profile: PrintProfile = _DEFAULT_PRINT_PROFILE,
    drawings: tuple[VectorDrawing, ...] | None = None,
    page_plan: PagePlan | None = None,
    interior_plan: InteriorPlan | None = None,
) -> PreflightReport:
    """Inspect PDF structure and optional original drawings without modifying either."""
    if not isinstance(pdf_bytes, bytes):
        raise TypeError("pdf_bytes must be bytes.")
    if not isinstance(profile, PrintProfile):
        raise TypeError("profile must be a PrintProfile.")
    if drawings is not None and not isinstance(drawings, tuple):
        raise TypeError("drawings must be a tuple of VectorDrawing instances or None.")
    if page_plan is not None and not isinstance(page_plan, PagePlan):
        raise TypeError("page_plan must be a PagePlan or None.")
    if interior_plan is not None and not isinstance(interior_plan, InteriorPlan):
        raise TypeError("interior_plan must be an InteriorPlan or None.")
    if page_plan is not None and interior_plan is not None:
        raise ValueError("Specify page_plan or interior_plan, not both.")
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except Exception:
        return PreflightReport(
            profile,
            None,
            None,
            (
                _issue(
                    "PDF_UNREADABLE", PreflightSeverity.ERROR, "PDF cannot be opened."
                ),
            ),
        )
    if reader.is_encrypted:
        return PreflightReport(
            profile,
            None,
            None,
            (_issue("PDF_ENCRYPTED", PreflightSeverity.ERROR, "PDF is encrypted."),),
        )
    actual = len(reader.pages)
    effective = _effective_page_count(actual)
    issues: list[PreflightIssue] = []
    if not profile.minimum_page_count <= effective <= profile.maximum_page_count:
        issues.append(
            _issue(
                "PAGE_COUNT",
                PreflightSeverity.ERROR,
                "Effective production page count is outside the supported KDP range.",
                actual=str(actual),
                required=f"{profile.minimum_page_count}-{profile.maximum_page_count}",
            )
        )
    if actual % 2:
        issues.append(
            _issue(
                "ODD_PAGE_COUNT",
                PreflightSeverity.INFO,
                "KDP will use an even effective production page count.",
                actual=str(actual),
                required=str(effective),
            )
        )
    if page_plan is not None and actual != len(page_plan.pages):
        issues.append(
            _issue(
                "PAGE_PLAN_COUNT",
                PreflightSeverity.ERROR,
                "PDF page count does not match the supplied PagePlan.",
                actual=str(actual),
                required=str(len(page_plan.pages)),
            )
        )
    if interior_plan is not None and actual != interior_plan.physical_page_count:
        issues.append(
            _issue(
                "INTERIOR_PLAN_COUNT",
                PreflightSeverity.ERROR,
                "PDF page count does not match the supplied InteriorPlan.",
                actual=str(actual),
                required=str(interior_plan.physical_page_count),
            )
        )
    for number, page in enumerate(reader.pages, start=1):
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if (
            abs(width - profile.trim_size.width) > profile.page_size_tolerance
            or abs(height - profile.trim_size.height) > profile.page_size_tolerance
        ):
            issues.append(
                _issue(
                    "PAGE_SIZE",
                    PreflightSeverity.ERROR,
                    "PDF page dimensions do not match the supported no-bleed trim.",
                    number,
                    f"{width}x{height}",
                    f"{profile.trim_size.width}x{profile.trim_size.height}",
                )
            )
        if width > height:
            issues.append(
                _issue(
                    "PAGE_ORIENTATION",
                    PreflightSeverity.ERROR,
                    "PDF page is landscape instead of portrait.",
                    number,
                )
            )
        if page.get("/Annots"):
            issues.append(
                _issue(
                    "ANNOTATIONS",
                    PreflightSeverity.ERROR,
                    "PDF page has annotations.",
                    number,
                )
            )
        try:
            if not page.extract_text().strip():
                issues.append(
                    _issue(
                        "BLANK_PAGE",
                        PreflightSeverity.WARNING,
                        "PDF page has no extractable text.",
                        number,
                    )
                )
        except Exception:
            issues.append(
                _issue(
                    "TEXT_EXTRACTION",
                    PreflightSeverity.WARNING,
                    "PDF text could not be extracted.",
                    number,
                )
            )
        fonts = page.get("/Resources", {}).get("/Font", {})
        for font_name in sorted(fonts):
            font = fonts[font_name].get_object()
            descriptor = font.get("/FontDescriptor")
            embedded = descriptor and any(
                key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3")
            )
            if not embedded:
                issues.append(
                    _issue(
                        "FONT_NOT_EMBEDDED",
                        PreflightSeverity.ERROR,
                        f"Font {font_name} is not embedded.",
                        number,
                    )
                )
    if drawings is None:
        issues.append(
            _issue(
                "DRAWING_GEOMETRY_REQUIRED",
                PreflightSeverity.INFO,
                "Margin, line-width, and text-placement checks require "
                "VectorDrawing input.",
            )
        )
    else:
        if len(drawings) != actual:
            issues.append(
                _issue(
                    "DRAWING_PAGE_COUNT",
                    PreflightSeverity.ERROR,
                    "Drawing count does not match PDF page count.",
                    actual=str(len(drawings)),
                    required=str(actual),
                )
            )
        else:
            issues.extend(_preflight_drawings(drawings, profile, effective))
    return PreflightReport(profile, actual, effective, tuple(issues))
