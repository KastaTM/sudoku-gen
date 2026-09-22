"""Clue-position symmetry, descriptive reports, and symmetric carving."""

import random
from dataclasses import FrozenInstanceError

import pytest

from sudoku_gen import generator
from sudoku_gen.difficulty import Difficulty, rate_difficulty
from sudoku_gen.exceptions import DifficultyGenerationError
from sudoku_gen.generator import generate_puzzle, generate_puzzle_for_difficulty
from sudoku_gen.models import Grid, SudokuPuzzle
from sudoku_gen.pattern import (
    PuzzlePatternReport,
    Symmetry,
    analyze_pattern,
    is_symmetric,
)
from sudoku_gen.solver import has_unique_solution, solve
from sudoku_gen.validation import clue_count, is_valid_grid, is_valid_solution

SOLVED_TEXT = (
    "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
)


def grid_with_clues(indices: set[int]) -> Grid:
    cells = [0] * 81
    for index in indices:
        cells[index] = index % 9 + 1
    return Grid(tuple(cells))


def test_none_places_no_constraint_and_rotational_uses_clue_positions_not_values() -> (
    None
):
    asymmetric = grid_with_clues({0})
    value_mismatched = Grid((7,) + (0,) * 79 + (3,))

    assert is_symmetric(asymmetric, Symmetry.NONE)
    assert not is_symmetric(asymmetric, Symmetry.ROTATIONAL_180)
    assert is_symmetric(value_mismatched, Symmetry.ROTATIONAL_180)
    assert analyze_pattern(asymmetric).symmetry is Symmetry.NONE
    assert analyze_pattern(value_mismatched).symmetry is Symmetry.ROTATIONAL_180


def test_every_rotational_orbit_and_the_center_are_handled_correctly() -> None:
    for index in range(40):
        complement = 80 - index
        assert not is_symmetric(grid_with_clues({index}), Symmetry.ROTATIONAL_180)
        assert is_symmetric(
            grid_with_clues({index, complement}), Symmetry.ROTATIONAL_180
        )
    assert is_symmetric(grid_with_clues({40}), Symmetry.ROTATIONAL_180)
    assert is_symmetric(Grid((0,) * 81), Symmetry.ROTATIONAL_180)


@pytest.mark.parametrize("value", [None, "rotational", 1, True])
def test_symmetry_arguments_must_be_typed(value: object) -> None:
    grid = Grid((0,) * 81)
    with pytest.raises(TypeError):
        is_symmetric(grid, value)
    with pytest.raises(TypeError):
        generate_puzzle(seed=0, symmetry=value)
    with pytest.raises(TypeError):
        generate_puzzle_for_difficulty(
            Difficulty.EASY, seed=0, target_clues=81, max_attempts=1, symmetry=value
        )


def test_pattern_report_contains_exact_row_column_box_and_total_counts() -> None:
    grid = grid_with_clues({0, 1, 9, 10, 40, 80})

    report = analyze_pattern(grid)

    assert report == PuzzlePatternReport(
        clue_count=6,
        symmetry=Symmetry.NONE,
        row_clue_counts=(2, 2, 0, 0, 1, 0, 0, 0, 1),
        column_clue_counts=(2, 2, 0, 0, 1, 0, 0, 0, 1),
        box_clue_counts=(4, 0, 0, 0, 1, 0, 0, 0, 1),
    )
    assert hash(report) == hash(analyze_pattern(grid))
    with pytest.raises(FrozenInstanceError):
        report.clue_count = 0
    with pytest.raises(FrozenInstanceError):
        report.row_clue_counts = ()


@pytest.mark.parametrize("generation_seed", [0, 1, 2])
def test_rotational_generation_is_valid_unique_symmetric_and_repeatable(
    generation_seed: int,
) -> None:
    first = generate_puzzle(
        seed=generation_seed, target_clues=80, symmetry=Symmetry.ROTATIONAL_180
    )
    second = generate_puzzle(
        seed=generation_seed, target_clues=80, symmetry=Symmetry.ROTATIONAL_180
    )

    assert first == second
    assert is_symmetric(first.grid, Symmetry.ROTATIONAL_180)
    assert is_valid_grid(first.grid)
    assert isinstance(first.solution, Grid)
    assert is_valid_solution(first.solution)
    assert has_unique_solution(first.grid)
    assert solve(first.grid) == first.solution
    assert clue_count(first.grid) >= 80
    assert all(
        clue == 0 or clue == answer
        for clue, answer in zip(first.grid.cells, first.solution.cells, strict=True)
    )


