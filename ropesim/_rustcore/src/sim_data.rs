// ropesim/_rustcore/src/sim_data.rs
// SimFrameData -- collected output from a full Rapier simulation run.

use pyo3::prelude::*;

#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct FailureEvent {
    pub gear_index: usize,
    pub timestamp_ms: f64,
    pub force_kn: f64,
    pub mbs_kn: f64,
}

#[pymethods]
impl FailureEvent {
    fn __repr__(&self) -> String {
        format!(
            "FailureEvent(gear={}, t={:.1}ms, force={:.2}kN, mbs={:.2}kN)",
            self.gear_index, self.timestamp_ms, self.force_kn, self.mbs_kn
        )
    }
}

#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct SimFrame {
    pub timestamp_ms: f64,
    pub rope_positions: Vec<[f64; 3]>,
    pub climber_position: [f64; 3],
    pub climber_velocity: [f64; 3],
    pub anchor_force_kn: f64,
    pub per_gear_forces: Vec<f64>,
    pub failures: Vec<FailureEvent>,
}

#[pymethods]
impl SimFrame {
    fn __repr__(&self) -> String {
        format!(
            "SimFrame(t={:.1}ms, anchor={:.2}kN, failures={})",
            self.timestamp_ms, self.anchor_force_kn, self.failures.len()
        )
    }
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct SimFrameData {
    #[pyo3(get)]
    pub frames: Vec<SimFrame>,
    #[pyo3(get)]
    pub dt_seconds: f64,
    #[pyo3(get)]
    pub total_time_seconds: f64,
}

#[pymethods]
impl SimFrameData {
    pub fn peak_anchor_force(&self) -> f64 {
        self.frames.iter().map(|f| f.anchor_force_kn).fold(0.0_f64, f64::max)
    }

    pub fn force_curve_numpy(&self) -> Vec<f64> {
        self.frames.iter().map(|f| f.anchor_force_kn).collect()
    }

    pub fn peak_deceleration_g(&self) -> f64 {
        self.peak_anchor_force() * 1000.0 / (80.0 * 9.81)
    }

    pub fn to_json(&self) -> String {
        let frames_json: Vec<String> = self.frames.iter().map(|f| {
            let rope_json: Vec<String> = f.rope_positions.iter()
                .map(|p| format!("[{},{},{}]", p[0], p[1], p[2]))
                .collect();
            let gear_json: Vec<String> = f.per_gear_forces.iter()
                .map(|v| format!("{:.4}", v))
                .collect();
            format!(
                "{{\"t\":{:.3},\"anchor_kn\":{:.4},\"climber\":[{},{},{}],\"rope\":[{}],\"gear\":[{}]}}",
                f.timestamp_ms,
                f.anchor_force_kn,
                f.climber_position[0], f.climber_position[1], f.climber_position[2],
                rope_json.join(","),
                gear_json.join(","),
            )
        }).collect();
        format!(
            "{{\"dt_s\":{:.6},\"total_s\":{:.4},\"frames\":[{}]}}",
            self.dt_seconds,
            self.total_time_seconds,
            frames_json.join(","),
        )
    }

    fn __repr__(&self) -> String {
        format!(
            "SimFrameData(frames={}, dt={:.4}s, total={:.2}s, peak={:.2}kN)",
            self.frames.len(), self.dt_seconds,
            self.total_time_seconds, self.peak_anchor_force(),
        )
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_c