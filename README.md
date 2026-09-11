# Sudoku Gen

A deterministic Sudoku generation engine intended to produce publication-quality
puzzles. Phase 1.7 adds recorded human-style logical solving with Naked and Hidden
Singles to the immutable domain model, rule checks, candidates, mathematical
solver, and seeded puzzle generation. Application features have not been
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
`SudokuPuzzle` contains `grid: Grid` and an optional `solution: Grid | None = None`.
Existing `SudokuPuzzle(grid=...)` construction remains supported; generated puzzles
always include their completed solution. Supplying a non-Grid solution raises
`TypeError`, and disagreeing non-zero clues raise `ValueError`. Direct construction
does not validate Sudoku rules or uniqueness; the generator guarantees these for
its results.
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
puzzles with multiple solutions. `solve()` stops after the first solution.

The same module also provides:

- `count_solutions(grid: Grid, limit: int = 2) -> int`: count solutions up to the
  requested cap. Invalid or unsatisfiable Sudoku grids return `0`. A result below
  the cap is exact; a result equal to the cap means at least that many solutions
  exist. The default cap of `2` distinguishes zero, one, and multiple solutions.
- `has_unique_solution(grid: Grid) -> bool`: return whether exactly one solution
  exists, stopping as soon as a second is found. This is equivalent to
  `count_solutions(grid, limit=2) == 1`.

`limit` must be a built-in integer of at least `1`. Other types, including booleans,
raise `TypeError`; zero and negative integers raise `ValueError`. The limit is
checked before grid validity. Counting with `limit=1` can establish that a solution
exists, but cannot establish uniqueness.

All three functions share one recursive search that yields completed solutions
on demand. Counting stops immediately at the cap; it does not collect or enumerate
all solutions first. Each call validates the starting grid once, preserves the
input and its clues, and uses the same deterministic search order.

## Human-style logical solving

`sudoku_gen.human_solver` derives explicit logical placements from the grid using
only **Naked Singles** and **Hidden Singles**. The mathematical `solve()` uses
backtracking to find a completion; `solve_logically()` records supported logical
moves and may stop before completion. It uses no guessing, recursive search,
backtracking, or associated `SudokuPuzzle.solution`.

```python
from sudoku_gen.human_solver import apply_step, next_step, solve_logically
from sudoku_gen.models import Grid

grid = Grid.from_string(
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
)
step = next_step(grid)
if step is not None:
    updated = apply_step(grid, step)
result = solve_logically(grid)
assert result.solved
```

- `next_step(grid: Grid) -> SolveStep | None` returns the first supported move,
  or `None` if the grid is solved or no supported move exists.
- `apply_step(grid: Grid, step: SolveStep) -> Grid` returns a new grid. It checks
  that the target is empty, the digit is a legal candidate, and the declared
  technique justifies it. Any justified move is accepted, even if it is not the
  first move in detection order. These failures raise `ValueError`.
- `solve_logically(grid: Grid) -> LogicalSolveResult` repeatedly detects and
  applies one move, recalculating candidates after every placement. The recorded
  steps can be replayed with `apply_step()` to reproduce the result grid exactly.

`SolveStep(technique, row, column, value)` is an immutable, hashable dataclass.
`Technique` has `NAKED_SINGLE` and `HIDDEN_SINGLE`. Coordinates are zero-based,
built-in integers in `0..8`; invalid types raise `TypeError` and out-of-range
indices raise `IndexError`. Values must be built-in integers in `1..9`:
invalid types raise `TypeError` and out-of-range digits raise `ValueError`.
Construction validates these fields; `apply_step()` validates their justification
on the supplied grid. A Hidden Single must be unique in at least one containing
unit, and may also qualify as a Naked Single.

Detection always prefers Naked Singles, visiting empty cells in row-major order.
A Naked Single has exactly one candidate. Hidden Singles follow in rows `0..8`,
then columns `0..8`, then boxes in row-major order. Within each unit, missing digits
are checked in ascending order. A Hidden Single's digit appears in exactly one
empty cell's candidate set in that unit, even when that cell has other candidates.
Both techniques reuse `candidates()`.

`LogicalSolveResult(grid, steps, status)` is immutable and hashable; `steps` is a
tuple in application order. Its `solved` property derives from
`LogicalSolveStatus`:

- `SOLVED`: the grid is a valid complete solution. An already solved input returns
  zero steps.
