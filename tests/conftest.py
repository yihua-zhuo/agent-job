"""Root pytest configuration.

Ensures that `src/` is on sys.path so top-level package imports (e.g.
`from services.x import Y`) resolve for all tests, regardless of which
subdirectory they live in.
"""
from __future__ import annotations

import sys
from pathlib import Path

_src_root = Path(__file__).resolve().parents[1] / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))
