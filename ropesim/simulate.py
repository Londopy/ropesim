"""
ropesim.simulate
================
Scenario-based fall simulation: model a full route with multiple pieces of
protection, simulate lead falls from any height, zipper failures, and sweep
peak force across all climber positions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

import numpy as np

from ropesim.rope import Rope, RopeSpec
from ropesim.fall import Fall, FallConditions, FallResult, BelayDevice
from ropesim.anchor import AnchorSystem, FailureResult


# ── Protection point ──────────────────────────────────────────────────────────

@dataclass
class ProtectionPoint:
    """A single piece of gear placed at a known height above the belay."""

    height_m:  float          # metres above the belay anchor
    anchor:    AnchorSystem
    label:     str = ""       # optional human-readable label (e.g. "cam #3")

    def __post_init__(self) -> None:
        if self.height_m < 0.0:
            raise ValueError("height_m must be >= 0")


# ── Sweep result ──────────────────────────────────────────────────────────────

@dataclass
class SweepResult:
    """Results from sweep_fall_positions()."""

    climber_heights_m: List[float]
    fall_distances_m:  List[float]
    fall_factors:      List[float]
    peak_forces_kn:    List[float]
    worst_index:       int            # index with highest peak force

    @property
    def worst_height_m(self) -> float:
        return self.climber_heights_m[self.worst_index]

    @property
    def worst_peak_kn(self) -> float:
        return self.peak_forces_kn[self.worst_index]

    def as_numpy(self) -> np.ndarray:
        """Return (N×4) array: [height, fall_dist, fall_factor, peak_kn]."""
        return np.column_stack([
            self.climber_heights_m,
            self.fall_distances_m,
            self.fall_factors,
            self.peak_forces_kn,
        ])


# ── Zipper result ─────────────────────────────────────────────────────────────

@dataclass
class ZipperResult:
    """Result of a zipper simulation."""

    initial_fall_result:     FallResult
    failure_sequence:        List[int]          # protection indices that failed (in order)
    per_step_results:        List[FailureResult]
    total_pieces_failed:     int
    ground_fall_reached:     bool               # True if all gear pulled


# ── Scenario ──────────────────────────────────────────────────────────────────

class Scenario:
    """
    Model a full climbing scenario: belay anchor, rope, protection points,
    and a climber at a given height.

    Workflow::

        rope = Rope.from_db("Beal Opera 8.5 Dry")
        scenario = Scenario(rope, climber_mass_kg=70.0)
        scenario.add_protection(8.0,  anchor_1, label="first bolt")
        scenario.add_protection(14.0, anchor_2, label="second bolt")

        result = scenario.simulate_fall(climber_height_m=16.0)
        sweep  = scenario.sweep_fall_positions()
        zipper = scenario.simulate_zipper(climber_height_m=16.0)
    """

    def __init__(
        self,
        rope:              Rope,
        climber_mass_kg:   float      = 80.0,
        belay_device:      BelayDevice = BelayDevice.ATC,
        belay_height_m:    float      = 0.0,
        is_wet:            bool       = False,
        temperature_c:     float      = 20.0,
        damping_ratio:     float      = 0.12,
        timestep_ms:       float      = 1.0,
    ) -> None:
        self.rope            = rope
        self.climber_mass_kg = climber_mass_kg
        self.belay_device    = belay_device
        self.belay_height_m  = belay_height_m
        self.is_wet          = is_wet
        self.temperature_c   = temperature_c
        self.damping_ratio   = damping_ratio
        self.timestep_ms     = timestep_ms

        self._protection: List[ProtectionPoint] = []  # kept sorted by height

    # ── Protection management ─────────────────────────────────────────────────

    def add_protection(
        self,
        height_m: float,
        anchor: AnchorSystem,
        label: str = "",
    ) -> None:
        """Add a piece of protection at `height_m` above the belay."""
        pt = ProtectionPoint(height_m=height_m, anchor=anchor, label=label)
        self._protection.append(pt)
        self._protection.sort(key=lambda p: p.height_m)

    def remove_protection(self, index: int) -> None:
        """Remove protection point by index (after sort order)."""
        self._protection.pop(index)

    def clear_protection(self) -> None:
        """Remove all protection points."""
        self._protection.clear()

    @property
    def protection(self) -> List[ProtectionPoint]:
        """Sorted list of protection points (lowest first)."""
        return list(self._protection)

    # ── Fall geometry helpers ─────────────────────────────────────────────────

    def _last_pro_below(self, climber_height_m: float) -> Optional[ProtectionPoint]:
        """Return the highest protection piece at or below climber."""
        candidates = [p for p in self._protection if p.height_m <= climber_height_m]
        return candidates[-1] if candidates else None

    def _fall_geometry(
        self,
        climber_height_m: float,
    ) -> tuple[float, float, float]:
        """
        Compute (fall_distance_m, rope_out_m, fall_factor) for a lead fall.

        Lead fall model:
        * If there is protection below the climber, the last piece is the
          highest run-out point.
        * fall_distance = 2 × (climber_height − last_pro_height)
          (factor of 2: climber falls same distance above pro on way down)
        * rope_out = total rope paid out = climber_height − belay_height
        * Fall factor = fall_distance / rope_out
        """
        last_pro = self._last_pro_below(climber_height_m)
        rope_out = max(climber_height_m - self.belay_height_m, 0.1)

        if last_pro is None:
            # No protection — fall directly to belay (factor ≈ 2)
            fall_distance = rope_out * 2.0
        else:
            fall_distance = max(2.0 * (climber_height_m - last_pro.height_m), 0.1)

        fall_factor = min(fall_distance / rope_out, 2.0)
        return fall_distance, rope_out, fall_factor

    # ── Primary simulation ────────────────────────────────────────────────────

    def simulate_fall(
        self,
        climber_height_m: float,
        rope_over_edge:    bool  = False,
        edge_friction:     float = 0.3,
    ) -> FallResult:
        """
        Simulate a lead fall from `climber_height_m`.

        Uses the current protection to determine fall geometry, then delegates
        to ``Fall.simulate()``.
        """
        fall_dist, rope_out, _ = self._fall_geometry(climber_height_m)

        conditions = FallConditions(
            climber_mass_kg     = self.climber_mass_kg,
            fall_distance_m     = fall_dist,
            rope_out_m          = rope_out,
            belay_device        = self.belay_device,
            rope                = self.rope.spec,
            is_wet              = self.is_wet,
            temperature_celsius = self.temperature_c,
            rope_over_edge      = rope_over_edge,
            edge_friction_coeff = edge_friction,
            timestep_ms         = self.timestep_ms,
            damping_ratio       = self.damping_ratio,
        )
        return Fall(conditions).simulate()

    # ── Zipper simulation ─────────────────────────────────────────────────────

    def simulate_zipper(self, climber_height_m: float) -> ZipperResult:
        """
        Simulate a zipper failure starting from the highest protection piece.

        A zipper occurs when the force on the highest piece exceeds its MBS,
        causing it to fail and loading the next piece below with the full
        fall force plus the redistributed load, potentially cascading.

        Algorithm:
        1. Simulate fall, compute load on highest protection piece.
        2. If that load exceeds the piece's effective MBS, remove it.
        3. Recompute fall geometry and repeat from the next piece.
        4. Stop when a piece holds or no gear remains.
        """
        working_protection = list(self._protection)
        failure_sequence: List[int] = []
        per_step_results: List[FailureResult] = []
        ground_fall_reached = False

        # Simulate the initial fall
        initial_result = self.simulate_fall(climber_height_m)

        # Try zipper progression
        while working_protection:
            # Find highest protection below climber
            candidates = [p for p in working_protection if p.height_m <= climber_height_m]
            if not candidates:
                ground_fall_reached = True
                break

            highest = candidates[-1]
            highest_idx = working_protection.index(highest)

            # Compute load on this piece
            rope_out = max(climber_height_m - self.belay_height_m, 0.1)
            fall_dist = max(2.0 * (climber_height_m - highest.height_m), 0.1)
            load_kn = initial_result.peak_force_kn  # simplified: full load on last pro

            # Check if the anchor system holds
            failure_result = highest.anchor.simulate_failure(load_kn)
            per_step_results.append(failure_result)

            if failure_result.failed_indices:
                # Piece failed — record it and remove from working set
                failure_sequence.append(highest_idx)
                working_protection.pop(highest_idx)
            else:
                break  # Piece holds — zipper stops here

        if not working_protection:
            ground_fall_reached = True

        return ZipperResult(
            initial_fall_result = initial_result,
            failure_sequence    = failure_sequence,
            per_step_results    = per_step_results,
            total_pieces_failed = len(failure_sequence),
            ground_fall_reached = ground_fall_reached,
        )

    # ── Position sweep ────────────────────────────────────────────────────────

    def sweep_fall_positions(
        self,
        height_range: tuple[float, float] = (2.0, 30.0),
        steps: int = 50,
    ) -> SweepResult:
        """
        Sweep the climber from ``height_range[0]`` to ``height_range[1]`` and
        compute peak force at each position.

        Uses the Rust batch sweep for speed (delegates to
        ``_rustcore.sweep_climber_height``).

        Returns a ``SweepResult`` with per-position fall geometry and forces.
        """
        from ropesim._rustcore import (
            sweep_climber_height,
            compute_stiffness_from_spec,
            apply_temperature_modifier,
        )
        from ropesim.fall import BELAY_FRICTION_COEFFICIENTS

        spec = self.rope.spec
        base_k = compute_stiffness_from_spec(
            spec.impact_force_kn,
            spec.dynamic_elongation_pct,
            80.0,
        )
        adj_k = apply_temperature_modifier(base_k, self.temperature_c)
        friction = BELAY_FRICTION_COEFFICIENTS.get(self.belay_device, 0.35)

        # Last protection below height_range[1]
        last_pro = self._last_pro_below(height_range[1])
        last_pro_h = last_pro.height_m if last_pro else self.belay_height_m

        flat = sweep_climber_height(
            self.climber_mass_kg,
            self.belay_height_m,
            last_pro_h,
            height_range[0],
            height_range[1],
            steps,
            adj_k,
            friction,
        )

        arr = np.array(flat).reshape(steps, 3)
        heights    = arr[:, 0].tolist()
        fall_dists = arr[:, 1].tolist()
        peak_forces = arr[:, 2].tolist()

        # Compute fall factors
        fall_factors = [
            min(fd / max(h - self.belay_height_m, 0.1), 2.0)
            for h, fd in zip(heights, fall_dists)
        ]

        worst_idx = int(np.argmax(peak_forces))

        return SweepResult(
            climber_heights_m = heights,
            fall_distances_m  = fall_dists,
            fall_factors      = fall_factors,
            peak_forces_kn    = peak_forces,
            worst_index       = worst_idx,
        )

    # ── Utility ───────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        """Return a dictionary summarising the scenario setup."""
        return {
            "rope":              repr(self.rope),
            "climber_mass_kg":   self.climber_mass_kg,
            "belay_device":      self.belay_device.value,
            "belay_height_m":    self.belay_height_m,
            "protection_count":  len(self._protection),
            "protection_heights": [p.height_m for p in self._protection],
            "is_wet":            self.is_wet,
            "temperature_c":     self.temperature_c,
        }

    def __repr__(self) -> str:
        return (
            f"Scenario(rope={self.rope.spec.name!r}, "
            f"mass={self.climber_mass_kg}kg, "
            f"{len(self._protection)} protection points)"
        )
