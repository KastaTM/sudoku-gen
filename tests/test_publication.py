"""Deterministic editorial plans assembled from trusted batch artifacts."""

from dataclasses import FrozenInstanceError

import pytest

from sudoku_gen.difficulty import Difficulty, DifficultyReport
from sudoku_gen.exceptions import DuplicatePublicationPuzzleError
from sudoku_gen.fingerprint import FingerprintMode, fingerprint_puzzle
from sudoku_gen.generator import PuzzleBatch, PuzzleBatchItem
from sudoku_gen.human_solver import LogicalSolveStatus
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.publication import (
    BookPlan,
    BookPuzzle,
    BookSection,
    BookSectionInput,
    build_book_plan,
)

SOLUTION = Grid.from_string(
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)


def subset(*kept: int) -> SudokuPuzzle:
    grid = Grid(
        tuple(
            value if index in kept else 0 for index, value in enumerate(SOLUTION.cells)
        )
    )
    return SudokuPuzzle(grid, SOLUTION)


def relabel(puzzle: SudokuPuzzle) -> SudokuPuzzle:
    mapping = {1: 7, 2: 1, 3: 9, 4: 2, 5: 8, 6: 3, 7: 6, 8: 4, 9: 5}
    relabeled_grid = Grid(
        tuple(mapping.get(value, 0) if value else 0 for value in puzzle.grid.cells)
    )
    relabeled_solution = Grid(tuple(mapping[value] for value in SOLUTION.cells))
    return SudokuPuzzle(relabeled_grid, relabeled_solution)


def report(difficulty: Difficulty) -> DifficultyReport:
    return DifficultyReport(difficulty, 0, None, 0, 0, 0, 0, LogicalSolveStatus.SOLVED)


def batch(difficulty: Difficulty, *puzzles: SudokuPuzzle) -> PuzzleBatch:
    return PuzzleBatch(
        tuple(
            PuzzleBatchItem(
                puzzle,
                report(difficulty),
                fingerprint_puzzle(puzzle, FingerprintMode.DIGIT_NORMALIZED),
            )
            for puzzle in puzzles
        ),
        difficulty,
        FingerprintMode.DIGIT_NORMALIZED,
        attempts=len(puzzles),
        difficulty_rejections=0,
        duplicate_rejections=0,
    )


def test_single_section_plan_numbers_and_derives_counts() -> None:
    source = batch(Difficulty.EASY, subset(0, 1), subset(2, 3))

    plan = build_book_plan((BookSectionInput("Warm-up", source),))

    assert tuple(puzzle.number for puzzle in plan.puzzles) == (1, 2)
    assert plan.total_puzzle_count == 2
    assert plan.sections[0].first_puzzle_number == 1
    assert plan.sections[0].last_puzzle_number == 2
    assert plan.difficulty_counts == (
        (Difficulty.EASY, 2),
        (Difficulty.MEDIUM, 0),
        (Difficulty.HARD, 0),
        (Difficulty.EXPERT, 0),
    )
    assert source == batch(Difficulty.EASY, subset(0, 1), subset(2, 3))


def test_section_and_puzzle_order_are_preserved_across_global_numbering() -> None:
    medium = batch(Difficulty.MEDIUM, subset(0), subset(1))
    easy = batch(Difficulty.EASY, subset(2))

    plan = build_book_plan(
        (BookSectionInput("Medium first", medium), BookSectionInput("Easy later", easy))
    )

    assert tuple(section.title for section in plan.sections) == (
        "Medium first",
        "Easy later",
    )
    assert tuple(puzzle.puzzle for puzzle in plan.puzzles) == (
        *tuple(item.puzzle for item in medium.items),
        easy.items[0].puzzle,
    )
    assert tuple(puzzle.number for puzzle in plan.puzzles) == (1, 2, 3)
    assert tuple(
        (section.first_puzzle_number, section.last_puzzle_number)
        for section in plan.sections
    ) == ((1, 2), (3, 3))
    assert plan == build_book_plan(
        (BookSectionInput("Medium first", medium), BookSectionInput("Easy later", easy))
    )


