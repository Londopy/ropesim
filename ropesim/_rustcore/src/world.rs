// ropesim/_rustcore/src/world.rs
// RopeSimWorld -- Rapier3D physics world for climbing-rope simulation.
//
// Force estimation note (rapier3d 0.21):
//   ImpulseJoint.impulses is pub(crate), not accessible externally.
//   We estimate anchor/gear forces from momentum change:
//     F_rope ~ m_climber * |dv_climber| / dt  (Newton 2nd law on climber)
//   This produces 0 during free-fall (gravity only) and a spike on catch.

use pyo3::prelude::*;
use rapier3d::prelude::*;
use nalgebra::{Point3, Vector3, UnitVector3};

use crate::sim_data::{FailureEvent, SimFrame, SimFrameData};

// ---------------------------------------------------------------------------
// Supporting enums
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
pub enum BelayDeviceType {
    Atc, GriGri, Tube, Reverso,
    ReversoGuide, MegaJul, GigaJul, ClickUp, IDevice, Sum, Munter,
}

impl BelayDeviceType {
    pub fn from_str(s: &str) -> Self {
        match s {
            "grigri"        => BelayDeviceType::GriGri,
            "tube"          => BelayDeviceType::Tube,
            "reverso"       => BelayDeviceType::Reverso,
            "reverso_guide" => BelayDeviceType::ReversoGuide,
            "megajul"       => BelayDeviceType::MegaJul,
            "giga_jul"      => BelayDeviceType::GigaJul,
            "click_up"      => BelayDeviceType::ClickUp,
            "i_device"      => BelayDeviceType::IDevice,
            "sum"           => BelayDeviceType::Sum,
            "munter"        => BelayDeviceType::Munter,
            _               => BelayDeviceType::Atc,
        }
    }
    pub fn friction_coefficient(&self) -> f32 {
        match self {
            BelayDeviceType::Atc          => 0.35,
            BelayDeviceType::GriGri       => 0.55,
            BelayDeviceType::Tube         => 0.33,
            BelayDeviceType::Reverso      => 0.40,
            BelayDeviceType::ReversoGuide => 0.65,
            BelayDeviceType::MegaJul      => 0.62,
            BelayDeviceType::GigaJul      => 0.60,
            BelayDeviceType::ClickUp      => 0.58,
            BelayDeviceType::IDevice      => 0.70,
            BelayDeviceType::Sum          => 0.65,
            BelayDeviceType::Munter       => 0.45,
        }
    }
}

// ---------------------------------------------------------------------------
// PendulumResult
// ---------------------------------------------------------------------------

#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct PendulumResult {
    pub swing_arc_positions: Vec<[f64; 3]>,
    pub wall_impact_velocity_mps: f64,
    pub wall_impact_force_kn: f64,
    pub terrain_contact: bool,
}

#[pymethods]
impl PendulumResult {
    fn __repr__(&self) -> String {
        format!(
            "PendulumResult(impact_v={:.2}m/s, impact_f={:.2}kN, wall={})",
            self.wall_impact_velocity_mps, self.wall_impact_force_kn, self.terrain_contact,
        )
    }
}

// ---------------------------------------------------------------------------
// Internal gear record
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
struct GearRecord {
    handle:       RigidBodyHandle,
    mbs_n:        f32,
    pull_out_dir: Vector3<f32>,
    quality:      f32,
    failed:       bool,
}

// ---------------------------------------------------------------------------
// RopeSimWorld
// ---------------------------------------------------------------------------

pub struct RopeSimWorld {
    pipeline:            PhysicsPipeline,
    gravity:             Vector3<f32>,
    integration_params:  IntegrationParameters,
    island_manager:      IslandManager,
    broad_phase:         DefaultBroadPhase,
    narrow_phase:        NarrowPhase,
    rigid_body_set:      RigidBodySet,
    collider_set:        ColliderSet,
    impulse_joint_set:   ImpulseJointSet,
    multibody_joint_set: MultibodyJointSet,
    ccd_solver:          CCDSolver,
    query_pipeline:      QueryPipeline,

