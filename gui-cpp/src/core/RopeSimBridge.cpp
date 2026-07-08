// gui-cpp/src/core/RopeSimBridge.cpp

#include "core/RopeSimBridge.h"

#include <ropesim.h>

RopeSimBridge::RopeSimBridge() = default;

RopeSimBridge::~RopeSimBridge() { destroyWorld(); }

// ── Fall analytics ──────────────────────────────────────────────────────────

double RopeSimBridge::computeFallFactor(double fallDist, double ropeOut) const {
    return ropesim_compute_fall_factor(fallDist, ropeOut);
}

double RopeSimBridge::computeImpactForce(double massKg, double fallFactor,
                                         double stiffness, double belayFriction,
                                         bool wet, double tempC) const {
    return ropesim_compute_impact_force(massKg, fallFactor, stiffness,
                                        belayFriction, wet ? 1 : 0, tempC);
}

std::vector<double> RopeSimBridge::computeForceCurve(double massKg, double fallDist,
                                                     double ropeOut, double stiffness,
                                                     double damping, double dtMs) const {
    std::vector<double> buf(4096);
    const int n = ropesim_compute_force_curve(massKg, fallDist, ropeOut, stiffness,
                                              damping, dtMs, buf.data(),
                                              static_cast<int>(buf.size()));
    buf.resize(n > 0 ? static_cast<size_t>(n) : 0);
    return buf;
}

// ── Anchor ──────────────────────────────────────────────────────────────────

std::pair<double, double> RopeSimBridge::slidingXDistribution(double loadKn,
                                                              double angleDeg) const {
    double a = 0.0, b = 0.0;
    ropesim_sliding_x_distribution(loadKn, angleDeg, &a, &b);
    return {a, b};
}

std::pair<double, double> RopeSimBridge::quadDistribution(double loadKn, double angleDeg,
                                                          bool extensionLimiter) const {
    double a = 0.0, b = 0.0;
    ropesim_quad_distribution(loadKn, angleDeg, extensionLimiter ? 1 : 0, &a, &b);
    return {a, b};
}

// ── World management ────────────────────────────────────────────────────────

void RopeSimBridge::createWorld(double gravity) {
    destroyWorld();
    m_world = ropesim_world_create(gravity);
}

void RopeSimBridge::destroyWorld() {
    if (m_world) {
        ropesim_world_destroy(m_world);
        m_world = nullptr;
    }
}

int RopeSimBridge::addRope(glm::vec3 start, glm::vec3 end, double lengthM,
                           double massPerM, double linkLen, double stiffness,
                           double damping) {
    if (!m_world) return -1;
    const double s[3] = {start.x, start.y, start.z};
    const double e[3] = {end.x, end.y, end.z};
    return ropesim_world_add_rope(m_world, s, e, lengthM, massPerM, linkLen,
                                  stiffness, damping);
}

int RopeSimBridge::addBolt(glm::vec3 pos, double mbsKn, int boltType) {
    if (!m_world) return -1;
    const double p[3] = {pos.x, pos.y, pos.z};
    return ropesim_world_add_bolt(m_world, p, mbsKn, boltType);
}

int RopeSimBridge::addCam(glm::vec3 pos, double mbsKn, double quality,
                          glm::vec3 pullDir) {
    if (!m_world) return -1;
    const double p[3] = {pos.x, pos.y, pos.z};
    const double d[3] = {pullDir.x, pullDir.y, pullDir.z};
    return ropesim_world_add_cam(m_world, p, mbsKn, quality, d);
}

int RopeSimBridge::addClimber(int ropeHandle, double massKg) {
    if (!m_world) return -1;
    return ropesim_world_add_climber(m_world, ropeHandle, massKg);
}

int RopeSimBridge::addLedge(const std::vector<glm::vec3>& verts, double friction) {
    if (!m_world || verts.size() < 3) return -1;
    std::vector<double> flat;
    flat.reserve(verts.size() * 3);
    for (const auto& v : verts) {
        flat.push_back(v.x);
        flat.push_back(v.y);
        flat.push_back(v.z);
    }
    return ropesim_world_add_ledge(m_world, flat.data(),
                                   static_cast<int>(verts.size()), friction);
}

int RopeSimBridge::addBelayer(glm::vec3 pos, double massKg, int deviceType,
                              bool dynamic) {
    if (!m_world) return -1;
    const double p[3] = {pos.x, pos.y, pos.z};
    return ropesim_world_add_belayer(m_world, p, massKg, deviceType, dynamic ? 1 : 0);
}

void RopeSimBridge::clipRope(int ropeLink, int gearHandle) {
    if (m_world) ropesim_world_clip_rope(m_world, ropeLink, gearHandle);
}

void RopeSimBridge::step(double dt) {
    if (m_world) ropesim_world_step(m_world, dt);
}

// ── Queries ─────────────────────────────────────────────────────────────────

