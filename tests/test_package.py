"""Smoke tests for the development package layout."""

from pathlib import Path

import sudoku_gen


def test_package_imports_from_src() -> None:
    """The editable installation exposes the package from the src directory."""
    assert sudoku_gen.__file__ is not None
    project_root = Path(__file__).resolve().parents[1]
    assert (
        Path(sudoku_gen.__file__).resolve()
        == project_root / "src" / "sudoku_gen" / "__init__.py"
    )
