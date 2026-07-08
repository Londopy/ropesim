// gui-cpp/src/core/SimulationResult.cpp

#include "core/SimulationResult.h"

#include <algorithm>

double SimFrameData::peakAnchorForceKn() const {
    double peak = 0.0;
    for (const auto& f : frames) peak = std::max(peak, f.anchorForceKn);
    return peak;
}

int SimFrameData::frameOfPeak() const {
    int best = 0;
    double peak = -1.0;
    for (size_t i = 0; i < frames.size(); ++i) {
        if (frames[i].anchorForceKn > peak) {
            peak = frames[i].anchorForceKn;
            best = static_cast<int>(i);
        }
    }
    return best;
}

SimulationResult::Banner SimulationResult::computeBanner() const {
    bool caution = false;
    for (const auto& c : components) {
        if (c.status == ComponentSafety::Status::Danger) return Banner::Danger;
        if (c.status == ComponentSafety::Status::Caution) caution = true;
    }
    // UIAA limit for single ropes is 12 kN on the climber; flag close calls.
    if (peakForceKn > 10.0) return Banner::Danger;
    if (peakForceKn > 8.0 || caution) return Banner::Caution;
    return Banner::Safe;
}
