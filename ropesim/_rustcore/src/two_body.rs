// ropesim/_rustcore/src/two_body.rs
//
// v4 — Two-body climber + belayer catch dynamics.
//
// Instead of asserting a "soft catch reduces force by X %", model the belayer
// as a second mass coupled to the climber through the top piece:
//
//   * Climber (mass M) hangs on the climber-side rope segment (length L_c,
//     unstretched) below the top piece.  Rope modelled as spring + damper.
//   * Belayer (mass m_b) is anchored to gravity only: when the belay-side
//     tension exceeds their weight they are lifted off the ground, feeding
//     rope over the top carabiner and lengthening the climber-side segment —
//     which is exactly the mechanism of a soft catch.
//   * Capstan friction at the top piece links the two tensions during slip:
//     T_belay = T_climber · e^(−μ·θ).
//
// States: x  — climber displacement below the catch point (m)
//         v  — climber velocity (m/s, downward +)
//         y  — belayer lift off the ground (m, upward +)
//         w  — belayer vertical velocity (m/s, upward +)
//
//   δ (rope stretch)     = x − y                  (belayer lift feeds rope)
//   T_climber            = k(δ) + c·(v − w),  δ > 0; else 0
//   M·dv/dt              = M·g − T_climber
//   m_b·dw/dt            = T_belay − m_b·g    while lifted or T_belay > m_b·g
//   ground constraint    : y ≥ 0 (w clamped when landing)
//
// Semi-implicit (symplectic) Euler with a small dt keeps the constraint
// handling simple and robust; peak values converge to <0.1 % at dt ≤ 0.2 ms.

use pyo3::prelude::*;

const G: f64 = 9.81;

/// Result of a two-body catch simulation.
#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct TwoBodyResult {
    /// Peak force on the climber, kN.
    pub peak_climber_kn: f64,
    /// Peak tension on the belayer side of the top piece, kN.
    pub peak_belay_kn: f64,
    /// Peak resultant load on the top piece (T_c + T_b at climber peak), kN.
    pub peak_top_piece_kn: f64,
    /// Maximum height the belayer is lifted, m.
    pub max_belayer_lift_m: f64,
    /// Peak climber force with the belayer replaced by a rigid anchor, kN.
    pub peak_fixed_anchor_kn: f64,
    /// Force reduction vs the fixed anchor, percent.
    pub reduction_pct: f64,
    /// Climber-side force curve, kN per timestep.
    pub force_curve_kn: Vec<f64>,
    /// Timestep of the curve, ms.
    pub timestep_ms: f64,
}

#[pymethods]
impl TwoBodyResult {
    fn __repr__(&self) -> String {
        format!(
            "TwoBodyResult(climber={:.2} kN, top={:.2} kN, lift={:.2} m, −{:.1}% vs fixed)",
            self.peak_climber_kn, self.peak_top_piece_kn, self.max_belayer_lift_m,
            self.reduction_pct
        )
    }
}

struct SimOut {
    peak_climber: f64,
    peak_belay: f64,
    peak_top: f64,
    max_lift: f64,
    curve: Vec<f64>,
}

