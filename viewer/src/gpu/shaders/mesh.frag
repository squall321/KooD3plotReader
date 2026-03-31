#version 330 core
in vec3 vNorm;
in float vFringe;
in vec3 vPos;

uniform sampler1D uColormap;
uniform vec3 uLightDir;
uniform float uAmbient;
uniform int uUseFringe;      // 1 = fringe colormap, 0 = flat color
uniform vec3 uFlatColor;

out vec4 fragColor;

void main() {
    vec3 color;
    if (uUseFringe == 1) {
        color = texture(uColormap, clamp(vFringe, 0.0, 1.0)).rgb;
    } else {
        color = uFlatColor;
    }

    // Diffuse lighting (two-sided)
    vec3 N = normalize(vNorm);
    float diff = abs(dot(N, uLightDir));
    color *= uAmbient + (1.0 - uAmbient) * diff;

    fragColor = vec4(color, 1.0);
}
