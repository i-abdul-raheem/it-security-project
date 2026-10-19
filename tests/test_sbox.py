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


def test_permutation_ddt_invariants_and_cache():
    sb = SBox((0, 1, 3, 2))
    ddt = sb.ddt()
    assert sb.ddt() is ddt
    assert ddt[0] == (4, 0, 0, 0)
    assert all(ddt[dx][0] == 0 for dx in range(1, sb.n))
    assert all(value % 2 == 0 for row in ddt for value in row)
    inv = sb.inv_ddt()
    assert all(inv[dy][dx] == ddt[dx][dy] for dx in range(sb.n) for dy in range(sb.n))