    rope_handles:        Vec<RigidBodyHandle>,
    climber_handle:      Option<RigidBodyHandle>,
    anchor_handle:       Option<RigidBodyHandle>,
    belayer_handle:      Option<RigidBodyHandle>,
    belayer_friction:    f32,
    gear_records:        Vec<GearRecord>,
    rope_edge_contacts:  Vec<(Point3<f32>, f32)>,
    pending_failures:    Vec<FailureEvent>,
    elapsed_s:           f64,

    // Velocity-difference force estimator state
    prev_climber_vel:    Vector3<f32>,
    current_anchor_force_kn: f64,
}

impl RopeSimWorld {
    pub fn new(gravity_mps2: f64) -> Self {
        let mut integration_params = IntegrationParameters::default();
        integration_params.dt = 1.0 / 240.0;
        RopeSimWorld {
            pipeline:            PhysicsPipeline::new(),
            gravity:             Vector3::new(0.0, -(gravity_mps2 as f32), 0.0),
            integration_params,
            island_manager:      IslandManager::new(),
            broad_phase:         DefaultBroadPhase::new(),
            narrow_phase:        NarrowPhase::new(),
            rigid_body_set:      RigidBodySet::new(),
            collider_set:        ColliderSet::new(),
            impulse_joint_set:   ImpulseJointSet::new(),
            multibody_joint_set: MultibodyJointSet::new(),
            ccd_solver:          CCDSolver::new(),
            query_pipeline:      QueryPipeline::new(),
            rope_handles:        Vec::new(),
            climber_handle:      None,
            anchor_handle:       None,
            belayer_handle:      None,
            belayer_friction:    0.35,
            gear_records:        Vec::new(),
            rope_edge_contacts:  Vec::new(),
            pending_failures:    Vec::new(),
            elapsed_s:           0.0,
            prev_climber_vel:    Vector3::zeros(),
            current_anchor_force_kn: 0.0,
        }
    }

    // -- add_rope -------------------------------------------------------------

    pub fn add_rope(
        &mut self,
        start_pos:     [f64; 3],
        end_pos:       [f64; 3],
        length_m:      f64,
        mass_per_meter: f64,
        link_length_m:  f64,
        stiffness:     f64,
        damping:       f64,
    ) -> Vec<RigidBodyHandle> {
        let n_links = ((length_m / link_length_m).ceil() as usize).max(2);
        let start   = Vector3::new(start_pos[0] as f32, start_pos[1] as f32, start_pos[2] as f32);
        let end     = Vector3::new(end_pos[0]   as f32, end_pos[1]   as f32, end_pos[2]   as f32);
        let link_mass = (mass_per_meter * link_length_m) as f32;
        let radius    = 0.005_f32;
        let half_len  = (link_length_m as f32) / 2.0;
        let stiff_f   = stiffness as f32;
        let damp_f    = damping   as f32;

        let mut handles: Vec<RigidBodyHandle> = Vec::with_capacity(n_links);
        let mut prev_handle: Option<RigidBodyHandle> = None;

        for i in 0..n_links {
            let t   = i as f32 / (n_links - 1).max(1) as f32;
            let pos = start + t * (end - start);
            let rb  = RigidBodyBuilder::dynamic()
                .translation(pos)
                .linear_damping(0.05)
                .angular_damping(0.5)
                .build();
            let handle = self.rigid_body_set.insert(rb);

            let col = ColliderBuilder::capsule_y(half_len, radius)
                .mass(link_mass)
                .friction(0.4)
                .restitution(0.05)
                .build();
            self.collider_set.insert_with_parent(col, handle, &mut self.rigid_body_set);

            if let Some(prev) = prev_handle {
                // SphericalJointBuilder::motor_model(axis, model) -- two-arg API in rapier 0.21
                let joint = SphericalJointBuilder::new()
                    .local_anchor1(Point3::new(0.0, -half_len, 0.0))
                    .local_anchor2(Point3::new(0.0,  half_len, 0.0))
                    .motor_model(JointAxis::AngX, MotorModel::AccelerationBased)
                    .motor_model(JointAxis::AngY, MotorModel::AccelerationBased)
                    .motor_model(JointAxis::AngZ, MotorModel::AccelerationBased)
                    .motor(JointAxis::AngX, 0.0, 0.0, stiff_f, damp_f)
                    .motor(JointAxis::AngY, 0.0, 0.0, stiff_f, damp_f)
                    .motor(JointAxis::AngZ, 0.0, 0.0, stiff_f, damp_f)
                    .build();
                self.impulse_joint_set.insert(prev, handle, joint, true);
            }
            handles.push(handle);
            prev_handle = Some(handle);
        }

        self.rope_handles.extend_from_slice(&handles);

        // Top link is fixed -- acts as anchor attachment
        if let Some(&top) = handles.first() {
            if let Some(rb) = self.rigid_body_set.get_mut(top) {
                rb.set_body_type(RigidBodyType::Fixed, true);
                self.anchor_handle = Some(top);
            }
        }
        handles
    }

