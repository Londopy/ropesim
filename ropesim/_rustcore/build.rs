// ropesim/_rustcore/build.rs
//
// Generates gui-cpp/include/ropesim.h from src/ffi.rs via cbindgen on every
// Rust build.  Header generation is best-effort: if cbindgen fails (e.g.
// during docs-only builds) we emit a warning instead of failing the build,
// because the Python extension does not need the header.

use std::env;
use std::path::PathBuf;

fn main() {
    println!("cargo:rerun-if-changed=src/ffi.rs");
    println!("cargo:rerun-if-changed=../../cbindgen.toml");

    let crate_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    // crate lives at <repo>/ropesim/_rustcore → repo root is two levels up
    let repo_root = crate_dir
        .parent()
        .and_then(|p| p.parent())
        .map(PathBuf::from)
        .unwrap_or_else(|| crate_dir.clone());

    let header_out = repo_root.join("gui-cpp").join("include").join("ropesim.h");
    if let Some(dir) = header_out.parent() {
        let _ = std::fs::create_dir_all(dir);
    }

    let config_path = repo_root.join("cbindgen.toml");
    let config = if config_path.exists() {
        cbindgen::Config::from_file(&config_path).unwrap_or_default()
    } else {
        cbindgen::Config::default()
    };

    match cbindgen::Builder::new()
        .with_crate(&crate_dir)
        .with_config(config)
        .generate()
    {
        Ok(bindings) => {
            bindings.write_to_file(&header_out);
            println!(
                "cargo:warning=ropesim.h generated at {}",
                header_out.display()
            );
        }
        Err(e) => {
            println!("cargo:warning=cbindgen failed (header not regenerated): {e}");
        }
    }
}
