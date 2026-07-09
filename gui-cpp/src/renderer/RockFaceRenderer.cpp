// gui-cpp/src/renderer/RockFaceRenderer.cpp

#include "renderer/RockFaceRenderer.h"

#include <QFile>
#include <QImage>
#include <QOpenGLContext>
#include <QOpenGLExtraFunctions>
#include <QTextStream>
#include <glm/gtc/type_ptr.hpp>

#include <array>
#include <cmath>
#include <limits>

namespace {
constexpr float kFaceWidth = 8.0f;  // m
constexpr float kFaceHeight = 20.0f; // m

QString textureFile(RockTextureType t) {
    switch (t) {
        case RockTextureType::Granite: return "assets/textures/granite.png";
        case RockTextureType::Limestone: return "assets/textures/limestone.png";
        case RockTextureType::Sandstone: return "assets/textures/sandstone.png";
        case RockTextureType::Basalt: return "assets/textures/basalt.png";
        case RockTextureType::Ice: return "assets/textures/ice.png";
    }
    return "assets/textures/granite.png";
}
} // namespace

bool RockFaceRenderer::initialize() {
    if (!m_program.addShaderFromSourceFile(QOpenGLShader::Vertex,
                                           "shaders/rockface.vert") ||
        !m_program.addShaderFromSourceFile(QOpenGLShader::Fragment,
                                           "shaders/rockface.frag") ||
        !m_program.link()) {
        qWarning("RockFaceRenderer: shader error: %s",
                 qPrintable(m_program.log()));
        return false;
    }
    m_vao.create();
    m_vbo.create();
    m_ready = true;
    setRockType(RockTextureType::Granite);
    setGeometry(RockFacePreset::VerticalSlab);
    return true;
}

void RockFaceRenderer::setRockType(RockTextureType type) {
    QImage img(textureFile(type));
    if (img.isNull()) {
        // Fallback: flat grey texture so rendering still works.
        img = QImage(4, 4, QImage::Format_RGB888);
        img.fill(Qt::gray);
    }
    m_texture = std::make_unique<QOpenGLTexture>(img.mirrored());
    m_texture->setWrapMode(QOpenGLTexture::Repeat);
    m_texture->setMinMagFilters(QOpenGLTexture::LinearMipMapLinear,
                                QOpenGLTexture::Linear);
}

void RockFaceRenderer::setGeometry(RockFacePreset preset) {
    switch (preset) {
        case RockFacePreset::VerticalSlab: buildPlanarFace(0.0f, false, false, false); break;
        case RockFacePreset::Overhang30:   buildPlanarFace(30.0f, false, false, false); break;
        case RockFacePreset::Overhang45:   buildPlanarFace(45.0f, false, false, false); break;
        case RockFacePreset::Roof:         buildPlanarFace(85.0f, false, false, false); break;
        case RockFacePreset::CrackSystem:  buildPlanarFace(0.0f, true, false, false); break;
        case RockFacePreset::Corner:       buildPlanarFace(0.0f, false, true, false); break;
        case RockFacePreset::Arete:        buildPlanarFace(0.0f, false, false, true); break;
    }
}

void RockFaceRenderer::buildPlanarFace(float overhangDeg, bool crack,
                                       bool corner, bool arete) {
    // Grid of quads; overhang tilts the face; crack carves a groove;
    // corner/arête fold the face along the vertical midline.
    std::vector<float> data;
    m_triangles.clear();
    constexpr int nx = 16, ny = 40;
    const float tilt = glm::radians(overhangDeg);

    auto surface = [&](float u, float v) -> glm::vec3 {
        float x = (u - 0.5f) * kFaceWidth;
        float y = v * kFaceHeight;
        float z = -std::tan(tilt) * y; // lean out with height
        if (crack) {
            const float d = std::abs(u - 0.5f);
            if (d < 0.04f) z -= 0.25f * (1.0f - d / 0.04f);
        }
        if (corner) z -= std::abs(u - 0.5f) * kFaceWidth * 0.6f;
        if (arete) z += std::abs(u - 0.5f) * kFaceWidth * 0.6f - kFaceWidth * 0.3f;
        return {x, y, z};
    };

    auto emit3 = [&](glm::vec3 a, glm::vec3 b, glm::vec3 c, glm::vec2 ua,
                     glm::vec2 ub, glm::vec2 uc) {
        const glm::vec3 n = glm::normalize(glm::cross(b - a, c - a));
        const glm::vec3 ps[3] = {a, b, c};
        const glm::vec2 uvs[3] = {ua, ub, uc};
        for (int i = 0; i < 3; ++i) {
            data.insert(data.end(),
                        {ps[i].x, ps[i].y, ps[i].z, n.x, n.y, n.z,
                         uvs[i].x * 4.0f, uvs[i].y * 10.0f});
            m_triangles.push_back(ps[i]);
        }
    };

    for (int j = 0; j < ny; ++j) {
        for (int i = 0; i < nx; ++i) {
            const float u0 = float(i) / nx, u1 = float(i + 1) / nx;
            const float v0 = float(j) / ny, v1 = float(j + 1) / ny;
            const glm::vec3 a = surface(u0, v0), b = surface(u1, v0),
                            c = surface(u1, v1), d = surface(u0, v1);
            emit3(a, b, c, {u0, v0}, {u1, v0}, {u1, v1});
            emit3(a, c, d, {u0, v0}, {u1, v1}, {u0, v1});
        }
    }
    uploadMesh(data);
}

