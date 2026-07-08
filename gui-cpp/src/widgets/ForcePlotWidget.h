// gui-cpp/src/widgets/ForcePlotWidget.h
//
// Custom OpenGL force-curve plot: multiple series, zoom/pan, hover value
// readout, annotations, PNG export.  Renders at 60 fps for live updates.

#pragma once

#include <QOpenGLWidget>
#include <QString>
#include <QStringList>
#include <vector>

class ForcePlotWidget : public QOpenGLWidget {
    Q_OBJECT
public:
    explicit ForcePlotWidget(QWidget* parent = nullptr);

    void plotForceCurve(const std::vector<double>& times,
                        const std::vector<double>& forces,
                        const QString& label);
    void plotAnchorSweep(const std::vector<double>& angles,
                         const std::vector<std::vector<double>>& perBoltForces,
                         const QStringList& boltLabels);
    void plotEnergyBudget(double pe, double rope, double belay, double residual);
    void addAnnotation(double x, const QString& label);
    void clear();
    bool exportPng(const QString& path);

protected:
    // All drawing via QPainter over the GL surface — fast enough at 60 fps
    // and keeps text rendering crisp.
    void paintGL() override;
    void wheelEvent(QWheelEvent* e) override;
    void mouseMoveEvent(QMouseEvent* e) override;
    void mousePressEvent(QMouseEvent* e) override;
    void mouseDoubleClickEvent(QMouseEvent* e) override;

private:
    struct Series {
        QString label;
        std::vector<double> x;
        std::vector<double> y;
        QColor color;
    };
    struct Annotation {
        double x;
        QString label;
    };
    struct Bar { // energy budget mode
        QString label;
        double joules;
        QColor color;
    };

    QRectF plotArea() const;
    QPointF dataToPixel(double x, double y) const;
    void computeAutoRange();

    std::vector<Series> m_series;
    std::vector<Annotation> m_annotations;
    std::vector<Bar> m_bars; // when non-empty, draw stacked bar mode
    QString m_xLabel = "time (ms)";
    QString m_yLabel = "force (kN)";

    double m_xMin = 0.0, m_xMax = 1.0, m_yMin = 0.0, m_yMax = 1.0;
    bool m_autoRange = true;
    QPointF m_hoverPx{-1, -1};
    QPoint m_lastMouse;
};
