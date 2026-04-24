"""
ropesim.rope
============
Rope data model, database access, and physics helpers.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field, field_validator, model_validator

from ropesim import standards
from ropesim.units import Units

# ── Enums ─────────────────────────────────────────────────────────────────────

class RopeType(str, Enum):
    SINGLE     = "single"
    HALF       = "half"
    TWIN       = "twin"
    DRY_SINGLE = "dry_single"
    DRY_HALF   = "dry_half"
    DRY_TWIN   = "dry_twin"


class RopeStandard(str, Enum):
    EN_892            = "EN 892:2012+A3:2023"
    UIAA_101          = "UIAA 101"
    BOTH              = "EN 892 + UIAA 101"


# ── Pydantic spec model ───────────────────────────────────────────────────────

class RopeSpec(BaseModel):
    """Full EN 892 / UIAA 101 rope specification."""

    name:                     str
    manufacturer:             str              = ""
    rope_type:                RopeType
    standard:                 RopeStandard     = RopeStandard.BOTH
    diameter_mm:              float            = Field(gt=5.0, lt=15.0)
    weight_gpm:               float            = Field(gt=0.0, description="g/m")
    sheath_percentage:        float            = Field(ge=0.0, le=60.0)
    sheath_material:          str              = "nylon"
    core_material:            str              = "nylon"
    dry_treated:              bool             = False
    impact_force_kn:          float            = Field(gt=0.0, le=20.0)
    number_of_falls:          int              = Field(ge=1)
    static_elongation_pct:    float            = Field(ge=0.0, le=30.0)
    dynamic_elongation_pct:   float            = Field(ge=0.0, le=60.0)
    knotability:              Optional[float]  = None   # EN sheath-slippage proxy (mm)
    length_m:                 float            = Field(default=60.0, gt=0.0)
    uiaa_falls:               Optional[int]    = None

    @field_validator("dry_treated")
    @classmethod
    def dry_matches_type(cls, v: bool, info) -> bool:
        rt = info.data.get("rope_type")
        if rt and rt.value.startswith("dry_") and not v:
            return True  # allow; just a label mismatch, not an error
        return v

    @model_validator(mode="after")
    def check_elongation_order(self) -> "RopeSpec":
        if self.dynamic_elongation_pct < self.static_elongation_pct:
            raise ValueError(
                "dynamic_elongation_pct must be >= static_elongation_pct"
            )
        return self

    def model_dump_json_str(self) -> str:
        return self.model_dump_json(indent=2)


# ── Rope class ────────────────────────────────────────────────────────────────

class Rope:
    """
    High-level rope object.  Wraps a `RopeSpec` and provides physics helpers
    that call into the Rust core.
    """

    def __init__(self, spec: RopeSpec) -> None:
        self.spec = spec

    # ── Database factory methods ──────────────────────────────────────────────

    @classmethod
    def from_db(cls, name: str) -> "Rope":
        """Load a rope by name from the bundled ropes.json database."""
        spec = RopeDatabase().get(name)
        if spec is None:
            raise KeyError(
                f"Rope '{name}' not found in database. "
                f"Use Rope.search() to browse available ropes."
            )
        return cls(spec)

    @classmethod
    def search(
        cls,
        rope_type: Optional[RopeType] = None,
        diameter_range: Optional[tuple[float, float]] = None,
        dry_only: bool = False,
        min_falls: Optional[int] = None,
    ) -> list["Rope"]:
        """Search the rope database with optional filters."""
        db = RopeDatabase()
        results = []
        for spec in db.load():
            if rope_type and spec.rope_type != rope_type:
                continue
            if diameter_range:
                lo, hi = diameter_range
                if not (lo <= spec.diameter_mm <= hi):
                    continue
            if dry_only and not spec.dry_treated:
                continue
            if min_falls and spec.number_of_falls < min_falls:
                continue
            results.append(cls(spec))
        return results

    # ── Physics helpers ───────────────────────────────────────────────────────

    def effective_stiffness(self) -> float:
        """
        Length-normalised rope stiffness k_eff (kN) back-calculated from
        EN 892 test data.
        """
        try:
            from ropesim._rustcore import compute_stiffness_from_spec
            return compute_stiffness_from_spec(
                self.spec.impact_force_kn,
                self.spec.dynamic_elongation_pct,
                80.0,  # EN 892 standard test mass
            )
        except ImportError:
            # Fallback: rough estimate
            return self.spec.impact_force_kn * 4.0

    def diameter_under_load(self, force_kn: float) -> float:
        """Estimated rope diameter (mm) at the given axial load (kN)."""
        try:
            from ropesim._rustcore import compute_diameter_under_load
            return compute_diameter_under_load(
                self.spec.diameter_mm,
                self.spec.sheath_percentage,
                force_kn,
            )
        except ImportError:
            return self.spec.diameter_mm

    def elongation_at_force(self, force_kn: float) -> float:
        """Elongated rope length (m) at the given force (kN)."""
        try:
            from ropesim._rustcore import compute_elongation
            return compute_elongation(
                self.spec.static_elongation_pct,
                self.spec.dynamic_elongation_pct,
                force_kn,
                self.spec.length_m,
            )
        except ImportError:
            # Linear interpolation fallback
            pct = self.spec.static_elongation_pct
            return self.spec.length_m * (1.0 + pct / 100.0)

    def degrade(self, falls_taken: int) -> "Rope":
        """
        Return a new Rope with spec degraded to reflect accumulated falls.

        Stiffness and impact force increase as fibres compress and fatigue;
        elongation decreases.  Model based on published nylon fatigue data.
        """
        if falls_taken <= 0:
            return Rope(self.spec.model_copy())

        ratio = min(falls_taken / max(self.spec.number_of_falls, 1), 1.0)
        # Stiffness increases ~20% at end of rated life (fibres compress)
        stiffness_factor = 1.0 + 0.20 * ratio
        # Impact force increases with stiffness
        new_impact = self.spec.impact_force_kn * stiffness_factor
        # Elongation decreases (rope becomes less stretchy)
        new_static = self.spec.static_elongation_pct * (1.0 - 0.15 * ratio)
        new_dynamic = self.spec.dynamic_elongation_pct * (1.0 - 0.20 * ratio)

        new_spec = self.spec.model_copy(update={
            "name":                   f"{self.spec.name} (degraded, {falls_taken} falls)",
            "impact_force_kn":        round(new_impact, 2),
            "static_elongation_pct":  round(new_static, 2),
            "dynamic_elongation_pct": round(max(new_dynamic, new_static + 0.1), 2),
            "number_of_falls":        max(self.spec.number_of_falls - falls_taken, 0),
        })
        return Rope(new_spec)

    def retirement_warning(self, falls_taken: int) -> Optional[str]:
        """Return a warning string if the rope should be retired, else None."""
        rated = self.spec.number_of_falls
        if falls_taken >= rated:
            return (
                f"Rope has exceeded rated fall count ({falls_taken}/{rated}). "
                f"Retire immediately."
            )
        if falls_taken >= rated * 0.8:
            pct = int(100 * falls_taken / rated)
            return (
                f"Rope is at {pct}% of rated falls ({falls_taken}/{rated}). "
                f"Inspect carefully before further use."
            )
        return None

    def validate_standard_compliance(self) -> list[str]:
        """Check EN 892 / UIAA 101 compliance.  Returns list of violations."""
        return standards.validate_rope(self.spec)

    def to_json(self) -> str:
        return self.spec.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Rope":
        return cls(RopeSpec.model_validate_json(json_str))

    def __repr__(self) -> str:
        s = self.spec
        return (
            f"Rope({s.name!r}, {s.rope_type.value}, "
            f"{s.diameter_mm}mm, {s.impact_force_kn}kN, {s.number_of_falls} falls)"
        )


# ── Database ──────────────────────────────────────────────────────────────────

_DB_PATH = Path(__file__).parent / "database" / "ropes.json"


class RopeDatabase:
    """CRUD access layer for the bundled ropes.json database."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or _DB_PATH

    def _read_raw(self) -> list[dict]:
        if not self._path.exists():
            return []
        try:
            with open(self._path, encoding="utf-8") as fh:
                content = fh.read().strip()
            if not content:
                return []
            data = json.loads(content)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _write_raw(self, data: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

    def load(self) -> list[RopeSpec]:
        """Load all rope specs from disk."""
        raw = self._read_raw()
        specs = []
        for item in raw:
            try:
                specs.append(RopeSpec.model_validate(item))
            except Exception:
                pass  # skip malformed entries
        return specs

    def save(self, specs: list[RopeSpec]) -> None:
        """Overwrite the database with the given specs."""
        self._write_raw([s.model_dump() for s in specs])

    def get(self, name: str) -> Optional[RopeSpec]:
        """Look up a rope by exact name (case-insensitive)."""
        name_lower = name.lower()
        for spec in self.load():
            if spec.name.lower() == name_lower:
                return spec
        return None

    def add(self, spec: RopeSpec) -> None:
        """Add a rope to the database (raises if name already exists)."""
        raw = self._read_raw()
        names = [r.get("name", "").lower() for r in raw]
        if spec.name.lower() in names:
            raise ValueError(f"Rope '{spec.name}' already exists in database.")
        raw.append(spec.model_dump())
        self._write_raw(raw)

    def remove(self, name: str) -> None:
        """Remove a rope by name.  Raises KeyError if not found."""
        raw = self._read_raw()
        new_raw = [r for r in raw if r.get("name", "").lower() != name.lower()]
        if len(new_raw) == len(raw):
            raise KeyError(f"Rope '{name}' not found in database.")
        self._write_raw(new_raw)

    def update(self, name: str, spec: RopeSpec) -> None:
        """Replace an existing entry by name."""
        raw = self._read_raw()
        updated = False
        for i, r in enumerate(raw):
            if r.get("name", "").lower() == name.lower():
                raw[i] = spec.model_dump()
                updated = True
                break
        if not updated:
            raise KeyError(f"Rope '{name}' not found in database.")
        self._write_raw(raw)

    def search(
        self,
        query: str = "",
        rope_type: Optional[RopeType] = None,
    ) -> list[RopeSpec]:
        """Simple text + type search."""
        q = query.lower()
        results = []
        for spec in self.load():
            if q and q not in spec.name.lower() and q not in spec.manufacturer.lower():
                continue
            if rope_type and spec.rope_type != rope_type:
                continue
            results.append(spec)
        return results

    def __len__(self) -> int:
        return len(self._read_raw())
