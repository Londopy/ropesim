// ropesim/_rustcore/src/ffi.rs
//
// Plain C FFI for the C++ Qt6 GUI (v3).
//
// Every function is `#[no_mangle] extern "C"` using only C-compatible types:
// f64/i32 scalars, raw pointer + length pairs for buffers, and an opaque
// `void*` for the Rapier world.  cbindgen (see build.rs / cbindgen.toml)
// generates gui-cpp/include/ropesim.h from this file.
//
// Safety contract (documented per-function in ropesim.h):
//   * out-pointers must be valid, aligned, and writable
//   * world pointers must come from ropesim_world_create and must not be
//     used after ropesim_world_destroy
//   * buffers are caller-allocated; functions return the element count
//     written and never write past `buffer_len`

use crate::abrasion;
use crate::abrasion::{RockType, SheathCondition};
use crate::anchor;
use crate::belay;
use crate::belay::BelayDevice;
use crate::knots;
use crate::knots::KnotType;
use crate::physics;
use crate::risk;
use crate::risk::ClimbingStyle;
use crate::twin_rope;
use crate::world::RopeSimWorld;

use rapier3d::prelude::RigidBodyHandle;

// ───────────────────────────── helpers ──────────────────────────────────────

/// Opaque world wrapper: owns the Rapier world plus a stable handle table so
/// the C side deals in plain ints.
pub struct FfiWorld {
    inner: RopeSimWorld,
    handles: Vec<RigidBodyHandle>,
}

impl FfiWorld {
    fn register(&mut self, h: RigidBodyHandle) -> i32 {
        self.handles.push(h);
        (self.handles.len() - 1) as i32
    }
    fn resolve(&self, idx: i32) -> Option<RigidBodyHandle> {
        if idx < 0 {
            return None;
        }
        self.handles.get(idx as usize).copied()
    }
}

#[inline]
unsafe fn world_mut<'a>(ptr: *mut core::ffi::c_void) -> Option<&'a mut FfiWorld> {
    (ptr as *mut FfiWorld).as_mut()
}

#[inline]
unsafe fn world_ref<'a>(ptr: *mut core::ffi::c_void) -> Option<&'a FfiWorld> {
    (ptr as *const FfiWorld).as_ref()
}

// ───────────────────────────── fall physics ────────────────────────────────

/// UIAA fall factor: fall_dist / rope_out, clamped to [0, 2].
/// Returns -1.0 if rope_out <= 0.
#[no_mangle]
pub extern "C" fn ropesim_compute_fall_factor(fall_dist: f64, rope_out: f64) -> f64 {
    if rope_out <= 0.0 {
        return -1.0;
    }
    (fall_dist / rope_out).clamp(0.0, 2.0)
}

/// UIAA 101 / EN 892 peak impact force (kN) with wet and temperature
/// modifiers applied.  `is_wet`: 0 = dry, nonzero = wet.
#[no_mangle]
pub extern "C" fn ropesim_compute_impact_force(
    mass_kg: f64,
    fall_factor: f64,
    stiffness_kn: f64,
    belay_friction: f64,
    is_wet: i32,
    temp_celsius: f64,
) -> f64 {
    let k = physics::apply_temperature_modifier(stiffness_kn, temp_celsius);
    let f = physics::compute_impact_force_uiaa(mass_kg, fall_factor, k, belay_friction);
    physics::apply_wet_modifier(f, is_wet != 0)
}

/// RK4 force–time curve.  Writes up to `buffer_len` force samples (kN) into
/// caller-allocated `out_buffer`; returns the number of values written.
/// Returns 0 on null/empty buffer.
#[no_mangle]
pub extern "C" fn ropesim_compute_force_curve(
    mass_kg: f64,
    fall_dist: f64,
    rope_out: f64,
    stiffness_kn: f64,
    damping: f64,
    dt_ms: f64,
    out_buffer: *mut f64,
    buffer_len: i32,
) -> i32 {
    if out_buffer.is_null() || buffer_len <= 0 {
        return 0;
    }
    let curve = physics::compute_force_curve_inner(
        mass_kg, fall_dist, rope_out, stiffness_kn, damping, dt_ms,
    );
    let n = curve.len().min(buffer_len as usize);
    unsafe {
        core::ptr::copy_nonoverlapping(curve.as_ptr(), out_buffer, n);
    }
    n as i32
}

