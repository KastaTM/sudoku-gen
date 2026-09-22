# Sudoku Gen

A deterministic Sudoku generation engine intended to produce publication-quality
puzzles. Phase 1.9 adds deterministic difficulty reports derived from human-style
solving traces, alongside the immutable domain model, rule checks, mathematical
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

`sudoku_gen.human_solver` records placements and candidate eliminations. The
mathematical `solve()` uses backtracking to find a completion;
`solve_logically()` applies supported logical techniques and may stop before
completion. It uses no guessing, recursive search, backtracking, or associated
`SudokuPuzzle.solution`.

```python
from sudoku_gen.human_solver import LogicalState, apply_step, solve_logically
from sudoku_gen.models import Grid

grid = Grid.from_string(
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
)
result = solve_logically(grid)
assert result.solved

# Replay placements and eliminations, preserving the same candidate state.
state = LogicalState.from_grid(grid)
for step in result.steps:
    state = apply_step(state, step)
assert state == result.state
```

- `solve_logically(grid) -> LogicalSolveResult` remains the main entry point and
  manages candidate state automatically. It also accepts a `LogicalState` to
  resume earlier reductions.
- `next_step(grid_or_state) -> LogicalStep | None` returns the first supported
  move, or `None` if solved or stuck. Passing a `Grid` starts with fresh candidates;
  pass a `LogicalState` to retain eliminations.
- `apply_step(state, step) -> LogicalState` validates and applies either action.
  The Phase 1.7 convenience call `apply_step(grid, placement) -> Grid` still works.
  Applying an elimination to a bare `Grid` raises `TypeError`: a grid cannot
  retain candidate reductions.

`LogicalState(grid, candidates)` is immutable and hashable. Its candidate data is
an 81-entry row-major tuple of frozensets; filled cells have empty sets. Each empty
cell's set must be a subset of `candidates(grid, row, column)`. The constructor
checks types, shape, and this subset invariant, but cannot certify the deduction
history of manually supplied reductions. `LogicalState.from_grid(grid)` initializes
the state using the unchanged mathematical `candidates()` API.

Placements create a new grid and intersect every old candidate set with the
candidates permitted by that grid. Previously eliminated candidates are never
restored. Eliminations remove candidates without changing the grid. An empty set
on an empty cell represents a contradiction, not a filled cell.

The immutable, hashable action records are:

- `SolveStep(technique, row, column, value)`, also named `PlacementStep`, retains
  the Phase 1.7 placement constructor and accepts the two Single techniques.
- `CandidateElimination(row, column, value)` identifies one candidate removal.
- `EliminationStep(technique, eliminations)` contains a nonempty tuple of unique
  removals, canonicalized by row, column, then digit. It accepts the four new
  elimination techniques. `LogicalStep` is the union of the two action types.

Coordinates remain built-in integers in `0..8` (`TypeError` for other types,
`IndexError` outside the range); digits must be built-in integers in `1..9`
(`TypeError` or `ValueError`). `apply_step()` also checks that targets are empty,
affected candidates exist, and the declared technique justifies the complete
step. Fabricated, stale, partial, or overextended deductions raise `ValueError`.
Any justified step may be applied explicitly, regardless of detection priority.

The exact global priority is:

1. **Naked Single**: one candidate in a cell, scanning cells row-major.
2. **Hidden Single**: one possible cell for a digit in a unit.
3. **Naked Pair**: exactly two cells with the same two candidates; remove those
   digits from other cells in the unit. Three matching cells are not a pair.
4. **Hidden Pair**: two digits occur in exactly the same two cells; remove other
   candidates from those cells.
5. **Pointing**: a box's two or three candidate positions for a digit share a
   row or column; remove that digit from the line outside the box.
6. **Box-Line Reduction (Claiming)**: a line's two or three candidate positions
   for a digit share a box; remove it from that box outside the line.

Hidden Singles and both pair techniques visit rows `0..8`, columns `0..8`, then
boxes in row-major order. Within each unit they visit ascending digits or
lexicographically ascending digit pairs. Pointing visits boxes row-major, then
digits ascending, checking the row before the column. Claiming visits rows before
columns, each by ascending index, then ascending digits. Elimination techniques
report only deductions that actually remove candidates. After every step the
solver restarts at Naked Singles, so newly enabled singles take priority.

`LogicalSolveResult` exposes final `state`, derived `grid`, an immutable `steps`
tuple in application order, and `status`. It is immutable and hashable. The old
`LogicalSolveResult(grid, steps, status)` constructor remains available for
placement-only logs; mixed logs require `state=final_state` to retain reductions.
Its `solved` property derives from `LogicalSolveStatus`:

