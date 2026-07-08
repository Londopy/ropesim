// gui-cpp/src/core/RopeSimBridge.h
//
// C++ wrapper around the raw ropesim C FFI (include/ropesim.h).
// Manages the opaque world pointer and translates between C++ types
// (std::vector, glm::vec3) and C arrays.
//
// All GUI code calls RopeSimBridge — nothing calls ropesim.h directly.

#pragma once

#include <glm/vec3.hpp>
#include <utility>
#include <vector>

class RopeSimBridge {
public:
    RopeSimBridge();
    ~RopeSimBridge(); // destroys the world if one was created

    RopeSimBridge(const RopeSimBridge&) = delete;
    RopeSimBridge& operator=(const RopeSimBridge&) = delete;

    // ── Fall analytics (no world needed) ────────────────────────────────
    double computeFallFactor(double fallDist, double ropeOut) const;
    double computeImpactForce(double massKg, double fallFactor,
                              double stiffness, double belayFriction,
                              bool wet, double tempC) const;
    std::vector<double> computeForceCurve(double massKg, double fallDist,
                                          double ropeOut, double stiffness,
                                          double damping, double dtMs) const;

    // ── Anchor ──────────────────────────────────────────────────────────
    std::pair<double, double> slidingXDistribution(double loadKn, double angleDeg) const;
    std::pair<double, double> quadDistribution(double loadKn, double angleDeg,
                                               bool extensionLimiter) const;

    // ── World management ────────────────────────────────────────────────
    void createWorld(double gravity = 9.81);
    void destroyWorld();
    bool hasWorld() const { return m_world != nullptr; }

    int addRope(glm::vec3 start, glm::vec3 end, double lengthM,
                double massPerM, double linkLen, double stiffness, double damping);
    int addBolt(glm::vec3 pos, double mbsKn, int boltType);
    int addCam(glm::vec3 pos, double mbsKn, double quality, glm::vec3 pullDir);
    int addClimber(int ropeHandle, double massKg);
    int addLedge(const std::vector<glm::vec3>& verts, double friction);
    int addBelayer(glm::vec3 pos, double massKg, int deviceType, bool dynamic);
    void clipRope(int ropeLink, int gearHandle);
    void step(double dt);

    // ── Queries ─────────────────────────────────────────────────────────
    std::vector<glm::vec3> getRopePositions() const;
    double getForceAtGear(int handle) const;
    double getAnchorForce() const;
    glm::vec3 getClimberPosition() const;

    // ── Rappel / haul / degradation ─────────────────────────────────────
    double staticElongation(double staticPct, double loadKg, double lengthM) const;
    double rappelLoad(double massKg, double deviceFriction, double speedMps) const;
    std::pair<double, double> haulForces(int systemType, double loadKg,
                                         double friction) const; // (actualMA, effort N)
    struct DegradedRope {
        double stiffness;
        double impactForce;
        int retirementWarning; // 0 fine, 1 inspect, 2 retire
    };
    DegradedRope degradeRope(double baseStiffness, int fallsTaken, int ratedFalls) const;

    // ── New v3 ──────────────────────────────────────────────────────────
    std::pair<double, double> twinRopeForces(double stiffA, double stiffB,
                                             double massKg, double ff,
                                             double interFriction) const;
    std::pair<double, double> halfRopeForces(double stiffA, double stiffB,
                                             double massKg, double ff,
                                             int activeRope) const;
    double knotStrengthFactor(int knotType, double diamMm) const;
    double cordAnchorStrength(double cordMbsKn, int knotType,
                              int numStrands, double diamMm) const;
    double abrasionIncrement(int rockType, double forceKn,
                             double durationS, double velocityMps) const;
    struct SheathUpdate {
        double score;
        int rating;          // RopesimSheathRating
        bool needsRetirement;
    };
    SheathUpdate accumulateSheathWear(double currentScore, double increment,
                                      double sheathPct) const;
    std::pair<double, double> fallProbability(double routeGrade, double climberGrade,
                                              int style, int attempts) const;
    double dynamicBelayReduction(double climberMassKg, double belayerMassKg,
                                 int deviceType, bool standing, bool softCatch) const;

    static int abiVersion();

private:
    void* m_world = nullptr;
};