// ───────────────────────────── anchors ─────────────────────────────────────

/// Sliding-X force distribution.  Writes per-bolt force (kN) to out params.
#[no_mangle]
pub extern "C" fn ropesim_sliding_x_distribution(
    load_kn: f64,
    angle_deg: f64,
    out_bolt_a: *mut f64,
    out_bolt_b: *mut f64,
) {
    let (a, b) = anchor::sliding_x_distribution(load_kn, angle_deg);
    unsafe {
        if !out_bolt_a.is_null() {
            *out_bolt_a = a;
        }
        if !out_bolt_b.is_null() {
            *out_bolt_b = b;
        }
    }
}

/// Quad anchor force distribution.  `extension_limiter`: 0 = no, nonzero = yes.
#[no_mangle]
pub extern "C" fn ropesim_quad_distribution(
    load_kn: f64,
    angle_deg: f64,
    extension_limiter: i32,
    out_bolt_a: *mut f64,
    out_bolt_b: *mut f64,
) {
    let (a, b) = anchor::quad_anchor_distribution(load_kn, angle_deg, extension_limiter != 0);
    unsafe {
        if !out_bolt_a.is_null() {
            *out_bolt_a = a;
        }
        if !out_bolt_b.is_null() {
            *out_bolt_b = b;
        }
    }
}

// ───────────────────────────── Rapier world ────────────────────────────────

/// Create a physics world.  Returns an opaque pointer; destroy with
/// ropesim_world_destroy.
#[no_mangle]
pub extern "C" fn ropesim_world_create(gravity: f64) -> *mut core::ffi::c_void {
    let boxed = Box::new(FfiWorld {
        inner: RopeSimWorld::new(gravity),
        handles: Vec::new(),
    });
    Box::into_raw(boxed) as *mut core::ffi::c_void
}

/// Destroy a world created by ropesim_world_create.  Passing null is a no-op.
#[no_mangle]
pub extern "C" fn ropesim_world_destroy(world: *mut core::ffi::c_void) {
    if world.is_null() {
        return;
    }
    unsafe {
        drop(Box::from_raw(world as *mut FfiWorld));
    }
}

/// Add a rope between start[3] and end[3].  Returns the handle of the rope's
/// *last* link (climber attachment point), or -1 on error.
#[no_mangle]
pub extern "C" fn ropesim_world_add_rope(
    world: *mut core::ffi::c_void,
    start: *const f64,
    end: *const f64,
    length_m: f64,
    mass_per_m: f64,
    link_len: f64,
    stiffness: f64,
    damping: f64,
) -> i32 {
    let w = match unsafe { world_mut(world) } {
        Some(w) => w,
        None => return -1,
    };
    if start.is_null() || end.is_null() {
        return -1;
    }
    let (s, e) = unsafe {
        (
            [*start, *start.add(1), *start.add(2)],
            [*end, *end.add(1), *end.add(2)],
        )
    };
    let handles = w
        .inner
        .add_rope(s, e, length_m, mass_per_m, link_len, stiffness, damping);
    match handles.last() {
        Some(&h) => w.register(h),
        None => -1,
    }
}

