// ropesim/_rustcore/src/risk.rs
//
// Fall probability and cumulative exposure model (v3).
//
// Estimates the probability of a leader fall from the gap between route
// grade and climber ability, then projects cumulative force exposure and
// rope wear across attempts and full climbing days.
//
// The per-attempt model is a logistic curve over grade delta, loosely
// calibrated to whipper-frequency survey data (sport climbers redpointing
// at their limit fall on most attempts; climbers 3+ grades below their
// limit almost never fall).
//
// Pure Rust — no PyO3.  Python bindings live in py_v3.rs, C FFI in ffi.rs.

/// Climbing style — affects baseline fall likelihood at a given grade delta.
///
/// Discriminants are stable and part of the C FFI contract (ropesim.h).
#[repr(i32)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ClimbingStyle {
    Sport = 0,
    Trad = 1,
    Boulder = 2,
}

impl ClimbingStyle {
    pub fn from_i32(v: i32) -> Option<Self> {
        match v {
            0 => Some(Self::Sport),
            1 => Some(Self::Trad),
            2 => Some(Self::Boulder),
            _ => None,
        }
    }

    /// Shift applied to the grade delta before the logistic.
    /// Trad climbers stay further inside their limit (falling is costly),
    /// boulderers try moves at or past their limit (falling is normal).
    fn style_shift(&self) -> f64 {
        match self {
            Self::Sport => 0.0,
            Self::Trad => -1.2,
            Self::Boulder => 1.0,
        }
    }
}

/// Probability (0–1) of falling on a single attempt.
///
/// * `route_grade_numeric`   — YDS numeric: 5.10a → 10.1, 5.12c → 12.3
/// * `climber_grade_numeric` — climber's typical redpoint grade, same scale
pub fn compute_fall_probability(
    route_grade_numeric: f64,
    climber_grade_numeric: f64,
    style: ClimbingStyle,
) -> f64 {
    // Grade delta in YDS letter grades ≈ 0.1 numeric units.
    let delta = route_grade_numeric - climber_grade_numeric;
    // Logistic: at the climber's limit (delta 0) p ≈ 0.5 for sport;
    // one number grade below (delta −1.0) p ≈ 0.05.
    let x = 3.0 * (delta + 0.0) + 0.6 * ClimbingStyle::style_shift(&style);
    let p = 1.0 / (1.0 + (-x).exp());
    p.clamp(0.01, 0.95)
}

/// Cumulative risk projection over repeated attempts.
#[derive(Clone, Copy, Debug)]
pub struct CumulativeRisk {
    pub expected_falls: f64,
    pub expected_total_force_kn: f64,
    pub rope_life_consumed_pct: f64,
    pub retirement_climbs_remaining: u32,
}

/// Project cumulative fall exposure over `num_attempts` on one route.
///
/// * `peak_force_kn`      — modelled peak impact force for this scenario
/// * `rope_rated_falls`   — UIAA rated fall count of the rope
/// * `falls_taken_so_far` — falls already logged on this rope
pub fn compute_cumulative_risk(
    fall_probability: f64,
    num_attempts: u32,
    peak_force_kn: f64,
    rope_rated_falls: u32,
    falls_taken_so_far: u32,
) -> CumulativeRisk {
    let p = fall_probability.clamp(0.0, 1.0);
    let expected_falls = p * num_attempts as f64;
    let expected_total_force = expected_falls * peak_force_kn.max(0.0);

    let rated = rope_rated_falls.max(1) as f64;
    // Only hard falls (≥ ~7 kN, near UIAA test severity) consume a full
    // rated fall; softer falls consume proportionally less.
    let severity = (peak_force_kn / 7.0).clamp(0.05, 2.0);
    let projected_falls = falls_taken_so_far as f64 + expected_falls * severity;
    let life_pct = (projected_falls / rated * 100.0).min(100.0);

    let per_session = (expected_falls * severity).max(1e-9);
    let sessions_left = ((rated - projected_falls).max(0.0) / per_session).floor();

    CumulativeRisk {
        expected_falls,
        expected_total_force_kn: expected_total_force,
        rope_life_consumed_pct: life_pct,
        retirement_climbs_remaining: sessions_left.min(u32::MAX as f64) as u32,
    }
}

/// One pitch in a day plan: (fall probability per attempt, attempts).
pub type PitchPlan = (f64, u32);

/// Aggregated exposure across a full climbing day.
#[derive(Clone, Debug)]
pub struct DailyExposureReport {
    pub total_expected_falls: f64,
    pub total_expected_force_kn: f64,
    pub rope_life_consumed_pct: f64,
    pub critical_pitch_index: i32, // −1 if none
    pub retirement_projected: bool,
}

