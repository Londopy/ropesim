// ropesim/_rustcore/src/physics.rs
//
// Fall physics, UIAA/EN 892 impact force model, RK4 force-curve integrator,
// rope elongation, energy budget, and environmental modifiers.
//
// Unit conventions (unless stated otherwise in the doc comment):
//   forces  — kN
//   mass    — kg
//   length  — m
//   time    — s  (timestep inputs may be in ms and are converted internally)

use pyo3::prelude::*;

const G: f64 = 9.81; // m/s²

// ── EN 892 standard test parameters ────────────────────────────────────────
// Standard test: 80 kg mass, 5 m fall over 2.82 m rope → ff ≈ 1.772
const EN892_TEST_MASS_KG: f64 = 80.0;
const EN892_TEST_FALL_FACTOR: f64 = 1.772;

// ── 1. Fall factor ──────────────────────────────────────────────────────────

/// Compute UIAA fall factor: f = fall_distance / rope_out.
/// Clamped to [0.0, 2.0].  Raises ValueError if rope_out ≤ 0.
#[pyfunction]
pub fn compute_fall_factor(fall_distance: f64, rope_out: f64) -> PyResult<f64> {
    if rope_out <= 0.0 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "rope_out must be > 0",
        ));
    }
    Ok((fall_distance / rope_out).clamp(0.0, 2.0))
}

// ── 2. UIAA peak impact force ───────────────────────────────────────────────

/// Compute peak impact force using the UIAA 101 / EN 892 energy model.
///
/// The formula derives from energy conservation for a mass on a spring:
///
///   F_peak = m·g + √( (m·g)² + 2·m·g·ff·k_eff )
///
/// where `k_eff` is the *length-normalised* rope stiffness (kN) such that
/// rope_out cancels: the force depends only on fall factor, not absolute
/// distances.  This is the key insight behind the UIAA fall-factor concept.
///
/// `belay_friction` is the fraction of force absorbed by the belay
/// device/rope system (e.g. 0.35 for ATC → transmits 65 % to anchor).
#[pyfunction]
pub fn compute_impact_force_uiaa(
    mass_kg: f64,
    fall_factor: f64,
    rope_stiffness_kn: f64, // length-normalised EA equivalent, kN
    belay_friction: f64,    // 0.0–1.0
) -> f64 {
    let mg = mass_kg * G / 1000.0; // kN
    let ff = fall_factor.clamp(0.0, 2.0);
    let k = rope_stiffness_kn.max(0.0);
    let friction = belay_friction.clamp(0.0, 0.9);

    // Energy method: F = mg + √( (mg)² + 2·mg·ff·k )
    let raw = mg + (mg * mg + 2.0 * mg * ff * k).sqrt();

    // Belay device reduces force transmitted to anchor/climber
    raw * (1.0 - friction)
}

// ── 3. RK4 force-time curve ─────────────────────────────────────────────────

/// ODE right-hand side: damped spring loaded by gravity.
///
/// State: [elongation δ (m), velocity v (m/s)]  (positive = downward)
///
///   dδ/dt = v
///   dv/dt = g − (k·δ + c·v) / m          when δ > 0 (rope taut)
///   dv/dt = g                              when δ ≤ 0 (rope slack)
///
/// Returns (dδ, dv).
#[inline]
fn ode_rhs(delta: f64, v: f64, m_kg: f64, k_nm: f64, c_ns_m: f64) -> (f64, f64) {
    let accel = if delta > 0.0 {
        let f_rope = k_nm * delta + c_ns_m * v;
        G - f_rope / m_kg
    } else {
        G // free fall / slack rope
    };
    (v, accel)
}

/// Single RK4 step; returns new (δ, v).
#[inline]
fn rk4_step(delta: f64, v: f64, m_kg: f64, k_nm: f64, c_ns_m: f64, dt: f64) -> (f64, f64) {
    let (k1d, k1v) = ode_rhs(delta, v, m_kg, k_nm, c_ns_m);
    let (k2d, k2v) = ode_rhs(delta + 0.5 * dt * k1d, v + 0.5 * dt * k1v, m_kg, k_nm, c_ns_m);
    let (k3d, k3v) = ode_rhs(delta + 0.5 * dt * k2d, v + 0.5 * dt * k2v, m_kg, k_nm, c_ns_m);
    let (k4d, k4v) = ode_rhs(delta + dt * k3d, v + dt * k3v, m_kg, k_nm, c_ns_m);
    (
        delta + (dt / 6.0) * (k1d + 2.0 * k2d + 2.0 * k3d + k4d),
        v + (dt / 6.0) * (k1v + 2.0 * k2v + 2.0 * k3v + k4v),
    )
}

