from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import FrozenSet


def _validate_bijection(table: tuple[int, ...]) -> None:
    n = len(table)
    if n == 0 or (n & (n - 1)) != 0:
        raise ValueError("S-box length must be a positive power of two")
    bits = n.bit_length() - 1
    seen = [False] * n
    for v in table:
        if v < 0 or v >= n or seen[v]:
            raise ValueError("S-box must be a permutation of 0..n-1")
        seen[v] = True


@dataclass(frozen=True)
class SBox:
    """n-bit S-box as a permutation table: image of x is table[x]."""

    table: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "table", tuple(self.table))
        _validate_bijection(self.table)

    @property
    def n(self) -> int:
        return len(self.table)

    @property
    def bits(self) -> int:
        return self.n.bit_length() - 1

    def image(self, x: int) -> int:
        return self.table[x]

    @lru_cache(maxsize=256)
    def ddt(self) -> tuple[tuple[int, ...], ...]:
        """Difference distribution table: ddt[da][db] = count of x with S(x^da)^S(x)=db."""
        n = self.n
        rows: list[tuple[int, ...]] = []
        for da in range(n):
            row = [0] * n
            for x in range(n):
                db = self.table[x ^ da] ^ self.table[x]
                row[db] += 1
            rows.append(tuple(row))
        return tuple(rows)

    @lru_cache(maxsize=256)
    def inv_ddt(self) -> tuple[tuple[int, ...], ...]:
        """Transpose view: for output difference db, input differences da with positive count."""
        ddt = self.ddt()
        n = self.n
        cols: list[list[int]] = [[0] * n for _ in range(n)]
        for da in range(n):
            for db in range(n):
                cols[db][da] = ddt[da][db]
        return tuple(tuple(r) for r in cols)

    def output_diffs_for_input(self, da: int) -> FrozenSet[int]:
        if not 0 <= da < self.n:
            raise ValueError("input difference out of range")
        ddt = self.ddt()
        return frozenset(db for db in range(self.n) if ddt[da][db] > 0)

    def input_diffs_for_output(self, db: int) -> FrozenSet[int]:
        if not 0 <= db < self.n:
            raise ValueError("output difference out of range")
        inv = self.inv_ddt()
        return frozenset(da for da in range(self.n) if inv[db][da] > 0)
