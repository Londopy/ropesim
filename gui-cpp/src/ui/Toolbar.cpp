// gui-cpp/src/ui/Toolbar.cpp

#include "ui/Toolbar.h"

#include <QAction>
#include <QActionGroup>

Toolbar::Toolbar(QWidget* parent) : QToolBar("Main", parent) {
    setMovable(false);
    setToolButtonStyle(Qt::ToolButtonTextBesideIcon);

    // ── Placement modes ──────────────────────────────────────────────────
    m_placeGroup = new QActionGroup(this);
    m_placeGroup->setExclusive(true);

    auto makeMode = [this](const QString& text, int mode) {
        QAction* a = addAction(text);
        a->setCheckable(true);
        m_placeGroup->addAction(a);
        connect(a, &QAction::toggled, this, [this, mode](bool on) {
            if (on) emit placementModeChanged(mode);
        });
        return a;
    };

    m_selectAction = makeMode(tr("Select"), 0);
    m_selectAction->setChecked(true);
    makeMode(tr("+ Bolt"), 1);
    makeMode(tr("+ Cam"), 2);
    makeMode(tr("+ Nut"), 3);

    addSeparator();

    // ── View toggle ──────────────────────────────────────────────────────
    QAction* view2d = addAction(tr("2D"));
    QAction* view3d = addAction(tr("3D"));
    view2d->setCheckable(true);
    view3d->setCheckable(true);
    auto* viewGroup = new QActionGroup(this);
    viewGroup->addAction(view2d);
    viewGroup->addAction(view3d);
    view3d->setChecked(true);
    connect(view3d, &QAction::toggled, this,
            [this](bool on) { emit viewModeChanged(on); });

    addSeparator();

    // ── Run ──────────────────────────────────────────────────────────────
    QAction* runA = addAction(tr("▶ Run"));
    runA->setToolTip(tr("Run analytical simulation (F5)"));
    connect(runA, &QAction::triggered, this, &Toolbar::runAnalyticalRequested);

    QAction* runR = addAction(tr("▶ Run 3D"));
    runR->setToolTip(tr("Run Rapier 3D simulation (F6)"));
    connect(runR, &QAction::triggered, this, &Toolbar::runRapierRequested);
}

void Toolbar::clearPlacementMode() { m_selectAction->setChecked(true); }