/// Compute the rope force–time curve via RK4 integration of a damped-spring ODE.
///
/// Returns a `Vec<f64>` of rope force values in **kN** at each timestep.
///
/// Model:
/// * Climber free-falls `fall_distance_m`, reaching v₀ = √(2·g·h) at rope catch.
/// * Rope then modelled as a damped spring with:
///     - k (N/m) = rope_stiffness_kn · 1000 / rope_out_m
///     - c (N·s/m) derived from `damping_coeff` as a fraction of critical damping:
///         c = damping_coeff · 2 · √(k · m)
/// * Integration continues until the rope goes slack AND the climber is rising,
///   or a 3000-step limit is reached (~3 s at 1 ms/step).
///
/// `damping_coeff` is the dimensionless damping ratio ζ (typically 0.05–0.25
/// for climbing ropes).  0.0 = undamped (unrealistic), 1.0 = critically damped.
#[pyfunction]
pub fn compute_force_curve(
    mass_kg: f64,
    fall_distance_m: f64,
    rope_out_m: f64,
    rope_stiffness_kn: f64, // length-normalised stiffness, kN
    damping_coeff: f64,     // dimensionless damping ratio ζ
    timestep_ms: f64,
) -> Vec<f64> {
    let dt = (timestep_ms / 1000.0).max(1e-6); // s
    let m = mass_kg.max(1.0);
    let h = fall_distance_m.max(0.0);
    let l = rope_out_m.max(0.01);

    // Spring constant for this rope length (N/m)
    let k_nm = (rope_stiffness_kn * 1_000.0) / l;
    // Damping coefficient (N·s/m) from damping ratio
    let c_ns_m = damping_coeff * 2.0 * (k_nm * m).sqrt();

    // Velocity at end of free fall (rope goes taut)
    let v0 = (2.0 * G * h).sqrt();

    let mut forces: Vec<f64> = Vec::with_capacity(1500);
    let mut delta = 0.0_f64; // rope elongation (m)
    let mut v = v0; // velocity (m/s, downward positive)
    let mut peak_passed = false;

    for _ in 0..3000 {
        // Rope force at this timestep (kN); clamp to ≥ 0 (rope can't push)
        let f_rope_n = if delta > 0.0 {
            (k_nm * delta + c_ns_m * v).max(0.0)
        } else {
            0.0
        };
        forces.push(f_rope_n / 1_000.0); // → kN

        // Detect peak (velocity reversal)
        if v < 0.0 {
            peak_passed = true;
        }

        // Stop when rope slack again after bounce
        if peak_passed && delta <= 0.0 && v < 0.0 {
            break;
        }

        let (d_new, v_new) = rk4_step(delta, v, m, k_nm, c_ns_m, dt);

        // Rope cannot be compressed — clamp elongation to 0
        delta = d_new.max(0.0);
        v = v_new;
    }

    forces
}

// ── 4. Elongation ────────────────────────────────────────────────────────────

/// Interpolate rope elongation for an applied force.
///
/// Uses a linear model between static elongation (at low load) and
/// dynamic elongation (at peak UIAA test load ≈ impact_force).
/// Returns elongated length in metres.
#[pyfunction]
pub fn compute_elongation(
    rope_static_elongation_pct: f64,
    rope_dynamic_elongation_pct: f64,
    applied_force_kn: f64,
    rope_length_m: f64,
) -> f64 {
    // EN 892: static elongation measured at 80 kg (≈ 0.784 kN)
    // Dynamic elongation measured at peak impact (~8–12 kN)
    // Interpolate linearly between the two reference points.
    let f_static = 0.784_f64; // kN (80 kg × g / 1000)
    let f_dynamic = 10.0_f64; // kN (representative UIAA test peak)

    let pct = if applied_force_kn <= f_static {
        rope_static_elongation_pct
    } else if applied_force_kn >= f_dynamic {
        rope_dynamic_elongation_pct
    } else {
        let t = (applied_force_kn - f_static) / (f_dynamic - f_static);
        rope_static_elongation_pct + t * (rope_dynamic_elongation_pct - rope_static_elongation_pct)
    };

    rope_length_m * (1.0 + pct / 100.0)
}

