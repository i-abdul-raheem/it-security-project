from __future__ import annotations

from dataclasses import dataclass

from spn_dc.linear import BinaryMatrix
from spn_dc.sbox import SBox


@dataclass(frozen=True)
class SPNRoundSpec:
    """One round: parallel S-boxes (same width each) then a linear bijection on the full state."""

    sboxes: tuple[SBox, ...]
    p_layer: BinaryMatrix

    def __post_init__(self) -> None:
        if not self.sboxes:
            raise ValueError("need at least one S-box")
        bits = self.sboxes[0].bits
        for sb in self.sboxes:
            if sb.bits != bits:
                raise ValueError("all S-boxes in a round must have the same width")
        if self.p_layer.dim != bits * len(self.sboxes):
            raise ValueError("P-layer dimension must match total S-box output bits")

    @property
    def sbox_bits(self) -> int:
        return self.sboxes[0].bits

    @property
    def num_sboxes(self) -> int:
        return len(self.sboxes)

    @property
    def block_bits(self) -> int:
        return self.sbox_bits * self.num_sboxes


@dataclass(frozen=True)
class SPNParams:
    """Full cipher shape: `rounds` identical round specs (for analysis we ignore key schedule)."""

    rounds: int
    round_spec: SPNRoundSpec

    def __post_init__(self) -> None:
        if self.rounds < 1:
            raise ValueError("need at least one round")

    @property
    def block_bits(self) -> int:
        return self.round_spec.block_bits
