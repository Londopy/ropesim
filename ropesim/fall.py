"""
ropesim.fall
============
Fall simulation: conditions model, result model, and the Fall simulator.

All computation is delegated to the Rust core (_rustcore).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field

from ropesim.units import Units
from ropesim.rope import RopeSpec  # must be a real import — Pydantic resolves it at class-build time

# ── Belay device ──────────────────────────────────────────────────────────────

class BelayDevice(str, Enum):
    ATC         = "atc"
    ATC_GUIDE   = "atc_guide"
    GRIGRI      = "grigri"
    GRIGRI_PLUS = "grigri_plus"
    TUBE        = "tube"
    REVERSO     = "reverso"
    MUNTER      = "munter"


#: Friction coefficient for each device (fraction of force absorbed by device).
#: Sources: Pavier (1998), Zanantoni et al. (2012), manufacturer test data.
BELAY_FRICTION_COEFFICIENTS: dict[BelayDevice, float] = {
    BelayDevice.ATC:         0.35,   # ~65% transmitted
    BelayDevice.ATC_GUIDE:   0.38,
    BelayDevice.GRIGRI:      0.55,   # ~45% transmitted
    BelayDevice.GRIGRI_PLUS: 0.60,
    BelayDevice.TUBE:        0.33,
    BelayDevice.REVERSO:     0.40,
    BelayDevice.MUNTER:      0.45,   # half-hitch creates high friction
}


# ── Energy budget (mirrors Rust struct) ──────────────────────────────────────

class EnergyBudget(BaseModel):
    """Energy partitioning for a fall event (all values in Joules)."""
    potential_energy_j: float
    kinetic_energy_j:   float
    rope_absorption_j:  float
    belay_device_j:     float
    residual_j:         float


# ── Conditions ────────────────────────────────────────────────────────────────

class FallConditions(BaseModel):
    """All inputs needed to simulate a single fall."""

    climber_mass_kg:    float       = Field(default=80.0, gt=0.0, le=300.0)
    fall_distance_m:    float       = Field(gt=0.0)
    rope_out_m:         float       = Field(gt=0.0)
    belay_device:       BelayDevice = BelayDevice.ATC
    rope:               RopeSpec
    is_wet:             bool        = False
    temperature_celsius: float      = Field(default=20.0, ge=-40.0, le=60.0)
    rope_over_edge:     bool        = False
    edge_friction_coeff: float      = Field(default=0.3, ge=0.0, le=1.0)
    timestep_ms:        float       = Field(default=1.0, gt=0.0, le=100.0)
    damping_ratio:      float       = Field(default=0.12, ge=0.0, le=1.0)

    model_config = {"arbitrary_types_allowed": True}


# Pydantic v2 needs model_rebuild() when annotations are evaluated lazily
# (i.e. when `from __future__ import annotations` is active) so it can
# resolve forward references like `RopeSpec` that appear as strings.
FallConditions.model_rebuild()


# ── Result ────────────────────────────────────────────────────────────────────

class FallResult(BaseModel):
    """All outputs from a simulated fall."""

    fall_factor:           float
    peak_force_kn:         float
    peak_force_lbf:        float
    peak_deceleration_g:   float
    force_curve:           list[float]   # kN at each timestep
    energy_budget:         EnergyBudget
    elongation_m:          float
    rope_survived:         bool
    warnings:              list[str]
    # geometry fields — populated by Fall.simulate() for GUI display
    fall_distance_m:       float = 0.0
    rope_out_m:            float = 0.0
    timestep_ms:           float = 1.0

    model_config = {"arbitrary_types_allowed": True}


# ── Fall simulator ────────────────────────────────────────────────────────────

class Fall:
    """
    Simulate a single fall event.

    Example::

        conditions = FallConditions(
            fall_distance_m=6.0,
            rope_out_m=20.0,
            rope=rope.spec,
        )
        result = Fall(conditions).simulate()
    """

    def __init__(self, conditions: FallConditions) -> None:
        self.conditions = conditions

    def fall_factor(self) -> float:
        """Compute the UIAA fall factor for these conditions."""
        c = self.conditions
        try:
            from ropesim._rustcore import compute_fall_factor
            return compute_fall_factor(c.fall_distance_m, c.rope_out_m)
        except ImportError:
            return min(c.fall_distance_m / c.rope_out_m, 2.0)

    def peak_force(self) -> float:
        """Quick estimate of peak impact force (kN)."""
        return self.simulate().peak_force_kn

    def force_curve_numpy(self) -> np.ndarray:
        """Return the force-time curve as a numpy array (kN)."""
        return np.array(self.simulate().force_curve)

    def simulate(self) -> FallResult:
        """
        Run the full fall simulation.

        Delegates all arithmetic to the Rust core.
        Raises ImportError if the Rust extension has not been compiled.
        """
        from ropesim._rustcore import (
            compute_fall_factor,
            compute_impact_force_uiaa,
            compute_force_curve,
            compute_elongation,
            compute_energy_budget,
            compute_stiffness_from_spec,
            apply_wet_modifier,
            apply_temperature_modifier,
        )

        c = self.conditions
        spec = c.rope
        warnings: list[str] = []

        # ── Fall factor ────────────────────────────────────────────────────
        ff = compute_fall_factor(c.fall_distance_m, c.rope_out_m)

        # ── Effective stiffness (temperature + wet adjusted) ───────────────
        base_stiffness = compute_stiffness_from_spec(
            spec.impact_force_kn,
            spec.dynamic_elongation_pct,
            80.0,
        )
        adj_stiffness = apply_temperature_modifier(base_stiffness, c.temperature_celsius)
        if c.temperature_celsius < 0.0:
            warnings.append(
                f"Rope is cold ({c.temperature_celsius}°C); stiffness increased. "
                "Impact force may be higher than rated."
            )

        # ── Belay friction ─────────────────────────────────────────────────
        friction = BELAY_FRICTION_COEFFICIENTS.get(c.belay_device, 0.35)

        # Edge friction reduces effective friction (rope drag absorbs some energy)
        if c.rope_over_edge:
            friction *= (1.0 - c.edge_friction_coeff * 0.3)
            warnings.append(
                "Rope running over an edge; edge friction modelled as "
                f"{c.edge_friction_coeff:.2f}."
            )

        # ── Peak impact force ──────────────────────────────────────────────
        raw_peak_kn = compute_impact_force_uiaa(
            c.climber_mass_kg,
            ff,
            adj_stiffness,
            friction,
        )
        if c.is_wet:
            raw_peak_kn = apply_wet_modifier(raw_peak_kn, True)
            warnings.append("Wet rope: impact force increased ~12% (EN 892 wet modifier).")

        # ── Force-time curve ───────────────────────────────────────────────
        force_curve: list[float] = compute_force_curve(
            c.climber_mass_kg,
            c.fall_distance_m,
            c.rope_out_m,
            adj_stiffness,
            c.damping_ratio,
            c.timestep_ms,
        )

        # ── Rope elongation ────────────────────────────────────────────────
        elongated_length = compute_elongation(
            spec.static_elongation_pct,
            spec.dynamic_elongation_pct,
            raw_peak_kn,
            c.rope_out_m,
        )
        elongation_m = elongated_length - c.rope_out_m

        # ── Energy budget ──────────────────────────────────────────────────
        rust_budget = compute_energy_budget(
            c.climber_mass_kg,
            c.fall_distance_m,
            raw_peak_kn,
            elongation_m,
            friction,
        )
        energy_budget = EnergyBudget(
            potential_energy_j = rust_budget.potential_energy_j,
            kinetic_energy_j   = rust_budget.kinetic_energy_j,
            rope_absorption_j  = rust_budget.rope_absorption_j,
            belay_device_j     = rust_budget.belay_device_j,
            residual_j         = rust_budget.residual_j,
        )

        # ── Derived values ─────────────────────────────────────────────────
        peak_lbf = Units.kn_to_lbf(raw_peak_kn)
        peak_g   = Units.kn_to_g(raw_peak_kn, c.climber_mass_kg)

        # ── Warnings ──────────────────────────────────────────────────────
        from ropesim import standards
        if ff >= 1.5:
            warnings.append(
                f"High fall factor ({ff:.2f}). Peak force near maximum: "
                f"{raw_peak_kn:.1f} kN."
            )
        max_f = standards.MAX_IMPACT_FORCE_KN.get(spec.rope_type.value, 12.0)
        if raw_peak_kn > max_f:
            warnings.append(
                f"Peak force {raw_peak_kn:.1f} kN exceeds EN 892 limit "
                f"of {max_f:.1f} kN for {spec.rope_type.value} rope!"
            )

        rope_survived = spec.number_of_falls > 0

        return FallResult(
            fall_factor         = round(ff, 4),
            peak_force_kn       = round(raw_peak_kn, 3),
            peak_force_lbf      = round(peak_lbf, 1),
            peak_deceleration_g = round(peak_g, 2),
            force_curve         = force_curve,
            energy_budget       = energy_budget,
            elongation_m        = round(elongation_m, 4),
            rope_survived       = rope_survived,
            warnings            = warnings,
            fall_distance_m     = round(c.fall_distance_m, 3),
            rope_out_m          = round(c.rope_out_m, 3),
            timestep_ms         = c.timestep_ms,
        )
