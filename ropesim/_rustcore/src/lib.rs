// ropesim/_rustcore/src/lib.rs
//
// PyO3 module registration — wires physics.rs, anchor.rs, batch.rs,
// sim_data.rs, and world.rs into the `ropesim._rustcore` Python extension.

use pyo3::prelude::*;

mod physics;
mod anchor;
mod batch;
mod sim_data;
mod world;

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
    Ok(())
}