- `SOLVED`: the grid is a valid complete solution. An already solved input returns
  zero steps.
- `STUCK`: the grid is incomplete and no supported technique can progress.
  This does not establish solvability or uniqueness.
- `CONTRADICTION`: Sudoku rule conflicts or an empty cell with no candidates were
  detected. The result retains the current state and all successfully applied
  steps, including zero steps for an invalid starting grid.

`next_step()` and `apply_step()` raise the existing `InvalidGridError` on these
contradictory starting states. The logical solver reports them as `CONTRADICTION`.
These are local checks: an unsatisfiable puzzle without a detected contradiction
can return `STUCK`. Mathematical solvability and uniqueness remain the existing
solver's responsibility. Difficulty analysis uses this trace and status;
generation filtering is not implemented.

## Difficulty rating

```python
from sudoku_gen.difficulty import Difficulty, rate_difficulty
from sudoku_gen.models import Grid

grid = Grid.from_string(
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
)
report = rate_difficulty(grid)
assert report.difficulty is Difficulty.EASY
assert report.score == 51  # 51 Naked Singles, without elimination steps.
```

`rate_difficulty(grid: Grid) -> DifficultyReport` calls `solve_logically()` exactly
once and derives all metrics from that result. It uses neither clue count nor
mathematical search depth, and does not invoke the mathematical solver or check
uniqueness. `rate_logical_result(result: LogicalSolveResult) -> DifficultyReport`
analyzes an existing trusted result without solving or replaying it. That helper
trusts the supplied trace and status; a resumed solve rates only its recorded
suffix. Use the original grid to rate a complete puzzle.

`DifficultyReport` is immutable and hashable, with these fields:

- `difficulty`: `EASY`, `MEDIUM`, `HARD`, `EXPERT`, or `UNRATED`.
- `score`: integer trace effort under the formula below.
- `hardest_technique`: highest explicit severity used, or `None` for zero steps.
- `step_count`, `placement_count`, and `elimination_step_count`.
- `candidate_elimination_count`: individual removals in elimination steps.
- `logical_status`: the original `SOLVED`, `STUCK`, or `CONTRADICTION` status.

Severity, step weights, and classification bands are explicit policy tables,
independent of enum declaration order and technique detection priority:

| Technique | Severity rank | Weight per step | Band when hardest used |
| --- | --- | --- | --- |
| Naked Single | 1 | 1 | Easy, subject to singles effort budget |
| Hidden Single | 2 | 2 | Easy, subject to singles effort budget |
| Naked Pair | 3 | 4 | Medium |
| Hidden Pair | 4 | 5 | Hard |
| Pointing | 5 | 6 | Hard |
| Box-Line Reduction | 6 | 7 | Expert |

The score is **sum of all step weights + candidate_elimination_count**. Every
placement or elimination contributes one step weight, so longer traces already
cost more. Each explicit candidate removal adds one point. Routine candidate
updates caused by placements are not counted as elimination actions. For example,
one Naked Pair step removing four candidates contributes one elimination step,
four removals, and a score of `4 + 4 = 8`.

Only `SOLVED` traces receive a normal classification. Their hardest technique
sets the band in the table, with one complexity adjustment: singles-only traces
scoring **at most 81 are Easy**, and those scoring **82 or more are Medium**.
The initial Easy budget is one point per board cell, so all Naked-Single-only
traces fit; longer traces relying on double-weight Hidden Singles can exceed it.
This is a simple policy choice, not an empirically fitted threshold. Higher
technique bands cannot be reduced by a short trace or low score. Score describes
effort within the policy and does not globally order the difficulty labels.

An already valid completed grid is Easy with score `0`, zero counts, and no
hardest technique. `STUCK` and `CONTRADICTION` are always **Unrated**, preserving
the score and metrics of any successful partial trace for diagnostics. A stuck
puzzle is not automatically Expert and may be either unsupported or unsatisfiable.

This is Sudoku Gen's first internal rating model. Identical grids produce
identical reports for the same logical engine and rating policy. Ratings describe
the deterministic trace actually selected, not proof that no easier solving path
exists. They are not calibrated to commercial publishers or universal human
difficulty; future calibration may adjust weights and thresholds. Reports are
derived on demand and are not stored in `SudokuPuzzle`.

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
are not guaranteed. Clue count is not a difficulty rating. Rate the resulting
grid separately, or use bounded targeted generation:

```python
from sudoku_gen.difficulty import Difficulty
from sudoku_gen.generator import generate_puzzle_for_difficulty

generated = generate_puzzle_for_difficulty(
    Difficulty.MEDIUM, seed=2026, target_clues=30, max_attempts=100
)
assert generated.difficulty_report.difficulty is Difficulty.MEDIUM
puzzle = generated.puzzle
```

