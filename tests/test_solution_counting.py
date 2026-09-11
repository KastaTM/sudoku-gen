"""Capped solution counting, uniqueness, and shared search invariants."""

import pytest
from hypothesis import example, given, seed, settings
from hypothesis import strategies as st

from sudoku_gen import solver
from sudoku_gen.candidates import candidates
from sudoku_gen.models import Grid
from sudoku_gen.solver import count_solutions, has_unique_solution, solve
from sudoku_gen.validation import empty_cells, is_valid_grid, is_valid_solution

SOLVED_TEXT = (
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)
EASY_TEXT = (
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
)
BACKTRACKING_TEXT = (
    "100007090030020008009400500005300900010080002400006000300000010060000007007000300"
)
BLOCKED_TEXT = "012345678" + "0" * 18 + "900000000" + "0" * 45
EMPTY_TEXT = "0" * 81
# Rows 0 and 3 contain opposite 6/7 pairs in columns 3 and 4. Removing
# those four clues allows both arrangements without changing any other cell.
AMBIGUOUS_INDICES = frozenset({3, 4, 30, 31})
TWO_SOLUTION_TEXT = "".join(
    "0" if index in AMBIGUOUS_INDICES else digit
    for index, digit in enumerate(SOLVED_TEXT)
)
# This is the deterministic empty-grid result from Phase 1.4.
EMPTY_FIRST_SOLUTION_TEXT = (
    "123456789456789123789123456231674895875912364694538217317265948542897631968341572"
)


class IntSubclass(int):
    """Limits require built-in integers, like existing coordinates and cells."""


def assert_preserves_clues(puzzle: Grid, solution: Grid) -> None:
    assert all(
        clue == 0 or clue == value
        for clue, value in zip(puzzle.cells, solution.cells, strict=True)
    )


def observe_completed_solutions(
    monkeypatch: pytest.MonkeyPatch, puzzle: Grid, maximum: int
) -> list[Grid]:
    """Reject extra search after reaching the cap without relying on timing."""
    observed: list[Grid] = []

    def check_solution(solution: Grid) -> bool:
        assert len(observed) < maximum, "Search continued beyond its solution limit"
        assert is_valid_solution(solution)
        assert_preserves_clues(puzzle, solution)
        assert solution not in observed, "A completion was counted more than once"
        observed.append(solution)
        return True

    def check_candidates(grid: Grid, row: int, column: int) -> frozenset[int]:
        assert len(observed) < maximum, (
            "Search explored a branch after reaching its cap"
        )
        return candidates(grid, row, column)

    monkeypatch.setattr(solver, "is_valid_solution", check_solution)
    monkeypatch.setattr(solver, "candidates", check_candidates)
    return observed


@pytest.fixture
def two_solution_grid() -> Grid:
    """Verify two explicit completions independently of the counting algorithm."""
    puzzle = Grid.from_string(TWO_SOLUTION_TEXT)
    first = Grid.from_string(SOLVED_TEXT)
    second = Grid(
        tuple(
            13 - value if index in AMBIGUOUS_INDICES else value
            for index, value in enumerate(first.cells)
        )
    )
    assert first != second
    assert is_valid_grid(puzzle)
    for completion in (first, second):
        assert is_valid_solution(completion)
        assert_preserves_clues(puzzle, completion)
    assert empty_cells(puzzle) == ((0, 3), (0, 4), (3, 3), (3, 4))
    for row, column in empty_cells(puzzle):
        assert candidates(puzzle, row, column) == frozenset({6, 7})
    # Choosing either digit in (0, 3) forces the other three by row/column
    # uniqueness, so the two explicit completions exhaust the possibilities.
    return puzzle


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(SOLVED_TEXT, id="solved"),
        pytest.param("0" + SOLVED_TEXT[1:], id="one-missing-cell"),
        pytest.param(EASY_TEXT, id="known-unique-puzzle"),
    ],
)
@pytest.mark.parametrize("limit", [1, 2, 5])
def test_unique_grids_have_one_solution_for_every_positive_cap(
    text: str, limit: int
) -> None:
    assert count_solutions(Grid.from_string(text), limit=limit) == 1


def test_a_limit_can_be_an_arbitrarily_large_positive_integer() -> None:
    assert count_solutions(Grid.from_string(SOLVED_TEXT), limit=10**100) == 1


