from __future__ import annotations

import argparse
import sys

from spn_dc import (
    BinaryMatrix,
    DiffCell,
    SPNParams,
    SPNRoundSpec,
    propagate_round_forward_sets,
)
from spn_dc.parsing import parse_int_list, parse_mapping, parse_matrix_rows
from spn_dc.session import (
    SPNSession,
    get_session,
    load_default_from_disk,
    random_bijective_matrix,
    random_sbox,
)


def _format_ddt(table: tuple[tuple[int, ...], ...]) -> str:
    n = len(table)
    w = max(3, len(str(n - 1)))
    hdr = " " * (w + 2) + "".join(f"{db:{w}d} " for db in range(n))
    lines = [hdr.rstrip()]
    for da, row in enumerate(table):
        lines.append(f"{da:{w}d} |" + "".join(f"{v:{w}d} " for v in row))
    return "\n".join(lines)


def _format_round_state(st, label: str) -> str:
    lines = [label]
    lines.append("  before S-box: " + str([sorted(s) for s in st.before_sbox]))
    lines.append("  after  S-box: " + str([sorted(s) for s in st.after_sbox]))
    lines.append("  after  P:    " + str([sorted(s) for s in st.after_p]))
    return "\n".join(lines)


def _format_path(p) -> str:
    lines = [f"path id={p.path_id} probability={p.probability:.6g}"]
    for ri, step in enumerate(p.trace):
        b, a, z = step
        lines.append(f"  round {ri + 1}: before={list(b)} after_sbox={list(a)} after_P={list(z)}")
    return "\n".join(lines)


