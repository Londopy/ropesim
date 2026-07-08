#version 410 core
// Rope tension colour mapping: blue → cyan → green → yellow → red

in vec3 vNormal;
in vec3 vWorldPos;
in float vTension;

uniform vec3 uLightDir; // normalised, world space

out vec4 fragColor;

vec3 tensionColor(float t) {
    t = clamp(t, 0.0, 1.0);
    vec3 blue   = vec3(0.15, 0.25, 0.95);
    vec3 cyan   = vec3(0.10, 0.80, 0.90);
    vec3 green  = vec3(0.15, 0.85, 0.30);
    vec3 yellow = vec3(0.95, 0.85, 0.15);
    vec3 red    = vec3(0.95, 0.15, 0.10);
    if (t < 0.3)  return mix(blue,   cyan,   t / 0.3);
    if (t < 0.6)  return mix(cyan,   green,  (t - 0.3) / 0.3);
    if (t < 0.8)  return mix(green,  yellow, (t - 0.6) / 0.2);
    return               mix(yellow, red,    (t - 0.8) / 0.2);
}

void main() {
    float diffuse = max(dot(normalize(vNormal), -uLightDir), 0.0);
    vec3 color = tensionColor(vTension) * (0.35 + 0.65 * diffuse);
    fragColor = vec4(color, 1.0);
}
