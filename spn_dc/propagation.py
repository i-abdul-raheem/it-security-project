from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet

from spn_dc.difference import DiffCell, cell_to_set, diff_set_intersection
from spn_dc.linear import BinaryMatrix
from spn_dc.sbox import SBox
from spn_dc.spn import SPNRoundSpec


def _split_block(x: int, num_sboxes: int, sbox_bits: int) -> tuple[int, ...]:
    """LSB-first chunks: index 0 is least significant sbox_bits of x."""
    mask = (1 << sbox_bits) - 1
    parts: list[int] = []
    for _ in range(num_sboxes):
        parts.append(x & mask)
        x >>= sbox_bits
    return tuple(parts)


def _merge_block(parts: tuple[int, ...], sbox_bits: int) -> int:
    """Inverse of _split_block (concatenate LSB-first parts)."""
    x = 0
    for i in range(len(parts) - 1, -1, -1):
        x <<= sbox_bits
        x |= parts[i]
    return x


@dataclass(frozen=True)
class RoundSetState:
    """Feasible difference values per S-box slice after each layer (exact, small n only)."""

    before_sbox: tuple[FrozenSet[int], ...]
    after_sbox: tuple[FrozenSet[int], ...]
    after_p: tuple[FrozenSet[int], ...]


def propagate_sbox_forward(
    sboxes: tuple[SBox, ...], cells: tuple[DiffCell, ...]
) -> tuple[FrozenSet[int], ...] | str:
    """
    For each S-box cell, return the set of possible output differences given input cell semantics.
    """
    if len(sboxes) != len(cells):
        return "S-box count does not match cell count"
    out_sets: list[FrozenSet[int]] = []
    for sb, cell in zip(sboxes, cells):
        n = sb.n
        inc = cell_to_set(cell, n)
        outs: set[int] = set()
        for da in inc:
            outs.update(sb.output_diffs_for_input(da))
        if not outs:
            return "incompatible input difference with S-box DDT (no outputs)"
        out_sets.append(frozenset(outs))
    return tuple(out_sets)


def propagate_sbox_backward(
    sboxes: tuple[SBox, ...], cells: tuple[DiffCell, ...]
) -> tuple[FrozenSet[int], ...] | str:
    """Possible input differences for each S-box given constrained outputs."""
    if len(sboxes) != len(cells):
        return "S-box count does not match cell count"
    in_sets: list[FrozenSet[int]] = []
    for sb, cell in zip(sboxes, cells):
        n = sb.n
        out_allowed = cell_to_set(cell, n)
        ins: set[int] = set()
        for db in out_allowed:
            ins.update(sb.input_diffs_for_output(db))
        if not ins:
            return "incompatible output difference with inverse DDT (no inputs)"
        in_sets.append(frozenset(ins))
    return tuple(in_sets)


def propagate_p_forward(
    p: BinaryMatrix,
    sbox_bits: int,
    num_sboxes: int,
    after_sbox_sets: tuple[FrozenSet[int], ...],
) -> tuple[FrozenSet[int], ...] | str:
    """
    Apply the linear P-layer to Cartesian products of per-S-box output sets.
    Exponential in set sizes; intended for small educational instances.
    """
    if len(after_sbox_sets) != num_sboxes:
        return "wrong number of S-box output sets"

    def rec(i: int, acc: tuple[int, ...]) -> set[tuple[int, ...]]:
        if i == num_sboxes:
            y = _merge_block(acc, sbox_bits)
            z = p.apply(y)
            return {_split_block(z, num_sboxes, sbox_bits)}
        out: set[tuple[int, ...]] = set()
        for v in after_sbox_sets[i]:
            out |= rec(i + 1, acc + (v,))
        return out

    combined = rec(0, ())
    if not combined:
        return "empty set after P-layer propagation"
    per: list[set[int]] = [set() for _ in range(num_sboxes)]
    for tup in combined:
        for j, v in enumerate(tup):
            per[j].add(v)
    return tuple(frozenset(s) for s in per)


def propagate_round_forward_sets(
    spec: SPNRoundSpec, before_sbox: tuple[DiffCell, ...]
) -> RoundSetState | str:
    sb_out = propagate_sbox_forward(spec.sboxes, before_sbox)
    if isinstance(sb_out, str):
        return sb_out
    p_out = propagate_p_forward(spec.p_layer, spec.sbox_bits, spec.num_sboxes, sb_out)
    if isinstance(p_out, str):
        return p_out
    before_sets = tuple(cell_to_set(c, spec.sboxes[i].n) for i, c in enumerate(before_sbox))
    return RoundSetState(before_sbox=before_sets, after_sbox=sb_out, after_p=p_out)


