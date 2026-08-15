#!/usr/bin/env python3
"""Entrada ejecutable para ``app.data_audit`` desde el árbol del servicio."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data_audit import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