def test_rotational_carving_checks_each_pair_once_and_removes_it_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    solution = Grid.from_string(SOLVED_TEXT)
    attempted: list[Grid] = []

    class IdentityShuffleRng:
        def shuffle(self, values: list[tuple[int, ...]]) -> None:
            return None

    monkeypatch.setattr(generator, "_generate_solution", lambda rng: solution)
    monkeypatch.setattr(generator, "_local_rng", lambda seed: IdentityShuffleRng())

    def accept(tentative: Grid) -> bool:
        attempted.append(tentative)
        return True

    monkeypatch.setattr(generator, "has_unique_solution", accept)

    puzzle = generate_puzzle(seed=0, target_clues=79, symmetry=Symmetry.ROTATIONAL_180)

    assert len(attempted) == 1
    removed = [i for i, value in enumerate(attempted[0].cells) if value == 0]
    assert len(removed) == 2
    assert removed == [0, 80]
    assert puzzle.grid == attempted[0]
    assert clue_count(puzzle.grid) == 79
    assert is_symmetric(puzzle.grid, Symmetry.ROTATIONAL_180)


def test_rotational_center_is_a_single_cell_orbit_for_an_even_clue_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    solution = Grid.from_string(SOLVED_TEXT)
    attempted: list[Grid] = []

    class IdentityShuffleRng:
        def shuffle(self, values: list[tuple[int, ...]]) -> None:
            return None

    monkeypatch.setattr(generator, "_generate_solution", lambda rng: solution)
    monkeypatch.setattr(generator, "_local_rng", lambda seed: IdentityShuffleRng())
    monkeypatch.setattr(
        generator,
        "has_unique_solution",
        lambda tentative: attempted.append(tentative) or True,
    )

    puzzle = generate_puzzle(seed=0, target_clues=80, symmetry=Symmetry.ROTATIONAL_180)

    assert len(attempted) == 1
    assert [i for i, value in enumerate(attempted[0].cells) if value == 0] == [40]
    assert clue_count(puzzle.grid) == 80
    assert is_symmetric(puzzle.grid, Symmetry.ROTATIONAL_180)


@pytest.mark.parametrize("target_clues", [80, 79, 78])
def test_rotational_targets_are_lower_bounds_even_when_orbit_sizes_prevent_exact_counts(
    target_clues: int,
) -> None:
    puzzle = generate_puzzle(
        seed=3, target_clues=target_clues, symmetry=Symmetry.ROTATIONAL_180
    )

    assert clue_count(puzzle.grid) >= target_clues
    assert is_symmetric(puzzle.grid, Symmetry.ROTATIONAL_180)


def test_rotational_target_eighty_one_preserves_completed_solution() -> None:
    puzzle = generate_puzzle(seed=4, target_clues=81, symmetry=Symmetry.ROTATIONAL_180)

    assert puzzle.grid == puzzle.solution
    assert clue_count(puzzle.grid) == 81
    assert is_symmetric(puzzle.grid, Symmetry.ROTATIONAL_180)


def test_symmetry_none_keeps_existing_default_generation_identical() -> None:
    default = generate_puzzle(seed=12345, target_clues=30)
    explicit_none = generate_puzzle(seed=12345, target_clues=30, symmetry=Symmetry.NONE)

    assert default == explicit_none


def test_rotational_generation_preserves_global_random_state() -> None:
    original_state = random.getstate()
    try:
        random.seed(1811)
        expected = random.Random(1811)
        assert random.random() == expected.random()

        generate_puzzle(seed=5, target_clues=80, symmetry=Symmetry.ROTATIONAL_180)

        assert random.getstate() == expected.getstate()
        assert [random.random() for _ in range(5)] == [
            expected.random() for _ in range(5)
        ]
    finally:
        random.setstate(original_state)


def test_difficulty_targeting_forwards_symmetry_and_keeps_its_bounded_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    solution = Grid.from_string(SOLVED_TEXT)
    symmetric_puzzle = SudokuPuzzle(solution, solution)
    requested: list[Symmetry] = []

    def generate_candidate(
        *, seed: int | None, target_clues: int, symmetry: Symmetry
    ) -> SudokuPuzzle:
        requested.append(symmetry)
        return symmetric_puzzle

    monkeypatch.setattr(generator, "generate_puzzle", generate_candidate)
    monkeypatch.setattr(
        generator, "rate_difficulty", lambda grid: rate_difficulty(grid)
    )

    success = generate_puzzle_for_difficulty(
        Difficulty.EASY,
        seed=6,
        target_clues=81,
        max_attempts=1,
        symmetry=Symmetry.ROTATIONAL_180,
    )
    assert success.puzzle is symmetric_puzzle
    assert requested == [Symmetry.ROTATIONAL_180]

    with pytest.raises(DifficultyGenerationError):
        generate_puzzle_for_difficulty(
            Difficulty.HARD,
            seed=6,
            target_clues=81,
            max_attempts=2,
            symmetry=Symmetry.ROTATIONAL_180,
        )
    assert requested == [
        Symmetry.ROTATIONAL_180,
        Symmetry.ROTATIONAL_180,
        Symmetry.ROTATIONAL_180,
    ]