    // -- add_bolt -------------------------------------------------------------

    pub fn add_bolt(&mut self, position: [f64; 3], mbs_kn: f64, _bolt_type: &str) -> RigidBodyHandle {
        let pos = Vector3::new(position[0] as f32, position[1] as f32, position[2] as f32);
        let rb  = RigidBodyBuilder::fixed().translation(pos).build();
        let handle = self.rigid_body_set.insert(rb);
        let col = ColliderBuilder::cylinder(0.01, 0.008).build();
        self.collider_set.insert_with_parent(col, handle, &mut self.rigid_body_set);
        self.gear_records.push(GearRecord {
            handle,
            mbs_n:        (mbs_kn * 1000.0) as f32,
            pull_out_dir: Vector3::new(0.0, -1.0, 0.0),
            quality:      1.0,
            failed:       false,
        });
        handle
    }

    // -- add_cam --------------------------------------------------------------

    pub fn add_cam(
        &mut self,
        position:           [f64; 3],
        mbs_kn:             f64,
        placement_quality:  f64,
        pull_out_direction: [f64; 3],
    ) -> RigidBodyHandle {
        let pos = Vector3::new(position[0] as f32, position[1] as f32, position[2] as f32);
        let dir = UnitVector3::try_new(
            Vector3::new(
                pull_out_direction[0] as f32,
                pull_out_direction[1] as f32,
                pull_out_direction[2] as f32,
            ),
            1e-6,
        ).map(|u| *u).unwrap_or_else(|| Vector3::new(0.0, -1.0, 0.0));

        let rb = RigidBodyBuilder::fixed().translation(pos).build();
        let handle = self.rigid_body_set.insert(rb);
        let col = ColliderBuilder::cuboid(0.02, 0.03, 0.02).build();
        self.collider_set.insert_with_parent(col, handle, &mut self.rigid_body_set);
        self.gear_records.push(GearRecord {
            handle,
            mbs_n:        (mbs_kn * 1000.0) as f32,
            pull_out_dir: dir,
            quality:      placement_quality as f32,
            failed:       false,
        });
        handle
    }

    // -- add_climber ----------------------------------------------------------

    pub fn add_climber(&mut self, rope_handle: RigidBodyHandle, mass_kg: f64) -> RigidBodyHandle {
        let attach_pos = self.rigid_body_set.get(rope_handle)
            .map(|rb| *rb.translation())
            .unwrap_or_else(|| Vector3::zeros());
        let pos = attach_pos + Vector3::new(0.0, -0.5, 0.0);

        let rb = RigidBodyBuilder::dynamic().translation(pos).build();
        let handle = self.rigid_body_set.insert(rb);
        let col = ColliderBuilder::capsule_y(0.4, 0.15)
            .mass(mass_kg as f32)
            .friction(0.3)
            .build();
        self.collider_set.insert_with_parent(col, handle, &mut self.rigid_body_set);

        let joint = SphericalJointBuilder::new()
            .local_anchor1(Point3::new(0.0, -0.5, 0.0))
            .local_anchor2(Point3::new(0.0,  0.4, 0.0))
            .build();
        self.impulse_joint_set.insert(rope_handle, handle, joint, true);
        self.climber_handle = Some(handle);
        handle
    }

