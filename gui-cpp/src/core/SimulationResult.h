// gui-cpp/src/core/SimulationResult.h
//
// Data structures for simulation output shared by the results panel,
// viewport playback, and export dialogs.

#pragma once

#include <glm/vec3.hpp>
#include <QString>
#include <vector>

/// One recorded frame of a Rapier simulation (for playback).
struct SimFrame {
    double timestampMs = 0.0;
    std::vector<glm::vec3> ropePositions;
    glm::vec3 climberPosition{0.0f};
    double anchorForceKn = 0.0;
    std::vector<double> perGearForcesKn;
};

/// Full recorded simulation (playback source).
struct SimFrameData {
    std::vector<SimFrame> frames;
    double dtSeconds = 1.0 / 240.0;

    double totalTimeSeconds() const { return frames.size() * dtSeconds; }
    double peakAnchorForceKn() const;
    int frameOfPeak() const;
    bool empty() const { return frames.empty(); }
};

/// Per-component safety row for the results table.
struct ComponentSafety {
    QString name;
    double forceKn = 0.0;
    double mbsKn = 0.0;
    enum class Status { Safe, Caution, Danger } status = Status::Safe;

    double marginPct() const {
        return mbsKn > 0.0 ? (1.0 - forceKn / mbsKn) * 100.0 : 0.0;
    }
};

/// Aggregate result of a simulation run (analytical or Rapier).
struct SimulationResult {
    QString scenarioType;   // "Lead" / "Top-Rope" / "Rappel" / "Haul"
    double fallFactor = 0.0;
    double peakForceKn = 0.0;
    double decelerationG = 0.0;
    double elongationM = 0.0;

    // Energy budget (J)
    double energyPotential = 0.0;
    double energyRope = 0.0;
    double energyBelay = 0.0;
    double energyResidual = 0.0;

    // Force curve (kN per timestep)
    std::vector<double> forceCurve;
    double forceCurveDtMs = 1.0;

    std::vector<ComponentSafety> components;
    SimFrameData replay; // empty for analytical runs

    enum class Banner { Safe, Caution, Danger } banner = Banner::Safe;
    Banner computeBanner() const;
};
