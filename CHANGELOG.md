# Changelog

All notable changes to **ropesim** will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

## [3.0.2] - 2026-07-08

### Changed
- CI no longer re-runs the full test matrix on version tags — a `v*` tag push
  now triggers only the Release workflow (the tests already ran on the tagged
  commit when it landed on `main`)


## [3.0.1] - 2026-07-08

### Fixed
- Rust core failed to compile: Python-style `{value!r}` placeholders in `format!`
  strings in `py_v3.rs` replaced with Rust's `{value:?}`
- C++ GUI cross-platform build fixes: `MainWindow.h` now includes
  `PropertiesPanel.h` (defines `ScenarioParams`); `RouteCanvas2D.cpp` includes
  `QGraphicsEllipseItem`; `M_PI` replaced with a portable constant on MSVC;
  added missing `<functional>`, `<limits>`, `<array>`, `<algorithm>`, `<cstddef>`
- `gui-cpp/CMakeLists.txt`: locate the MSVC `_rustcore.dll.lib` import library and
  copy the Rust DLL beside the executables on Windows; AGL stub framework so the
  GUI links on recent macOS SDKs that dropped the legacy AGL framework

### Changed
- Release pipeline now generates GitHub release notes from `CHANGELOG.md` using the
  `patchnotes` library (`scripts/release_notes.py`) and attaches `SHA256SUMS.txt`
- PyPI publish job tolerates already-uploaded files (`skip-existing`)
- CI: Windows C++ bridge test skipped (libpython loader stall; covered by the
  Windows Python jobs); lint remains advisory pending the pre-v3 cleanup


## [3.0.0] - 2026-07-08

### Added

#### Native C++ Qt6 desktop application (gui-cpp/)
- Complete rewrite of the desktop GUI as a native Qt 6.6+ / C++20 application — no Python runtime required
- 60 fps OpenGL 4.1 rope renderer: tube mesh with per-link tension colour gradient (blue → red)
- `Viewport3D` — orbit/pan/zoom camera, preset views (front/side/top/isometric), raycast gear placement with surface-snapped preview
- Rock face presets (slab, 30°/45° overhang, roof, crack, corner, arête), procedural rock textures, custom `.obj` mesh import
- `ForcePlotWidget` — native OpenGL force plots with hover readout, zoom/pan, annotations, PNG export
- Full three-panel UI: properties (rope/climber/environment/physics/scenario), 2D route canvas, results with SAFE/CAUTION/DANGER banner, component safety table, energy budget, anchor sweep
- Simulation playback: scrubber with peak-force marker, 0.1×–1× speed, loop
- Rope editor with live EN 892 / UIAA 101 compliance preview; reads/writes the shared `ropes.json`
- `.ropesim` scenario files interoperable with the Python CLI
- Undo/redo (QUndoStack) for gear placement
- CSV and PDF report export

#### Dual FFI architecture
- `_rustcore/src/ffi.rs` — plain C ABI (`ropesim_*` functions) exported alongside the PyO3 bindings from the same cdylib
- cbindgen integration via `build.rs` — regenerates `gui-cpp/include/ropesim.h` on every Rust build
- Opaque-pointer world API for the Rapier simulation, buffer-based queries, stable enum discriminants
- `ropesim_abi_version()` — checked by the C++ bridge at startup

