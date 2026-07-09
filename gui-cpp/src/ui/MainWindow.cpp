// gui-cpp/src/ui/MainWindow.cpp

#include "ui/MainWindow.h"

#include <QApplication>
#include <QClipboard>
#include <QDesktopServices>
#include <QFileDialog>
#include <QUrl>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMenuBar>
#include <QMessageBox>
#include <QSplitter>
#include <QStackedWidget>
#include <QUndoCommand>

#include <functional>

#include <cmath>

#include "canvas/RouteCanvas2D.h"
#include "canvas/Viewport3D.h"
#include "dialogs/PreferencesDialog.h"
#include "ui/AboutDialog.h"
#include "dialogs/RopeEditorDialog.h"
#include "dialogs/ScenarioExportDialog.h"
#include "ui/PropertiesPanel.h"
#include "ui/ResultsPanel.h"
#include "ui/StatusBar.h"
#include "ui/Toolbar.h"
#include "widgets/PlaybackScrubber.h"

#include <QCheckBox>
#include <QComboBox>
#include <QPushButton>

namespace {
constexpr double kG = 9.81;

/// Undo command for gear placement.
class PlaceGearCommand : public QUndoCommand {
public:
    PlaceGearCommand(std::vector<PlacedGear>* gear, PlacedGear piece,
                     std::function<void()> refresh)
        : m_gear(gear), m_piece(piece), m_refresh(std::move(refresh)) {
        setText("place gear");
    }
    void redo() override {
        m_gear->push_back(m_piece);
        m_refresh();
    }
    void undo() override {
        if (!m_gear->empty()) m_gear->pop_back();
        m_refresh();
    }

private:
    std::vector<PlacedGear>* m_gear;
    PlacedGear m_piece;
    std::function<void()> m_refresh;
};
} // namespace

MainWindow::MainWindow() {
    setWindowTitle("ropesim");
    resize(1440, 900);
    m_db.load();

    m_toolbar = new Toolbar(this);
    addToolBar(m_toolbar);
    m_statusBar = new StatusBar(this);
    setStatusBar(m_statusBar);
    m_statusBar->setCoreInfo(RopeSimBridge::abiVersion());

    buildCentral();
    buildMenus();
    applyDarkTheme();

    // Toolbar wiring
    connect(m_toolbar, &Toolbar::placementModeChanged, this, [this](int mode) {
        m_viewport3d->setPlacementMode(static_cast<PlacementMode>(mode));
        m_canvas2d->setPlacementMode(mode);
    });
    connect(m_toolbar, &Toolbar::viewModeChanged, this,
            [this](bool is3d) { m_viewStack->setCurrentIndex(is3d ? 1 : 0); });
    connect(m_toolbar, &Toolbar::runAnalyticalRequested, this,
            &MainWindow::runAnalytical);
    connect(m_toolbar, &Toolbar::runRapierRequested, this,
            &MainWindow::runRapier);

    // Placement from both views
    connect(m_viewport3d, &Viewport3D::gearPlaced, this,
            &MainWindow::onGearPlaced);
    connect(m_canvas2d, &RouteCanvas2D::gearPlaced, this,
            &MainWindow::onGearPlaced);

    // Properties → live view updates
    connect(m_properties, &PropertiesPanel::rockTypeChanged, this,
            [this](const QString& t) {
                RockTextureType type = RockTextureType::Granite;
                if (t == "limestone") type = RockTextureType::Limestone;
                else if (t == "sandstone") type = RockTextureType::Sandstone;
                else if (t == "basalt") type = RockTextureType::Basalt;
                else if (t == "ice") type = RockTextureType::Ice;
                m_viewport3d->setRockType(type);
            });
    connect(m_properties, &PropertiesPanel::rockPresetChanged, this,
            [this](int preset) {
                m_viewport3d->setRockPreset(static_cast<RockFacePreset>(preset));
            });
    connect(m_properties, &PropertiesPanel::routeAngleChanged, this,
            [this](double deg) { m_canvas2d->setRouteAngleDeg(deg); });
    connect(m_properties, &PropertiesPanel::editRopeRequested, this,
            [this](bool createNew) {
                RopeEditorDialog dlg(&m_db, this);
                if (!createNew) {
                    const auto p = m_properties->params();
                    dlg.loadSpec(p.rope);
                }
                if (dlg.exec() == QDialog::Accepted) m_properties->refreshRopes();
            });

    // Results panel export + playback
    connect(m_results, &ResultsPanel::exportPdfRequested, this,
            &MainWindow::exportPdf);
    connect(m_results, &ResultsPanel::exportCsvRequested, this,
            &MainWindow::exportCsv);
    connect(m_results, &ResultsPanel::copySummaryRequested, this,
            &MainWindow::copySummary);
    connect(m_results->playButton(), &QPushButton::clicked, this, [this] {
        if (m_viewport3d->isPlaying()) {
            m_viewport3d->pause();
            m_results->playButton()->setText(tr("▶ Play"));
        } else {
            m_viewport3d->play();
            m_results->playButton()->setText(tr("⏸ Pause"));
        }
    });
    connect(m_results->scrubber(), &PlaybackScrubber::frameScrubbed,
            m_viewport3d, &Viewport3D::setPlaybackFrame);
    connect(m_viewport3d, &Viewport3D::playbackFrameChanged,
            m_results->scrubber(), &PlaybackScrubber::setCurrentFrame);
    connect(m_results->speedCombo(), &QComboBox::currentIndexChanged, this,
            [this](int) {
                m_viewport3d->setSpeed(
                    m_results->speedCombo()->currentData().toDouble());
            });
    connect(m_results->loopCheck(), &QCheckBox::toggled, m_viewport3d,
            &Viewport3D::setLoop);

    refreshViews();
}

