// 빔 요소의 단면력(축력·전단·모멘트·비틀림)을 파트별 시계열로 뽑는 분석기
/**
 * @file BeamAnalyzer.hpp
 * @brief Beam resultant force analysis
 *
 * d3plot 의 빔 요소 데이터(NV1D)는 지금까지 파싱만 되고 아무도 쓰지 않았다.
 * 볼트·리벳·용접 대체 빔의 축력은 파단 판정의 1차 지표라 분석이 필요하다.
 *
 * 워드 배치 (ls-dyna_database.txt, NV1D >= 6):
 *   0: 축력 (axial force)      — 인장 +, 압축 −
 *   1: S 방향 전단
 *   2: T 방향 전단
 *   3: S 축 굽힘 모멘트
 *   4: T 축 굽힘 모멘트
 *   5: 비틀림 모멘트
 * NV1D > 6 이면 뒤에 적분점별 응력/변형률이 붙지만 여기서는 단면력만 쓴다.
 */

#pragma once

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/AnalysisResult.hpp"
#include "kood3plot/data/StateData.hpp"

#include <string>
#include <vector>

namespace kood3plot {
namespace analysis {

/// 빔 단면력 성분. 인덱스는 d3plot 워드 순서와 같다.
enum class BeamComponent {
    AXIAL_FORCE = 0,
    SHEAR_S     = 1,
    SHEAR_T     = 2,
    MOMENT_S    = 3,
    MOMENT_T    = 4,
    TORSION     = 5,
};

/// 성분 이름 (CSV/JSON 표기 및 파일명)
inline const char* beamComponentName(BeamComponent c) {
    switch (c) {
        case BeamComponent::AXIAL_FORCE: return "axial_force";
        case BeamComponent::SHEAR_S:     return "shear_s";
        case BeamComponent::SHEAR_T:     return "shear_t";
        case BeamComponent::MOMENT_S:    return "moment_s";
        case BeamComponent::MOMENT_T:    return "moment_t";
        case BeamComponent::TORSION:     return "torsion";
    }
    return "unknown";
}

/**
 * @brief 빔 단면력 분석기
 *
 * 파트별로 각 성분의 max/min/avg 시계열을 만든다.
 * **축력은 부호가 의미를 갖는다** — 인장(+)과 압축(−)을 절대값으로 뭉개면
 * 볼트 프리로드와 압축 좌굴을 구분할 수 없다. 그래서 max 와 min 을 모두 낸다.
 */
class BeamAnalyzer {
public:
    explicit BeamAnalyzer(D3plotReader& reader);

    /**
     * @brief 초기화 (메시·제어 데이터 확보)
     * @return 빔 요소가 없거나 NV1D 가 부족하면 false
     */
    bool initialize();

    /// 분석 대상 파트 지정 (비우면 전체)
    void setTargetParts(const std::vector<int32_t>& part_ids) { target_parts_ = part_ids; }

    /**
     * @brief 전 상태를 훑어 파트별 성분 시계열 생성
     * @param states 모든 상태
     * @param components 뽑을 성분 (비우면 6성분 전부)
     */
    std::vector<PartTimeSeriesStats> analyze(
        const std::vector<data::StateData>& states,
        const std::vector<BeamComponent>& components = {});

    /// 빔 요소 수 (초기화 후 유효)
    int32_t numBeams() const { return num_beams_; }

    /// 초기화 실패 사유. 성공이면 빈 문자열.
    const std::string& getLastError() const { return last_error_; }

private:
    D3plotReader& reader_;
    data::Mesh mesh_;
    int32_t num_beams_ = 0;
    int32_t nv1d_ = 0;
    std::vector<int32_t> target_parts_;
    std::string last_error_;
    bool initialized_ = false;
};

} // namespace analysis
} // namespace kood3plot
