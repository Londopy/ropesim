// ropesim/_rustcore/src/nonlinear.rs
//
// v4 — Nonlinear rope model.
//
// Replaces the single-parameter linear spring with a cubic force–strain law
//
//     F(ε) = a·ε + b·ε³        (F in kN, ε = δ / L dimensionless strain)
//
// calibrated against BOTH published EN 892 numbers for a rope:
//
//   * rated impact force  F*  (kN, 80 kg, ff 1.772)
//   * dynamic elongation  ε*  (fraction, at the same test)
//
// Two conditions pin down the two coefficients exactly:
//
//   force match :  a·ε* + b·ε*³                  = F*
//   energy match:  a·ε*²/2 + b·ε*⁴/4             = m·g·(ff + ε*)   [= E*]
//
// Solving the 2×2 linear system:
//
//   a = (4·E* − F*·ε*) / ε*²
//   b = (2·F*·ε* − 4·E*) / ε*⁴
//
// For real rope specs `b` is usually negative (the true force–strain curve is
// concave: stiff initially, yielding near peak — nylon plasticity), so the
// cubic is only trusted up to the calibration strain ε*.  Beyond ε* the model
// extends linearly along the tangent at ε*, keeping force monotone increasing.
//
// The energy match implicitly lumps viscous dissipation into the effective
// elastic curve — appropriate because the calibration target (rated impact
// force) is itself the *measured* peak of a damped first drop.

use pyo3::prelude::*;

const G: f64 = 9.81;
const EN892_TEST_FALL_FACTOR: f64 = 1.772;
const MIN_TANGENT_KN: f64 = 1.0; // floor on extension slope (kN per unit strain)

/// Calibrated nonlinear rope. Construct via `calibrate_nonlinear_rope`.
#[pyclass(get_all)]
#[derive(Clone, Copy, Debug)]
pub struct NonlinearRope {
    /// Linear coefficient a (kN per unit strain)
    pub a_kn: f64,
    /// Cubic coefficient b (kN per unit strain³)
    pub b_kn: f64,
    /// Calibration strain ε* (dynamic elongation as a fraction)
    pub eps_star: f64,
    /// Tangent stiffness at ε* used for linear extension (kN per unit strain)
    pub tangent_kn: f64,
}

impl NonlinearRope {
    /// Force (kN) at strain ε.  Cubic below ε*, tangent extension above.
    pub fn force_kn(&self, eps: f64) -> f64 {
        if eps <= 0.0 {
            0.0
        } else if eps <= self.eps_star {
            self.a_kn * eps + self.b_kn * eps * eps * eps
        } else {
            let f_star = self.a_kn * self.eps_star + self.b_kn * self.eps_star.powi(3);
            f_star + self.tangent_kn * (eps - self.eps_star)
        }
    }

    /// Stored elastic energy per unit rope length (kN·strain ≡ kJ/m per kN…)
    /// U(ε) = ∫₀^ε F dε.  Units: kN (multiply by rope length in m for Joules·10³).
    pub fn energy_kn(&self, eps: f64) -> f64 {
        if eps <= 0.0 {
            return 0.0;
        }
        let e = eps.min(self.eps_star);
        let mut u = self.a_kn * e * e / 2.0 + self.b_kn * e.powi(4) / 4.0;
        if eps > self.eps_star {
            let f_star = self.a_kn * self.eps_star + self.b_kn * self.eps_star.powi(3);
            let d = eps - self.eps_star;
            u += f_star * d + 0.5 * self.tangent_kn * d * d;
        }
        u
    }

    /// Tangent stiffness dF/dε (kN) at strain ε — used for damping scaling.
    pub fn stiffness_kn(&self, eps: f64) -> f64 {
        if eps <= 0.0 {
            self.a_kn
        } else if eps <= self.eps_star {
            (self.a_kn + 3.0 * self.b_kn * eps * eps).max(MIN_TANGENT_KN)
        } else {
            self.tangent_kn
        }
    }
}

#[pymethods]
impl NonlinearRope {
    /// Force (kN) at strain ε (Python-visible).
    fn force_at_strain(&self, eps: f64) -> f64 {
        self.force_kn(eps)
    }

    fn __repr__(&self) -> String {
        format!(
            "NonlinearRope(a={:.2} kN, b={:.2} kN, eps*={:.3}, tangent={:.2} kN)",
            self.a_kn, self.b_kn, self.eps_star, self.tangent_kn
        )
    }
}

/// Calibrate the cubic force–strain law from a rope's published EN 892 spec.
///
/// * `impact_force_kn`        — rated impact force F* (first drop, 80 kg, ff 1.772)
/// * `dynamic_elongation_pct` — dynamic elongation at the same test (e.g. 33.0)
/// * `mass_kg`                — test mass (80.0 for single ropes, 55.0 half)
#[pyfunction]
pub fn calibrate_nonlinear_rope(
    impact_force_kn: f64,
    dynamic_elongation_pct: f64,
    mass_kg: f64,
) -> PyResult<NonlinearRope> {
    if impact_force_kn <= 0.0 || !(1.0..=60.0).contains(&dynamic_elongation_pct) || mass_kg <= 0.0 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "impact_force_kn > 0, 1 <= dynamic_elongation_pct <= 60, mass_kg > 0 required",
        ));
    }
    let mg = mass_kg * G / 1000.0; // kN
    let ff = EN892_TEST_FALL_FACTOR;
    let eps = dynamic_elongation_pct / 100.0;
    let f_star = impact_force_kn;
    let e_star = mg * (ff + eps); // energy per unit rope length, kN

    let a = (4.0 * e_star - f_star * eps) / (eps * eps);
    let b = (2.0 * f_star * eps - 4.0 * e_star) / eps.powi(4);

    if a <= 0.0 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "spec inconsistent: derived initial stiffness non-positive",
        ));
    }

    // Tangent at eps* for the linear extension; floored to stay monotone.
    let tangent = (a + 3.0 * b * eps * eps).max(MIN_TANGENT_KN);

    Ok(NonlinearRope { a_kn: a, b_kn: b, eps_star: eps, tangent_kn: tangent })
}

