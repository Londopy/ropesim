// gui-cpp/src/canvas/RouteCanvas2D.h
//
// 2D route builder: QGraphicsScene with a wall profile, gear items and a
// climber marker.  Click to place gear when a placement mode is active.

#pragma once

#include <QGraphicsView>
#include <optional>
#include <vector>

#include "renderer/GearRenderer.h" // GearInstance/GearType (shared plain structs)

class QGraphicsScene;
class QGraphicsEllipseItem;

class RouteCanvas2D : public QGraphicsView {
    Q_OBJECT
public:
    explicit RouteCanvas2D(QWidget* parent = nullptr);

    void setPlacementMode(int mode); // PlacementMode enum value from Viewport3D
    void setGear(const std::vector<GearInstance>& gear);
    void setClimberHeight(double heightM);
    void setRouteAngleDeg(double deg);
    void setRopePath(const std::vector<QPointF>& metresXY);

signals:
    void gearPlaced(int gearType, float x, float y, float z);

protected:
    void mousePressEvent(QMouseEvent* e) override;
    void drawBackground(QPainter* painter, const QRectF& rect) override;

private:
    QPointF metresToScene(double xM, double yM) const;
    QPointF sceneToMetres(const QPointF& scene) const;
    void rebuild();

    QGraphicsScene* m_scene;
    int m_placementMode = 0;
    double m_routeAngleDeg = 90.0;
    double m_climberHeightM = 10.0;
    std::vector<GearInstance> m_gear;
    std::vector<QPointF> m_ropePath;

    static constexpr double kPxPerM = 24.0;
    static constexpr double kWallHeightM = 30.0;
};
