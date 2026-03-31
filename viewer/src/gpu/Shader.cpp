#include "gpu/Shader.hpp"
#include <iostream>

GLuint Shader::compile(GLenum type, const char* src) {
    GLuint s = glCreateShader(type);
    glShaderSource(s, 1, &src, nullptr);
    glCompileShader(s);
    int ok;
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[512];
        glGetShaderInfoLog(s, 512, nullptr, log);
        std::cerr << "Shader compile error: " << log << "\n";
        return 0;
    }
    return s;
}

bool Shader::loadFromString(const char* vertSrc, const char* fragSrc) {
    GLuint vs = compile(GL_VERTEX_SHADER, vertSrc);
    GLuint fs = compile(GL_FRAGMENT_SHADER, fragSrc);
    if (!vs || !fs) return false;

    id = glCreateProgram();
    glAttachShader(id, vs);
    glAttachShader(id, fs);
    glLinkProgram(id);

    int ok;
    glGetProgramiv(id, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[512];
        glGetProgramInfoLog(id, 512, nullptr, log);
        std::cerr << "Shader link error: " << log << "\n";
        return false;
    }

    glDeleteShader(vs);
    glDeleteShader(fs);
    return true;
}

void Shader::setMat4(const char* name, const float* m) const {
    glUniformMatrix4fv(glGetUniformLocation(id, name), 1, GL_FALSE, m);
}
void Shader::setMat3(const char* name, const float* m) const {
    glUniformMatrix3fv(glGetUniformLocation(id, name), 1, GL_FALSE, m);
}
void Shader::setVec3(const char* name, float x, float y, float z) const {
    glUniform3f(glGetUniformLocation(id, name), x, y, z);
}
void Shader::setInt(const char* name, int v) const {
    glUniform1i(glGetUniformLocation(id, name), v);
}
void Shader::setFloat(const char* name, float v) const {
    glUniform1f(glGetUniformLocation(id, name), v);
}

Shader::~Shader() {
    if (id) glDeleteProgram(id);
}
