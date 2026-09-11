"""Seeded generation, uniqueness-preserving carving, and immutable results."""

import random
from collections.abc import Callable
from dataclasses import FrozenInstanceError

import pytest
from hypothesis import given, seed, settings
from hypothesis import strategies as st

from sudoku_gen import generator
from sudoku_gen.generator import generate_puzzle, generate_solution
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.solver import has_unique_solution, solve
from sudoku_gen.validation import (
    clue_count,
    is_complete,
    is_valid_grid,
    is_valid_solution,
)

SOLVED_TEXT = (
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)
PARTIAL_TEXT = (
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
)
EMPTY_FIRST_SOLUTION_TEXT = (
    "123456789456789123789123456231674895875912364694538217317265948542897631968341572"
)


class IntSubclass(int):
    """Generation parameters follow the existing built-in integer convention."""


def assert_puzzle_invariants(puzzle: SudokuPuzzle, target_clues: int) -> None:
    assert isinstance(puzzle.solution, Grid)
    assert is_valid_solution(puzzle.solution)
    assert is_valid_grid(puzzle.grid)
    assert target_clues <= clue_count(puzzle.grid) <= 81
    assert all(
        clue == 0 or clue == answer
        for clue, answer in zip(puzzle.grid.cells, puzzle.solution.cells, strict=True)
    )
    assert has_unique_solution(puzzle.grid)
    assert solve(puzzle.grid) == puzzle.solution


@pytest.mark.parametrize("generation_seed", [-7, 0, 1, 12345, 10**100])
def test_solution_generation_is_valid_complete_and_repeatable(
    generation_seed: int,
) -> None:
    first = generate_solution(seed=generation_seed)
    second = generate_solution(seed=generation_seed)

    assert isinstance(first, Grid)
    assert is_complete(first)
    assert is_valid_grid(first)
    assert is_valid_solution(first)
    assert clue_count(first) == 81
    assert first == second
    assert hash(first) == hash(second)


def test_different_seeds_can_generate_distinct_solutions() -> None:
    solutions = {generate_solution(seed=value) for value in (0, 1, 2)}

    # Seed collisions are allowed; diversity does not require every pair to differ.
    assert len(solutions) > 1


@pytest.mark.parametrize(
    ("generation_seed", "target_clues"),
    [(12345, 30), (0, 40), (1, 80), (12345, 81)],
)
def test_generated_puzzles_preserve_uniqueness_clues_and_seeded_solution(
    generation_seed: int, target_clues: int
) -> None:
    puzzle = generate_puzzle(seed=generation_seed, target_clues=target_clues)

    assert_puzzle_invariants(puzzle, target_clues)
    assert puzzle.solution == generate_solution(seed=generation_seed)
    assert puzzle == generate_puzzle(seed=generation_seed, target_clues=target_clues)
    if target_clues < 81:
        assert not is_complete(puzzle.grid)
    else:
        assert puzzle.grid == puzzle.solution


def test_default_target_is_thirty_clues() -> None:
    assert generate_puzzle(seed=0) == generate_puzzle(seed=0, target_clues=30)


def test_lowest_supported_target_preserves_uniqueness_even_if_not_reached() -> None:
    puzzle = generate_puzzle(seed=0, target_clues=17)

    assert_puzzle_invariants(puzzle, target_clues=17)
    assert not is_complete(puzzle.grid)


def test_omitted_and_none_seeds_use_a_local_random_generator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received_seeds: list[int | None] = []

    def seeded_random(value: int | None) -> random.Random:
        received_seeds.append(value)
        return random.Random(1601 if value is None else value)

    monkeypatch.setattr(generator, "Random", seeded_random)

    first_solution = generate_solution()
    second_solution = generate_solution(seed=None)
    first_puzzle = generate_puzzle(target_clues=80)
    second_puzzle = generate_puzzle(seed=None, target_clues=80)

    assert received_seeds == [None, None, None, None]
    assert first_solution == second_solution == first_puzzle.solution
    assert first_puzzle == second_puzzle
    assert_puzzle_invariants(first_puzzle, target_clues=80)