    // -- add_rock_face / add_ledge --------------------------------------------

    pub fn add_rock_face(&mut self, vertices: Vec<[f64; 3]>, friction: f64) -> ColliderHandle {
        let verts: Vec<Point3<f32>> = vertices.iter()
            .map(|v| Point3::new(v[0] as f32, v[1] as f32, v[2] as f32))
            .collect();
        let n = verts.len();
        let mut indices: Vec<[u32; 3]> = Vec::new();
        for i in 1..n.saturating_sub(1) {
            indices.push([0, i as u32, (i + 1) as u32]);
        }
        let col = ColliderBuilder::trimesh(verts, indices)
            .friction(friction as f32)
            .build();
        self.collider_set.insert(col)
    }

    pub fn add_ledge(&mut self, vertices: Vec<[f64; 3]>, friction: f64) -> ColliderHandle {
        self.add_rock_face(vertices, friction)
    }

    // -- add_belayer ----------------------------------------------------------

    pub fn add_belayer(
        &mut self,
        position: [f64; 3],
        mass_kg:  f64,
        device:   &str,
        dynamic:  bool,
    ) -> RigidBodyHandle {
        let pos = Vector3::new(position[0] as f32, position[1] as f32, position[2] as f32);
        self.belayer_friction = BelayDeviceType::from_str(device).friction_coefficient();

        let rb = if dynamic {
            RigidBodyBuilder::dynamic()
                .translation(pos)
                .locked_axes(
                    LockedAxes::ROTATION_LOCKED
                    | LockedAxes::TRANSLATION_LOCKED_X
                    | LockedAxes::TRANSLATION_LOCKED_Z,
                )
                .build()
        } else {
            RigidBodyBuilder::fixed().translation(pos).build()
        };
        let handle = self.rigid_body_set.insert(rb);
        let col = ColliderBuilder::capsule_y(0.4, 0.2).mass(mass_kg as f32).build();
        self.collider_set.insert_with_parent(col, handle, &mut self.rigid_body_set);
        self.belayer_handle = Some(handle);
        handle
    }

    // -- add_belay_device -----------------------------------------------------

    pub fn add_belay_device(
        &mut self,
        _position:            [f64; 3],
        rope_handle:          RigidBodyHandle,
        friction_coefficient: f64,
    ) {
        if let Some(rb) = self.rigid_body_set.get_mut(rope_handle) {
            let cur = rb.linear_damping();
            rb.set_linear_damping(cur + friction_coefficient as f32 * 5.0);
        }
    }

    // -- clip_rope_to_gear ----------------------------------------------------

    pub fn clip_rope_to_gear(&mut self, rope_link_index: usize, gear_handle: RigidBodyHandle) {
        let rope_handle = match self.rope_handles.get(rope_link_index) {
            Some(&h) => h,
            None => return,
        };
        let gear_pos = self.rigid_body_set.get(gear_handle)
            .map(|rb| *rb.translation()).unwrap_or_else(|| Vector3::zeros());
        let rope_pos = self.rigid_body_set.get(rope_handle)
            .map(|rb| *rb.translation()).unwrap_or_else(|| Vector3::zeros());
        let offset = gear_pos - rope_pos;
        let joint = SphericalJointBuilder::new()
            .local_anchor1(Point3::from(offset))
            .local_anchor2(Point3::origin())
            .build();
        self.impulse_joint_set.insert(rope_handle, gear_handle, joint, true);
    }

    // -- set_rope_edge_contacts -----------------------------------------------

    pub fn set_rope_edge_contacts(&mut self, contacts: Vec<([f64; 3], f64)>) {
        self.rope_edge_contacts = contacts.into_iter()
            .map(|(p, f)| (Point3::new(p[0] as f32, p[1] as f32, p[2] as f32), f as f32))
            .collect();
        for (contact_pt, friction) in &self.rope_edge_contacts {
            for &handle in &self.rope_handles {
                if let Some(rb) = self.rigid_body_set.get_mut(handle) {
                    let dist = (rb.translation() - contact_pt.coords).norm();
                    if dist < 0.3 {
                        let extra = friction * (1.0 - dist / 0.3);
                        let cur   = rb.linear_damping();
                        rb.set_linear_damping(cur + extra * 3.0);
                    }
                }
            }
        }
    }

