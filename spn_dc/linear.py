from __future__ import annotations

from dataclasses import dataclass


def _popcount(x: int) -> int:
    c = 0
    while x:
        c += x & 1
        x >>= 1
    return c


def _gf2_rank(rows: list[int], n: int) -> int:
    """Rank of n×n matrix; rows[i] holds bits M[i,0..n-1] with LSB = column 0."""
    cp = rows[:]
    r = 0
    for col in range(n):
        piv = 1 << col
        pivot_row = None
        for i in range(r, n):
            if cp[i] & piv:
                pivot_row = i
                break
        if pivot_row is None:
            continue
        cp[r], cp[pivot_row] = cp[pivot_row], cp[r]
        for i in range(n):
            if i != r and (cp[i] & piv):
                cp[i] ^= cp[r]
        r += 1
    return r


@dataclass(frozen=True)
class BinaryMatrix:
    """
    Square GF(2) linear map y = M @ x with x,y ∈ GF(2)^n.

    Bit j of integer x (LSB = j = 0) is coordinate x_j.
    Row i of M is `rows[i]`: bit j set means M[i,j] = 1.
    Output y has y_i = (popcount(rows[i] & x)) mod 2, stored as bit i of the result int.
    """

    dim: int
    rows: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.dim <= 0:
            raise ValueError("dim must be positive")
        rows = tuple(int(r) for r in self.rows)
        if len(rows) != self.dim:
            raise ValueError("need exactly dim row masks")
        mask = (1 << self.dim) - 1
        for r in rows:
            if r < 0 or r > mask:
                raise ValueError("row mask out of range")
        object.__setattr__(self, "rows", rows)
        if _gf2_rank(list(self.rows), self.dim) != self.dim:
            raise ValueError("matrix must be invertible (bijective linear map)")

    def apply(self, x: int) -> int:
        if x < 0 or x >= (1 << self.dim):
            raise ValueError("vector out of range")
        y = 0
        for i, row in enumerate(self.rows):
            if _popcount(row & x) & 1:
                y |= 1 << i
        return y

    def inverse(self) -> BinaryMatrix:
        n = self.dim
        aug = [self.rows[i] | ((1 << i) << n) for i in range(n)]
        for col in range(n):
            piv = 1 << col
            pivot_r = None
            for r in range(col, n):
                if aug[r] & piv:
                    pivot_r = r
                    break
            if pivot_r is None:
                raise ValueError("singular matrix")
            aug[col], aug[pivot_r] = aug[pivot_r], aug[col]
            for r in range(n):
                if r != col and (aug[r] & piv):
                    aug[r] ^= aug[col]
        left_mask = (1 << n) - 1
        inv_rows: list[int] = []
        for i in range(n):
            left = aug[i] & left_mask
            if left != (1 << i):
                raise ValueError("elimination did not yield identity")
            inv_rows.append((aug[i] >> n) & left_mask)
        return BinaryMatrix(n, tuple(inv_rows))


def identity_matrix(n: int) -> BinaryMatrix:
    return BinaryMatrix(n, tuple(1 << i for i in range(n)))
