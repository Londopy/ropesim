// ropesim/_rustcore/src/capstan.rs
//
// v4 — Capstan (rope-over-carabiner) friction along a pitch.
//
// As the rope slides over each carabiner during a catch, friction reduces the
// tension transmitted toward the belayer by the capstan equation
//
//     T_out = T_in · e^(−μ·θ)
//
// where θ is the bend angle (the change of rope direction at that piece,
// radians) and μ the rope-on-anodised-aluminium friction coefficient
// (≈ 0.1–0.3; UIAA/Petzl drop-tower work commonly uses ~0.15–0.25 for a
// loaded wire-gate; the classic top-piece "pulley effect" ratio of ~1.66
// corresponds to μ·θ ≈ 0.5 at θ = π).
//
// The load on each piece is the vector resultant of the two rope-segment
// tensions.  If the rope direction changes by θ, the two pull directions on
// the carabiner are (π − θ) apart:
//
//     |F| = √( T₁² + T₂² + 2·T₁·T₂·cos(π − θ) )
//
//   θ = π  (rope doubles back, top piece)  →  |F| = T₁ + T₂
//   θ = 0  (rope runs straight through)    →  |F| = T₁ − T₂ ≈ 0
//
// Piece order convention: index 0 is the TOP piece (climber side), the last
// index is the piece closest to the belayer.

use pyo3::prelude::*;

/// Tension ratio e^(μθ) across a single bend. θ in radians.
#[pyfunction]
pub fn capstan_tension_ratio(mu: f64, theta_rad: f64) -> f64 {
    (mu.max(0.0) * theta_rad.max(0.0)).exp()
}

/// Result of propagating a climber-side peak tension down a protected pitch.
#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct RouteFriction {
    /// Tension in each rope segment, kN. Index 0 = climber→top-piece segment;
    /// last = bottom-piece→belayer segment. Length = n_pieces + 1.
    pub segment_tensions_kn: Vec<f64>,
    /// Resultant load on each piece, kN (same order as `bend_angles_deg`).
    pub piece_loads_kn: Vec<f64>,
    /// Tension reaching the belay device, kN.
    pub belay_tension_kn: f64,
    /// Overall drag factor e^(μ·Σθ) = climber tension / belay tension.
    pub drag_factor: f64,
}

#[pymethods]
impl RouteFriction {
    fn __repr__(&self) -> String {
        format!(
            "RouteFriction(pieces={}, belay={:.2} kN, drag×{:.2})",
            self.piece_loads_kn.len(),
            self.belay_tension_kn,
            self.drag_factor
        )
    }
}

/// Propagate a climber-side tension through every carabiner on the pitch.
///
/// * `climber_tension_kn` — peak force on the climber side (e.g. from
///   `compute_impact_force_uiaa` / `compute_impact_force_nonlinear`)
/// * `bend_angles_deg`    — rope direction change at each piece, top first.
///   The top piece is typically 150–180°; a well-extended draw on a straight
///   line is close to 0–20°.
/// * `mu`                 — rope-on-carabiner friction coefficient.
#[pyfunction]
pub fn compute_route_friction(
    climber_tension_kn: f64,
    bend_angles_deg: Vec<f64>,
    mu: f64,
) -> PyResult<RouteFriction> {
    if climber_tension_kn < 0.0 || mu < 0.0 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "climber_tension_kn and mu must be >= 0",
        ));
    }
    let n = bend_angles_deg.len();
    let mut tensions = Vec::with_capacity(n + 1);
    let mut loads = Vec::with_capacity(n);

    let mut t = climber_tension_kn;
    tensions.push(t);
    for &deg in &bend_angles_deg {
        let theta = deg.clamp(0.0, 180.0).to_radians();
        let t_next = t * (-mu * theta).exp();
        // Resultant on the piece: pull directions are (π − θ) apart.
        let cos_term = (std::f64::consts::PI - theta).cos();
        let load = (t * t + t_next * t_next + 2.0 * t * t_next * cos_term)
            .max(0.0)
            .sqrt();
        loads.push(load);
        tensions.push(t_next);
        t = t_next;
    }

    let belay = t;
    let drag = if belay > 1e-12 { climber_tension_kn / belay } else { 1.0 };

    Ok(RouteFriction {
        segment_tensions_kn: tensions,
        piece_loads_kn: loads,
        belay_tension_kn: belay,
        drag_factor: drag,
    })
}

/// Effective belay-side transmission fraction for a route: the fraction of
/// climber-side force that reaches the belay device, 1/e^(μ·Σθ).
/// Drop-in replacement for the old scalar `belay_friction` guess.
#[pyfunction]
pub fn route_transmission_fraction(bend_angles_deg: Vec<f64>, mu: f64) -> f64 {
    let total_theta: f64 = bend_angles_deg
        .iter()
        .map(|d| d.clamp(0.0, 180.0).to_radians())
        .sum();
    (-mu.max(0.0) * total_theta).exp()
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RouteFriction>()?;
    m.add_function(wrap_pyfunction!(capstan_tension_ratio, m)?)?;
    m.add_function(wrap_pyfunction!(compute_route_friction, m)?)?;
    m.add_function(wrap_pyfunction!(route_transmission_fraction, m)?)?;
    Ok(())
}
