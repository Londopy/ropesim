// gui-cpp/src/renderer/RockFaceRenderer.h
//
// Rock face mesh + texture.  Presets generate parametric geometry; custom
// .obj meshes can be loaded for real crags.

#pragma once

#include <QOpenGLBuffer>
#include <QOpenGLShaderProgram>
#include <QOpenGLTexture>
#include <QOpenGLVertexArrayObject>
#include <glm/glm.hpp>
#include <memory>
#include <optional>
#include <string>
#include <vector>

enum class RockFacePreset {
    VerticalSlab,
    Overhang30,
    Overhang45,
    Roof,
    CrackSystem,
    Corner,
    Arete,
};

enum class RockTextureType { Granite, Limestone, Sandstone, Basalt, Ice };

class RockFaceRenderer {
public:
    bool initialize();

    void setGeometry(RockFacePreset preset);
    bool loadCustomMesh(const std::string& objPath);
    void setRockType(RockTextureType type);

    void draw(const glm::mat4& view, const glm::mat4& proj,
              const glm::vec3& lightDir);

    /// Ray-cast against the face triangles.  Returns hit point (world) or
    /// nullopt.  Used by placement mode.
    std::optional<glm::vec3> raycast(const glm::vec3& origin,
                                     const glm::vec3& dir) const;

    /// Outward normal at the last raycast hit (flat per-triangle).
    glm::vec3 lastHitNormal() const { return m_lastHitNormal; }

private:
    void uploadMesh(const std::vector<float>& interleaved); // pos3 n3 uv2
    void buildPlanarFace(float overhangDeg, bool crack, bool corner, bool arete);

    QOpenGLShaderProgram m_program;
    QOpenGLVertexArrayObject m_vao;
    QOpenGLBuffer m_vbo{QOpenGLBuffer::VertexBuffer};
    std::unique_ptr<QOpenGLTexture> m_texture;
    int m_vertexCount = 0;
    bool m_ready = false;

    // CPU copy for raycasting: triangles as flat vec3 list.
    std::vector<glm::vec3> m_triangles;
    mutable glm::vec3 m_lastHitNormal{0.0f, 0.0f, 1.0f};
};
