from spn_dc.propagation import RoundSetState
from spn_dc.ui_viz import frames_from_trail, render_propagation_frame_html


def test_frames_and_html():
    st = RoundSetState((frozenset({0xF}),), (frozenset({1, 2}),), (frozenset({3}),))
    frames = frames_from_trail([st])
    assert len(frames) == 3
    html = render_propagation_frame_html(frames[0], sbox_bits=4, frame_index=0, total_frames=3)
    assert "Before S-box" in html
    assert "S-box 0" in html
