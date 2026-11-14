# Sudoku Gen — Engineering and Agent Instructions

Read this file before changing anything in the repository. It is the
contract between the promoter, the Orchestrator agent, and every
department or sub-agent that works on Sudoku Gen.

## Project goal

Sudoku Gen is a deterministic Sudoku generation and publication engine.
It produces large collections of publication-quality 9x9 puzzles and
composes them into print-ready books (vector interior PDF, paperback
cover PDF, manifest, and quality report).

The business hypothesis under validation is selling printed Sudoku
books, first through Amazon KDP, later in several languages
(es, en, fr, de). Nothing has been published or sold yet.

The system must prioritize correctness, reproducibility, testability,
and maintainability over premature performance optimization.

## Current status and scope

| Milestone | Status | Evidence |
| --- | --- | --- |
| H0 — Sudoku engine (historical phase 1) | Implemented | `src/sudoku_gen/*.py`, tests |
| H1 — Editorial pipeline (historical phases 2.1–2.11) | Implemented | `src/sudoku_gen/publication/`, `scripts/create_phase_2_11_publication.py` |
| H2 — Rebaseline and agentic governance | In progress | This file, `docs/` |
| H3 — Pilot edition with foundational i18n | Approved, not started | `docs/ROADMAP.md` |

Baseline of record: tag `v0.2.0` = commit
`c05ce0c858ac36e3d2dd35762856301c25cca856` (2026-09-24).

**In scope now (H2/H3):** documentation repair, CI, localizable
editorial text resources, a persistent per-edition fingerprint registry,
manifest schema v2, and one pilot edition in `es-ES`.

**Out of scope unless the promoter approves a business case:** web
interfaces, public APIs, databases, cloud infrastructure, authentication,
UI, marketplace API integrations, paid advertising automation.

The restriction that once forbade PDF generation and KDP-related work is
lifted: both are implemented and are the core product output.

## Python

Target Python 3.12+. Dependencies are managed with `uv` and pinned in
`uv.lock`; keep the lock file committed and in sync with `pyproject.toml`.

Use modern Python typing. Prefer dataclasses, enums, pathlib, immutable
data structures, and small pure functions. Avoid unnecessary third-party
dependencies. Runtime dependencies are ReportLab and pypdf only.

## Sudoku representation

A Sudoku grid contains exactly 81 integer cells. Allowed values: `0`
(empty) and `1-9` (filled). The canonical internal representation is
immutable. Do not silently accept malformed grids.

## Architecture

Modules and their responsibilities (keep them separate):

- `models`: immutable `Grid` and `SudokuPuzzle` domain objects
- `exceptions`: typed domain errors
- `validation`: cell/unit access and Sudoku rule checks
- `candidates`: local candidate sets
- `solver`: mathematical solving, capped counting, uniqueness
- `human_solver`, `_logical_models`, `_logical_techniques`: logical
  solving with explicit techniques and replayable steps
- `difficulty`: trace-based difficulty policy and reports
- `pattern`: clue-position symmetry and pattern reports
- `fingerprint`: stable puzzle identities and deduplication
- `generator`: seeded generation, carving, bounded targeting, batches
- `quality`: batch statistics and independent invariant audits
- `benchmark`: observational timing harness
- `publication/`: book planning, page planning, geometry, vector
  rendering, SVG and PDF backends, front matter, print preflight,
  paperback cover, and the end-to-end `run_publication` /
  `export_publication` pipeline

Dependency rules:

- The solver must not depend on the generator.
- The generator may depend on the solver.
- Difficulty analysis must remain independent from puzzle generation.
- `publication/` consumes trusted engine results; it must not re-implement
  solving, rating, or fingerprinting.
- Editorial text must not be hard-coded in renderers once the locale
  resource layer (H3/WP1) exists; until then, treat the remaining
  literals (`SUDOKUS`, `SOLUCIONES`, `Sudoku #`, `Solución #`,
  `Información`, `Instrucciones`, `Contenido`, and the English
  difficulty label) as known debt, not as a pattern to extend.

## Determinism and reproducibility

Never use module-level random state. All randomness comes from an
explicit seeded `random.Random`. Given the same generator version,
configuration, and seed, generation must produce the same result.

