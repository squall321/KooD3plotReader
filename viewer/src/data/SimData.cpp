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

void SimData::loadStatesBudgeted(const std::string& d3plotPath, int maxMemMB) {
    loadThread_ = std::thread([this, d3plotPath, maxMemMB]() {
        D3plotReader reader(d3plotPath);
        if (reader.open() != ErrorCode::SUCCESS) {
            loadError = "Failed to open d3plot for states";
            return;
        }

        size_t totalStates = reader.get_num_states();
        if (totalStates == 0) { statesLoaded = true; return; }

        // Estimate memory per state: read first state to measure
        auto st0 = reader.read_state(0);
        size_t bytesPerState = st0.node_displacements.size() * sizeof(double)
                             + st0.solid_data.size() * sizeof(double)
                             + st0.shell_data.size() * sizeof(double)
                             + sizeof(data::StateData);
        if (bytesPerState == 0) bytesPerState = 1;

        size_t budgetBytes = static_cast<size_t>(maxMemMB) * 1024ULL * 1024ULL;
        size_t maxStates = std::max(size_t(2), budgetBytes / bytesPerState);

        // Compute stride: keep first + last + evenly spaced
        size_t stride = 1;
        if (totalStates > maxStates)
            stride = (totalStates - 1) / (maxStates - 1); // -1 to always include last
        if (stride < 1) stride = 1;

        std::cout << "[SimData] Budget: " << maxMemMB << " MB, "
                  << bytesPerState / 1024 << " KB/state, "
                  << totalStates << " total → stride=" << stride
                  << " → loading ~" << std::min(totalStates, maxStates) << " states\n";

        // Load with stride
        states.clear();
        states.reserve(std::min(totalStates, maxStates) + 1);
        states.push_back(std::move(st0)); // state 0 already read
        statesProgress = 1;

        for (size_t i = stride; i < totalStates; i += stride) {
            states.push_back(reader.read_state(i));
            statesProgress = static_cast<int>(states.size() * 100 / std::min(totalStates, maxStates));
        }

        // Always include last state if not already there
        size_t lastIdx = totalStates - 1;
        if (lastIdx > 0 && (lastIdx % stride) != 0) {
            states.push_back(reader.read_state(lastIdx));
        }

        std::cout << "[SimData] Loaded " << states.size() << " / " << totalStates
                  << " states (~" << (states.size() * bytesPerState / 1024 / 1024) << " MB)\n";
        statesProgress = 100;
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
