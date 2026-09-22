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


def _peers(cell: _Cell) -> _Unit:
    """Return all other cells sharing the cell's row, column, or box.

    The row-major ordering gives XY-Wing pincer and target scans a stable
    coordinate order without maintaining a second candidate representation.
    """
    row, column = cell
    return tuple(
        (other_row, other_column)
        for other_row in range(9)
        for other_column in range(9)
        if (other_row, other_column) != cell
        and (
            other_row == row
            or other_column == column
            or (other_row // 3, other_column // 3) == (row // 3, column // 3)
        )
    )


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


def naked_triples(state: LogicalState) -> Iterator[EliminationStep]:
    """Remove a three-digit triple from other cells in one unit.

    Units are rows, columns, then boxes. Candidate cell combinations are
    row-major. Exactly three cells in the whole unit must be non-empty subsets
    of the triple digits, preventing a four-cell subset false positive.
    """
    for unit in _units():
        for cells in combinations(unit, 3):
            values = frozenset().union(*(_options(state, cell) for cell in cells))
            if len(values) != 3 or any(
                not _options(state, cell) or not _options(state, cell) <= values
                for cell in cells
            ):
                continue
            confined_cells = tuple(
                cell
                for cell in unit
                if _options(state, cell) and _options(state, cell) <= values
            )
            if confined_cells != cells:
                continue
            targets = tuple(cell for cell in unit if cell not in cells)
            eliminations = _removals(state, targets, values)
            if eliminations:
                yield EliminationStep(Technique.NAKED_TRIPLE, eliminations)


def hidden_triples(state: LogicalState) -> Iterator[EliminationStep]:
    """Restrict three cells when three digits occur only within those cells.

    Units are rows, columns, then boxes. Digits and their three-cell union are
    considered in ascending combination order. Every selected digit must occur
    at least once, and no selected digit may appear outside the selected cells.
    """
    for unit in _units():
        positions = {value: _positions(state, unit, value) for value in range(1, 10)}
        for digits in combinations(range(1, 10), 3):
            cells = tuple(
                cell
                for cell in unit
                if any(cell in positions[value] for value in digits)
            )
            if len(cells) != 3 or any(not positions[value] for value in digits):
                continue
            values = frozenset(digits)
            eliminations = tuple(
                CandidateElimination(row, column, value)
                for row, column in cells
                for value in sorted(_options(state, (row, column)) - values)
            )
            if eliminations:
                yield EliminationStep(Technique.HIDDEN_TRIPLE, eliminations)


def x_wings(state: LogicalState) -> Iterator[EliminationStep]:
    """Find canonical row-based then column-based two-by-two X-Wings.

    Digits scan ascending. For each orientation, source-line combinations scan
    ascending, and eliminations are emitted in canonical coordinate order.
    """
    for value in range(1, 10):
        row_positions = {
            row: tuple(
                column for column in range(9) if value in _options(state, (row, column))
            )
            for row in range(9)
        }
        for first_row, second_row in combinations(range(9), 2):
            columns = row_positions[first_row]
            if len(columns) != 2 or columns != row_positions[second_row]:
                continue
            targets = tuple(
                (row, column)
                for row in range(9)
                if row not in (first_row, second_row)
                for column in columns
            )
            eliminations = _removals(state, targets, frozenset((value,)))
            if eliminations:
                yield EliminationStep(Technique.X_WING, eliminations)
    for value in range(1, 10):
        column_positions = {
            column: tuple(
                row for row in range(9) if value in _options(state, (row, column))
            )
            for column in range(9)
        }
        for first_column, second_column in combinations(range(9), 2):
            rows = column_positions[first_column]
            if len(rows) != 2 or rows != column_positions[second_column]:
                continue
            targets = tuple(
                (row, column)
                for row in rows
                for column in range(9)
                if column not in (first_column, second_column)
            )
            eliminations = _removals(state, targets, frozenset((value,)))
            if eliminations:
                yield EliminationStep(Technique.X_WING, eliminations)


def xy_wings(state: LogicalState) -> Iterator[EliminationStep]:
    """Find XY-Wings with row-major pivots and pincers.

    A pivot ``{X, Y}`` is considered in row-major order with ``X < Y``. Its
    ``{X, Z}`` pincer then precedes its ``{Y, Z}`` pincer in row-major order.
    The eliminated ``Z`` candidates are emitted in row-major order. Pincers
    may share any peer relation with the pivot and do not need to see each other.
    """
    cells = tuple((row, column) for row in range(9) for column in range(9))
    for pivot in cells:
        pivot_values = _options(state, pivot)
        if len(pivot_values) != 2:
            continue
        first, second = sorted(pivot_values)
        pivot_peers = _peers(pivot)
        for first_pincer in pivot_peers:
            first_values = _options(state, first_pincer)
            if len(first_values) != 2 or first_values & pivot_values != {first}:
                continue
            third_values = first_values - pivot_values
            if len(third_values) != 1:
                continue
            third = next(iter(third_values))
            for second_pincer in pivot_peers:
                if second_pincer == first_pincer:
                    continue
                if _options(state, second_pincer) != frozenset((second, third)):
                    continue
                participants = frozenset((pivot, first_pincer, second_pincer))
                second_peers = frozenset(_peers(second_pincer))
                targets = tuple(
                    cell
                    for cell in _peers(first_pincer)
                    if cell in second_peers and cell not in participants
                )
                eliminations = _removals(state, targets, frozenset((third,)))
                if eliminations:
                    yield EliminationStep(Technique.XY_WING, eliminations)


def swordfish(state: LogicalState) -> Iterator[EliminationStep]:
    """Find row-based then column-based Swordfish deductions.

    Within each orientation, digits scan ascending and source-line triples use
    lexicographic combination order. Each source line has two or three
    positions, their union has exactly three target lines, and removals are in
    canonical row-major order.
    """
    for value in range(1, 10):
        positions = {
            row: tuple(
                column for column in range(9) if value in _options(state, (row, column))
            )
            for row in range(9)
        }
        for source_rows in combinations(range(9), 3):
            columns = tuple(
                sorted({column for row in source_rows for column in positions[row]})
            )
            if (
                any(not 2 <= len(positions[row]) <= 3 for row in source_rows)
                or len(columns) != 3
            ):
                continue
            targets = tuple(
                (row, column)
                for row in range(9)
                if row not in source_rows
                for column in columns
            )
            eliminations = _removals(state, targets, frozenset((value,)))
            if eliminations:
                yield EliminationStep(Technique.SWORDFISH, eliminations)
    for value in range(1, 10):
        positions = {
            column: tuple(
                row for row in range(9) if value in _options(state, (row, column))
            )
            for column in range(9)
        }
        for source_columns in combinations(range(9), 3):
            rows = tuple(
                sorted({row for column in source_columns for row in positions[column]})
            )
            if (
                any(not 2 <= len(positions[column]) <= 3 for column in source_columns)
                or len(rows) != 3
            ):
                continue
            targets = tuple(
                (row, column)
                for row in rows
                for column in range(9)
                if column not in source_columns
            )
            eliminations = _removals(state, targets, frozenset((value,)))
            if eliminations:
                yield EliminationStep(Technique.SWORDFISH, eliminations)