/// Add a bolt.  `bolt_type`: 0 = expansion, 1 = glue-in (cosmetic only).
/// Returns gear handle or -1.
#[no_mangle]
pub extern "C" fn ropesim_world_add_bolt(
    world: *mut core::ffi::c_void,
    pos: *const f64,
    mbs_kn: f64,
    bolt_type: i32,
) -> i32 {
    let w = match unsafe { world_mut(world) } {
        Some(w) => w,
        None => return -1,
    };
    if pos.is_null() {
        return -1;
    }
    let p = unsafe { [*pos, *pos.add(1), *pos.add(2)] };
    let type_name = if bolt_type == 1 { "glue_in" } else { "expansion" };
    let h = w.inner.add_bolt(p, mbs_kn, type_name);
    w.register(h)
}

/// Add a cam.  `quality` 0–1, `pull_dir[3]` expected pull-out direction.
/// Returns gear handle or -1.
#[no_mangle]
pub extern "C" fn ropesim_world_add_cam(
    world: *mut core::ffi::c_void,
    pos: *const f64,
    mbs_kn: f64,
    quality: f64,
    pull_dir: *const f64,
) -> i32 {
    let w = match unsafe { world_mut(world) } {
        Some(w) => w,
        None => return -1,
    };
    if pos.is_null() || pull_dir.is_null() {
        return -1;
    }
    let p = unsafe { [*pos, *pos.add(1), *pos.add(2)] };
    let d = unsafe { [*pull_dir, *pull_dir.add(1), *pull_dir.add(2)] };
    let h = w.inner.add_cam(p, mbs_kn, quality, d);
    w.register(h)
}

/// Attach a climber to a rope handle (as returned by add_rope).
/// Returns climber handle or -1.
#[no_mangle]
pub extern "C" fn ropesim_world_add_climber(
    world: *mut core::ffi::c_void,
    rope_handle: i32,
    mass_kg: f64,
) -> i32 {
    let w = match unsafe { world_mut(world) } {
        Some(w) => w,
        None => return -1,
    };
    let rh = match w.resolve(rope_handle) {
        Some(h) => h,
        None => return -1,
    };
    let h = w.inner.add_climber(rh, mass_kg);
    w.register(h)
}

/// Add a ledge/rock face from a triangle-fan vertex list (xyz triples).
/// Returns 0 on success, -1 on error.
#[no_mangle]
pub extern "C" fn ropesim_world_add_ledge(
    world: *mut core::ffi::c_void,
    verts: *const f64,
    vert_count: i32,
    friction: f64,
) -> i32 {
    let w = match unsafe { world_mut(world) } {
        Some(w) => w,
        None => return -1,
    };
    if verts.is_null() || vert_count < 3 {
        return -1;
    }
    let mut v = Vec::with_capacity(vert_count as usize);
    for i in 0..vert_count as usize {
        unsafe {
            v.push([
                *verts.add(i * 3),
                *verts.add(i * 3 + 1),
                *verts.add(i * 3 + 2),
            ]);
        }
    }
    w.inner.add_ledge(v, friction);
    0
}

/// Add a belayer.  `device_type` uses the RopesimBelayDevice enum values;
/// `dynamic`: 0 = anchored/static, nonzero = dynamic (can be lifted).
/// Returns belayer handle or -1.
#[no_mangle]
pub extern "C" fn ropesim_world_add_belayer(
    world: *mut core::ffi::c_void,
    pos: *const f64,
    mass_kg: f64,
    device_type: i32,
    dynamic: i32,
) -> i32 {
    let w = match unsafe { world_mut(world) } {
        Some(w) => w,
        None => return -1,
    };
    if pos.is_null() {
        return -1;
    }
    let p = unsafe { [*pos, *pos.add(1), *pos.add(2)] };
    let device = BelayDevice::from_i32(device_type).unwrap_or(BelayDevice::Atc);
    let name = match device {
        BelayDevice::Atc => "atc",
        BelayDevice::GriGri => "grigri",
        BelayDevice::Tube => "tube",
        BelayDevice::Reverso => "reverso",
        BelayDevice::ReversoGuide => "reverso_guide",
        BelayDevice::MegaJul => "megajul",
        BelayDevice::GigaJul => "giga_jul",
        BelayDevice::ClickUp => "click_up",
        BelayDevice::IDevice => "i_device",
        BelayDevice::Sum => "sum",
        BelayDevice::Munter => "munter",
    };
    let h = w.inner.add_belayer(p, mass_kg, name, dynamic != 0);
    w.register(h)
}

