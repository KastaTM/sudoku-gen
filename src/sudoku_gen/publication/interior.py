"""Immutable editorial metadata, front matter, and complete-interior planning."""

from dataclasses import dataclass

from sudoku_gen.publication.pages import Page, PagePlan


def _optional_text(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string or None.")
    if not value.strip():
        raise ValueError(f"{name} must not be empty or whitespace.")
    return value


@dataclass(frozen=True, slots=True)
class PublicationMetadata:
    """Caller-supplied editorial information, separate from Sudoku content."""

    title: str
    subtitle: str | None = None
    author: str | None = None
    copyright_notice: str | None = None
    instructions: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.title, str):
            raise TypeError("title must be a string.")
        if not self.title.strip():
            raise ValueError("title must not be empty or whitespace.")
        for name in ("subtitle", "author", "copyright_notice", "instructions"):
            object.__setattr__(self, name, _optional_text(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class FrontMatterConfig:
    """The intentionally small set of supported introductory page types."""

    include_title_page: bool = True
    include_copyright_page: bool = False
    include_instructions_page: bool = False
    include_contents_page: bool = False

    def __post_init__(self) -> None:
        for name in (
            "include_title_page",
            "include_copyright_page",
            "include_instructions_page",
            "include_contents_page",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be a bool.")


_DEFAULT_FRONT_MATTER_CONFIG = FrontMatterConfig()


@dataclass(frozen=True, slots=True)
class TitlePage:
    physical_page_number: int

    def __post_init__(self) -> None:
        _validate_physical_page_number(self.physical_page_number)


@dataclass(frozen=True, slots=True)
class CopyrightPage:
    physical_page_number: int

    def __post_init__(self) -> None:
        _validate_physical_page_number(self.physical_page_number)


@dataclass(frozen=True, slots=True)
class InstructionsPage:
    physical_page_number: int

    def __post_init__(self) -> None:
        _validate_physical_page_number(self.physical_page_number)


@dataclass(frozen=True, slots=True)
class ContentsEntry:
    title: str
    editorial_page_number: int

    def __post_init__(self) -> None:
        if not isinstance(self.title, str):
            raise TypeError("title must be a string.")
        if not self.title.strip():
            raise ValueError("title must not be empty or whitespace.")
        if type(self.editorial_page_number) is not int:
            raise TypeError("editorial_page_number must be a built-in integer.")
        if self.editorial_page_number < 1:
            raise ValueError("editorial_page_number must be positive.")


@dataclass(frozen=True, slots=True)
class ContentsPage:
    physical_page_number: int
    entries: tuple[ContentsEntry, ...]

    def __post_init__(self) -> None:
        _validate_physical_page_number(self.physical_page_number)
        if not isinstance(self.entries, tuple) or not self.entries:
            raise ValueError(
                "entries must be a nonempty tuple of ContentsEntry instances."
            )
        if not all(isinstance(entry, ContentsEntry) for entry in self.entries):
            raise TypeError("entries must contain only ContentsEntry instances.")


type FrontMatterPage = TitlePage | CopyrightPage | InstructionsPage | ContentsPage
type InteriorPage = FrontMatterPage | Page


def _validate_physical_page_number(value: int) -> None:
    if type(value) is not int:
        raise TypeError("physical_page_number must be a built-in integer.")
    if value < 1:
        raise ValueError("physical_page_number must be positive.")


@dataclass(frozen=True, slots=True)
class InteriorPlan:
    """One ordered physical interior that references immutable existing page plans."""

    metadata: PublicationMetadata
    front_matter: tuple[FrontMatterPage, ...]
    page_plan: PagePlan

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, PublicationMetadata):
            raise TypeError("metadata must be a PublicationMetadata.")
        if not isinstance(self.front_matter, tuple) or not all(
            isinstance(page, (TitlePage, CopyrightPage, InstructionsPage, ContentsPage))
            for page in self.front_matter
        ):
            raise TypeError("front_matter must be a tuple of front-matter pages.")
        if not isinstance(self.page_plan, PagePlan):
            raise TypeError("page_plan must be a PagePlan.")
        if tuple(page.physical_page_number for page in self.front_matter) != tuple(
            range(1, len(self.front_matter) + 1)
        ):
            raise ValueError("Front-matter physical page numbers must be sequential.")

    @property
    def pages(self) -> tuple[InteriorPage, ...]:
        return self.front_matter + self.page_plan.pages

    @property
    def physical_page_count(self) -> int:
        return len(self.pages)


def plan_interior(
    metadata: PublicationMetadata,
    page_plan: PagePlan,
    *,
    config: FrontMatterConfig = _DEFAULT_FRONT_MATTER_CONFIG,
) -> InteriorPlan:
    """Compose deterministic front matter before unchanged puzzle and solution pages."""
    if not isinstance(metadata, PublicationMetadata):
        raise TypeError("metadata must be a PublicationMetadata.")
    if not isinstance(page_plan, PagePlan):
        raise TypeError("page_plan must be a PagePlan.")
    if not isinstance(config, FrontMatterConfig):
        raise TypeError("config must be a FrontMatterConfig.")
    pages: list[FrontMatterPage] = []
    if config.include_title_page:
        pages.append(TitlePage(len(pages) + 1))
    if config.include_copyright_page:
        if metadata.copyright_notice is None:
            raise ValueError("A copyright page requires copyright_notice content.")
        pages.append(CopyrightPage(len(pages) + 1))
    if config.include_instructions_page:
        if metadata.instructions is None:
            raise ValueError("An instructions page requires instructions content.")
        pages.append(InstructionsPage(len(pages) + 1))
    if config.include_contents_page:
        entries = tuple(
            ContentsEntry(
                section.title,
                page_plan.page_for_puzzle(section.first_puzzle_number).page_number,
            )
            for section in page_plan.book.sections
        )
        pages.append(ContentsPage(len(pages) + 1, entries))
    return InteriorPlan(metadata, tuple(pages), page_plan)
