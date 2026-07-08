// gui-cpp/tests/test_bridge.cpp
//
// FFI bridge smoke tests — no Qt event loop, just the C ABI through
// RopeSimBridge.  Run via ctest.

#include <cassert>
#include <cmath>
#include <cstdio>

#include "core/RopeSimBridge.h"

#define CHECK(cond)                                                       \
    do {                                                                  \
        if (!(cond)) {                                                    \
            std::fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, \
                         #cond);                                          \
            return 1;                                                     \
        }                                                                 \
    } while (0)

int main() {
    RopeSimBridge bridge;

    // ABI
    CHECK(RopeSimBridge::abiVersion() == 3);

    // Fall factor (EN 892 test geometry)
    const double ff = bridge.computeFallFactor(5.0, 2.82);
    CHECK(std::abs(ff - 1.77304964539) < 1e-6);
    CHECK(bridge.computeFallFactor(1.0, 0.0) < 0.0); // error sentinel

    // Impact force: wet > dry, cold > warm
    const double dry = bridge.computeImpactForce(80, 1.0, 24, 0.35, false, 15);
    const double wet = bridge.computeImpactForce(80, 1.0, 24, 0.35, true, 15);
    const double cold = bridge.computeImpactForce(80, 1.0, 24, 0.35, false, -15);
    CHECK(dry > 1.0 && dry < 15.0);
    CHECK(wet > dry);
    CHECK(cold > dry);

    // Force curve
    const auto curve = bridge.computeForceCurve(80, 4, 8, 24, 0.15, 1.0);
    CHECK(curve.size() > 10);
    double peak = 0;
    for (double v : curve) peak = std::max(peak, v);
    CHECK(peak > 2.0 && peak < 20.0);

    // Anchor
    const auto [xa, xb] = bridge.slidingXDistribution(10.0, 60.0);
    CHECK(std::abs(xa - xb) < 1e-9 && xa > 5.0);
    const auto [qa, qb] = bridge.quadDistribution(10.0, 120.0, true);
    CHECK(qa < xa * 2.0 && std::abs(qa - qb) < 1e-9);

    // v3 physics
    const auto [ta, tb] = bridge.twinRopeForces(20, 20, 80, 1.0, 0.2);
    CHECK(ta > 0 && std::abs(ta - tb) < 1e-9);
    const auto [ha, hb] = bridge.halfRopeForces(15, 15, 80, 1.0, 0);
    CHECK(ha > 2.0 && hb < 0.1 * ha);
    const double knot = bridge.knotStrengthFactor(0, 9.5);
    CHECK(knot > 0.7 && knot < 0.85);
    const double abr = bridge.abrasionIncrement(2, 5.0, 0.4, 2.0);
    CHECK(abr > 0.0 && abr < 0.1);
    const auto sheath = bridge.accumulateSheathWear(0.8, 0.1, 37.0);
    CHECK(sheath.needsRetirement && sheath.rating == 3);
    const auto [prob, ef] = bridge.fallProbability(12.0, 12.0, 0, 4);
    CHECK(prob > 0.3 && prob < 0.7 && std::abs(ef - prob * 4) < 1e-9);
    const double red = bridge.dynamicBelayReduction(55, 80, 0, true, true);
    CHECK(red >= 0.55 && red < 1.0);

    // Degradation
    const auto deg = bridge.degradeRope(24.0, 9, 8);
    CHECK(deg.retirementWarning == 2 && deg.stiffness > 24.0);

    // World lifecycle + short fall
    bridge.createWorld(9.81);
    CHECK(bridge.hasWorld());
    const int rope = bridge.addRope({0, 0, 0}, {0, -2, 0}, 2.0, 0.065, 0.5, 80, 8);
    CHECK(rope >= 0);
    CHECK(bridge.addClimber(rope, 80.0) >= 0);
    for (int i = 0; i < 240; ++i) bridge.step(1.0 / 240.0);
    const auto positions = bridge.getRopePositions();
    CHECK(positions.size() >= 2);
    CHECK(bridge.getClimberPosition().y < 0.0f);
    bridge.destroyWorld();
    CHECK(!bridge.hasWorld());

    std::printf("test_bridge: all checks passed\n");
    return 0;
}