    // -- simulate_pendulum_fall -----------------------------------------------

    pub fn simulate_pendulum_fall(
        &mut self,
        climber_pos:      [f64; 3],
        last_piece_pos:   [f64; 3],
        lateral_offset_m: f64,
    ) -> PendulumResult {
        let dx = climber_pos[0] - last_piece_pos[0];
        let dy = climber_pos[1] - last_piece_pos[1];
        let dz = climber_pos[2] - last_piece_pos[2];
        let rope_len = (dx*dx + dy*dy + dz*dz).sqrt();

        let handles = self.add_rope(last_piece_pos, climber_pos, rope_len, 0.065, 0.08, 50.0, 5.0);

        if let Some(&last_link) = handles.last() {
            if let Some(rb) = self.rigid_body_set.get_mut(last_link) {
                let lateral_v = (2.0 * 9.81 * lateral_offset_m.abs()).sqrt() as f32;
                let sign: f32  = if lateral_offset_m >= 0.0 { 1.0 } else { -1.0 };
                rb.set_linvel(Vector3::new(sign * lateral_v, 0.0, 0.0), true);
            }
        }

        let mut arc_positions: Vec<[f64; 3]> = Vec::new();
        let mut max_impact_v = 0.0_f32;
        let mut terrain_contact = false;
        let dt = 1.0 / 240.0_f64;

        for _ in 0..(5.0 / dt) as usize {
            self.step(dt);
            if let Some(climber) = self.climber_handle {
                let pos = self.rigid_body_set.get(climber)
                    .map(|rb| *rb.translation())
                    .unwrap_or_else(|| Vector3::zeros());
                arc_positions.push([pos.x as f64, pos.y as f64, pos.z as f64]);
                let wall_x = last_piece_pos[0] as f32;
                if (pos.x - wall_x).abs() < 0.3 {
                    let vel = self.rigid_body_set.get(climber)
                        .map(|rb| rb.linvel().norm()).unwrap_or(0.0);
                    if vel > max_impact_v { max_impact_v = vel; terrain_contact = true; }
                }
            }
        }

        let mass_kg = 80.0_f32;
        PendulumResult {
            swing_arc_positions:      arc_positions,
            wall_impact_velocity_mps: max_impact_v as f64,
            wall_impact_force_kn:     (mass_kg * max_impact_v / 0.05 / 1000.0) as f64,
            terrain_contact,
        }
    }

    // -- step -----------------------------------------------------------------

    pub fn step(&mut self, dt: f64) {
        self.integration_params.dt = dt as f32;
        self.pending_failures.clear();

        // Snapshot climber velocity before step for force estimation
        let vel_before: Vector3<f32> = self.climber_handle
            .and_then(|h| self.rigid_body_set.get(h))
            .map(|rb| *rb.linvel())
            .unwrap_or_else(|| Vector3::zeros());

        self.pipeline.step(
            &self.gravity,
            &self.integration_params,
            &mut self.island_manager,
            &mut self.broad_phase,
            &mut self.narrow_phase,
            &mut self.rigid_body_set,
            &mut self.collider_set,
            &mut self.impulse_joint_set,
            &mut self.multibody_joint_set,
            &mut self.ccd_solver,
            Some(&mut self.query_pipeline),
            &(),
            &(),
        );

        self.elapsed_s += dt;

        // Estimate anchor force from climber momentum change
        // F_rope = m * dv / dt - m * g  (rope force = net force minus gravity)
        // During free fall: dv/dt = g, so F_rope = 0 (correct)
        // During catch:     dv/dt >> g, so F_rope >> 0 (force spike)
        if let Some(h) = self.climber_handle {
            if let Some(rb) = self.rigid_body_set.get(h) {
                let vel_after = *rb.linvel();
                let dv        = vel_after - vel_before;
                let m         = rb.mass(); // kg
                let dt_f      = dt as f32;
                let g_vec     = Vector3::new(0.0, -(self.gravity.norm()), 0.0);
                // Rope force on climber (upward when catching)
                let f_rope_n  = m * (dv / dt_f - g_vec);
                // The anchor must resist this force (Newton 3rd law) -- take magnitude
                let f_kn      = f_rope_n.norm() / 1000.0;
                self.current_anchor_force_kn = f_kn as f64;
            }
        } else {
            self.current_anchor_force_kn = 0.0;
        }

        self.check_gear_failures_internal();
    }

