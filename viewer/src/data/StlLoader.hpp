#pragma once
#include <string>
#include <vector>
#include <cstdint>

struct StlTriangle {
    float normal[3];
    float v[3][3];  // 3 vertices × xyz
};

struct StlMesh {
    std::vector<StlTriangle> triangles;
    float bboxMin[3], bboxMax[3];
    float center[3];
    float maxExtent;

    bool loadFile(const std::string& path);
    bool loadBinary(const std::string& path);
    bool loadAscii(const std::string& path);
};
