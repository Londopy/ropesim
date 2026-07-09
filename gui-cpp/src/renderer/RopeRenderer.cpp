// gui-cpp/src/renderer/RopeRenderer.cpp

#include "renderer/RopeRenderer.h"

#include <QOpenGLContext>
#include <QOpenGLExtraFunctions>
#include <glm/gtc/type_ptr.hpp>

#include <cmath>
#include <cstddef>

namespace { constexpr double kPi = 3.14159265358979323846; }

namespace {
struct Vertex {
    glm::vec3 pos;
    glm::vec3 normal;
    float tension;
};

// Orthonormal basis perpendicular to `dir`.
void basisFor(const glm::vec3& dir, glm::vec3& u, glm::vec3& v) {
    const glm::vec3 up = std::abs(dir.y) < 0.99f ? glm::vec3(0, 1, 0)
                                                 : glm::vec3(1, 0, 0);
    u = glm::normalize(glm::cross(dir, up));
    v = glm::normalize(glm::cross(dir, u));
}
} // namespace

bool RopeRenderer::initialize() {
    if (!m_program.addShaderFromSourceFile(QOpenGLShader::Vertex,
                                           "shaders/rope.vert") ||
        !m_program.addShaderFromSourceFile(QOpenGLShader::Fragment,
                                           "shaders/rope.frag") ||
        !m_program.link()) {
        qWarning("RopeRenderer: shader error: %s",
                 qPrintable(m_program.log()));
        return false;
    }
    m_vao.create();
    m_vbo.create();
    m_ibo.create();
    m_ready = true;
    return true;
}

void RopeRenderer::updatePositions(const std::vector<glm::vec3>& linkPositions,
                                   const std::vector<double>& tensions,
                                   float radius) {
    if (!m_ready || linkPositions.size() < 2) {
        m_indexCount = 0;
        return;
    }

    const size_t n = linkPositions.size();
    std::vector<Vertex> vertices;
    vertices.reserve(n * kSides);
    std::vector<unsigned int> indices;
    indices.reserve((n - 1) * kSides * 6);

    // Ring of vertices around each link position.
    for (size_t i = 0; i < n; ++i) {
        const glm::vec3 dir = glm::normalize(
            (i + 1 < n ? linkPositions[i + 1] : linkPositions[i]) -
            (i > 0 ? linkPositions[i - 1] : linkPositions[i]) +
            glm::vec3(1e-6f));
        glm::vec3 u, v;
        basisFor(dir, u, v);
        const float t = i < tensions.size()
                            ? static_cast<float>(tensions[i])
                            : (tensions.empty() ? 0.0f
                                                : static_cast<float>(tensions.back()));
        for (int s = 0; s < kSides; ++s) {
            const float a = 2.0f * static_cast<float>(kPi) * s / kSides;
            const glm::vec3 normal = u * std::cos(a) + v * std::sin(a);
            vertices.push_back({linkPositions[i] + normal * radius, normal, t});
        }
    }

    // Quad strip between consecutive rings.
    for (size_t i = 0; i + 1 < n; ++i) {
        for (int s = 0; s < kSides; ++s) {
            const unsigned int a = static_cast<unsigned int>(i * kSides + s);
            const unsigned int b =
                static_cast<unsigned int>(i * kSides + (s + 1) % kSides);
            const unsigned int c = a + kSides;
            const unsigned int d = b + kSides;
            indices.insert(indices.end(), {a, c, b, b, c, d});
        }
    }

    m_vao.bind();
    m_vbo.bind();
    m_vbo.allocate(vertices.data(),
                   static_cast<int>(vertices.size() * sizeof(Vertex)));
    m_ibo.bind();
    m_ibo.allocate(indices.data(),
                   static_cast<int>(indices.size() * sizeof(unsigned int)));

    auto* f = QOpenGLContext::currentContext()->extraFunctions();
    f->glEnableVertexAttribArray(0);
    f->glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(Vertex),
                             reinterpret_cast<void*>(offsetof(Vertex, pos)));
    f->glEnableVertexAttribArray(1);
    f->glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, sizeof(Vertex),
                             reinterpret_cast<void*>(offsetof(Vertex, normal)));
    f->glEnableVertexAttribArray(2);
    f->glVertexAttribPointer(2, 1, GL_FLOAT, GL_FALSE, sizeof(Vertex),
                             reinterpret_cast<void*>(offsetof(Vertex, tension)));
    m_vao.release();

    m_indexCount = static_cast<int>(indices.size());
}

void RopeRenderer::draw(const glm::mat4& view, const glm::mat4& proj,
                        const glm::vec3& lightDir) {
    if (!m_ready || m_indexCount == 0) return;
    auto* f = QOpenGLContext::currentContext()->extraFunctions();

    m_program.bind();
    m_program.setUniformValue(
        "uView", QMatrix4x4(glm::value_ptr(glm::transpose(view))));
    m_program.setUniformValue(
        "uProj", QMatrix4x4(glm::value_ptr(glm::transpose(proj))));
    m_program.setUniformValue("uLightDir",
                              QVector3D(lightDir.x, lightDir.y, lightDir.z));
    m_vao.bind();
    f->glDrawElements(GL_TRIANGLES, m_indexCount, GL_UNSIGNED_INT, nullptr);
    m_vao.release();
    m_program.release();
}
