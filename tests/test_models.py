"""Structural domain invariants and canonical grid serialization."""

from dataclasses import FrozenInstanceError, fields

import pytest
from hypothesis import given, seed
from hypothesis import strategies as st

from sudoku_gen.exceptions import InvalidGridError, SudokuError
from sudoku_gen.models import Grid, SudokuPuzzle

CANONICAL_GRID = (
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
)
CANONICAL_SOLUTION = (
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)


class IntSubclass(int):
    """Check that cells require plain integers rather than numeric subclasses."""


def test_invalid_grid_error_is_a_domain_error_and_value_error() -> None:
    assert issubclass(InvalidGridError, SudokuError)
    assert issubclass(InvalidGridError, ValueError)


def test_parse_and_serialize_preserve_cell_order_and_empty_cells() -> None:
    grid = Grid.from_string(CANONICAL_GRID)

    assert grid.cells == tuple(int(character) for character in CANONICAL_GRID)
    assert grid.to_string() == CANONICAL_GRID


@pytest.mark.parametrize("value", range(10))
def test_grid_accepts_all_allowed_values_without_checking_sudoku_rules(
    value: int,
) -> None:
    grid = Grid(cells=(value,) * 81)

    assert grid.cells == (value,) * 81
    assert grid.to_string() == str(value) * 81


@pytest.mark.parametrize("length", [0, 1, 9, 80, 82, 162])
def test_grid_rejects_wrong_cell_counts(length: int) -> None:
    with pytest.raises(InvalidGridError):
        Grid(cells=(0,) * length)


@pytest.mark.parametrize(
    "cells",
    [
        None,
        [0] * 81,
        "0" * 81,
        b"0" * 81,
        bytearray(81),
        {index: 0 for index in range(81)},
        range(81),
    ],
)
def test_grid_rejects_non_tuple_containers(cells: object) -> None:
    with pytest.raises(InvalidGridError):
        Grid(cells=cells)


@pytest.mark.parametrize("cells", [((0,) * 9,) * 9, ((0,),) * 81])
def test_grid_rejects_nested_cells(cells: tuple[tuple[int, ...], ...]) -> None:
    with pytest.raises(InvalidGridError):
        Grid(cells=cells)


@pytest.mark.parametrize("index", [0, 40, 80])
@pytest.mark.parametrize(
    "value", [-1, 10, 100, True, False, 1.0, "1", None, IntSubclass(1)]
)
def test_grid_rejects_invalid_cell_types_and_values(index: int, value: object) -> None:
    cells: list[object] = [0] * 81
    cells[index] = value

    with pytest.raises(InvalidGridError):
        Grid(cells=tuple(cells))


@pytest.mark.parametrize("length", [0, 1, 9, 80, 82, 162])
def test_parse_rejects_wrong_lengths(length: int) -> None:
    with pytest.raises(InvalidGridError):
        Grid.from_string("0" * length)


@pytest.mark.parametrize("index", [0, 40, 80])
@pytest.mark.parametrize("character", ["a", ".", "-", " ", "\n", "\t", "١", "１", "²"])
def test_parse_rejects_non_ascii_digits(index: int, character: str) -> None:
    text = "0" * index + character + "0" * (80 - index)

    with pytest.raises(InvalidGridError):
        Grid.from_string(text)


@pytest.mark.parametrize("text", [None, 0, b"0" * 81, ["0"] * 81, (0,) * 81])
def test_parse_rejects_non_strings(text: object) -> None:
    with pytest.raises(InvalidGridError):
        Grid.from_string(text)


@pytest.mark.parametrize("text", [" " + "0" * 81, "0" * 81 + "\n"])
def test_parse_does_not_strip_whitespace(text: str) -> None:
    with pytest.raises(InvalidGridError):
        Grid.from_string(text)


def test_grid_is_immutable() -> None:
    grid = Grid(cells=(0,) * 81)

    with pytest.raises(FrozenInstanceError):
        grid.cells = (1,) * 81
    with pytest.raises(TypeError):
        grid.cells[0] = 1

    assert grid.cells == (0,) * 81


def test_grid_equality_and_hash_are_based_on_cells() -> None:
    grid = Grid.from_string(CANONICAL_GRID)
    duplicate = Grid(cells=tuple(int(character) for character in CANONICAL_GRID))
    different = Grid(cells=(0,) * 81)

    assert grid == duplicate
    assert hash(grid) == hash(duplicate)
    assert grid != different
    assert len({grid, duplicate, different}) == 2


