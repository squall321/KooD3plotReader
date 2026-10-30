// S1 경량 추출본의 기하 핵심 — 겉면 규칙(StepForge 꼴) · 요소 von Mises · 바닥 평면 · 자세 재료
#pragma once

#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"

#include <array>
#include <cstdint>
#include <set>
#include <string>
#include <vector>

namespace kood3plot {
namespace s1 {

/// 솔리드 요소의 꼴 — StepForge `core/deck_surface.py` solid_form 과 같은 판정
enum class SolidForm { Hex, Tet, Wedge, Pyramid };

/**
 * @brief 8슬롯 솔리드의 꼴. 모르는 축퇴 꼴은 std::runtime_error.
 * @param conn 8칸 절점(어떤 번호 체계든 같은 절점은 같은 값)
 */
SolidForm solidForm(const std::array<int32_t, 8>& conn);

/**
 * @brief 요소의 면들 — 양의 야코비안에서 바깥 법선 차례의 절점 고리(삼각 3 · 사변형 4).
 *        방향은 요소 차례를 따른다(뒤집힌 요소는 extractSurface 가 부피 부호로 맞춘다).
 */
std::vector<std::vector<int32_t>> solidFaces(const std::array<int32_t, 8>& conn,
                                             SolidForm* form = nullptr);

/// 겉면 한 장 — 절점은 0-based 내부 절점 순번, 넷째가 −1 이면 삼각형
struct SurfaceFace {
    std::array<int32_t, 4> nodes{-1, -1, -1, -1};
    size_t solid_index = 0;   ///< mesh.solids 의 순번
};

struct Surface {
    std::vector<SurfaceFace> faces;
    size_t n_device_elems = 0;          ///< 대상 솔리드 수(제외 파트 뺌)
    std::set<int32_t> device_nodes;     ///< 대상 솔리드의 절점(0-based 내부 순번)
    size_t n_inter_part_shared_faces = 0;  ///< 서로 다른 파트의 두 요소가 공유한 면 수
    size_t n_flipped_elems = 0;         ///< 부피 부호가 음수라 면을 뒤집은 요소 수
    size_t n_shell_elems_skipped = 0;   ///< 셸 · 두꺼운 셸(판 1 에 넣지 않음)
};

/**
 * @brief 대상 솔리드 전체에서 한 번만 나온 면 = 겉면.
 *        정렬한 고유 절점을 열쇠로 센다. 셋 이상 나온 면(비다양체)·모르는 꼴은 std::runtime_error.
 * @param excluded_parts 겉면에서 뺄 파트(환경 — 바닥 등)
 */
Surface extractSurface(const data::Mesh& mesh, const std::set<int32_t>& excluded_parts);

/// 솔리드 요소 e 의 von Mises (solid_data 의 앞 6 성분 σxx σyy σzz σxy σyz σzx)
double solidVonMises(const data::StateData& state, size_t elem_index, int nv3d);

/// 3성분 벡터 (이 모듈 전용)
struct V3 {
    double x = 0, y = 0, z = 0;
};

/// 바닥 평면 — 바닥 파트의 기기 쪽 층
struct FloorPlane {
    V3 point;               ///< 그 층 절점 무게중심
    V3 normal;              ///< 기기 쪽 단위 법선
    double flatness = 0;    ///< 그 층 절점의 평면 잔차 최대
    size_t n_layer_nodes = 0;
};

/**
 * @brief 바닥 절점에서 기기 쪽 층을 골라 평면을 맞춘다.
 *        주성분(가장 작은 고윳값) 방향을 법선으로 잡고 기기 무게중심 쪽으로 돌린 뒤,
 *        법선 투영이 가장 큰(기기에 가장 가까운) 층만으로 다시 맞춘다.
 * @throws std::runtime_error 절점이 3개 미만이거나 평면이 아닐 때
 */
FloorPlane fitFloorPlane(const std::vector<V3>& floor_nodes, const V3& device_centroid);

/// 대칭 3×3 행렬의 가장 작은 고윳값에 맞는 단위 고유벡터 (야코비 회전)
V3 smallestEigenvector(const double m[3][3]);

}  // namespace s1
}  // namespace kood3plot
