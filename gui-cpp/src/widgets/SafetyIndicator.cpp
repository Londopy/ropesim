// gui-cpp/src/widgets/SafetyIndicator.cpp

#include "widgets/SafetyIndicator.h"

#include <QPainter>

SafetyIndicator::SafetyIndicator(QWidget* parent) : QWidget(parent) {
    setFixedSize(14, 14);
}

QColor SafetyIndicator::colorFor(Level level) {
    switch (level) {
        case Level::Safe: return QColor(126, 207, 69);
        case Level::Caution: return QColor(232, 184, 75);
        case Level::Danger: return QColor(224, 80, 80);
    }
    return Qt::gray;
}

void SafetyIndicator::setLevel(Level level) {
    m_level = level;
    setToolTip(level == Level::Safe      ? "SAFE"
               : level == Level::Caution ? "CAUTION"
                                         : "DANGER");
    update();
}

void SafetyIndicator::paintEvent(QPaintEvent*) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    const QColor c = colorFor(m_level);
    p.setPen(QPen(c.darker(140), 1));
    p.setBrush(c);
    p.drawEllipse(rect().adjusted(2, 2, -2, -2));
}
