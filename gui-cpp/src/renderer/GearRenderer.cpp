// gui-cpp/src/renderer/GearRenderer.cpp

#include "renderer/GearRenderer.h"

#include <QOpenGLContext>
#include <QOpenGLExtraFunctions>
#include <glm/gtc/matrix_transform.hpp>
#include <glm/gtc/type_ptr.hpp>

#include <algorithm>
#include <cmath>

namespace { constexpr double kPi = 3.14159265358979323846; }

namespace {
void pushTri(std::vector<float>& out, glm::vec3 a, glm::vec3 b, glm::vec3 c) {
    const glm::vec3 n = glm::normalize(glm::cross(b - a, c - a));
    for (const auto& p : {a, b, c}) {
        out.insert(out.end(), {p.x, p.y, p.z, n.x, n.y, n.z});
    }
}

glm::vec3 loadColor(double frac) {
    const float t = static_cast<float>(std::clamp(frac, 0.0, 1.0));
    if (t < 0.5f) return glm::mix(glm::vec3(0.3f, 0.8f, 0.35f),
                                  glm::vec3(0.95f, 0.85f, 0.15f), t * 2.0f);
    return glm::mix(glm::vec3(0.95f, 0.85f, 0.15f),
                    glm::vec3(0.95f, 0.15f, 0.10f), (t - 0.5f) * 2.0f);
}
} // namespace

bool GearRenderer::initialize() {
    if (!m_program.addShaderFromSourceFile(QOpenGLShader::Vertex,
                                           "shaders/gear.vert") ||
        !m_program.addShaderFromSourceFile(QOpenGLShader::Fragment,
                                           "shaders/gear.frag") ||
        !m_program.link()) {
        qWarning("GearRenderer: shader error: %s", qPrintable(m_program.log()));
        return false;
    }
    buildBolt();
    buildCam();
    buildNut();
    m_ready = true;
    return true;
}

void GearRenderer::buildMesh(Mesh& mesh, const std::vector<float>& data) {
    mesh.vao.create();
    mesh.vao.bind();
    mesh.vbo.create();
    mesh.vbo.bind();
    mesh.vbo.allocate(data.data(), static_cast<int>(data.size() * sizeof(float)));

    auto* f = QOpenGLContext::currentContext()->extraFunctions();
    f->glEnableVertexAttribArray(0);
    f->glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float),
                             reinterpret_cast<void*>(0));
    f->glEnableVertexAttribArray(1);
    f->glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float),
                             reinterpret_cast<void*>(3 * sizeof(float)));
    mesh.vao.release();
    mesh.vertexCount = static_cast<int>(data.size() / 6);
}

void GearRenderer::buildBolt() {
    // Hanger disc + shaft cylinder along +Z, ~5 cm scene scale.
    std::vector<float> v;
    constexpr int seg = 12;
    const float r = 0.03f, len = 0.05f;
    for (int i = 0; i < seg; ++i) {
        const float a0 = 2.0f * kPi * i / seg, a1 = 2.0f * kPi * (i + 1) / seg;
        const glm::vec3 c0(r * std::cos(a0), r * std::sin(a0), 0.0f);
        const glm::vec3 c1(r * std::cos(a1), r * std::sin(a1), 0.0f);
        // disc face
        pushTri(v, {0, 0, 0}, c0, c1);
        // shaft side
        const glm::vec3 s0 = c0 * 0.35f, s1 = c1 * 0.35f;
        pushTri(v, s0, s0 + glm::vec3(0, 0, len), s1 + glm::vec3(0, 0, len));
        pushTri(v, s0, s1 + glm::vec3(0, 0, len), s1);
    }
    buildMesh(m_bolt, v);
}

