from spn_dc.difference import DiffCell
from spn_dc.linear import identity_matrix
from spn_dc.session import SPNSession
from spn_dc.sbox import SBox
from spn_dc.spn import SPNRoundSpec


def _id4() -> SBox:
    return SBox(tuple(range(16)))


def test_session_propagate_and_paths():
    s = SPNSession()
    s.reset()
    s.create_spn(2, 2, 4)
    s.set_sbox(0, _id4().table)
    s.set_sbox(1, _id4().table)
    s.set_permutation(identity_matrix(8).rows)
    trail, err = s.propagate_difference(0x11)
    assert err is None
    assert len(trail) == 2
    msg, err2 = s.generate_paths(0x11, max_paths=500)
    assert err2 is None
    assert "generated" in msg


def test_check_constraints_conflict():
    s = SPNSession()
    s.reset()
    s.create_spn(1, 2, 4)
    s.set_sbox(0, _id4().table)
    s.set_sbox(1, _id4().table)
    s.set_permutation(identity_matrix(8).rows)
    s.fix_input_difference(0, 1)
    s.fix_input_difference(1, 2)
    s.link_differences((0, 1))
    trail, err = s.check_constraints()
    assert trail is None
    assert err is not None


def test_cipher_changes_invalidate_generated_paths():
    s = SPNSession()
    s.create_spn(1, 1, 2)
    msg, err = s.generate_paths(1)
    assert err is None and msg
    assert s._paths

    s.set_sbox(0, (0, 2, 3, 1))
    assert s._paths == () and s._paths_filtered is None

    s.generate_paths(1)
    assert s._paths
    s.set_permutation(identity_matrix(2).rows)
    assert s._paths == () and s._paths_filtered is None


def test_constraint_changes_invalidate_generated_paths():
    s = SPNSession()
    s.create_spn(1, 2, 2)
    s.generate_paths(0x5)
    assert s._paths
    s.fix_input_difference(0, 1)
    assert s._paths == ()
