#version 410 core
// Rope tube — position + normal + per-vertex tension (0-1 of MBS)

layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in float aTension;

uniform mat4 uView;
uniform mat4 uProj;

out vec3 vNormal;
out vec3 vWorldPos;
out float vTension;

void main() {
    vNormal = aNormal;
    vWorldPos = aPos;
    vTension = aTension;
    gl_Position = uProj * uView * vec4(aPos, 1.0);
}
