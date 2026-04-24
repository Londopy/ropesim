// ropesim/_rustcore/src/batch.rs
//
// Parallel batch sweep functions using Rayon.
//
// All sweeps expose a simple flat-Vec<f64> interface so Python can reshape
// results with numpy without any extra copies.

use pyo3::prelude::*;
use rayon::prelude::*;

use crate::physics::{
    compute_impact_force_uiaa_inner,
    compute_force_curve_inner,
};

// ── 1. Sweep fall factor → peak force ────────────────────────────────────────

/// Compute peak impact force for a list of fall factors in parallel.
///
/// Returns Vec<f64> of length `ff_values.len()`, one peak force (kN) per
/// fall factor.  Useful for producing "peak force vs fall factor" curves.
#[pyfunction]
pub fn batch_sweep_fall_factors(
    mass_kg:        f64,
    ff_values:      Vec<f64>,
    stiffness_kn:   f64,
    belay_friction: f64,
) -> Vec<f64> {
    ff_values
        .par_iter()
        .map(|&ff| compute_impact_force_uiaa_inner(mass_kg, ff, stiffness_kn, belay_friction))
        .collect()
}

// ── 2. Sweep rope-out → peak force ───────────────────────────────────────────

/// For a fixed fall distance, sweep rope-out length and return peak force (kN).
///
/// Returns Vec<f64> of length `steps`.
#[pyfunction]
pub fn batch_sweep_rope_out(
    mass_kg:         f64,
    fall_distance_m: f64,
    rope_out_min_m:  f64,
    rope_out_max_m:  f64,
    steps:           usize,
    stiffness_kn:    f64,
    belay_friction:  f64,
) -> PyResult<Vec<f64>> {
    if steps == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("steps must be > 0"));
    }
    if rope_out_min_m <= 0.0 || rope_out_max_m <= 0.0 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "rope_out values must be > 0",
        ));
    }

    let results = (0..steps)
        .into_par_iter()
        .map(|i| {
            let t = if steps > 1 { i as f64 / (steps - 1) as f64 } else { 0.5 };
            let rope_out = rope_out_min_m + t * (rope_out_max_m - rope_out_min_m);
            let ff = (fall_distance_m / rope_out).clamp(0.0, 2.0);
            compute_impact_force_uiaa_inner(mass_kg, ff, stiffness_kn, belay_friction)
        })
        .collect();

    Ok(results)
}

// ── 3. Batch parallel force curves ────────────────────────────────────────────

/// Compute multiple RK4 force-time curves in parallel.
///
/// `params` is a list of (mass_kg, fall_distance_m, rope_out_m, stiffness_kn,
/// damping_ratio, timestep_ms) tuples — one simulation per tuple.
///
/// Returns a list of force curves, each a Vec<f64> of kN values.
#[pyfunction]
pub fn parallel_force_curves(
    params: Vec<(f64, f64, f64, f64, f64, f64)>,
) -> Vec<Vec<f64>> {
    params
        .par_iter()
        .map(|&(mass_kg, fall_dist, rope_out, stiffness_kn, damping, timestep_ms)| {
            compute_force_curve_inner(
                mass_kg, fall_dist, rope_out, stiffness_kn, damping, timestep_ms,
            )
        })
        .collect()
}

// ── 4. Sweep climber height → peak force ─────────────────────────────────────

/// Sweep climber height above ground, modelling each as a lead-fall.
///
/// The last piece of protection is at `last_pro_height_m`; belay is at
/// `belay_height_m` (usually 0.0).
///
/// Returns flat Vec<f64> of length `steps × 3` in row-major order:
///   [height_m, fall_distance_m, peak_force_kn, ...]
#[pyfunction]
pub fn sweep_climber_height(
    mass_kg:            f64,
    belay_height_m:     f64,
    last_pro_height_m:  f64,
    height_min_m:       f64,
    height_max_m:       f64,
    steps:              usize,
    stiffness_kn:       f64,
    belay_friction:     f64,
) -> PyResult<Vec<f64>> {
    if steps == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("steps must be > 0"));
    }

    let results: Vec<f64> = (0..steps)
        .into_par_iter()
        .flat_map_iter(|i| {
            let t = if steps > 1 { i as f64 / (steps - 1) as f64 } else { 0.5 };
            let h = height_min_m + t * (height_max_m - height_min_m);
            let fall_dist = (2.0 * (h - last_pro_height_m)).max(0.01);
            let rope_out  = (last_pro_height_m - belay_height_m).max(0.5);
            let ff        = (fall_dist / rope_out).clamp(0.0, 2.0);
            let peak_kn   = compute_impact_force_uiaa_inner(mass_kg, ff, stiffness_kn, belay_friction);
            vec![h, fall_dist, peak_kn]
        })
        .collect();

    Ok(results)
}

// ── Registration ──────────────────────────────────────────────────────────────
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(batch_sweep_fall_factors, m)?)?;
    m.add_function(wrap_pyfunction!(batch_sweep_rope_out, m)?)?;
    m.add_function(wrap_pyfunction!(parallel_force_curves, m)?)?;
    m.add_function(wrap_pyfunction!(sweep_climber_height, m)?)?;
    Ok(())
}
