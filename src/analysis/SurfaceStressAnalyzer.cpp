/**
 * @file SurfaceStressAnalyzer.cpp
 * @brief Implementation of surface stress analysis
 */

#include "kood3plot/analysis/SurfaceStressAnalyzer.hpp"
#include "kood3plot/data/ControlData.hpp"
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cmath>
#include <limits>
#include <iostream>

namespace kood3plot {
namespace analysis {

SurfaceStressAnalyzer::SurfaceStressAnalyzer(D3plotReader& reader)
    : reader_(reader)
    , nv3d_(0)
    , num_solid_elements_(0)
{
    initialize();
}

bool SurfaceStressAnalyzer::initialize() {
    // Get control data
    const auto& control_data = reader_.get_control_data();

    nv3d_ = control_data.NV3D;
    num_solid_elements_ = control_data.NEL8;

    // Build element ID to index mapping
    buildElementIndexMap();

    return true;
}

void SurfaceStressAnalyzer::buildElementIndexMap() {
    data::Mesh mesh = reader_.read_mesh();

    elem_id_to_index_.clear();

    // Use real_solid_ids if available, otherwise use sequential indexing
    if (!mesh.real_solid_ids.empty()) {
        for (size_t i = 0; i < mesh.real_solid_ids.size(); ++i) {
            elem_id_to_index_[mesh.real_solid_ids[i]] = i;
        }
    } else {
        // Fallback: use 1-based sequential IDs
        for (size_t i = 0; i < mesh.solids.size(); ++i) {
            elem_id_to_index_[mesh.solids[i].id] = i;
        }
    }
}

StressTensor SurfaceStressAnalyzer::extractStressTensor(
    const data::StateData& state,
    size_t elem_internal_index
) {
    // Solid element stress layout (per element):
    // Words 0-5: sxx, syy, szz, sxy, yz, zx (stress components)
    // Word 6: effective plastic strain
    // Words 7+: extra history variables or strain

    const auto& solid_data = state.solid_data;
    size_t base_offset = elem_internal_index * nv3d_;

    if (base_offset + 6 > solid_data.size()) {
        // Return zero tensor if data not available
        return StressTensor(0, 0, 0, 0, 0, 0);
    }

    double sxx = solid_data[base_offset + 0];
    double syy = solid_data[base_offset + 1];
    double szz = solid_data[base_offset + 2];
    double sxy = solid_data[base_offset + 3];
    double syz = solid_data[base_offset + 4];
    double szx = solid_data[base_offset + 5];

    return StressTensor(sxx, syy, szz, sxy, syz, szx);
}

FaceStressResult SurfaceStressAnalyzer::analyzeFace(
    const Face& face,
    const data::StateData& state
) {
    FaceStressResult result;
    result.element_id = face.element_id;
    result.part_id = face.part_id;
    result.time = state.time;
    result.face_normal = face.normal;
    result.face_centroid = face.centroid;

    // Get internal index for element
    auto it = elem_id_to_index_.find(face.element_id);
    if (it == elem_id_to_index_.end()) {
        // Element not found - return zeros
        result.sxx = result.syy = result.szz = 0;
        result.sxy = result.syz = result.szx = 0;
        result.von_mises = result.normal_stress = result.shear_stress = 0;
        result.max_principal = result.min_principal = 0;
        return result;
    }

    size_t elem_index = it->second;
    StressTensor stress = extractStressTensor(state, elem_index);

    // Store raw components
    result.sxx = stress.xx;
    result.syy = stress.yy;
    result.szz = stress.zz;
    result.sxy = stress.xy;
    result.syz = stress.yz;
    result.szx = stress.zx;

    // Calculate derived values
    result.von_mises = stress.vonMises();
    result.normal_stress = stress.normalStress(face.normal);
    result.shear_stress = stress.shearStress(face.normal);

    auto principals = stress.principalStresses();
    result.max_principal = principals[0];
    result.min_principal = principals[2];

    return result;
}

std::vector<FaceStressResult> SurfaceStressAnalyzer::analyzeFaces(
    const std::vector<Face>& faces,
    const data::StateData& state
) {
    std::vector<FaceStressResult> results;
    results.reserve(faces.size());

    for (const auto& face : faces) {
        results.push_back(analyzeFace(face, state));
    }

    return results;
}

SurfaceStressStats SurfaceStressAnalyzer::analyzeState(
    const std::vector<Face>& faces,
    const data::StateData& state
) {
    SurfaceStressStats stats;
    stats.time = state.time;
    stats.num_faces = faces.size();

    if (faces.empty()) {
        return stats;
    }

    // Initialize with extreme values
    stats.von_mises_max = -std::numeric_limits<double>::max();
    stats.von_mises_min = std::numeric_limits<double>::max();
    stats.normal_stress_max = -std::numeric_limits<double>::max();
    stats.normal_stress_min = std::numeric_limits<double>::max();
    stats.shear_stress_max = -std::numeric_limits<double>::max();
    stats.shear_stress_min = std::numeric_limits<double>::max();

    double von_mises_sum = 0;
    double normal_stress_sum = 0;
    double shear_stress_sum = 0;

    for (const auto& face : faces) {
        FaceStressResult result = analyzeFace(face, state);

        // Von Mises
        if (result.von_mises > stats.von_mises_max) {
            stats.von_mises_max = result.von_mises;
            stats.von_mises_max_element = result.element_id;
        }
        if (result.von_mises < stats.von_mises_min) {
            stats.von_mises_min = result.von_mises;
        }
        von_mises_sum += result.von_mises;

        // Normal stress (can be negative for compression)
        if (result.normal_stress > stats.normal_stress_max) {
            stats.normal_stress_max = result.normal_stress;
            stats.normal_stress_max_element = result.element_id;
        }
        if (result.normal_stress < stats.normal_stress_min) {
            stats.normal_stress_min = result.normal_stress;
        }
        normal_stress_sum += result.normal_stress;

        // Shear stress (always positive)
        if (result.shear_stress > stats.shear_stress_max) {
            stats.shear_stress_max = result.shear_stress;
            stats.shear_stress_max_element = result.element_id;
        }
        if (result.shear_stress < stats.shear_stress_min) {
            stats.shear_stress_min = result.shear_stress;
        }
        shear_stress_sum += result.shear_stress;
    }

    size_t n = faces.size();
    stats.von_mises_avg = von_mises_sum / n;
    stats.normal_stress_avg = normal_stress_sum / n;
    stats.shear_stress_avg = shear_stress_sum / n;

    return stats;
}

SurfaceStressHistory SurfaceStressAnalyzer::analyzeAllStates(
    const std::vector<Face>& faces,
    const Vec3& reference_direction,
    double angle_threshold
) {
    return analyzeAllStates(faces, reference_direction, angle_threshold, nullptr);
}

SurfaceStressHistory SurfaceStressAnalyzer::analyzeAllStates(
    const std::vector<Face>& faces,
    const Vec3& reference_direction,
    double angle_threshold,
    ProgressCallback callback
) {
    SurfaceStressHistory history;
    history.reference_direction = reference_direction;
    history.angle_threshold_degrees = angle_threshold;

    if (faces.empty()) {
        return history;
    }

    // Get number of states
    size_t num_states = reader_.get_num_states();
    history.time_history.reserve(num_states);

    // Initialize global extremes
    history.global_von_mises_max = -std::numeric_limits<double>::max();
    history.global_normal_stress_max = -std::numeric_limits<double>::max();
    history.global_shear_stress_max = -std::numeric_limits<double>::max();

    for (size_t state_idx = 0; state_idx < num_states; ++state_idx) {
        if (callback) {
            callback(state_idx, num_states, "Analyzing state " + std::to_string(state_idx + 1));
        }

        // Read state data
        data::StateData state = reader_.read_state(state_idx);

        // Analyze this state
        SurfaceStressStats stats = analyzeState(faces, state);
        history.time_history.push_back(stats);

        // Update global maxes
        if (stats.von_mises_max > history.global_von_mises_max) {
            history.global_von_mises_max = stats.von_mises_max;
            history.time_of_max_von_mises = stats.time;
        }
        if (stats.normal_stress_max > history.global_normal_stress_max) {
            history.global_normal_stress_max = stats.normal_stress_max;
            history.time_of_max_normal_stress = stats.time;
        }
        if (stats.shear_stress_max > history.global_shear_stress_max) {
            history.global_shear_stress_max = stats.shear_stress_max;
            history.time_of_max_shear_stress = stats.time;
        }
    }

    if (callback) {
        callback(num_states, num_states, "Analysis complete");
    }

    return history;
}

bool SurfaceStressAnalyzer::exportToCSV(
    const SurfaceStressHistory& history,
    const std::string& filepath
) {
    std::ofstream file(filepath);
    if (!file.is_open()) {
        return false;
    }

    // Header
    file << "Time,NumFaces,"
         << "VonMises_Max,VonMises_Min,VonMises_Avg,VonMises_MaxElem,"
         << "NormalStress_Max,NormalStress_Min,NormalStress_Avg,NormalStress_MaxElem,"
         << "ShearStress_Max,ShearStress_Min,ShearStress_Avg,ShearStress_MaxElem\n";

    // Data
    for (const auto& stats : history.time_history) {
        file << stats.time << "," << stats.num_faces << ","
             << stats.von_mises_max << "," << stats.von_mises_min << ","
             << stats.von_mises_avg << "," << stats.von_mises_max_element << ","
             << stats.normal_stress_max << "," << stats.normal_stress_min << ","
             << stats.normal_stress_avg << "," << stats.normal_stress_max_element << ","
             << stats.shear_stress_max << "," << stats.shear_stress_min << ","
             << stats.shear_stress_avg << "," << stats.shear_stress_max_element << "\n";
    }

    file.close();
    return true;
}

SurfaceAnalysisStats SurfaceStressAnalyzer::toAnalysisStats(
    const SurfaceStressHistory& history
) {
    SurfaceAnalysisStats result;
    result.reference_direction = history.reference_direction;
    result.angle_threshold_degrees = history.angle_threshold_degrees;

    // Convert time history to SurfaceTimePointStats
    for (const auto& stats : history.time_history) {
        SurfaceTimePointStats point;
        point.time = stats.time;
        point.normal_stress_max = stats.normal_stress_max;
        point.normal_stress_min = stats.normal_stress_min;
        point.normal_stress_avg = stats.normal_stress_avg;
        point.normal_stress_max_element_id = stats.normal_stress_max_element;
        point.shear_stress_max = stats.shear_stress_max;
        point.shear_stress_avg = stats.shear_stress_avg;
        point.shear_stress_max_element_id = stats.shear_stress_max_element;
        result.data.push_back(point);
    }

    // Set num_faces from first time point if available
    if (!history.time_history.empty()) {
        result.num_faces = static_cast<int32_t>(history.time_history[0].num_faces);
    }

    return result;
}

} // namespace analysis
} // namespace kood3plot
