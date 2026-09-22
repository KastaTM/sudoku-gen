"""Immutable editorial content plans assembled from trusted generation batches."""

from collections.abc import Iterable
from dataclasses import dataclass

from sudoku_gen.difficulty import Difficulty, DifficultyReport
from sudoku_gen.exceptions import DuplicatePublicationPuzzleError
from sudoku_gen.fingerprint import (
    FingerprintMode,
    GridFingerprint,
    deduplicate_puzzles,
    fingerprint_puzzle,
)
from sudoku_gen.generator import PuzzleBatch
from sudoku_gen.models import SudokuPuzzle

_PUBLISHABLE_DIFFICULTIES = frozenset(
    (Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD, Difficulty.EXPERT)
)


def _validate_title(title: str) -> None:
    if not isinstance(title, str):
        raise TypeError("title must be a string.")
    if not title.strip():
        raise ValueError("title must not be empty or whitespace.")


def _validate_publishable_difficulty(difficulty: Difficulty) -> None:
    if not isinstance(difficulty, Difficulty):
        raise TypeError("difficulty must be a Difficulty.")
    if difficulty not in _PUBLISHABLE_DIFFICULTIES:
        raise ValueError("difficulty must be a publishable difficulty, not UNRATED.")


@dataclass(frozen=True, slots=True)
class BookPuzzle:
    """One numbered publication puzzle backed by a generated puzzle artifact."""

    number: int
    puzzle: SudokuPuzzle
    difficulty_report: DifficultyReport
    fingerprint: GridFingerprint

    def __post_init__(self) -> None:
        if type(self.number) is not int:
            raise TypeError("number must be a built-in integer.")
        if self.number < 1:
            raise ValueError("number must be positive.")
        if not isinstance(self.puzzle, SudokuPuzzle):
            raise TypeError("puzzle must be a SudokuPuzzle.")
        if self.puzzle.solution is None:
            raise ValueError("A publication puzzle must have an associated solution.")
        if not isinstance(self.difficulty_report, DifficultyReport):
            raise TypeError("difficulty_report must be a DifficultyReport.")
        _validate_publishable_difficulty(self.difficulty_report.difficulty)
        if not isinstance(self.fingerprint, GridFingerprint):
            raise TypeError("fingerprint must be a GridFingerprint.")
        if fingerprint_puzzle(self.puzzle, self.fingerprint.mode) != self.fingerprint:
            raise ValueError("fingerprint must match the publication puzzle.")


@dataclass(frozen=True, slots=True)
class BookSection:
    """One ordered, nonempty publishable difficulty section."""

    title: str
    difficulty: Difficulty
    puzzles: tuple[BookPuzzle, ...]

    def __post_init__(self) -> None:
        _validate_title(self.title)
        _validate_publishable_difficulty(self.difficulty)
        if not isinstance(self.puzzles, tuple):
            raise TypeError("puzzles must be a tuple of BookPuzzle instances.")
        if not self.puzzles:
            raise ValueError("A book section must contain at least one puzzle.")
        if not all(isinstance(puzzle, BookPuzzle) for puzzle in self.puzzles):
            raise TypeError("puzzles must contain only BookPuzzle instances.")
        if any(
            puzzle.difficulty_report.difficulty is not self.difficulty
            for puzzle in self.puzzles
        ):
            raise ValueError("Every section puzzle must match the section difficulty.")

    @property
    def first_puzzle_number(self) -> int:
        return self.puzzles[0].number

    @property
    def last_puzzle_number(self) -> int:
        return self.puzzles[-1].number


@dataclass(frozen=True, slots=True)
class BookSectionInput:
    """Trusted generated batch content and its caller-chosen editorial title."""

    title: str
    batch: PuzzleBatch

    def __post_init__(self) -> None:
        _validate_title(self.title)
        if not isinstance(self.batch, PuzzleBatch):
            raise TypeError("batch must be a PuzzleBatch.")
        _validate_publishable_difficulty(self.batch.difficulty)


