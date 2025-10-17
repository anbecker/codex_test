"""Test helper to ensure the project package is importable when run as a script."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

for path in (PROJECT_ROOT, SRC_PATH):
    str_path = str(path)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)
