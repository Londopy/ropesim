"""
ropesim.standards
=================
EN 892:2012+A3:2023 and UIAA 101 constants and compliance validators.

Sources:
  EN 892:2012+A3:2023 — Dynamic mountaineering ropes — Safety requirements and test methods
  UIAA 101:2020       — Dynamic ropes
  EN 566:2017         — Mountaineering equipment — Slings
  EN 12275:2013       — Mountaineering equipment — Connectors
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ropesim.rope import RopeSpec

# ── EN 892 limits ─────────────────────────────────────────────────────────────

#: Maximum permitted impact force (kN) per rope type — EN 892 §5.2
MAX_IMPACT_FORCE_KN: dict[str, float] = {
    "single": 12.0,
    "half":   8.0,
    "twin":   12.0,
    "dry_single": 12.0,
    "dry_half":    8.0,
    "dry_twin":   12.0,
}

#: Minimum number of UIAA falls before failure — EN 892 §5.3
MIN_FALLS: dict[str, int] = {
    "single":     5,
    "half":       5,
    "twin":      12,
    "dry_single": 5,
    "dry_half":   5,
    "dry_twin":  12,
}

#: Maximum static elongation (%) — EN 892 §5.4
MAX_STATIC_ELONGATION_PCT: dict[str, float] = {
    "single":     10.0,
    "half":       10.0,
    "twin":       10.0,
    "dry_single": 10.0,
    "dry_half":   10.0,
    "dry_twin":   10.0,
}

#: Maximum dynamic elongation (%) — EN 892 §5.4
MAX_DYNAMIC_ELONGATION_PCT: dict[str, float] = {
    "single":     40.0,
    "half":       40.0,
    "twin":       40.0,
    "dry_single": 40.0,
    "dry_half":   40.0,
    "dry_twin":   40.0,
}

#: Minimum sheath slippage allowance (mm) — EN 892 §5.6
MAX_SHEATH_SLIPPAGE_MM: float = 40.0

#: Diameter ranges for EN 892 compliance (mm) [min, max]
DIAMETER_RANGES_MM: dict[str, tuple[float, float]] = {
    "single":     (8.5, 11.0),
    "half":       (7.5,  9.5),
    "twin":       (7.0,  9.0),
    "dry_single": (8.5, 11.0),
    "dry_half":   (7.5,  9.5),
    "dry_twin":   (7.0,  9.0),
}

# ── EN 566 sling limits ───────────────────────────────────────────────────────

#: Minimum MBS for slings (kN) — EN 566:2017
SLING_MIN_MBS_KN: dict[str, float] = {
    "nylon":    22.0,
    "dyneema":  22.0,
    "technora": 22.0,
}

# ── EN 12275 connector limits (kN) ───────────────────────────────────────────

CONNECTOR_MAJOR_AXIS_MBS_KN:   float = 20.0
CONNECTOR_MINOR_AXIS_MBS_KN:   float = 7.0
CONNECTOR_OPEN_GATE_MBS_KN:    float = 6.0

# ── Bolt/anchor MBS minimums ──────────────────────────────────────────────────

#: Minimum recommended bolt MBS (kN) for sport climbing
BOLT_MIN_RECOMMENDED_MBS_KN: float = 25.0


# ── Validators ────────────────────────────────────────────────────────────────

def validate_rope(spec: "RopeSpec") -> list[str]:
    """
    Check a RopeSpec against EN 892:2012+A3:2023 and UIAA 101.

    Returns a list of violation strings.  Empty list means compliant.
    """
    violations: list[str] = []
    rt = spec.rope_type.value  # e.g. "single", "half", "twin"

    # Impact force
    max_f = MAX_IMPACT_FORCE_KN.get(rt)
    if max_f is not None and spec.impact_force_kn > max_f:
        violations.append(
            f"Impact force {spec.impact_force_kn:.1f} kN exceeds EN 892 limit "
            f"of {max_f:.1f} kN for {rt} rope."
        )

    # Falls
    min_f = MIN_FALLS.get(rt)
    if min_f is not None and spec.number_of_falls < min_f:
        violations.append(
            f"Fall count {spec.number_of_falls} is below EN 892 minimum "
            f"of {min_f} for {rt} rope."
        )

    # Static elongation
    max_se = MAX_STATIC_ELONGATION_PCT.get(rt)
    if max_se is not None and spec.static_elongation_pct > max_se:
        violations.append(
            f"Static elongation {spec.static_elongation_pct:.1f}% exceeds "
            f"EN 892 maximum of {max_se:.1f}%."
        )

    # Dynamic elongation
    max_de = MAX_DYNAMIC_ELONGATION_PCT.get(rt)
    if max_de is not None and spec.dynamic_elongation_pct > max_de:
        violations.append(
            f"Dynamic elongation {spec.dynamic_elongation_pct:.1f}% exceeds "
            f"EN 892 maximum of {max_de:.1f}%."
        )

    # Diameter range
    drange = DIAMETER_RANGES_MM.get(rt)
    if drange is not None:
        dmin, dmax = drange
        if not (dmin <= spec.diameter_mm <= dmax):
            violations.append(
                f"Diameter {spec.diameter_mm:.1f} mm is outside EN 892 "
                f"range [{dmin:.1f}, {dmax:.1f}] mm for {rt} rope."
            )

    return violations


def reference() -> dict[str, dict]:
    """Return a structured reference of all supported standards."""
    return {
        "EN 892:2012+A3:2023": {
            "scope": "Dynamic mountaineering ropes",
            "key_limits": {
                "max_impact_force_single_kn": 12.0,
                "max_impact_force_half_kn":    8.0,
                "max_impact_force_twin_kn":   12.0,
                "min_falls_single":            5,
                "min_falls_twin":             12,
                "max_static_elongation_pct":  10.0,
                "max_dynamic_elongation_pct": 40.0,
                "max_sheath_slippage_mm":     40.0,
            },
            "citation": "EN 892:2012+A3:2023, CEN Technical Committee 136",
        },
        "UIAA 101": {
            "scope": "Dynamic ropes — UIAA test methodology",
            "key_limits": {
                "max_impact_force_single_kn": 12.0,
                "max_impact_force_half_kn":    8.0,
                "min_falls_single":            5,
                "min_falls_twin":             12,
            },
            "citation": "UIAA 101:2020, UIAA Safety Commission",
        },
        "EN 566:2017": {
            "scope": "Slings — MBS and width requirements",
            "key_limits": {
                "min_mbs_kn": 22.0,
            },
            "citation": "EN 566:2017, CEN Technical Committee 136",
        },
        "EN 12275:2013": {
            "scope": "Connectors (carabiners) — major/minor axis, open gate",
            "key_limits": {
                "major_axis_mbs_kn":  20.0,
                "minor_axis_mbs_kn":   7.0,
                "open_gate_mbs_kn":    6.0,
            },
            "citation": "EN 12275:2013, CEN Technical Committee 136",
        },
    }
