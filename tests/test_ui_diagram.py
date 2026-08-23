from spn_dc.linear import identity_matrix
from spn_dc.ui_diagram import (
    pin_state_at_bit,
    pin_states_from_slices,
    render_spn_bit_diagram_svg,
)


def test_pin_states():
    assert pin_state_at_bit(frozenset({0b1011}), 0) == "1"
    assert pin_state_at_bit(frozenset({0b1011}), 1) == "1"
    assert pin_state_at_bit(frozenset({0, 1}), 0) == "?"
    assert pin_states_from_slices((frozenset({0xF}), frozenset({0})), 4) == ["1"] * 4 + ["0"] * 4


def test_svg_contains_boxes_and_pins():
    p = identity_matrix(8)
    svg = render_spn_bit_diagram_svg(
        num_sboxes=2,
        sbox_bits=4,
        p_rows=p.rows,
        input_states=["1", "0", "1", "1", "0", "0", "0", "0"],
        active_layer="before_sbox",
    )
    assert "S0" in svg and "S1" in svg
    assert "b0" in svg
    assert "<circle" in svg