def _cmd_demo() -> None:
    from spn_dc.sbox import SBox

    t = (
        12,
        5,
        6,
        11,
        9,
        0,
        10,
        13,
        3,
        14,
        15,
        8,
        4,
        7,
        1,
        2,
    )
    sb = SBox(t)
    n = 8
    rows = [1 << (i ^ 4) for i in range(n)]
    p = BinaryMatrix(n, tuple(rows))
    spec = SPNRoundSpec((sb, sb), p)
    cipher = SPNParams(5, spec)
    before = (DiffCell.concrete(0xF), DiffCell.nonzero())
    res = propagate_round_forward_sets(spec, before)
    print("SPN demo:", cipher.block_bits, "bit state,", cipher.rounds, "rounds")
    if isinstance(res, str):
        print("propagation error:", res)
        return
    print("before S-box sets:", [sorted(s) for s in res.before_sbox])
    print("after  S-box sets:", [sorted(s) for s in res.after_sbox])
    print("after  P-layer sets:", [sorted(s) for s in res.after_p])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="spn-dc",
        description="SPN differential analysis CLI",
        epilog="Session is stored in .spn_dc_state.json (override with SPN_DC_STATE). "
        "Set SPN_DC_NO_PERSIST=1 to disable disk storage.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("create_spn", help="Initialize cipher shape")
    s.add_argument("--rounds", type=int, required=True)
    s.add_argument("--sboxes", type=int, required=True)
    s.add_argument("--sbox-bits", type=int, default=4, dest="sbox_bits")

    s = sub.add_parser("set_sbox", help="Set one S-box permutation table")
    s.add_argument("--index", type=int, required=True)
    s.add_argument("--mapping", type=str, required=True, help="comma-separated ints, e.g. 0,1,...,15")

    s = sub.add_parser("set_permutation", help="Set P-layer as GF(2) invertible matrix rows")
    s.add_argument("--matrix", type=str, required=True, help="comma-separated row bitmasks")

    s = sub.add_parser("compute_ddt", help="Print DDT for an S-box")
    s.add_argument("--sbox", type=int, required=True, dest="sbox_id")

    s = sub.add_parser("propagate_difference", help="Propagate packed input difference through all rounds")
    s.add_argument("--input", type=lambda x: int(x, 0), required=True)

    s = sub.add_parser("analyze_round", help="Show one round's set state (1-based round index)")
    s.add_argument("--round", type=int, required=True)
    s.add_argument("--input_diff", type=lambda x: int(x, 0), required=True)

    s = sub.add_parser("fix_input_difference", help="Fix round-1 input difference at one S-box")
    s.add_argument("--position", type=int, required=True)
    s.add_argument("--value", type=lambda x: int(x, 0), required=True)

    s = sub.add_parser("fix_output_difference", help="Fix output difference after S-box layer in round 1")
    s.add_argument("--position", type=int, required=True)
    s.add_argument("--value", type=lambda x: int(x, 0), required=True)

    s = sub.add_parser("set_constraint", help="Relational constraint on inputs")
    s.add_argument("--type", type=str, required=True, choices=["equal"], dest="ctype")
    s.add_argument("--positions", type=str, required=True, help="comma-separated indices, e.g. 0,1")

    s = sub.add_parser("check_constraints", help="Verify current configuration is consistent")

    s = sub.add_parser("set_abstract_difference", help="Require nonzero difference at an S-box input")
    s.add_argument("--position", type=int, required=True)

    s = sub.add_parser("link_differences", help="Equal input differences at listed positions")
    s.add_argument("--positions", type=str, required=True)

    s = sub.add_parser("generate_paths", help="Enumerate differential trails from input difference")
    s.add_argument("--input_diff", type=lambda x: int(x, 0), required=True)
    s.add_argument("--max-paths", type=int, default=50_000, dest="max_paths")

    s = sub.add_parser("filter_paths", help="Filter last generated paths by trail probability")
    s.add_argument(
        "--probability",
        type=float,
        required=True,
        help="keep paths with probability strictly greater than this value",
    )

    s = sub.add_parser("show_path", help="Display one trail by id")
    s.add_argument("--id", type=int, required=True, dest="path_id")

    s = sub.add_parser("random_sbox", help="Print a random S-box permutation")
    s.add_argument("--bits", type=int, default=None, help="defaults to session sbox width")
    s.add_argument("--apply-index", type=int, default=None, dest="apply_index")

    s = sub.add_parser("random_permutation", help="Set P to a random invertible binary matrix")

    s = sub.add_parser("reset", help="Clear session")

    sub.add_parser("demo", help="Run built-in Present-style demo (stateless)")

    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    load_default_from_disk()
    parser = build_parser()
    args = parser.parse_args(argv)
    sess: SPNSession = get_session()

    try:
        if args.command == "demo":
            _cmd_demo()
            return 0
        if args.command == "reset":
            sess.reset()
            print("session reset")
            return 0
        if args.command == "create_spn":
            sess.create_spn(args.rounds, args.sboxes, args.sbox_bits)
            print(f"SPN: {args.rounds} rounds, {args.sboxes} x {args.sbox_bits}-bit S-boxes")
            return 0
        if args.command == "set_sbox":
            sess.set_sbox(args.index, parse_mapping(args.mapping))
            print(f"S-box {args.index} updated")
            return 0
        if args.command == "set_permutation":
            sess.set_permutation(parse_matrix_rows(args.matrix))
            print("P-layer updated")
            return 0
        if args.command == "compute_ddt":
            t = sess.compute_ddt(args.sbox_id)
            print(_format_ddt(t))
            return 0
        if args.command == "propagate_difference":
            trail, err = sess.propagate_difference(args.input)
            if err:
                print("error:", err)
                return 1
            for i, st in enumerate(trail):
                print(_format_round_state(st, f"Round {i + 1}"))
            return 0
        if args.command == "analyze_round":
            st = sess.analyze_round(args.round, args.input_diff)
            if isinstance(st, str):
                print("error:", st)
                return 1
            print(_format_round_state(st, f"Round {args.round}"))
            return 0
        if args.command == "fix_input_difference":
            sess.fix_input_difference(args.position, args.value)
            print(f"fixed input at {args.position} := {args.value}")
            return 0
        if args.command == "fix_output_difference":
            sess.fix_output_difference(args.position, args.value)
            print(f"fixed round-1 output at {args.position} := {args.value}")
            return 0
        if args.command == "set_constraint":
            pos = parse_int_list(args.positions)
            sess.set_constraint(args.ctype, pos)
            print("constraint added")
            return 0
        if args.command == "check_constraints":
            trail, err = sess.check_constraints()
            if err:
                print("constraints impossible:", err)
                return 1
            print("constraints OK; propagated trail:")
            for i, st in enumerate(trail):
                print(_format_round_state(st, f"Round {i + 1}"))
            return 0
        if args.command == "set_abstract_difference":
            sess.set_abstract_difference(args.position)
            print(f"position {args.position} set to abstract (nonzero unknown)")
            return 0
        if args.command == "link_differences":
            pos = parse_int_list(args.positions)
            sess.link_differences(pos)
            print("equality link added")
            return 0
        if args.command == "generate_paths":
            msg, err = sess.generate_paths(args.input_diff, max_paths=args.max_paths)
            if err:
                print("error:", err)
                return 1
            print(msg)
            return 0
        if args.command == "filter_paths":
            sess.filter_paths(args.probability, strict=True)
            n = len(sess._paths_filtered or ())
            print(f"filtered to {n} path(s)")
            return 0
        if args.command == "show_path":
            p = sess.show_path(args.path_id)
            if p is None:
                print("path not found")
                return 1
            print(_format_path(p))
            return 0
        if args.command == "random_sbox":
            if args.apply_index is not None:
                sess._require_cipher()
                sb = random_sbox(sess._sbox_bits)
                sess.set_sbox(args.apply_index, sb.table)
                print("applied S-box", args.apply_index, ":", ",".join(str(x) for x in sb.table))
            else:
                bits = args.bits if args.bits is not None else 4
                sb = random_sbox(bits)
                print(",".join(str(x) for x in sb.table))
            return 0
        if args.command == "random_permutation":
            sess._require_cipher()
            dim = sess._num_sboxes * sess._sbox_bits
            m = random_bijective_matrix(dim)
            sess.set_permutation(m.rows)
            print("P rows:", ",".join(str(r) for r in m.rows))
            return 0
    except Exception as e:
        print("error:", e)
        return 1

    print("unknown command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