def refine_round_with_output_fixes(
    spec: SPNRoundSpec, st: RoundSetState, fixes: dict[int, int]
) -> RoundSetState | str:
    """Intersect after-S-box sets with fixed output differences, then recompute P-layer."""
    if not fixes:
        return st
    lst = list(st.after_sbox)
    n_sb = spec.sboxes[0].n
    for i, db in fixes.items():
        if not 0 <= i < spec.num_sboxes:
            return "output fix index out of range"
        if not 0 <= db < n_sb:
            return "output fix value out of range"
        inter = lst[i] & frozenset({db})
        if not inter:
            return f"output difference fix at S-box {i} is incompatible with propagation"
        lst[i] = inter
    p_out = propagate_p_forward(spec.p_layer, spec.sbox_bits, spec.num_sboxes, tuple(lst))
    if isinstance(p_out, str):
        return p_out
    return RoundSetState(before_sbox=st.before_sbox, after_sbox=tuple(lst), after_p=p_out)


def apply_equality_constraints(
    sets: tuple[FrozenSet[int], ...], groups: tuple[tuple[int, ...], ...]
) -> tuple[FrozenSet[int], ...] | str:
    """
    Indices in each group must take the same simultaneous value; narrow each set to the
    intersection of all members in that group, then assign that intersection to each index.
    """
    cur = list(sets)
    for group in groups:
        if not group:
            continue
        common = cur[group[0]]
        for idx in group[1:]:
            common = diff_set_intersection(common, cur[idx])
        if not common:
            return "equality constraint impossible (empty intersection)"
        for idx in group:
            cur[idx] = common
    return tuple(cur)


def narrow_output_with_choice(
    outputs: tuple[FrozenSet[int], ...], index: int, chosen: int
) -> tuple[FrozenSet[int], ...] | str:
    """Pick one feasible output difference for S-box `index` after the DDT step."""
    if not 0 <= index < len(outputs):
        return "index out of range"
    if chosen not in outputs[index]:
        return "chosen output difference not in feasible set"
    lst = list(outputs)
    lst[index] = frozenset({chosen})
    return tuple(lst)


def sets_to_diff_cells(sets: tuple[FrozenSet[int], ...]) -> tuple[DiffCell, ...]:
    return tuple(DiffCell.subset(s) for s in sets)


def narrow_round1_cells(
    cells: tuple[DiffCell, ...],
    packed_dx: int | None,
    equality_groups: tuple[tuple[int, ...], ...],
    num_sboxes: int,
    sbox_bits: int,
) -> tuple[DiffCell, ...] | str:
    """Merge optional packed block difference, then apply equality groups on S-box inputs."""
    n = 1 << sbox_bits
    if len(cells) != num_sboxes:
        return "cell count does not match S-box count"
    if packed_dx is None:
        cur_sets = tuple(cell_to_set(c, n) for c in cells)
    else:
        mask = (1 << (num_sboxes * sbox_bits)) - 1
        if packed_dx < 0 or packed_dx > mask:
            return "packed input difference out of range"
        parts = _split_block(packed_dx, num_sboxes, sbox_bits)
        cur_sets_list: list[FrozenSet[int]] = []
        for i, p in enumerate(parts):
            s = frozenset({p}) & cell_to_set(cells[i], n)
            if not s:
                return f"S-box input position {i}: packed difference conflicts with constraints"
            cur_sets_list.append(s)
        cur_sets = tuple(cur_sets_list)
    narrowed = apply_equality_constraints(cur_sets, equality_groups)
    if isinstance(narrowed, str):
        return narrowed
    return sets_to_diff_cells(narrowed)


def propagate_multiple_rounds(
    spec: SPNRoundSpec, rounds: int, initial_before_sbox: tuple[DiffCell, ...]
) -> list[RoundSetState] | str:
    """Chain identical rounds; each round output after P becomes next round S-box input."""
    if rounds < 1:
        return "need at least one round"
    trail: list[RoundSetState] = []
    cur = initial_before_sbox
    for _ in range(rounds):
        st = propagate_round_forward_sets(spec, cur)
        if isinstance(st, str):
            return st
        trail.append(st)
        cur = sets_to_diff_cells(st.after_p)
    return trail


def cells_from_singleton_sets(
    spec: SPNRoundSpec, sets: tuple[FrozenSet[int], ...]
) -> tuple[DiffCell, ...] | str:
    """After manual narrowing, turn per-S-box singleton sets into CONCRETE input cells."""
    if len(sets) != spec.num_sboxes:
        return "wrong slice count"
    cells: list[DiffCell] = []
    for s in sets:
        if len(s) != 1:
            return "need singleton sets to fix concrete trail cells"
        (v,) = tuple(s)
        cells.append(DiffCell.concrete(v))
    return tuple(cells)
