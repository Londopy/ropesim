// ropesim/_rustcore/src/anchor.rs
//
// Vector force resolution for 2-D anchor systems.
//
// References:
//   Pavier (1998) "Developments in the theory of anchor systems"
//   Long (2010) "Climbing Anchors" 3rd ed., Falcon Press
//   Merchant (2007) UIAA anchor geometry analysis
//
// Unit conventions: kN, metres, degrees (converted internally to radians).

use pyo3::prelude::*;
use std::f64::consts::PI;

// ── Failure result ────────────────────────────────────────────────────────────

/// Result of a component-failure simulation.
#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct FailureResult {
    pub failed_indices: Vec<usize>,
    pub redistributed_forces: Vec<f64>,
    pub cascade_occurred: bool,
}

#[pymethods]
impl FailureResult {
    fn __repr__(&self) -> String {
        format!(
            "FailureResult(failed={:?}, cascade={})",
            self.failed_indices, self.cascade_occurred
        )
    }
}

// ── 1. General 2-D vector force resolution ───────────────────────────────────

/// Resolve load forces at each bolt given bolt positions, a total load, and
/// load direction.
///
/// Method: equate the master-point position to the weighted centroid of bolt
/// positions, then compute the load component along each sling using vector
/// projection.  For a simple 2-bolt symmetric anchor with equal sling lengths
/// this reduces to the analytic Sliding-X result.
///
/// `bolt_positions` — [(x, y), …] in metres on the cliff face
/// `sling_lengths`  — sling length from each bolt to master point (m)
/// `load_kn`        — total applied load (kN)
/// `load_angle_deg` — angle of load from straight down (positive = right)
///
/// Returns per-bolt force in kN.
#[pyfunction]
pub fn resolve_anchor_forces_2d(
    bolt_positions: Vec<(f64, f64)>,
    sling_lengths: Vec<f64>,
    load_kn: f64,
    load_angle_deg: f64,
) -> PyResult<Vec<f64>> {
    let n = bolt_positions.len();
    if n == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "bolt_positions must not be empty",
        ));
    }
    if sling_lengths.len() != n {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "sling_lengths must have the same length as bolt_positions",
        ));
    }

    let load_rad = load_angle_deg * PI / 180.0;
    // Load vector (unit vector pointing in direction of applied load)
    let load_dir = (load_rad.sin(), -load_rad.cos()); // (x, y) — y negative = downward

    // Estimate master-point position as weighted centroid of bolts
    // (weighting by inverse sling length — shorter slings pull harder)
    let total_w: f64 = sling_lengths.iter().map(|l| 1.0 / l.max(0.01)).sum();
    let mx: f64 = bolt_positions
        .iter()
        .zip(sling_lengths.iter())
        .map(|((x, _), l)| x / l.max(0.01))
        .sum::<f64>()
        / total_w;
    let my: f64 = bolt_positions
        .iter()
        .zip(sling_lengths.iter())
        .map(|((_, y), l)| y / l.max(0.01))
        .sum::<f64>()
        / total_w;

    // Vector from master point to each bolt
    let mut forces = Vec::with_capacity(n);
    let mut sum_cos: f64 = 0.0;

    // Angles of each sling leg from master point
    let angles: Vec<f64> = bolt_positions
        .iter()
        .map(|(bx, by)| {
            let dx = bx - mx;
            let dy = by - my;
            dy.atan2(dx) // angle of sling from master point
        })
        .collect();

    // Project load direction onto each sling direction, accumulate
    for &theta in &angles {
        // Cosine of angle between sling and load direction
        let sling_dir = (theta.cos(), theta.sin());
        let cos_theta = -(sling_dir.0 * load_dir.0 + sling_dir.1 * load_dir.1);
        sum_cos += cos_theta.max(0.0);
    }

    for &theta in &angles {
        let sling_dir = (theta.cos(), theta.sin());
        let cos_theta = -(sling_dir.0 * load_dir.0 + sling_dir.1 * load_dir.1).max(0.0);
        let f = if sum_cos > 1e-9 {
            load_kn * cos_theta / sum_cos
        } else {
            load_kn / n as f64
        };
        forces.push(f);
    }

    Ok(forces)
}

