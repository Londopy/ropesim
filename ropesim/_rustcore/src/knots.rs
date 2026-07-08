// ropesim/_rustcore/src/knots.rs
//
// Knot strength reduction model (v3).
//
// Any knot concentrates stress at the first tight bend where the rope enters
// the knot, reducing breaking strength versus the straight-pull rating.
//
// Reduction factors are midpoints of published pull-to-failure test ranges:
//   DMM "Knot strength" test series (2015)
//   Black Diamond QC Lab drop/pull tests
//   UIAA Safety Commission knot efficiency tables
//   Ashley (1944) for classical baseline values
//
// Pure Rust — no PyO3.  Python bindings live in py_v3.rs, C FFI in ffi.rs.

/// Knot types modelled by ropesim.
///
/// Discriminants are stable and part of the C FFI contract (ropesim.h).
#[repr(i32)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum KnotType {
    FigureEightRetrace = 0,
    FigureEightOnBight = 1,
    Bowline = 2,
    CloveHitch = 3,
    MunterHitch = 4,
    DoubleFishermans = 5,
    OverhandOnBight = 6,
    AlpineButterfly = 7,
}

impl KnotType {
    pub fn from_i32(v: i32) -> Option<Self> {
        match v {
            0 => Some(Self::FigureEightRetrace),
            1 => Some(Self::FigureEightOnBight),
            2 => Some(Self::Bowline),
            3 => Some(Self::CloveHitch),
            4 => Some(Self::MunterHitch),
            5 => Some(Self::DoubleFishermans),
            6 => Some(Self::OverhandOnBight),
            7 => Some(Self::AlpineButterfly),
            _ => None,
        }
    }

    pub fn from_name(s: &str) -> Option<Self> {
        match s.to_ascii_lowercase().as_str() {
            "figure_eight_retrace" | "figure8_retrace" | "figure_8" => {
                Some(Self::FigureEightRetrace)
            }
            "figure_eight_on_bight" | "figure8_on_bight" => Some(Self::FigureEightOnBight),
            "bowline" => Some(Self::Bowline),
            "clove_hitch" => Some(Self::CloveHitch),
            "munter_hitch" | "munter" => Some(Self::MunterHitch),
            "double_fishermans" | "double_fishermans_bend" => Some(Self::DoubleFishermans),
            "overhand_on_bight" | "overhand" => Some(Self::OverhandOnBight),
            "alpine_butterfly" | "butterfly" => Some(Self::AlpineButterfly),
            _ => None,
        }
    }

    pub fn name(&self) -> &'static str {
        match self {
            Self::FigureEightRetrace => "figure_eight_retrace",
            Self::FigureEightOnBight => "figure_eight_on_bight",
            Self::Bowline => "bowline",
            Self::CloveHitch => "clove_hitch",
            Self::MunterHitch => "munter_hitch",
            Self::DoubleFishermans => "double_fishermans",
            Self::OverhandOnBight => "overhand_on_bight",
            Self::AlpineButterfly => "alpine_butterfly",
        }
    }

    /// Baseline strength retention factor at the 9.5 mm reference diameter.
    fn base_factor(&self) -> f64 {
        match self {
            Self::FigureEightRetrace => 0.775, // 0.75–0.80
            Self::FigureEightOnBight => 0.79,  // 0.77–0.81
            Self::Bowline => 0.70,             // 0.67–0.73
            Self::CloveHitch => 0.625,         // 0.60–0.65
            Self::MunterHitch => 0.68,         // 0.65–0.72
            Self::DoubleFishermans => 0.775,   // 0.75–0.80
            Self::OverhandOnBight => 0.675,    // 0.65–0.70
            Self::AlpineButterfly => 0.725,    // 0.70–0.75
        }
    }
}

/// Strength retention multiplier (0–1) applied to the rope's rated MBS
/// when the given knot is tied in it.
///
/// Thinner ropes lose slightly more strength in a knot: the bend radius
/// relative to fibre diameter is smaller, concentrating shear.  Adjustment:
/// ±0.5 % per mm from the 9.5 mm reference, capped at ±4 %.
pub fn compute_knot_strength_factor(knot: KnotType, diameter_mm: f64) -> f64 {
    let d = diameter_mm.clamp(4.0, 13.0);
    let adjustment = ((d - 9.5) * 0.005).clamp(-0.04, 0.04);
    (knot.base_factor() + adjustment).clamp(0.40, 0.95)
}

/// Effective strength (kN) of a knotted, multi-strand cord anchor
/// (cordelette, sling girth-hitch, etc.).
///
/// * `cord_mbs_kn`  — rated single-strand breaking strength of the cord
/// * `knot`         — master-point knot
/// * `num_strands`  — strands sharing the load at the master point
/// * `diameter_mm`  — cord diameter (for knot factor adjustment)
///
/// Strands never share perfectly: each added strand contributes at ~92 %
/// efficiency (Long & Gaines anchor test data).
pub fn compute_cord_anchor_strength(
    cord_mbs_kn: f64,
    knot: KnotType,
    num_strands: u32,
    diameter_mm: f64,
) -> f64 {
    let n = num_strands.max(1) as f64;
    let knot_factor = compute_knot_strength_factor(knot, diameter_mm);
    let share_efficiency = 0.92_f64.powf(n - 1.0).max(0.70);
    cord_mbs_kn.max(0.0) * knot_factor * n * share_efficiency
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn factors_within_published_ranges() {
        let d = 9.5;
        let f8 = compute_knot_strength_factor(KnotType::FigureEightRetrace, d);
        assert!((0.75..=0.80).contains(&f8), "figure-8: {f8}");
        let clove = compute_knot_strength_factor(KnotType::CloveHitch, d);
        assert!((0.60..=0.65).contains(&clove), "clove: {clove}");
        let overhand = compute_knot_strength_factor(KnotType::OverhandOnBight, d);
        assert!((0.65..=0.70).contains(&overhand), "overhand: {overhand}");
    }

    #[test]
    fn all_knots_reduce_strength() {
        for k in [
            KnotType::FigureEightRetrace,
            KnotType::FigureEightOnBight,
            KnotType::Bowline,
            KnotType::CloveHitch,
            KnotType::MunterHitch,
            KnotType::DoubleFishermans,
            KnotType::OverhandOnBight,
            KnotType::AlpineButterfly,
        ] {
            let f = compute_knot_strength_factor(k, 9.8);
            assert!(f < 1.0 && f > 0.4, "{k:?} factor {f} out of range");
        }
    }

    #[test]
    fn thinner_rope_loses_more() {
        let thin = compute_knot_strength_factor(KnotType::Bowline, 7.7);
        let thick = compute_knot_strength_factor(KnotType::Bowline, 10.5);
        assert!(thin < thick);
    }

    #[test]
    fn enum_roundtrip() {
        for i in 0..8 {
            let k = KnotType::from_i32(i).unwrap();
            assert_eq!(k as i32, i);
            assert_eq!(KnotType::from_name(k.name()), Some(k));
        }
        assert!(KnotType::from_i32(99).is_none());
        assert!(KnotType::from_name("granny_knot").is_none());
    }

    #[test]
    fn cordelette_strength_scales_with_strands() {
        let one = compute_cord_anchor_strength(14.0, KnotType::OverhandOnBight, 1, 7.0);
        let three = compute_cord_anchor_strength(14.0, KnotType::OverhandOnBight, 3, 7.0);
        assert!(three > 2.0 * one, "three strands beat two singles");
        assert!(three < 3.0 * one, "but not perfectly efficient");
    }
}
