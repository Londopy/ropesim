// gui-cpp/src/canvas/Viewport3D.cpp

#include "canvas/Viewport3D.h"

#include <QKeyEvent>
#include <QMouseEvent>
#include <QOpenGLContext>
#include <QOpenGLExtraFunctions>
#include <QWheelEvent>
#include <glm/gtc/matrix_transform.hpp>

#include <algorithm>
#include <cmath>

Viewport3D::Viewport3D(QWidget* parent) : QOpenGLWidget(parent) {
    setFocusPolicy(Qt::StrongFocus);
    setMouseTracking(true);
    m_playTimer.setInterval(1000 / 60);
    connect(&m_playTimer, &QTimer::timeout, this, &Viewport3D::advancePlayback);
}

Viewport3D::~Viewport3D() {
    // Destroy GL resources with the context current.
    makeCurrent();
    m_ropeRenderer.reset();
    m_gearRenderer.reset();
    m_rockRenderer.reset();
    m_arrowRenderer.reset();
    m_markerRenderer.reset();
    doneCurrent();
}

// ── GL lifecycle ─────────────────────────────────────────────────────────────

void Viewport3D::initializeGL() {
    auto* f = QOpenGLContext::currentContext()->extraFunctions();
    f->glEnable(GL_DEPTH_TEST);
    f->glClearColor(0.055f, 0.07f, 0.065f, 1.0f);

    m_ropeRenderer = std::make_unique<RopeRenderer>();
    m_gearRenderer = std::make_unique<GearRenderer>();
    m_rockRenderer = std::make_unique<RockFaceRenderer>();
    m_arrowRenderer = std::make_unique<ForceArrowRenderer>();
    m_markerRenderer = std::make_unique<GearRenderer>();

    m_ropeRenderer->initialize();
    m_gearRenderer->initialize();
    m_rockRenderer->initialize();
    m_arrowRenderer->initialize();
    m_markerRenderer->initialize();

    if (!m_ropePositions.empty())
        m_ropeRenderer->updatePositions(m_ropePositions, m_ropeTensions,
                                        m_ropeRadius);
}

void Viewport3D::resizeGL(int, int) {}

void Viewport3D::paintGL() {
    auto* f = QOpenGLContext::currentContext()->extraFunctions();
    f->glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

    const glm::mat4 view = viewMatrix();
    const glm::mat4 proj = projMatrix();
    const glm::vec3 light = glm::normalize(glm::vec3(-0.4f, -0.7f, -0.6f));

    m_rockRenderer->draw(view, proj, light);
    m_ropeRenderer->draw(view, proj, light);
    m_gearRenderer->draw(view, proj, light);
    m_arrowRenderer->draw(view, proj);
    drawClimberAndPreview();
}

void Viewport3D::drawClimberAndPreview() {
    // Reuse the gear renderer with synthetic instances for the climber
    // capsule (approximated by a cam box) and the placement preview marker.
    std::vector<GearInstance> markers;
    if (m_climberPos) {
        GearInstance climber;
        climber.type = GearType::Cam;
        climber.position = *m_climberPos;
        climber.orientation = {0.0f, 0.0f, 1.0f};
        climber.loadFraction = 0.0;
        markers.push_back(climber);
    }
    if (m_placementMode != PlacementMode::None && m_placementPreview) {
        GearInstance preview;
        preview.type = m_placementMode == PlacementMode::AddBolt ? GearType::Bolt
                       : m_placementMode == PlacementMode::AddCam ? GearType::Cam
                                                                  : GearType::Nut;
        preview.position = *m_placementPreview;
        preview.orientation = m_rockRenderer->lastHitNormal();
        preview.loadFraction = 0.5; // yellow — "pending"
        markers.push_back(preview);
    }
    if (markers.empty()) return;
    const glm::vec3 light = glm::normalize(glm::vec3(-0.4f, -0.7f, -0.6f));
    m_markerRenderer->setGear(markers);
    m_markerRenderer->draw(viewMatrix(), projMatrix(), light);
}

// ── Camera ───────────────────────────────────────────────────────────────────

glm::vec3 Viewport3D::cameraPosition() const {
    const float yaw = glm::radians(m_yawDeg);
    const float pitch = glm::radians(m_pitchDeg);
    const glm::vec3 offset(m_distance * std::cos(pitch) * std::sin(yaw),
                           m_distance * std::sin(pitch),
                           m_distance * std::cos(pitch) * std::cos(yaw));
    return m_target + offset;
}

