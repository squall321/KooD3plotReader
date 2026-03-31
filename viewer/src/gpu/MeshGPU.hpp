#pragma once
#include <glad/glad.h>
#include <vector>
#include <cstdint>
#include <cstddef>

struct MeshPartGPU {
    GLuint vao = 0;
    GLuint vbo = 0;
    GLuint ebo = 0;
    GLsizei indexCount = 0;
    int32_t partId = 0;
    bool visible = true;
    float color[3] = {0.5f, 0.5f, 0.5f};
};

// Vertex: [float3 pos | float3 normal | float fringe] = 28 bytes
struct MeshVertex {
    float px, py, pz;
    float nx, ny, nz;
    float fringe;
};

class MeshGPU {
public:
    ~MeshGPU();

    // Build from extracted exterior faces
    // faces: list of {node_indices[3 or 4], part_id, normal}
    struct InputFace {
        int32_t nodeIdx[4];  // 0-based, nodeIdx[3]=-1 for triangle
        int32_t partId;
        float nx, ny, nz;   // face normal
    };

    void build(const std::vector<float>& nodeCoords,  // x,y,z interleaved
               const std::vector<InputFace>& faces);

    // Update deformed positions + fringe values (per frame)
    void updatePositions(const std::vector<float>& deformedCoords,
                         const std::vector<float>& fringePerNode);

    // Draw all visible parts
    void draw(bool useFringe) const;

    // Part management
    size_t partCount() const { return parts_.size(); }
    MeshPartGPU& part(size_t i) { return parts_[i]; }
    const MeshPartGPU& part(size_t i) const { return parts_[i]; }

    // Bounding box
    float bboxMin[3]{}, bboxMax[3]{};

private:
    std::vector<MeshPartGPU> parts_;
    size_t totalVertices_ = 0;

    // Global VBO (shared across parts for efficient update)
    GLuint globalVBO_ = 0;
    std::vector<MeshVertex> cpuVertices_;

    // Mapping: globalVertexIndex → nodeIndex (for position update)
    std::vector<int32_t> vertToNode_;
};
