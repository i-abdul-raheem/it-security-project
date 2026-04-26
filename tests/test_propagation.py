from spn_dc.difference import DiffCell
from spn_dc.linear import identity_matrix
from spn_dc.propagation import (
    apply_equality_constraints,
    propagate_multiple_rounds,
    propagate_round_forward_sets,
    narrow_output_with_choice,
)
from spn_dc.sbox import SBox
from spn_dc.spn import SPNRoundSpec


def _identity4() -> SBox:
    return SBox(tuple(range(16)))


def test_round_with_identity_sbox_and_p():
    sb = _identity4()
    p = identity_matrix(8)
    spec = SPNRoundSpec((sb, sb), p)
    before = (DiffCell.concrete(1), DiffCell.concrete(2))
    st = propagate_round_forward_sets(spec, before)
    assert not isinstance(st, str)
    assert st.before_sbox == (frozenset({1}), frozenset({2}))
    assert st.after_sbox == (frozenset({1}), frozenset({2}))
    assert st.after_p == (frozenset({1}), frozenset({2}))


def test_equality_conflict():
    sets = (frozenset({1}), frozenset({2}))
    err = apply_equality_constraints(sets, ((0, 1),))
    assert isinstance(err, str)


def test_narrow_choice_ok():
    sets = (frozenset({1, 2}), frozenset({3}))
    n = narrow_output_with_choice(sets, 0, 2)
    assert n == (frozenset({2}), frozenset({3}))


def test_propagate_multiple_rounds():
    sb = _identity4()
    p = identity_matrix(8)
    spec = SPNRoundSpec((sb, sb), p)
    trail = propagate_multiple_rounds(spec, 3, (DiffCell.concrete(1), DiffCell.concrete(0)))
    assert not isinstance(trail, str)
    assert len(trail) == 3
