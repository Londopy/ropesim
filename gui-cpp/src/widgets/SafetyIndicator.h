// gui-cpp/src/widgets/SafetyIndicator.h
//
// Small coloured status dot: SAFE (green) / CAUTION (amber) / DANGER (red).

#pragma once

#include <QWidget>

class SafetyIndicator : public QWidget {
    Q_OBJECT
public:
    enum class Level { Safe, Caution, Danger };

    explicit SafetyIndicator(QWidget* parent = nullptr);
    void setLevel(Level level);
    Level level() const { return m_level; }
    static QColor colorFor(Level level);

protected:
    void paintEvent(QPaintEvent*) override;

private:
    Level m_level = Level::Safe;
};
