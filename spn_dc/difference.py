from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import FrozenSet


class DiffKind(Enum):
    """How constrained a single n-bit difference cell is."""

    ANY = auto()  # completely unconstrained
    ZERO = auto()  # forced to 0
    NONZERO = auto()  # not 0, value unspecified ("abstract" nonzero)
    CONCRETE = auto()  # fixed value
    SET = auto()  # one of several values (after narrowing / branching)


@dataclass(frozen=True)
class DiffCell:
    """One S-box-sized difference with optional concrete value."""

    kind: DiffKind
    value: int = 0  # meaningful when kind is CONCRETE (or ZERO)
    members: frozenset[int] | None = None  # required when kind is SET

    def __post_init__(self) -> None:
        if self.kind is DiffKind.SET:
            if not self.members:
                raise ValueError("SET cell requires non-empty members")
        elif self.members is not None:
            raise ValueError("members is only valid for SET")

    @staticmethod
    def concrete(v: int) -> DiffCell:
        return DiffCell(DiffKind.CONCRETE, v, None)

    @staticmethod
    def zero() -> DiffCell:
        return DiffCell(DiffKind.ZERO, 0, None)

    @staticmethod
    def nonzero() -> DiffCell:
        return DiffCell(DiffKind.NONZERO, 0, None)

    @staticmethod
    def any_() -> DiffCell:
        return DiffCell(DiffKind.ANY, 0, None)

    @staticmethod
    def subset(s: FrozenSet[int]) -> DiffCell:
        if not s:
            raise ValueError("subset cell cannot be empty")
        if len(s) == 1:
            (v,) = tuple(s)
            return DiffCell.concrete(v)
        return DiffCell(DiffKind.SET, 0, frozenset(s))


def diff_set_intersection(a: FrozenSet[int], b: FrozenSet[int]) -> FrozenSet[int]:
    return frozenset(x for x in a if x in b)


def cell_to_set(cell: DiffCell, n_values: int) -> FrozenSet[int]:
    """Expand a cell to the set of integer differences it allows (for n-bit S-box domain)."""
    if cell.kind is DiffKind.ANY:
        return frozenset(range(n_values))
    if cell.kind is DiffKind.ZERO:
        return frozenset({0})
    if cell.kind is DiffKind.NONZERO:
        return frozenset(v for v in range(n_values) if v != 0)
    if cell.kind is DiffKind.CONCRETE:
        if not 0 <= cell.value < n_values:
            raise ValueError("concrete value out of range")
        return frozenset({cell.value})
    if cell.kind is DiffKind.SET:
        if cell.members is None:
            raise ValueError("SET cell requires members")
        bad = [v for v in cell.members if not 0 <= v < n_values]
        if bad:
            raise ValueError("SET member out of range")
        return frozenset(cell.members)
    raise TypeError("unknown kind")
