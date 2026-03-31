#include "gpu/MeshGPU.hpp"
#include <map>
#include <cmath>
#include <algorithm>

MeshGPU::~MeshGPU() {
    if (globalVBO_) glDeleteBuffers(1, &globalVBO_);
    for (auto& p : parts_) {
        if (p.vao) glDeleteVertexArrays(1, &p.vao);
        if (p.ebo) glDeleteBuffers(1, &p.ebo);
    }
}

static const float g_palette[][3] = {
    {0.12f,0.47f,0.71f}, {0.84f,0.15f,0.16f}, {0.17f,0.63f,0.17f},
    {1.00f,0.50f,0.05f}, {0.58f,0.40f,0.74f}, {0.09f,0.75f,0.81f},
    {0.74f,0.74f,0.13f}, {0.89f,0.47f,0.76f}, {0.55f,0.34f,0.29f},
    {0.50f,0.50f,0.50f}, {0.65f,0.81f,0.89f}, {0.99f,0.60f,0.60f},
};
static constexpr int PALETTE_SIZE = sizeof(g_palette) / sizeof(g_palette[0]);

void MeshGPU::build(const std::vector<float>& nodeCoords,
                     const std::vector<InputFace>& faces) {
    // Bounding box
    size_t numNodes = nodeCoords.size() / 3;
    bboxMin[0] = bboxMin[1] = bboxMin[2] = 1e30f;
    bboxMax[0] = bboxMax[1] = bboxMax[2] = -1e30f;
    for (size_t i = 0; i < numNodes; ++i) {
        for (int j = 0; j < 3; ++j) {
            bboxMin[j] = std::min(bboxMin[j], nodeCoords[i*3+j]);
            bboxMax[j] = std::max(bboxMax[j], nodeCoords[i*3+j]);
        }
    }

    // Group faces by part
    std::map<int32_t, std::vector<size_t>> partFaceMap;
    for (size_t i = 0; i < faces.size(); ++i) {
        partFaceMap[faces[i].partId].push_back(i);
    }

    // Build ALL vertices into single global array
    // Each face vertex is unique (flat shading — face normal per vertex)
    cpuVertices_.clear();
    vertToNode_.clear();

    // Per-part: track start index and index count in global vertex array
    struct PartBuild {
        int32_t partId;
        size_t vertexStart;   // first vertex index in cpuVertices_
        std::vector<uint32_t> indices;  // GLOBAL vertex indices
    };
    std::vector<PartBuild> partBuilds;

    int colorIdx = 0;
    for (auto& [pid, faceIndices] : partFaceMap) {
        PartBuild pb;
        pb.partId = pid;
        pb.vertexStart = cpuVertices_.size();

        for (size_t fi : faceIndices) {
            const auto& f = faces[fi];
            bool isQuad = (f.nodeIdx[3] >= 0);
            int nVerts = isQuad ? 4 : 3;

            uint32_t v0 = static_cast<uint32_t>(cpuVertices_.size());

            for (int j = 0; j < nVerts; ++j) {
                int ni = f.nodeIdx[j];
                MeshVertex v;
                v.px = nodeCoords[ni*3+0];
                v.py = nodeCoords[ni*3+1];
                v.pz = nodeCoords[ni*3+2];
                v.nx = f.nx; v.ny = f.ny; v.nz = f.nz;
                v.fringe = 0.0f;
                cpuVertices_.push_back(v);
                vertToNode_.push_back(ni);
            }

            // Triangle 1
            pb.indices.push_back(v0);
            pb.indices.push_back(v0 + 1);
            pb.indices.push_back(v0 + 2);

            // Triangle 2 (quad)
            if (isQuad) {
                pb.indices.push_back(v0);
                pb.indices.push_back(v0 + 2);
                pb.indices.push_back(v0 + 3);
            }
        }

        partBuilds.push_back(std::move(pb));
        colorIdx++;
    }

    totalVertices_ = cpuVertices_.size();

    // Upload global VBO (all vertices, all parts)
    glGenBuffers(1, &globalVBO_);
    glBindBuffer(GL_ARRAY_BUFFER, globalVBO_);
    glBufferData(GL_ARRAY_BUFFER,
                 cpuVertices_.size() * sizeof(MeshVertex),
                 cpuVertices_.data(), GL_DYNAMIC_DRAW);

    // Create one VAO + EBO per part, all sharing the same global VBO
    colorIdx = 0;
    for (auto& pb : partBuilds) {
        MeshPartGPU gp;
        gp.partId = pb.partId;
        gp.color[0] = g_palette[colorIdx % PALETTE_SIZE][0];
        gp.color[1] = g_palette[colorIdx % PALETTE_SIZE][1];
        gp.color[2] = g_palette[colorIdx % PALETTE_SIZE][2];
        gp.indexCount = static_cast<GLsizei>(pb.indices.size());
        colorIdx++;

        glGenVertexArrays(1, &gp.vao);
        glBindVertexArray(gp.vao);

        // Bind shared global VBO — no offset, indices are global
        glBindBuffer(GL_ARRAY_BUFFER, globalVBO_);

        // Vertex attributes (no byte offset — indices handle the addressing)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(MeshVertex),
                              (void*)offsetof(MeshVertex, px));
        glEnableVertexAttribArray(0);

        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, sizeof(MeshVertex),
                              (void*)offsetof(MeshVertex, nx));
        glEnableVertexAttribArray(1);

        glVertexAttribPointer(2, 1, GL_FLOAT, GL_FALSE, sizeof(MeshVertex),
                              (void*)offsetof(MeshVertex, fringe));
        glEnableVertexAttribArray(2);

        // EBO with global indices
        glGenBuffers(1, &gp.ebo);
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, gp.ebo);
        glBufferData(GL_ELEMENT_ARRAY_BUFFER,
                     pb.indices.size() * sizeof(uint32_t),
                     pb.indices.data(), GL_STATIC_DRAW);

        parts_.push_back(gp);
    }

    glBindVertexArray(0);
}

void MeshGPU::updatePositions(const std::vector<float>& deformedCoords,
                               const std::vector<float>& fringePerNode) {
    bool hasFringe = !fringePerNode.empty();

    for (size_t i = 0; i < cpuVertices_.size(); ++i) {
        int ni = vertToNode_[i];
        if (ni >= 0 && static_cast<size_t>(ni * 3 + 2) < deformedCoords.size()) {
            cpuVertices_[i].px = deformedCoords[ni*3+0];
            cpuVertices_[i].py = deformedCoords[ni*3+1];
            cpuVertices_[i].pz = deformedCoords[ni*3+2];
        }
        if (hasFringe && ni >= 0 && static_cast<size_t>(ni) < fringePerNode.size()) {
            cpuVertices_[i].fringe = fringePerNode[ni];
        }
    }

    // Upload
    glBindBuffer(GL_ARRAY_BUFFER, globalVBO_);
    glBufferSubData(GL_ARRAY_BUFFER, 0,
                    cpuVertices_.size() * sizeof(MeshVertex), cpuVertices_.data());
}

void MeshGPU::draw(bool useFringe) const {
    for (const auto& p : parts_) {
        if (!p.visible) continue;
        glBindVertexArray(p.vao);
        glDrawElements(GL_TRIANGLES, p.indexCount, GL_UNSIGNED_INT, nullptr);
    }
}