@pytest.fixture
def forbid_random_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_random(value: int | None) -> random.Random:
        pytest.fail("Invalid parameters must fail before generation starts")

    monkeypatch.setattr(generator, "Random", unexpected_random)


@pytest.mark.usefixtures("forbid_random_construction")
@pytest.mark.parametrize(
    "generation_seed", [True, False, 1.5, "1", b"1", IntSubclass(1)]
)
@pytest.mark.parametrize("generate", [generate_solution, generate_puzzle])
def test_seed_requires_a_builtin_integer_or_none(
    generate: Callable[..., Grid | SudokuPuzzle], generation_seed: object
) -> None:
    with pytest.raises(TypeError):
        generate(seed=generation_seed)


@pytest.mark.usefixtures("forbid_random_construction")
@pytest.mark.parametrize(
    "target_clues", [True, False, 30.0, "30", None, IntSubclass(30)]
)
def test_target_requires_a_builtin_integer(target_clues: object) -> None:
    with pytest.raises(TypeError):
        generate_puzzle(seed=0, target_clues=target_clues)


@pytest.mark.usefixtures("forbid_random_construction")
@pytest.mark.parametrize("target_clues", [-1, 0, 16, 82, 10**100])
def test_target_outside_supported_range_is_rejected(target_clues: int) -> None:
    with pytest.raises(ValueError):
        generate_puzzle(seed=0, target_clues=target_clues)


@pytest.mark.parametrize("generation_kind", ["solution", "puzzle"])
def test_generation_preserves_the_global_random_sequence(generation_kind: str) -> None:
    original_state = random.getstate()
    try:
        random.seed(1602)
        expected = random.Random(1602)
        assert random.random() == expected.random()

        if generation_kind == "solution":
            generate_solution(seed=12345)
        else:
            generate_puzzle(seed=12345, target_clues=40)

        assert random.getstate() == expected.getstate()
        assert [random.random() for _ in range(5)] == [
            expected.random() for _ in range(5)
        ]
    finally:
        random.setstate(original_state)


def test_seeded_generation_does_not_depend_on_the_global_random_state() -> None:
    original_state = random.getstate()
    try:
        random.seed(1603)
        first = generate_puzzle(seed=1, target_clues=40)
        random.seed(1604)
        second = generate_puzzle(seed=1, target_clues=40)
    finally:
        random.setstate(original_state)

    assert first == second


def test_generation_does_not_change_deterministic_solving() -> None:
    empty = Grid((0,) * 81)
    expected = Grid.from_string(EMPTY_FIRST_SOLUTION_TEXT)

    assert solve(empty) == expected
    generate_solution(seed=12345)
    generate_puzzle(seed=0, target_clues=80)
    assert solve(empty) == expected
    assert empty.cells == (0,) * 81


def test_generated_puzzle_and_associated_grids_remain_immutable_and_hashable() -> None:
    puzzle = generate_puzzle(seed=0, target_clues=80)
    assert isinstance(puzzle.solution, Grid)
    original_grid = puzzle.grid
    original_solution = puzzle.solution
    original_hash = hash(puzzle)

    with pytest.raises(FrozenInstanceError):
        puzzle.grid = original_solution
    with pytest.raises(FrozenInstanceError):
        puzzle.solution = original_grid
    with pytest.raises(FrozenInstanceError):
        puzzle.grid.cells = (0,) * 81
    with pytest.raises(TypeError):
        puzzle.solution.cells[0] = 0

    assert puzzle.grid == original_grid
    assert puzzle.solution == original_solution
    assert hash(puzzle) == original_hash
    assert len({puzzle, generate_puzzle(seed=0, target_clues=80)}) == 1