`generate_puzzle_for_difficulty(difficulty, *, seed=None, target_clues=30,
max_attempts=100) -> DifficultyGeneratedPuzzle` repeatedly composes the existing
unique puzzle generator with `rate_difficulty()`. It accepts only `EASY`,
`MEDIUM`, `HARD`, and `EXPERT`, and requires an exact match. `UNRATED` cannot be
requested. The immutable result contains `puzzle`, the exact
`difficulty_report` used to accept it, and the one-based `attempts` count.

The search is always bounded. If no candidate matches in `max_attempts`, it raises
`DifficultyGenerationError`, a `SudokuError`, whose message includes the requested
difficulty and exhausted bound. It never returns a closest or final nonmatching
candidate. `max_attempts` must be a built-in integer at least `1`; booleans and
other types raise `TypeError`, and lower values raise `ValueError`.

One local `Random(seed)` supplies a fresh random component for each candidate seed;
the attempt number is encoded as well, so no attempt can repeat a candidate seed.
Thus the same explicit seed, difficulty, target clues, attempt bound, and generator
version traverse the same candidates and yield the same accepted result or bounded
failure. It does not use or change Python's module-level random state. Individual
candidate seeds are implementation details and are not exposed by the result.

Target clue count and difficulty remain separate controls: the normal generator
semantics still make `target_clues` a lower bound, and actual clues may be higher.
Each candidate is generated once and rated once. A uniquely solvable candidate that
the current human solver rates `UNRATED` simply does not match and consumes one
attempt. Targeting `EASY` with `target_clues=81` can succeed because completed
grids rate Easy with score zero; targeting a harder label at 81 naturally exhausts
the bound. Generator filtering beyond this bounded exact-match API and clue-pattern
symmetry are not implemented.

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
Human-solver tests independently check singles, pairs in all unit types,
Pointing/Claiming in both directions, boundaries, false positives, no-op
suppression, deterministic priority, and elimination-to-single cascades. Mixed
logs replay to the exact final grid, candidate sets, and status. State validation
tests cover immutable data and fabricated moves. Bounded seeded properties check
clue and solution preservation, candidate subsets, and absence of candidate
resurrection.
Difficulty tests cover exact trace metrics, every technique and rating band,
the singles effort boundary, partial unrated traces, real completed puzzles,
one-solve accounting, repeatability, and bounded score/severity monotonicity.
Targeted-generation tests cover exact matching for each normal difficulty,
deterministic attempt progression, bounded exhaustion, single rating per candidate,
global-random isolation, immutable results, and a real completed Easy generation.

## Repository layout

```text
src/sudoku_gen/__init__.py    Package scaffold
src/sudoku_gen/models.py      Immutable Grid and SudokuPuzzle domain objects
src/sudoku_gen/exceptions.py  Typed domain errors
src/sudoku_gen/validation.py  Cell/unit access and Sudoku rule checks
src/sudoku_gen/candidates.py  Local immutable candidate sets
src/sudoku_gen/solver.py      Solving, capped counting, and uniqueness checks
src/sudoku_gen/human_solver.py  Logical solving, checked actions, and state replay
src/sudoku_gen/_logical_models.py  Immutable logical state and action records
src/sudoku_gen/_logical_techniques.py  Pure single, pair, and box/line deductions
src/sudoku_gen/difficulty.py  Explicit trace-based difficulty policy and reports
src/sudoku_gen/generator.py   Seeded generation, carving, and bounded rating targeting
tests/test_package.py        Package import smoke test
tests/test_models.py         Domain model tests and serialization properties
tests/test_validation.py     Sudoku rules, coordinates, and clue-removal property
tests/test_candidates.py     Candidate rules and cell-access behavior
tests/test_solver.py         Solving, backtracking, and solution invariants
tests/test_solution_counting.py  Counts, uniqueness, and early termination
tests/test_generator.py      Seeded generation and carving invariants
tests/test_human_techniques.py  Independent single detection and priority fixtures
tests/test_human_solver.py    Logical solving, replay, errors, and invariants
tests/test_elimination_techniques.py  Pair and box/line deduction fixtures
tests/test_logical_state.py   Candidate-state validation and replay compatibility
tests/test_logical_replay.py  Mixed logs and candidate-preservation properties
tests/test_difficulty.py     Exact metrics, classification boundaries, and properties
tests/test_difficulty_puzzles.py  Real puzzle ratings and conservative status handling
tests/test_difficulty_generation.py  Bounded exact-difficulty generation
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
