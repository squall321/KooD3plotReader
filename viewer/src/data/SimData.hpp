#pragma once
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/SurfaceExtractor.hpp"
#include "gpu/MeshGPU.hpp"
#include <vector>
#include <string>
#include <thread>
#include <atomic>
#include <mutex>

struct SimData {
    // Mesh
    kood3plot::data::Mesh mesh;
    kood3plot::data::ControlData control;
    std::vector<kood3plot::analysis::Face> extFaces;

    // States
    std::vector<kood3plot::data::StateData> states;

    // Node coords (float, interleaved x,y,z)
    std::vector<float> initialCoords;

    // Loading status
    std::atomic<bool> meshLoaded{false};
    std::atomic<bool> statesLoaded{false};
    std::atomic<int> statesProgress{0};
    std::string loadError;

    // Load mesh (blocking)
    bool loadMesh(const std::string& d3plotPath);

    // Load states (background thread)
    void loadStatesAsync(const std::string& d3plotPath, int threads = 4);

    // Load states with memory budget (background thread).
    // maxMemMB: approximate memory budget in MB for state data.
    // Automatically computes stride to stay within budget.
    void loadStatesBudgeted(const std::string& d3plotPath, int maxMemMB = 2048);

    // Build GPU input faces from SurfaceExtractor result
    std::vector<MeshGPU::InputFace> buildGPUFaces() const;

    // Get deformed coords for state
    std::vector<float> getDeformedCoords(int stateIdx) const;

    // Get per-node Von Mises fringe for state
    std::vector<float> getVonMisesFringe(int stateIdx) const;

    int numStates() const { return static_cast<int>(states.size()); }
    double stateTime(int idx) const { return (idx >= 0 && idx < numStates()) ? states[idx].time : 0.0; }

private:
    std::thread loadThread_;
};