/// Clip rope link `rope_link` (index along the rope) to a gear handle.
#[no_mangle]
pub extern "C" fn ropesim_world_clip_rope(
    world: *mut core::ffi::c_void,
    rope_link: i32,
    gear_handle: i32,
) {
    if let Some(w) = unsafe { world_mut(world) } {
        if let Some(gh) = w.resolve(gear_handle) {
            if rope_link >= 0 {
                w.inner.clip_rope_to_gear(rope_link as usize, gh);
            }
        }
    }
}

/// Advance the simulation by `dt` seconds.
#[no_mangle]
pub extern "C" fn ropesim_world_step(world: *mut core::ffi::c_void, dt: f64) {
    if let Some(w) = unsafe { world_mut(world) } {
        w.inner.step(dt);
    }
}

/// Write rope link positions as xyz triples into `out_buf`
/// (capacity `buf_len` doubles).  Returns the number of f64 values written.
#[no_mangle]
pub extern "C" fn ropesim_world_get_rope_positions(
    world: *mut core::ffi::c_void,
    out_buf: *mut f64,
    buf_len: i32,
) -> i32 {
    let w = match unsafe { world_ref(world) } {
        Some(w) => w,
        None => return 0,
    };
    if out_buf.is_null() || buf_len <= 0 {
        return 0;
    }
    let positions = w.inner.get_rope_positions();
    let mut written = 0usize;
    let cap = buf_len as usize;
    'outer: for p in &positions {
        for &c in p {
            if written >= cap {
                break 'outer;
            }
            unsafe {
                *out_buf.add(written) = c;
            }
            written += 1;
        }
    }
    written as i32
}

/// Current estimated force (kN) at a gear handle.
#[no_mangle]
pub extern "C" fn ropesim_world_get_force_at_gear(
    world: *mut core::ffi::c_void,
    gear_handle: i32,
) -> f64 {
    match unsafe { world_ref(world) } {
        Some(w) => match w.resolve(gear_handle) {
            Some(h) => w.inner.get_force_at_gear(h),
            None => 0.0,
        },
        None => 0.0,
    }
}

/// Current estimated anchor force (kN).
#[no_mangle]
pub extern "C" fn ropesim_world_get_anchor_force(world: *mut core::ffi::c_void) -> f64 {
    match unsafe { world_ref(world) } {
        Some(w) => w.inner.get_force_at_anchor(),
        None => 0.0,
    }
}

/// Climber position (xyz) written to out[3].
#[no_mangle]
pub extern "C" fn ropesim_world_get_climber_position(
    world: *mut core::ffi::c_void,
    out: *mut f64,
) {
    if out.is_null() {
        return;
    }
    let p = match unsafe { world_ref(world) } {
        Some(w) => w.inner.get_climber_position(),
        None => [0.0; 3],
    };
    unsafe {
        *out = p[0];
        *out.add(1) = p[1];
        *out.add(2) = p[2];
    }
}

// ───────────────── static elongation / rappel / haul ───────────────────────

/// Static elongation (m) under a sustained load.
#[no_mangle]
pub extern "C" fn ropesim_static_elongation(
    static_pct: f64,
    load_kg: f64,
    length_m: f64,
) -> f64 {
    physics::compute_static_elongation_under_weight(static_pct, load_kg, length_m)
}

/// Rappel anchor load (kN) during steady descent (no sudden stop).
#[no_mangle]
pub extern "C" fn ropesim_rappel_load(
    mass_kg: f64,
    device_friction: f64,
    speed_mps: f64,
) -> f64 {
    physics::compute_rappel_load(mass_kg, device_friction, speed_mps, false)
}

