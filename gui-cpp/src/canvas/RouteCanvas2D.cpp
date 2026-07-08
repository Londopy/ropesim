// gui-cpp/src/canvas/RouteCanvas2D.cpp

#include "canvas/RouteCanvas2D.h"

#include <QGraphicsScene>
#include <QMouseEvent>
#include <QPainter>
#include <QPainterPath>

#include <cmath>

RouteCanvas2D::RouteCanvas2D(QWidget* parent)
    : QGraphicsView(parent), m_scene(new QGraphicsScene(this)) {
    setScene(m_scene);
    setRenderHint(QPainter::Antialiasing);
    setDragMode(QGraphicsView::ScrollHandDrag);
    setBackgroundBrush(QColor(14, 18, 16));
    m_scene->setSceneRect(-80, -kWallHeightM * kPxPerM - 60, 480,
                          kWallHeightM * kPxPerM + 140);
    rebuild();
}

QPointF RouteCanvas2D::metresToScene(double xM, double yM) const {
    // y up in metres → y down in scene
    return {xM * kPxPerM, -yM * kPxPerM};
}

QPointF RouteCanvas2D::sceneToMetres(const QPointF& s) const {
    return {s.x() / kPxPerM, -s.y() / kPxPerM};
}

void RouteCanvas2D::setPlacementMode(int mode) {
    m_placementMode = mode;
    setCursor(mode == 0 ? Qt::OpenHandCursor : Qt::CrossCursor);
    setDragMode(mode == 0 ? QGraphicsView::ScrollHandDrag
                          : QGraphicsView::NoDrag);
}

void RouteCanvas2D::setGear(const std::vector<GearInstance>& gear) {
    m_gear = gear;
    rebuild();
}

void RouteCanvas2D::setClimberHeight(double heightM) {
    m_climberHeightM = heightM;
    rebuild();
}

void RouteCanvas2D::setRouteAngleDeg(double deg) {
    m_routeAngleDeg = deg;
    rebuild();
    viewport()->update();
}

void RouteCanvas2D::setRopePath(const std::vector<QPointF>& metresXY) {
    m_ropePath = metresXY;
    rebuild();
}

void RouteCanvas2D::mousePressEvent(QMouseEvent* e) {
    if (m_placementMode != 0 && e->button() == Qt::LeftButton) {
        const QPointF m = sceneToMetres(mapToScene(e->pos()));
        if (m.y() >= 0.0 && m.y() <= kWallHeightM) {
            // 2D canvas: x is lateral offset from the wall line, z = 0
            emit gearPlaced(m_placementMode, static_cast<float>(m.x()),
                            static_cast<float>(m.y()), 0.0f);
        }
        return;
    }
    QGraphicsView::mousePressEvent(e);
}

void RouteCanvas2D::drawBackground(QPainter* p, const QRectF& rect) {
    QGraphicsView::drawBackground(p, rect);
    // Height grid every 5 m
    p->setPen(QPen(QColor(40, 52, 45), 0));
    for (int h = 0; h <= static_cast<int>(kWallHeightM); h += 5) {
        const QPointF a = metresToScene(-2.5, h);
        const QPointF b = metresToScene(14.0, h);
        p->drawLine(a, b);
        p->setPen(QPen(QColor(96, 118, 104), 0));
        p->drawText(QPointF(b.x() + 6, b.y() + 4), QStringLiteral("%1 m").arg(h));
        p->setPen(QPen(QColor(40, 52, 45), 0));
    }
}

void RouteCanvas2D::rebuild() {
    m_scene->clear();

    // Wall profile: lean by (routeAngle − 90°)
    const double leanRad =
        (m_routeAngleDeg - 90.0) * M_PI / 180.0; // >0 = overhanging
    QPainterPath wall;
    wall.moveTo(metresToScene(0.0, 0.0));
    const double topX = -std::tan(leanRad) * kWallHeightM;
    wall.lineTo(metresToScene(topX, kWallHeightM));
    wall.lineTo(metresToScene(topX - 3.0, kWallHeightM));
    wall.lineTo(metresToScene(-3.0, 0.0));
    wall.closeSubpath();
    m_scene->addPath(wall, QPen(QColor(70, 88, 76), 2),
                     QBrush(QColor(28, 36, 31)));

    // Rope path
    if (m_ropePath.size() >= 2) {
        QPainterPath rope;
        rope.moveTo(metresToScene(m_ropePath[0].x(), m_ropePath[0].y()));
        for (size_t i = 1; i < m_ropePath.size(); ++i)
            rope.lineTo(metresToScene(m_ropePath[i].x(), m_ropePath[i].y()));
        m_scene->addPath(rope, QPen(QColor(126, 207, 69), 2));
    }

    // Gear markers
    for (const auto& g : m_gear) {
        const QPointF c = metresToScene(g.position.x, g.position.y);
        const QColor col = g.type == GearType::Bolt   ? QColor(120, 170, 255)
                           : g.type == GearType::Cam  ? QColor(255, 170, 90)
                                                      : QColor(200, 140, 255);
        auto* item = m_scene->addEllipse(c.x() - 5, c.y() - 5, 10, 10,
                                         QPen(col.darker(130), 1.5),
                                         QBrush(col));
        item->setToolTip(g.type == GearType::Bolt  ? "Bolt"
                         : g.type == GearType::Cam ? "Cam"
                                                   : "Nut");
    }

    // Climber
    const double leanX =
        -std::tan(leanRad) * m_climberHeightM; // follow the wall
    const QPointF climber = metresToScene(leanX + 0.4, m_climberHeightM);
    m_scene->addEllipse(climber.x() - 7, climber.y() - 7, 14, 14,
                        QPen(QColor(230, 90, 70), 2),
                        QBrush(QColor(230, 90, 70, 120)));
}
