// 셸 · 두꺼운 셸 요소 블록의 층(두께 방향 적분점) 배치를 머리말에서 읽어, 규격 공식과 맞을 때만 믿는 작은 도우미
#pragma once
/**
 * @file ShellLayerLayout.hpp
 * @brief 셸 · 두꺼운 셸 요소 블록의 층 배치 — 층(MAXINT)마다 [응력 6][ε_p(IOSHL(2))][이력 변수 NEIPS]
 *
 * 분석기 파트 이력(SinglePassAnalyzer::layeredLayout)과 같은 검사를 통과할 때만 층으로 읽는다.
 *   - IOSHL(1) ≠ 0, MAXINT > 0, P = 6·IOSHL(1) + IOSHL(2) + NEIPS
 *   - 셸: NDIM 5 · 7(강체 셸이 빠진 채 압축 — 요소 자리가 어긋난다)이 아니고 NV2D − (MAXINT·P + 8·IOSHL(3) + 4·IOSHL(4)) ∈ {0, 12}
 *   - 두꺼운 셸: NV3DT − MAXINT·P ∈ {0, 1, 12, 13}
 * 통과하지 못하면 layers = 0 — 부르는 쪽이 종전처럼 블록의 앞 7 워드만 읽는다.
 * 쓰는 곳: 단면 렌더 절점 평균(NodalAverager), LS-PrePost 타깃 색 범위(TargetFringeRange).
 */

#include "kood3plot/data/ControlData.hpp"

#include <cstddef>

namespace kood3plot {
namespace data {

struct ShellLayerLayout {
    int    layers = 0;   ///< 저장된 층 수(MAXINT). 0 = 배치를 믿지 못한다 — 블록의 앞 7 워드만 읽는다
    int    stride = 0;   ///< 층 하나의 워드 수 = 6·IOSHL(1) + IOSHL(2) + NEIPS
    size_t words  = 0;   ///< 층마다 읽는 워드 수 — 응력 6, ε_p 를 적는 덱(IOSHL(2) = 1)은 7

    /// @param shell 참이면 셸(NV2D), 거짓이면 두꺼운 셸(NV3DT)
    static ShellLayerLayout from(const ControlData& c, bool shell)
    {
        ShellLayerLayout L;
        const int nv = shell ? c.NV2D : c.NV3DT;
        if (nv <= 0 || c.IOSHL[0] == 0 || c.MAXINT <= 0) return L;
        if (shell && (c.NDIM == 5 || c.NDIM == 7)) return L;   // 강체 셸이 빠진 채 압축된 덱 — 요소 자리가 어긋난다
        const int P = 6 * c.IOSHL[0] + c.IOSHL[1] + c.NEIPS;
        const int lw = c.MAXINT * P;
        const int rem = shell ? nv - (lw + 8 * c.IOSHL[2] + 4 * c.IOSHL[3])   // 12 = 변형률(안 · 바깥 면)
                              : nv - lw;                                      // 12 = 변형률, 1 = 내부 에너지
        const bool ok = shell ? (rem == 0 || rem == 12) : (rem == 0 || rem == 1 || rem == 12 || rem == 13);
        if (!ok) return L;
        L.layers = c.MAXINT;
        L.stride = P;
        L.words  = c.IOSHL[1] ? 7 : 6;
        return L;
    }
};

}  // namespace data
}  // namespace kood3plot