/// Haul system forces.  `system_type`: 0 = 3:1, 1 = 5:1, 2 = 6:1, 3 = piggyback.
/// Writes actual mechanical advantage and hauler effort (N).
#[no_mangle]
pub extern "C" fn ropesim_haul_forces(
    system_type: i32,
    load_kg: f64,
    friction: f64,
    out_actual_ma: *mut f64,
    out_hauler_effort: *mut f64,
) {
    let system = match system_type {
        1 => physics::HaulSystem::FiveToOne,
        2 => physics::HaulSystem::SixToOne,
        3 => physics::HaulSystem::Piggyback,
        _ => physics::HaulSystem::ThreeToOne,
    };
    let r = physics::compute_haul_system_force(load_kg, system, friction);
    unsafe {
        if !out_actual_ma.is_null() {
            *out_actual_ma = r.actual_ma;
        }
        if !out_hauler_effort.is_null() {
            *out_hauler_effort = r.hauler_effort_n;
        }
    }
}

// ───────────────────────── rope degradation ────────────────────────────────

/// Rope degradation with accumulated falls.  Mirrors ropesim.rope.Rope.degrade:
/// stiffness (and impact force) rise up to +20 % at end of rated life.
/// `out_retirement_warning`: 0 = fine, 1 = inspect (≥80 %), 2 = retire (≥100 %).
#[no_mangle]
pub extern "C" fn ropesim_degrade_rope(
    base_stiffness: f64,
    falls_taken: i32,
    rated_falls: i32,
    out_stiffness: *mut f64,
    out_impact_force: *mut f64,
    out_retirement_warning: *mut i32,
) {
    let falls = falls_taken.max(0) as f64;
    let rated = rated_falls.max(1) as f64;
    let ratio = (falls / rated).min(1.0);
    let factor = 1.0 + 0.20 * ratio;
    let new_stiffness = base_stiffness * factor;
    // Impact force at EN 892 test conditions with the degraded stiffness
    let impact = physics::compute_impact_force_uiaa(80.0, 1.772, new_stiffness, 0.0);
    let warning = if falls >= rated {
        2
    } else if falls >= 0.8 * rated {
        1
    } else {
        0
    };
    unsafe {
        if !out_stiffness.is_null() {
            *out_stiffness = new_stiffness;
        }
        if !out_impact_force.is_null() {
            *out_impact_force = impact;
        }
        if !out_retirement_warning.is_null() {
            *out_retirement_warning = warning;
        }
    }
}

// ───────────────────────── v3 new physics ──────────────────────────────────

/// Twin-rope pair forces (kN) through a shared piece.
#[no_mangle]
pub extern "C" fn ropesim_twin_rope_forces(
    rope_a_stiffness: f64,
    rope_b_stiffness: f64,
    mass_kg: f64,
    fall_factor: f64,
    inter_rope_friction: f64,
    out_force_a: *mut f64,
    out_force_b: *mut f64,
) {
    let (a, b) = twin_rope::compute_twin_rope_forces(
        rope_a_stiffness,
        rope_b_stiffness,
        mass_kg,
        fall_factor,
        inter_rope_friction,
    );
    unsafe {
        if !out_force_a.is_null() {
            *out_force_a = a;
        }
        if !out_force_b.is_null() {
            *out_force_b = b;
        }
    }
}

/// Half-rope pair forces (kN); `active_rope` 0 or 1 selects the strand
/// arresting this fall.
#[no_mangle]
pub extern "C" fn ropesim_half_rope_forces(
    rope_a_stiffness: f64,
    rope_b_stiffness: f64,
    mass_kg: f64,
    fall_factor: f64,
    active_rope: i32,
    out_force_a: *mut f64,
    out_force_b: *mut f64,
) {
    let (a, b) = twin_rope::compute_half_rope_forces(
        rope_a_stiffness,
        rope_b_stiffness,
        mass_kg,
        fall_factor,
        if active_rope == 1 { 1 } else { 0 },
    );
    unsafe {
        if !out_force_a.is_null() {
            *out_force_a = a;
        }
        if !out_force_b.is_null() {
            *out_force_b = b;
        }
    }
}

