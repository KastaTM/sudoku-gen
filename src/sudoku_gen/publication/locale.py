"""Editorial text resources for book rendering.

Every user-visible string a renderer needs lives here, per locale. There is
no fallback: a locale that lacks a key cannot be constructed, and an unknown
locale code raises. The locale never influences puzzle identity or difficulty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from string import Formatter

from sudoku_gen.difficulty import Difficulty
from sudoku_gen.exceptions import PublicationError

_PUBLISHABLE = (
    Difficulty.EASY,
    Difficulty.MEDIUM,
    Difficulty.HARD,
    Difficulty.EXPERT,
)
_CODE_PATTERN = re.compile(r"^[a-z]{2}-[A-Z]{2}$")


class UnknownLocaleError(PublicationError):
    """A requested locale code has no registered editorial resources."""


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string.")


def _require_number_template(name: str, value: str) -> None:
    _require_text(name, value)
    fields = [field for _, field, _, _ in Formatter().parse(value) if field is not None]
    if fields != ["number"]:
        raise ValueError(f"{name} must contain exactly one {{number}} placeholder.")


@dataclass(frozen=True, slots=True)
class BookLocale:
    """Complete set of renderer-visible editorial strings for one locale."""

    code: str
    puzzle_page_header: str
    puzzle_title: str
    solution_page_header: str
    solution_title: str
    contents_heading: str
    copyright_heading: str
    instructions_heading: str
    difficulty_labels: tuple[tuple[Difficulty, str], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not _CODE_PATTERN.match(self.code):
            raise ValueError("code must look like 'es-ES'.")
        _require_text("puzzle_page_header", self.puzzle_page_header)
        _require_text("solution_page_header", self.solution_page_header)
        _require_text("contents_heading", self.contents_heading)
        _require_text("copyright_heading", self.copyright_heading)
        _require_text("instructions_heading", self.instructions_heading)
        _require_number_template("puzzle_title", self.puzzle_title)
        _require_number_template("solution_title", self.solution_title)
        if not isinstance(self.difficulty_labels, tuple):
            raise TypeError("difficulty_labels must be a tuple of pairs.")
        covered = [difficulty for difficulty, _ in self.difficulty_labels]
        if sorted(covered, key=_PUBLISHABLE.index) != list(_PUBLISHABLE):
            raise ValueError(
                "difficulty_labels must cover each publishable difficulty once."
            )
        for difficulty, label in self.difficulty_labels:
            _require_text(f"difficulty label {difficulty.name}", label)

    def difficulty_label(self, difficulty: Difficulty) -> str:
        """Return the reader-facing label; UNRATED is never publishable."""
        for candidate, label in self.difficulty_labels:
            if candidate is difficulty:
                return label
        raise ValueError("difficulty must be a publishable difficulty.")

    def puzzle_label(self, number: int) -> str:
        return self.puzzle_title.format(number=number)

    def solution_label(self, number: int) -> str:
        return self.solution_title.format(number=number)


ES_ES = BookLocale(
    code="es-ES",
    puzzle_page_header="SUDOKUS",
    puzzle_title="Sudoku #{number}",
    solution_page_header="SOLUCIONES",
    solution_title="Solución #{number}",
    contents_heading="Contenido",
    copyright_heading="Información",
    instructions_heading="Instrucciones",
    difficulty_labels=(
        (Difficulty.EASY, "Fácil"),
        (Difficulty.MEDIUM, "Medio"),
        (Difficulty.HARD, "Difícil"),
        (Difficulty.EXPERT, "Experto"),
    ),
)

# Test locale only: not reviewed by a native speaker, never used for sale.
EN_US = BookLocale(
    code="en-US",
    puzzle_page_header="SUDOKU PUZZLES",
    puzzle_title="Puzzle #{number}",
    solution_page_header="SOLUTIONS",
    solution_title="Solution #{number}",
    contents_heading="Contents",
    copyright_heading="Information",
    instructions_heading="Instructions",
    difficulty_labels=(
        (Difficulty.EASY, "Easy"),
        (Difficulty.MEDIUM, "Medium"),
        (Difficulty.HARD, "Hard"),
        (Difficulty.EXPERT, "Expert"),
    ),
)

_LOCALES = {locale.code: locale for locale in (ES_ES, EN_US)}


def get_book_locale(code: str) -> BookLocale:
    """Return a registered locale; unknown codes raise, they never fall back."""
    try:
        return _LOCALES[code]
    except (KeyError, TypeError):
        raise UnknownLocaleError(
            f"No editorial resources for locale {code!r}."
        ) from None


def available_book_locales() -> tuple[str, ...]:
    return tuple(sorted(_LOCALES))
