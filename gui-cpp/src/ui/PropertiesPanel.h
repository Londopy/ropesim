// gui-cpp/src/ui/PropertiesPanel.h
//
// Left panel: rope, climber, environment, physics, scenario type sections.

#pragma once

#include <QWidget>

#include "core/RopeDatabase.h"

class QButtonGroup;
class QCheckBox;
class QComboBox;
class QDoubleSpinBox;
class QLabel;
class QSlider;
class QSpinBox;
class RopeSelector;

/// Snapshot of every user-editable simulation parameter.
struct ScenarioParams {
    RopeSpec rope;
    int fallsTaken = 0;

    double climberMassKg = 80.0;
    double climberHeightM = 1.75;
    int belayDevice = 0; // RopesimBelayDevice
    double belayerMassKg = 75.0;
    bool dynamicBelay = true;

    QString rockType = "granite";
    bool wet = false;
    double temperatureC = 15.0;
    double routeAngleDeg = 90.0;

    bool useRapier = false;
    double linkSpacingM = 0.25;  // fine 0.1 / medium 0.25 / coarse 0.5
    double timestepS = 1.0 / 240.0;
    int rockPreset = 0;

    QString scenarioType = "Lead"; // Lead / Top-Rope / Rappel / Haul / Lower
    double topRopeSlackM = 1.0;
    double rappelSpeedMps = 2.0;
    bool rappelSuddenStop = false;
    int haulSystem = 0; // 0=3:1 1=5:1 2=6:1 3=piggyback
    double haulLoadKg = 80.0;

    // Route geometry (2D): fall from climberHeight above last piece
    double climberRouteHeightM = 12.0;
    double lastPieceHeightM = 10.0;
};

class PropertiesPanel : public QWidget {
    Q_OBJECT
public:
    explicit PropertiesPanel(RopeDatabase* db, QWidget* parent = nullptr);

    ScenarioParams params() const;
    void refreshRopes();

signals:
    void paramsChanged();
    void rockTypeChanged(const QString& rockType);
    void rockPresetChanged(int preset);
    void routeAngleChanged(double deg);
    void editRopeRequested(bool createNew);

private:
    QWidget* buildRopeSection();
    QWidget* buildClimberSection();
    QWidget* buildEnvironmentSection();
    QWidget* buildPhysicsSection();
    QWidget* buildScenarioSection();

    RopeDatabase* m_db;
    RopeSelector* m_ropeSelector;
    QSpinBox* m_fallsTaken;
    QLabel* m_retirementLabel;

    QDoubleSpinBox* m_mass;
    QDoubleSpinBox* m_height;
    QComboBox* m_device;
    QDoubleSpinBox* m_belayerMass;
    QCheckBox* m_dynamicBelay;

    QComboBox* m_rockType;
    QButtonGroup* m_wetGroup;
    QSlider* m_temperature;
    QLabel* m_tempLabel;
    QSlider* m_routeAngle;
    QLabel* m_angleLabel;

    QButtonGroup* m_physicsGroup;
    QComboBox* m_linkSpacing;
    QComboBox* m_timestep;
    QComboBox* m_rockPreset;

    QComboBox* m_scenarioType;
    QDoubleSpinBox* m_slack;
    QDoubleSpinBox* m_rappelSpeed;
    QCheckBox* m_suddenStop;
    QComboBox* m_haulSystem;
    QDoubleSpinBox* m_haulLoad;
    QDoubleSpinBox* m_climberRouteHeight;
    QDoubleSpinBox* m_lastPieceHeight;
    QWidget *m_topRopeRow, *m_rappelRow, *m_haulRow;
};
