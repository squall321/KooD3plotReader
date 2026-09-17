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

    return true;
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

std::vector<bool> SurfaceStressAnalyzer::deletedSolidMask(const data::StateData& state, size_t num_solids) {
    std::vector<bool> mask;
    if (state.deleted_solids.empty() || num_solids == 0) return mask;
    mask.assign(num_solids, false);
    for (int32_t ord : state.deleted_solids) {
        if (ord < 1) continue;
        const size_t idx = static_cast<size_t>(ord) - 1;
        if (idx < num_solids) mask[idx] = true;
    }
    return mask;
}

FaceStressResult SurfaceStressAnalyzer::analyzeFace(
    const Face& face,
    const data::StateData& state
) {
    FaceStressResult result;
    result.element_id = face.element_real_id;
    result.part_id = face.part_id;
    result.time = state.time;
    result.face_normal = face.normal;
    result.face_centroid = face.centroid;
    result.sxx = result.syy = result.szz = 0;
    result.sxy = result.syz = result.szx = 0;
    result.von_mises = result.normal_stress = result.shear_stress = 0;
    result.max_principal = result.min_principal = 0;

    // face.element_id 는 SurfaceExtractor 가 준 **내부 0-based 순번**이고
    // state.solid_data 도 같은 순번으로 놓여 있다. 예전엔 이 순번을 실제 요소 ID
    // 사전에서 찾아, 실제 ID 가 순번과 다른 덱에서는 전 면이 '못 찾음 → 0' 으로
    // 집계됐다 (배터리 덱 파트 100 ±Z: 22시점 전부 0).
    // 셸 면의 element_id 는 셸 배열 순번이라 solid_data 로 읽으면 남의 응력이다.
    if (face.element_type != SurfaceElementType::SOLID || face.element_id < 0 || nv3d_ < 6) {
        return result;
    }
    const size_t elem_index = static_cast<size_t>(face.element_id);
    if (elem_index * static_cast<size_t>(nv3d_) + 6 > state.solid_data.size()) {
        return result;
    }
    result.valid = true;
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
    stats.max_principal_max = -std::numeric_limits<double>::max();
    stats.max_principal_min = std::numeric_limits<double>::max();
    stats.min_principal_max = -std::numeric_limits<double>::max();
    stats.min_principal_min = std::numeric_limits<double>::max();

    double von_mises_sum = 0;
    double normal_stress_sum = 0;
    double shear_stress_sum = 0;
    double max_principal_sum = 0;
    double min_principal_sum = 0;

    // 침식된 요소의 면은 뺀다 — 응력 워드가 0 으로 실려 '실측 0' 으로 위장된다.
    const std::vector<bool> dead =
        deletedSolidMask(state, static_cast<size_t>(std::max(num_solid_elements_, 0)));

    size_t n = 0;
    for (const auto& face : faces) {
        if (!dead.empty() && face.element_id >= 0 &&
            static_cast<size_t>(face.element_id) < dead.size() &&
            dead[static_cast<size_t>(face.element_id)]) {
            ++stats.num_faces_skipped;
            continue;
        }
        FaceStressResult result = analyzeFace(face, state);
        if (!result.valid) {
            ++stats.num_faces_skipped;
            continue;
        }
        ++n;

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

        // σ1 — 최대값 추적
        if (result.max_principal > stats.max_principal_max) {
            stats.max_principal_max = result.max_principal;
            stats.max_principal_max_element = result.element_id;
        }
        if (result.max_principal < stats.max_principal_min) {
            stats.max_principal_min = result.max_principal;
        }
        max_principal_sum += result.max_principal;

        // σ3 — 압축측이므로 **최소값**에 대표 요소를 붙인다
        if (result.min_principal < stats.min_principal_min) {
            stats.min_principal_min = result.min_principal;
            stats.min_principal_min_element = result.element_id;
        }
        if (result.min_principal > stats.min_principal_max) {
            stats.min_principal_max = result.min_principal;
        }
        min_principal_sum += result.min_principal;
    }

    stats.num_faces = n;
    if (n == 0) {
        // 읽은 면이 없다(전량 침식 등) — 0 이나 극값 초기값(±max)으로 위장하지 않고
        // NaN 으로 남긴다. JSON 에는 null 로 나간다.
        const double nan_v = std::numeric_limits<double>::quiet_NaN();
        SurfaceStressStats empty;
        empty.time = state.time;
        empty.num_faces_skipped = stats.num_faces_skipped;
        empty.von_mises_max = empty.von_mises_min = empty.von_mises_avg = nan_v;
        empty.normal_stress_max = empty.normal_stress_min = empty.normal_stress_avg = nan_v;
        empty.shear_stress_max = empty.shear_stress_min = empty.shear_stress_avg = nan_v;
        empty.max_principal_max = empty.max_principal_min = empty.max_principal_avg = nan_v;
        empty.min_principal_max = empty.min_principal_min = empty.min_principal_avg = nan_v;
        return empty;
    }
    stats.von_mises_avg = von_mises_sum / n;
    stats.normal_stress_avg = normal_stress_sum / n;
    stats.shear_stress_avg = shear_stress_sum / n;
    stats.max_principal_avg = max_principal_sum / n;
    stats.min_principal_avg = min_principal_sum / n;

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
        result.data.push_back(toTimePoint(stats));
    }

    // Set num_faces from first time point if available
    if (!history.time_history.empty()) {
        result.num_faces = static_cast<int32_t>(history.time_history[0].num_faces);
    }

    return result;
}

SurfaceTimePointStats SurfaceStressAnalyzer::toTimePoint(const SurfaceStressStats& stats) {
    SurfaceTimePointStats tp;
    tp.time = stats.time;
    tp.normal_stress_max = stats.normal_stress_max;
    tp.normal_stress_min = stats.normal_stress_min;
    tp.normal_stress_avg = stats.normal_stress_avg;
    tp.normal_stress_max_element_id = stats.normal_stress_max_element;
    tp.shear_stress_max = stats.shear_stress_max;
    tp.shear_stress_avg = stats.shear_stress_avg;
    tp.shear_stress_max_element_id = stats.shear_stress_max_element;
    tp.von_mises_max = stats.von_mises_max;
    tp.von_mises_min = stats.von_mises_min;
    tp.von_mises_avg = stats.von_mises_avg;
    tp.von_mises_max_element_id = stats.von_mises_max_element;
    tp.max_principal_max = stats.max_principal_max;
    tp.max_principal_min = stats.max_principal_min;
    tp.max_principal_avg = stats.max_principal_avg;
    tp.max_principal_max_element_id = stats.max_principal_max_element;
    tp.min_principal_max = stats.min_principal_max;
    tp.min_principal_min = stats.min_principal_min;
    tp.min_principal_avg = stats.min_principal_avg;
    tp.min_principal_min_element_id = stats.min_principal_min_element;
    return tp;
}

} // namespace analysis
} // namespace kood3plot