void GearRenderer::buildCam() {
    // Simplified cam body: four lobes approximated by a squat box + axle.
    std::vector<float> v;
    const glm::vec3 h(0.035f, 0.045f, 0.03f);
    const glm::vec3 corners[8] = {
        {-h.x, -h.y, -h.z}, {h.x, -h.y, -h.z}, {h.x, h.y, -h.z}, {-h.x, h.y, -h.z},
        {-h.x, -h.y, h.z},  {h.x, -h.y, h.z},  {h.x, h.y, h.z},  {-h.x, h.y, h.z}};
    const int faces[6][4] = {{0, 1, 2, 3}, {5, 4, 7, 6}, {4, 0, 3, 7},
                             {1, 5, 6, 2}, {3, 2, 6, 7}, {4, 5, 1, 0}};
    for (const auto& fc : faces) {
        pushTri(v, corners[fc[0]], corners[fc[1]], corners[fc[2]]);
        pushTri(v, corners[fc[0]], corners[fc[2]], corners[fc[3]]);
    }
    buildMesh(m_cam, v);
}

void GearRenderer::buildNut() {
    // Tapered wedge.
    std::vector<float> v;
    const glm::vec3 a(-0.02f, -0.03f, -0.012f), b(0.02f, -0.03f, -0.012f),
        c(0.012f, 0.03f, -0.008f), d(-0.012f, 0.03f, -0.008f),
        e(-0.02f, -0.03f, 0.012f), f6(0.02f, -0.03f, 0.012f),
        g(0.012f, 0.03f, 0.008f), h(-0.012f, 0.03f, 0.008f);
    const glm::vec3 q[8] = {a, b, c, d, e, f6, g, h};
    const int faces[6][4] = {{0, 1, 2, 3}, {5, 4, 7, 6}, {4, 0, 3, 7},
                             {1, 5, 6, 2}, {3, 2, 6, 7}, {4, 5, 1, 0}};
    for (const auto& fc : faces) {
        pushTri(v, q[fc[0]], q[fc[1]], q[fc[2]]);
        pushTri(v, q[fc[0]], q[fc[2]], q[fc[3]]);
    }
    buildMesh(m_nut, v);
}

void GearRenderer::draw(const glm::mat4& view, const glm::mat4& proj,
                        const glm::vec3& lightDir) {
    if (!m_ready || m_gear.empty()) return;
    auto* f = QOpenGLContext::currentContext()->extraFunctions();

    m_program.bind();
    m_program.setUniformValue("uView",
                              QMatrix4x4(glm::value_ptr(glm::transpose(view))));
    m_program.setUniformValue("uProj",
                              QMatrix4x4(glm::value_ptr(glm::transpose(proj))));
    m_program.setUniformValue("uLightDir",
                              QVector3D(lightDir.x, lightDir.y, lightDir.z));

    for (const auto& g : m_gear) {
        // Orient +Z toward the gear's face normal.
        const glm::vec3 z = glm::normalize(g.orientation);
        const glm::vec3 up =
            std::abs(z.y) < 0.99f ? glm::vec3(0, 1, 0) : glm::vec3(1, 0, 0);
        const glm::vec3 x = glm::normalize(glm::cross(up, z));
        const glm::vec3 y = glm::cross(z, x);
        glm::mat4 model(1.0f);
        model[0] = glm::vec4(x, 0.0f);
        model[1] = glm::vec4(y, 0.0f);
        model[2] = glm::vec4(z, 0.0f);
        model[3] = glm::vec4(g.position, 1.0f);

        m_program.setUniformValue(
            "uModel", QMatrix4x4(glm::value_ptr(glm::transpose(model))));
        const glm::vec3 col = loadColor(g.loadFraction);
        m_program.setUniformValue("uColor", QVector3D(col.r, col.g, col.b));

        Mesh* mesh = g.type == GearType::Bolt ? &m_bolt
                     : g.type == GearType::Cam ? &m_cam
                                               : &m_nut;
        mesh->vao.bind();
        f->glDrawArrays(GL_TRIANGLES, 0, mesh->vertexCount);
        mesh->vao.release();
    }
    m_program.release();
}
