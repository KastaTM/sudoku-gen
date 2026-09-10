"""Deterministic solving, failure semantics, and immutable Sudoku invariants."""

import pytest
from hypothesis import example, given, seed, settings
from hypothesis import strategies as st

from sudoku_gen.candidates import candidates
from sudoku_gen.models import Grid
from sudoku_gen.solver import solve
from sudoku_gen.validation import (
    empty_cells,
    is_complete,
    is_valid_grid,
    is_valid_solution,
)

SOLVED_TEXT = (
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)
EASY_TEXT = (
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
)
MEDIUM_TEXT = (
    "003020600900305001001806400008102900700000008006708200002609500800203009005010300"
)
MEDIUM_SOLUTION_TEXT = (
    "483921657967345821251876493548132976729564138136798245372689514814253769695417382"
)
BACKTRACKING_TEXT = (
    "100007090030020008009400500005300900010080002400006000300000010060000007007000300"
)
BACKTRACKING_SOLUTION_TEXT = (
    "142857693536129478789463521675312984913584762428796135354678219261935847897241356"
)
BOX_CONFLICT_TEXT = (
    "123456789234567891345678912456789123567891234678912345789123456891234567912345678"
)
# The empty top-left cell requires 9 from its row, but 9 is already in its column.
BLOCKED_TEXT = "012345678" + "0" * 18 + "900000000" + "0" * 45


def assert_solution_preserves_clues(puzzle: Grid, solution: Grid | None) -> None:
    """Check the solver contract without assuming a puzzle has a unique solution."""
    assert isinstance(solution, Grid)
    assert is_complete(solution)
    assert is_valid_solution(solution)
    assert all(
        clue == 0 or clue == value
        for clue, value in zip(puzzle.cells, solution.cells, strict=True)
    )


def test_already_solved_grid_returns_an_equivalent_solution() -> None:
    grid = Grid.from_string(SOLVED_TEXT)

    assert solve(grid) == grid


@pytest.mark.parametrize(
    ("puzzle_text", "solution_text"),
    [
        pytest.param(EASY_TEXT, SOLVED_TEXT, id="easy"),
        pytest.param(MEDIUM_TEXT, MEDIUM_SOLUTION_TEXT, id="medium"),
    ],
)
def test_known_puzzles_return_their_expected_solutions(
    puzzle_text: str, solution_text: str
) -> None:
    puzzle = Grid.from_string(puzzle_text)

    result = solve(puzzle)

    assert result == Grid.from_string(solution_text)
    assert_solution_preserves_clues(puzzle, result)


@pytest.mark.parametrize("index", [0, 8, 40, 72, 80])
def test_one_missing_cell_is_restored_at_corners_and_center(index: int) -> None:
    solved = Grid.from_string(SOLVED_TEXT)
    puzzle = Grid(solved.cells[:index] + (0,) + solved.cells[index + 1 :])

    assert solve(puzzle) == solved


def test_empty_grid_returns_one_valid_solution_deterministically() -> None:
    grid = Grid((0,) * 81)

    first = solve(grid)
    second = solve(Grid((0,) * 81))

    assert_solution_preserves_clues(grid, first)
    assert second == first
    assert grid.cells == (0,) * 81


@pytest.mark.parametrize(
    ("first", "second"),
    [
        pytest.param((8, 2), (8, 3), id="row-across-box-boundary"),
        pytest.param((2, 8), (3, 8), id="column-across-box-boundary"),
        pytest.param((6, 6), (8, 8), id="box-with-distinct-row-and-column"),
    ],
)
def test_a_partial_grid_with_a_unit_conflict_has_no_solution(
    first: tuple[int, int], second: tuple[int, int]
) -> None:
    cells = [0] * 81
    for row, column in (first, second):
        cells[row * 9 + column] = 7
    grid = Grid(tuple(cells))

    assert not is_valid_grid(grid)
    assert solve(grid) is None


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("1" * 81, id="all-units-conflict"),
        pytest.param("634678912572195348" + SOLVED_TEXT[18:], id="only-rows-conflict"),
        pytest.param("354678912" + SOLVED_TEXT[9:], id="only-columns-conflict"),
        pytest.param(BOX_CONFLICT_TEXT, id="only-boxes-conflict"),
    ],
)
def test_a_complete_grid_with_conflicts_is_not_returned_as_a_solution(
    text: str,
) -> None:
    grid = Grid.from_string(text)

    assert is_complete(grid)
    assert not is_valid_grid(grid)
    assert solve(grid) is None


def test_a_valid_grid_with_an_empty_cell_without_candidates_has_no_solution() -> None:
    grid = Grid.from_string(BLOCKED_TEXT)

    assert is_valid_grid(grid)
    assert not is_complete(grid)
    assert candidates(grid, 0, 0) == frozenset()
    assert solve(grid) is None


def test_solver_backtracks_after_a_legal_candidate_proves_unsatisfiable() -> None:
    grid = Grid.from_string(BACKTRACKING_TEXT)

    # (1, 2) is the first MRV cell: its candidates are 4 and 6, with no
    # singleton cells or earlier cells tied for that minimum in this fixture.
    assert is_valid_grid(grid)
    assert candidates(grid, 1, 2) == frozenset({4, 6})
    assert all(
        len(candidates(grid, row, column)) >= 2 for row, column in empty_cells(grid)
    )
    assert all(
        len(candidates(grid, row, column)) > 2
        for row, column in empty_cells(grid)
        if (row, column) < (1, 2)
    )

    wrong_branch = Grid(grid.cells[:11] + (4,) + grid.cells[12:])
    assert is_valid_grid(wrong_branch)
    assert all(
        candidates(wrong_branch, row, column)
        for row, column in empty_cells(wrong_branch)
    )
    # This branch starts with legal candidates everywhere, yet search must
    # discover that it is unsatisfiable before trying 6 in the original grid.
    assert solve(wrong_branch) is None

    result = solve(grid)

    assert result == Grid.from_string(BACKTRACKING_SOLUTION_TEXT)
    assert_solution_preserves_clues(grid, result)
    assert grid.to_string() == BACKTRACKING_TEXT


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(EASY_TEXT, id="solvable"),
        pytest.param(SOLVED_TEXT, id="already-solved"),
        pytest.param("11" + "0" * 79, id="invalid"),
        pytest.param(BLOCKED_TEXT, id="unsatisfiable"),
    ],
)
def test_solving_is_repeatable_and_leaves_the_input_unchanged(text: str) -> None:
    grid = Grid.from_string(text)
    original_cells = grid.cells
    original_hash = hash(grid)

    first = solve(grid)
    second = solve(grid)

    assert first == second
    assert grid.cells == original_cells
    assert grid.to_string() == text
    assert hash(grid) == original_hash


@seed(1401)
@settings(max_examples=20, deadline=None)
@given(removed=st.sets(st.integers(min_value=0, max_value=80)))
@example(removed=set())
@example(removed=set(range(81)))
def test_removing_any_clues_from_a_solution_leaves_a_solvable_puzzle(
    removed: set[int],
) -> None:
    solved = Grid.from_string(SOLVED_TEXT)
    puzzle = Grid(
        tuple(
            0 if index in removed else value for index, value in enumerate(solved.cells)
        )
    )
    original_cells = puzzle.cells

    result = solve(puzzle)

    assert_solution_preserves_clues(puzzle, result)
    assert puzzle.cells == original_cells
