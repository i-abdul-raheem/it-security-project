from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from spn_dc.propagation import _merge_block, _split_block
from spn_dc.sbox import SBox
from spn_dc.spn import SPNRoundSpec


def ddt_probability(sb: SBox, da: int, db: int) -> float:
    return sb.ddt()[da][db] / sb.n


@dataclass(frozen=True)
class DifferentialPath:
    """One full differential trail (choice of output difference per S-box per round)."""

    path_id: int
    probability: float
    # (before_sbox_parts, after_sbox_parts, after_p_parts) per round
    trace: tuple[tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]], ...]


def generate_paths_exhaustive(
    spec: SPNRoundSpec,
    rounds: int,
    before_round1: tuple[int, ...],
    *,
    max_paths: int = 50_000,
) -> tuple[tuple[DifferentialPath, ...], bool]:
    """
    Enumerate trails from a fixed input difference tuple (one value per S-box before round 1).
    Returns (paths, truncated).
    """
    m = spec.num_sboxes
    bits = spec.sbox_bits
    if len(before_round1) != m:
        raise ValueError("tuple length must match number of S-boxes")
    for v in before_round1:
        if v < 0 or v >= (1 << bits):
            raise ValueError("difference component out of range")

    paths: list[DifferentialPath] = []
    truncated = False
    pid = 0

    def dfs(
        r: int,
        before_parts: tuple[int, ...],
        prob: float,
        trace: list[tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]],
    ) -> None:
        nonlocal truncated, pid
        if truncated:
            return
        if r == rounds:
            paths.append(DifferentialPath(pid, prob, tuple(trace)))
            pid += 1
            if len(paths) >= max_paths:
                truncated = True
            return
        opts: list[list[int]] = []
        for i, sb in enumerate(spec.sboxes):
            da = before_parts[i]
            ddt = sb.ddt()
            opts.append([db for db in range(sb.n) if ddt[da][db] > 0])
        for choice in itertools.product(*opts):
            merged = _merge_block(choice, bits)
            after_p = _split_block(spec.p_layer.apply(merged), m, bits)
            p_mul = math.prod(ddt_probability(spec.sboxes[i], before_parts[i], choice[i]) for i in range(m))
            trace.append((before_parts, choice, after_p))
            dfs(r + 1, after_p, prob * p_mul, trace)
            trace.pop()
            if truncated:
                return

    dfs(0, before_round1, 1.0, [])
    return tuple(paths), truncated


def generate_paths_from_packed(
    spec: SPNRoundSpec, rounds: int, packed_input_dx: int, *, max_paths: int = 50_000
) -> tuple[tuple[DifferentialPath, ...], bool]:
    m = spec.num_sboxes
    bits = spec.sbox_bits
    mask = (1 << (m * bits)) - 1
    if packed_input_dx < 0 or packed_input_dx > mask:
        raise ValueError("input difference out of range for block size")
    br = _split_block(packed_input_dx, m, bits)
    return generate_paths_exhaustive(spec, rounds, br, max_paths=max_paths)


def first_round_starts_from_sets(
    sets: tuple[frozenset[int], ...], *, max_starts: int = 2048
) -> tuple[tuple[int, ...], ...] | str:
    """Cartesian product of per-S-box input sets, capped."""
    opts = [sorted(s) for s in sets]
    n = 1
    for o in opts:
        n *= len(o)
        if n > max_starts:
            return f"too many starting combinations (>{max_starts}); narrow constraints"
    out: list[tuple[int, ...]] = []
    for tup in itertools.product(*opts):
        out.append(tuple(tup))
    return tuple(out)


def generate_paths_with_starts(
    spec: SPNRoundSpec,
    rounds: int,
    starts: tuple[tuple[int, ...], ...],
    *,
    max_paths: int = 50_000,
) -> tuple[tuple[DifferentialPath, ...], bool]:
    all_paths: list[DifferentialPath] = []
    truncated = False
    next_id = 0
    for start in starts:
        chunk, trunc = generate_paths_exhaustive(spec, rounds, start, max_paths=max_paths - len(all_paths))
        for p in chunk:
            all_paths.append(DifferentialPath(next_id, p.probability, p.trace))
            next_id += 1
        if trunc or len(all_paths) >= max_paths:
            truncated = True
            break
    return tuple(all_paths), truncated


def filter_paths_by_probability(
    paths: tuple[DifferentialPath, ...], *, min_probability: float, strict: bool = False
) -> tuple[DifferentialPath, ...]:
    if strict:
        return tuple(p for p in paths if p.probability > min_probability)
    return tuple(p for p in paths if p.probability >= min_probability)


def path_respects_equality_groups(
    before_round1: tuple[int, ...], groups: tuple[tuple[int, ...], ...]
) -> bool:
    for g in groups:
        if not g:
            continue
        v0 = before_round1[g[0]]
        if any(before_round1[i] != v0 for i in g[1:]):
            return False
    return True
