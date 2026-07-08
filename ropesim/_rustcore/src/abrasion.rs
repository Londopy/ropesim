// ropesim/_rustcore/src/abrasion.rs
//
// Sheath abrasion accumulator (v3).
//
// Tracks cumulative sheath wear from rope-over-rock contact.  Wear rate
// scales with rock abrasiveness, contact pressure, slip velocity and
// duration — a simplified Archard wear model applied to nylon kernmantle,
// calibrated so a typical hard sport fall over a granite edge contributes
// ~0.5–2 % of sheath life.
//
// References:
//   Archard (1953) wear equation
//   Käpylä et al. tribology studies on nylon 6.6 vs. mineral surfaces
//   McKenna, Hearle & O'Hear (2004) "Handbook of Fibre Rope Technology"
//
// Pure Rust — no PyO3.  Python bindings live in py_v3.rs, C FFI in ffi.rs.

/// Rock types, ordered roughly by abrasiveness.
///
/// Discriminants are stable and part of the C FFI contract (ropesim.h).
#[repr(i32)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RockType {
    Granite = 0,
    Limestone = 1,
    Sandstone = 2,
    Basalt = 3,
    Ice = 4,
}

impl RockType {
    pub fn from_i32(v: i32) -> Option<Self> {
        match v {
            0 => Some(Self::Granite),
            1 => Some(Self::Limestone),
            2 => Some(Self::Sandstone),
            3 => Some(Self::Basalt),
            4 => Some(Self::Ice),
            _ => None,
        }
    }

    pub fn from_name(s: &str) -> Option<Self> {
        match s.to_ascii_lowercase().as_str() {
            "granite" => Some(Self::Granite),
            "limestone" => Some(Self::Limestone),
            "sandstone" => Some(Self::Sandstone),
            "basalt" => Some(Self::Basalt),
            "ice" => Some(Self::Ice),
            _ => None,
        }
    }

    pub fn name(&self) -> &'static str {
        match self {
            Self::Granite => "granite",
            Self::Limestone => "limestone",
            Self::Sandstone => "sandstone",
            Self::Basalt => "basalt",
            Self::Ice => "ice",
        }
    }

    /// Relative abrasiveness coefficient (sandstone = 1.0 reference).
    /// Sandstone's loose quartz grains cut nylon fastest; polished
    /// limestone is comparatively gentle; ice barely abrades at all.
    pub fn abrasiveness(&self) -> f64 {
        match self {
            Self::Sandstone => 1.00,
            Self::Granite => 0.85,
            Self::Basalt => 0.65,
            Self::Limestone => 0.50,
            Self::Ice => 0.10,
        }
    }
}

/// Visual sheath condition rating.
///
/// Discriminants are stable and part of the C FFI contract (ropesim.h).
#[repr(i32)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SheathRating {
    New = 0,
    Good = 1,
    Worn = 2,
    Critical = 3,
}

/// Cumulative sheath condition.
#[derive(Clone, Copy, Debug)]
pub struct SheathCondition {
    /// 0.0 (new) … 1.0 (fully consumed).  Retirement at ≥ 0.85.
    pub abrasion_score: f64,
    /// Estimate of similar wear events remaining before retirement.
    pub estimated_falls_remaining: u32,
    pub visual_rating: SheathRating,
}

impl SheathCondition {
    pub fn new_rope() -> Self {
        SheathCondition {
            abrasion_score: 0.0,
            estimated_falls_remaining: u32::MAX,
            visual_rating: SheathRating::New,
        }
    }

    pub fn needs_retirement(&self) -> bool {
        self.abrasion_score >= RETIREMENT_THRESHOLD
            || self.visual_rating == SheathRating::Critical
    }
}

pub const RETIREMENT_THRESHOLD: f64 = 0.85;

fn rating_for_score(score: f64) -> SheathRating {
    if score < 0.05 {
        SheathRating::New
    } else if score < 0.45 {
        SheathRating::Good
    } else if score < RETIREMENT_THRESHOLD {
        SheathRating::Worn
    } else {
        SheathRating::Critical
    }
}

/// Abrasion increment for one rope-over-rock contact event.
///
/// * `contact_force_kn`   — normal force pressing rope onto rock
/// * `contact_duration_s` — duration of loaded sliding contact
/// * `rope_velocity_mps`  — rope slip speed over the rock
///
/// Archard-style: wear ∝ abrasiveness × load^1.3 × sliding distance,
/// where sliding distance = velocity × duration.  The 1.3 exponent captures
/// the super-linear cutting behaviour of sharp mineral grains under
/// increasing pressure.  Calibration constant chosen so that a 5 kN fall
/// sliding 2 m/s for 0.4 s over granite ≈ 0.013 (≈ 65 such events to
/// retirement).
pub fn compute_abrasion_increment(
    rock: RockType,
    contact_force_kn: f64,
    contact_duration_s: f64,
    rope_velocity_mps: f64,
) -> f64 {
    const CALIBRATION: f64 = 0.0023;
    let force = contact_force_kn.max(0.0);
    let slide_m = rope_velocity_mps.max(0.0) * contact_duration_s.max(0.0);
    (CALIBRATION * rock.abrasiveness() * force.powf(1.3) * slide_m).clamp(0.0, 1.0)
}

