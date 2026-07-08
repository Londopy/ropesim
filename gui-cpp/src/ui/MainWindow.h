// gui-cpp/src/ui/MainWindow.h
//
// Top-level application window: menu bar, toolbar, three-panel splitter
// (properties | 2D/3D view | results), status bar, undo stack.

#pragma once

#include <QMainWindow>
#include <QUndoStack>
#include <glm/vec3.hpp>
#include <memory>
#include <vector>

#include "core/RopeDatabase.h"
#include "core/RopeSimBridge.h"
#include "core/SimulationResult.h"
#include "renderer/GearRenderer.h"

class QSplitter;
class QStackedWidget;
class PropertiesPanel;
class ResultsPanel;
class RouteCanvas2D;
class StatusBar;
class Toolbar;
class Viewport3D;

/// One placed protection piece (scenario model).
struct PlacedGear {
    int gearType = 1; // 1 bolt, 2 cam, 3 nut
    glm::vec3 position{0.0f};
    glm::vec3 pullDir{0.0f, -1.0f, 0.0f};
    double mbsKn = 25.0;
    double quality = 1.0;
};

class MainWindow : public QMainWindow {
    Q_OBJECT
public:
    MainWindow();

private:
    // Setup
    void buildMenus();
    void buildCentral();
    void applyDarkTheme();

    // Scenario file I/O (.ropesim JSON, same format as the Python GUI)
    void newScenario();
    void openScenario();
    void saveScenario();
    void saveScenarioAs();
    bool writeScenario(const QString& path);
    bool readScenario(const QString& path);

    // Simulation
    void runAnalytical();
    void runRapier();
    void runZipper();
    void runSweep();
    SimulationResult buildAnalyticalResult(const ScenarioParams& p);

    // Gear
    void onGearPlaced(int gearType, float x, float y, float z);
    void refreshViews();

    // Export
    void exportPdf();
    void exportCsv();
    void copySummary();

    RopeDatabase m_db;
    RopeSimBridge m_bridge;
    QUndoStack m_undoStack;

    Toolbar* m_toolbar;
    PropertiesPanel* m_properties;
    ResultsPanel* m_results;
    QStackedWidget* m_viewStack;
    RouteCanvas2D* m_canvas2d;
    Viewport3D* m_viewport3d;
    StatusBar* m_statusBar;

    std::vector<PlacedGear> m_gear;
    SimulationResult m_lastResult;
    QString m_scenarioPath;
    bool m_imperial = false;
};
