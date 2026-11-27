// LS-PrePost 타깃 렌더에 걸 색 범위를 타깃 파트의 값으로 내는 도우미 — 전 상태, 요소 값은 LS-PrePost 의 「max IP. value」
#pragma once
/**
 * @file TargetFringeRange.h
 * @brief 타깃 파트의 fringe 값 범위
 *
 * LS-PrePost 의 자동 범위는 화면에 보이는 모델 전체에서 잡혀, 타깃만 색을 입혀도 응력이 작은 타깃은 거의 한 색이 된다
 * (Test_006 파트 6 — 단면 최대 46.8 대 자동 범위 287). 그래서 타깃 렌더에는 타깃 파트의 범위를 `range userdef` 로 건다
 * (사용자 결정 2026-11-22). 값은 LS-PrePost 가 칠하는 것과 같게 낸다.
 *   - 솔리드 — 값이 실린 적분점 자리마다 낸 값의 최대(0 으로 채운 자리는 뺀다)
 *   - 셸 · 두꺼운 셸 — 저장된 층마다 낸 값의 최대. 층 배치를 믿지 못하는 덱은 넣지 않는다
 *   - 값 — von Mises · 유효 소성 변형률 · 압력(대수) · 최대 전단 (σ1−σ3)/2, 변위 · 속도 · 가속도는 타깃 요소 절점의 크기
 *   - 지운 요소(상태별 삭제 목록 — 1부터 순번)는 그 상태에서 뺀다
 *   - 변위 · 속도 · 가속도는 그 상태에서 산 요소에 하나도 속하지 않는 절점(지운 요소에만 속해 떨어져 나간 절점)을 뺀다
 * 범위를 낼 수 없으면(모르는 fringe, 값이 없거나 한 값뿐) ok = false — 부르는 쪽이 LS-PrePost 자동 범위를 그대로 쓴다.
 */

#include "kood3plot/data/ControlData.hpp"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"
#include "kood3plot/render/LSPrePostRenderer.h"

#include <cstdint>
#include <functional>
#include <map>
#include <vector>

namespace kood3plot {
class D3plotReader;

namespace render {

/// 색 범위 — ok 가 거짓이면 LS-PrePost 자동 범위를 그대로 쓴다
struct FringeRange {
    bool ok = false;
    double min = 0.0;
    double max = 0.0;
};

/// 상태 index 를 out 에 채운다 — 못 채우면 거짓
using StateSource = std::function<bool(size_t index, data::StateData& out)>;

/// 파트마다 전 상태의 fringe 값 범위. 키는 parts 의 파트 번호(값이 없으면 ok = false)
std::map<int32_t, FringeRange> partFringeRanges(const data::Mesh& mesh, const data::ControlData& control,
                                                size_t num_states, const StateSource& states,
                                                const std::vector<int32_t>& parts, FringeType type);

/// D3plotReader 로 메시 · 머리말 · 상태를 읽어 위를 부른다(상태는 read_state — 전 상태 캐시를 쓴다)
std::map<int32_t, FringeRange> partFringeRanges(D3plotReader& reader, const std::vector<int32_t>& parts, FringeType type);

/// 여러 파트를 합친 범위 — 값이 있는 파트만
FringeRange mergeRanges(const std::map<int32_t, FringeRange>& ranges, const std::vector<int32_t>& parts);

}  // namespace render
}  // namespace kood3plot
