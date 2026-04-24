"""
ropesim.anchor
==============
Anchor components (Bolt, Cam, Nut, Sling) and the AnchorSystem simulator.

Force resolution delegates to the Rust core.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Union

import numpy as np
from pydantic import BaseModel, Field

# ── Rock type ─────────────────────────────────────────────────────────────────

class RockType(str, Enum):
    GRANITE      = "granite"
    LIMESTONE    = "limestone"
    SANDSTONE    = "sandstone"
    BASALT       = "basalt"
    QUARTZITE    = "quartzite"
    CONGLOMERATE = "conglomerate"
    CHOSS        = "choss"
    ICE          = "ice"
    ALPINE_MIXED = "alpine_mixed"
    CUSTOM       = "custom"


#: Rock-type MBS modifiers: (glue-in modifier, expansion modifier)
#: Source: Pieper (2009) bolt MBS study; UIAA rock failure data.
ROCK_BOLT_MODIFIERS: dict[RockType, tuple[float, float]] = {
    RockType.GRANITE:      (1.00, 1.00),
    RockType.LIMESTONE:    (0.80, 0.75),
    RockType.SANDSTONE:    (0.60, 0.55),
    RockType.BASALT:       (0.90, 0.85),
    RockType.QUARTZITE:    (0.95, 0.92),
    RockType.CONGLOMERATE: (0.50, 0.45),
    RockType.CHOSS:        (0.30, 0.25),
    RockType.ICE:          (0.85, 0.70),
    RockType.ALPINE_MIXED: (0.75, 0.65),
    RockType.CUSTOM:       (1.00, 1.00),
}

#: Rock friction coefficients (rope-over-rock drag model)
#: Source: Meijer & de Vries (2008) tribology of rock surfaces.
ROCK_FRICTION_COEFFICIENTS: dict[RockType, float] = {
    RockType.GRANITE:   0.38,
    RockType.LIMESTONE: 0.30,
    RockType.SANDSTONE: 0.42,
    RockType.BASALT:    0.25,
    RockType.QUARTZITE: 0.35,
    RockType.CHOSS:     0.20,
    RockType.ICE:       0.10,
}

# ── Bolt ──────────────────────────────────────────────────────────────────────

class BoltType(str, Enum):
    GLUE_IN          = "glue_in"
    EXPANSION_WEDGE  = "expansion_wedge"
    EXPANSION_SLEEVE = "expansion_sleeve"
    BUTTONHEAD       = "buttonhead"   # legacy
    RAWL             = "rawl"         # legacy


class Bolt(BaseModel):
    """Fixed protection: bolt/hanger system."""

    bolt_type:       BoltType             = BoltType.GLUE_IN
    rated_mbs_kn:    float                = Field(default=25.0, gt=0.0)
    age_years:       float                = Field(default=0.0, ge=0.0)
    corrosion_level: float                = Field(default=0.0, ge=0.0, le=1.0)
    rock_type:       RockType             = RockType.GRANITE
    position:        tuple[float, float]  = (0.0, 0.0)

    def effective_mbs(self) -> float:
        """MBS after rock-type, age, and corrosion penalties."""
        glue_mod, exp_mod = ROCK_BOLT_MODIFIERS.get(self.rock_type, (1.0, 1.0))
        rock_mod = (
            glue_mod if self.bolt_type == BoltType.GLUE_IN else exp_mod
        )
        # Age degradation: ~1% per year, capped at 30%
        age_factor = max(1.0 - 0.01 * self.age_years, 0.70)
        # Corrosion penalty: up to 50% reduction at full corrosion
        corr_factor = 1.0 - 0.50 * self.corrosion_level
        # Legacy bolt penalty
        legacy_factor = 0.80 if self.bolt_type in (BoltType.BUTTONHEAD, BoltType.RAWL) else 1.0
        return self.rated_mbs_kn * rock_mod * age_factor * corr_factor * legacy_factor


# ── Cam ───────────────────────────────────────────────────────────────────────

class CamPlacement(str, Enum):
    PERFECT  = "perfect"
    GOOD     = "good"
    MARGINAL = "marginal"
    POOR     = "poor"


#: MBS multipliers by placement quality
PLACEMENT_MBS_FACTORS: dict[CamPlacement, float] = {
    CamPlacement.PERFECT:  1.00,
    CamPlacement.GOOD:     0.85,
    CamPlacement.MARGINAL: 0.55,
    CamPlacement.POOR:     0.30,
}


class Cam(BaseModel):
    """Spring-loaded camming device (SLCD)."""

    brand:          str                   = ""
    size:           str                   = ""
    rated_mbs_kn:   float                 = Field(default=14.0, gt=0.0)
    placement:      CamPlacement          = CamPlacement.GOOD
    rock_type:      RockType              = RockType.GRANITE
    position:       tuple[float, float]   = (0.0, 0.0)
    walking_risk:   float                 = Field(default=0.0, ge=0.0, le=1.0)

    def effective_mbs(self) -> float:
        """MBS after placement quality and rock-type modifiers."""
        p_factor = PLACEMENT_MBS_FACTORS.get(self.placement, 0.85)
        rock_mod, _ = ROCK_BOLT_MODIFIERS.get(self.rock_type, (1.0, 1.0))
        # Walking risk: a cam that might walk out has reduced effective MBS
        walk_penalty = 1.0 - 0.40 * self.walking_risk
        return self.rated_mbs_kn * p_factor * rock_mod * walk_penalty

    def placement_quality_score(self) -> float:
        """0.0–1.0 quality score for this placement."""
        return PLACEMENT_MBS_FACTORS.get(self.placement, 0.5)


# ── Nut ───────────────────────────────────────────────────────────────────────

class Nut(BaseModel):
    """Passive nut / wired stopper."""

    rated_mbs_kn: float                = Field(default=12.0, gt=0.0)
    placement:    CamPlacement         = CamPlacement.GOOD
    rock_type:    RockType             = RockType.GRANITE
    position:     tuple[float, float]  = (0.0, 0.0)

    def effective_mbs(self) -> float:
        p_factor  = PLACEMENT_MBS_FACTORS.get(self.placement, 0.85)
        rock_mod, _ = ROCK_BOLT_MODIFIERS.get(self.rock_type, (1.0, 1.0))
        return self.rated_mbs_kn * p_factor * rock_mod


# ── Sling ─────────────────────────────────────────────────────────────────────

class SlingMaterial(str, Enum):
    NYLON    = "nylon"
    DYNEEMA  = "dyneema"
    TECHNORA = "technora"


#: Elongation factor for each sling material (energy absorption proxy)
#: Source: UIAA Safety Commission; manufacturer data sheets.
SLING_ELONGATION_FACTORS: dict[SlingMaterial, float] = {
    SlingMaterial.NYLON:    0.08,  # ~8% elongation — absorbs some energy
    SlingMaterial.DYNEEMA:  0.02,  # ~2% — very stiff, shock-load risk
    SlingMaterial.TECHNORA: 0.04,
}

#: UV degradation penalty per 0.1 unit of uv_degradation
SLING_UV_PENALTY_PER_UNIT: float = 0.20  # up to 20% MBS loss


class Sling(BaseModel):
    """Textile sling connecting gear to the rope system."""

    material:        SlingMaterial = SlingMaterial.NYLON
    width_mm:        float         = Field(default=25.0, gt=0.0)
    rated_mbs_kn:    float         = Field(default=22.0, gt=0.0)
    length_m:        float         = Field(default=0.6, gt=0.0)
    uv_degradation:  float         = Field(default=0.0, ge=0.0, le=1.0)

    def effective_mbs(self) -> float:
        """MBS after UV degradation."""
        uv_penalty = 1.0 - SLING_UV_PENALTY_PER_UNIT * self.uv_degradation
        return self.rated_mbs_kn * max(uv_penalty, 0.30)

    def elongation_factor(self) -> float:
        """Elongation factor (fraction of length) for energy absorption."""
        return SLING_ELONGATION_FACTORS.get(self.material, 0.05)


# ── Anchor types ──────────────────────────────────────────────────────────────

class AnchorType(str, Enum):
    SLIDING_X    = "sliding_x"
    MAGIC_X      = "magic_x"
    QUAD         = "quad"
    CORDELETTE   = "cordelette"
    SHELF        = "shelf"
    DIRECT_2BOLT = "direct_2bolt"
    DIRECT_3BOLT = "direct_3bolt"
    SINGLE_POINT = "single_point"


# ── FailureResult (mirrors Rust struct) ──────────────────────────────────────

class FailureResult(BaseModel):
    failed_indices:        list[int]
    redistributed_forces:  list[float]
    cascade_occurred:      bool


# ── AnchorSystem ─────────────────────────────────────────────────────────────

GearComponent = Union[Bolt, Cam, Nut]


class AnchorSystem:
    """
    A complete anchor system: type + components + optional sling.

    All force computations delegate to the Rust core.
    """

    def __init__(
        self,
        anchor_type: AnchorType,
        components: list[GearComponent],
        sling: Optional[Sling] = None,
    ) -> None:
        if not components:
            raise ValueError("AnchorSystem requires at least one component.")
        self.anchor_type = anchor_type
        self.components = components
        self.sling = sling

    # ── Force distribution ────────────────────────────────────────────────

    def load_distribution(
        self,
        load_kn: float,
        load_angle_deg: float = 0.0,
    ) -> dict[str, float]:
        """
        Compute force (kN) on each component for the given load.

        Returns ``{component_index: force_kn}``.
        """
        from ropesim._rustcore import (
            sliding_x_distribution,
            quad_anchor_distribution,
            resolve_anchor_forces_2d,
            cordelette_distribution,
        )

        n = len(self.components)
        positions = [c.position for c in self.components]

        if self.anchor_type in (AnchorType.SLIDING_X, AnchorType.MAGIC_X) and n == 2:
            fa, fb = sliding_x_distribution(load_kn, load_angle_deg)
            return {"0": fa, "1": fb}

        if self.anchor_type == AnchorType.QUAD and n == 2:
            fa, fb = quad_anchor_distribution(load_kn, load_angle_deg, True)
            return {"0": fa, "1": fb}

        if self.anchor_type == AnchorType.CORDELETTE:
            forces = cordelette_distribution(positions, load_kn, load_angle_deg)
            return {str(i): f for i, f in enumerate(forces)}

        if self.anchor_type == AnchorType.SINGLE_POINT and n >= 1:
            return {"0": load_kn}

        # Generic 2-D vector resolution for all other types
        sling_lengths = [
            self.sling.length_m / max(n, 1) if self.sling else 1.0
            for _ in range(n)
        ]
        forces = resolve_anchor_forces_2d(positions, sling_lengths, load_kn, load_angle_deg)
        return {str(i): f for i, f in enumerate(forces)}

    def load_sweep(
        self,
        load_kn: float,
        angle_range: tuple[float, float] = (-60.0, 60.0),
        steps: int = 120,
    ) -> np.ndarray:
        """
        Sweep load angle from angle_range[0] to angle_range[1].

        Returns a (steps × n_components) numpy array.
        """
        from ropesim._rustcore import compute_anchor_load_sweep

        n = len(self.components)
        positions = [c.position for c in self.components]
        flat = compute_anchor_load_sweep(
            positions, load_kn, angle_range[0], angle_range[1], steps
        )
        return np.array(flat).reshape(steps, n)

    def simulate_failure(
        self,
        load_kn: float,
        load_angle_deg: float = 0.0,
    ) -> FailureResult:
        """Simulate progressive component failure."""
        from ropesim._rustcore import simulate_component_failure

        dist = self.load_distribution(load_kn, load_angle_deg)
        bolt_forces = [dist.get(str(i), 0.0) for i in range(len(self.components))]
        bolt_mbs    = [c.effective_mbs() for c in self.components]

        rust_result = simulate_component_failure(bolt_forces, bolt_mbs)
        return FailureResult(
            failed_indices       = list(rust_result.failed_indices),
            redistributed_forces = list(rust_result.redistributed_forces),
            cascade_occurred     = rust_result.cascade_occurred,
        )

    def safety_margins(self, load_kn: float) -> dict[str, float]:
        """
        Return the safety margin (% of MBS remaining) for each component.

        100% = unloaded; 0% = at MBS; negative = over MBS.
        """
        dist = self.load_distribution(load_kn)
        margins = {}
        for i, comp in enumerate(self.components):
            force = dist.get(str(i), 0.0)
            mbs   = comp.effective_mbs()
            margins[str(i)] = round(100.0 * (1.0 - force / mbs), 1) if mbs > 0 else 0.0
        return margins

    def is_redundant(self) -> bool:
        """True if the system has ≥ 2 independent load-bearing components."""
        return len(self.components) >= 2

    def weakest_component(self) -> GearComponent:
        """Return the component with the lowest effective MBS."""
        return min(self.components, key=lambda c: c.effective_mbs())

    def __repr__(self) -> str:
        return (
            f"AnchorSystem({self.anchor_type.value}, "
            f"{len(self.components)} components, "
            f"redundant={self.is_redundant()})"
        )