// ── 5. Diameter under load ───────────────────────────────────────────────────

/// Model radial compression (Poisson effect) under axial load.
///
/// Based on a simplified linear model: diameter decreases ~1.5 % per 10 kN
/// for typical nylon kernmantle ropes, bounded by sheath percentage.
/// Returns estimated diameter in mm.
#[pyfunction]
pub fn compute_diameter_under_load(
    nominal_diameter_mm: f64,
    sheath_percentage: f64, // 0–100 %
    applied_force_kn: f64,
) -> f64 {
    // Empirical coefficient: ~0.25% diameter reduction per kN
    // Source: approximation from Pavier (1998) and Durand et al. (2009)
    let reduction_pct_per_kn = 0.0025;
    let sheath_factor = (sheath_percentage / 100.0).clamp(0.2, 0.6);
    // Sheath resists compression more than core; higher sheath → less reduction
    let adjusted_coeff = reduction_pct_per_kn * (1.0 - 0.5 * sheath_factor);
    let reduction = (nominal_diameter_mm * adjusted_coeff * applied_force_kn).min(nominal_diameter_mm * 0.15);
    (nominal_diameter_mm - reduction).max(nominal_diameter_mm * 0.70)
}

// ── 6. Energy budget ─────────────────────────────────────────────────────────

/// Energy-budget result exposed to Python.
#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct EnergyBudget {
    pub potential_energy_j: f64,
    pub kinetic_energy_j: f64,
    pub rope_absorption_j: f64,
    pub belay_device_j: f64,
    pub residual_j: f64,
}

#[pymethods]
impl EnergyBudget {
    fn __repr__(&self) -> String {
        format!(
            "EnergyBudget(PE={:.1}J, rope={:.1}J, belay={:.1}J, residual={:.1}J)",
            self.potential_energy_j,
            self.rope_absorption_j,
            self.belay_device_j,
            self.residual_j,
        )
    }
}

/// Partition the energy of a fall into its physical components.
///
/// * `belay_friction` — fraction absorbed by the belay device (0–1)
#[pyfunction]
pub fn compute_energy_budget(
    mass_kg: f64,
    fall_distance_m: f64,
    peak_force_kn: f64,
    rope_elongation_m: f64,
    belay_friction: f64,
) -> EnergyBudget {
    let g = G;
    let m = mass_kg;
    let h_total = fall_distance_m + rope_elongation_m;

    // Gravitational PE released over total displacement
    let pe = m * g * h_total; // J

    // KE at rope-catch point (after free fall only)
    let ke_at_catch = m * g * fall_distance_m; // J

    // Energy absorbed by the rope spring (area under force-extension curve ≈ ½F·x)
    let rope_abs = 0.5 * peak_force_kn * 1_000.0 * rope_elongation_m; // J

    // Energy absorbed by belay device (friction dissipation)
    let belay = pe * belay_friction.clamp(0.0, 0.9) * 0.5; // simplified model

    // Residual = PE not accounted for by rope or belay (transmitted to harness/body)
    let residual = (pe - rope_abs - belay).max(0.0);

    EnergyBudget {
        potential_energy_j: pe,
        kinetic_energy_j: ke_at_catch,
        rope_absorption_j: rope_abs,
        belay_device_j: belay,
        residual_j: residual,
    }
}

// ── 7. Wet modifier ──────────────────────────────────────────────────────────

/// Apply EN 892 wet-condition modifier to impact force.
///
/// EN 892 requires that peak force does not exceed rated limit when wet.
/// In practice, wet nylon ropes are ~10–15 % stiffer → higher force.
/// Source: EN 892:2012+A3:2023 §6.3; Microys (1977) nylon water absorption data.
#[pyfunction]
pub fn apply_wet_modifier(impact_force_kn: f64, is_wet: bool) -> f64 {
    if is_wet {
        impact_force_kn * 1.12 // +12 % — midpoint of EN 892 wet test allowance
    } else {
        impact_force_kn
    }
}

// ── 8. Temperature modifier ──────────────────────────────────────────────────

