"""
ropesim.physics_v3 -- v3 physics: twin/half ropes, knots, sheath abrasion,
fall probability, and the dynamic belayer model.

Every function prefers the compiled Rust core (``ropesim._rustcore``) and
falls back to a pure-Python implementation of the same model when the
extension is not compiled, so the public API works everywhere (including
Colab and source checkouts without a Rust toolchain).

Formulas are kept in lockstep with the Rust modules:
    _rustcore/src/twin_rope.rs, knots.rs, abrasion.rs, risk.rs, belay.rs
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "KnotType",
    "ClimbingStyle",
    "SheathRating",
    "SheathCondition",
    "CumulativeRisk",
    "DailyExposureReport",
    "twin_rope_forces",
    "half_rope_forces",
    "knot_strength_factor",
    "cord_anchor_strength",
    "abrasion_increment",
    "accumulate_sheath_wear",
    "fall_probability",
    "cumulative_risk",
    "daily_exposure",
    "dynamic_belay_reduction",
    "RETIREMENT_THRESHOLD",
]

_G = 9.81
RETIREMENT_THRESHOLD = 0.85


class KnotType(str, Enum):
    """Knots modelled by the strength-reduction table."""

    FIGURE_EIGHT_RETRACE = "figure_eight_retrace"
    FIGURE_EIGHT_ON_BIGHT = "figure_eight_on_bight"
    BOWLINE = "bowline"
    CLOVE_HITCH = "clove_hitch"
    MUNTER_HITCH = "munter_hitch"
    DOUBLE_FISHERMANS = "double_fishermans"
    OVERHAND_ON_BIGHT = "overhand_on_bight"
    ALPINE_BUTTERFLY = "alpine_butterfly"


class ClimbingStyle(str, Enum):
    SPORT = "sport"
    TRAD = "trad"
    BOULDER = "boulder"


class SheathRating(str, Enum):
    NEW = "NEW"
    GOOD = "GOOD"
    WORN = "WORN"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class SheathCondition:
    """Cumulative sheath abrasion state."""

    abrasion_score: float = 0.0
    estimated_falls_remaining: int = 2**32 - 1
    visual_rating: SheathRating = SheathRating.NEW

    @property
    def needs_retirement(self) -> bool:
        return (
            self.abrasion_score >= RETIREMENT_THRESHOLD
            or self.visual_rating is SheathRating.CRITICAL
        )


@dataclass(frozen=True)
class CumulativeRisk:
    expected_falls: float
    expected_total_force_kn: float
    rope_life_consumed_pct: float
    retirement_climbs_remaining: int


@dataclass(frozen=True)
class DailyExposureReport:
    total_expected_falls: float
    total_expected_force_kn: float
    rope_life_consumed_pct: float
    critical_pitch_index: int  # -1 if none
    retirement_projected: bool


# ── internal helpers ─────────────────────────────────────────────────────────

def _uiaa_peak_force(mass_kg: float, fall_factor: float, stiffness_kn: float) -> float:
    mg = mass_kg * _G / 1000.0
    ff = min(max(fall_factor, 0.0), 2.0)
    k = max(stiffness_kn, 0.0)
    return mg + math.sqrt(mg * mg + 2.0 * mg * ff * k)


def _knot_name(knot: "KnotType | str") -> str:
    return knot.value if isinstance(knot, KnotType) else str(knot)


# ── twin / half ropes ────────────────────────────────────────────────────────

def twin_rope_forces(
    stiffness_a_kn: float,
    stiffness_b_kn: float,
    mass_kg: float,
    fall_factor: float,
    inter_rope_friction: float = 0.2,
) -> tuple[float, float]:
    """Forces (kN) on each strand of a twin-rope pair through a shared piece.

    The strands act as parallel springs sharing load by stiffness;
    inter-strand friction dissipates energy (up to ~12 % of peak) and
    partially equalises the pair.
    """
    try:
        from ropesim._rustcore import compute_twin_rope_forces

        return compute_twin_rope_forces(
            stiffness_a_kn, stiffness_b_kn, mass_kg, fall_factor, inter_rope_friction
        )
    except ImportError:
        pass

    ka = max(stiffness_a_kn, 0.0)
    kb = max(stiffness_b_kn, 0.0)
    mu = min(max(inter_rope_friction, 0.0), 1.0)
    k_total = max(ka + kb, 1e-9)

    f_total = _uiaa_peak_force(mass_kg, fall_factor, k_total)
    dissipation = 0.12 * (1.0 - math.exp(-3.0 * mu))
    f_total *= 1.0 - dissipation

    share_a = ka / k_total
    transfer = 0.5 * (1.0 - math.exp(-2.0 * mu))
    eq_share_a = share_a + (0.5 - share_a) * transfer
    return f_total * eq_share_a, f_total * (1.0 - eq_share_a)


def half_rope_forces(
    stiffness_a_kn: float,
    stiffness_b_kn: float,
    mass_kg: float,
    fall_factor: float,
    active_rope: int = 0,
) -> tuple[float, float]:
    """Forces (kN) on a half-rope pair clipped alternately.

    Only the ``active_rope`` strand (0 = A, 1 = B) arrests the fall; the
    other sees ~4 % residual drag.
    """
    if active_rope not in (0, 1):
        raise ValueError("active_rope must be 0 or 1")
    try:
        from ropesim._rustcore import compute_half_rope_forces

        return compute_half_rope_forces(
            stiffness_a_kn, stiffness_b_kn, mass_kg, fall_factor, active_rope
        )
    except ImportError:
        pass

    residual = 0.04
    if active_rope == 0:
        f = _uiaa_peak_force(mass_kg, fall_factor, stiffness_a_kn)
        return f, f * residual
    f = _uiaa_peak_force(mass_kg, fall_factor, stiffness_b_kn)
    return f * residual, f


# ── knots ────────────────────────────────────────────────────────────────────

_KNOT_BASE_FACTORS = {
    "figure_eight_retrace": 0.775,
    "figure_eight_on_bight": 0.79,
    "bowline": 0.70,
    "clove_hitch": 0.625,
    "munter_hitch": 0.68,
    "double_fishermans": 0.775,
    "overhand_on_bight": 0.675,
    "alpine_butterfly": 0.725,
}


def knot_strength_factor(knot: "KnotType | str", diameter_mm: float) -> float:
    """Strength retention multiplier (0-1) for a knot tied in a rope.

    Midpoints of published pull-test ranges (DMM, BD QC Lab, UIAA), with a
    small diameter adjustment: thinner ropes lose slightly more strength.
    """
    name = _knot_name(knot)
    try:
        from ropesim._rustcore import compute_knot_strength_factor

        return compute_knot_strength_factor(name, diameter_mm)
    except ImportError:
        pass

    if name not in _KNOT_BASE_FACTORS:
        raise ValueError(f"unknown knot type: {name!r}")
    d = min(max(diameter_mm, 4.0), 13.0)
    adjustment = min(max((d - 9.5) * 0.005, -0.04), 0.04)
    return min(max(_KNOT_BASE_FACTORS[name] + adjustment, 0.40), 0.95)


def cord_anchor_strength(
    cord_mbs_kn: float,
    knot: "KnotType | str",
    num_strands: int,
    diameter_mm: float = 7.0,
) -> float:
    """Effective strength (kN) of a knotted multi-strand cord anchor."""
    name = _knot_name(knot)
    try:
        from ropesim._rustcore import compute_cord_anchor_strength

        return compute_cord_anchor_strength(cord_mbs_kn, name, max(num_strands, 1), diameter_mm)
    except ImportError:
        pass

    n = max(num_strands, 1)
    factor = knot_strength_factor(name, diameter_mm)
    share_efficiency = max(0.92 ** (n - 1), 0.70)
    return max(cord_mbs_kn, 0.0) * factor * n * share_efficiency


# ── sheath abrasion ──────────────────────────────────────────────────────────

_ROCK_ABRASIVENESS = {
    "sandstone": 1.00,
    "granite": 0.85,
    "basalt": 0.65,
    "limestone": 0.50,
    "ice": 0.10,
}


def abrasion_increment(
    rock_type: str,
    contact_force_kn: float,
    contact_duration_s: float,
    rope_velocity_mps: float,
) -> float:
    """Sheath abrasion increment for one rope-over-rock contact event.

    Archard-style wear: abrasiveness x load^1.3 x sliding distance.
    """
    rock = str(rock_type).lower()
    try:
        from ropesim._rustcore import compute_abrasion_increment

        return compute_abrasion_increment(
            rock, contact_force_kn, contact_duration_s, rope_velocity_mps
        )
    except ImportError:
        pass

    if rock not in _ROCK_ABRASIVENESS:
        raise ValueError(f"unknown rock type: {rock_type!r}")
    calibration = 0.0023
    force = max(contact_force_kn, 0.0)
    slide_m = max(rope_velocity_mps, 0.0) * max(contact_duration_s, 0.0)
    return min(max(calibration * _ROCK_ABRASIVENESS[rock] * force**1.3 * slide_m, 0.0), 1.0)


def _rating_for_score(score: float) -> SheathRating:
    if score < 0.05:
        return SheathRating.NEW
    if score < 0.45:
        return SheathRating.GOOD
    if score < RETIREMENT_THRESHOLD:
        return SheathRating.WORN
    return SheathRating.CRITICAL


def accumulate_sheath_wear(
    current: "SheathCondition | float",
    increment: float,
    sheath_pct: float = 37.0,
) -> SheathCondition:
    """Fold one abrasion increment into a sheath condition.

    ``current`` may be a :class:`SheathCondition` or a bare score float.
    A thicker sheath (higher ``sheath_pct``) wears proportionally slower.
    """
    score_in = current.abrasion_score if isinstance(current, SheathCondition) else float(current)
    prev_remaining = (
        current.estimated_falls_remaining
        if isinstance(current, SheathCondition)
        else 2**32 - 1
    )

    try:
        from ropesim._rustcore import accumulate_sheath_wear as _rust_acc

        r = _rust_acc(score_in, increment, sheath_pct)
        return SheathCondition(
            abrasion_score=r.abrasion_score,
            estimated_falls_remaining=int(r.estimated_falls_remaining),
            visual_rating=SheathRating(r.visual_rating),
        )
    except ImportError:
        pass

    sheath_factor = min(max(37.0 / min(max(sheath_pct, 20.0), 55.0), 0.65), 1.85)
    effective = min(max(increment, 0.0) * sheath_factor, 1.0)
    score = min(score_in + effective, 1.0)

    if effective > 1e-9:
        remaining = int(max(RETIREMENT_THRESHOLD - score, 0.0) / effective + 1e-9)
    else:
        remaining = prev_remaining

    return SheathCondition(
        abrasion_score=score,
        estimated_falls_remaining=remaining,
        visual_rating=_rating_for_score(score),
    )


# ── fall probability / risk ──────────────────────────────────────────────────

_STYLE_SHIFT = {"sport": 0.0, "trad": -1.2, "boulder": 1.0}


def fall_probability(
    route_grade_numeric: float,
    climber_grade_numeric: float,
    style: "ClimbingStyle | str" = ClimbingStyle.SPORT,
) -> float:
    """Probability (0-1) of falling on a single attempt.

    Grades use YDS numeric (5.10a -> 10.1, 5.12c -> 12.3).  Logistic over
    the grade delta; at the climber's limit p is about 0.5 for sport.
    """
    style_name = style.value if isinstance(style, ClimbingStyle) else str(style).lower()
    try:
        from ropesim._rustcore import compute_fall_probability

        return compute_fall_probability(route_grade_numeric, climber_grade_numeric, style_name)
    except ImportError:
        pass

    if style_name not in _STYLE_SHIFT:
        raise ValueError(f"unknown style: {style!r}")
    delta = route_grade_numeric - climber_grade_numeric
    x = 3.0 * delta + 0.6 * _STYLE_SHIFT[style_name]
    p = 1.0 / (1.0 + math.exp(-x))
    return min(max(p, 0.01), 0.95)


def cumulative_risk(
    fall_probability: float,
    num_attempts: int,
    peak_force_kn: float,
    rope_rated_falls: int,
    falls_taken_so_far: int = 0,
) -> CumulativeRisk:
    """Project cumulative fall exposure over ``num_attempts`` on one route."""
    try:
        from ropesim._rustcore import compute_cumulative_risk

        r = compute_cumulative_risk(
            fall_probability,
            max(num_attempts, 0),
            peak_force_kn,
            max(rope_rated_falls, 1),
            max(falls_taken_so_far, 0),
        )
        return CumulativeRisk(
            expected_falls=r.expected_falls,
            expected_total_force_kn=r.expected_total_force_kn,
            rope_life_consumed_pct=r.rope_life_consumed_pct,
            retirement_climbs_remaining=int(r.retirement_climbs_remaining),
        )
    except ImportError:
        pass

    p = min(max(fall_probability, 0.0), 1.0)
    expected_falls = p * max(num_attempts, 0)
    expected_total_force = expected_falls * max(peak_force_kn, 0.0)

    rated = float(max(rope_rated_falls, 1))
    severity = min(max(peak_force_kn / 7.0, 0.05), 2.0)
    projected = max(falls_taken_so_far, 0) + expected_falls * severity
    life_pct = min(projected / rated * 100.0, 100.0)

    per_session = max(expected_falls * severity, 1e-9)
    sessions_left = int(max(rated - projected, 0.0) / per_session)

    return CumulativeRisk(
        expected_falls=expected_falls,
        expected_total_force_kn=expected_total_force,
        rope_life_consumed_pct=life_pct,
        retirement_climbs_remaining=sessions_left,
    )


def daily_exposure(
    pitches: list[tuple[float, int]],
    peak_force_kn: float,
    rope_rated_falls: int,
    falls_taken_so_far: int = 0,
) -> DailyExposureReport:
    """Model a full climbing day across multiple pitches.

    ``pitches`` -- list of (fall_probability, attempts) per pitch.
    Flags the first pitch whose falls push the rope past rated life.
    """
    try:
        from ropesim._rustcore import compute_daily_exposure

        r = compute_daily_exposure(
            [(float(p), int(a)) for p, a in pitches],
            peak_force_kn,
            max(rope_rated_falls, 1),
            max(falls_taken_so_far, 0),
        )
        return DailyExposureReport(
            total_expected_falls=r.total_expected_falls,
            total_expected_force_kn=r.total_expected_force_kn,
            rope_life_consumed_pct=r.rope_life_consumed_pct,
            critical_pitch_index=int(r.critical_pitch_index),
            retirement_projected=bool(r.retirement_projected),
        )
    except ImportError:
        pass

    rated = float(max(rope_rated_falls, 1))
    severity = min(max(peak_force_kn / 7.0, 0.05), 2.0)

    running = float(max(falls_taken_so_far, 0))
    total_expected = 0.0
    critical = -1
    for i, (p, attempts) in enumerate(pitches):
        ef = min(max(p, 0.0), 1.0) * int(attempts)
        total_expected += ef
        running += ef * severity
        if critical < 0 and running >= rated:
            critical = i

    return DailyExposureReport(
        total_expected_falls=total_expected,
        total_expected_force_kn=total_expected * max(peak_force_kn, 0.0),
        rope_life_consumed_pct=min(running / rated * 100.0, 100.0),
        critical_pitch_index=critical,
        retirement_projected=running >= rated,
    )


# ── dynamic belayer ──────────────────────────────────────────────────────────

_DEVICE_SLIP = {
    "atc": 0.12,
    "tube": 0.12,
    "reverso": 0.10,
    "munter": 0.09,
    "megajul": 0.05,
    "giga_jul": 0.05,
    "click_up": 0.04,
    "sum": 0.04,
    "grigri": 0.02,
    "i_device": 0.02,
    "reverso_guide": 0.02,
}


def dynamic_belay_reduction(
    climber_mass_kg: float,
    belayer_mass_kg: float,
    belay_device: str = "atc",
    belayer_standing: bool = True,
    soft_catch_technique: bool = False,
) -> float:
    """Force-reduction factor (0.55-1.0) to multiply into peak impact force.

    Energy-based model: belayer lift plus device rope slip absorb part of
    the fall energy.  A light belayer giving a deliberate soft catch can
    reduce peak force by 30-45 % (Pavier 1998; Petzl test data).
    """
    device = str(belay_device).lower()
    try:
        from ropesim._rustcore import compute_dynamic_belay_reduction

        return compute_dynamic_belay_reduction(
            climber_mass_kg,
            belayer_mass_kg,
            device,
            belayer_standing,
            soft_catch_technique,
        )
    except ImportError:
        pass

    if device not in _DEVICE_SLIP:
        raise ValueError(f"unknown belay device: {belay_device!r}")

    mc = max(climber_mass_kg, 1.0)
    mb = max(belayer_mass_kg, 1.0)
    ratio = min(max(mc / mb, 0.2), 3.0)

    stance = 1.0 if belayer_standing else 0.45
    lift_m = 0.5 * (ratio - 0.2) / 0.8 * stance
    if soft_catch_technique:
        lift_m += 0.55 * stance
    lift_m = min(max(lift_m, 0.0), 1.5)

    fall_energy = mc * _G * 4.0
    belayer_energy = mb * _G * lift_m
    lift_fraction = min(max(belayer_energy / fall_energy, 0.0), 0.35)

    slip_fraction = _DEVICE_SLIP[device] * (1.3 if soft_catch_technique else 1.0)
    retained = min(max(1.0 - lift_fraction - slip_fraction, 0.30), 1.0)
    return min(max(math.sqrt(retained), 0.55), 1.0)