@dataclass(frozen=True, slots=True)
class BookPlan:
    """A deterministic, numbered publication-content plan without page layout."""

    sections: tuple[BookSection, ...]
    deduplication_mode: FingerprintMode = FingerprintMode.DIGIT_NORMALIZED

    def __post_init__(self) -> None:
        if not isinstance(self.sections, tuple):
            raise TypeError("sections must be a tuple of BookSection instances.")
        if not self.sections:
            raise ValueError("A book plan must contain at least one section.")
        if not all(isinstance(section, BookSection) for section in self.sections):
            raise TypeError("sections must contain only BookSection instances.")
        if not isinstance(self.deduplication_mode, FingerprintMode):
            raise TypeError("deduplication_mode must be a FingerprintMode.")
        puzzles = self.puzzles
        if tuple(puzzle.number for puzzle in puzzles) != tuple(
            range(1, len(puzzles) + 1)
        ):
            raise ValueError("Book puzzle numbers must be globally sequential from 1.")
        if any(
            puzzle.fingerprint.mode is not self.deduplication_mode for puzzle in puzzles
        ):
            raise ValueError(
                "Book puzzle fingerprints must use the book deduplication mode."
            )
        if len(
            deduplicate_puzzles(
                (puzzle.puzzle for puzzle in puzzles), mode=self.deduplication_mode
            )
        ) != len(puzzles):
            raise ValueError("Book plan contains duplicate puzzle identities.")

    @property
    def puzzles(self) -> tuple[BookPuzzle, ...]:
        """Flatten sections in their supplied editorial order."""
        return tuple(puzzle for section in self.sections for puzzle in section.puzzles)

    @property
    def total_puzzle_count(self) -> int:
        return len(self.puzzles)

    @property
    def difficulty_counts(self) -> tuple[tuple[Difficulty, int], ...]:
        """Counts in stable section-independent publishable-difficulty order."""
        return tuple(
            (
                difficulty,
                sum(
                    puzzle.difficulty_report.difficulty is difficulty
                    for puzzle in self.puzzles
                ),
            )
            for difficulty in (
                Difficulty.EASY,
                Difficulty.MEDIUM,
                Difficulty.HARD,
                Difficulty.EXPERT,
            )
        )


def build_book_plan(
    sections: Iterable[BookSectionInput],
    *,
    deduplication_mode: FingerprintMode = FingerprintMode.DIGIT_NORMALIZED,
) -> BookPlan:
    """Build a numbered plan from ordered batches without rerunning engine work.

    Batch order and item order are retained exactly. Fingerprints are recomputed
    in the requested book mode before collision-safe duplicate checking.
    """
    if not isinstance(deduplication_mode, FingerprintMode):
        raise TypeError("deduplication_mode must be a FingerprintMode.")
    inputs = tuple(sections)
    if not inputs:
        raise ValueError("A book plan requires at least one section input.")
    if not all(isinstance(section, BookSectionInput) for section in inputs):
        raise TypeError("sections must contain only BookSectionInput instances.")

    built_sections: list[BookSection] = []
    prior_by_fingerprint: dict[
        GridFingerprint, list[tuple[int, int, SudokuPuzzle]]
    ] = {}
    number = 1
    for section_index, section_input in enumerate(inputs, start=1):
        batch = section_input.batch
        entries: list[BookPuzzle] = []
        for position, item in enumerate(batch.items, start=1):
            fingerprint = fingerprint_puzzle(item.puzzle, deduplication_mode)
            for first_section, first_position, first_puzzle in prior_by_fingerprint.get(
                fingerprint, []
            ):
                if (
                    len(
                        deduplicate_puzzles(
                            (first_puzzle, item.puzzle), mode=deduplication_mode
                        )
                    )
                    == 1
                ):
                    raise DuplicatePublicationPuzzleError(
                        first_section, first_position, section_index, position
                    )
            prior_by_fingerprint.setdefault(fingerprint, []).append(
                (section_index, position, item.puzzle)
            )
            entries.append(
                BookPuzzle(number, item.puzzle, item.difficulty_report, fingerprint)
            )
            number += 1
        built_sections.append(
            BookSection(section_input.title, batch.difficulty, tuple(entries))
        )
    return BookPlan(tuple(built_sections), deduplication_mode)
