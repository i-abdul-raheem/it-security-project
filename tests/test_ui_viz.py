from spn_dc.propagation import RoundSetState
from spn_dc.paths import DifferentialPath
from spn_dc.difference import DiffCell
from spn_dc.sbox import SBox
from spn_dc.ui_analysis import (
    ddt_transition_rows,
    ddt_row_summary,
    ddt_summary,
    constraint_conflict_indices,
    render_backward_differential_svg,
    render_cipher_configuration_svg,
    render_constraint_graph_svg,
    render_activity_matrix_svg,
    render_concrete_sbox_pair_svg,
    render_ddt_heatmap_svg,
    render_differential_trail_svg,
    render_multiround_spn_svg,
    render_path_probability_svg,
    render_path_search_tree_svg,
    p_layer_diffusion_profile,
    render_p_diffusion_svg,
    render_sbox_differential_svg,
)
from spn_dc.ui_viz import frames_from_trail, render_propagation_frame_html


def test_frames_and_html():
    st = RoundSetState((frozenset({0xF}),), (frozenset({1, 2}),), (frozenset({3}),))
    frames = frames_from_trail([st])
    assert len(frames) == 3
    html = render_propagation_frame_html(frames[0], sbox_bits=4, frame_index=0, total_frames=3)
    assert "Before S-box" in html
    assert "S-box 0" in html


def test_ddt_diagrams_and_probability_rows():
    sb = SBox((0, 1, 3, 2))
    heatmap = render_ddt_heatmap_svg(sb.ddt(), selected_input=1)
    transitions = render_sbox_differential_svg(sb, 1)
    rows = ddt_transition_rows(sb, 1)
    summary = ddt_summary(sb.ddt())
    row_summary = ddt_row_summary(sb, 1)
    assert "Difference distribution table" in heatmap
    assert "Δx=0x1" in transitions
    assert rows and abs(sum(row["probability"] for row in rows) - 1.0) < 1e-12
    assert summary["differential_uniformity"] == 4
    assert summary["maximum_probability"] == 1.0
    assert "selected row: Δx = 0x1" in heatmap
    assert row_summary["feasible_outputs"] == len(rows)


def test_large_ddt_transition_diagrams_are_bounded():
    sb = SBox(tuple(range(16)))
    forward = render_sbox_differential_svg(sb, 1, max_nodes=1)
    backward = render_backward_differential_svg(sb, 1, max_nodes=1)
    assert "Δy=0x1" in forward
    assert "Δx=0x1" in backward


def test_structural_and_activity_diagrams():
    state = RoundSetState(
        (frozenset({0}), frozenset({1})),
        (frozenset({0}), frozenset({2})),
        (frozenset({0, 1}), frozenset({3})),
    )
    network = render_multiround_spn_svg(2, 2, 4)
    activity = render_activity_matrix_svg([state])
    pair = render_concrete_sbox_pair_svg(SBox((0, 1, 3, 2)), 0, 1)
    assert "Round 2" in network and "S1 (4b)" in network
    assert "possibly active" in activity and "inactive" in activity
    assert "Δx = 0x1" in pair and "Δy = 0x1" in pair


def test_path_diagrams():
    paths = (
        DifferentialPath(0, 0.25, (((1, 1), (2, 3), (3, 2)), ((3, 2), (4, 5), (5, 4)))),
        DifferentialPath(1, 0.125, (((1, 1), (2, 4), (4, 2)), ((4, 2), (1, 3), (3, 1)))),
    )
    trail = render_differential_trail_svg(paths[0])
    chart = render_path_probability_svg(paths)
    tree = render_path_search_tree_svg(paths)
    assert "Trail 0" in trail and "Round 2" in trail
    assert "id 1" in chart and "0.25" in chart
    assert "round 2" in tree and "2 3" in tree


def test_constraint_conflict_and_backward_diagrams():
    cells = (DiffCell.concrete(1), DiffCell.concrete(2), DiffCell.nonzero())
    groups = ((0, 1),)
    bad = constraint_conflict_indices(cells, groups, 16)
    graph = render_constraint_graph_svg(cells, {2: 3}, groups, n_values=16)
    backward = render_backward_differential_svg(SBox((0, 1, 3, 2)), 1)
    assert bad == frozenset({0, 1})
    assert "empty equality intersection" in graph and "after S2" in graph
    assert "inverse DDT" in backward and "Δx=0x1" in backward


def test_configuration_and_diffusion_diagrams():
    rows = tuple(1 << i for i in range(8))
    profile, branch = p_layer_diffusion_profile(rows, 2, 4)
    config = render_cipher_configuration_svg(rounds=3, num_sboxes=2, sbox_bits=4, p_rows=rows)
    diffusion = render_p_diffusion_svg(rows, 2, 4)
    assert branch == 2
    assert profile[0]["minimum_active_outputs"] == 1
    assert "3" in config and "bit shuffle" in config
    assert "Exact bundle branch number: 2" in diffusion