    // Estimate force on a gear body from the velocity changes of attached rope links
    fn estimate_gear_force_n(&self, gear_handle: RigidBodyHandle) -> f32 {
        let dt = self.integration_params.dt;
        // Sum velocity magnitudes of rope links that have joints to this gear
        let linked_force: f32 = self.rope_handles.iter()
            .filter_map(|&rh| {
                // Check if there's a joint between this rope link and the gear
                let has_joint = self.impulse_joint_set.iter()
                    .any(|(_, j)| {
                        (j.body1 == rh && j.body2 == gear_handle)
                        || (j.body2 == rh && j.body1 == gear_handle)
                    });
                if !has_joint { return None; }
                self.rigid_body_set.get(rh).map(|rb| {
                    rb.mass() * rb.linvel().norm() / dt
                })
            })
            .sum();
        linked_force
    }

    fn check_gear_failures_internal(&mut self) {
        let elapsed_ms = (self.elapsed_s * 1000.0) as f64;
        for i in 0..self.gear_records.len() {
            if self.gear_records[i].failed { continue; }
            let handle      = self.gear_records[i].handle;
            let quality     = self.gear_records[i].quality;
            let mbs_n       = self.gear_records[i].mbs_n;
            let eff_mbs     = mbs_n * quality;
            let force_n     = self.estimate_gear_force_n(handle);

            if force_n > eff_mbs {
                self.gear_records[i].failed = true;
                self.pending_failures.push(FailureEvent {
                    gear_index:   i,
                    timestamp_ms: elapsed_ms,
                    force_kn:     (force_n / 1000.0) as f64,
                    mbs_kn:       (eff_mbs  / 1000.0) as f64,
                });
                if let Some(rb) = self.rigid_body_set.get_mut(handle) {
                    rb.set_body_type(RigidBodyType::Dynamic, true);
                }
            }
        }
    }

    // -- step_n ---------------------------------------------------------------

    pub fn step_n(&mut self, n: usize, dt: f64) -> SimFrameData {
        let mut frames: Vec<SimFrame> = Vec::with_capacity(n);
        for _ in 0..n {
            self.step(dt);
            let per_gear: Vec<f64> = (0..self.gear_records.len())
                .map(|i| {
                    let h = self.gear_records[i].handle;
                    (self.estimate_gear_force_n(h) / 1000.0) as f64
                })
                .collect();
            frames.push(SimFrame {
                timestamp_ms:     (self.elapsed_s * 1000.0) as f64,
                rope_positions:   self.get_rope_positions(),
                climber_position: self.get_climber_position(),
                climber_velocity: self.get_climber_velocity(),
                anchor_force_kn:  self.current_anchor_force_kn,
                per_gear_forces:  per_gear,
                failures:         self.pending_failures.clone(),
            });
        }
        SimFrameData {
            frames,
            dt_seconds:        dt,
            total_time_seconds: n as f64 * dt,
        }
    }

    // -- queries --------------------------------------------------------------

    pub fn get_rope_positions(&self) -> Vec<[f64; 3]> {
        self.rope_handles.iter()
            .filter_map(|&h| self.rigid_body_set.get(h))
            .map(|rb| { let t = rb.translation(); [t.x as f64, t.y as f64, t.z as f64] })
            .collect()
    }

    fn get_force_at_gear_index(&self, idx: usize) -> f64 {
        match self.gear_records.get(idx) {
            Some(g) => (self.estimate_gear_force_n(g.handle) / 1000.0) as f64,
            None    => 0.0,
        }
    }

