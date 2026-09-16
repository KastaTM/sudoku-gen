"""Pure, deterministic deductions over preserved logical candidate state.

These generators assume their input state has passed the orchestration layer's
consistency checks. They never compute new candidates or change the state.
Each elimination step contains every actual removal made by one deduction.
"""

from collections.abc import Iterator
from itertools import combinations

from sudoku_gen._logical_models import (
    CandidateElimination,
    EliminationStep,
    LogicalState,
    SolveStep,
    Technique,
)

type _Cell = tuple[int, int]
type _Unit = tuple[_Cell, ...]


def _lines() -> Iterator[_Unit]:
    """Visit rows, then columns, in ascending index order."""
    for row in range(9):
        yield tuple((row, column) for column in range(9))
    for column in range(9):
        yield tuple((row, column) for row in range(9))


def _box_cells(box_row: int, box_column: int) -> _Unit:
    """Return a box's cells in row-major order, using box indices 0..2."""
    return tuple(
        (box_row * 3 + row, box_column * 3 + column)
        for row in range(3)
        for column in range(3)
    )


def _boxes() -> Iterator[_Unit]:
    for box_row in range(3):
        for box_column in range(3):
            yield _box_cells(box_row, box_column)


def _units() -> Iterator[_Unit]:
    """Visit rows, columns, then boxes; cells within units are row-major."""
    yield from _lines()
    yield from _boxes()


def _options(state: LogicalState, cell: _Cell) -> frozenset[int]:
    row, column = cell
    return state.candidates[row * 9 + column]


def _positions(state: LogicalState, unit: _Unit, value: int) -> _Unit:
    return tuple(cell for cell in unit if value in _options(state, cell))


def _removals(
    state: LogicalState, cells: _Unit, values: frozenset[int]
) -> tuple[CandidateElimination, ...]:
    return tuple(
        CandidateElimination(row, column, value)
        for row, column in cells
        for value in sorted(_options(state, (row, column)) & values)
    )


def naked_singles(state: LogicalState) -> Iterator[SolveStep]:
    """Find singleton cells in row-major order."""
    for index, values in enumerate(state.candidates):
        if len(values) == 1:
            row, column = divmod(index, 9)
            yield SolveStep(Technique.NAKED_SINGLE, row, column, next(iter(values)))


def hidden_singles(state: LogicalState) -> Iterator[SolveStep]:
    """Scan rows, columns, then boxes, with ascending digits within each unit."""
    for unit in _units():
        for value in range(1, 10):
            positions = _positions(state, unit, value)
            if len(positions) == 1:
                row, column = positions[0]
                yield SolveStep(Technique.HIDDEN_SINGLE, row, column, value)


def naked_pairs(state: LogicalState) -> Iterator[EliminationStep]:
    """Remove an exact two-cell pair from the other cells in its unit.

    Units follow rows/columns/boxes order. Distinct candidate pairs are visited
    in ascending digit-pair order. Three cells sharing a pair are not a pair.
    """
    for unit in _units():
        pairs = {
            tuple(sorted(_options(state, cell)))
            for cell in unit
            if len(_options(state, cell)) == 2
        }
        for pair in sorted(pairs):
            values = frozenset(pair)
            positions = tuple(cell for cell in unit if _options(state, cell) == values)
            if len(positions) != 2:
                continue
            targets = tuple(cell for cell in unit if cell not in positions)
            eliminations = _removals(state, targets, values)
            if eliminations:
                yield EliminationStep(Technique.NAKED_PAIR, eliminations)


def hidden_pairs(state: LogicalState) -> Iterator[EliminationStep]:
    """Restrict two cells when two digits occur only in those same cells."""
    for unit in _units():
        positions = {value: _positions(state, unit, value) for value in range(1, 10)}
        for first, second in combinations(range(1, 10), 2):
            cells = positions[first]
            if len(cells) != 2 or cells != positions[second]:
                continue
            pair = frozenset((first, second))
            eliminations = tuple(
                CandidateElimination(row, column, value)
                for row, column in cells
                for value in sorted(_options(state, (row, column)) - pair)
            )
            if eliminations:
                yield EliminationStep(Technique.HIDDEN_PAIR, eliminations)


def pointing(state: LogicalState) -> Iterator[EliminationStep]:
    """Project two or three box positions onto a row or column outside the box.

    Scan boxes row-major, then ascending digits, with rows before columns.
    """
    for box in _boxes():
        for value in range(1, 10):
            positions = _positions(state, box, value)
            if len(positions) not in (2, 3):
                continue
            row, column = positions[0]
            if all(cell_row == row for cell_row, _ in positions):
                targets = tuple((row, col) for col in range(9) if (row, col) not in box)
                eliminations = _removals(state, targets, frozenset((value,)))
                if eliminations:
                    yield EliminationStep(Technique.POINTING, eliminations)
            if all(cell_column == column for _, cell_column in positions):
                targets = tuple(
                    (cell_row, column)
                    for cell_row in range(9)
                    if (cell_row, column) not in box
                )
                eliminations = _removals(state, targets, frozenset((value,)))
                if eliminations:
                    yield EliminationStep(Technique.POINTING, eliminations)


def box_line_reductions(state: LogicalState) -> Iterator[EliminationStep]:
    """Claim a box when a line's two or three digit positions lie inside it.

    Scan rows before columns, ascending line index, then ascending digit.
    """
    for line in _lines():
        for value in range(1, 10):
            positions = _positions(state, line, value)
            if len(positions) not in (2, 3):
                continue
            first_row, first_column = positions[0]
            box_row, box_column = first_row // 3, first_column // 3
            if any(
                row // 3 != box_row or column // 3 != box_column
                for row, column in positions
            ):
                continue
            targets = tuple(
                cell for cell in _box_cells(box_row, box_column) if cell not in line
            )
            eliminations = _removals(state, targets, frozenset((value,)))
            if eliminations:
                yield EliminationStep(Technique.BOX_LINE_REDUCTION, eliminations)
