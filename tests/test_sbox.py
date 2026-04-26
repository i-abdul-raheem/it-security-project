import pytest

from spn_dc.sbox import SBox


def test_present_sbox_is_permutation():
    t = (
        12,
        5,
        6,
        11,
        9,
        0,
        10,
        13,
        3,
        14,
        15,
        8,
        4,
        7,
        1,
        2,
    )
    sb = SBox(t)
    assert sb.n == 16
    assert set(sb.table) == set(range(16))


def test_invalid_sbox():
    with pytest.raises(ValueError):
        SBox((0, 0))


def test_ddt_row_sums():
    sb = SBox((1, 0))  # 1-bit "S-box" swap
    ddt = sb.ddt()
    for da in range(2):
        assert sum(ddt[da]) == 2
