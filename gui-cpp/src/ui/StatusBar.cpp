// gui-cpp/src/ui/StatusBar.cpp

#include "ui/StatusBar.h"

#include <QLabel>

StatusBar::StatusBar(QWidget* parent) : QStatusBar(parent) {
    m_mode = new QLabel(this);
    m_units = new QLabel(this);
    m_core = new QLabel(this);
    for (auto* l : {m_mode, m_units, m_core}) {
        l->setStyleSheet("color: #6b7d6c; padding: 0 8px;");
        addPermanentWidget(l);
    }
    setPhysicsMode("Analytical");
    setUnits("SI");
}

void StatusBar::setPhysicsMode(const QString& mode) {
    m_mode->setText(tr("physics: %1").arg(mode));
}

void StatusBar::setUnits(const QString& units) {
    m_units->setText(tr("units: %1").arg(units));
}

void StatusBar::setCoreInfo(int abiVersion) {
    m_core->setText(tr("rust core ABI v%1").arg(abiVersion));
}

void StatusBar::showTransient(const QString& message, int ms) {
    showMessage(message, ms);
}
