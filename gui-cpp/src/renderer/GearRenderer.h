// gui-cpp/src/renderer/GearRenderer.h
//
// 3D gear geometry: bolts (cylinder + disc), cams (simplified body),
// nuts (wedge).  Colour encodes load fraction of MBS.

#pragma once

#include <QOpenGLBuffer>
#include <QOpenGLShaderProgram>
#include <QOpenGLVertexArrayObject>
#include <glm/glm.hpp>
#include <vector>

enum class GearType { Bolt, Cam, Nut };

struct GearInstance {
    GearType type = GearType::Bolt;
    glm::vec3 position{0.0f};
    glm::vec3 orientation{0.0f, 0.0f, 1.0f}; // face normal / pull direction
    double loadFraction = 0.0;               // force / MBS, drives colour
};

class GearRenderer {
public:
    bool initialize();
    void setGear(const std::vector<GearInstance>& gear) { m_gear = gear; }
    void draw(const glm::mat4& view, const glm::mat4& proj,
              const glm::vec3& lightDir);

private:
    struct Mesh {
        QOpenGLVertexArrayObject vao;
        QOpenGLBuffer vbo{QOpenGLBuffer::VertexBuffer};
        int vertexCount = 0;
    };

    void buildMesh(Mesh& mesh, const std::vector<float>& interleaved);
    void buildBolt();
    void buildCam();
    void buildNut();

    QOpenGLShaderProgram m_program;
    Mesh m_bolt, m_cam, m_nut;
    std::vector<GearInstance> m_gear;
    bool m_ready = false;
};
