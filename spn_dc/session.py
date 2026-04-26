from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from pathlib import Path

from spn_dc.difference import DiffCell, DiffKind, cell_to_set
from spn_dc.linear import BinaryMatrix, identity_matrix
from spn_dc.parsing import parse_mapping, parse_matrix_rows
from spn_dc.paths import (
    DifferentialPath,
    filter_paths_by_probability,
    first_round_starts_from_sets,
    generate_paths_with_starts,
    path_respects_equality_groups,
)
from spn_dc.propagation import (
    narrow_round1_cells,
    propagate_round_forward_sets,
    refine_round_with_output_fixes,
    sets_to_diff_cells,
)
from spn_dc.sbox import SBox
from spn_dc.spn import SPNParams, SPNRoundSpec


def identity_sbox(bits: int) -> SBox:
    n = 1 << bits
    return SBox(tuple(range(n)))


def random_sbox(bits: int, rng: random.Random | None = None) -> SBox:
    r = rng or random.Random()
    t = list(range(1 << bits))
    r.shuffle(t)
    return SBox(tuple(t))


def random_bijective_matrix(dim: int, rng: random.Random | None = None) -> BinaryMatrix:
    r = rng or random.Random()
    while True:
        rows = tuple(r.randrange(1 << dim) for _ in range(dim))
        try:
            return BinaryMatrix(dim, rows)
        except ValueError:
            continue


def state_file_path() -> Path:
    return Path(os.environ.get("SPN_DC_STATE", ".spn_dc_state.json")).expanduser()


def persist_enabled() -> bool:
    return os.environ.get("SPN_DC_NO_PERSIST", "").lower() not in ("1", "true", "yes")


def persist_session(sess: "SPNSession") -> None:
    if not persist_enabled():
        return
    p = state_file_path()
    if not sess._sboxes or sess._rounds == 0:
        if p.exists():
            p.unlink()
        return
    p.write_text(sess.to_json())


def load_default_from_disk() -> None:
    global _default_session
    if not persist_enabled():
        return
    p = state_file_path()
    if p.exists():
        try:
            _default_session = SPNSession.from_json(p.read_text())
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            pass


def _cell_to_dict(c: DiffCell) -> dict:
    if c.kind is DiffKind.ANY:
        return {"kind": "any"}
    if c.kind is DiffKind.ZERO:
        return {"kind": "zero"}
    if c.kind is DiffKind.NONZERO:
        return {"kind": "nonzero"}
    if c.kind is DiffKind.CONCRETE:
        return {"kind": "concrete", "value": c.value}
    if c.kind is DiffKind.SET:
        return {"kind": "set", "members": sorted(c.members or ())}
    raise TypeError("unknown DiffCell kind")


def _cell_from_dict(d: dict) -> DiffCell:
    k = d["kind"]
    if k == "any":
        return DiffCell.any_()
    if k == "zero":
        return DiffCell.zero()
    if k == "nonzero":
        return DiffCell.nonzero()
    if k == "concrete":
        return DiffCell.concrete(int(d["value"]))
    if k == "set":
        return DiffCell.subset(frozenset(int(x) for x in d["members"]))
    raise ValueError(f"unknown cell kind {k}")


