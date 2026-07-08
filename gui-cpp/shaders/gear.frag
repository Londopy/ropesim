#version 410 core
// Gear — flat colour set from load fraction of MBS

in vec3 vNormal;

uniform vec3 uColor;
uniform vec3 uLightDir;

out vec4 fragColor;

void main() {
    float diffuse = max(dot(normalize(vNormal), -uLightDir), 0.0);
    fragColor = vec4(uColor * (0.4 + 0.6 * diffuse), 1.0);
}
