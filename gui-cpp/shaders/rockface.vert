#version 410 core
// Rock face mesh with texture coordinates

layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec2 aUv;

uniform mat4 uView;
uniform mat4 uProj;

out vec3 vNormal;
out vec2 vUv;

void main() {
    vNormal = aNormal;
    vUv = aUv;
    gl_Position = uProj * uView * vec4(aPos, 1.0);
}
