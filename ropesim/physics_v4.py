"""
physics_v4 — nonlinear rope model, capstan route friction, and two-body
belayer dynamics.

Thin, typed Python facade over the v4 Rust core functions:

* :func:`nonlinear_rope_from_spec` / :func:`nonlinear_impact_force` — cubic
  force–strain rope calibrated against BOTH the rated impact force and the
  dynamic elongation (two-point EN 892 calibration).
* :func:`route_friction` / :func:`route_transmission` — capstan-equation
  tension propagation through every carabiner on a pitch.
* :func:`two_body_catch` — coupled climber + belayer ODE; the soft catch
  emerges from the belayer being lifted rather than being asserted.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from ropesim import _rustcore as _rc

if TYPE_CHECKING:  # pragma: no cover
    from ropesim.rope import Rope, RopeSpec

__all__ = [
    "nonlinear_rope_from_spec",
    "nonlinear_impact_force",
    "nonlinear_force_curve",
    "capstan_ratio",
    "route_friction",
    "route_transmission",
    "two_body_catch",
]


def _spec_of(rope: "Rope | RopeSpec"):
    return rope.spec if hasattr(rope, "spec") else rope


def nonlinear_rope_from_spec(rope: "Rope | RopeSpec", test_mass_kg: float = 80.0):
    """Calibrate the cubic force–strain model from a rope's published spec.

    Uses both ``impact_force_kn`` and ``dynamic_elongation_pct``, pinning the
    model to the EN 892 test point exactly in force *and* elongation.
    Returns a ``NonlinearRope`` handle for the other v4 functions.
    """
    spec = _spec_of(rope)
    return _rc.calibrate_nonlinear_rope(
        spec.impact_force_kn, spec.dynamic_elongation_pct, test_mass_kg
    )


def nonlinear_impact_force(
    rope: "Rope | RopeSpec",
    mass_kg: float,
    fall_factor: float,
    belay_friction: float = 0.0,
    test_mass_kg: float = 80.0,
) -> float:
    """Peak impact force (kN) from the nonlinear model via energy balance."""
    nl = nonlinear_rope_from_spec(rope, test_mass_kg)
    return _rc.compute_impact_force_nonlinear(mass_kg, fall_factor, nl, belay_friction)


def nonlinear_force_curve(
    rope: "Rope | RopeSpec",
    mass_kg: float,
    fall_distance_m: float,
    rope_out_m: float,
    damping_ratio: float = 0.15,
    timestep_ms: float = 1.0,
    test_mass_kg: float = 80.0,
) -> list[float]:
    """Force–time curve (kN per step) using the nonlinear spring in RK4."""
    nl = nonlinear_rope_from_spec(rope, test_mass_kg)
    return _rc.compute_force_curve_nonlinear(
        mass_kg, fall_distance_m, rope_out_m, nl, damping_ratio, timestep_ms
    )


def capstan_ratio(mu: float, theta_deg: float) -> float:
    """Tension ratio e^(mu*theta) across one bend (theta in degrees)."""
    import math

    return _rc.capstan_tension_ratio(mu, math.radians(theta_deg))


def route_friction(
    climber_tension_kn: float,
    bend_angles_deg: Sequence[float],
    mu: float = 0.2,
):
    """Propagate a climber-side tension down the pitch (top piece first).

    Returns ``RouteFriction`` with per-segment tensions, per-piece resultant
    loads, belay-device tension, and the overall drag factor.
    """
    return _rc.compute_route_friction(climber_tension_kn, list(bend_angles_deg), mu)


def route_transmission(bend_angles_deg: Sequence[float], mu: float = 0.2) -> float:
    """Fraction of climber-side force reaching the belay device (0–1).

    Physically derived replacement for the legacy scalar ``belay_friction``.
    """
    return _rc.route_transmission_fraction(list(bend_angles_deg), mu)


def two_body_catch(
    climber_kg: float,
    belayer_kg: float,
    fall_distance_m: float,
    climber_side_rope_m: float,
    rope: "Rope | RopeSpec | float",
    damping_ratio: float = 0.15,
    mu_top: float = 0.25,
    theta_top_deg: float = 170.0,
    timestep_ms: float = 0.1,
):
    """Simulate a catch with a liftable belayer (coupled two-mass ODE).

    ``rope`` may be a Rope/RopeSpec (stiffness back-calculated from spec) or a
    length-normalised stiffness in kN.  Returns ``TwoBodyResult`` including
    the force reduction relative to a rigid anchor — the soft-catch effect,
    derived rather than asserted.
    """
    if isinstance(rope, (int, float)):
        stiffness = float(rope)
    else:
        spec = _spec_of(rope)
        stiffness = _rc.compute_stiffness_from_spec(
            spec.impact_force_kn, spec.dynamic_elongation_pct, 80.0
        )
    return _rc.simulate_two_body_fall(
        climber_kg,
        belayer_kg,
        fall_distance_m,
        climber_side_rope_m,
        stiffness,
        damping_ratio,
        mu_top,
        theta_top_deg,
        timestep_ms,
    )
