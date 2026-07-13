// ropesim/_rustcore/src/lib.rs
//
// PyO3 module registration — wires physics.rs, anchor.rs, batch.rs,
// sim_data.rs, world.rs and the v3 modules into the `ropesim._rustcore`
// Python extension.  The same cdylib also exports the plain C FFI (ffi.rs)
// consumed by the C++ GUI.

use pyo3::prelude::*;

mod physics;
mod anchor;
mod batch;
mod sim_data;
mod world;

// v3 — pure-Rust physics modules (shared by PyO3 and the C FFI)
mod twin_rope;
mod knots;
mod abrasion;
mod risk;
mod belay;

// v3 — frontends
mod py_v3;
pub mod ffi;

// v4 — nonlinear rope, capstan friction, two-body belayer dynamics
mod nonlinear;
mod capstan;
mod two_body;

/// ropesim._rustcore
///
/// Rust-accelerated physics core for the ropesim library.
/// Do not import this module directly — use the public Python API instead.
#[pymodule]
fn _rustcore(m: &Bound<'_, PyModule>) -> PyResult<()> {
    physics::register(m)?;
    anchor::register(m)?;
    batch::register(m)?;
    sim_data::register(m)?;
    world::register(m)?;
    py_v3::register(m)?;
    nonlinear::register(m)?;
    capstan::register(m)?;
    two_body::register(m)?;
    Ok(())
}