def test_publication_records_enforce_solution_and_difficulty() -> None:
    puzzle = subset(0)
    fingerprint = fingerprint_puzzle(puzzle)
    with pytest.raises(ValueError, match="solution"):
        BookPuzzle(1, SudokuPuzzle(puzzle.grid), report(Difficulty.EASY), fingerprint)
    with pytest.raises(ValueError, match="UNRATED"):
        BookPuzzle(1, puzzle, report(Difficulty.UNRATED), fingerprint)
    with pytest.raises(ValueError, match="fingerprint"):
        BookPuzzle(
            1,
            puzzle,
            report(Difficulty.EASY),
            fingerprint_puzzle(subset(1)),
        )

    entry = BookPuzzle(1, puzzle, report(Difficulty.EASY), fingerprint)
    with pytest.raises(ValueError, match="match the section"):
        BookSection("Wrong", Difficulty.MEDIUM, (entry,))
    with pytest.raises(ValueError, match="at least one"):
        BookSection("Empty", Difficulty.EASY, ())
    with pytest.raises(ValueError, match="at least one"):
        BookPlan(())
    with pytest.raises(ValueError, match="requires at least one"):
        build_book_plan(())


def test_cross_section_duplicate_policy_is_explicit_and_mode_configurable() -> None:
    original = subset(0, 1, 2)
    relabeled = relabel(original)
    first = batch(Difficulty.EASY, original)
    second = batch(Difficulty.MEDIUM, relabeled)

    with pytest.raises(DuplicatePublicationPuzzleError) as duplicate:
        build_book_plan((BookSectionInput("A", first), BookSectionInput("B", second)))
    assert (
        duplicate.value.first_section,
        duplicate.value.first_position,
        duplicate.value.duplicate_section,
        duplicate.value.duplicate_position,
    ) == (1, 1, 2, 1)

    exact = build_book_plan(
        (BookSectionInput("A", first), BookSectionInput("B", second)),
        deduplication_mode=FingerprintMode.EXACT,
    )
    assert exact.total_puzzle_count == 2
    assert all(
        puzzle.fingerprint.mode is FingerprintMode.EXACT for puzzle in exact.puzzles
    )


def test_exact_duplicates_and_distinct_puzzles_have_expected_outcomes() -> None:
    original = subset(0, 1)
    duplicate = batch(Difficulty.MEDIUM, original)
    first = batch(Difficulty.EASY, original)
    with pytest.raises(DuplicatePublicationPuzzleError):
        build_book_plan(
            (BookSectionInput("A", first), BookSectionInput("B", duplicate)),
            deduplication_mode=FingerprintMode.EXACT,
        )

    distinct = batch(Difficulty.MEDIUM, subset(2, 3))
    plan = build_book_plan(
        (BookSectionInput("A", first), BookSectionInput("B", distinct))
    )
    assert plan.total_puzzle_count == 2


def test_publication_value_records_are_frozen_and_validate_sequential_numbers() -> None:
    puzzle = subset(0)
    entry = BookPuzzle(1, puzzle, report(Difficulty.EASY), fingerprint_puzzle(puzzle))
    section = BookSection("One", Difficulty.EASY, (entry,))
    plan = BookPlan((section,), FingerprintMode.EXACT)

    assert hash(entry) == hash(
        BookPuzzle(1, puzzle, report(Difficulty.EASY), fingerprint_puzzle(puzzle))
    )
    assert hash(plan) == hash(BookPlan((section,), FingerprintMode.EXACT))
    with pytest.raises(FrozenInstanceError):
        entry.number = 2
    with pytest.raises(ValueError, match="sequential"):
        BookPlan(
            (
                BookSection(
                    "Bad",
                    Difficulty.EASY,
                    (
                        BookPuzzle(
                            2,
                            puzzle,
                            report(Difficulty.EASY),
                            fingerprint_puzzle(puzzle),
                        ),
                    ),
                ),
            ),
            FingerprintMode.EXACT,
        )
