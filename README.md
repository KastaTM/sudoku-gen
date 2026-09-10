# Sudoku Gen

A deterministic Sudoku generation engine intended to produce publication-quality
puzzles. Phase 1.4 provides the immutable core domain model, its canonical text
representation, standard 9x9 Sudoku rule checks, local candidate calculation, and
a deterministic solver. Generation and application features have not been
implemented.

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

## Candidates and cell access

`sudoku_gen.validation` also provides:

- `cell_value(grid, row, column)`: read a cell, including zero for an empty cell.
- `box_coordinates(row, column)`: get the cell's `(box_row, box_column)` in `0..2`.
- `empty_cells(grid)`: get an immutable tuple of empty-cell coordinates in
  row-major order.

These use the same coordinate types, ranges, and errors as unit access.

```python
from sudoku_gen.candidates import candidates
from sudoku_gen.models import Grid
from sudoku_gen.validation import empty_cells

grid = Grid.from_string("0" * 81)
row, column = empty_cells(grid)[0]
assert candidates(grid, row, column) == frozenset(range(1, 10))
```

`candidates(grid, row, column)` returns a `frozenset[int]`: digits `1..9` minus
the non-zero digits present in the current row, column, and box. Filled cells
return an empty frozenset. An empty cell can also have no legal candidates;
use `cell_value()` or iterate `empty_cells()` to distinguish that case.

Candidate calculation uses only local unit values and does not call whole-grid
validation. Even on a conflicting grid, it excludes currently used peer digits;
it does not establish solvability or resolve conflicts. It never modifies the
grid or fills cells. Call `is_valid_grid()` separately when rule validation is
needed. Candidate sets have deterministic contents; their iteration order is
not an API guarantee.

## Solver

```python
from sudoku_gen.models import Grid
from sudoku_gen.solver import solve

grid = Grid.from_string(
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
)
solution = solve(grid)
```

`solve(grid: Grid) -> Grid | None` returns one valid completed grid while preserving
all clues and the original input. An already solved valid grid is returned
unchanged. Starting grids with Sudoku rule conflicts and valid-looking grids with
no solution both return `None`. Representation errors remain the responsibility
of `Grid` construction.

The solver uses recursive backtracking with Minimum Remaining Values (MRV): it
chooses the empty cell with the fewest candidates, breaks ties in row-major order,
and tries digits in ascending order. An empty cell with no candidates ends the
current branch immediately. The starting grid is validated once before search;
each tentative placement creates a new `Grid` directly from its cells. Complete
results are checked with `is_valid_solution()`.

Repeated calls produce the same solution, including for the empty grid and other
puzzles with multiple solutions. The solver finds one solution; it does not count
solutions or test uniqueness.

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
consistency. Candidate tests cover local constraints, cell and box coordinates,
filled and blocked cells, and properties of candidates on valid partial grids.
Solver tests cover known puzzles, required backtracking, invalid and unsatisfiable
states, determinism, and clue preservation. Seeded property tests solve grids with
clues removed from a known solution, checking validity rather than assuming
uniqueness.

## Repository layout

```text
src/sudoku_gen/__init__.py    Package scaffold
src/sudoku_gen/models.py      Immutable Grid and SudokuPuzzle domain objects
src/sudoku_gen/exceptions.py  Typed domain errors
src/sudoku_gen/validation.py  Cell/unit access and Sudoku rule checks
src/sudoku_gen/candidates.py  Local immutable candidate sets
src/sudoku_gen/solver.py      Deterministic MRV backtracking solver
tests/test_package.py        Package import smoke test
tests/test_models.py         Domain model tests and serialization properties
tests/test_validation.py     Sudoku rules, coordinates, and clue-removal property
tests/test_candidates.py     Candidate rules and cell-access behavior
tests/test_solver.py         Solving, backtracking, and solution invariants
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