void MainWindow::buildCentral() {
    auto* splitter = new QSplitter(Qt::Horizontal, this);

    m_properties = new PropertiesPanel(&m_db, splitter);

    m_viewStack = new QStackedWidget(splitter);
    m_canvas2d = new RouteCanvas2D(m_viewStack);
    m_viewport3d = new Viewport3D(m_viewStack);
    m_viewStack->addWidget(m_canvas2d);
    m_viewStack->addWidget(m_viewport3d);
    m_viewStack->setCurrentIndex(1); // 3D default

    m_results = new ResultsPanel(splitter);

    splitter->addWidget(m_properties);
    splitter->addWidget(m_viewStack);
    splitter->addWidget(m_results);
    splitter->setSizes({260, 840, 320});
    splitter->setStretchFactor(1, 1);
    setCentralWidget(splitter);
}

void MainWindow::buildMenus() {
    // ── File ────────────────────────────────────────────────────────────
    QMenu* file = menuBar()->addMenu(tr("&File"));
    file->addAction(tr("New Scenario"), QKeySequence::New, this,
                    &MainWindow::newScenario);
    file->addAction(tr("Open Scenario…"), QKeySequence::Open, this,
                    &MainWindow::openScenario);
    file->addAction(tr("Save Scenario"), QKeySequence::Save, this,
                    &MainWindow::saveScenario);
    file->addAction(tr("Save Scenario As…"), QKeySequence::SaveAs, this,
                    &MainWindow::saveScenarioAs);
    file->addSeparator();
    file->addAction(tr("Export Report (PDF)"), this, &MainWindow::exportPdf);
    file->addAction(tr("Export Data (CSV)"), this, &MainWindow::exportCsv);
    file->addSeparator();
    file->addAction(tr("Quit"), QKeySequence::Quit, qApp, &QApplication::quit);

    // ── Edit ────────────────────────────────────────────────────────────
    QMenu* edit = menuBar()->addMenu(tr("&Edit"));
    QAction* undo = m_undoStack.createUndoAction(this, tr("Undo"));
    undo->setShortcut(QKeySequence::Undo);
    QAction* redo = m_undoStack.createRedoAction(this, tr("Redo"));
    redo->setShortcut(QKeySequence("Ctrl+Y"));
    edit->addAction(undo);
    edit->addAction(redo);
    edit->addSeparator();
    edit->addAction(tr("Preferences…"), this, [this] {
        PreferencesDialog dlg(this);
        if (dlg.exec() == QDialog::Accepted) {
            m_imperial = PreferencesDialog::useImperialUnits();
            m_statusBar->setUnits(m_imperial ? "Imperial" : "SI");
        }
    });

    // ── View ────────────────────────────────────────────────────────────
    QMenu* view = menuBar()->addMenu(tr("&View"));
    view->addAction(tr("2D Canvas"), QKeySequence(Qt::Key_F1), this,
                    [this] { m_viewStack->setCurrentIndex(0); });
    view->addAction(tr("3D Viewport"), QKeySequence(Qt::Key_F2), this,
                    [this] { m_viewStack->setCurrentIndex(1); });
    view->addSeparator();
    view->addAction(tr("Toggle Properties"), QKeySequence("Ctrl+1"), this,
                    [this] { m_properties->setVisible(!m_properties->isVisible()); });
    view->addAction(tr("Toggle Results"), QKeySequence("Ctrl+2"), this,
                    [this] { m_results->setVisible(!m_results->isVisible()); });

    // ── Simulate ────────────────────────────────────────────────────────
    QMenu* sim = menuBar()->addMenu(tr("&Simulate"));
    sim->addAction(tr("Run (Analytical)"), QKeySequence(Qt::Key_F5), this,
                   &MainWindow::runAnalytical);
    sim->addAction(tr("Run (Rapier 3D)"), QKeySequence(Qt::Key_F6), this,
                   &MainWindow::runRapier);
    sim->addAction(tr("Run Zipper Sim"), QKeySequence(Qt::Key_F7), this,
                   &MainWindow::runZipper);
    sim->addAction(tr("Sweep Positions"), QKeySequence(Qt::Key_F8), this,
                   &MainWindow::runSweep);

    // ── Demo ────────────────────────────────────────────────────────────
    // One-click, fully preset scenarios that set every parameter and run.
    QMenu* demo = menuBar()->addMenu(tr("&Demo"));
    demo->addAction(tr("2D Fall Analysis Demo"), QKeySequence(Qt::Key_F9), this,
                    &MainWindow::runDemo2D);
    demo->addAction(tr("3D Rapier Fall Demo"), QKeySequence(Qt::Key_F10), this,
                    &MainWindow::runDemo3D);

    // ── Help ────────────────────────────────────────────────────────────
    QMenu* help = menuBar()->addMenu(tr("&Help"));
    help->addAction(tr("Documentation"), this, [] {
        QDesktopServices::openUrl(QUrl("https://londopy.github.io/ropesim/"));
    });
    help->addAction(tr("About ropesim"), this, [this] {
        AboutDialog dlg(this);
        dlg.exec();
    });
}