bool RockFaceRenderer::loadCustomMesh(const std::string& objPath) {
    QFile file(QString::fromStdString(objPath));
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) return false;

    std::vector<glm::vec3> verts;
    std::vector<glm::vec2> uvs;
    std::vector<float> data;
    m_triangles.clear();

    QTextStream in(&file);
    std::vector<std::array<int, 3>> faceIdx;
    while (!in.atEnd()) {
        const QString line = in.readLine().trimmed();
        const QStringList parts = line.split(' ', Qt::SkipEmptyParts);
        if (parts.isEmpty()) continue;
        if (parts[0] == "v" && parts.size() >= 4) {
            verts.emplace_back(parts[1].toFloat(), parts[2].toFloat(),
                               parts[3].toFloat());
        } else if (parts[0] == "vt" && parts.size() >= 3) {
            uvs.emplace_back(parts[1].toFloat(), parts[2].toFloat());
        } else if (parts[0] == "f" && parts.size() >= 4) {
            // triangulate fan; indices may be v, v/vt, v/vt/vn
            std::vector<std::pair<int, int>> fv;
            for (int k = 1; k < parts.size(); ++k) {
                const QStringList comps = parts[k].split('/');
                const int vi = comps[0].toInt() - 1;
                const int ti = comps.size() > 1 && !comps[1].isEmpty()
                                   ? comps[1].toInt() - 1
                                   : -1;
                fv.emplace_back(vi, ti);
            }
            for (size_t k = 1; k + 1 < fv.size(); ++k) {
                const std::pair<int, int> tri[3] = {fv[0], fv[k], fv[k + 1]};
                glm::vec3 p[3];
                glm::vec2 t[3];
                bool ok = true;
                for (int m = 0; m < 3; ++m) {
                    if (tri[m].first < 0 ||
                        tri[m].first >= static_cast<int>(verts.size())) {
                        ok = false;
                        break;
                    }
                    p[m] = verts[tri[m].first];
                    t[m] = (tri[m].second >= 0 &&
                            tri[m].second < static_cast<int>(uvs.size()))
                               ? uvs[tri[m].second]
                               : glm::vec2(p[m].x * 0.25f, p[m].y * 0.25f);
                }
                if (!ok) continue;
                const glm::vec3 n =
                    glm::normalize(glm::cross(p[1] - p[0], p[2] - p[0]));
                for (int m = 0; m < 3; ++m) {
                    data.insert(data.end(), {p[m].x, p[m].y, p[m].z, n.x, n.y,
                                             n.z, t[m].x, t[m].y});
                    m_triangles.push_back(p[m]);
                }
            }
        }
    }
    if (data.empty()) return false;
    uploadMesh(data);
    return true;
}

void RockFaceRenderer::uploadMesh(const std::vector<float>& interleaved) {
    if (!m_ready) return;
    m_vao.bind();
    m_vbo.bind();
    m_vbo.allocate(interleaved.data(),
                   static_cast<int>(interleaved.size() * sizeof(float)));
    auto* f = QOpenGLContext::currentContext()->extraFunctions();
    const int stride = 8 * sizeof(float);
    f->glEnableVertexAttribArray(0);
    f->glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride,
                             reinterpret_cast<void*>(0));
    f->glEnableVertexAttribArray(1);
    f->glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride,
                             reinterpret_cast<void*>(3 * sizeof(float)));
    f->glEnableVertexAttribArray(2);
    f->glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, stride,
                             reinterpret_cast<void*>(6 * sizeof(float)));
    m_vao.release();
    m_vertexCount = static_cast<int>(interleaved.size() / 8);
}

void RockFaceRenderer::draw(const glm::mat4& view, const glm::mat4& proj,
                            const glm::vec3& lightDir) {
    if (!m_ready || m_vertexCount == 0) return;
    auto* f = QOpenGLContext::currentContext()->extraFunctions();

    m_program.bind();
    m_program.setUniformValue("uView",
                              QMatrix4x4(glm::value_ptr(glm::transpose(view))));
    m_program.setUniformValue("uProj",
                              QMatrix4x4(glm::value_ptr(glm::transpose(proj))));
    m_program.setUniformValue("uLightDir",
                              QVector3D(lightDir.x, lightDir.y, lightDir.z));
    m_program.setUniformValue("uTexture", 0);
    if (m_texture) m_texture->bind(0);
    m_vao.bind();
    f->glDrawArrays(GL_TRIANGLES, 0, m_vertexCount);
    m_vao.release();
    if (m_texture) m_texture->release();
    m_program.release();
}

std::optional<glm::vec3> RockFaceRenderer::raycast(const glm::vec3& origin,
                                                   const glm::vec3& dir) const {
    // Möller–Trumbore over the CPU triangle list; nearest hit wins.
    float best = std::numeric_limits<float>::max();
    std::optional<glm::vec3> hit;
    for (size_t i = 0; i + 2 < m_triangles.size(); i += 3) {
        const glm::vec3 &a = m_triangles[i], &b = m_triangles[i + 1],
                        &c = m_triangles[i + 2];
        const glm::vec3 e1 = b - a, e2 = c - a;
        const glm::vec3 p = glm::cross(dir, e2);
        const float det = glm::dot(e1, p);
        if (std::abs(det) < 1e-8f) continue;
        const float inv = 1.0f / det;
        const glm::vec3 tvec = origin - a;
        const float u = glm::dot(tvec, p) * inv;
        if (u < 0.0f || u > 1.0f) continue;
        const glm::vec3 q = glm::cross(tvec, e1);
        const float v = glm::dot(dir, q) * inv;
        if (v < 0.0f || u + v > 1.0f) continue;
        const float t = glm::dot(e2, q) * inv;
        if (t > 1e-4f && t < best) {
            best = t;
            hit = origin + dir * t;
            m_lastHitNormal = glm::normalize(glm::cross(e1, e2));
            if (glm::dot(m_lastHitNormal, dir) > 0.0f)
                m_lastHitNormal = -m_lastHitNormal;
        }
    }
    return hit;
}
