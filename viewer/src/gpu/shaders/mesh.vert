#version 330 core
layout(location=0) in vec3 aPos;
layout(location=1) in vec3 aNorm;
layout(location=2) in float aFringe;

uniform mat4 uMVP;
uniform mat3 uNormalMat;

out vec3 vNorm;
out float vFringe;
out vec3 vPos;

void main() {
    gl_Position = uMVP * vec4(aPos, 1.0);
    vNorm = normalize(uNormalMat * aNorm);
    vFringe = aFringe;
    vPos = aPos;
}
