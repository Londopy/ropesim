// ropesim/_rustcore/src/py_v3.rs
//
// PyO3 bindings for the v3 physics modules (twin_rope, knots, abrasion,
// risk, belay).  The physics itself lives in the pure-Rust modules; this
// file only translates types.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::abrasion;
use crate::abrasion::{RockType, SheathRating};
use crate::belay;
use crate::belay::BelayDevice;
use crate::knots;
use crate::knots::KnotType;
use crate::risk;
use crate::risk::ClimbingStyle;
use crate::twin_rope;

fn parse_knot(name: &str) -> PyResult<KnotType> {
    KnotType::from_name(name)
        .ok_or_else(|| PyValueError::new_err(format!("unknown knot type: {name:?}")))
}

fn parse_rock(name: &str) -> PyResult<RockType> {
    RockType::from_name(name)
        .ok_or_else(|| PyValueError::new_err(format!("unknown rock type: {name:?}")))
}

fn parse_style(name: &str) -> PyResult<ClimbingStyle> {
    match name.to_ascii_lowercase().as_str() {
        "sport" => Ok(ClimbingStyle::Sport),
        "trad" => Ok(ClimbingStyle::Trad),
        "boulder" => Ok(ClimbingStyle::Boulder),
        _ => Err(PyValueError::new_err(format!("unknown style: {name:?}"))),
    }
}

fn parse_device(name: &str) -> PyResult<BelayDevice> {
    BelayDevice::from_name(name)
        .ok_or_else(|| PyValueError::new_err(format!("unknown belay device: {name:?}")))
}

// ── twin / half ropes ────────────────────────────────────────────────────────

/// Forces (kN) on each strand of a twin-rope pair through a shared piece.
#[pyfunction]
pub fn compute_twin_rope_forces(
    stiffness_a_kn: f64,
    stiffness_b_kn: f64,
    mass_kg: f64,
    fall_factor: f64,
    inter_rope_friction: f64,
) -> (f64, f64) {
    twin_rope::compute_twin_rope_forces(
        stiffness_a_kn,
        stiffness_b_kn,
        mass_kg,
        fall_factor,
        inter_rope_friction,
    )
}

/// Forces (kN) on a half-rope pair clipped alternately.
/// `active_rope` — 0 = strand A arrests this fall, 1 = strand B.
#[pyfunction]
pub fn compute_half_rope_forces(
    stiffness_a_kn: f64,
    stiffness_b_kn: f64,
    mass_kg: f64,
    fall_factor: f64,
    active_rope: u8,
) -> PyResult<(f64, f64)> {
    if active_rope > 1 {
        return Err(PyValueError::new_err("active_rope must be 0 or 1"));
    }
    Ok(twin_rope::compute_half_rope_forces(
        stiffness_a_kn,
        stiffness_b_kn,
        mass_kg,
        fall_factor,
        active_rope,
    ))
}

// ── knots ────────────────────────────────────────────────────────────────────

/// Strength retention multiplier (0–1) for a knot tied in a rope.
///
/// Knot names: figure_eight_retrace, figure_eight_on_bight, bowline,
/// clove_hitch, munter_hitch, double_fishermans, overhand_on_bight,
/// alpine_butterfly.
#[pyfunction]
pub fn compute_knot_strength_factor(knot: &str, diameter_mm: f64) -> PyResult<f64> {
    Ok(knots::compute_knot_strength_factor(parse_knot(knot)?, diameter_mm))
}

/// Effective strength (kN) of a knotted multi-strand cord anchor.
#[pyfunction]
pub fn compute_cord_anchor_strength(
    cord_mbs_kn: f64,
    knot: &str,
    num_strands: u32,
    diameter_mm: f64,
) -> PyResult<f64> {
    Ok(knots::compute_cord_anchor_strength(
        cord_mbs_kn,
        parse_knot(knot)?,
        num_strands,
        diameter_mm,
    ))
}

// ── sheath abrasion ──────────────────────────────────────────────────────────

/// Sheath condition after accumulated abrasion.
#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct PySheathCondition {
    pub abrasion_score: f64,
    pub estimated_falls_remaining: u64,
    pub visual_rating: String,
    pub needs_retirement: bool,
}

#[pymethods]
impl PySheathCondition {
    fn __repr__(&self) -> String {
        format!(
            "SheathCondition(score={:.3}, rating={}, retire={})",
            self.abrasion_score, self.visual_rating, self.needs_retirement
        )
    }
}

fn rating_name(r: SheathRating) -> &'static str {
    match r {
        SheathRating::New => "NEW",
        SheathRating::Good => "GOOD",
        SheathRating::Worn => "WORN",
        SheathRating::Critical => "CRITICAL",
    }
}

/// Abrasion increment for one rope-over-rock contact event.
///
/// Rock names: granite, limestone, sandstone, basalt, ice.
#[pyfunction]
pub fn compute_abrasion_increment(
    rock_type: &str,
    contact_force_kn: f64,
    contact_duration_s: f64,
    rope_velocity_mps: f64,
) -> PyResult<f64> {
    Ok(abrasion::compute_abrasion_increment(
        parse_rock(rock_type)?,
        contact_force_kn,
        contact_duration_s,
        rope_velocity_mps,
    ))
}

