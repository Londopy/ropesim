// ropesim/_rustcore/src/twin_rope.rs
//
// Twin-rope and half-rope force models (v3).
//
// When two ropes run through the same piece of protection they do not behave
// as two independent springs: friction at the carabiner transfers load
// between the strands and dissipates energy, so the total peak force is
// lower than the naive two-spring sum.
//
// References:
//   UIAA 101 twin/half rope test requirements (EN 892 Annex)
//   Beal / Edelrid twin-rope drop test data (published catalogues)
//   Semmel & Hellberg (2006) "Halbseil und Zwillingsseil", DAV Panorama
//
// Pure Rust — no PyO3.  Python bindings live in py_v3.rs, C FFI in ffi.rs.

const G: f64 = 9.81;

/// Peak force for a single strand via the UIAA energy model (kN).
#[inline]
pub(crate) fn uiaa_peak_force(mass_kg: f64, fall_factor: f64, stiffness_kn: f64) -> f64 {
    let mg = mass_kg * G / 1000.0; // kN
    let ff = fall_factor.clamp(0.0, 2.0);
    let k = stiffness_kn.max(0.0);
    mg + (mg * mg + 2.0 * mg * ff * k).sqrt()
}

/// Forces on each strand of a twin-rope pair clipped through the same piece.
///
/// * `stiffness_a_kn`, `stiffness_b_kn` — length-normalised strand stiffness (kN)
/// * `mass_kg`      — falling mass
/// * `fall_factor`  — UIAA fall factor (0–2)
/// * `inter_rope_friction` — friction coefficient between the strands at the
///   carabiner (0 = frictionless, typical 0.1–0.3)
///
/// Returns `(force_on_rope_a_kn, force_on_rope_b_kn)`.
///
/// Model: the two strands act as springs in parallel, sharing load in
/// proportion to stiffness.  Inter-rope friction does two things:
///  1. dissipates energy (reduces total peak force, up to ~12 %)
///  2. transfers load from the stiffer strand to the softer one,
///     partially equalising the pair.
pub fn compute_twin_rope_forces(
    stiffness_a_kn: f64,
    stiffness_b_kn: f64,
    mass_kg: f64,
    fall_factor: f64,
    inter_rope_friction: f64,
) -> (f64, f64) {
    let ka = stiffness_a_kn.max(0.0);
    let kb = stiffness_b_kn.max(0.0);
    let mu = inter_rope_friction.clamp(0.0, 1.0);

    let k_total = (ka + kb).max(1e-9);

    // Total peak force for the parallel spring pair.
    let f_total_ideal = uiaa_peak_force(mass_kg, fall_factor, k_total);

    // Friction between the moving strands dissipates energy.
    // Bounded: even high friction cannot remove more than ~12 % of peak force
    // (energy is dominated by strand elongation, not inter-strand slip).
    let dissipation = 0.12 * (1.0 - (-3.0 * mu).exp());
    let f_total = f_total_ideal * (1.0 - dissipation);

    // Stiffness-proportional share…
    let share_a = ka / k_total;
    // …partially equalised by friction transfer (mu = 0 → pure stiffness
    // share; large mu → pulled toward 50/50).
    let transfer = 0.5 * (1.0 - (-2.0 * mu).exp()); // 0‥0.43
    let eq_share_a = share_a + (0.5 - share_a) * transfer;

    (f_total * eq_share_a, f_total * (1.0 - eq_share_a))
}

/// Forces on a half-rope (double-rope) pair clipped **alternately**.
///
/// Only one strand arrests a given fall.  The inactive strand sees a small
/// residual drag load from running through lower pieces (~4 % of the active
/// strand force).
///
/// * `active_rope` — 0 = strand A takes the fall, 1 = strand B.
///
/// Returns `(force_on_rope_a_kn, force_on_rope_b_kn)`.
pub fn compute_half_rope_forces(
    stiffness_a_kn: f64,
    stiffness_b_kn: f64,
    mass_kg: f64,
    fall_factor: f64,
    active_rope: u8,
) -> (f64, f64) {
    const RESIDUAL: f64 = 0.04;
    if active_rope == 0 {
        let f = uiaa_peak_force(mass_kg, fall_factor, stiffness_a_kn);
        (f, f * RESIDUAL)
    } else {
        let f = uiaa_peak_force(mass_kg, fall_factor, stiffness_b_kn);
        (f * RESIDUAL, f)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const M: f64 = 80.0;
    const FF: f64 = 1.0;
    const K: f64 = 20.0; // typical twin strand stiffness, kN

    #[test]
    fn twin_total_below_two_independent_strands() {
        let (fa, fb) = compute_twin_rope_forces(K, K, M, FF, 0.2);
        let single = uiaa_peak_force(M, FF, K);
        assert!(fa + fb < 2.0 * single, "twin pair must share energy");
        assert!(fa + fb > single, "pair must exceed one strand alone");
    }

    #[test]
    fn twin_equal_stiffness_splits_evenly() {
        let (fa, fb) = compute_twin_rope_forces(K, K, M, FF, 0.15);
        assert!((fa - fb).abs() < 1e-9);
    }

    #[test]
    fn twin_stiffer_strand_takes_more_load() {
        let (fa, fb) = compute_twin_rope_forces(30.0, 15.0, M, FF, 0.0);
        assert!(fa > fb);
        // exact stiffness-proportional split at zero friction
        assert!((fa / (fa + fb) - 30.0 / 45.0).abs() < 1e-9);
    }

    #[test]
    fn twin_friction_equalises_strands() {
        let (fa0, fb0) = compute_twin_rope_forces(30.0, 15.0, M, FF, 0.0);
        let (fa1, fb1) = compute_twin_rope_forces(30.0, 15.0, M, FF, 0.5);
        assert!((fa1 - fb1).abs() < (fa0 - fb0).abs());
    }

    #[test]
    fn twin_friction_reduces_total_force() {
        let (fa0, fb0) = compute_twin_rope_forces(K, K, M, FF, 0.0);
        let (fa1, fb1) = compute_twin_rope_forces(K, K, M, FF, 0.4);
        assert!(fa1 + fb1 < fa0 + fb0);
    }

    #[test]
    fn half_rope_only_active_strand_loaded() {
        let (fa, fb) = compute_half_rope_forces(15.0, 15.0, M, FF, 0);
        assert!(fa > 2.0, "active strand must carry real force");
        assert!(fb < 0.1 * fa, "inactive strand only residual drag");

        let (fa2, fb2) = compute_half_rope_forces(15.0, 15.0, M, FF, 1);
        assert!((fa - fb2).abs() < 1e-9 && (fb - fa2).abs() < 1e-9, "symmetric");
    }

    #[test]
    fn half_rope_lower_force_than_single_stiff_rope() {
        // Half ropes have lower rated impact force (softer) than singles.
        let (fa, _) = compute_half_rope_forces(14.0, 14.0, M, FF, 0);
        let single = uiaa_peak_force(M, FF, 24.0);
        assert!(fa < single);
    }

    #[test]
    fn degenerate_inputs_do_not_panic() {
        let (fa, fb) = compute_twin_rope_forces(0.0, 0.0, M, FF, 0.0);
        assert!(fa.is_finite() && fb.is_finite());
        let (fa, fb) = compute_twin_rope_forces(K, K, M, 0.0, 0.0);
        assert!(fa > 0.0 && fb > 0.0); // still body weight
    }
}
