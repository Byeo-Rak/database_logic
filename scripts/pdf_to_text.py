#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from pdf_to_text_app.pipeline import main  # pyright: ignore[reportMissingImports]


if __name__ == "__main__":
    raise SystemExit(main())