PDF output uses ReportLab invariant mode and an embedded font so that the
same inputs produce byte-identical files. Treat a change in the
reference hashes of `scripts/create_phase_2_11_publication.py` output as
a behavior change that must be explained in the pull request.

## Sudoku correctness

A publishable puzzle must be a valid 9x9 Sudoku, contain only values
0-9, have a valid complete solution, have exactly one solution, and have
clues consistent with its solution.

Never weaken uniqueness validation, difficulty matching, or
deduplication to make generation faster or to reach a target count.
A bounded generation failure is a valid outcome; relaxing controls is not.

## Solver

The mathematical solver must support solving, detecting unsolvable
puzzles, counting solutions, and stopping after a configurable limit.
Uniqueness checks normally stop after two solutions.

## Editorial output

Local preflight (`publication/preflight.py`) and cover validation are
diagnostics. They do not certify acceptance by Amazon KDP or any printer.
Every edition intended for sale must additionally pass the channel's
official tools (KDP Print Previewer and Cover Calculator at the time of
writing), a human visual inspection, and a native-language review. See
`docs/RELEASE_CHECKLIST.md`.

## Testing

Every feature or bug fix must include tests. Use pytest, and Hypothesis
where property-based testing adds value. Tests must cover normal cases,
malformed input, edge cases, deterministic behavior, and Sudoku
invariants. Avoid tests that depend on random behavior without an
explicit seed. Do not assert machine-specific timings.

## Quality gates

Before considering work complete, run from the repository root:

```sh
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest --cov --cov-report=term-missing
```

All must pass. The same gates run in CI (`.github/workflows/ci.yml`) on
every pull request and on `main`. A gate that was not executed is
reported as **NOT VERIFIED**, never as passed.

Agents load `docs/CONTEXT_CORE.md` as their minimal briefing. The ratchet
test `tests/test_editorial_literals.py` fails on any new hard-coded editorial
text in `publication/` renderers (see ADR-0004).

## Governance for agents

- **Evidence labels.** Every significant claim in a report, issue, or
  pull request is labeled CONFIRMED (with evidence), PROMOTER INTENT,
  PROPOSAL, TO VERIFY, PENDING DECISION, or NOT VERIFIED. Never claim
  sales, publications, approvals, or test runs that did not happen.
- **Task contracts.** Substantial work is declared with an id, owner,
  baseline SHA, scope and non-scope, deliverables, acceptance criteria,
  validation, risks, dependencies, and approval gate. Status flows
  `PROPOSED → APPROVED → IN_PROGRESS → IN_REVIEW → ACCEPTED | BLOCKED |
  REJECTED`. Nobody accepts their own task.
- **Branches and pull requests.** Work on a branch cut from `main`.
  One coherent change per pull request, with the evidence (CI run,
  hashes, screenshots) in its description. Merge is allowed only when
  CI is green; the promoter may additionally require review.
- **Human approval is mandatory** for publishing to any marketplace,
  spending money, setting public prices, paid advertising, creating
  external accounts, production deployments, and any change to the
  difficulty or uniqueness policy that affects existing editions.
- **Decision log and risks.** Record decisions in `docs/DECISIONS.md`
  and risks in `docs/RISK_REGISTER.md`. The roadmap lives in
  `docs/ROADMAP.md`. Update them in the same pull request as the change
  they describe.
- **Documentation follows code.** A pull request that changes behavior
  updates `README.md` and, when relevant, this file.

## Development rules

Work in small increments. Do not perform unrelated refactors. Do not add
dependencies unless clearly justified. Do not optimize before measuring.
Prefer clear code over clever code. Do not duplicate Sudoku logic across
modules. Document non-obvious algorithms and invariants.

## Workflow for substantial changes

1. Inspect the existing repository and the current baseline.
2. Write or reference the task contract and explain the plan.
3. Implement the smallest coherent change.
4. Add or update tests.
5. Run the quality gates and keep the logs.
6. Update documentation, decisions, and risks.
7. Summarize what changed, the evidence, and any open decisions.

If requirements conflict with the existing architecture or with a
recorded decision, flag the conflict before making a large change.