- `STUCK`: the grid is incomplete and neither supported technique can progress.
  This does not establish solvability or uniqueness.
- `CONTRADICTION`: Sudoku rule conflicts or an empty cell with no candidates were
  detected. The result retains the current grid and all successfully applied
  steps, including zero steps for an invalid starting grid.

`next_step()` and `apply_step()` raise the existing `InvalidGridError` on these
contradictory starting states. The logical solver reports them as `CONTRADICTION`.
These are local checks: an unsatisfiable puzzle without a detected contradiction
can return `STUCK`. Mathematical solvability and uniqueness remain the existing
solver's responsibility. Difficulty labels, scores, and generation filtering are
not implemented.

## Generation

```python
from sudoku_gen.generator import generate_puzzle, generate_solution
from sudoku_gen.validation import clue_count

solution = generate_solution(seed=1234)
puzzle = generate_puzzle(seed=1234, target_clues=30)
assert puzzle.solution == solution
actual_clues = clue_count(puzzle.grid)
```

- `generate_solution(seed: int | None = None) -> Grid` constructs a valid completed
  Sudoku by randomized backtracking. It selects among equally constrained MRV
  cells and shuffles candidate digits during construction.
- `generate_puzzle(*, seed: int | None = None, target_clues: int = 30) -> SudokuPuzzle`
  constructs a solution, then attempts clue removals in a shuffled order. Every
  accepted removal must pass `has_unique_solution()`, which stops upon finding a
  second solution. The returned clues agree with the associated solution, and
  solving the generated puzzle recovers that solution.
- `clue_count(grid: Grid) -> int` derives the number of non-zero cells. The count
  is not stored as redundant model state.

Each generation call uses its own `Random(seed)`. Puzzle generation uses that one
RNG for both construction and removal ordering; it neither uses nor modifies
Python's global random state. The same explicit seed and parameters reproduce the
same result for the same generator version. Seeds must be built-in integers or
`None`; other types, including booleans, raise `TypeError`. `None` allows normal
nondeterministic seeding. Different seeds can produce different boards, but they
are not guaranteed to be distinct.

`target_clues` must be a built-in integer in `17..81`. Other types, including
booleans, raise `TypeError`; out-of-range integers raise `ValueError`. A single
removal pass stops at the requested count or after all positions have been tried.
The result may contain **more clues than the target**, but never fewer. Use
`clue_count(puzzle.grid)` to obtain the actual count. Target `81` returns a complete
puzzle with its solution.

Generated puzzles are uniquely solvable; exact clue targets and minimal puzzles
are not guaranteed. Clue count is not a difficulty rating. Difficulty scoring and
clue-pattern symmetry are outside this phase.

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
Capped-counting tests verify a four-cell puzzle with exactly two completions,
limit validation, and immediate stopping through guarded solution validation.
Generator tests cover seeded reproducibility, global RNG isolation, solution
validity, uniqueness-preserving removals, target semantics, and clue/solution
agreement. A small seeded property test checks generation invariants over bounded
seeds and targets.
Human-solver tests independently check row, column, and box Hidden Singles,
Naked Singles, deterministic technique priority, checked move application,
contradiction and stuck results, immutable data, and exact step replay. Bounded
seeded properties check legal placements, intermediate validity, and clue
preservation.

## Repository layout

```text
src/sudoku_gen/__init__.py    Package scaffold
src/sudoku_gen/models.py      Immutable Grid and SudokuPuzzle domain objects
src/sudoku_gen/exceptions.py  Typed domain errors
src/sudoku_gen/validation.py  Cell/unit access and Sudoku rule checks
src/sudoku_gen/candidates.py  Local immutable candidate sets
src/sudoku_gen/solver.py      Solving, capped counting, and uniqueness checks
src/sudoku_gen/human_solver.py  Recorded Naked and Hidden Single placements
src/sudoku_gen/generator.py   Seeded solution construction and puzzle carving
tests/test_package.py        Package import smoke test
tests/test_models.py         Domain model tests and serialization properties
tests/test_validation.py     Sudoku rules, coordinates, and clue-removal property
tests/test_candidates.py     Candidate rules and cell-access behavior
tests/test_solver.py         Solving, backtracking, and solution invariants
tests/test_solution_counting.py  Counts, uniqueness, and early termination
tests/test_generator.py      Seeded generation and carving invariants
tests/test_human_techniques.py  Independent single detection and priority fixtures
tests/test_human_solver.py    Logical solving, replay, errors, and invariants
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
