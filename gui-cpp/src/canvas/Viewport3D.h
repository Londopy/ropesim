// gui-cpp/src/canvas/Viewport3D.h
//
// Main 3D rendering surface (QOpenGLWidget, GL 4.1 core).
// Orbit/pan/zoom camera, gear placement raycasting, simulation playback.

#pragma once

#include <QOpenGLWidget>
#include <QTimer>
#include <glm/glm.hpp>
#include <memory>
#include <optional>
#include <vector>

#include "core/SimulationResult.h"
#include "renderer/ForceArrowRenderer.h"
#include "renderer/GearRenderer.h"
#include "renderer/RockFaceRenderer.h"
#include "renderer/RopeRenderer.h"

enum class PlacementMode { None, AddBolt, AddCam, AddNut };

class Viewport3D : public QOpenGLWidget {
    Q_OBJECT
public:
    explicit Viewport3D(QWidget* parent = nullptr);
    ~Viewport3D() override;

    // ── Scene content ────────────────────────────────────────────────────
    void setRope(const std::vector<glm::vec3>& positions,
                 const std::vector<double>& tensions,
                 float diameterMm = 9.8f);
    void setGear(const std::vector<GearInstance>& gear);
    void setForceArrows(const std::vector<ForceArrow>& arrows);
    void setClimberPosition(std::optional<glm::vec3> pos);
    void setRockPreset(RockFacePreset preset);
    void setRockType(RockTextureType type);
    bool loadCustomRockMesh(const QString& path);

    // ── Placement mode ───────────────────────────────────────────────────
    void setPlacementMode(PlacementMode mode);
    PlacementMode placementMode() const { return m_placementMode; }

    // ── Playback ─────────────────────────────────────────────────────────
    void loadReplay(const SimFrameData& frames);
    void setPlaybackFrame(int frame);
    int playbackFrame() const { return m_playbackFrame; }
    int frameCount() const { return static_cast<int>(m_replay.frames.size()); }
    void play();
    void pause();
    bool isPlaying() const { return m_playTimer.isActive(); }
    void setSpeed(double speed); // 0.1x … 1x
    void setLoop(bool loop) { m_loop = loop; }

signals:
    void gearPlaced(int gearType /* PlacementMode value */, float x, float y, float z);
    void playbackFrameChanged(int frame);

protected:
    void initializeGL() override;
    void resizeGL(int w, int h) override;
    void paintGL() override;

    void mousePressEvent(QMouseEvent* e) override;
    void mouseMoveEvent(QMouseEvent* e) override;
    void wheelEvent(QWheelEvent* e) override;
    void keyPressEvent(QKeyEvent* e) override;

private:
    glm::mat4 viewMatrix() const;
    glm::mat4 projMatrix() const;
    glm::vec3 cameraPosition() const;
    // Ray from a screen pixel into the scene.
    std::pair<glm::vec3, glm::vec3> screenRay(const QPoint& px) const;
    void resetCamera();
    void advancePlayback();
    void drawClimberAndPreview();

    std::unique_ptr<RopeRenderer> m_ropeRenderer;
    std::unique_ptr<GearRenderer> m_gearRenderer;
    std::unique_ptr<RockFaceRenderer> m_rockRenderer;
    std::unique_ptr<ForceArrowRenderer> m_arrowRenderer;
    // Small helper renderer reused for climber capsule + placement preview.
    std::unique_ptr<GearRenderer> m_markerRenderer;

    // Camera (orbit around target)
    glm::vec3 m_target{0.0f, 8.0f, 0.0f};
    float m_distance = 18.0f;
    float m_yawDeg = 20.0f;
    float m_pitchDeg = 10.0f;
    float m_fovDeg = 45.0f;

    QPoint m_lastMouse;
    PlacementMode m_placementMode = PlacementMode::None;
    std::optional<glm::vec3> m_placementPreview;

    std::optional<glm::vec3> m_climberPos;
    float m_ropeRadius = 0.02f;
    std::vector<glm::vec3> m_ropePositions;
    std::vector<double> m_ropeTensions;

    // Playback
    SimFrameData m_replay;
    int m_playbackFrame = 0;
    double m_speed = 1.0;
    bool m_loop = false;
    QTimer m_playTimer;
};
