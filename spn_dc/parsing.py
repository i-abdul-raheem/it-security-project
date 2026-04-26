from __future__ import annotations


def parse_int_list(s: str) -> tuple[int, ...]:
    """Parse comma-separated integers (supports 0x hex)."""
    parts = [p.strip() for p in s.replace(";", ",").split(",") if p.strip()]
    if not parts:
        raise ValueError("expected at least one integer")
    return tuple(int(p, 0) for p in parts)


def parse_mapping(s: str) -> tuple[int, ...]:
    return parse_int_list(s)


def parse_matrix_rows(s: str) -> tuple[int, ...]:
    """Comma-separated row bitmasks for BinaryMatrix (square, dim = number of rows)."""
    return parse_int_list(s)