glm::mat4 Viewport3D::viewMatrix() const {
    return glm::lookAt(cameraPosition(), m_target, glm::vec3(0, 1, 0));
}

glm::mat4 Viewport3D::projMatrix() const {
    const float aspect =
        height() > 0 ? static_cast<float>(width()) / height() : 1.0f;
    return glm::perspective(glm::radians(m_fovDeg), aspect, 0.05f, 500.0f);
}

std::pair<glm::vec3, glm::vec3> Viewport3D::screenRay(const QPoint& px) const {
    const float x = 2.0f * px.x() / std::max(width(), 1) - 1.0f;
    const float y = 1.0f - 2.0f * px.y() / std::max(height(), 1);
    const glm::mat4 inv = glm::inverse(projMatrix() * viewMatrix());
    glm::vec4 nearP = inv * glm::vec4(x, y, -1.0f, 1.0f);
    glm::vec4 farP = inv * glm::vec4(x, y, 1.0f, 1.0f);
    nearP /= nearP.w;
    farP /= farP.w;
    return {glm::vec3(nearP), glm::normalize(glm::vec3(farP - nearP))};
}

void Viewport3D::resetCamera() {
    m_target = {0.0f, 8.0f, 0.0f};
    m_distance = 18.0f;
    m_yawDeg = 20.0f;
    m_pitchDeg = 10.0f;
    m_fovDeg = 45.0f;
    update();
}

// ── Input ────────────────────────────────────────────────────────────────────

void Viewport3D::mousePressEvent(QMouseEvent* e) {
    m_lastMouse = e->pos();
    if (e->button() == Qt::LeftButton &&
        m_placementMode != PlacementMode::None) {
        const auto [origin, dir] = screenRay(e->pos());
        if (const auto hit = m_rockRenderer->raycast(origin, dir)) {
            emit gearPlaced(static_cast<int>(m_placementMode), hit->x, hit->y,
                            hit->z);
        }
    }
}

void Viewport3D::mouseMoveEvent(QMouseEvent* e) {
    const QPoint delta = e->pos() - m_lastMouse;

    if (m_placementMode != PlacementMode::None) {
        const auto [origin, dir] = screenRay(e->pos());
        m_placementPreview = m_rockRenderer->raycast(origin, dir);
        update();
    }

    if (e->buttons() & Qt::LeftButton && m_placementMode == PlacementMode::None) {
        // Orbit (arcball-style)
        m_yawDeg -= delta.x() * 0.4f;
        m_pitchDeg = std::clamp(m_pitchDeg + delta.y() * 0.4f, -85.0f, 85.0f);
        update();
    } else if (e->buttons() & Qt::MiddleButton) {
        // Pan in camera plane
        const glm::mat4 view = viewMatrix();
        const glm::vec3 right(view[0][0], view[1][0], view[2][0]);
        const glm::vec3 up(view[0][1], view[1][1], view[2][1]);
        const float scale = m_distance * 0.0018f;
        m_target += (-right * static_cast<float>(delta.x()) +
                     up * static_cast<float>(delta.y())) *
                    scale;
        update();
    }
    m_lastMouse = e->pos();
}

void Viewport3D::wheelEvent(QWheelEvent* e) {
    const float steps = e->angleDelta().y() / 120.0f;
    m_distance = std::clamp(m_distance * std::pow(0.9f, steps), 1.0f, 120.0f);
    update();
}

void Viewport3D::keyPressEvent(QKeyEvent* e) {
    switch (e->key()) {
        case Qt::Key_R: resetCamera(); break;
        case Qt::Key_1: m_yawDeg = 0.0f;  m_pitchDeg = 0.0f;  update(); break; // front
        case Qt::Key_2: m_yawDeg = 90.0f; m_pitchDeg = 0.0f;  update(); break; // side
        case Qt::Key_3: m_yawDeg = 0.0f;  m_pitchDeg = 84.0f; update(); break; // top
        case Qt::Key_I: m_yawDeg = 45.0f; m_pitchDeg = 30.0f; update(); break; // iso
        default: QOpenGLWidget::keyPressEvent(e);
    }
}

