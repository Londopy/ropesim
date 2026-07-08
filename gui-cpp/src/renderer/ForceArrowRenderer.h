// gui-cpp/src/renderer/ForceArrowRenderer.h
//
// Force vector arrows at gear positions after a simulation run.
// Arrow length ∝ force magnitude; colour matches the gear safety indicator.

#pragma once

#include <QOpenGLBuffer>
#include <QOpenGLShaderProgram>
#include <QOpenGLVertexArrayObject>
#include <glm/glm.hpp>
#include <vector>

struct ForceArrow {
    glm::vec3 position{0.0f};
    glm::vec3 direction{0.0f, -1.0f, 0.0f};
    double forceKn = 0.0;
    double mbsKn = 25.0; // for colour
};

class ForceArrowRenderer {
public:
    bool initialize();
    void setArrows(const std::vector<ForceArrow>& arrows) { m_arrows = arrows; }
    void clear() { m_arrows.clear(); }
    void draw(const glm::mat4& view, const glm::mat4& proj);

private:
    QOpenGLShaderProgram m_program;
    QOpenGLVertexArrayObject m_vao;
    QOpenGLBuffer m_vbo{QOpenGLBuffer::VertexBuffer};
    int m_vertexCount = 0;
    std::vector<ForceArrow> m_arrows;
    bool m_ready = false;
};
