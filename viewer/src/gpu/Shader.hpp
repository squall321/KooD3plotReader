#pragma once
#include <glad/glad.h>
#include <string>

class Shader {
public:
    GLuint id = 0;

    bool loadFromString(const char* vertSrc, const char* fragSrc);
    void use() const { glUseProgram(id); }

    void setMat4(const char* name, const float* m) const;
    void setMat3(const char* name, const float* m) const;
    void setVec3(const char* name, float x, float y, float z) const;
    void setInt(const char* name, int v) const;
    void setFloat(const char* name, float v) const;

    ~Shader();

private:
    static GLuint compile(GLenum type, const char* src);
};