def test_every_tentative_removal_is_checked_and_only_unique_states_are_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    solution = generate_solution(seed=12345)
    accepted = solution
    attempted_positions: list[int] = []
    target_clues = 30

    def check_removal(tentative: Grid) -> bool:
        nonlocal accepted
        assert clue_count(accepted) > target_clues, "Carving continued after the target"
        changed = [
            index
            for index, (before, after) in enumerate(
                zip(accepted.cells, tentative.cells, strict=True)
            )
            if before != after
        ]
        assert len(changed) == 1
        position = changed[0]
        assert accepted.cells[position] != 0
        assert tentative.cells[position] == 0
        assert position not in attempted_positions
        attempted_positions.append(position)
        unique = has_unique_solution(tentative)
        if unique:
            accepted = tentative
        return unique

    monkeypatch.setattr(generator, "has_unique_solution", check_removal)

    puzzle = generate_puzzle(seed=12345, target_clues=target_clues)

    assert puzzle.solution == solution
    assert puzzle.grid == accepted
    assert 1 <= len(attempted_positions) <= 81
    assert clue_count(puzzle.grid) == target_clues or len(attempted_positions) == 81
    assert_puzzle_invariants(puzzle, target_clues)


def test_a_rejected_clue_is_retained_and_carving_stops_at_the_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tentative_grids: list[Grid] = []

    def reject_first_removal(tentative: Grid) -> bool:
        tentative_grids.append(tentative)
        assert len(tentative_grids) <= 2, "Carving did not stop at 80 clues"
        # Conservatively reject the first attempt to exercise clue restoration.
        return len(tentative_grids) > 1 and has_unique_solution(tentative)

    monkeypatch.setattr(generator, "has_unique_solution", reject_first_removal)

    puzzle = generate_puzzle(seed=0, target_clues=80)

    assert len(tentative_grids) == 2
    assert isinstance(puzzle.solution, Grid)
    rejected_position = tentative_grids[0].cells.index(0)
    assert (
        puzzle.grid.cells[rejected_position] == puzzle.solution.cells[rejected_position]
    )
    assert puzzle.grid == tentative_grids[1]
    assert clue_count(puzzle.grid) == 80
    assert_puzzle_invariants(puzzle, target_clues=80)


def test_a_failed_removal_pass_is_bounded_and_may_return_more_than_the_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted_positions: list[int] = []

    def reject_removal(tentative: Grid) -> bool:
        assert len(attempted_positions) < 81, (
            "Carving retried an exhausted removal pass"
        )
        assert clue_count(tentative) == 80
        position = tentative.cells.index(0)
        assert position not in attempted_positions
        attempted_positions.append(position)
        return False

    monkeypatch.setattr(generator, "has_unique_solution", reject_removal)

    puzzle = generate_puzzle(seed=1, target_clues=17)

    assert set(attempted_positions) == set(range(81))
    assert puzzle.grid == puzzle.solution
    assert clue_count(puzzle.grid) == 81
    assert_puzzle_invariants(puzzle, target_clues=17)


def test_target_eighty_one_does_not_attempt_to_remove_clues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_removal(tentative: Grid) -> bool:
        pytest.fail("A completed puzzle already satisfies a target of 81 clues")

    monkeypatch.setattr(generator, "has_unique_solution", unexpected_removal)

    puzzle = generate_puzzle(seed=1, target_clues=81)

    assert puzzle.grid == puzzle.solution
    assert is_valid_solution(puzzle.grid)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("0" * 81, 0, id="empty"),
        pytest.param("0" * 40 + "9" + "0" * 40, 1, id="one-clue"),
        pytest.param(PARTIAL_TEXT, 30, id="partial"),
        pytest.param(SOLVED_TEXT, 81, id="complete"),
        pytest.param("1" * 81, 81, id="count-independent-of-rule-validity"),
    ],
)
def test_clue_count_counts_nonzero_cells_without_mutation(
    text: str, expected: int
) -> None:
    grid = Grid.from_string(text)
    original_hash = hash(grid)

    assert clue_count(grid) == expected
    assert grid.to_string() == text
    assert hash(grid) == original_hash


@seed(1605)
@settings(max_examples=4, deadline=None)
@given(
    generation_seed=st.integers(min_value=0, max_value=1000),
    target_clues=st.integers(min_value=35, max_value=45),
)
def test_bounded_seed_and_target_combinations_preserve_generator_invariants(
    generation_seed: int, target_clues: int
) -> None:
    puzzle = generate_puzzle(seed=generation_seed, target_clues=target_clues)

    assert_puzzle_invariants(puzzle, target_clues)