/// Fold one abrasion increment into a sheath condition.
///
/// * `sheath_pct` — sheath mass as % of rope (EN 892 spec sheet value,
///   typically 30–45 %).  A thicker sheath wears proportionally slower.
pub fn accumulate_sheath_wear(
    current: SheathCondition,
    increment: f64,
    sheath_pct: f64,
) -> SheathCondition {
    // Reference sheath is 37 % — thicker sheaths absorb wear more slowly.
    let sheath_factor = (37.0 / sheath_pct.clamp(20.0, 55.0)).clamp(0.65, 1.85);
    let effective = (increment.max(0.0) * sheath_factor).min(1.0);
    let score = (current.abrasion_score + effective).min(1.0);

    let falls_remaining = if effective > 1e-9 {
        (((RETIREMENT_THRESHOLD - score).max(0.0)) / effective + 1e-9).floor() as u32
    } else {
        current.estimated_falls_remaining
    };

    SheathCondition {
        abrasion_score: score,
        estimated_falls_remaining: falls_remaining,
        visual_rating: rating_for_score(score),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sandstone_wears_faster_than_limestone() {
        let s = compute_abrasion_increment(RockType::Sandstone, 5.0, 0.4, 2.0);
        let l = compute_abrasion_increment(RockType::Limestone, 5.0, 0.4, 2.0);
        assert!(s > l);
    }

    #[test]
    fn ice_barely_abrades() {
        let i = compute_abrasion_increment(RockType::Ice, 5.0, 0.4, 2.0);
        let g = compute_abrasion_increment(RockType::Granite, 5.0, 0.4, 2.0);
        assert!(i < 0.2 * g);
    }

    #[test]
    fn higher_force_and_velocity_wear_more() {
        let base = compute_abrasion_increment(RockType::Granite, 4.0, 0.4, 1.0);
        assert!(compute_abrasion_increment(RockType::Granite, 8.0, 0.4, 1.0) > base);
        assert!(compute_abrasion_increment(RockType::Granite, 4.0, 0.4, 3.0) > base);
        assert!(compute_abrasion_increment(RockType::Granite, 4.0, 0.8, 1.0) > base);
    }

    #[test]
    fn zero_contact_is_zero_wear() {
        assert_eq!(compute_abrasion_increment(RockType::Granite, 0.0, 0.4, 2.0), 0.0);
        assert_eq!(compute_abrasion_increment(RockType::Granite, 5.0, 0.0, 2.0), 0.0);
    }

    #[test]
    fn typical_fall_consumes_small_fraction() {
        // 5 kN over granite, 0.4 s at 2 m/s — should take dozens of events
        // to retire the rope, not a handful, and not thousands.
        let inc = compute_abrasion_increment(RockType::Granite, 5.0, 0.4, 2.0);
        let events = RETIREMENT_THRESHOLD / inc;
        assert!(events > 20.0 && events < 500.0, "events to retirement: {events}");
    }

    #[test]
    fn accumulation_progresses_to_retirement() {
        let mut cond = SheathCondition::new_rope();
        assert_eq!(cond.visual_rating, SheathRating::New);
        let inc = 0.1;
        for _ in 0..20 {
            cond = accumulate_sheath_wear(cond, inc, 37.0);
            if cond.needs_retirement() {
                break;
            }
        }
        assert!(cond.needs_retirement());
        assert_eq!(cond.visual_rating, SheathRating::Critical);
        assert!(cond.abrasion_score <= 1.0);
    }

    #[test]
    fn thick_sheath_wears_slower() {
        let a = accumulate_sheath_wear(SheathCondition::new_rope(), 0.1, 45.0);
        let b = accumulate_sheath_wear(SheathCondition::new_rope(), 0.1, 30.0);
        assert!(a.abrasion_score < b.abrasion_score);
    }

    #[test]
    fn falls_remaining_estimate_decreases() {
        let c1 = accumulate_sheath_wear(SheathCondition::new_rope(), 0.05, 37.0);
        let c2 = accumulate_sheath_wear(c1, 0.05, 37.0);
        assert!(c2.estimated_falls_remaining < c1.estimated_falls_remaining);
     }
}