/// Knot strength retention factor (0–1).  `knot_type` uses the RopesimKnotType
/// enum values; unknown values return the conservative clove-hitch factor.
#[no_mangle]
pub extern "C" fn ropesim_knot_strength_factor(knot_type: i32, rope_diameter_mm: f64) -> f64 {
    let knot = KnotType::from_i32(knot_type).unwrap_or(KnotType::CloveHitch);
    knots::compute_knot_strength_factor(knot, rope_diameter_mm)
}

/// Knotted multi-strand cord anchor strength (kN).
#[no_mangle]
pub extern "C" fn ropesim_cord_anchor_strength(
    cord_mbs_kn: f64,
    knot_type: i32,
    num_strands: i32,
    diameter_mm: f64,
) -> f64 {
    let knot = KnotType::from_i32(knot_type).unwrap_or(KnotType::OverhandOnBight);
    knots::compute_cord_anchor_strength(cord_mbs_kn, knot, num_strands.max(1) as u32, diameter_mm)
}

/// Sheath abrasion increment for one rope-over-rock contact.
/// `rock_type` uses the RopesimRockType enum values.
#[no_mangle]
pub extern "C" fn ropesim_abrasion_increment(
    rock_type: i32,
    contact_force_kn: f64,
    contact_duration_s: f64,
    rope_velocity_mps: f64,
) -> f64 {
    let rock = RockType::from_i32(rock_type).unwrap_or(RockType::Granite);
    abrasion::compute_abrasion_increment(
        rock,
        contact_force_kn,
        contact_duration_s,
        rope_velocity_mps,
    )
}

/// Fold an abrasion increment into a running score.  Returns the new score
/// (0–1) and writes the visual rating (RopesimSheathRating values) and
/// retirement flag (0/1).
#[no_mangle]
pub extern "C" fn ropesim_accumulate_sheath_wear(
    current_score: f64,
    increment: f64,
    sheath_pct: f64,
    out_rating: *mut i32,
    out_needs_retirement: *mut i32,
) -> f64 {
    let current = SheathCondition {
        abrasion_score: current_score.clamp(0.0, 1.0),
        estimated_falls_remaining: u32::MAX,
        visual_rating: crate::abrasion::SheathRating::New,
    };
    let updated = abrasion::accumulate_sheath_wear(current, increment, sheath_pct);
    unsafe {
        if !out_rating.is_null() {
            *out_rating = updated.visual_rating as i32;
        }
        if !out_needs_retirement.is_null() {
            *out_needs_retirement = i32::from(updated.needs_retirement());
        }
    }
    updated.abrasion_score
}

/// Fall probability per attempt and cumulative risk over `attempts`.
/// `pitch_grade` / climber grade use YDS numeric (5.10a → 10.1).
/// Climber grade is fixed at the route grade minus `grade_margin`.
///
/// Simpler two-output form required by the GUI results panel:
/// writes probability per attempt and expected falls over `attempts`.
#[no_mangle]
pub extern "C" fn ropesim_fall_probability(
    pitch_grade: f64,
    climber_grade: f64,
    style: i32,
    attempts: i32,
    out_prob_per_attempt: *mut f64,
    out_expected_falls: *mut f64,
) {
    let s = ClimbingStyle::from_i32(style).unwrap_or(ClimbingStyle::Sport);
    let p = risk::compute_fall_probability(pitch_grade, climber_grade, s);
    unsafe {
        if !out_prob_per_attempt.is_null() {
            *out_prob_per_attempt = p;
        }
        if !out_expected_falls.is_null() {
            *out_expected_falls = p * attempts.max(0) as f64;
        }
    }
}

