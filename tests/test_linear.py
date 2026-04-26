import pytest

from spn_dc.linear import BinaryMatrix, identity_matrix


def test_identity_apply():
    n = 6
    i = identity_matrix(n)
    for x in range(1 << n):
        assert i.apply(x) == x


def test_inverse_roundtrip():
    # Swap coordinate 0 and 1 (self-inverse)
    m = BinaryMatrix(4, (0b0010, 0b0001, 0b0100, 0b1000))
    inv = m.inverse()
    for x in range(16):
        assert inv.apply(m.apply(x)) == x
        assert m.apply(inv.apply(x)) == x


def test_non_invertible_raises():
    with pytest.raises(ValueError):
        BinaryMatrix(2, (0b11, 0b11))
