"""
ropesim.database.db
===================
Convenience re-exports.  The primary database classes live in rope.py and
anchor.py to avoid circular imports; this module re-exports them and adds
an anchors loader.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ropesim.rope import RopeDatabase, RopeSpec, RopeType  # noqa: F401

_ANCHORS_PATH = Path(__file__).parent / "anchors.json"


def load_anchors() -> list[dict[str, Any]]:
    """Load raw anchor records from anchors.json."""
    if not _ANCHORS_PATH.exists():
        return []
    with open(_ANCHORS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


__all__ = ["RopeDatabase", "RopeSpec", "RopeType", "load_anchors"]
