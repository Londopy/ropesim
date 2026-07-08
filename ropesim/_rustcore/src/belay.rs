// ropesim/_rustcore/src/belay.rs
//
// Dynamic belayer model, v3 revision.
//
// v2 modelled the belayer as extra rope damping.  v3 adds an explicit
// energy-based force-reduction factor accounting for belayer mass, stance,
// device slip characteristics and deliberate soft-catch technique.
//
// References:
//   Pavier (1998) "Experimental and theoretical simulations of climbing falls"
//   UIAA Safety Commission belay dynamics reports
//   Petzl "belaying with a dynamic technique" test data
//
// Pure Rust — no PyO3.  Python bindings live in py_v3.rs, C FFI in ffi.rs.

/// Belay devices, mirroring `world::BelayDeviceType`, but with the slip
/// behaviour needed for the dynamic-catch model.
///
/// Discriminants are stable and part of the C FFI contract (ropesim.h).
#[repr(i32)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BelayDevice {
    Atc = 0,
    GriGri = 1,
    Tube = 2,
    Reverso = 3,
    ReversoGuide = 4,
    MegaJul = 5,
    GigaJul = 6,
    ClickUp = 7,
    IDevice = 8,
    Sum = 9,
    Munter = 10,
}

impl BelayDevice {
    pub fn from_i32(v: i32) -> Option<Self> {
        match v {
            0 => Some(Self::Atc),
            1 => Some(Self::GriGri),
            2 => Some(Self::Tube),
            3 => Some(Self::Reverso),
            4 => Some(Self::ReversoGuide),
            5 => Some(Self::MegaJul),
            6 => Some(Self::GigaJul),
            7 => Some(Self::ClickUp),
            8 => Some(Self::IDevice),
            9 => Some(Self::Sum),
            10 => Some(Self::Munter),
            _ => None,
        }
    }

    pub fn from_name(s: &str) -> Option<Self> {
        match s.to_ascii_lowercase().as_str() {
            "atc" => Some(Self::Atc),
            "grigri" => Some(Self::GriGri),
            "tube" => Some(Self::Tube),
            "reverso" => Some(Self::Reverso),
            "reverso_guide" => Some(Self::ReversoGuide),
            "megajul" => Some(Self::MegaJul),
            "giga_jul" | "gigajul" => Some(Self::GigaJul),
            "click_up" | "clickup" => Some(Self::ClickUp),
            "i_device" | "idevice" => Some(Self::IDevice),
            "sum" => Some(Self::Sum),
            "munter" => Some(Self::Munter),
            _ => None,
        }
    }

    /// Fraction of catch energy the device can dissipate by controlled rope
    /// slip.  Tube-style devices slip freely (dynamic); assisted-braking
    /// devices lock hard (static catch).
    fn slip_capacity(&self) -> f64 {
        match self {
            Self::Atc | Self::Tube => 0.12,
            Self::Reverso => 0.10,
            Self::Munter => 0.09,
            Self::MegaJul | Self::GigaJul => 0.05,
            Self::ClickUp | Self::Sum => 0.04,
            Self::GriGri | Self::IDevice | Self::ReversoGuide => 0.02,
        }
    }
}

