"""Abstract deterministic pagination over immutable editorial book plans."""

from dataclasses import FrozenInstanceError

import pytest

from sudoku_gen.difficulty import Difficulty, DifficultyReport
from sudoku_gen.fingerprint import FingerprintMode, fingerprint_puzzle
from sudoku_gen.human_solver import LogicalSolveStatus
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.publication import (
    BookPlan,
    BookPuzzle,
    BookSection,
    PageLayoutProfile,
    PagePlan,
    PuzzlePage,
    PuzzlePageItem,
    SolutionPage,
    SolutionPageItem,
    plan_book_pages,
)

SOLUTION = Grid.from_string(
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)


def make_entry(number: int, difficulty: Difficulty = Difficulty.EASY) -> BookPuzzle:
    grid = Grid(
        tuple(
            value if index == number - 1 else 0
            for index, value in enumerate(SOLUTION.cells)
        )
    )
    puzzle = SudokuPuzzle(grid, SOLUTION)
    report = DifficultyReport(
        difficulty, 0, None, 0, 0, 0, 0, LogicalSolveStatus.SOLVED
    )
    return BookPuzzle(number, puzzle, report, fingerprint_puzzle(puzzle))


def make_book(count: int, *, section_break: int | None = None) -> BookPlan:
    entries = tuple(make_entry(number) for number in range(1, count + 1))
    if section_break is None:
        sections = (BookSection("Puzzles", Difficulty.EASY, entries),)
    else:
        sections = (
            BookSection("First", Difficulty.EASY, entries[:section_break]),
            BookSection("Second", Difficulty.EASY, entries[section_break:]),
        )
    return BookPlan(sections, FingerprintMode.EXACT)


def numbers(page: PuzzlePage | SolutionPage) -> tuple[int, ...]:
    return tuple(item.puzzle.number for item in page.items)


def test_seven_puzzle_regression_example_has_exact_pages_slots_and_numbers() -> None:
    book = make_book(7)
    layout = PageLayoutProfile(2, 4, 5)

    plan = plan_book_pages(book, layout=layout)

    assert tuple((page.page_number, numbers(page)) for page in plan.puzzle_pages) == (
        (5, (1, 2)),
        (6, (3, 4)),
        (7, (5, 6)),
        (8, (7,)),
    )
    assert tuple((page.page_number, numbers(page)) for page in plan.solution_pages) == (
        (9, (1, 2, 3, 4)),
        (10, (5, 6, 7)),
    )
    assert tuple(tuple(item.slot for item in page.items) for page in plan.pages) == (
        (1, 2),
        (1, 2),
        (1, 2),
        (1,),
        (1, 2, 3, 4),
        (1, 2, 3),
    )


@pytest.mark.parametrize(
    ("count", "puzzle_capacity", "expected_pages", "final_size"),
    [(1, 2, 1, 1), (2, 2, 1, 2), (3, 2, 2, 1), (6, 2, 3, 2)],
)
def test_puzzle_pagination_handles_single_full_partial_and_multiple_pages(
    count: int, puzzle_capacity: int, expected_pages: int, final_size: int
) -> None:
    plan = plan_book_pages(
        make_book(count), layout=PageLayoutProfile(puzzle_capacity, 6)
    )

    assert plan.puzzle_page_count == expected_pages
    assert len(plan.last_puzzle_page.items) == final_size
    assert all(len(page.items) <= puzzle_capacity for page in plan.puzzle_pages)


def test_capacities_are_independent_and_every_book_puzzle_appears_once() -> None:
    book = make_book(7)
    plan = plan_book_pages(book, layout=PageLayoutProfile(3, 2))

    assert plan.puzzle_page_count == 3
    assert plan.solution_page_count == 4
    assert plan.total_page_count == 7
    assert tuple(
        number for page in plan.puzzle_pages for number in numbers(page)
    ) == tuple(range(1, 8))
    assert tuple(
        number for page in plan.solution_pages for number in numbers(page)
    ) == tuple(range(1, 8))
    assert plan.first_puzzle_page.page_number == 1
    assert plan.last_puzzle_page.page_number == 3
    assert plan.first_solution_page.page_number == 4
    assert plan.last_solution_page.page_number == 7