/// Model a full day across multiple pitches.
///
/// * `pitches`              — per-pitch (fall probability, attempts)
/// * `peak_force_kn`        — representative peak force per fall
/// * `rope_rated_falls`     — UIAA rated fall count
/// * `falls_taken_so_far`   — falls already on the rope before today
///
/// Flags the first pitch (index) whose falls alone would push the rope past
/// its rated life; −1 if no single pitch is critical.
pub fn compute_daily_exposure(
    pitches: &[PitchPlan],
    peak_force_kn: f64,
    rope_rated_falls: u32,
    falls_taken_so_far: u32,
) -> DailyExposureReport {
    let rated = rope_rated_falls.max(1) as f64;
    let severity = (peak_force_kn / 7.0).clamp(0.05, 2.0);

    let mut running_falls = falls_taken_so_far as f64;
    let mut total_expected_falls = 0.0;
    let mut critical_pitch: i32 = -1;

    for (i, &(p, attempts)) in pitches.iter().enumerate() {
        let ef = p.clamp(0.0, 1.0) * attempts as f64;
        total_expected_falls += ef;
        running_falls += ef * severity;
        if critical_pitch < 0 && running_falls >= rated {
            critical_pitch = i as i32;
        }
    }

    let life_pct = (running_falls / rated * 100.0).min(100.0);

    DailyExposureReport {
        total_expected_falls,
        total_expected_force_kn: total_expected_falls * peak_force_kn.max(0.0),
        rope_life_consumed_pct: life_pct,
        critical_pitch_index: critical_pitch,
        retirement_projected: running_falls >= rated,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn falling_more_likely_on_harder_routes() {
        let easy = compute_fall_probability(9.0, 12.0, ClimbingStyle::Sport);
        let limit = compute_fall_probability(12.0, 12.0, ClimbingStyle::Sport);
        let over = compute_fall_probability(13.0, 12.0, ClimbingStyle::Sport);
        assert!(easy < limit && limit < over);
        assert!(easy < 0.05, "way below limit should be near-zero: {easy}");
        assert!(over > 0.9, "way above limit should be near-certain: {over}");
    }

    #[test]
    fn at_limit_probability_is_moderate() {
        let p = compute_fall_probability(11.0, 11.0, ClimbingStyle::Sport);
        assert!((0.3..=0.7).contains(&p), "at-limit p: {p}");
    }

    #[test]
    fn style_ordering_trad_sport_boulder() {
        let t = compute_fall_probability(11.0, 11.0, ClimbingStyle::Trad);
        let s = compute_fall_probability(11.0, 11.0, ClimbingStyle::Sport);
        let b = compute_fall_probability(11.0, 11.0, ClimbingStyle::Boulder);
        assert!(t < s && s < b);
    }

    #[test]
    fn probability_always_bounded() {
        for (r, c) in [(5.0, 15.0), (15.0, 5.0), (10.0, 10.0)] {
            let p = compute_fall_probability(r, c, ClimbingStyle::Sport);
            assert!((0.01..=0.95).contains(&p));
        }
    }

    #[test]
    fn cumulative_risk_scales_with_attempts() {
        let r5 = compute_cumulative_risk(0.5, 5, 6.0, 8, 0);
        let r10 = compute_cumulative_risk(0.5, 10, 6.0, 8, 0);
        assert!((r5.expected_falls - 2.5).abs() < 1e-9);
        assert!(r10.expected_total_force_kn > r5.expected_total_force_kn);
        assert!(r10.rope_life_consumed_pct > r5.rope_life_consumed_pct);
    }

    #[test]
    fn prior_falls_consume_rope_life() {
        let fresh = compute_cumulative_risk(0.5, 4, 7.0, 8, 0);
        let used = compute_cumulative_risk(0.5, 4, 7.0, 8, 6);
        assert!(used.rope_life_consumed_pct > fresh.rope_life_consumed_pct);
        assert!(used.retirement_climbs_remaining < fresh.retirement_climbs_remaining);
    }

    #[test]
    fn soft_falls_consume_less_life() {
        let soft = compute_cumulative_risk(0.5, 10, 3.0, 8, 0);
        let hard = compute_cumulative_risk(0.5, 10, 9.0, 8, 0);
        assert!(soft.rope_life_consumed_pct < hard.rope_life_consumed_pct);
    }

    #[test]
    fn daily_exposure_aggregates_pitches() {
        let pitches = vec![(0.3, 3), (0.6, 5), (0.1, 2)];
        let report = compute_daily_exposure(&pitches, 6.0, 8, 0);
        let expected = 0.3 * 3.0 + 0.6 * 5.0 + 0.1 * 2.0;
        assert!((report.total_expected_falls - expected).abs() < 1e-9);
        assert!(!report.retirement_projected);
        assert_eq!(report.critical_pitch_index, -1);
    }

    #[test]
    fn daily_exposure_flags_critical_pitch() {
        // Rope with 2 rated falls, 1 already taken; a projecting pitch with
        // near-certain hard falls should trip the critical flag.
        let pitches = vec![(0.1, 1), (0.9, 10)];
        let report = compute_daily_exposure(&pitches, 9.0, 2, 1);
        assert!(report.retirement_projected);
        assert_eq!(report.critical_pitch_index, 1);
    }
}
