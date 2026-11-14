"""Ratchet test: no new hard-coded editorial text in the publication renderers.

Editorial text lives in ``publication/locale.py`` (``BookLocale``). This test
fails when a renderer embeds a literal word or re-cases a value instead of
reading it from the locale. ``KNOWN_DEBT`` is empty and must stay empty.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PUBLICATION_DIR = (
    Path(__file__).resolve().parents[1] / "src" / "sudoku_gen" / ("publication")
)
TEXT_KEYWORDS = frozenset({"heading", "text", "title", "label"})
CASE_METHODS = frozenset({"title", "upper", "capitalize"})
LETTER = re.compile(r"[^\W\d_]")

# (module, source of the text expression). Empty since H3/WP1a: all
# editorial text comes from BookLocale. Do not add entries.
KNOWN_DEBT: frozenset[tuple[str, str]] = frozenset()


def _is_editorial_expression(node: ast.expr) -> bool:
    """True if the expression embeds literal words or re-cases a value."""
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Constant)
            and isinstance(child.value, str)
            and LETTER.search(child.value)
        ):
            return True
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr in CASE_METHODS
        ):
            return True
    return False


def _text_expressions(call: ast.Call) -> list[ast.expr]:
    func = call.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    expressions: list[ast.expr] = []
    if name == "Text" and call.args:
        expressions.append(call.args[0])
    expressions.extend(
        keyword.value for keyword in call.keywords if keyword.arg in TEXT_KEYWORDS
    )
    return expressions


def _find_editorial_literals() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path in sorted(PUBLICATION_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for expression in _text_expressions(node):
                if _is_editorial_expression(expression):
                    found.add((path.name, ast.unparse(expression)))
    return found


def test_no_new_hardcoded_editorial_text() -> None:
    new = _find_editorial_literals() - KNOWN_DEBT
    assert not new, (
        "New hard-coded editorial text in a renderer; route it through the "
        f"locale resources instead of extending the pattern: {sorted(new)}"
    )


def test_known_debt_list_has_no_stale_entries() -> None:
    stale = KNOWN_DEBT - _find_editorial_literals()
    assert not stale, f"Remove resolved entries from KNOWN_DEBT: {sorted(stale)}"