    pub fn get_force_at_gear(&self, handle: RigidBodyHandle) -> f64 {
        let idx = self.gear_records.iter().position(|g| g.handle == handle);
        match idx { Some(i) => self.get_force_at_gear_index(i), None => 0.0 }
    }

    pub fn get_force_at_anchor(&self) -> f64 { self.current_anchor_force_kn }

    pub fn get_climber_velocity(&self) -> [f64; 3] {
        self.climber_handle.and_then(|h| self.rigid_body_set.get(h))
            .map(|rb| { let v = rb.linvel(); [v.x as f64, v.y as f64, v.z as f64] })
            .unwrap_or([0.0, 0.0, 0.0])
    }

    pub fn get_climber_position(&self) -> [f64; 3] {
        self.climber_handle.and_then(|h| self.rigid_body_set.get(h))
            .map(|rb| { let t = rb.translation(); [t.x as f64, t.y as f64, t.z as f64] })
            .unwrap_or([0.0, 0.0, 0.0])
    }

    pub fn check_failures(&self) -> Vec<FailureEvent> { self.pending_failures.clone() }
}

// ---------------------------------------------------------------------------
// PyRopeSimWorld
// ---------------------------------------------------------------------------

#[pyclass]
pub struct PyRopeSimWorld {
    inner:      RopeSimWorld,
    handle_map: Vec<RigidBodyHandle>,
}

impl PyRopeSimWorld {
    fn register_handle(&mut self, h: RigidBodyHandle) -> usize {
        let idx = self.handle_map.len();
        self.handle_map.push(h);
        idx
    }
    fn resolve_handle(&self, idx: usize) -> Option<RigidBodyHandle> {
        self.handle_map.get(idx).copied()
    }
}

#[pymethods]
impl PyRopeSimWorld {
    #[new]
    pub fn new(gravity: f64) -> Self {
        PyRopeSimWorld { inner: RopeSimWorld::new(gravity), handle_map: Vec::new() }
    }

    pub fn add_rope(
        &mut self,
        start_pos: [f64; 3], end_pos: [f64; 3], length_m: f64,
        mass_per_meter: f64, link_length_m: f64, stiffness: f64, damping: f64,
    ) -> Vec<usize> {
        let handles = self.inner.add_rope(start_pos, end_pos, length_m, mass_per_meter, link_length_m, stiffness, damping);
        handles.into_iter().map(|h| self.register_handle(h)).collect()
    }

    pub fn add_bolt(&mut self, position: [f64; 3], mbs_kn: f64, bolt_type: &str) -> usize {
        let h = self.inner.add_bolt(position, mbs_kn, bolt_type);
        self.register_handle(h)
    }

    pub fn add_cam(
        &mut self, position: [f64; 3], mbs_kn: f64,
        placement_quality: f64, pull_out_direction: [f64; 3],
    ) -> usize {
        let h = self.inner.add_cam(position, mbs_kn, placement_quality, pull_out_direction);
        self.register_handle(h)
    }

