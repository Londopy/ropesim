# Changelog

All notable changes to **ropesim** will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

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
  - `force_curve()`, `peak_anch