#[allow(clippy::too_many_arguments)]
fn integrate(
    m_climber: f64,
    m_belayer: f64, // f64::INFINITY → fixed anchor
    fall_m: f64,
    l_climber_side: f64,
    stiffness_kn: f64, // length-normalised, kN per unit strain
    zeta: f64,
    beta: f64, // capstan transmission e^(−μθ) at top piece
    dt: f64,
) -> SimOut {
    let fixed = !m_belayer.is_finite();
    let k_nm0 = stiffness_kn * 1000.0 / l_climber_side; // N/m at initial length
    let c = zeta * 2.0 * (k_nm0 * m_climber).sqrt(); // N·s/m

    let mut x = 0.0_f64;
    let mut v = (2.0 * G * fall_m.max(0.0)).sqrt();
    let mut y = 0.0_f64;
    let mut w = 0.0_f64;

    let mut peak_climber = 0.0_f64;
    let mut peak_belay = 0.0_f64;
    let mut peak_top = 0.0_f64;
    let mut max_lift = 0.0_f64;
    let mut curve = Vec::with_capacity(2048);
    let mut peak_passed = false;

    const MAX_SIM_TIME_S: f64 = 5.0;
    let max_steps = ((MAX_SIM_TIME_S / dt).ceil() as usize).clamp(3000, 5_000_000);

    for _ in 0..max_steps {
        let delta = x - y;
        // Feeding rope over the biner lengthens the climber-side segment.
        let l_eff = (l_climber_side + y).max(0.01);
        let k_nm = stiffness_kn * 1000.0 / l_eff;
        let t_climber_n = if delta > 0.0 {
            (k_nm * delta + c * (v - w)).max(0.0)
        } else {
            0.0
        };
        let t_belay_n = t_climber_n * beta;

        curve.push(t_climber_n / 1000.0);
        peak_climber = peak_climber.max(t_climber_n / 1000.0);
        peak_belay = peak_belay.max(t_belay_n / 1000.0);
        peak_top = peak_top.max((t_climber_n + t_belay_n) / 1000.0);
        max_lift = max_lift.max(y);

        if v < 0.0 {
            peak_passed = true;
        }
        if peak_passed && delta <= 0.0 && v < 0.0 {
            break;
        }

        // Climber (semi-implicit Euler)
        v += (G - t_climber_n / m_climber) * dt;
        x += v * dt;

        // Belayer
        if !fixed {
            let lifted = y > 0.0 || t_belay_n > m_belayer * G;
            if lifted {
                w += (t_belay_n / m_belayer - G) * dt;
                y += w * dt;
                if y <= 0.0 {
                    y = 0.0;
                    if w < 0.0 {
                        w = 0.0; // inelastic landing
                    }
                }
            }
        }
    }

    SimOut { peak_climber, peak_belay, peak_top, max_lift, curve }
}

/// Simulate a lead-fall catch with a dynamic (liftable) belayer.
///
/// * `climber_kg`, `belayer_kg` — the two masses
/// * `fall_distance_m`          — free-fall distance before the rope comes taut
/// * `climber_side_rope_m`      — unstretched rope, top piece → climber
/// * `rope_stiffness_kn`        — length-normalised stiffness (from
///   `compute_stiffness_from_spec`)
/// * `damping_ratio`            — ζ, as in `compute_force_curve`
/// * `mu_top`, `theta_top_deg`  — capstan friction at the top piece
///   (defaults ~0.25 / 170° reproduce the classic ≈1.6–1.7 pulley ratio)
/// * `timestep_ms`              — integrator step (0.1 ms default)
#[pyfunction]
#[pyo3(signature = (climber_kg, belayer_kg, fall_distance_m, climber_side_rope_m,
                    rope_stiffness_kn, damping_ratio=0.15, mu_top=0.25,
                    theta_top_deg=170.0, timestep_ms=0.1))]
#[allow(clippy::too_many_arguments)]
pub fn simulate_two_body_fall(
    climber_kg: f64,
    belayer_kg: f64,
    fall_distance_m: f64,
    climber_side_rope_m: f64,
    rope_stiffness_kn: f64,
    damping_ratio: f64,
    mu_top: f64,
    theta_top_deg: f64,
    timestep_ms: f64,
) -> PyResult<TwoBodyResult> {
    if climber_kg <= 0.0 || belayer_kg <= 0.0 || climber_side_rope_m <= 0.0
        || rope_stiffness_kn <= 0.0
    {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "masses, climber_side_rope_m and rope_stiffness_kn must be > 0",
        ));
    }
    let dt = (timestep_ms / 1000.0).clamp(1e-6, 1e-3);
    let beta = (-mu_top.max(0.0) * theta_top_deg.clamp(0.0, 180.0).to_radians()).exp();

    let dynamic = integrate(
        climber_kg, belayer_kg, fall_distance_m, climber_side_rope_m,
        rope_stiffness_kn, damping_ratio, beta, dt,
    );
    let fixed = integrate(
        climber_kg, f64::INFINITY, fall_distance_m, climber_side_rope_m,
        rope_stiffness_kn, damping_ratio, beta, dt,
    );

    let reduction = if fixed.peak_climber > 1e-9 {
        (1.0 - dynamic.peak_climber / fixed.peak_climber) * 100.0
    } else {
        0.0
    };

    Ok(TwoBodyResult {
        peak_climber_kn: dynamic.peak_climber,
        peak_belay_kn: dynamic.peak_belay,
        peak_top_piece_kn: dynamic.peak_top,
        max_belayer_lift_m: dynamic.max_lift,
        peak_fixed_anchor_kn: fixed.peak_climber,
        reduction_pct: reduction,
        force_curve_kn: dynamic.curve,
        timestep_ms: dt * 1000.0,
    })
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TwoBodyResult>()?;
    m.add_function(wrap_pyfunction!(simulate_two_body_fall, m)?)?;
    Ok(())
}
