import pytest

from spn_dc.difference import DiffCell
from spn_dc.linear import identity_matrix
from spn_dc.session import SPNSession, random_permutation_matrix
from spn_dc.sbox import SBox
from spn_dc.spn import SPNRoundSpec


def _id4() -> SBox:
    return SBox(tuple(range(16)))


def test_random_permutation_matrix_is_one_to_one():
    matrix = random_permutation_matrix(16)
    assert all(row.bit_count() == 1 for row in matrix.rows)
    assert len(set(matrix.rows)) == matrix.dim


def test_session_rejects_one_to_many_p_layer():
    s = SPNSession()
    s.create_spn(1, 2, 2)
    with pytest.raises(ValueError, match="one input connected to one output"):
        s.set_permutation((0b0011, 0b0010, 0b0100, 0b1000))


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
