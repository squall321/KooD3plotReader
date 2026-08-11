// 빔 단면력 분석 구현 — d3plot beam_data(NV1D) 를 파트별 시계열로 집계
/**
 * @file BeamAnalyzer.cpp
 * @brief Beam resultant force analysis implementation
 */

#include "kood3plot/analysis/BeamAnalyzer.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <map>

namespace kood3plot {
namespace analysis {

namespace {
/// 빔 단면력이 실리는 워드 수. 이보다 짧으면 단면력 자체가 없는 것이다.
constexpr int32_t kBeamResultantWords = 6;
}  // namespace

BeamAnalyzer::BeamAnalyzer(D3plotReader& reader) : reader_(reader) {}

bool BeamAnalyzer::initialize() {
    initialized_ = false;
    last_error_.clear();

    const auto& cd = reader_.get_control_data();
    num_beams_ = cd.NEL2;
    nv1d_ = cd.NV1D;

    if (num_beams_ <= 0) {
        last_error_ = "빔 요소 없음 (NEL2=0)";
        return false;
    }
    if (nv1d_ < kBeamResultantWords) {
        // NV1D 가 6 미만이면 단면력이 기록되지 않은 것 — 0 으로 채우면
        // '축력 0' 으로 오독되므로 여기서 끊는다.
        last_error_ = "빔 단면력 미기록 (NV1D=" + std::to_string(nv1d_) +
                      ", 6 이상 필요). *DATABASE_EXTENT_BINARY 확인";
        return false;
    }

    mesh_ = reader_.read_mesh();
    if (mesh_.beams.empty()) {
        last_error_ = "메시에 빔 연결성이 없음";
        return false;
    }

    initialized_ = true;
    return true;
}

std::vector<PartTimeSeriesStats> BeamAnalyzer::analyze(
    const std::vector<data::StateData>& states,
    const std::vector<BeamComponent>& components) {

    std::vector<PartTimeSeriesStats> out;
    if (!initialized_ || states.empty()) {
        return out;
    }

    std::vector<BeamComponent> comps = components;
    if (comps.empty()) {
        comps = {BeamComponent::AXIAL_FORCE, BeamComponent::SHEAR_S,
                 BeamComponent::SHEAR_T,     BeamComponent::MOMENT_S,
                 BeamComponent::MOMENT_T,    BeamComponent::TORSION};
    }

    // 파트 → 빔 인덱스 목록
    std::map<int32_t, std::vector<size_t>> part_beams;
    const size_t n_beam = mesh_.beams.size();
    for (size_t i = 0; i < n_beam; ++i) {
        const int32_t pid = (i < mesh_.beam_parts.size()) ? mesh_.beam_parts[i] : 0;
        if (!target_parts_.empty() &&
            std::find(target_parts_.begin(), target_parts_.end(), pid) == target_parts_.end()) {
            continue;
        }
        part_beams[pid].push_back(i);
    }
    if (part_beams.empty()) {
        return out;
    }

    const size_t stride = static_cast<size_t>(nv1d_);

    for (const auto& comp : comps) {
        const size_t word = static_cast<size_t>(comp);

        for (const auto& kv : part_beams) {
            PartTimeSeriesStats st;
            st.part_id = kv.first;
            st.quantity = std::string("beam_") + beamComponentName(comp);
            st.data.reserve(states.size());

            for (const auto& state : states) {
                TimePointStats tp;
                tp.time = state.time;

                double mx = -std::numeric_limits<double>::max();
                double mn = std::numeric_limits<double>::max();
                double sum = 0.0;
                double sq = 0.0;
                size_t n = 0;

                for (size_t bi : kv.second) {
                    const size_t base = bi * stride;
                    if (base + word >= state.beam_data.size()) continue;
                    const double v = state.beam_data[base + word];
                    if (!std::isfinite(v)) continue;   // 삭제된 빔의 inf/nan 제외

                    const int32_t eid = (bi < mesh_.beams.size())
                                        ? mesh_.beams[bi].id
                                        : static_cast<int32_t>(bi + 1);
                    if (v > mx) { mx = v; tp.max_element_id = eid; }
                    if (v < mn) { mn = v; tp.min_element_id = eid; }
                    sum += v;
                    sq += v * v;
                    ++n;
                }

                if (n > 0) {
                    // 축력은 부호가 의미다 — 인장(+)/압축(−)을 절대값으로
                    // 뭉개지 않고 max/min 을 모두 남긴다.
                    tp.max_value = mx;
                    tp.min_value = mn;
                    tp.avg_value = sum / static_cast<double>(n);
                    tp.rms_value = std::sqrt(sq / static_cast<double>(n));
                }
                st.data.push_back(tp);
            }

            if (!st.data.empty()) {
                out.push_back(std::move(st));
            }
        }
    }

    return out;
}

}  // namespace analysis
}  // namespace kood3plot