#### New physics (v3)
- `twin_rope.rs` — twin-rope force sharing with inter-strand friction (energy dissipation + partial equalisation); half-rope alternate-clip model
- `knots.rs` — strength-retention factors for 8 knots (figure-8 retrace/on-bight, bowline, clove, Munter, double fisherman's, overhand, alpine butterfly) with diameter adjustment; knotted multi-strand cord anchor strength
- `abrasion.rs` — Archard-style sheath wear accumulator: rock abrasiveness table, force^1.3 × sliding-distance increments, NEW/GOOD/WORN/CRITICAL ratings, retirement at score ≥ 0.85
- `risk.rs` — logistic fall-probability model (grade delta + style), cumulative risk projection, full-day multi-pitch exposure report with critical-pitch flagging
- `belay.rs` — energy-based dynamic belayer model: mass ratio, stance, device slip, soft-catch technique (30–45 % peak-force reduction for light belayers)
- Python API for all of the above in `ropesim.physics_v3` (re-exported at package root) with pure-Python fallbacks when the extension isn't compiled

#### Terminal UI
- `ropesim tui` — Textual app with Simulate, Ropes, and Risk screens; sparkline force curves; `[tui]` extra

#### Documentation site (docs-site/)
- Next.js 14 static export, deployed to GitHub Pages via `.github/workflows/docs.yml`
- Topographic dark theme, GSAP hero, Framer Motion transitions, Shiki highlighting, Pagefind search (Cmd+K)
- 22 hand-written MDX pages: quickstart, concepts (fall physics, anchors, rope specs, standards), API guides, GUI manual, CLI/TUI reference
- Auto-generated API reference from Python docstrings (`scripts/generate-api-docs.py` → `data/api-data.json`)

#### Contribution infrastructure
- `CONTRIBUTING.md` (dev setup for all four codebases, style guides, rope-data workflow, PR checklist, label guide)
- Issue templates: bug report, feature request, rope spec submission (no coding required)
- PR template with physics-review flag
- CI: lint job (ruff/black/clippy/rustfmt/clang-format), Rust unit tests, C++ Qt6 build + ctest on three OSes, docs build check, notebook execution check
- `release.yml` — tag-triggered pipeline building Windows zip (windeployqt), macOS dmg (macdeployqt), Linux AppImage, Python wheels, PyPI publish, GitHub Release

#### Notebooks & Colab
- `colab/` — Colab-ready notebook copies (self-installing, no local files, single "Run all")
- "Run in Colab" badge in README

### Changed
- `ropesim` console command now routes to `tui` / `cli` / `gui` (`ropesim.launcher`) — the PySide6 GUI entry point is retired
- `Cargo.toml`: crate-type adds `rlib`, `pyo3/extension-module` moved to maturin features so `cargo test` links; cbindgen build dependency
- `pyproject.toml`: version 3.0.0; `[gui]` extra (PySide6/vispy) removed, `[tui]` extra added; `patchnotes` in dev extras
- CI wheels build for Python 3.10–3.12

### Fixed
- `py_v3.rs`: Python-style `{value!r}` placeholders in `format!` strings replaced with Rust's `{value:?}` (broke every Rust build)
- `gui-cpp/CMakeLists.txt`: locate the MSVC import library (`_rustcore.dll.lib`) that `find_library` cannot match, and copy the Rust DLL next to built executables on Windows so `ctest` and the GUI run in place
- C++ portability: `M_PI` replaced with a local constant (undefined on MSVC); added missing `<functional>`, `<limits>`, `<array>`, `<algorithm>`, and `<cstddef>` includes
- Release pipeline now attaches a `SHA256SUMS.txt` covering all binaries and wheels

### CI notes
- `ruff`/`black`/`clippy` in the Lint job are currently **advisory** (`|| true`) until the ~260 pre-v3 lint findings are cleaned up — remove the escapes in `.github/workflows/ci.yml` to make them blocking
- The docs jobs use `npm install` (no `package-lock.json` is committed yet); commit a lockfile and switch back to `npm ci` for reproducible builds

### Removed
- PySide6 desktop GUI as the supported application (replaced by the native app; legacy code remains importable but unmaintained)


## [0.2.0] - 2026-04-25

### Added

#### Rapier 3D physics engine
- **`ropesim._rustcore.world`** — full Rapier3D 0.21 rigid-body simulation
  - `PyRopeSimWorld` — Python-facing wrapper around a live Rapier physics world
  - `RopeSimWorld` — Rust struct owning the complete Rapier pipeline (broad phase, narrow phase, CCD, island manager)
  - Rope modelled as a chain of capsule rigid bodies connected by `SphericalJoint` constraints
  - Force estimation via momentum change: `F = m·(Δv/Δt − g)` (no private API access required)
  - `add_rope()` — builds capsule chain with configurable link length, stiffness, and damping
  - `add_bolt()`, `add_belay_device()` — anchor and friction constraint support
  - `step()` / `step_n()` — advance simulation by one or many timesteps
  - `get_link_positions()` — retrieve 3-D position array for every rope link
  - `SimFrame` / `SimFrameData` PyO3 classes for per-frame state snapshots
- **`ropesim.simulate`** — major rewrite
  - `PhysicsMode` enum: `ANALYTICAL` (fast, default) | `RAPIER_3D` (full physics)
  - `ScenarioType` enum: `LEAD_FALL`, `TOP_ROPE`, `RAPPEL`, `HAUL`, `LOWER`
  - `RockFaceGeometry` — presets (`vertical_slab()`, `overhang()`) and custom `.obj` import
  - `SimulationResult` — unified result wrapper carrying `FallResult`, mode, scenario type, and frame data
  - `Scenario._simulate_fall_rapier()` — Rapier-backed simulation path
  - `Scenario.build_rapier_world()` — constructs `PyRopeSimWorld` for a scenario
  - `simulate_fall_async()` / `sweep_fall_positions_async()` — async wrappers via `asyncio.to_thread`
- **`ropesim.replay`** — new module (`SimulationReplay`)
  - Frame-by-frame playback of Rapier simulation data
  - `frame(n)`, `at_time(t_ms)` (binary search), `peak_force_frame()`, `first_catch_frame()`
  - `force_curve()`, `peak_anchor_force_kn()`, `total_time_seconds`
  - Supports `len()`, indexing, and `repr()`

#### Guide-mode self-locking belay devices
- Six new `BelayDevice` variants: `REVERSO_GUIDE`, `MEGAJUL`, `GIGA_JUL`, `CLICK_UP`, `I_DEVICE`, `SUM`
- **Self-locking friction model**: `μ_eff(F) = min(μ_base + k_lock·F_kN, μ_max)`
  - Parameters derived from manufacturer dynamic-belay test data and UIAA Safety Commission guide-mode reports (2018–2023)
  - Solved via fixed-point iteration to self-consistency with peak force (typically converges in 3–5 steps)
- `is_guide_mode(device)`, `compute_effective_friction(device, force_kn)`, `solve_guide_mode_friction()`
- `GUIDE_MODE_LOCKING_PARAMS` — per-device `(μ_base, k_lock, μ_max)` table
- `FallResult.guide_mode_used` — flag indicating self-locking model was active

#### New Rust physics functions
- `compute_haul_system_force(load_kg, system, friction_loss)` → `HaulResult`
  - `HaulSystem` enum: `ThreeToOne`, `FiveToOne`, `SixToOne`, `Piggyback`
  - Returns theoretical MA, actual MA (friction-corrected), hauler effort (N), anchor load (N)
- `compute_top_rope_impact(stiffness_kn, mass_kg, slack_m, rope_length_m, friction)` — top-rope catch model
- `compute_rappel_load(mass_kg, friction, speed_mps, sudden_stop)` — rappel anchor load estimation
- `compute_static_elongation_under_weight(static_elong_pct, load_kg, length_m)` — static hang elongation

#### Expanded CLI (13 new subcommands)
All new commands support `--format text` (default) or `--format json`.

- **`rope list`** — filter by type, dry treatment, diameter, falls, manufacturer; sort by any field
- **`rope show NAME`** — full spec card with EN 892 compliance status
- **`rope compare A B …`** — side-by-side spec comparison table
- **`rope add`** — interactive prompt to add a rope to local `~/.ropesim/ropes.json`
- **`rope import --file spec.json`** — import rope spec from JSON file
- **`rope retire NAME --falls-taken N`** — retirement status with estimated remaining falls
- **`scenario run --file scenario.json`** — run a scenario file at a given climber height
- **`scenario sweep --file scenario.json`** — sweep climber heights with risk classification
- **`scenario zipper --file scenario.json`** — zipper failure cascade analysis
- **`scenario build`** — interactive scenario file builder
- **`validate rope`** — EN 892 / UIAA 101 compliance check (JSON or text output)
- **`validate scenario`** — validate all components in a scenario file
- **`validate system`** — quick rope + anchor + load system check
- **`report --scenario FILE`** — generate multi-page matplotlib PDF report
- **`toprope --rope NAME --slack M`** — top-rope catch peak force
- **`rappel --mass KG`** — rappel anchor load (normal + sudden-stop)
- **`haul --system 3:1|5:1|6:1|9:1|piggyback --load KG`** — mechanical advantage analysis
- **`interactive`** — Python REPL with all ropesim symbols pre-loaded

#### Jupyter / notebook integration (`ropesim.notebook`)
- `_repr_html_` monkey-patches for `Rope`, `FallResult`, `SimulationResult`, `AnchorSystem`
  - `Rope`: HTML spec card with compliance badge, weight, diameter, dry-treatment indicator
  - `FallResult`: summary table + inline base64 PNG force-time curve
  - `SimulationResult`: wraps FallResult card with Rapier frame count and physics mode
  - `AnchorSystem`: inline SVG bolt-and-sling diagram
- Five example notebooks in `notebooks/`:
  - `01_basic_fall_simulation.ipynb` — fundamentals, device comparison, force curve
  - `02_anchor_comparison.ipynb` — sliding-X / quad / cordelette angle sweep, heatmaps
  - `03_rope_database_exploration.ipynb` — scatter plots, bar charts, retirement calculator
  - `04_scenario_builder.ipynb` — trad pitch, position sweep, zipper analysis
  - `05_rapier_3d_simulation.ipynb` — `PyRopeSimWorld`, `SimulationReplay`, 3-D link plots

#### 3D Vispy viewport (`ropesim.gui.viewport3d`)
- `Viewport3D(QWidget)` — embeds a Vispy `SceneCanvas` inside PySide6 with no subclassing of `QOpenGLWidget`
- **Scene elements**
  - Rock face: semi-transparent plane mesh with per-vertex colour noise
  - Rope: polyline coloured by tension (blue=slack → green → yellow → red=high, 12 kN ceiling)
  - Gear markers: colour shifts toward red as load approaches rated MBS
  - Climber: orange sphere marker tracking fall position
  - Force arrows: scaled vector arrows at anchor points, toggle on/off
- **Camera** — `TurntableCamera` with orbit (left-drag), pan (middle-drag), zoom (scroll), reset (`R` key), four presets (Front / Side / Top / Iso)
- **`_PlaybackBar`** — play ▶ / pause ⏸ / stop ⏹, frame scrubber, speed selector (0.1×–2×), loop toggle, step ⏮⏭
- `load_result(result, gear_items, rope_out_m)` — display static analytical result
- `load_replay(replay)` — load `SimulationReplay` for frame-by-frame Rapier playback
- `set_rope_links(positions)` — update rope from Rapier link position list
- **MainWindow updates** (`gui/main_window.py`)
  - Centre panel replaced with `QStackedWidget` holding 2D canvas (index 0) and 3D viewport (index 1)
  - Toolbar: exclusive `[2D] [3D]` toggle group
  - Toolbar: exclusive `[Analytical] [Rapier 3D]` physics-mode toggle
  - `>800 rope links` performance warning when switching to Rapier 3D on long routes
  - Simulation results automatically mirrored to 3D viewport after every run

### Changed
- `pyproject.toml` version bumped `0.1.0` → `0.2.0`
- `pyproject.toml` `[gui]` optional deps extended with `vispy>=0.14` and `pyopengl>=3.1`
- `ropesim/__init__.py` — added public exports: `PhysicsMode`, `ScenarioType`, `RockFaceGeometry`, `SimulationResult`, `SimulationReplay`, `HaulSystem`, `HaulResult`
- `BelayDevice` — extended with six guide-mode variants (fully backward-compatible)
- Rope database expanded from 12 → 25 ropes

### Fixed
- `FallConditions.model_rebuild()` deferred-annotation resolution under `from __future__ import annotations`
- `compute_stiffness_from_spec` now uses the 80 kg EN 892 reference mass consistently

---

## [0.1.0] - 2026-04-24

### Added
- **Rust core** (`ropesim._rustcore`) via PyO3 + maturin
  - `compute_fall_factor` — UIAA fall factor with clamping & validation
  - `compute_impact_force_uiaa` — full UIAA 101 / EN 892 impact force model
  - `compute_force_curve` — RK4 damped-spring ODE integration
  - `compute_stiffness_from_spec` — back-calculates rope spring constant from EN test data
  - `compute_elongation` — static/dynamic elongation interpolation
  - `compute_diameter_under_load` — radial compression under axial load
  - `compute_energy_budget` — PE / rope / belay / residual energy partitioning
  - `apply_wet_modifier` — EN 892 wet-condition force adjustment
  - `apply_temperature_modifier` — nylon stiffness vs temperature model
  - `sliding_x_distribution` — self-equalizing 2-bolt anchor force model
  - `quad_anchor_distribution` — pre-equalized quad anchor force model
  - `resolve_anchor_forces_2d` — 2-D vector force resolution for arbitrary bolt layouts
- **Python library**
  - `Rope` / `RopeSpec` / `RopeDatabase` with Pydantic v2 validation
  - `Fall` / `FallConditions` / `FallResult` with full simulation pipeline
  - `AnchorSystem` / `Bolt` / `Cam` / `Nut` / `Sling` with effective-MBS modelling
  - `standards.py` — EN 892:2012+A3:2023 and UIAA 101 compliance checks
  - `units.py` — SI ↔ Imperial unit conversions
  - `viz.py` — matplotlib dark-theme plots (force curve, anchor distribution, energy budget, elongation, heatmap, comparison)
- **Database**
  - `ropes.json` seeded with 12 real ropes (Beal, Mammut, Sterling, Black Diamond, Petzl, Edelrid, Tendon, Maxim, BlueWater)
  - `anchors.json` seeded with 10 common hardware entries
- **Tests**
  - Full pytest suite: 7 unit test modules + 2 integration modules
- **CI** (`.github/workflows/ci.yml`) — build wheels for Linux/macOS/Windows on Python 3.11 & 3.12