/// Cumulative risk projection.  Outputs: expected falls, expected total
/// force (kN), rope life consumed (%), retirement climbs remaining.
#[no_mangle]
pub extern "C" fn ropesim_cumulative_risk(
    fall_probability: f64,
    num_attempts: i32,
    peak_force_kn: f64,
    rope_rated_falls: i32,
    falls_taken_so_far: i32,
    out_expected_falls: *mut f64,
    out_expected_total_force_kn: *mut f64,
    out_rope_life_consumed_pct: *mut f64,
    out_retirement_climbs_remaining: *mut i32,
) {
    let r = risk::compute_cumulative_risk(
        fall_probability,
        num_attempts.max(0) as u32,
        peak_force_kn,
        rope_rated_falls.max(1) as u32,
        falls_taken_so_far.max(0) as u32,
    );
    unsafe {
        if !out_expected_falls.is_null() {
            *out_expected_falls = r.expected_falls;
        }
        if !out_expected_total_force_kn.is_null() {
            *out_expected_total_force_kn = r.expected_total_force_kn;
        }
        if !out_rope_life_consumed_pct.is_null() {
            *out_rope_life_consumed_pct = r.rope_life_consumed_pct;
        }
        if !out_retirement_climbs_remaining.is_null() {
            *out_retirement_climbs_remaining =
                r.retirement_climbs_remaining.min(i32::MAX as u32) as i32;
        }
    }
}

/// Dynamic belay force-reduction factor (0.55–1.0) to multiply into peak
/// impact force.  `device_type` uses the RopesimBelayDevice enum values.
#[no_mangle]
pub extern "C" fn ropesim_dynamic_belay_reduction(
    climber_mass_kg: f64,
    belayer_mass_kg: f64,
    device_type: i32,
    belayer_standing: i32,
    soft_catch_technique: i32,
) -> f64 {
    let device = BelayDevice::from_i32(device_type).unwrap_or(BelayDevice::Atc);
    belay::compute_dynamic_belay_reduction(
        climber_mass_kg,
        belayer_mass_kg,
        device,
        belayer_standing != 0,
        soft_catch_technique != 0,
    )
}

// ───────────────────────────── version ─────────────────────────────────────

