// gui-cpp/src/renderer/ForceArrowRenderer.cpp

#include "renderer/ForceArrowRenderer.h"

#include <QOpenGLContext>
#include <QOpenGLExtraFunctions>
#include <glm/gtc/type_ptr.hpp>

#include <cmath>

bool ForceArrowRenderer::initialize() {
    if (!m_program.addShaderFromSourceFile(QOpenGLShader::Vertex,
                                           "shaders/arrow.vert") ||
        !m_program.addShaderFromSourceFile(QOpenGLShader::Fragment,
                                           "shaders/arrow.frag") ||
        !m_program.link()) {
        qWarning("ForceArrowRenderer: shader error: %s",
                 qPrintable(m_program.log()));
        return false;
    }

    // Unit arrow along -Y: shaft (line strip as thin quads not needed —
    // use GL_LINES for shaft + small cone as triangles).
    // Layout: 2 line verts + 12 cone verts (4 triangles).
    std::vector<float> v = {
        0.0f, 0.0f, 0.0f,   0.0f, -0.85f, 0.0f, // shaft line
    };
    // cone at tip
    const float tipY = -1.0f, baseY = -0.8f, r = 0.06f;
    const glm::vec3 tip(0.0f, tipY, 0.0f);
    constexpr int seg = 4;
    for (int i = 0; i < seg; ++i) {
        const float a0 = 2.0f * M_PI * i / seg, a1 = 2.0f * M_PI * (i + 1) / seg;
        const glm::vec3 b0(r * std::cos(a0), baseY, r * std::sin(a0));
        const glm::vec3 b1(r * std::cos(a1), baseY, r * std::sin(a1));
        for (const auto& p : {tip, b0, b1})
            v.insert(v.end(), {p.x, p.y, p.z});
    }

    m_vao.create();
    m_vao.bind();
    m_vbo.create();
    m_vbo.bind();
    m_vbo.allocate(v.data(), static_cast<int>(v.size() * sizeof(float)));
    auto* f = QOpenGLContext::currentContext()->extraFunctions();
    f->glEnableVertexAttribArray(0);
    f->glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * sizeof(float),
                             reinterpret_cast<void*>(0));
    m_vao.release();
    m_vertexCount = static_cast<int>(v.size() / 3);
    m_ready = true;
    return true;
}

void ForceArrowRenderer::draw(const glm::mat4& view, const glm::mat4& proj) {
    if (!m_ready || m_arrows.empty()) return;
    auto* f = QOpenGLContext::currentContext()->extraFunctions();

    m_program.bind();
    m_program.setUniformValue("uView",
                              QMatrix4x4(glm::value_ptr(glm::transpose(view))));
    m_program.setUniformValue("uProj",
                              QMatrix4x4(glm::value_ptr(glm::transpose(proj))));

    for (const auto& a : m_arrows) {
        if (a.forceKn <= 0.01) continue;
        // Length: 0.5 m per 5 kN, capped.
        const float len =
            std::min(static_cast<float>(a.forceKn) * 0.1f, 3.0f) + 0.2f;

        const glm::vec3 dir = glm::normalize(a.direction);
        // Basis mapping -Y (unit arrow axis) onto dir.
        const glm::vec3 y = -dir;
        const glm::vec3 up =
            std::abs(y.x) < 0.99f ? glm::vec3(1, 0, 0) : glm::vec3(0, 0, 1);
        const glm::vec3 x = glm::normalize(glm::cross(up, y));
        const glm::vec3 z = glm::cross(x, y);
        glm::mat4 model(1.0f);
        model[0] = glm::vec4(x * len * 0.3f, 0.0f);
        model[1] = glm::vec4(y * len, 0.0f);
        model[2] = glm::vec4(z * len * 0.3f, 0.0f);
        model[3] = glm::vec4(a.position, 1.0f);
        m_program.setUniformValue(
            "uModel", QMatrix4x4(glm::value_ptr(glm::transpose(model))));

        // Colour by load fraction: green → yellow → red.
        const float frac = static_cast<float>(
            std::clamp(a.mbsKn > 0.0 ? a.forceKn / a.mbsKn : 1.0, 0.0, 1.0));
        const glm::vec3 col =
            frac < 0.5f
                ? glm::mix(glm::vec3(0.3f, 0.85f, 0.35f),
                           glm::vec3(0.95f, 0.85f, 0.15f), frac * 2.0f)
                : glm::mix(glm::vec3(0.95f, 0.85f, 0.15f),
                           glm::vec3(0.95f, 0.15f, 0.10f), (frac - 0.5f) * 2.0f);
        m_program.setUniformValue("uColor", QVector3D(col.r, col.g, col.b));

        m_vao.bind();
        f->glLineWidth(2.0f);
        f->glDrawArrays(GL_LINES, 0, 2);
        f->glDrawArrays(GL_TRIANGLES, 2, m_vertexCount - 2);
        m_vao.release();
    }
    m_program.release();
}
