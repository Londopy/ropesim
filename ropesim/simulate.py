"""
ropesim.simulate
================
Scenario-based fall simulation: model a full route with multiple pieces of
protection, simulate lead falls from any height, zipper failures, and sweep
peak force across all climber positions.

v2 additions:
  - PhysicsMode enum (ANALYTICAL, RAPIER_3D)
  - ScenarioType enum (LEAD_FALL, TOP_ROPE, RAPPEL, HAUL, LOWER)
  - RockFaceGeometry class
  - Scenario.simulate_fall accepts mode parameter
  - Scenario.build_rapier_world() for direct Rapier access
  - async API: simulate_fall_async, sweep_fall_positions_async
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List

import numpy as np

from ropesim.rope import Rope, RopeSpec
from ropesim.fall import Fall, FallConditions, FallResult, BelayDevice
from ropesim.anchor import AnchorSystem, FailureResult


# ── v2 enums ─────────────────────────────────────────────────────────────────

class PhysicsMode(str, Enum):
    """Physics backend to use for simulation."""
    ANALYTICAL = "analytical"   # fast UIAA/RK4 model (v1 behaviour)
    RAPIER_3D  = "rapier_3d"    # full 3-D Rapier rigid-body simulation


class ScenarioType(str, Enum):
    """High-level scenario classification."""
    LEAD_FALL = "lead_fall"   # standard lead fall (default)
    TOP_ROPE  = "top_rope"    # top-rope catch, low fall factor, slack model
    RAPPEL    = "rappel"      # anchor load during rappel
    HAUL      = "haul"        # mechanical advantage haul system
    LOWER     = "lower"       # lowering off anchor


# ── Rock face geometry ────────────────────────────────────────────────────────

class RockFaceGeometry:
    """
    Describe the rock face geometry for Rapier 3-D simulations.

    Pre-built presets::

        face = RockFaceGeometry.vertical_slab()
        face = RockFaceGeometry.overhang(angle_deg=30)
        face = RockFaceGeometry.from_obj("cliff.obj")

    The geometry is passed to ``RopeSimWorld.add_rock_face()`` when building
    a Rapier world via ``Scenario.build_rapier_world()``.
    """

    # Preset names
    VERTICAL_SLAB = "vertical_slab"
    OVERHANG_30   = "overhang_30"
    OVERHANG_45   = "overhang_45"
    ROOF          = "roof"
    CRACK_SYSTEM  = "crack_system"
    CORNER        = "corner"

    def __init__(
        self,
        vertices: List[List[float]],   # list of [x, y, z] triples
        friction: float = 0.5,
        preset_name: str = "",
    ) -> None:
        self.vertices    = vertices
        self.friction    = friction
        self.preset_name = preset_name

    # -- Presets ---------------------------------------------------------------

    @classmethod
    def vertical_slab(cls, width_m: float = 10.0, height_m: float = 40.0,
                      friction: float = 0.5) -> "RockFaceGeometry":
        """Flat vertical wall."""
        v = [
            [-width_m / 2, 0.0,       0.0],
            [ width_m / 2, 0.0,       0.0],
            [ width_m / 2, height_m,  0.0],
            [-width_m / 2, height_m,  0.0],
        ]
        return cls(vertices=v, friction=friction, preset_name=cls.VERTICAL_SLAB)

    @classmethod
    def overhang(cls, angle_deg: float = 30.0, width_m: float = 10.0,
                 height_m: float = 40.0, friction: float = 0.4) -> "RockFaceGeometry":
        """Overhanging wall tilted at ``angle_deg`` past vertical."""
        import math
        lean = height_m * math.tan(math.radians(angle_deg))
        v = [
            [-width_m / 2,  0.0,      0.0],
            [ width_m / 2,  0.0,      0.0],
            [ width_m / 2,  height_m, lean],
            [-width_m / 2,  height_m, lean],
        ]
        return cls(vertices=v, friction=friction,
                   preset_name=f"overhang_{int(angle_deg)}")

    @classmethod
    def from_obj(cls, filepath: str, friction: float = 0.5) -> "RockFaceGeometry":
        """Load geometry from a Wavefront .obj file (vertices only)."""
        vertices: List[List[float]] = []
        with open(filepath) as fh:
            for line in fh:
                parts = line.split()
                if parts and parts[0] == "v":
                    vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
        return cls(vertices=vertices, friction=friction, preset_name=filepath)

    def as_flat_array(self) -> List[List[float]]:
        """Return vertices as a list of [x, y, z] for Rust consumption."""
        return self.vertices

    def __repr__(self) -> str:
        return (
            f"RockFaceGeometry(preset={self.preset_name!r}, "
            f"vertices={len(self.vertices)}, friction={self.friction})"
        )


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
        """Return (N x 4) array: [height, fall_dist, fall_factor, peak_kn]."""
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


# ── Simulation result wrapper (v2) ────────────────────────────────────────────

@dataclass
class SimulationResult:
    """
    Unified result object returned by ``Scenario.simulate_fall`` in v2.

    In ANALYTICAL mode, ``frame_data`` is None.
    In RAPIER_3D mode, ``frame_data`` holds the full 3-D simulation output.
    """
    fall_result:  FallResult
    mode:         PhysicsMode
    scenario_type: ScenarioType = ScenarioType.LEAD_FALL
    frame_data:   Optional[object] = None   # SimFrameData when mode=RAPIER_3D

    @property
    def peak_force_kn(self) -> float:
        return self.fall_result.peak_force_kn

    def __repr__(self) -> str:
        fd = "yes" if self.frame_data is not None else "no"
        return (
            f"SimulationResult(mode={self.mode.value}, "
            f"peak={self.peak_force_kn:.2f}kN, 3D_data={fd})"
        )


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

    v2 RAPIER_3D mode::

        result = scenario.simulate_fall(16.0, mode=PhysicsMode.RAPIER_3D)
        replay = SimulationReplay(result.frame_data)
    """

    def __init__(
        self,
        rope:              Rope,
        climber_mass_kg:   float       = 80.0,
        belay_device:      BelayDevice  = BelayDevice.ATC,
        belay_height_m:    float       = 0.0,
        is_wet:            bool        = False,
        temperature_c:     float       = 20.0,
        damping_ratio:     float       = 0.12,
        timestep_ms:       float       = 1.0,
        rock_face:         Optional[RockFaceGeometry] = None,
    ) -> None:
        self.rope            = rope
        self.climber_mass_kg = climber_mass_kg
        self.belay_device    = belay_device
        self.belay_height_m  = belay_height_m
        self.is_wet          = is_wet
        self.temperature_c   = temperature_c
        self.damping_ratio   = damping_ratio
        self.timestep_ms     = timestep_ms
        self.rock_face       = rock_face

        self._protection: List[ProtectionPoint] = []  # kept sorted by height

    # ── Protection management ─────────────────────────────────────────────────

    def add_protection(
        self,
        height_m: float,
        anchor: AnchorSystem,
        label: str = "",
    ) -> None:
        """Add a piece of protection at ``height_m`` above the belay."""
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
        * fall_distance = 2 x (climber_height - last_pro_height)
          (factor of 2: climber falls same distance above pro on way down)
        * rope_out = total rope paid out = climber_height - belay_height
        * Fall factor = fall_distance / rope_out
        """
        last_pro = self._last_pro_below(climber_height_m)
        rope_out = max(climber_height_m - self.belay_height_m, 0.1)

        if last_pro is None:
            # No protection -- fall directly to belay (factor approx 2)
            fall_distance = rope_out * 2.0
        else:
            fall_distance = max(2.0 * (climber_height_m - last_pro.height_m), 0.1)

        fall_factor = min(fall_distance / rope_out, 2.0)
        return fall_distance, rope_out, fall_factor

    # ── Primary simulation ────────────────────────────────────────────────────

    def simulate_fall(
        self,
        climber_height_m: float,
        mode:              PhysicsMode = PhysicsMode.ANALYTICAL,
        dt_seconds:        float = 1 / 240,
        rope_over_edge:    bool  = False,
        edge_friction:     float = 0.3,
    ) -> FallResult:
        """
        Simulate a lead fall from ``climber_height_m``.

        ``mode=PhysicsMode.ANALYTICAL`` (default): fast UIAA/RK4 model.
        ``mode=PhysicsMode.RAPIER_3D``: full 3-D Rapier simulation.
        Returns a plain ``FallResult`` in ANALYTICAL mode.  In RAPIER_3D
        mode the result still has all FallResult fields but is backed by
        full frame data available via ``build_rapier_world().step_n()``.
        """
        if mode == PhysicsMode.RAPIER_3D:
            return self._simulate_fall_rapier(climber_height_m, dt_seconds)

        fall_dist, rope_out, _ = self._fall_geometry(climber_height_m)
        conditions = FallConditions(
            climber_mass_kg      = self.climber_mass_kg,
            fall_distance_m      = fall_dist,
            rope_out_m           = rope_out,
            belay_device         = self.belay_device,
            rope                 = self.rope.spec,
            is_wet               = self.is_wet,
            temperature_celsius  = self.temperature_c,
            rope_over_edge       = rope_over_edge,
            edge_friction_coeff  = edge_friction,
            timestep_ms          = self.timestep_ms,
            damping_ratio        = self.damping_ratio,
        )
        return Fall(conditions).simulate()

    def _simulate_fall_rapier(
        self,
        climber_height_m: float,
        dt_seconds: float,
    ) -> FallResult:
        """Run a Rapier 3-D simulation and return results as a FallResult."""
        from ropesim.fall import BELAY_FRICTION_COEFFICIENTS
        world = self.build_rapier_world()
        # Number of steps: simulate until 3 seconds of fall time
        n_steps = int(3.0 / dt_seconds)
        frame_data = world.step_n(n_steps, dt_seconds)
        peak_kn = frame_data.peak_anchor_force()

        # Build a minimal FallResult from the Rapier output
        fall_dist, rope_out, fall_factor = self._fall_geometry(climber_height_m)
        from ropesim._rustcore import compute_energy_budget
        friction = BELAY_FRICTION_COEFFICIENTS.get(self.belay_device, 0.35)
        budget = compute_energy_budget(
            self.climber_mass_kg, fall_dist, peak_kn,
            self.rope.spec.dynamic_elongation_pct / 100.0 * rope_out,
            friction,
        )
        from ropesim.fall import FallResult, EnergyBudget
        from ropesim.units import Units
        eb = EnergyBudget(
            potential_energy_j = budget.potential_energy_j,
            kinetic_energy_j   = budget.kinetic_energy_j,
            rope_absorption_j  = budget.rope_absorption_j,
            belay_device_j     = budget.belay_device_j,
            residual_j         = budget.residual_j,
        )
        peak_g = frame_data.peak_deceleration_g()
        return FallResult(
            peak_force_kn       = round(peak_kn, 3),
            peak_force_lbf      = round(Units.kn_to_lbf(peak_kn), 1),
            fall_factor         = round(fall_factor, 4),
            peak_deceleration_g = round(peak_g, 2),
            force_curve         = frame_data.force_curve_numpy(),
            energy_budget       = eb,
            elongation_m        = round(
                self.rope.spec.dynamic_elongation_pct / 100.0 * rope_out, 4
            ),
            rope_survived       = self.rope.spec.number_of_falls > 0,
            warnings            = ["Simulated with Rapier 3D physics engine."],
            fall_distance_m     = round(fall_dist, 3),
            rope_out_m          = round(rope_out, 3),
            timestep_ms         = dt_seconds * 1000.0,
        )

    def build_rapier_world(self) -> object:
        """
        Construct and return a ``PyRopeSimWorld`` for this scenario.

        Advanced users can step the world manually, query any body,
        and extract full 3-D state at each timestep.

        Example::

            world = scenario.build_rapier_world()
            frame_data = world.step_n(720, 1/240)
            print(frame_data.peak_anchor_force())
        """
        from ropesim._rustcore import PyRopeSimWorld
        from ropesim.fall import BELAY_FRICTION_COEFFICIENTS

        fall_dist, rope_out, _ = self._fall_geometry(
            max((p.height_m for p in self._protection), default=10.0) + 2.0
        )

        world = PyRopeSimWorld(gravity=9.81)

        # Build the rope: start at anchor (top), end at climber position
        rope_start = [0.0, rope_out, 0.0]
        rope_end   = [0.0, 0.0, 0.0]
        spec = self.rope.spec
        rope_handles = world.add_rope(
            rope_start,
            rope_end,
            rope_out,
            getattr(spec, "weight_gpm", 65.0) / 1000.0,  # g/m -> kg/m
            0.08,   # link_length_m
            40.0,   # stiffness kN
            0.12,   # damping ratio
        )

        # Climber attached to bottom rope link
        if rope_handles:
            world.add_climber(rope_handles[-1], self.climber_mass_kg)

        # Rock face geometry if provided
        if self.rock_face is not None:
            world.add_rock_face(self.rock_face.as_flat_array(), self.rock_face.friction)

        return world

    # ── Async API ─────────────────────────────────────────────────────────────

    async def simulate_fall_async(
        self,
        climber_height_m: float,
        mode:             PhysicsMode = PhysicsMode.ANALYTICAL,
        dt_seconds:       float = 1 / 240,
    ) -> FallResult:
        """
        Non-blocking fall simulation using asyncio.

        Runs the simulation in a thread-pool executor so it does not block
        the event loop.  Useful in notebooks, web backends, and async scripts.

        Example::

            result = await scenario.simulate_fall_async(16.0)
        """
        return await asyncio.to_thread(
            self.simulate_fall,
            climber_height_m,
            mode,
            dt_seconds,
        )

    async def sweep_fall_positions_async(
        self,
        height_range: tuple[float, float] = (2.0, 30.0),
        steps: int = 50,
    ) -> SweepResult:
        """
        Non-blocking sweep of climber positions using asyncio.

        Delegates to the Rust parallel batch sweep and returns without
        blocking the event loop.

        Example::

            results = await scenario.sweep_fall_positions_async(
                height_range=(5, 25), steps=50
            )
        """
        return await asyncio.to_thread(self.sweep_fall_positions, height_range, steps)

    # ── Zipper simulation ─────────────────────────────────────────────────────

    def simulate_zipper(self, climber_height_m: float) -> ZipperResult:
        """
        Simulate a zipper failure starting from the highest protection piece.

        A zipper occurs when the force on the highest piece exceeds its MBS,
        causing it to fail and loading the next piece below with the full
        fall force plus the redistributed load, potentially cascading.
        """
        working_protection = list(self._protection)
        failure_sequence: List[int] = []
        per_step_results: List[FailureResult] = []
        ground_fall_reached = False

        initial_result = self.simulate_fall(climber_height_m)

        while working_protection:
            candidates = [p for p in working_protection if p.height_m <= climber_height_m]
            if not candidates:
                ground_fall_reached = True
                break

            highest = candidates[-1]
            highest_idx = working_protection.index(highest)
            load_kn = initial_result.peak_force_kn
            failure_result = highest.anchor.simulate_failure(load_kn)
            per_step_results.append(failure_result)

            if failure_result.failed_indices:
                failure_sequence.append(highest_idx)
                working_protection.pop(highest_idx)
            else:
                break

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
        heights     = arr[:, 0].tolist()
        fall_dists  = arr[:, 1].tolist()
        peak_forces = arr[:, 2].tolist()

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
            "rope":               repr(self.rope),
           