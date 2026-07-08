// gui-cpp/src/widgets/ForcePlotWidget.cpp

#include "widgets/ForcePlotWidget.h"

#include <QMouseEvent>
#include <QPainter>
#include <QPainterPath>
#include <QWheelEvent>

#include <algorithm>
#include <cmath>

namespace {
const QColor kSeriesColors[] = {
    QColor(126, 207, 69),  QColor(120, 170, 255), QColor(255, 170, 90),
    QColor(200, 140, 255), QColor(90, 220, 210),  QColor(240, 120, 130),
};
} // namespace

ForcePlotWidget::ForcePlotWidget(QWidget* parent) : QOpenGLWidget(parent) {
    setMouseTracking(true);
    setMinimumHeight(160);
}

void ForcePlotWidget::plotForceCurve(const std::vector<double>& times,
                                     const std::vector<double>& forces,
                                     const QString& label) {
    m_bars.clear();
    Series s;
    s.label = label;
    s.x = times;
    s.y = forces;
    s.color = kSeriesColors[m_series.size() % 6];
    m_series.push_back(std::move(s));
    m_xLabel = "time (ms)";
    m_yLabel = "force (kN)";
    if (m_autoRange) computeAutoRange();
    update();
}

void ForcePlotWidget::plotAnchorSweep(
    const std::vector<double>& angles,
    const std::vector<std::vector<double>>& perBoltForces,
    const QStringList& boltLabels) {
    clear();
    for (size_t b = 0; b < perBoltForces.size(); ++b) {
        Series s;
        s.label = b < static_cast<size_t>(boltLabels.size())
                      ? boltLabels[static_cast<int>(b)]
                      : QStringLiteral("bolt %1").arg(b + 1);
        s.x = angles;
        s.y = perBoltForces[b];
        s.color = kSeriesColors[b % 6];
        m_series.push_back(std::move(s));
    }
    m_xLabel = "anchor angle (deg)";
    m_yLabel = "per-bolt force (kN)";
    computeAutoRange();
    update();
}

void ForcePlotWidget::plotEnergyBudget(double pe, double rope, double belay,
                                       double residual) {
    clear();
    m_bars = {
        {"PE", pe, QColor(120, 170, 255)},
        {"rope", rope, QColor(126, 207, 69)},
        {"belay", belay, QColor(255, 170, 90)},
        {"residual", residual, QColor(240, 120, 130)},
    };
    update();
}

void ForcePlotWidget::addAnnotation(double x, const QString& label) {
    m_annotations.push_back({x, label});
    update();
}

void ForcePlotWidget::clear() {
    m_series.clear();
    m_annotations.clear();
    m_bars.clear();
    m_autoRange = true;
    update();
}

bool ForcePlotWidget::exportPng(const QString& path) {
    return grabFramebuffer().save(path, "PNG");
}

QRectF ForcePlotWidget::plotArea() const {
    return QRectF(52, 14, width() - 66, height() - 46);
}

QPointF ForcePlotWidget::dataToPixel(double x, double y) const {
    const QRectF a = plotArea();
    const double px =
        a.left() + (x - m_xMin) / std::max(m_xMax - m_xMin, 1e-12) * a.width();
    const double py = a.bottom() -
                      (y - m_yMin) / std::max(m_yMax - m_yMin, 1e-12) * a.height();
    return {px, py};
}

void ForcePlotWidget::computeAutoRange() {
    m_xMin = m_yMin = std::numeric_limits<double>::max();
    m_xMax = m_yMax = std::numeric_limits<double>::lowest();
    for (const auto& s : m_series) {
        for (double v : s.x) { m_xMin = std::min(m_xMin, v); m_xMax = std::max(m_xMax, v); }
        for (double v : s.y) { m_yMin = std::min(m_yMin, v); m_yMax = std::max(m_yMax, v); }
    }
    if (m_series.empty()) { m_xMin = 0; m_xMax = 1; m_yMin = 0; m_yMax = 1; }
    m_yMin = std::min(m_yMin, 0.0);
    m_yMax *= 1.08;
    if (m_yMax <= m_yMin) m_yMax = m_yMin + 1.0;
}

