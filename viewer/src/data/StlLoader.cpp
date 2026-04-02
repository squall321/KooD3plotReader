#include "data/StlLoader.hpp"
#include <fstream>
#include <sstream>
#include <cstring>
#include <algorithm>
#include <cmath>
#include <iostream>

bool StlMesh::loadFile(const std::string& path) {
    // Detect ASCII vs binary: ASCII starts with "solid"
    std::ifstream f(path, std::ios::binary);
    if (!f) return false;

    char header[6] = {};
    f.read(header, 5);
    f.close();

    if (std::strncmp(header, "solid", 5) == 0) {
        // Could be ASCII or binary with "solid" in header name — try ASCII first
        if (loadAscii(path)) return true;
    }
    return loadBinary(path);
}

bool StlMesh::loadBinary(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return false;

    // 80 byte header
    char header[80];
    f.read(header, 80);

    // Number of triangles
    uint32_t numTri;
    f.read(reinterpret_cast<char*>(&numTri), 4);

    if (numTri == 0 || numTri > 10000000) return false;

    triangles.resize(numTri);
    for (uint32_t i = 0; i < numTri; ++i) {
        f.read(reinterpret_cast<char*>(&triangles[i].normal), 12);
        f.read(reinterpret_cast<char*>(&triangles[i].v), 36);
        uint16_t attr;
        f.read(reinterpret_cast<char*>(&attr), 2);  // attribute byte count
    }

    // Compute bounding box
    bboxMin[0] = bboxMin[1] = bboxMin[2] = 1e30f;
    bboxMax[0] = bboxMax[1] = bboxMax[2] = -1e30f;
    for (auto& tri : triangles) {
        for (int vi = 0; vi < 3; ++vi) {
            for (int j = 0; j < 3; ++j) {
                bboxMin[j] = std::min(bboxMin[j], tri.v[vi][j]);
                bboxMax[j] = std::max(bboxMax[j], tri.v[vi][j]);
            }
        }
    }
    for (int j = 0; j < 3; ++j)
        center[j] = (bboxMin[j] + bboxMax[j]) * 0.5f;

    float dx = bboxMax[0]-bboxMin[0], dy = bboxMax[1]-bboxMin[1], dz = bboxMax[2]-bboxMin[2];
    maxExtent = std::max({dx, dy, dz, 1e-6f});

    std::cout << "[STL] Loaded " << triangles.size() << " triangles from " << path << "\n";
    return true;
}

bool StlMesh::loadAscii(const std::string& path) {
    std::ifstream f(path);
    if (!f) return false;

    std::string line;
    StlTriangle tri{};
    int vertIdx = 0;

    while (std::getline(f, line)) {
        std::istringstream ss(line);
        std::string keyword;
        ss >> keyword;

        if (keyword == "facet") {
            std::string tmp;
            ss >> tmp;  // "normal"
            ss >> tri.normal[0] >> tri.normal[1] >> tri.normal[2];
            vertIdx = 0;
        } else if (keyword == "vertex" && vertIdx < 3) {
            ss >> tri.v[vertIdx][0] >> tri.v[vertIdx][1] >> tri.v[vertIdx][2];
            vertIdx++;
        } else if (keyword == "endfacet") {
            triangles.push_back(tri);
        }
    }

    if (triangles.empty()) return false;

    // Compute bounding box
    bboxMin[0] = bboxMin[1] = bboxMin[2] = 1e30f;
    bboxMax[0] = bboxMax[1] = bboxMax[2] = -1e30f;
    for (auto& t : triangles) {
        for (int vi = 0; vi < 3; ++vi) {
            for (int j = 0; j < 3; ++j) {
                bboxMin[j] = std::min(bboxMin[j], t.v[vi][j]);
                bboxMax[j] = std::max(bboxMax[j], t.v[vi][j]);
            }
        }
    }
    for (int j = 0; j < 3; ++j)
        center[j] = (bboxMin[j] + bboxMax[j]) * 0.5f;

    float dx = bboxMax[0]-bboxMin[0], dy = bboxMax[1]-bboxMin[1], dz = bboxMax[2]-bboxMin[2];
    maxExtent = std::max({dx, dy, dz, 1e-6f});

    std::cout << "[STL] Loaded " << triangles.size() << " ASCII triangles from " << path << "\n";
    return true;
}