/// ABI version of this header.  The C++ bridge asserts on this at startup.
#[no_mangle]
pub extern "C" fn ropesim_abi_version() -> i32 {
    3
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fall_factor_matches_python_semantics() {
        assert!((ropesim_compute_fall_factor(5.0, 2.82) - 1.7730496453900708).abs() < 1e-9);
        assert_eq!(ropesim_compute_fall_factor(1.0, 0.0), -1.0);
        assert_eq!(ropesim_compute_fall_factor(10.0, 2.0), 2.0); // clamped
    }

    #[test]
    fn force_curve_fills_buffer() {
        let mut buf = vec![0.0_f64; 4000];
        let n = ropesim_compute_force_curve(
            80.0, 4.0, 8.0, 24.0, 0.15, 1.0, buf.as_mut_ptr(), buf.len() as i32,
        );
        assert!(n > 10, "expected a real curve, got {n} samples");
        let peak = buf[..n as usize].iter().cloned().fold(0.0, f64::max);
        assert!(peak > 2.0 && peak < 20.0, "peak {peak} kN");
        // null / empty safety
        assert_eq!(
            ropesim_compute_force_curve(80.0, 4.0, 8.0, 24.0, 0.15, 1.0, core::ptr::null_mut(), 10),
            0
        );
    }

    #[test]
    fn truncated_buffer_respected() {
        let mut buf = vec![0.0_f64; 8];
        let n = ropesim_compute_force_curve(
            80.0, 4.0, 8.0, 24.0, 0.15, 1.0, buf.as_mut_ptr(), buf.len() as i32,
        );
        assert_eq!(n, 8);
    }

    #[test]
    fn anchor_distributions_write_outputs() {
        let (mut a, mut b) = (0.0, 0.0);
        ropesim_sliding_x_distribution(10.0, 60.0, &mut a, &mut b);
        assert!((a - b).abs() < 1e-12);
        assert!(a > 5.0, "60° opening angle multiplies force: {a}");

        let (mut qa, mut qb) = (0.0, 0.0);
        ropesim_quad_distribution(10.0, 120.0, 1, &mut qa, &mut qb);
        let (mut xa, _xb) = (0.0, 0.0);
        ropesim_sliding_x_distribution(10.0, 120.0, &mut xa, core::ptr::null_mut());
        assert!(qa < xa, "limiter caps quad force below sliding-X at 120°");
    }

    #[test]
    fn world_lifecycle_and_fall() {
        let w = ropesim_world_create(9.81);
        assert!(!w.is_null());

        let start = [0.0, 0.0, 0.0];
        let end = [0.0, -2.0, 0.0];
        let rope = ropesim_world_add_rope(w, start.as_ptr(), end.as_ptr(), 2.0, 0.065, 0.5, 80.0, 8.0);
        assert!(rope >= 0);
        let climber = ropesim_world_add_climber(w, rope, 80.0);
        assert!(climber >= 0);

        for _ in 0..240 {
            ropesim_world_step(w, 1.0 / 240.0);
        }

        let mut buf = vec![0.0_f64; 512];
        let n = ropesim_world_get_rope_positions(w, buf.as_mut_ptr(), buf.len() as i32);
        assert!(n >= 6 && n % 3 == 0, "expected xyz triples, got {n}");

        let anchor_force = ropesim_world_get_anchor_force(w);
        assert!(anchor_force.is_finite());

        let mut pos = [0.0_f64; 3];
        ropesim_world_get_climber_position(w, pos.as_mut_ptr());
        assert!(pos[1] < 0.0, "climber should hang below anchor");

        ropesim_world_destroy(w);
        ropesim_world_destroy(core::ptr::null_mut()); // no-op
    }

    #[test]
    fn degrade_rope_warning_levels() {
        let (mut k, mut f, mut w) = (0.0, 0.0, -1);
        ropesim_degrade_rope(24.0, 0, 8, &mut k, &mut f, &mut w);
        assert_eq!(w, 0);
        assert!((k - 24.0).abs() < 1e-9);

        ropesim_degrade_rope(24.0, 7, 8, &mut k, &mut f, &mut w);
        assert_eq!(w, 1);
        assert!(k > 24.0);

        ropesim_degrade_rope(24.0, 9, 8, &mut k, &mut f, &mut w);
        assert_eq!(w, 2);
        assert!((k - 24.0 * 1.2).abs() < 1e-9);
    }

    #[test]
    fn v3_functions_roundtrip() {
        let (mut a, mut b) = (0.0, 0.0);
        ropesim_twin_rope_forces(20.0, 20.0, 80.0, 1.0, 0.2, &mut a, &mut b);
        assert!(a > 0.0 && (a - b).abs() < 1e-9);

        let f8 = ropesim_knot_strength_factor(0, 9.5);
        assert!((0.7..0.85).contains(&f8));

        let inc = ropesim_abrasion_increment(2, 5.0, 0.4, 2.0); // sandstone
        assert!(inc > 0.0 && inc < 0.1);

        let (mut rating, mut retire) = (-1, -1);
        let score = ropesim_accumulate_sheath_wear(0.8, 0.1, 37.0, &mut rating, &mut retire);
        assert!(score >= 0.85 && retire == 1 && rating == 3);

        let (mut p, mut ef) = (0.0, 0.0);
        ropesim_fall_probability(12.0, 12.0, 0, 4, &mut p, &mut ef);
        assert!((0.3..=0.7).contains(&p));
        assert!((ef - p * 4.0).abs() < 1e-9);

        let red = ropesim_dynamic_belay_reduction(55.0, 80.0, 0, 1, 1);
        assert!((0.55..1.0).contains(&red));

        assert_eq!(ropesim_abi_version(), 3);
    }
}
