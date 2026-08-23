from spn_dc.linear import identity_matrix
from spn_dc.sbox import SBox
from spn_dc.ui_permutation import (
    bit_permutation_wiring,
    is_pure_bit_permutation,
    render_sbox_permutation_svg,
    sbox_mapping_rows,
)


def test_sbox_mapping_rows():
    sb = SBox(tuple(range(16)))
    rows = sbox_mapping_rows(sb.table, 4)
    assert len(rows) == 16
    assert rows[0]["input (dec)"] == 0
    assert rows[0]["output S(x) (dec)"] == 0


def test_identity_p_is_bit_permutation():
    p = identity_matrix(4)
    assert is_pure_bit_permutation(p.rows)
    assert bit_permutation_wiring(p.rows) == [(0, 0), (1, 1), (2, 2), (3, 3)]


def test_sbox_svg():
    sb = SBox((1, 0, 3, 2))
    svg = render_sbox_permutation_svg(sb.table, 2)
    assert "<path" in svg