// ── 2. Sliding-X ─────────────────────────────────────────────────────────────

/// Sliding-X (Magic X) anchor force distribution.
///
/// Self-equalising: each bolt sees the same force regardless of horizontal load
/// shift.  Force increases with the opening angle between the two sling legs.
///
/// Formula:  F_bolt = F_load / ( 2 · cos(θ/2) )
///   where θ = angle between the two sling legs as seen from the master point.
///
/// At θ = 0°  : each bolt carries F/2  (ideal)
/// At θ = 60° : each bolt carries F/√3 ≈ 0.577·F
/// At θ = 120°: each bolt carries F    (1:1 force multiplication!)
/// At θ → 180°: → ∞  (never build such an anchor!)
///
/// Returns (bolt_a_kn, bolt_b_kn).
#[pyfunction]
pub fn sliding_x_distribution(load_kn: f64, angle_deg: f64) -> (f64, f64) {
    let theta = angle_deg.clamp(0.0, 170.0) * PI / 180.0;
    let half_cos = (theta / 2.0).cos().max(0.01);
    let f_bolt = load_kn / (2.0 * half_cos);
    (f_bolt, f_bolt) // self-equalising → equal forces on both bolts
}

// ── 3. Quad anchor ───────────────────────────────────────────────────────────

/// Quad anchor force distribution.
///
/// The Quad is pre-equalised via two limiter knots that prevent full extension.
/// Less angle-sensitive than the Sliding-X.
///
/// Model:
///   Without extension limiter: same as Sliding-X (ideal equalisation).
///   With extension limiter: caps force multiplication at θ = 60°, reducing
///   the worst-case to about 1.15·F/2 per bolt even when load shifts.
///
/// Source: Long (2010); manufacturer test data from Metolius and Petzl.
/// Returns (bolt_a_kn, bolt_b_kn).
#[pyfunction]
pub fn quad_anchor_distribution(
    load_kn: f64,
    angle_deg: f64,
    extension_limiter: bool,
) -> (f64, f64) {
    let effective_angle = if extension_limiter {
        // Limiters prevent full shift — cap effective angle at ~60°
        angle_deg.clamp(0.0, 60.0)
    } else {
        angle_deg.clamp(0.0, 170.0)
    };
    let theta = effective_angle * PI / 180.0;
    let half_cos = (theta / 2.0).cos().max(0.01);
    let f_bolt = load_kn / (2.0 * half_cos);
    (f_bolt, f_bolt) // pre-equalised → equal on both bolts
}

// ── 4. Cordelette ─────────────────────────────────────────────────────────────

/// Cordelette (non-self-equalising) anchor force distribution.
///
/// The master-point knot is set at the original load direction; when load
/// shifts, one bolt absorbs the majority of the force.
///
/// Simplified model: the bolt closest to the load direction sees proportionally
/// more force based on the angular deviation.
/// Returns per-bolt force in kN.
#[pyfunction]
pub fn cordelette_distribution(
    bolt_positions: Vec<(f64, f64)>,
    load_kn: f64,
    load_angle_deg: f64,
) -> PyResult<Vec<f64>> {
    let n = bolt_positions.len();
    if n == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "bolt_positions must not be empty",
        ));
    }

    let load_rad = load_angle_deg * PI / 180.0;
    // Centroid of bolts as approximate master-point
    let cx = bolt_positions.iter().map(|(x, _)| x).sum::<f64>() / n as f64;
    let cy = bolt_positions.iter().map(|(_, y)| y).sum::<f64>() / n as f64;

    // Weight each bolt by cos(angle between its sling and load direction)
    let weights: Vec<f64> = bolt_positions
        .iter()
        .map(|(bx, by)| {
            let dx = bx - cx;
            let dy = by - cy;
            // Angle of this sling from master point relative to load direction
            let sling_angle = dy.atan2(dx);
            let delta = (sling_angle - (load_rad - PI)).abs();
            // Closer to load direction → higher weight
            delta.cos().max(0.0).powi(2) + 0.1 // floor to avoid zero
        })
        .collect();

    let sum_w: f64 = weights.iter().sum();
    let forces: Vec<f64> = weights
        .iter()
        .map(|w| load_kn * w / sum_w)
        .collect();

    Ok(forces)
}

