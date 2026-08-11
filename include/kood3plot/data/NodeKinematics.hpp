// d3plot 절점 좌표/변위를 규약에 맞게 읽는 단일 진입점 (직접 인덱싱 금지)
/**
 * @file NodeKinematics.hpp
 * @brief 절점 현재좌표·변위를 구하는 유일한 올바른 경로
 *
 * `StateData::node_displacements` 는 이름과 달리 **d3plot 에서는 현재 절대
 * 좌표**다 (IU=1). 이 사실을 모르고 각자 인덱싱한 결과 코드베이스 전역에서
 * 두 갈래로 틀렸다.
 *
 *   (1) 좌표를 좌표로 쓰면서 초기좌표에 **또 더함** → 기하가 2·X0 + u
 *       (요소품질, 단면뷰 렌더, BoundingBox)
 *   (2) 좌표를 그대로 **변위로 씀** → 변위가 '원점으로부터의 거리'
 *       (모션 분석 피크변위, 단면뷰 변위/변형률 필드, VTK 내보내기)
 *
 * 그래서 배열을 직접 인덱싱하지 말고 여기를 쓴다.
 *
 * @note RadiossReader 가 채운 StateData 는 **델타**를 담는다
 *       (RadiossReader.cpp). 이 헬퍼는 d3plot 규약 전용이다 —
 *       Radioss 원본 상태에는 쓰지 말 것.
 */

#pragma once

#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"
#include <cstddef>
#include <cmath>

namespace kood3plot {
namespace data {

/// 3성분 값. 이 헤더만을 위한 최소 구조체 (analysis::Vec3 의존을 피한다).
struct NodeVec3 {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

/**
 * @brief 절점 벡터 배열(변위/속도/가속도)의 노드당 성분 수
 *
 * NDIM = 4, 5, 7 은 특수 포맷 표기이고 실제 공간 차원은 3 이다
 * (StateDataParser.cpp:213-217 이 그렇게 읽는다). cd.NDIM 을 그대로
 * stride 로 쓰면 어긋난다 — 실측 Test_006 은 NDIM=4 인데 배열은
 * 노드당 3 성분(93528 = 31176 x 3)이라 노드 수가 23382 로 잘못 나왔다.
 */
inline int effectiveNodeStride(int ndim) {
    return (ndim == 4 || ndim == 5 || ndim == 7) ? 3 : ndim;
}

/**
 * @brief 절점의 현재(변형 후) 좌표
 *
 * 상태에 좌표가 없으면 초기좌표를 돌려준다.
 * @param node_idx 0-based 내부 절점 인덱스
 */
inline NodeVec3 nodePosition(const Mesh& mesh,
                             const StateData& state,
                             std::size_t node_idx) {
    const std::size_t base = node_idx * 3;
    if (base + 2 < state.node_displacements.size()) {
        return {state.node_displacements[base + 0],
                state.node_displacements[base + 1],
                state.node_displacements[base + 2]};
    }
    if (node_idx < mesh.nodes.size()) {
        const auto& n = mesh.nodes[node_idx];
        return {n.x, n.y, n.z};
    }
    return {};
}

/**
 * @brief 절점 변위 u = X(t) - X(0)
 *
 * t=0 에서 정확히 0 이 나와야 한다. 0 이 아니면 이 규약이 깨진 것이다.
 */
inline NodeVec3 nodeDisplacement(const Mesh& mesh,
                                 const StateData& state,
                                 std::size_t node_idx) {
    if (node_idx >= mesh.nodes.size()) return {};
    const std::size_t base = node_idx * 3;
    if (base + 2 >= state.node_displacements.size()) return {};
    const auto& n = mesh.nodes[node_idx];
    return {state.node_displacements[base + 0] - n.x,
            state.node_displacements[base + 1] - n.y,
            state.node_displacements[base + 2] - n.z};
}

/// 변위 크기 |u|
inline double nodeDisplacementMagnitude(const Mesh& mesh,
                                        const StateData& state,
                                        std::size_t node_idx) {
    const NodeVec3 u = nodeDisplacement(mesh, state, node_idx);
    return std::sqrt(u.x * u.x + u.y * u.y + u.z * u.z);
}

} // namespace data
} // namespace kood3plot