/// Peak impact force (kN) for the nonlinear rope via the energy balance
/// `m·g·(ff + ε_pk) = U(ε_pk)`,
/// solved by bisection (U − mg·(ff+ε) is monotone increasing past ε=0 root).
/// `belay_friction` mirrors the linear model: fraction of force NOT
/// transmitted (0.0–0.9).
#[pyfunction]
pub fn compute_impact_force_nonlinear(
    mass_kg: f64,
    fall_factor: f64,
    rope: NonlinearRope,
    belay_friction: f64,
) -> f64 {
    let mg = mass_kg * G / 1000.0;
    let ff = fall_factor.clamp(0.0, 2.0);
    let friction = belay_friction.clamp(0.0, 0.9);

    // g(ε) = U(ε) − mg(ff + ε): negative at 0⁺ (for ff>0), grows without bound.
    let g = |e: f64| rope.energy_kn(e) - mg * (ff + e);

    let mut lo = 1e-9;
    let mut hi = rope.eps_star.max(0.1);
    while g(hi) < 0.0 {
        hi *= 2.0;
        if hi > 100.0 {
            return f64::NAN; // spec so soft the fall never arrests (unphysical inputs)
        }
    }
    for _ in 0..200 {
        let mid = 0.5 * (lo + hi);
        if g(mid) < 0.0 {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    rope.force_kn(0.5 * (lo + hi)) * (1.0 - friction)
}

/// RK4 force–time curve for the nonlinear rope (kN per timestep).
/// Same integration scheme and stopping rules as the linear
/// `compute_force_curve`, with the spring term replaced by F(δ/L).
#[pyfunction]
pub fn compute_force_curve_nonlinear(
    mass_kg: f64,
    fall_distance_m: f64,
    rope_out_m: f64,
    rope: NonlinearRope,
    damping_coeff: f64, // dimensionless damping ratio ζ
    timestep_ms: f64,
) -> Vec<f64> {
    let dt = (timestep_ms / 1000.0).max(1e-6);
    let m = mass_kg.max(1.0);
    let h = fall_distance_m.max(0.0);
    let l = rope_out_m.max(0.01);

    // Damping from ζ against the *initial* tangent stiffness.
    let k0_nm = rope.a_kn * 1000.0 / l;
    let c_ns_m = damping_coeff * 2.0 * (k0_nm * m).sqrt();

    // Rope force in N at elongation delta (m) and velocity v (m/s).
    let rope_force_n = |delta: f64, v: f64| -> f64 {
        if delta <= 0.0 {
            0.0
        } else {
            (rope.force_kn(delta / l) * 1000.0 + c_ns_m * v).max(0.0)
        }
    };
    let rhs = |delta: f64, v: f64| -> (f64, f64) {
        (v, G - rope_force_n(delta, v) / m)
    };

    let v0 = (2.0 * G * h).sqrt();
    let mut forces: Vec<f64> = Vec::with_capacity(1500);
    let mut delta = 0.0_f64;
    let mut v = v0;
    let mut peak_passed = false;

    const MAX_SIM_TIME_S: f64 = 3.0;
    let max_steps = ((MAX_SIM_TIME_S / dt).ceil() as usize).clamp(3000, 3_000_000);

    for _ in 0..max_steps {
        forces.push(rope_force_n(delta, v) / 1000.0);

        if v < 0.0 {
            peak_passed = true;
        }
        if peak_passed && delta <= 0.0 && v < 0.0 {
            break;
        }

        let (k1d, k1v) = rhs(delta, v);
        let (k2d, k2v) = rhs(delta + 0.5 * dt * k1d, v + 0.5 * dt * k1v);
        let (k3d, k3v) = rhs(delta + 0.5 * dt * k2d, v + 0.5 * dt * k2v);
        let (k4d, k4v) = rhs(delta + dt * k3d, v + dt * k3v);
        delta = (delta + (dt / 6.0) * (k1d + 2.0 * k2d + 2.0 * k3d + k4d)).max(0.0);
        v += (dt / 6.0) * (k1v + 2.0 * k2v + 2.0 * k3v + k4v);
    }

    forces
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<NonlinearRope>()?;
    m.add_function(wrap_pyfunction!(calibrate_nonlinear_rope, m)?)?;
    m.add_function(wrap_pyfunction!(compute_impact_force_nonlinear, m)?)?;
    m.add_function(wrap_pyfunction!(compute_force_curve_nonlinear, m)?)?;
    Ok(())
}
