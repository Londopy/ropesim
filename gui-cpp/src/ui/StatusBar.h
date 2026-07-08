// gui-cpp/src/ui/StatusBar.h

#pragma once

#include <QStatusBar>

class QLabel;

class StatusBar : public QStatusBar {
    Q_OBJECT
public:
    explicit StatusBar(QWidget* parent = nullptr);

    void setPhysicsMode(const QString& mode);
    void setUnits(const QString& units);
    void setCoreInfo(int abiVersion);
    void showTransient(const QString& message, int ms = 3000);

private:
    QLabel* m_mode;
    QLabel* m_units;
    QLabel* m_core;
};