def test_section_boundary_can_share_a_puzzle_page() -> None:
    book = make_book(5, section_break=3)

    plan = plan_book_pages(book, layout=PageLayoutProfile(2, 5))

    assert numbers(plan.puzzle_pages[1]) == (3, 4)
    assert plan.puzzle_pages[1].items[0].puzzle is book.sections[0].puzzles[-1]
    assert plan.puzzle_pages[1].items[1].puzzle is book.sections[1].puzzles[0]


def test_lookup_finds_puzzle_and_solution_pages_and_rejects_invalid_numbers() -> None:
    plan = plan_book_pages(make_book(7), layout=PageLayoutProfile(2, 4, 5))

    assert plan.page_for_puzzle(7).page_number == 8
    assert plan.page_for_puzzle(2).page_number == 5
    assert plan.solution_page_for_puzzle(7).page_number == 10
    assert plan.solution_page_for_puzzle(2).page_number == 9
    for invalid in (0, 8, -1):
        with pytest.raises(ValueError):
            plan.page_for_puzzle(invalid)
    for invalid_type in (True, 1.0, "1", None):
        with pytest.raises(TypeError):
            plan.solution_page_for_puzzle(invalid_type)


@pytest.mark.parametrize(
    "field", ("puzzles_per_page", "solutions_per_page", "first_page_number")
)
@pytest.mark.parametrize("value", (True, False, 1.0, "1", None, 0, -1))
def test_layout_profile_rejects_invalid_capacity_and_number_values(
    field: str, value: object
) -> None:
    values: dict[str, object] = {
        "puzzles_per_page": 2,
        "solutions_per_page": 6,
        "first_page_number": 1,
    }
    values[field] = value
    with pytest.raises((TypeError, ValueError)):
        PageLayoutProfile(**values)


def test_page_and_plan_validation_rejects_slots_numbers_capacity_and_coverage() -> None:
    book = make_book(3)
    with pytest.raises(ValueError, match="slots"):
        PuzzlePage(1, (PuzzlePageItem(2, book.puzzles[0]),))

    valid = plan_book_pages(book, layout=PageLayoutProfile(2, 3, 5))
    renumbered = PuzzlePage(7, valid.puzzle_pages[0].items)
    with pytest.raises(ValueError, match="sequential"):
        PagePlan(book, (renumbered, *valid.pages[1:]), valid.layout)

    overflow = PuzzlePage(
        5,
        tuple(
            PuzzlePageItem(slot, puzzle) for slot, puzzle in enumerate(book.puzzles, 1)
        ),
    )
    solutions = SolutionPage(
        6,
        tuple(
            SolutionPageItem(slot, puzzle)
            for slot, puzzle in enumerate(book.puzzles, 1)
        ),
    )
    with pytest.raises(ValueError, match="capacity"):
        PagePlan(book, (overflow, solutions), valid.layout)

    duplicate = PuzzlePage(
        5,
        (PuzzlePageItem(1, book.puzzles[0]), PuzzlePageItem(2, book.puzzles[0])),
    )
    final = PuzzlePage(6, (PuzzlePageItem(1, book.puzzles[2]),))
    solutions = SolutionPage(
        7,
        tuple(
            SolutionPageItem(slot, puzzle)
            for slot, puzzle in enumerate(book.puzzles, 1)
        ),
    )
    with pytest.raises(ValueError, match="exactly once"):
        PagePlan(book, (duplicate, final, solutions), valid.layout)


def test_planning_is_deterministic_hashable_immutable_and_preserves_book() -> None:
    book = make_book(5, section_break=2)
    original_hash = hash(book)
    layout = PageLayoutProfile(2, 3, 9)

    first = plan_book_pages(book, layout=layout)
    second = plan_book_pages(book, layout=layout)

    assert first == second
    assert hash(first) == hash(second)
    assert first.book is book
    assert hash(book) == original_hash
    assert book == make_book(5, section_break=2)
    with pytest.raises(FrozenInstanceError):
        first.pages = ()
    with pytest.raises(FrozenInstanceError):
        first.pages[0].page_number = 99