void MainWindow::applyDarkTheme() {
    setStyleSheet(R"(
        QMainWindow, QDialog, QWidget { background: #0f1410; color: #d6e8d7; }
        QGroupBox {
            border: 1px solid #242b25; border-radius: 4px;
            margin-top: 10px; padding-top: 12px; font-weight: 600;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; color: #7ecf45; }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget {
            background: #171c18; border: 1px solid #242b25; border-radius: 3px;
            padding: 3px 6px; color: #edf5ee;
        }
        QPushButton {
            background: #1c241d; border: 1px solid #2e3a2f; border-radius: 3px;
            padding: 5px 12px; color: #d6e8d7;
        }
        QPushButton:hover { background: #24301f; border-color: #3a6020; }
        QPushButton:pressed { background: #3a6020; }
        QToolBar { background: #111413; border-bottom: 1px solid #242b25; spacing: 4px; }
        QToolBar QToolButton { color: #d6e8d7; padding: 4px 8px; }
        QToolBar QToolButton:checked { background: #3a6020; border-radius: 3px; }
        QMenuBar { background: #111413; color: #d6e8d7; }
        QMenuBar::item:selected, QMenu::item:selected { background: #3a6020; }
        QMenu { background: #171c18; color: #d6e8d7; border: 1px solid #242b25; }
        QHeaderView::section {
            background: #171c18; color: #6b7d6c; border: none; padding: 4px;
        }
        QStatusBar { background: #111413; }
        QSlider::groove:horizontal { height: 5px; background: #242b25; border-radius: 2px; }
        QSlider::handle:horizontal {
            width: 14px; margin: -5px 0; border-radius: 7px; background: #7ecf45;
        }
    )");
}

// ── Scenario I/O ─────────────────────────────────────────────────────────────

void MainWindow::newScenario() {
    m_gear.clear();
    m_undoStack.clear();
    m_scenarioPath.clear();
    m_results->clear();
    refreshViews();
    m_statusBar->showTransient(tr("new scenario"));
}

void MainWindow::openScenario() {
    const QString path = QFileDialog::getOpenFileName(
        this, tr("Open Scenario"), QString(), tr("ropesim scenario (*.ropesim)"));
    if (path.isEmpty()) return;
    if (readScenario(path)) {
        m_scenarioPath = path;
        m_statusBar->showTransient(tr("loaded %1").arg(path));
    } else {
        QMessageBox::warning(this, tr("Open"), tr("Could not read %1").arg(path));
    }
}

void MainWindow::saveScenario() {
    if (m_scenarioPath.isEmpty()) {
        saveScenarioAs();
        return;
    }
    writeScenario(m_scenarioPath);
}

void MainWindow::saveScenarioAs() {
    const QString path = QFileDialog::getSaveFileName(
        this, tr("Save Scenario"), "scenario.ropesim",
        tr("ropesim scenario (*.ropesim)"));
    if (path.isEmpty()) return;
    if (writeScenario(path)) m_scenarioPath = path;
}

bool MainWindow::writeScenario(const QString& path) {
    const auto p = m_properties->params();
    QJsonObject root;
    root["version"] = 3;
    root["rope_name"] = p.rope.name;
    root["climber_mass_kg"] = p.climberMassKg;
    root["scenario_type"] = p.scenarioType;
    root["route_angle_deg"] = p.routeAngleDeg;
    root["climber_height_m"] = p.climberRouteHeightM;
    root["last_piece_height_m"] = p.lastPieceHeightM;
    QJsonArray gear;
    for (const auto& g : m_gear) {
        QJsonObject o;
        o["type"] = g.gearType;
        o["x"] = g.position.x;
        o["y"] = g.position.y;
        o["z"] = g.position.z;
        o["mbs_kn"] = g.mbsKn;
        o["quality"] = g.quality;
        gear.append(o);
    }
    root["gear"] = gear;

    QFile f(path);
    if (!f.open(QIODevice::WriteOnly)) return false;
    f.write(QJsonDocument(root).toJson(QJsonDocument::Indented));
    return true;
}

bool MainWindow::readScenario(const QString& path) {
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) return false;
    const auto doc = QJsonDocument::fromJson(f.readAll());
    if (!doc.isObject()) return false;
    const auto root = doc.object();

    m_gear.clear();
    for (const auto& item : root.value("gear").toArray()) {
        const auto o = item.toObject();
        PlacedGear g;
        g.gearType = o.value("type").toInt(1);
        g.position = {static_cast<float>(o.value("x").toDouble()),
                      static_cast<float>(o.value("y").toDouble()),
                      static_cast<float>(o.value("z").toDouble())};
        g.mbsKn = o.value("mbs_kn").toDouble(25.0);
        g.quality = o.value("quality").toDouble(1.0);
        m_gear.push_back(g);
    }
    m_undoStack.clear();
    refreshViews();
    return true;
}

// ── Gear placement ───────────────────────────────────────────────────────────

void MainWindow::onGearPlaced(int gearType, float x, float y, float z) {
    PlacedGear g;
    g.gearType = gearType;
    g.position = {x, y, z};
    g.mbsKn = gearType == 1 ? 25.0 : gearType == 2 ? 14.0 : 10.0;
    g.quality = 1.0;
    m_undoStack.push(
        new PlaceGearCommand(&m_gear, g, [this] { refreshViews(); }));
    m_statusBar->showTransient(
        tr("placed %1 at (%2, %3)")
            .arg(gearType == 1 ? "bolt" : gearType == 2 ? "cam" : "nut")
            .arg(x, 0, 'f', 1)
            .arg(y, 0, 'f', 1));
}

void MainWindow::refreshViews() {
    std::vector<GearInstance> instances;
    for (const auto& g : m_gear) {
        GearInstance i;
        i.type = g.gearType == 1   ? GearType::Bolt
                 : g.gearType == 2 ? GearType::Cam
                                   : GearType::Nut;
        i.position = g.position;
        i.orientation = {0.0f, 0.0f, 1.0f};
        i.loadFraction = 0.0;
        instances.push_back(i);
    }
    m_viewport3d->setGear(instances);
    m_canvas2d->setGear(instances);

    const auto p = m_properties->params();
    m_canvas2d->setClimberHeight(p.climberRouteHeightM);
    m_canvas2d->setRouteAngleDeg(p.routeAngleDeg);
}

// ── Simulation ───────────────────────────────────────────────────────────────

SimulationResult MainWindow::buildAnalyticalResult(const ScenarioParams& p) {
    SimulationResult r;
    r.scenarioType = p.scenarioType;

    // Degrade rope for falls taken.
    const auto degraded =
        m_bridge.degradeRope(p.rope.stiffnessKn(), p.fallsTaken,
                             p.rope.numberOfFalls);
    const double stiffness = degraded.stiffness;
    const double belayFriction = 0.35; // device baseline; dynamic belay below

    if (p.scenarioType == "Rappel") {
        r.peakForceKn = m_bridge.rappelLoad(p.climberMassKg, 0.6,
                                            p.rappelSpeedMps);
        r.fallFactor = 0.0;
    } else if (p.scenarioType == "Haul") {
        const auto [ma, effort] =
            m_bridge.haulForces(p.haulSystem, p.haulLoadKg, 0.12);
        r.peakForceKn = (p.haulLoadKg * kG + effort) / 1000.0;
        r.fallFactor = 0.0;
        r.scenarioType = QStringLiteral("Haul (%1:1 actual %2)")
                             .arg(p.haulSystem == 0   ? 3
                                  : p.haulSystem == 1 ? 5
                                  : p.haulSystem == 2 ? 6
                                                      : 9)
                             .arg(ma, 0, 'f', 2);
    } else {
        // Lead / Top-Rope / Lower
        double fallDist, ropeOut;
        if (p.scenarioType == "Top-Rope") {
            fallDist = 2.0 * p.topRopeSlackM;
            ropeOut = p.climberRouteHeightM;
        } else {
            fallDist = 2.0 * (p.climberRouteHeightM - p.lastPieceHeightM);
            ropeOut = p.climberRouteHeightM;
        }
        fallDist = std::max(fallDist, 0.1);
        ropeOut = std::max(ropeOut, 0.5);

        r.fallFactor = m_bridge.computeFallFactor(fallDist, ropeOut);
        double peak = m_bridge.computeImpactForce(
            p.climberMassKg, r.fallFactor, stiffness, belayFriction, p.wet,
            p.temperatureC);
        if (p.dynamicBelay) {
            peak *= m_bridge.dynamicBelayReduction(
                p.climberMassKg, p.belayerMassKg, p.belayDevice, true, false);
        }
        r.peakForceKn = peak;

        r.forceCurve = m_bridge.computeForceCurve(
            p.climberMassKg, fallDist, ropeOut, stiffness, 0.15, 1.0);
        r.forceCurveDtMs = 1.0;

        r.decelerationG =
            r.peakForceKn * 1000.0 / (p.climberMassKg * kG) - 1.0;
        r.elongationM =
            m_bridge.staticElongation(p.rope.staticElongationPct,
                                      p.climberMassKg, ropeOut) *
            (r.fallFactor + 1.0);

        // Energy budget (simplified mirror of the Python model)
        const double pe = p.climberMassKg * kG * (fallDist + r.elongationM);
        const double rope = 0.5 * r.peakForceKn * 1000.0 * r.elongationM;
        const double belay = pe * belayFriction * 0.5;
        r.energyPotential = pe;
        r.energyRope = std::min(rope, pe);
        r.energyBelay = std::min(belay, pe - r.energyRope);
        r.energyResidual = std::max(pe - r.energyRope - r.energyBelay, 0.0);
    }

    // Component safety table
    auto statusFor = [](double force, double mbs) {
        const double margin = mbs > 0 ? force / mbs : 1.0;
        return margin < 0.5   ? ComponentSafety::Status::Safe
               : margin < 0.8 ? ComponentSafety::Status::Caution
                              : ComponentSafety::Status::Danger;
    };
    int idx = 1;
    for (const auto& g : m_gear) {
        ComponentSafety c;
        c.name = QStringLiteral("%1 %2")
                     .arg(g.gearType == 1   ? "bolt"
                          : g.gearType == 2 ? "cam"
                                            : "nut")
                     .arg(idx++);
        // Top piece takes the full force; lower pieces see rope drag only.
        c.forceKn = (idx == 2) ? r.peakForceKn : r.peakForceKn * 0.15;
        c.mbsKn = g.mbsKn * g.quality;
        c.status = statusFor(c.forceKn, c.mbsKn);
        r.components.push_back(c);
    }
    ComponentSafety climber;
    climber.name = "climber";
    climber.forceKn = r.peakForceKn;
    climber.mbsKn = 12.0; // UIAA limit on the climber
    climber.status = statusFor(climber.forceKn, climber.mbsKn);
    r.components.push_back(climber);

    return r;
}

void MainWindow::runAnalytical() {
    const auto p = m_properties->params();
    m_lastResult = buildAnalyticalResult(p);
    m_results->showResult(m_lastResult);
    m_statusBar->setPhysicsMode("Analytical");
    m_statusBar->showTransient(
        tr("peak %1 kN at ff %2")
            .arg(m_lastResult.peakForceKn, 0, 'f', 2)
            .arg(m_lastResult.fallFactor, 0, 'f', 2));
}

void MainWindow::runRapier() {
    const auto p = m_properties->params();
    m_statusBar->setPhysicsMode("Rapier 3D");
    m_statusBar->showTransient(tr("running Rapier simulation…"));

    m_bridge.createWorld(PreferencesDialog::defaultGravity());

    // Rope from anchor (top of route) down to the climber.
    const glm::vec3 anchor(0.0f, static_cast<float>(p.climberRouteHeightM + 1.0), 0.0f);
    const glm::vec3 climberPos(0.0f, static_cast<float>(p.climberRouteHeightM), 0.4f);
    const double ropeLen = p.climberRouteHeightM + 2.0;
    const int rope =
        m_bridge.addRope(anchor, climberPos, ropeLen, p.rope.weightGPerM / 1000.0,
                         p.linkSpacingM, p.rope.stiffnessKn() * 3.0, 8.0);
    m_bridge.addClimber(rope, p.climberMassKg);

    std::vector<int> gearHandles;
    for (const auto& g : m_gear) {
        const int h = g.gearType == 2
                          ? m_bridge.addCam(g.position, g.mbsKn, g.quality,
                                            g.pullDir)
                          : m_bridge.addBolt(g.position, g.mbsKn,
                                             g.gearType == 1 ? 0 : 1);
        gearHandles.push_back(h);
    }

    // Record ~2.5 s of simulation.
    SimFrameData replay;
    replay.dtSeconds = p.timestepS;
    const int steps = static_cast<int>(2.5 / p.timestepS);
    double peak = 0.0;
    for (int i = 0; i < steps; ++i) {
        m_bridge.step(p.timestepS);
        SimFrame frame;
        frame.timestampMs = (i + 1) * p.timestepS * 1000.0;
        frame.ropePositions = m_bridge.getRopePositions();
        frame.climberPosition = m_bridge.getClimberPosition();
        frame.anchorForceKn = m_bridge.getAnchorForce();
        for (int h : gearHandles)
            frame.perGearForcesKn.push_back(m_bridge.getForceAtGear(h));
        peak = std::max(peak, frame.anchorForceKn);
        replay.frames.push_back(std::move(frame));
    }

    m_lastResult = buildAnalyticalResult(p); // analytics for the panels
    m_lastResult.replay = std::move(replay);
    m_lastResult.scenarioType += " (Rapier 3D)";
    m_results->showResult(m_lastResult);

    m_viewport3d->loadReplay(m_lastResult.replay);

    // Force arrows at gear positions from the last frame.
    std::vector<ForceArrow> arrows;
    if (!m_lastResult.replay.empty()) {
        const auto& last = m_lastResult.replay.frames.back();
        for (size_t i = 0; i < m_gear.size() && i < last.perGearForcesKn.size();
             ++i) {
            ForceArrow a;
            a.position = m_gear[i].position;
            a.direction = {0.0f, -1.0f, 0.0f};
            a.forceKn = last.perGearForcesKn[i];
            a.mbsKn = m_gear[i].mbsKn;
            arrows.push_back(a);
        }
    }
    m_viewport3d->setForceArrows(arrows);
    m_statusBar->showTransient(
        tr("Rapier run complete — peak anchor %1 kN").arg(peak, 0, 'f', 2));
}

void MainWindow::runZipper() {
    // Zipper: simulate progressive failure bottom-up using the analytical
    // model + sliding-X redistribution.
    const auto p = m_properties->params();
    auto result = buildAnalyticalResult(p);
    result.scenarioType += " (zipper check)";
    // Mark any component loaded beyond MBS as failed and cascade the load.
    double carried = result.peakForceKn;
    for (auto it = result.components.rbegin(); it != result.components.rend();
         ++it) {
        if (it->name == "climber") continue;
        it->forceKn = carried;
        if (carried > it->mbsKn) {
            it->status = ComponentSafety::Status::Danger;
            carried *= 1.25; // dynamic re-loading of the next piece
        } else {
            break;
        }
    }
    m_lastResult = result;
    m_results->showResult(m_lastResult);
}

void MainWindow::runSweep() {
    // Anchor angle sweep displayed in the results panel.
    const auto p = m_properties->params();
    std::vector<double> angles;
    std::vector<double> boltA, boltB;
    double load = m_lastResult.peakForceKn > 0 ? m_lastResult.peakForceKn : 8.0;
    for (int a = 0; a <= 170; a += 5) {
        angles.push_back(a);
        const auto [fa, fb] = m_bridge.slidingXDistribution(load, a);
        boltA.push_back(fa);
        boltB.push_back(fb);
    }
    m_lastResult.scenarioType = p.scenarioType + " (anchor sweep)";
    m_results->showResult(m_lastResult);
    m_statusBar->showTransient(tr("anchor sweep at %1 kN").arg(load, 0, 'f', 1));
}

// ── Built-in demos ─────────────────────────────────────────────────────────────

void MainWindow::loadDemoScenario() {
    // Preset every parameter, then place four bolts up a vertical wall.
    m_properties->applyDemoPreset();
    m_gear.clear();
    const double heights[] = {4.0, 8.0, 12.0, 16.0};
    for (double h : heights) {
        PlacedGear g;
        g.gearType = 1; // bolt
        g.position = {0.0f, static_cast<float>(h), 0.0f};
        g.pullDir = {0.0f, -1.0f, 0.0f};
        g.mbsKn = 25.0;
        g.quality = 1.0;
        m_gear.push_back(g);
    }
    m_undoStack.clear();
    m_scenarioPath.clear();
    refreshViews();
}

void MainWindow::runDemo2D() {
    m_statusBar->showTransient(tr("loading 2D demo scenario…"));
    loadDemoScenario();
    m_viewStack->setCurrentIndex(0); // 2D canvas
    runAnalytical();                 // updates results panel + status
}

void MainWindow::runDemo3D() {
    m_statusBar->showTransient(tr("loading 3D demo scenario…"));
    loadDemoScenario();
    m_viewStack->setCurrentIndex(1); // 3D viewport
    runRapier();                     // records + plays the replay
}

// ── Export ───────────────────────────────────────────────────────────────────

void MainWindow::exportPdf() {
    const QString path = QFileDialog::getSaveFileName(
        this, tr("Export PDF"), "ropesim_report.pdf", tr("PDF (*.pdf)"));
    if (path.isEmpty()) return;
    if (!ScenarioExportDialog::exportPdf(m_lastResult, path))
        QMessageBox::warning(this, tr("Export"), tr("Could not write %1").arg(path));
}

void MainWindow::exportCsv() {
    const QString path = QFileDialog::getSaveFileName(
        this, tr("Export CSV"), "ropesim_data.csv", tr("CSV (*.csv)"));
    if (path.isEmpty()) return;
    if (!ScenarioExportDialog::exportCsv(m_lastResult, path))
        QMessageBox::warning(this, tr("Export"), tr("Could not write %1").arg(path));
}

void MainWindow::copySummary() {
    QApplication::clipboard()->setText(
        QStringLiteral("ropesim: %1 | ff %2 | peak %3 kN | %4 g | elong %5 m")
            .arg(m_lastResult.scenarioType)
            .arg(m_lastResult.fallFactor, 0, 'f', 2)
            .arg(m_lastResult.peakForceKn, 0, 'f', 2)
            .arg(m_lastResult.decelerationG, 0, 'f', 1)
            .arg(m_lastResult.elongationM, 0, 'f', 2));
    m_statusBar->showTransient(tr("summary copied"));
}
