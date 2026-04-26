"""Run the `spn-dc` CLI (`python -m spn_dc --help`)."""

import sys

from spn_dc.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
