// gui-cpp/src/renderer/RopeRenderer.h
//
// OpenGL rope tube renderer.  Builds a tube mesh around the rope link chain
// with per-vertex tension values mapped to a blue→red gradient in the shader.

#pragma once

#include <QOpenGLBuffer>
#include <QOpenGLShaderProgram>
#include <QOpenGLVertexArrayObject>
#include <glm/glm.hpp>
#include <vector>

class RopeRenderer {
public:
    RopeRenderer() = default;
    ~RopeRenderer() = default;

    /// Compile shaders + create buffers.  Requires a current GL context.
    bool initialize();

    /// Rebuild the tube mesh from link positions and per-link tension
    /// (fraction of MBS, 0–1).  `radius` in scene units (rope diameter / 2).
    void updatePositions(const std::vector<glm::vec3>& linkPositions,
                         const std::vector<double>& tensions,
                         float radius = 0.02f);

    void draw(const glm::mat4& view, const glm::mat4& proj,
              const glm::vec3& lightDir);

private:
    QOpenGLShaderProgram m_program;
    QOpenGLVertexArrayObject m_vao;
    QOpenGLBuffer m_vbo{QOpenGLBuffer::VertexBuffer};
    QOpenGLBuffer m_ibo{QOpenGLBuffer::IndexBuffer};
    int m_indexCount = 0;
    bool m_ready = false;

    static constexpr int kSides = 8; // tube cross-section segments
};