/// Fold an abrasion increment into a running abrasion score.
#[pyfunction]
pub fn accumulate_sheath_wear(
    current_score: f64,
    increment: f64,
    sheath_pct: f64,
) -> PySheathCondition {
    let current = abrasion::SheathCondition {
        abrasion_score: current_score.clamp(0.0, 1.0),
        estimated_falls_remaining: u32::MAX,
        visual_rating: SheathRating::New,
    };
    let updated = abrasion::accumulate_sheath_wear(current, increment, sheath_pct);
    PySheathCondition {
        abrasion_score: updated.abrasion_score,
        estimated_falls_remaining: updated.estimated_falls_remaining as u64,
        visual_rating: rating_name(updated.visual_rating).to_string(),
        needs_retirement: updated.needs_retirement(),
    }
}

// ── fall probability / risk ──────────────────────────────────────────────────

/// Cumulative risk projection over repeated attempts.
#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct PyCumulativeRisk {
    pub expected_falls: f64,
    pub expected_total_force_kn: f64,
    pub rope_life_consumed_pct: f64,
    pub retirement_climbs_remaining: u32,
}

#[pymethods]
impl PyCumulativeRisk {
    fn __repr__(&self) -> String {
        format!(
            "CumulativeRisk(falls={:.2}, force={:.1}kN, life={:.0}%)",
            self.expected_falls, self.expected_total_force_kn, self.rope_life_consumed_pct
        )
    }
}

/// Aggregated exposure across a full climbing day.
#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct PyDailyExposureReport {
    pub total_expected_falls: f64,
    pub total_expected_force_kn: f64,
    pub rope_life_consumed_pct: f64,
    pub critical_pitch_index: i32,
    pub retirement_projected: bool,
}

#[pymethods]
impl PyDailyExposureReport {
    fn __repr__(&self) -> String {
        format!(
            "DailyExposureReport(falls={:.2}, life={:.0}%, retire={})",
            self.total_expected_falls, self.rope_life_consumed_pct, self.retirement_projected
        )
    }
}

/// Probability (0–1) of falling on a single attempt.
///
/// Grades use YDS numeric (5.10a → 10.1).  Styles: sport, trad, boulder.
#[pyfunction]
pub fn compute_fall_probability(
    route_grade_numeric: f64,
    climber_grade_numeric: f64,
    style: &str,
) -> PyResult<f64> {
    Ok(risk::compute_fall_probability(
        route_grade_numeric,
        climber_grade_numeric,
        parse_style(style)?,
    ))
}

/// Project cumulative fall exposure over `num_attempts` on one route.
#[pyfunction]
pub fn compute_cumulative_risk(
    fall_probability: f64,
    num_attempts: u32,
    peak_force_kn: f64,
    rope_rated_falls: u32,
    falls_taken_so_far: u32,
) -> PyCumulativeRisk {
    let r = risk::compute_cumulative_risk(
        fall_probability,
        num_attempts,
        peak_force_kn,
        rope_rated_falls,
        falls_taken_so_far,
    );
    PyCumulativeRisk {
        expected_falls: r.expected_falls,
        expected_total_force_kn: r.expected_total_force_kn,
        rope_life_consumed_pct: r.rope_life_consumed_pct,
        retirement_climbs_remaining: r.retirement_climbs_remaining,
    }
}

/// Model a full climbing day across multiple pitches.
///
/// `pitches` — list of (fall_probability, attempts) tuples.
#[pyfunction]
pub fn compute_daily_exposure(
    pitches: Vec<(f64, u32)>,
    peak_force_kn: f64,
    rope_rated_falls: u32,
    falls_taken_so_far: u32,
) -> PyDailyExposureReport {
    let r = risk::compute_daily_exposure(
        &pitches,
        peak_force_kn,
        rope_rated_falls,
        falls_taken_so_far,
    );
    PyDailyExposureReport {
        total_expected_falls: r.total_expected_falls,
        total_expected_force_kn: r.total_expected_force_kn,
        rope_life_consumed_pct: r.rope_life_consumed_pct,
        critical_pitch_index: r.critical_pitch_index,
        retirement_projected: r.retirement_projected,
    }
}

// ── dynamic belayer ──────────────────────────────────────────────────────────

/// Dynamic belay force-reduction factor (0.55–1.0).
///
/// Devices: atc, grigri, tube, reverso, reverso_guide, megajul, giga_jul,
/// click_up, i_device, sum, munter.
#[pyfunction]
pub fn compute_dynamic_belay_reduction(
    climber_mass_kg: f64,
    belayer_mass_kg: f64,
    belay_device: &str,
    belayer_standing: bool,
    soft_catch_technique: bool,
) -> PyResult<f64> {
    Ok(belay::compute_dynamic_belay_reduction(
        climber_mass_kg,
        belayer_mass_kg,
        parse_device(belay_device)?,
        belayer_standing,
        soft_catch_technique,
    ))
}

// ── registration ─────────────────────────────────────────────────────────────

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compute_twin_rope_forces, m)?)?;
    m.add_function(wrap_pyfunction!(compute_half_rope_forces, m)?)?;
    m.add_function(wrap_pyfunction!(compute_knot_strength_factor, m)?)?;
    m.add_function(wrap_pyfunction!(compute_cord_anchor_strength, m)?)?;
    m.add_function(wrap_pyfunction!(compute_abrasion_increment, m)?)?;
    m.add_function(wrap_pyfunction!(accumulate_sheath_wear, m)?)?;
    m.add_function(wrap_pyfunction!(compute_fall_probability, m)?)?;
    m.add_function(wrap_py