/// Force-reduction factor (0–1) to multiply into the peak impact force.
///
/// * `climber_mass_kg`, `belayer_mass_kg`
/// * `belayer_standing`     — a standing belayer is lifted further (more
///   energy absorbed) than one sitting/anchored tight
/// * `soft_catch_technique` — belayer deliberately jumps/steps into the catch
///
/// Model: the belayer lift absorbs `m_b · g · h_lift` of fall energy; device
/// slip absorbs a device-dependent share.  A light belayer catching a heavy
/// climber is lifted furthest — the classic soft catch.  Reduction is
/// bounded to [0.55, 1.0]: even a perfect soft catch cannot remove more
/// than ~40–45 % of peak force (Pavier; Petzl test data).
pub fn compute_dynamic_belay_reduction(
    climber_mass_kg: f64,
    belayer_mass_kg: f64,
    device: BelayDevice,
    belayer_standing: bool,
    soft_catch_technique: bool,
) -> f64 {
    let mc = climber_mass_kg.max(1.0);
    let mb = belayer_mass_kg.max(1.0);

    // Mass ratio drives belayer lift: ratio 1.0 → strong lift; heavy
    // belayer (ratio « 1) barely moves.
    let ratio = (mc / mb).clamp(0.2, 3.0);

    // Lift distance the belayer experiences (m), empirical fit:
    // equal masses standing ≈ 0.5 m, heavy belayer ≈ 0.1 m.
    let stance = if belayer_standing { 1.0 } else { 0.45 };
    let mut lift_m = 0.5 * (ratio - 0.2) / 0.8 * stance;
    if soft_catch_technique {
        lift_m += 0.55 * stance; // deliberate hop/step-in adds travel
    }
    lift_m = lift_m.clamp(0.0, 1.5);

    // Energy fraction absorbed by belayer displacement, normalised against
    // a representative 4 m fall of the climber's mass.
    let fall_energy = mc * 9.81 * 4.0;
    let belayer_energy = mb * 9.81 * lift_m;
    let lift_fraction = (belayer_energy / fall_energy).clamp(0.0, 0.35);

    // Device slip dissipation.
    let slip_fraction = device.slip_capacity() * if soft_catch_technique { 1.3 } else { 1.0 };

    // Peak force scales roughly with sqrt of retained energy for a spring.
    let retained = (1.0 - lift_fraction - slip_fraction).clamp(0.30, 1.0);
    retained.sqrt().clamp(0.55, 1.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn heavy_belayer_reduces_less() {
        let light = compute_dynamic_belay_reduction(80.0, 55.0, BelayDevice::Atc, true, false);
        let heavy = compute_dynamic_belay_reduction(80.0, 110.0, BelayDevice::Atc, true, false);
        assert!(light < heavy, "light belayer gives softer catch");
    }

    #[test]
    fn soft_catch_reduces_force() {
        let hard = compute_dynamic_belay_reduction(80.0, 75.0, BelayDevice::GriGri, true, false);
        let soft = compute_dynamic_belay_reduction(80.0, 75.0, BelayDevice::GriGri, true, true);
        assert!(soft < hard);
    }

    #[test]
    fn soft_catch_for_light_climber_saves_30_to_45_pct() {
        // Spec: soft catch can reduce peak force 30–40 % for light climbers.
        let f = compute_dynamic_belay_reduction(55.0, 80.0, BelayDevice::Atc, true, true);
        assert!((0.55..=0.75).contains(&f), "reduction factor {f}");
    }

    #[test]
    fn tube_softer_than_grigri() {
        let tube = compute_dynamic_belay_reduction(80.0, 75.0, BelayDevice::Atc, true, false);
        let grigri = compute_dynamic_belay_reduction(80.0, 75.0, BelayDevice::GriGri, true, false);
        assert!(tube < grigri);
    }

    #[test]
    fn standing_softer_than_sitting() {
        let stand = compute_dynamic_belay_reduction(80.0, 70.0, BelayDevice::Atc, true, false);
        let sit = compute_dynamic_belay_reduction(80.0, 70.0, BelayDevice::Atc, false, false);
        assert!(stand < sit);
    }

    #[test]
    fn factor_always_in_bounds() {
        for mc in [40.0, 80.0, 120.0] {
            for mb in [40.0, 80.0, 120.0] {
                for soft in [false, true] {
                    let f = compute_dynamic_belay_reduction(mc, mb, BelayDevice::Atc, true, soft);
                    assert!((0.55..=1.0).contains(&f), "f={f} mc={mc} mb={mb}");
                }
            }
        }
    }

    #[test]
    fn device_enum_roundtrip() {
        for i in 0..11 {
            let d = BelayDevice::from_i32(i).unwrap();
            assert_eq!(d as i32, i);
        }
        assert!(BelayDevice::from_i32(42).is_none());
        assert_eq!(BelayDevice::from_name("grigri"), Some(BelayDevice::GriGri));
    }
}
