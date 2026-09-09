# Sudoku Gen

A deterministic Sudoku generation engine intended to produce publication-quality
puzzles. Phase 1.2 provides the immutable core domain model, its canonical text
representation, and standard 9x9 Sudoku rule checks. Solving, generation, and
application features have not been implemented.

## Domain model

```python
from sudoku_gen.models import Grid, SudokuPuzzle

grid = Grid.from_string("0" * 81)
puzzle = SudokuPuzzle(grid=grid)
assert puzzle.grid.to_string() == "0" * 81
```

`Grid(cells=...)` requires a tuple of exactly 81 built-in integers from 0 through 9
in row-major order. Zero means empty. `Grid.from_string()` accepts exactly 81 ASCII
digits; `to_string()` returns that same canonical format. Whitespace, separators,
Unicode digits, booleans, and implicit value conversions are rejected. Malformed
grids raise `sudoku_gen.exceptions.InvalidGridError`, which is both a `SudokuError`
and a `ValueError`.

Both `Grid` and `SudokuPuzzle` are immutable, hashable dataclasses.
`SudokuPuzzle` contains only a `grid` field and requires a `Grid` instance.
The model enforces shape and cell values; it does not check row, column, or box
conflicts, solvability, or uniqueness. Text conversion belongs to this value
object; it does not read or write files.

## Sudoku rules

Rule checks live in `sudoku_gen.validation` and accept an existing `Grid`.
They are pure functions and rely on the model's representation checks.

| Function | Behavior |
| --- | --- |
| `row_values(grid, row)` | Row values from left to right, as a tuple. |
| `column_values(grid, column)` | Column values from top to bottom, as a tuple. |
| `box_values(grid, box_row, box_column)` | Box values in row-major order, as a tuple. |
| `has_nonzero_duplicates(values)` | Whether a unit contains a repeated non-zero value. |
| `is_valid_grid(grid)` | Whether every row, column, and box has unique non-zero values. |
| `is_complete(grid)` | Whether the grid contains no zeroes, regardless of conflicts. |
| `is_valid_solution(grid)` | Whether the grid is both complete and valid. |

Row and column indices are zero-based (`0..8`). Box coordinates are also zero-based:
`(0, 0)` is the top-left box and `(2, 2)` the bottom-right box. Each box coordinate
must be in `0..2`. Coordinates must be built-in integers; other types, including
booleans, raise `TypeError`. Out-of-range coordinates raise `IndexError`.

Repeated zeroes are allowed, so an empty grid is valid and incomplete. Rule
consistency alone does not establish solvability or solution uniqueness.

## Development setup

Install Python 3.12+ and `uv`, then run from the repository root:

```sh
uv sync --locked
```

This creates `.venv`, installs `sudoku_gen` in editable mode, and installs pytest,
pytest-cov, Hypothesis, Ruff, and mypy. There are no runtime dependencies.
The existing `uv_build` backend handles package installation and builds.
`.python-version` selects Python 3.12 for local development; `uv.lock` records the
resolved dependency versions and should be committed.

## Quality checks

Read [AGENTS.md](AGENTS.md) before making changes. Run the required checks from
the repository root:

```sh
uv run ruff format .
uv run ruff check .
uv run mypy src
uv run pytest
```

To collect coverage:

```sh
uv run pytest --cov --cov-report=term-missing
```

Tests cover the editable package import, grid invariants, malformed inputs,
immutability, the puzzle wrapper, unit extraction, Sudoku conflicts, completion,
and index boundaries. Seeded Hypothesis tests exercise canonical serialization
round trips and verify that removing clues from a valid solution preserves rule
consistency.

## Repository layout

```text
src/sudoku_gen/__init__.py    Package scaffold
src/sudoku_gen/models.py      Immutable Grid and SudokuPuzzle domain objects
src/sudoku_gen/exceptions.py  Typed domain errors
src/sudoku_gen/validation.py  Unit extraction and Sudoku rule checks
tests/test_package.py        Package import smoke test
tests/test_models.py         Domain model tests and serialization properties
tests/test_validation.py     Sudoku rules, coordinates, and clue-removal property
pyproject.toml               Package metadata, dev dependencies, tool configuration
uv.lock                      Resolved dependency versions
.python-version              Local Python version
.gitignore                   Generated files excluded from Git
.vscode/settings.json        Python, pytest, Ruff, and mypy editor settings
.vscode/extensions.json      Recommended development extensions
AGENTS.md                    Engineering instructions
README.md                    Project status and development workflow
```

Open the repository root in VS Code and install the recommended extensions.
The workspace settings use `.venv`, enable pytest discovery, format Python with
Ruff on save, and use the environment's Ruff and mypy installations.