@dataclass
class SPNSession:
    """Mutable analysis session: cipher shape, S-boxes, P-layer, constraints, cached paths."""

    _rounds: int = 0
    _num_sboxes: int = 0
    _sbox_bits: int = 4
    _sboxes: list[SBox] = field(default_factory=list)
    _p: BinaryMatrix | None = None
    _input_cells: list[DiffCell] = field(default_factory=list)
    _output_fix: dict[int, int] = field(default_factory=dict)
    _equality_groups: list[tuple[int, ...]] = field(default_factory=list)
    _paths: tuple[DifferentialPath, ...] = ()
    _paths_filtered: tuple[DifferentialPath, ...] | None = None

    def reset(self) -> None:
        self._rounds = 0
        self._num_sboxes = 0
        self._sbox_bits = 4
        self._sboxes = []
        self._p = None
        self._input_cells = []
        self._output_fix = {}
        self._equality_groups = []
        self._paths = ()
        self._paths_filtered = None
        persist_session(self)

    def create_spn(self, rounds: int, sboxes: int, sbox_bits: int = 4) -> None:
        if rounds < 1 or sboxes < 1 or sbox_bits < 1:
            raise ValueError("rounds, sboxes, and sbox_bits must be positive")
        self._rounds = rounds
        self._num_sboxes = sboxes
        self._sbox_bits = sbox_bits
        self._sboxes = [identity_sbox(sbox_bits) for _ in range(sboxes)]
        dim = sboxes * sbox_bits
        self._p = identity_matrix(dim)
        self._input_cells = [DiffCell.any_() for _ in range(sboxes)]
        self._output_fix = {}
        self._equality_groups = []
        self._paths = ()
        self._paths_filtered = None
        persist_session(self)

    def to_json(self) -> str:
        self._require_cipher()
        payload = {
            "v": 1,
            "rounds": self._rounds,
            "num_sboxes": self._num_sboxes,
            "sbox_bits": self._sbox_bits,
            "sboxes": [list(sb.table) for sb in self._sboxes],
            "p_rows": list(self._p.rows) if self._p else [],
            "input_cells": [_cell_to_dict(c) for c in self._input_cells],
            "output_fix": {str(k): int(v) for k, v in self._output_fix.items()},
            "equality_groups": [list(g) for g in self._equality_groups],
        }
        return json.dumps(payload, indent=2)

    @classmethod
    def from_json(cls, data: str) -> SPNSession:
        d = json.loads(data)
        if d.get("v") != 1:
            raise ValueError("unsupported state file version")
        s = cls()
        s._rounds = int(d["rounds"])
        s._num_sboxes = int(d["num_sboxes"])
        s._sbox_bits = int(d["sbox_bits"])
        s._sboxes = [SBox(tuple(int(x) for x in tab)) for tab in d["sboxes"]]
        dim = s._num_sboxes * s._sbox_bits
        rows = tuple(int(x) for x in d["p_rows"])
        if len(rows) != dim:
            raise ValueError("P-layer row count mismatch")
        s._p = BinaryMatrix(dim, rows)
        s._input_cells = [_cell_from_dict(x) for x in d["input_cells"]]
        s._output_fix = {int(k): int(v) for k, v in d.get("output_fix", {}).items()}
        s._equality_groups = [tuple(int(x) for x in g) for g in d.get("equality_groups", [])]
        s._paths = ()
        s._paths_filtered = None
        return s

    def _require_cipher(self) -> None:
        if not self._sboxes or self._p is None:
            raise RuntimeError("call create_spn first")

    def round_spec(self) -> SPNRoundSpec:
        self._require_cipher()
        return SPNRoundSpec(tuple(self._sboxes), self._p)

    def params(self) -> SPNParams:
        return SPNParams(self._rounds, self.round_spec())

    def set_sbox(self, index: int, mapping: tuple[int, ...] | list[int] | str) -> None:
        self._require_cipher()
        if isinstance(mapping, str):
            mapping = parse_mapping(mapping)
        if index < 0 or index >= self._num_sboxes:
            raise IndexError("S-box index out of range")
        sb = SBox(tuple(mapping))
        if sb.bits != self._sbox_bits:
            raise ValueError(f"S-box width is {sb.bits} bits but cipher uses {self._sbox_bits} bits per S-box")
        self._sboxes[index] = sb
        persist_session(self)

    def set_permutation(self, matrix: tuple[int, ...] | list[int] | str) -> None:
        self._require_cipher()
        if isinstance(matrix, str):
            rows = parse_matrix_rows(matrix)
        else:
            rows = tuple(matrix)
        dim = self._num_sboxes * self._sbox_bits
        if len(rows) != dim:
            raise ValueError(f"expected {dim} row masks for P-layer, got {len(rows)}")
        self._p = BinaryMatrix(dim, tuple(rows))
        persist_session(self)

    def compute_ddt(self, sbox_id: int) -> tuple[tuple[int, ...], ...]:
        self._require_cipher()
        if sbox_id < 0 or sbox_id >= self._num_sboxes:
            raise IndexError("sbox id out of range")
        return self._sboxes[sbox_id].ddt()

    def fix_input_difference(self, position: int, value: int) -> None:
        self._require_cipher()
        if position < 0 or position >= self._num_sboxes:
            raise IndexError("position out of range")
        n = 1 << self._sbox_bits
        if not 0 <= value < n:
            raise ValueError("difference value out of range")
        self._input_cells[position] = DiffCell.concrete(value)
        persist_session(self)

    def fix_output_difference(self, position: int, value: int) -> None:
        self._require_cipher()
        n = 1 << self._sbox_bits
        if not 0 <= position < self._num_sboxes:
            raise IndexError("position out of range")
        if not 0 <= value < n:
            raise ValueError("difference value out of range")
        self._output_fix[position] = value
        persist_session(self)

    def set_abstract_difference(self, position: int) -> None:
        self._require_cipher()
        if position < 0 or position >= self._num_sboxes:
            raise IndexError("position out of range")
        self._input_cells[position] = DiffCell.nonzero()
        persist_session(self)

    def set_constraint(self, typ: str, positions: tuple[int, ...]) -> None:
        if typ.lower() != "equal":
            raise ValueError("only type 'equal' is supported")
        self.link_differences(positions)

    def link_differences(self, positions: tuple[int, ...]) -> None:
        self._require_cipher()
        if len(positions) < 2:
            raise ValueError("need at least two positions to link")
        for p in positions:
            if p < 0 or p >= self._num_sboxes:
                raise IndexError("position out of range")
        self._equality_groups.append(tuple(positions))
        persist_session(self)

    def _narrowed_round1_cells(self, packed_dx: int | None) -> tuple[DiffCell, ...] | str:
        return narrow_round1_cells(
            tuple(self._input_cells),
            packed_dx,
            tuple(self._equality_groups),
            self._num_sboxes,
            self._sbox_bits,
        )

    def check_constraints(self):
        """Returns (trail, None) on success or (None, error_message)."""
        self._require_cipher()
        cells = self._narrowed_round1_cells(None)
        if isinstance(cells, str):
            return None, cells
        spec = self.round_spec()
        trail = []
        cur = cells
        for ri in range(self._rounds):
            st = propagate_round_forward_sets(spec, cur)
            if isinstance(st, str):
                return None, st
            if ri == 0 and self._output_fix:
                st = refine_round_with_output_fixes(spec, st, self._output_fix)
                if isinstance(st, str):
                    return None, st
            trail.append(st)
            cur = sets_to_diff_cells(st.after_p)
        return trail, None

    apply_constraints = check_constraints

    def propagate_difference(self, input_dx: int):
        """Propagate packed Δx through all rounds (respects fixes, equality, output round-0 fixes)."""
        self._require_cipher()
        cells = self._narrowed_round1_cells(input_dx)
        if isinstance(cells, str):
            return None, cells
        spec = self.round_spec()
        trail = []
        cur = cells
        for ri in range(self._rounds):
            st = propagate_round_forward_sets(spec, cur)
            if isinstance(st, str):
                return None, st
            if ri == 0 and self._output_fix:
                st = refine_round_with_output_fixes(spec, st, self._output_fix)
                if isinstance(st, str):
                    return None, st
            trail.append(st)
            cur = sets_to_diff_cells(st.after_p)
        return trail, None

    def analyze_round(self, round_r: int, input_diff: int) -> object | str:
        """1-based round index; returns that round's RoundSetState."""
        if round_r < 1 or round_r > self._rounds:
            return "round index out of range"
        trail, err = self.propagate_difference(input_diff)
        if err:
            return err
        return trail[round_r - 1]

    def generate_paths(self, input_diff: int, *, max_paths: int = 50_000) -> tuple[str, None] | tuple[None, str]:
        self._require_cipher()
        spec = self.round_spec()
        cells = self._narrowed_round1_cells(input_diff)
        if isinstance(cells, str):
            return None, cells
        n = 1 << self._sbox_bits
        sets = tuple(cell_to_set(c, n) for c in cells)
        starts_e = first_round_starts_from_sets(sets, max_starts=2048)
        if isinstance(starts_e, str):
            return None, starts_e
        starts = tuple(s for s in starts_e if path_respects_equality_groups(s, tuple(self._equality_groups)))
        if not starts:
            return None, "no starting tuples satisfy equality constraints"
        paths, trunc = generate_paths_with_starts(spec, self._rounds, starts, max_paths=max_paths)
        self._paths = paths
        self._paths_filtered = None
        msg = f"generated {len(paths)} path(s)" + (" (truncated to cap)" if trunc else "")
        persist_session(self)
        return msg, None

    def filter_paths(self, min_probability: float, *, strict: bool = True) -> None:
        if not self._paths:
            raise RuntimeError("no paths; run generate_paths first")
        self._paths_filtered = filter_paths_by_probability(
            self._paths, min_probability=min_probability, strict=strict
        )
        persist_session(self)

    def show_path(self, path_id: int) -> DifferentialPath | None:
        pool = self._paths_filtered if self._paths_filtered is not None else self._paths
        for p in pool:
            if p.path_id == path_id:
                return p
        return None


