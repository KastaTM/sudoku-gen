# Sudoku Gen — Engineering Instructions

## Project goal

Sudoku Gen is a deterministic Sudoku generation engine intended to
produce large collections of publication-quality Sudoku puzzles.

The system must prioritize correctness, reproducibility, testability,
and maintainability over premature performance optimization.

## Current scope

We are currently implementing Phase 1: the Sudoku generation engine.

Do not implement:

- PDF generation
- Amazon KDP integration
- web interfaces
- databases
- cloud infrastructure
- APIs
- authentication
- UI

unless explicitly requested.

## Python

Target Python 3.12+.

Use modern Python typing.

Prefer:

- dataclasses
- enums
- pathlib
- immutable data structures
- small pure functions

Avoid unnecessary third-party dependencies.

## Sudoku representation

A Sudoku grid contains exactly 81 integer cells.

Allowed values:

- 0 = empty
- 1-9 = filled cell

The canonical internal representation should be immutable.

Do not silently accept malformed Sudoku grids.

## Architecture

Keep these responsibilities separate:

- models: domain objects
- validation: Sudoku validity checks
- solver: mathematical solving and solution counting
- generator: solved-grid and puzzle generation
- difficulty: human-oriented difficulty analysis
- storage: serialization
- cli: command-line interface

The solver must not depend on the generator.

The generator may depend on the solver.

Difficulty analysis must remain independent from puzzle generation
whenever possible.

## Determinism

Never use module-level random state for puzzle generation.

All randomness must come from an explicit seeded random number generator.

Given the same:

- generator version
- configuration
- seed

generation should produce the same result.

## Sudoku correctness

A publishable puzzle must:

1. be a valid 9x9 Sudoku puzzle;
2. contain only values 0-9;
3. have a valid complete solution;
4. have exactly one solution;
5. have puzzle clues consistent with its solution.

Never weaken uniqueness validation for performance.

## Solver

The mathematical solver must support:

- solving a puzzle;
- detecting unsolvable puzzles;
- counting solutions;
- stopping solution counting after a configurable limit.

Uniqueness checks should normally stop after finding two solutions.

## Testing

Every feature or bug fix must include tests.

Use pytest.

Use Hypothesis where property-based testing provides meaningful value.

Tests should cover:

- normal cases;
- malformed input;
- edge cases;
- deterministic behavior;
- Sudoku invariants.

Avoid tests that depend on random behavior without an explicit seed.

## Quality checks

Before considering work complete, run:

uv run ruff format .
uv run ruff check .
uv run mypy src
uv run pytest

All must pass.

## Development rules

Work in small increments.

Do not perform unrelated refactors.

Do not add dependencies unless clearly justified.

Do not optimize before measuring.

Prefer clear code over clever code.

Do not duplicate Sudoku logic across modules.

Document non-obvious algorithms and invariants.

## Codex workflow

For substantial changes:

1. inspect the existing repository;
2. explain the proposed implementation plan;
3. implement the smallest coherent change;
4. add/update tests;
5. run quality checks;
6. summarize what changed and any design decisions.

If requirements conflict with existing architecture, flag the conflict
before making a large architectural change.
