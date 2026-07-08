// gui-cpp/src/ui/Toolbar.h
//
// Main toolbar: placement modes, view toggle, run buttons.

#pragma once

#include <QToolBar>

class QActionGroup;

class Toolbar : public QToolBar {
    Q_OBJECT
public:
    explicit Toolbar(QWidget* parent = nullptr);

    void clearPlacementMode();

signals:
    void placementModeChanged(int mode); // 0 none, 1 bolt, 2 cam, 3 nut
    void viewModeChanged(bool is3D);
    void runAnalyticalRequested();
    void runRapierRequested();

private:
    QActionGroup* m_placeGroup;
    QAction* m_selectAction;
};