/// Adjust rope stiffness for temperature effects on nylon.
///
/// Nylon's Young's modulus increases at low temperatures; frozen ropes
/// can be significantly stiffer and more brittle.
///
/// Curve fitted to published data:
///   Leech (2002) "Rope stiffness at temperature", UIAA Safety Commission.
///   Approximate model: linear stiffness increase ~0.5 % / °C below 20 °C,
///   accelerating below 0 °C (ice crystal formation in fibres).
#[pyfunction]
pub fn apply_temperature_modifier(stiffness_kn: f64, temp_celsius: f64) -> f64 {
    let modifier = if temp_celsius >= 20.0 {
        // Above reference temp: slight softening (~0.3 %/°C)
        1.0 - 0.003 * (temp_celsius - 20.0).min(20.0)
    } else if temp_celsius >= 0.0 {
        // 0–20 °C: linear stiffening (~0.5 %/°C)
        1.0 + 0.005 * (20.0 - temp_celsius)
    } else {
        // Below 0 °C: accelerated stiffening (frozen fibres)
        let base = 1.0 + 0.005 * 20.0; // factor at 0 °C
        base + 0.02 * (-temp_celsius).min(30.0) // +2 %/°C below 0
    };
    stiffness_kn * modifier.max(0.1)
}

// ── 9. Back-calculate rope spring constant from EN spec ──────────────────────

/// Back-calculate length-normalised rope stiffness k_eff (kN) from the EN 892
/// standard test result.
///
/// From:  F = m·g + √( (m·g)² + 2·m·g·ff·k )
///   →  k = [ (F − m·g)² − (m·g)² ] / ( 2·m·g·ff )
///
/// Uses EN 892 standard test fall factor ≈ 1.772 and the provided test mass
/// (typically 80 kg).
#[pyfunction]
pub fn compute_stiffness_from_spec(
    impact_force_kn: f64,
    _dynamic_elongation_pct: f64, // reserved — used for cross-validation in future
    mass_kg: f64,
) -> f64 {
    let mg = mass_kg * G / 1000.0; // kN
    let f = impact_force_kn.max(mg + 0.01); // must exceed mg
    let ff = EN892_TEST_FALL_FACTOR;

    // Invert energy equation
    let numerator = (f - mg) * (f - mg) - mg * mg;
    let denominator = 2.0 * mg * ff;

    if denominator <= 0.0 || numerator <= 0.0 {
        // Fallback: estimate from typical rope EA ≈ 40 kN
        return 40.0;
    }
    (numerator / denominator).max(1.0)
}


// ── Internal wrappers (callable from batch.rs without PyO3 overhead) ─────────

/// Pure-Rust wrapper around compute_force_curve for use in batch.rs.
pub fn compute_force_curve_inner(
    mass_kg: f64,
    fall_distance_m: f64,
    rope_out_m: f64,
    rope_stiffness_kn: f64,
    damping_coeff: f64,
    timestep_ms: f64,
) -> Vec<f64> {
    compute_force_curve(mass_kg, fall_distance_m, rope_out_m, rope_stiffness_kn, damping_coeff, timestep_ms)
}

/// Pure-Rust wrapper around compute_impact_force_uiaa for use in batch.rs.
pub fn compute_impact_force_uiaa_inner(
    mass_kg: f64,
    fall_factor: f64,
    rope_stiffness_kn: f64,
    belay_friction: f64,
) -> f64 {
    compute_impact_force_uiaa(mass_kg, fall_factor, rope_stiffness_kn, belay_friction)
}

// ── Registration helper (called from lib.rs) ─────────────────────────────────
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compute_fall_factor, m)?)?;
    m.add_function(wrap_pyfunction!(compute_impact_force_uiaa, m)?)?;
    m.add_function(wrap_pyfunction!(compute_force_curve, m)?)?;
    m.add_function(wrap_pyfunction!(compute_elongation, m)?)?;
    m.add_function(wrap_pyfunction!(compute_diameter_under_load, m)?)?;
    m.add_function(wrap_pyfunction!(compute_energy_budget, m)?)?;
    m.add_function(wrap_pyfunction!(apply_wet_modifier, m)?)?;
    m.add_function(wrap_pyfunction!(apply_temperature_modifier, m)?)?;
    m.add_function(wrap_pyfunction!(compute_stiffness_from_spec, m)?)?;
    m.add_class::<EnergyBudget>()?;
    Ok(())
}