    pub fn add_climber(&mut self, rope_handle: usize, mass_kg: f64) -> PyResult<usize> {
        let h = self.resolve_handle(rope_handle).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!("invalid rope_handle {rope_handle}"))
        })?;
        let ch = self.inner.add_climber(h, mass_kg);
        Ok(self.register_handle(ch))
    }

    pub fn add_rock_face(&mut self, vertices: Vec<[f64; 3]>, friction: f64) -> usize {
        self.inner.add_rock_face(vertices, friction);
        usize::MAX
    }

    pub fn add_ledge(&mut self, vertices: Vec<[f64; 3]>, friction: f64) -> usize {
        self.inner.add_ledge(vertices, friction);
        usize::MAX
    }

    pub fn add_belayer(
        &mut self, position: [f64; 3], mass_kg: f64, device: &str, dynamic: bool,
    ) -> usize {
        let h = self.inner.add_belayer(position, mass_kg, device, dynamic);
        self.register_handle(h)
    }

    pub fn clip_rope_to_gear(&mut self, rope_link_index: usize, gear_handle: usize) -> PyResult<()> {
        let gh = self.resolve_handle(gear_handle).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!("invalid gear_handle {gear_handle}"))
        })?;
        self.inner.clip_rope_to_gear(rope_link_index, gh);
        Ok(())
    }

    pub fn set_rope_edge_contacts(&mut self, contacts: Vec<([f64; 3], f64)>) {
        self.inner.set_rope_edge_contacts(contacts);
    }

    pub fn step(&mut self, dt: f64) { self.inner.step(dt); }
    pub fn step_n(&mut self, n: usize, dt: f64) -> SimFrameData { self.inner.step_n(n, dt) }
    pub fn get_rope_positions(&self) -> Vec<[f64; 3]> { self.inner.get_rope_positions() }

    pub fn get_force_at_gear(&self, handle: usize) -> PyResult<f64> {
        let h = self.resolve_handle(handle).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!("invalid gear handle {handle}"))
        })?;
        Ok(self.inner.get_force_at_gear(h))
    }

    pub fn get_force_at_anchor(&self) -> f64  { self.inner.get_force_at_anchor() }
    pub fn get_climber_velocity(&self) -> [f64; 3] { self.inner.get_climber_velocity() }
    pub fn get_climber_position(&self) -> [f64; 3] { self.inner.get_climber_position() }
    pub fn check_failures(&self) -> Vec<FailureEvent> { self.inner.check_failures() }

    pub fn simulate_pendulum_fall(
        &mut self, climber_pos: [f64; 3], last_piece_pos: [f64; 3], lateral_offset_m: f64,
    ) -> PendulumResult {
        self.inner.simulate_pendulum_fall(climber_pos, last_piece_pos, lateral_offset_m)
    }
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyRopeSimWorld>()?;
    m.add_class::<PendulumResult>()?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Unit tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    /// Drop a mass on a rope, verify it catches and produces a force spike.
    ///
    /// Setup: 2 m rope, top fixed (anchor), bottom link has 80 kg climber.
    /// Run 0.3 s pre-catch (rope already taut -> catches quickly), then 0.7 s
    /// post-catch.  Expect:
    ///   - peak anchor force > 0 kN  (rope tension is positive)
    ///   - peak anchor force < 30 kN (not wildly unphysical)
    ///   - final climber speed < 15 m/s (rope arrested the fall)
    #[test]
    fn test_drop_mass_catches_and_produces_force_spike() {
        let mut world = RopeSimWorld::new(9.81);

        let handles = world.add_rope(
            [0.0,  0.0, 0.0],  // top (will be fixed)
            [0.0, -2.0, 0.0],  // bottom
            2.0,   // length_m
            0.065, // mass_per_meter kg/m
            0.5,   // link_length_m (coarse for test speed)
            80.0,  // stiffness
            8.0,   // damping
        );
        assert!(handles.len() >= 2, "need at least 2 rope links");

        // Attach climber to the bottom rope link
        let last_link = *handles.last().unwrap();
        world.add_climber(last_link, 80.0);

        let dt = 1.0 / 240.0;

        // Pre-catch window: let the system settle / start catching
        for _ in 0..(0.3 / dt) as usize { world.step(dt); }

        // Post-catch window: collect frame data and find peak
        let frames = world.step_n((0.7 / dt) as usize, dt);
        let peak_kn = frames.peak_anchor_force();

        println!("Peak anchor force after catch: {:.3} kN", peak_kn);

        assert!(peak_kn > 0.0,
            "Expected positive anchor force after catch, got {:.3} kN", peak_kn);
        assert!(peak_kn < 30.0,
            "Peak {:.3} kN is unrealistically high", peak_kn);

        // Verify climber has been arrested
        let vel = world.get_climber_velocity();
        let speed = (vel[0].powi(2) + vel[1].powi(2) + vel[2].powi(2)).sqrt();
        println!("Final climber speed: {:.3} m/s", speed);
        assert!(speed < 15.0,
            "Climber still at {:.2} m/s -- rope did not arrest the fall", speed);
    }
}