// ── Scene content ────────────────────────────────────────────────────────────

void Viewport3D::setRope(const std::vector<glm::vec3>& positions,
                         const std::vector<double>& tensions,
                         float diameterMm) {
    m_ropePositions = positions;
    m_ropeTensions = tensions;
    // Scene exaggeration: real 10 mm rope would be invisible at 20 m scale.
    m_ropeRadius = std::max(diameterMm, 6.0f) / 1000.0f * 4.0f;
    if (m_ropeRenderer) {
        makeCurrent();
        m_ropeRenderer->updatePositions(positions, tensions, m_ropeRadius);
        doneCurrent();
    }
    update();
}

void Viewport3D::setGear(const std::vector<GearInstance>& gear) {
    if (m_gearRenderer) m_gearRenderer->setGear(gear);
    update();
}

void Viewport3D::setForceArrows(const std::vector<ForceArrow>& arrows) {
    if (m_arrowRenderer) m_arrowRenderer->setArrows(arrows);
    update();
}

void Viewport3D::setClimberPosition(std::optional<glm::vec3> pos) {
    m_climberPos = pos;
    update();
}

void Viewport3D::setRockPreset(RockFacePreset preset) {
    if (m_rockRenderer) {
        makeCurrent();
        m_rockRenderer->setGeometry(preset);
        doneCurrent();
    }
    update();
}

void Viewport3D::setRockType(RockTextureType type) {
    if (m_rockRenderer) {
        makeCurrent();
        m_rockRenderer->setRockType(type);
        doneCurrent();
    }
    update();
}

bool Viewport3D::loadCustomRockMesh(const QString& path) {
    if (!m_rockRenderer) return false;
    makeCurrent();
    const bool ok = m_rockRenderer->loadCustomMesh(path.toStdString());
    doneCurrent();
    update();
    return ok;
}

void Viewport3D::setPlacementMode(PlacementMode mode) {
    m_placementMode = mode;
    m_placementPreview.reset();
    setCursor(mode == PlacementMode::None ? Qt::ArrowCursor
                                          : Qt::CrossCursor);
    update();
}

// ── Playback ─────────────────────────────────────────────────────────────────

void Viewport3D::loadReplay(const SimFrameData& frames) {
    m_replay = frames;
    m_playbackFrame = 0;
    if (!m_replay.empty()) setPlaybackFrame(0);
}

void Viewport3D::setPlaybackFrame(int frame) {
    if (m_replay.empty()) return;
    m_playbackFrame =
        std::clamp(frame, 0, static_cast<int>(m_replay.frames.size()) - 1);
    const SimFrame& f = m_replay.frames[m_playbackFrame];

    // Tension per link estimated from anchor force falloff along the rope.
    std::vector<double> tensions(f.ropePositions.size());
    for (size_t i = 0; i < tensions.size(); ++i) {
        const double falloff =
            1.0 - 0.4 * (static_cast<double>(i) / std::max(tensions.size() - 1,
                                                            size_t{1}));
        tensions[i] = std::clamp(f.anchorForceKn / 12.0 * falloff, 0.0, 1.0);
    }
    setRope(f.ropePositions, tensions, m_ropeRadius * 250.0f);
    setClimberPosition(f.climberPosition);
    emit playbackFrameChanged(m_playbackFrame);
}

void Viewport3D::play() {
    if (!m_replay.empty()) m_playTimer.start();
}

void Viewport3D::pause() { m_playTimer.stop(); }

void Viewport3D::setSpeed(double speed) {
    m_speed = std::clamp(speed, 0.05, 4.0);
}

void Viewport3D::advancePlayback() {
    if (m_replay.empty()) return;
    // Frames are dtSeconds apart; advance to match wall clock * speed.
    const double framesPerTick =
        (1.0 / 60.0) * m_speed / std::max(m_replay.dtSeconds, 1e-6);
    static double accumulator = 0.0;
    accumulator += framesPerTick;
    const int step = static_cast<int>(accumulator);
    if (step < 1) return;
    accumulator -= step;

    int next = m_playbackFrame + step;
    const int last = static_cast<int>(m_replay.frames.size()) - 1;
    if (next > last) {
        if (m_loop) {
            next = 0;
        } else {
            next = last;
            pause();
        }
    }
    setPlaybackFrame(next);
}
