"""Entry point for `spn-dc-ui` console script: runs Streamlit app."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    app = Path(__file__).resolve().parent / "streamlit_app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app), *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