void ForcePlotWidget::paintGL() {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    p.fillRect(rect(), QColor(15, 20, 16)); // dark theme

    const QRectF a = plotArea();

    // ── Stacked energy bar mode ─────────────────────────────────────────
    if (!m_bars.empty()) {
        double total = 0.0;
        for (const auto& b : m_bars) total += std::max(b.joules, 0.0);
        total = std::max(total, 1e-9);
        double x = a.left();
        const double h = 34.0;
        const double y = a.center().y() - h / 2;
        p.setPen(Qt::NoPen);
        for (const auto& b : m_bars) {
            const double w = std::max(b.joules, 0.0) / total * a.width();
            p.setBrush(b.color);
            p.drawRect(QRectF(x, y, w, h));
            if (w > 46) {
                p.setPen(QColor(10, 12, 11));
                p.drawText(QRectF(x, y, w, h), Qt::AlignCenter,
                           QStringLiteral("%1\n%2 J")
                               .arg(b.label)
                               .arg(b.joules, 0, 'f', 0));
                p.setPen(Qt::NoPen);
            }
            x += w;
        }
        // Legend under the bar for thin segments
        p.setPen(QColor(150, 170, 155));
        QString legend;
        for (const auto& b : m_bars)
            legend += QStringLiteral("%1 %2 J   ").arg(b.label).arg(b.joules, 0, 'f', 0);
        p.drawText(QRectF(a.left(), y + h + 8, a.width(), 18),
                   Qt::AlignHCenter, legend.trimmed());
        return;
    }

    // ── Axes + grid ─────────────────────────────────────────────────────
    p.setPen(QPen(QColor(36, 43, 37), 1));
    for (int i = 0; i <= 4; ++i) {
        const double y = a.top() + a.height() * i / 4.0;
        p.drawLine(QPointF(a.left(), y), QPointF(a.right(), y));
    }
    p.setPen(QColor(107, 125, 108));
    p.setFont(QFont(p.font().family(), 8));
    for (int i = 0; i <= 4; ++i) {
        const double v = m_yMax - (m_yMax - m_yMin) * i / 4.0;
        const double y = a.top() + a.height() * i / 4.0;
        p.drawText(QRectF(0, y - 8, 46, 16), Qt::AlignRight | Qt::AlignVCenter,
                   QString::number(v, 'f', 1));
    }
    for (int i = 0; i <= 5; ++i) {
        const double v = m_xMin + (m_xMax - m_xMin) * i / 5.0;
        const double x = a.left() + a.width() * i / 5.0;
        p.drawText(QRectF(x - 30, a.bottom() + 4, 60, 16), Qt::AlignHCenter,
                   QString::number(v, 'f', 0));
    }
    p.drawText(QRectF(0, height() - 18, width(), 16), Qt::AlignHCenter, m_xLabel);

    // ── Series ──────────────────────────────────────────────────────────
    p.setClipRect(a);
    for (const auto& s : m_series) {
        if (s.x.size() < 2) continue;
        QPainterPath path;
        path.moveTo(dataToPixel(s.x[0], s.y[0]));
        for (size_t i = 1; i < s.x.size(); ++i)
            path.lineTo(dataToPixel(s.x[i], s.y[i]));
        p.setPen(QPen(s.color, 1.8));
        p.setBrush(Qt::NoBrush);
        p.drawPath(path);
    }

    // ── Annotations ─────────────────────────────────────────────────────
    for (const auto& an : m_annotations) {
        const double x = dataToPixel(an.x, 0).x();
        p.setPen(QPen(QColor(232, 184, 75), 1, Qt::DashLine));
        p.drawLine(QPointF(x, a.top()), QPointF(x, a.bottom()));
        p.setPen(QColor(232, 184, 75));
        p.drawText(QPointF(x + 4, a.top() + 12), an.label);
    }
    p.setClipping(false);

    // ── Legend ──────────────────────────────────────────────────────────
    double lx = a.left() + 8;
    for (const auto& s : m_series) {
        p.setPen(QPen(s.color, 3));
        p.drawLine(QPointF(lx, a.top() + 8), QPointF(lx + 14, a.top() + 8));
        p.setPen(QColor(214, 232, 215));
        p.drawText(QPointF(lx + 18, a.top() + 12), s.label);
        lx += 30 + p.fontMetrics().horizontalAdvance(s.label);
    }

    // ── Hover readout ───────────────────────────────────────────────────
    if (a.contains(m_hoverPx) && !m_series.empty()) {
        const double dataX =
            m_xMin + (m_hoverPx.x() - a.left()) / a.width() * (m_xMax - m_xMin);
        const auto& s = m_series.front();
        // nearest sample
        size_t best = 0;
        double bestD = std::numeric_limits<double>::max();
        for (size_t i = 0; i < s.x.size(); ++i) {
            const double d = std::abs(s.x[i] - dataX);
            if (d < bestD) { bestD = d; best = i; }
        }
        if (best < s.y.size()) {
            const QPointF px = dataToPixel(s.x[best], s.y[best]);
            p.setPen(QPen(QColor(237, 245, 238), 1));
            p.setBrush(QColor(23, 28, 24));
            const QString txt = QStringLiteral("%1, %2")
                                    .arg(s.x[best], 0, 'f', 1)
                                    .arg(s.y[best], 0, 'f', 2);
            const QRectF box(px + QPointF(8, -22),
                             QSizeF(p.fontMetrics().horizontalAdvance(txt) + 12, 18));
            p.drawRoundedRect(box, 3, 3);
            p.drawText(box, Qt::AlignCenter, txt);
            p.setBrush(QColor(126, 207, 69));
            p.drawEllipse(px, 3, 3);
        }
    }
}

void ForcePlotWidget::wheelEvent(QWheelEvent* e) {
    if (m_series.empty()) return;
    const double zoom = std::pow(0.9, e->angleDelta().y() / 120.0);
    const QRectF a = plotArea();
    const double cx =
        m_xMin + (e->position().x() - a.left()) / a.width() * (m_xMax - m_xMin);
    m_xMin = cx - (cx - m_xMin) * zoom;
    m_xMax = cx + (m_xMax - cx) * zoom;
    m_autoRange = false;
    update();
}

void ForcePlotWidget::mouseMoveEvent(QMouseEvent* e) {
    m_hoverPx = e->position();
    if (e->buttons() & Qt::LeftButton && !m_series.empty()) {
        const QRectF a = plotArea();
        const double dx = (e->pos().x() - m_lastMouse.x()) / a.width() *
                          (m_xMax - m_xMin);
        m_xMin -= dx;
        m_xMax -= dx;
        m_autoRange = false;
    }
    m_lastMouse = e->pos();
    update();
}

void ForcePlotWidget::mousePressEvent(QMouseEvent* e) { m_lastMouse = e->pos(); }

void ForcePlotWidget::mouseDoubleClickEvent(QMouseEvent*) {
    m_autoRange = true;
    computeAutoRange();
    update();
}