@pytest.mark.parametrize("limit", [1, 2, 5])
def test_known_two_solution_grid_obeys_the_cap_and_exhausts_at_two(
    two_solution_grid: Grid, limit: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = min(2, limit)
    observed = observe_completed_solutions(monkeypatch, two_solution_grid, limit)

    assert count_solutions(two_solution_grid, limit=limit) == expected
    assert len(observed) == expected


def test_known_two_solution_grid_uses_two_as_its_default_cap(
    two_solution_grid: Grid, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed = observe_completed_solutions(monkeypatch, two_solution_grid, 2)

    assert count_solutions(two_solution_grid) == 2
    assert len(observed) == 2


@pytest.mark.parametrize(
    "limit", [None, 1, 2, 4], ids=["default", "one", "two", "four"]
)
def test_empty_grid_stops_after_the_requested_number_of_distinct_solutions(
    limit: int | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    grid = Grid.from_string(EMPTY_TEXT)
    expected = 2 if limit is None else limit
    observed = observe_completed_solutions(monkeypatch, grid, expected)

    result = count_solutions(grid) if limit is None else count_solutions(grid, limit)

    assert result == expected
    assert len(observed) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param(EMPTY_TEXT, EMPTY_FIRST_SOLUTION_TEXT, id="empty"),
        pytest.param(TWO_SOLUTION_TEXT, SOLVED_TEXT, id="two-solutions"),
    ],
)
def test_solve_stops_at_one_and_preserves_its_previous_deterministic_result(
    text: str, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    grid = Grid.from_string(text)
    observed = observe_completed_solutions(monkeypatch, grid, 1)

    assert solve(grid) == Grid.from_string(expected)
    assert len(observed) == 1


@pytest.mark.parametrize("text", [EMPTY_TEXT, TWO_SOLUTION_TEXT])
def test_uniqueness_stops_as_soon_as_a_second_completion_is_found(
    text: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    grid = Grid.from_string(text)
    observed = observe_completed_solutions(monkeypatch, grid, 2)

    assert has_unique_solution(grid) is False
    assert len(observed) == 2


@pytest.mark.parametrize("text", [SOLVED_TEXT, EASY_TEXT])
def test_uniqueness_is_true_when_only_one_solution_exists(text: str) -> None:
    assert has_unique_solution(Grid.from_string(text)) is True


@pytest.mark.parametrize(
    "coordinates",
    [
        pytest.param(((8, 2), (8, 3)), id="row-across-box-boundary"),
        pytest.param(((2, 8), (3, 8)), id="column-across-box-boundary"),
        pytest.param(((6, 6), (8, 8)), id="box-distinct-rows-and-columns"),
    ],
)
def test_conflicting_partial_grids_have_zero_solutions(
    coordinates: tuple[tuple[int, int], tuple[int, int]],
) -> None:
    cells = [0] * 81
    for row, column in coordinates:
        cells[row * 9 + column] = 7
    grid = Grid(tuple(cells))

    assert not is_valid_grid(grid)
    assert count_solutions(grid) == 0
    assert has_unique_solution(grid) is False


def test_complete_conflicting_grid_has_zero_solutions() -> None:
    grid = Grid.from_string("1" * 81)

    assert count_solutions(grid) == 0
    assert has_unique_solution(grid) is False


def test_a_valid_grid_with_a_blocked_cell_has_zero_solutions() -> None:
    grid = Grid.from_string(BLOCKED_TEXT)

    assert is_valid_grid(grid)
    assert candidates(grid, 0, 0) == frozenset()
    assert count_solutions(grid) == 0
    assert has_unique_solution(grid) is False


def test_a_valid_grid_can_require_search_to_prove_it_has_zero_solutions() -> None:
    original = Grid.from_string(BACKTRACKING_TEXT)
    # The legal 4 at (1, 2) is the unsatisfiable branch verified in Phase 1.4.
    grid = Grid(original.cells[:11] + (4,) + original.cells[12:])

    assert is_valid_grid(grid)
    assert all(candidates(grid, row, column) for row, column in empty_cells(grid))
    assert count_solutions(grid) == 0
    assert has_unique_solution(grid) is False


@pytest.mark.parametrize("text", [SOLVED_TEXT, "11" + "0" * 79])
@pytest.mark.parametrize("limit", [True, False, 1.0, "2", None, IntSubclass(2)])
def test_limit_requires_a_builtin_integer_even_for_an_invalid_grid(
    text: str, limit: object
) -> None:
    with pytest.raises(TypeError):
        count_solutions(Grid.from_string(text), limit=limit)


@pytest.mark.parametrize("text", [SOLVED_TEXT, "11" + "0" * 79])
@pytest.mark.parametrize("limit", [0, -1, -100])
def test_nonpositive_limit_is_rejected_even_for_an_invalid_grid(
    text: str, limit: int
) -> None:
    with pytest.raises(ValueError):
        count_solutions(Grid.from_string(text), limit=limit)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param(EASY_TEXT, 1, id="unique"),
        pytest.param(SOLVED_TEXT, 1, id="solved"),
        pytest.param(TWO_SOLUTION_TEXT, 2, id="multiple"),
        pytest.param("11" + "0" * 79, 0, id="invalid"),
        pytest.param(BLOCKED_TEXT, 0, id="unsatisfiable"),
    ],
)
def test_counting_and_uniqueness_are_repeatable_and_preserve_the_input(
    text: str, expected: int
) -> None:
    grid = Grid.from_string(text)
    original_cells = grid.cells
    original_hash = hash(grid)

    for _ in range(2):
        assert count_solutions(grid) == expected
        assert has_unique_solution(grid) is (expected == 1)

    assert grid.cells == original_cells
    assert grid.to_string() == text
    assert hash(grid) == original_hash


@seed(1501)
@settings(max_examples=20, deadline=None)
@given(removed=st.sets(st.integers(min_value=0, max_value=80)))
@example(removed=set())
@example(removed=set(range(81)))
def test_clue_removal_preserves_a_completion_and_counts_are_monotonic(
    removed: set[int],
) -> None:
    solved = Grid.from_string(SOLVED_TEXT)
    grid = Grid(
        tuple(
            0 if index in removed else digit for index, digit in enumerate(solved.cells)
        )
    )
    original_cells = grid.cells

    with pytest.MonkeyPatch.context() as monkeypatch:
        first_observed = observe_completed_solutions(monkeypatch, grid, 1)
        first_count = count_solutions(grid, limit=1)
        second_observed = observe_completed_solutions(monkeypatch, grid, 2)
        second_count = count_solutions(grid, limit=2)

    assert first_count == len(first_observed) == 1
    assert first_count <= second_count == len(second_observed) <= 2
    assert grid.cells == original_cells
