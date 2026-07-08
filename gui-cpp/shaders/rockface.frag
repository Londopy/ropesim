#version 410 core
// Rock face — textured lambert

in vec3 vNormal;
in vec2 vUv;

uniform sampler2D uTexture;
uniform vec3 uLightDir;

out vec4 fragColor;

void main() {
    vec3 tex = texture(uTexture, vUv).rgb;
    float diffuse = max(dot(normalize(vNormal), -uLightDir), 0.0);
    fragColor = vec4(tex * (0.45 + 0.55 * diffuse), 1.0);
}
