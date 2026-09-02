from spn_dc.linear import identity_matrix
from spn_dc.ui_diagram import (
    pin_state_at_bit,
    pin_states_from_slices,
    render_spn_bit_diagram_svg,
    render_sbox_to_p_layer_svg,
    sbox_bit_dependencies,
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
        sbox_tables=(tuple(range(16)), tuple(reversed(range(16)))),
        input_states=["1", "0", "1", "1", "0", "0", "0", "0"],
        active_layer="before_sbox",
    )
    assert "S0" in svg and "S1" in svg
    assert "b0" in svg
    assert "<circle" in svg
    assert ">=</text>" in svg
    assert "0→0 1→1 2→2" in svg
    assert "0→F 1→E 2→D" in svg
    assert "data-sbox-dependency" in svg
    assert "can influence output bit" in svg


def test_general_p_layer_has_xor_nodes():
    # Invertible triangular matrix; y1 = x0 XOR x1.
    p_rows = (0b01, 0b11)
    svg = render_spn_bit_diagram_svg(
        num_sboxes=1,
        sbox_bits=2,
        p_rows=p_rows,
        active_layer="after_p",
    )
    assert ">⊕</text>" in svg


def test_sbox_dependencies_are_derived_from_mapping():
    identity = sbox_bit_dependencies((0, 1, 2, 3), 2)
    mixed = sbox_bit_dependencies((0, 3, 1, 2), 2)
    assert identity == [(0, 0), (1, 1)]
    assert set(mixed) == {(0, 0), (0, 1), (1, 0)}


def test_sbox_outputs_to_p_layer_diagram():
    # y0 = S0.o0 XOR S1.o0; remaining outputs are copied.
    rows = (0b0101, 0b0010, 0b0100, 0b1000)
    svg = render_sbox_to_p_layer_svg(num_sboxes=2, sbox_bits=2, p_rows=rows)
    assert "S0.o0 (b0)" in svg
    assert "S1.o0 (b2)" in svg
    assert "y0 = b0 ⊕ b2" in svg
    assert "S1.o0 → P input b2 → y0" in svg