@seed(1101)
@given(st.lists(st.integers(min_value=0, max_value=9), min_size=81, max_size=81))
def test_cells_round_trip_through_canonical_string(cells: list[int]) -> None:
    grid = Grid(cells=tuple(cells))

    serialized = grid.to_string()

    assert len(serialized) == 81
    assert set(serialized) <= set("0123456789")
    assert Grid.from_string(serialized).cells == tuple(cells)


@seed(1102)
@given(st.text(alphabet="0123456789", min_size=81, max_size=81))
def test_canonical_string_round_trip_through_grid(text: str) -> None:
    assert Grid.from_string(text).to_string() == text


def test_sudoku_puzzle_defaults_to_no_associated_solution() -> None:
    grid = Grid.from_string(CANONICAL_GRID)
    puzzle = SudokuPuzzle(grid=grid)

    assert puzzle.grid == grid
    assert puzzle.solution is None
    assert tuple(field.name for field in fields(puzzle)) == ("grid", "solution")


def test_sudoku_puzzle_is_immutable_and_hashable() -> None:
    puzzle = SudokuPuzzle(grid=Grid.from_string(CANONICAL_GRID))
    duplicate = SudokuPuzzle(grid=Grid.from_string(CANONICAL_GRID))

    with pytest.raises(FrozenInstanceError):
        puzzle.grid = Grid(cells=(0,) * 81)

    assert puzzle == duplicate
    assert hash(puzzle) == hash(duplicate)


@pytest.mark.parametrize("grid", [None, (0,) * 81, "0" * 81])
def test_sudoku_puzzle_rejects_non_grid_values(grid: object) -> None:
    with pytest.raises(TypeError):
        SudokuPuzzle(grid=grid)


def test_sudoku_puzzle_stores_matching_grid_and_solution() -> None:
    grid = Grid.from_string(CANONICAL_GRID)
    solution = Grid.from_string(CANONICAL_SOLUTION)

    puzzle = SudokuPuzzle(grid=grid, solution=solution)

    assert puzzle.grid == grid
    assert puzzle.solution == solution


def test_sudoku_puzzle_solution_is_immutable() -> None:
    puzzle = SudokuPuzzle(
        grid=Grid.from_string(CANONICAL_GRID),
        solution=Grid.from_string(CANONICAL_SOLUTION),
    )

    with pytest.raises(FrozenInstanceError):
        puzzle.solution = None

    assert puzzle.solution == Grid.from_string(CANONICAL_SOLUTION)


def test_sudoku_puzzle_equality_and_hash_include_associated_solution() -> None:
    grid = Grid(cells=(0,) * 81)
    solution = Grid.from_string(CANONICAL_SOLUTION)
    different_solution = Grid(cells=tuple(value % 9 + 1 for value in solution.cells))
    puzzle = SudokuPuzzle(grid=grid, solution=solution)
    duplicate = SudokuPuzzle(
        grid=Grid(cells=(0,) * 81),
        solution=Grid.from_string(CANONICAL_SOLUTION),
    )
    alternative = SudokuPuzzle(grid=grid, solution=different_solution)
    without_solution = SudokuPuzzle(grid=grid)

    assert puzzle == duplicate
    assert hash(puzzle) == hash(duplicate)
    assert puzzle != alternative
    assert puzzle != without_solution
    assert len({puzzle, duplicate, alternative, without_solution}) == 3


@pytest.mark.parametrize("solution", [0, False, (0,) * 81, "0" * 81, [0] * 81])
def test_sudoku_puzzle_rejects_non_grid_solutions(solution: object) -> None:
    with pytest.raises(TypeError):
        SudokuPuzzle(grid=Grid(cells=(0,) * 81), solution=solution)


@pytest.mark.parametrize("index", [0, 40, 80])
@pytest.mark.parametrize("missing_answer", [False, True])
def test_sudoku_puzzle_rejects_clues_inconsistent_with_solution(
    index: int, missing_answer: bool
) -> None:
    solution_cells = tuple(int(value) for value in CANONICAL_SOLUTION)
    clue = solution_cells[index]
    grid = Grid(cells=(0,) * index + (clue,) + (0,) * (80 - index))
    different_answer = 0 if missing_answer else clue % 9 + 1
    inconsistent_solution = Grid(
        cells=solution_cells[:index] + (different_answer,) + solution_cells[index + 1 :]
    )

    with pytest.raises(ValueError, match="does not match its solution"):
        SudokuPuzzle(grid=grid, solution=inconsistent_solution)
