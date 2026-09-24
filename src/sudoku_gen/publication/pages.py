"""Deterministic abstract pagination for immutable publication content."""

from dataclasses import dataclass

from sudoku_gen.publication.models import BookPlan, BookPuzzle


def _validate_positive_integer(value: int, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be a built-in integer.")
    if value < 1:
        raise ValueError(f"{name} must be at least 1.")


@dataclass(frozen=True, slots=True)
class PageLayoutProfile:
    """Abstract capacities and starting number, without physical geometry."""

    puzzles_per_page: int = 2
    solutions_per_page: int = 6
    first_page_number: int = 1

    def __post_init__(self) -> None:
        _validate_positive_integer(self.puzzles_per_page, "puzzles_per_page")
        _validate_positive_integer(self.solutions_per_page, "solutions_per_page")
        _validate_positive_integer(self.first_page_number, "first_page_number")


_DEFAULT_PAGE_LAYOUT = PageLayoutProfile()


@dataclass(frozen=True, slots=True)
class PuzzlePageItem:
    """A book puzzle assigned to one contiguous abstract puzzle-page slot."""

    slot: int
    puzzle: BookPuzzle

    def __post_init__(self) -> None:
        _validate_positive_integer(self.slot, "slot")
        if not isinstance(self.puzzle, BookPuzzle):
            raise TypeError("puzzle must be a BookPuzzle.")


@dataclass(frozen=True, slots=True)
class SolutionPageItem:
    """A book puzzle assigned to one contiguous abstract solution-page slot."""

    slot: int
    puzzle: BookPuzzle

    def __post_init__(self) -> None:
        _validate_positive_integer(self.slot, "slot")
        if not isinstance(self.puzzle, BookPuzzle):
            raise TypeError("puzzle must be a BookPuzzle.")


@dataclass(frozen=True, slots=True)
class PuzzlePage:
    """One nonempty ordered page of puzzle references."""

    page_number: int
    items: tuple[PuzzlePageItem, ...]

    def __post_init__(self) -> None:
        _validate_positive_integer(self.page_number, "page_number")
        if not isinstance(self.items, tuple):
            raise TypeError("items must be a tuple of PuzzlePageItem instances.")
        if not self.items:
            raise ValueError("A puzzle page must contain at least one item.")
        if not all(isinstance(item, PuzzlePageItem) for item in self.items):
            raise TypeError("items must contain only PuzzlePageItem instances.")
        if tuple(item.slot for item in self.items) != tuple(
            range(1, len(self.items) + 1)
        ):
            raise ValueError("Puzzle-page slots must be contiguous from 1.")


@dataclass(frozen=True, slots=True)
class SolutionPage:
    """One nonempty ordered page of solution references."""

    page_number: int
    items: tuple[SolutionPageItem, ...]

    def __post_init__(self) -> None:
        _validate_positive_integer(self.page_number, "page_number")
        if not isinstance(self.items, tuple):
            raise TypeError("items must be a tuple of SolutionPageItem instances.")
        if not self.items:
            raise ValueError("A solution page must contain at least one item.")
        if not all(isinstance(item, SolutionPageItem) for item in self.items):
            raise TypeError("items must contain only SolutionPageItem instances.")
        if tuple(item.slot for item in self.items) != tuple(
            range(1, len(self.items) + 1)
        ):
            raise ValueError("Solution-page slots must be contiguous from 1.")


type Page = PuzzlePage | SolutionPage


@dataclass(frozen=True, slots=True)
class PagePlan:
    """Validated puzzle-pages-first pagination for one immutable book plan."""

    book: BookPlan
    pages: tuple[Page, ...]
    layout: PageLayoutProfile

    def __post_init__(self) -> None:
        if not isinstance(self.book, BookPlan):
            raise TypeError("book must be a BookPlan.")
        if not isinstance(self.layout, PageLayoutProfile):
            raise TypeError("layout must be a PageLayoutProfile.")
        if not isinstance(self.pages, tuple):
            raise TypeError("pages must be a tuple of page records.")
        if not self.pages or not all(
            isinstance(page, (PuzzlePage, SolutionPage)) for page in self.pages
        ):
            raise ValueError("pages must contain puzzle and solution pages.")
        expected_numbers = tuple(
            range(
                self.layout.first_page_number,
                self.layout.first_page_number + len(self.pages),
            )
        )
        if tuple(page.page_number for page in self.pages) != expected_numbers:
            raise ValueError("Page numbers must be unique and globally sequential.")
        if self.pages != (*self.puzzle_pages, *self.solution_pages):
            raise ValueError("All puzzle pages must precede all solution pages.")
        self._validate_capacity(
            self.puzzle_pages, self.layout.puzzles_per_page, "Puzzle"
        )
        self._validate_capacity(
            self.solution_pages, self.layout.solutions_per_page, "Solution"
        )
        if self._puzzle_sequence() != self.book.puzzles:
            raise ValueError(
                "Puzzle pages must contain every book puzzle exactly once in order."
            )
        if self._solution_sequence() != self.book.puzzles:
            raise ValueError(
                "Solution pages must contain every book puzzle exactly once in order."
            )

    @staticmethod
    def _validate_capacity(
        pages: tuple[PuzzlePage, ...] | tuple[SolutionPage, ...],
        capacity: int,
        label: str,
    ) -> None:
        if not pages:
            raise ValueError(
                f"A page plan must contain at least one {label.lower()} page."
            )
        if any(len(page.items) > capacity for page in pages):
            raise ValueError(f"{label} page capacity exceeded.")
        if any(len(page.items) != capacity for page in pages[:-1]):
            raise ValueError(f"Every non-final {label.lower()} page must be full.")

    def _puzzle_sequence(self) -> tuple[BookPuzzle, ...]:
        return tuple(item.puzzle for page in self.puzzle_pages for item in page.items)

    def _solution_sequence(self) -> tuple[BookPuzzle, ...]:
        return tuple(item.puzzle for page in self.solution_pages for item in page.items)

    @property
    def puzzle_pages(self) -> tuple[PuzzlePage, ...]:
        return tuple(page for page in self.pages if isinstance(page, PuzzlePage))

    @property
    def solution_pages(self) -> tuple[SolutionPage, ...]:
        return tuple(page for page in self.pages if isinstance(page, SolutionPage))

    @property
    def total_page_count(self) -> int:
        return len(self.pages)

    @property
    def puzzle_page_count(self) -> int:
        return len(self.puzzle_pages)

    @property
    def solution_page_count(self) -> int:
        return len(self.solution_pages)

    @property
    def first_puzzle_page(self) -> PuzzlePage:
        return self.puzzle_pages[0]

    @property
    def last_puzzle_page(self) -> PuzzlePage:
        return self.puzzle_pages[-1]

    @property
    def first_solution_page(self) -> SolutionPage:
        return self.solution_pages[0]

    @property
    def last_solution_page(self) -> SolutionPage:
        return self.solution_pages[-1]

    def page_for_puzzle(self, number: int) -> PuzzlePage:
        """Return the puzzle page containing one valid global puzzle number."""
        self._validate_puzzle_number(number)
        return next(
            page
            for page in self.puzzle_pages
            if any(item.puzzle.number == number for item in page.items)
        )

    def solution_page_for_puzzle(self, number: int) -> SolutionPage:
        """Return the solution page containing one valid global puzzle number."""
        self._validate_puzzle_number(number)
        return next(
            page
            for page in self.solution_pages
            if any(item.puzzle.number == number for item in page.items)
        )

    def _validate_puzzle_number(self, number: int) -> None:
        if type(number) is not int:
            raise TypeError("puzzle number must be a built-in integer.")
        if not 1 <= number <= self.book.total_puzzle_count:
            raise ValueError("puzzle number is outside this book plan.")


def plan_book_pages(
    book: BookPlan,
    *,
    layout: PageLayoutProfile = _DEFAULT_PAGE_LAYOUT,
) -> PagePlan:
    """Return deterministic puzzle pages followed by deterministic solution pages."""
    if not isinstance(book, BookPlan):
        raise TypeError("book must be a BookPlan.")
    if not isinstance(layout, PageLayoutProfile):
        raise TypeError("layout must be a PageLayoutProfile.")

    pages: list[Page] = []
    page_number = layout.first_page_number
    for start in range(0, len(book.puzzles), layout.puzzles_per_page):
        chunk = book.puzzles[start : start + layout.puzzles_per_page]
        puzzle_items = tuple(
            PuzzlePageItem(slot, puzzle) for slot, puzzle in enumerate(chunk, start=1)
        )
        pages.append(PuzzlePage(page_number, puzzle_items))
        page_number += 1
    for start in range(0, len(book.puzzles), layout.solutions_per_page):
        chunk = book.puzzles[start : start + layout.solutions_per_page]
        solution_items = tuple(
            SolutionPageItem(slot, puzzle) for slot, puzzle in enumerate(chunk, start=1)
        )
        pages.append(SolutionPage(page_number, solution_items))
        page_number += 1
    return PagePlan(book, tuple(pages), layout)
