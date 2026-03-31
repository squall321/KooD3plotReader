#include "data/SimData.hpp"
#include <iostream>
#include <cmath>
#include <set>

using namespace kood3plot;
using namespace kood3plot::analysis;

bool SimData::loadMesh(const std::string& d3plotPath) {
    D3plotReader reader(d3plotPath);
    ErrorCode err = reader.open();
    if (err != ErrorCode::SUCCESS) {
        loadError = "Failed to open d3plot";
        return false;
    }

    mesh = reader.read_mesh();
    control = reader.get_control_data();

    // Build initial coords (float)
    initialCoords.resize(mesh.nodes.size() * 3);
    for (size_t i = 0; i < mesh.nodes.size(); ++i) {
        initialCoords[i*3+0] = static_cast<float>(mesh.nodes[i].x);
        initialCoords[i*3+1] = static_cast<float>(mesh.nodes[i].y);
        initialCoords[i*3+2] = static_cast<float>(mesh.nodes[i].z);
    }

    // Extract exterior surfaces
    SurfaceExtractor extractor(reader);
    if (extractor.initialize()) {
        auto result = extractor.extractExteriorSurfaces();
        extFaces = std::move(result.faces);
    }

    meshLoaded = true;
    return true;
}

void SimData::loadStatesAsync(const std::string& d3plotPath, int threads) {
    loadThread_ = std::thread([this, d3plotPath, threads]() {
        D3plotReader reader(d3plotPath);
        if (reader.open() != ErrorCode::SUCCESS) {
            loadError = "Failed to open d3plot for states";
            return;
        }
        states = reader.read_all_states_parallel(threads);
        statesLoaded = true;
    });
    loadThread_.detach();
}

std::vector<MeshGPU::InputFace> SimData::buildGPUFaces() const {
    std::vector<MeshGPU::InputFace> result;
    result.reserve(extFaces.size());

    for (const auto& f : extFaces) {
        MeshGPU::InputFace gf;
        gf.partId = f.part_id;
        gf.nx = static_cast<float>(f.normal.x);
        gf.ny = static_cast<float>(f.normal.y);
        gf.nz = static_cast<float>(f.normal.z);

        int n = std::min(static_cast<int>(f.node_indices.size()), 4);
        for (int i = 0; i < 4; ++i) {
            gf.nodeIdx[i] = (i < n) ? f.node_indices[i] : -1;
        }

        result.push_back(gf);
    }
    return result;
}

std::vector<float> SimData::getDeformedCoords(int stateIdx) const {
    if (stateIdx < 0 || stateIdx >= numStates()) return initialCoords;

    const auto& st = states[stateIdx];
    std::vector<float> coords(initialCoords);

    if (!st.node_displacements.empty()) {
        size_t n = std::min(mesh.nodes.size(), st.node_displacements.size() / 3);
        for (size_t i = 0; i < n; ++i) {
            coords[i*3+0] += static_cast<float>(st.node_displacements[i*3+0]);
            coords[i*3+1] += static_cast<float>(st.node_displacements[i*3+1]);
            coords[i*3+2] += static_cast<float>(st.node_displacements[i*3+2]);
        }
    }
    return coords;
}

std::vector<float> SimData::getVonMisesFringe(int stateIdx) const {
    std::vector<float> fringe(mesh.nodes.size(), 0.0f);
    if (stateIdx < 0 || stateIdx >= numStates()) return fringe;

    const auto& st = states[stateIdx];
    if (st.solid_data.empty()) return fringe;

    int nv3d = control.NV3D;
    if (nv3d < 7) return fringe;

    // Per-node: average Von Mises from connected elements
    std::vector<float> nodeSum(mesh.nodes.size(), 0.0f);
    std::vector<int> nodeCount(mesh.nodes.size(), 0);

    float globalMax = 0.0f;

    for (size_t ei = 0; ei < mesh.solids.size(); ++ei) {
        size_t base = ei * nv3d;
        if (base + 5 >= st.solid_data.size()) break;

        double sxx = st.solid_data[base+0];
        double syy = st.solid_data[base+1];
        double szz = st.solid_data[base+2];
        double sxy = st.solid_data[base+3];
        double syz = st.solid_data[base+4];
        double szx = st.solid_data[base+5];
        double d1 = sxx-syy, d2 = syy-szz, d3 = szz-sxx;
        float vm = static_cast<float>(std::sqrt(0.5*(d1*d1+d2*d2+d3*d3) + 3.0*(sxy*sxy+syz*syz+szx*szx)));

        if (vm > globalMax) globalMax = vm;

        const auto& elem = mesh.solids[ei];
        for (int32_t nid : elem.node_ids) {
            int ni = nid - 1;  // 1-based → 0-based
            if (ni >= 0 && ni < static_cast<int>(mesh.nodes.size())) {
                nodeSum[ni] += vm;
                nodeCount[ni]++;
            }
        }
    }

    // Normalize to [0, 1]
    if (globalMax > 1e-10f) {
        for (size_t i = 0; i < fringe.size(); ++i) {
            if (nodeCount[i] > 0) {
                fringe[i] = (nodeSum[i] / nodeCount[i]) / globalMax;
            }
        }
    }

    return fringe;
}