// ── 5. Component failure simulation ──────────────────────────────────────────

/// Simulate progressive component failure.
///
/// If any bolt force exceeds its MBS, mark it failed and redistribute its
/// load equally to remaining bolts.  Cascade until stable or all failed.
#[pyfunction]
pub fn simulate_component_failure(
    bolt_forces: Vec<f64>,
    bolt_mbs: Vec<f64>,
) -> PyResult<FailureResult> {
    let n = bolt_forces.len();
    if bolt_mbs.len() != n {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "bolt_forces and bolt_mbs must have the same length",
        ));
    }

    let mut forces = bolt_forces.clone();
    let mut failed: Vec<bool> = vec![false; n];
    let mut failed_indices: Vec<usize> = Vec::new();
    let mut cascade_occurred = false;

    // Iterative redistribution
    loop {
        let mut new_failure = false;
        for i in 0..n {
            if !failed[i] && forces[i] > bolt_mbs[i] {
                failed[i] = true;
                failed_indices.push(i);
                new_failure = true;
                if !failed_indices.is_empty() && failed_indices.len() > 1 {
                    cascade_occurred = true;
                }
            }
        }
        if !new_failure {
            break;
        }
        // Redistribute failed bolt's load to survivors
        let n_active = failed.iter().filter(|&&f| !f).count();
        if n_active == 0 {
            break; // total failure
        }
        let extra_load: f64 = failed
            .iter()
            .enumerate()
            .filter(|(_, &f)| f)
            .map(|(i, _)| {
                let excess = forces[i] - bolt_mbs[i];
                forces[i] = bolt_mbs[i]; // cap at MBS
                excess
            })
            .sum();
        let share = extra_load / n_active as f64;
        for i in 0..n {
            if !failed[i] {
                forces[i] += share;
            }
        }
    }

    if failed_indices.len() > 1 {
        cascade_occurred = true;
    }

    Ok(FailureResult {
        failed_indices,
        redistributed_forces: forces,
        cascade_occurred,
    })
}

// ── 6. Anchor load sweep ──────────────────────────────────────────────────────

/// Compute per-bolt forces across a sweep of load angles.
///
/// Returns a flat Vec<f64> of shape [steps × n_bolts] in row-major order.
/// (Python side reshapes to numpy array.)
#[pyfunction]
pub fn compute_anchor_load_sweep(
    bolt_positions: Vec<(f64, f64)>,
    load_kn: f64,
    angle_start_deg: f64,
    angle_end_deg: f64,
    steps: usize,
) -> PyResult<Vec<f64>> {
    if steps == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("steps must be > 0"));
    }
    let n = bolt_positions.len();
    let sling_lengths: Vec<f64> = vec![1.0; n]; // unit sling lengths for sweep
    let mut result = Vec::with_capacity(steps * n);

    for i in 0..steps {
        let t = if steps > 1 { i as f64 / (steps - 1) as f64 } else { 0.5 };
        let angle = angle_start_deg + t * (angle_end_deg - angle_start_deg);
        let forces = resolve_anchor_forces_2d(
            bolt_positions.clone(),
            sling_lengths.clone(),
            load_kn,
            angle,
        )?;
        result.extend(forces);
    }
    Ok(result)
}

// ── Registration helper ────────────────────────────────────────────────────────
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(resolve_anchor_forces_2d, m)?)?;
    m.add_function(wrap_pyfunction!(sliding_x_distribution, m)?)?;
    m.add_function(wrap_pyfunction!(quad_anchor_distribution, m)?)?;
    m.add_function(wrap_pyfunction!(cordelette_distribution, m)?)?;
    m.add_function(wrap_pyfunction!(simulate_component_failure, m)?)?;
    m.add_function(wrap_pyfunction!(compute_anchor_load_sweep, m)?)?;
    m.add_class::<FailureResult>()?;
    Ok(())
}