_default_session = SPNSession()


def get_session() -> SPNSession:
    return _default_session


def reset() -> None:
    _default_session.reset()


def create_spn(rounds: int, sboxes: int, sbox_bits: int = 4) -> SPNSession:
    _default_session.create_spn(rounds, sboxes, sbox_bits)
    return _default_session


def set_sbox(index: int, mapping: tuple[int, ...] | list[int] | str) -> None:
    _default_session.set_sbox(index, mapping)


def set_permutation(matrix: tuple[int, ...] | list[int] | str) -> None:
    _default_session.set_permutation(matrix)


def compute_ddt(sbox_id: int) -> tuple[tuple[int, ...], ...]:
    return _default_session.compute_ddt(sbox_id)


def propagate_difference(input_dx: int):
    return _default_session.propagate_difference(input_dx)


def apply_constraints():
    return _default_session.check_constraints()


def check_constraints():
    return _default_session.check_constraints()


def fix_input_difference(position: int, value: int) -> None:
    _default_session.fix_input_difference(position, value)


def fix_output_difference(position: int, value: int) -> None:
    _default_session.fix_output_difference(position, value)


def set_abstract_difference(position: int) -> None:
    _default_session.set_abstract_difference(position)


def set_constraint_equal(positions: tuple[int, ...]) -> None:
    _default_session.set_constraint("equal", positions)


def link_differences(positions: tuple[int, ...]) -> None:
    _default_session.link_differences(positions)


def generate_paths(input_diff: int, *, max_paths: int = 50_000):
    return _default_session.generate_paths(input_diff, max_paths=max_paths)


def filter_paths(min_probability: float, *, strict: bool = True) -> None:
    _default_session.filter_paths(min_probability, strict=strict)


def show_path(path_id: int):
    return _default_session.show_path(path_id)