std::vector<glm::vec3> RopeSimBridge::getRopePositions() const {
    std::vector<glm::vec3> out;
    if (!m_world) return out;
    std::vector<double> buf(4096 * 3);
    const int n = ropesim_world_get_rope_positions(m_world, buf.data(),
                                                   static_cast<int>(buf.size()));
    out.reserve(n / 3);
    for (int i = 0; i + 2 < n; i += 3) {
        out.emplace_back(static_cast<float>(buf[i]),
                         static_cast<float>(buf[i + 1]),
                         static_cast<float>(buf[i + 2]));
    }
    return out;
}

double RopeSimBridge::getForceAtGear(int handle) const {
    return m_world ? ropesim_world_get_force_at_gear(m_world, handle) : 0.0;
}

double RopeSimBridge::getAnchorForce() const {
    return m_world ? ropesim_world_get_anchor_force(m_world) : 0.0;
}

glm::vec3 RopeSimBridge::getClimberPosition() const {
    double p[3] = {0.0, 0.0, 0.0};
    if (m_world) ropesim_world_get_climber_position(m_world, p);
    return {static_cast<float>(p[0]), static_cast<float>(p[1]),
            static_cast<float>(p[2])};
}

// ── Rappel / haul / degradation ─────────────────────────────────────────────

double RopeSimBridge::staticElongation(double staticPct, double loadKg,
                                       double lengthM) const {
    return ropesim_static_elongation(staticPct, loadKg, lengthM);
}

double RopeSimBridge::rappelLoad(double massKg, double deviceFriction,
                                 double speedMps) const {
    return ropesim_rappel_load(massKg, deviceFriction, speedMps);
}

std::pair<double, double> RopeSimBridge::haulForces(int systemType, double loadKg,
                                                    double friction) const {
    double ma = 0.0, effort = 0.0;
    ropesim_haul_forces(systemType, loadKg, friction, &ma, &effort);
    return {ma, effort};
}

RopeSimBridge::DegradedRope RopeSimBridge::degradeRope(double baseStiffness,
                                                       int fallsTaken,
                                                       int ratedFalls) const {
    DegradedRope r{baseStiffness, 0.0, 0};
    ropesim_degrade_rope(baseStiffness, fallsTaken, ratedFalls, &r.stiffness,
                         &r.impactForce, &r.retirementWarning);
    return r;
}

// ── New v3 ──────────────────────────────────────────────────────────────────

std::pair<double, double> RopeSimBridge::twinRopeForces(double stiffA, double stiffB,
                                                        double massKg, double ff,
                                                        double interFriction) const {
    double a = 0.0, b = 0.0;
    ropesim_twin_rope_forces(stiffA, stiffB, massKg, ff, interFriction, &a, &b);
    return {a, b};
}

std::pair<double, double> RopeSimBridge::halfRopeForces(double stiffA, double stiffB,
                                                        double massKg, double ff,
                                                        int activeRope) const {
    double a = 0.0, b = 0.0;
    ropesim_half_rope_forces(stiffA, stiffB, massKg, ff, activeRope, &a, &b);
    return {a, b};
}

double RopeSimBridge::knotStrengthFactor(int knotType, double diamMm) const {
    return ropesim_knot_strength_factor(knotType, diamMm);
}

double RopeSimBridge::cordAnchorStrength(double cordMbsKn, int knotType,
                                         int numStrands, double diamMm) const {
    return ropesim_cord_anchor_strength(cordMbsKn, knotType, numStrands, diamMm);
}

double RopeSimBridge::abrasionIncrement(int rockType, double forceKn,
                                        double durationS, double velocityMps) const {
    return ropesim_abrasion_increment(rockType, forceKn, durationS, velocityMps);
}

RopeSimBridge::SheathUpdate RopeSimBridge::accumulateSheathWear(double currentScore,
                                                                double increment,
                                                                double sheathPct) const {
    SheathUpdate u{0.0, 0, false};
    int retire = 0;
    u.score = ropesim_accumulate_sheath_wear(currentScore, increment, sheathPct,
                                             &u.rating, &retire);
    u.needsRetirement = retire != 0;
    return u;
}

std::pair<double, double> RopeSimBridge::fallProbability(double routeGrade,
                                                         double climberGrade,
                                                         int style, int attempts) const {
    double p = 0.0, ef = 0.0;
    ropesim_fall_probability(routeGrade, climberGrade, style, attempts, &p, &ef);
    return {p, ef};
}

double RopeSimBridge::dynamicBelayReduction(double climberMassKg, double belayerMassKg,
                                            int deviceType, bool standing,
                                            bool softCatch) const {
    return ropesim_dynamic_belay_reduction(climberMassKg, belayerMassKg, deviceType,
                                           standing ? 1 : 0, softCatch ? 1 : 0);
}

int RopeSimBridge::abiVersion() { return ropesim_abi_version(); }
