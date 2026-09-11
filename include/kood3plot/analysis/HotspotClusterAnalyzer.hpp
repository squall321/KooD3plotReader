// 파트 내 상위 백분위 요소를 공간 군집화해 핫스팟 덩어리 단위로 보고하는 분석기
#pragma once

#include "kood3plot/Types.hpp"
#include "kood3plot/data/Mesh.hpp"

#include <cmath>
#include <cstdint>
#include <limits>
#include <map>
#include <string>
#include <vector>

namespace kood3plot {
namespace analysis {

/**
 * @brief 군집 선별 기준량
 *
 * 부호와 "뜨거운" 방향이 기준마다 다르다 (docs/hotspot-criterion-plan.md §2).
 *
 * | 기준          | 값 범위   | 뜨거운 방향        | 시간축 극값 |
 * |---------------|-----------|--------------------|-------------|
 * | VonMises      | ≥ 0       | 큰 값              | max         |
 * | MaxPrincipal  | 부호 있음 | 큰 값 (인장)       | max         |
 * | MinPrincipal  | 부호 있음 | **작은 값 (압축)** | **min**     |
 */
enum class HotspotCriterion {
    VonMises = 0,
    MaxPrincipal = 1,
    MinPrincipal = 2,
};

/// 문자열 → 기준. "von_mises" / "max_principal" / "min_principal" (대소문자·'-' 무시).
/// 모르는 이름이면 false 를 돌려주고 @p out 은 건드리지 않는다.
bool parseHotspotCriterion(const std::string& name, HotspotCriterion& out);

/// 기준 → 정규 이름 (JSON `criterion` 필드에 쓰는 값)
const char* hotspotCriterionName(HotspotCriterion c);

/// 이름 목록 → 기준 목록. 순서 유지·중복 제거. 모르는 이름은 @p unknown 에 모은다.
/// 비어 있거나 전부 모르는 이름이면 **빈 벡터** — 폴백은 호출부가 정한다.
std::vector<HotspotCriterion> parseHotspotCriteria(const std::vector<std::string>& names,
                                                   std::vector<std::string>* unknown = nullptr);

/// 요소별 시간축 극값 묶음 (기준 하나분). 크기는 전부 솔리드 요소 수.
struct ElementExtremes {
    std::vector<double> value;   ///< 극값. NaN = 미기록
    std::vector<double> time;    ///< 그 극값이 난 시각
    std::vector<double> strain;  ///< 같은 시각의 짝 변형률. 비어 있으면 미보고
};

/// 뜨거운 방향이 '작은 값' 인 기준이면 true (현재 MinPrincipal 만)
inline bool hotspotCriterionIsMin(HotspotCriterion c) {
    return c == HotspotCriterion::MinPrincipal;
}

/// a 가 b 보다 뜨거운가 — 기준 방향을 반영한 비교
inline bool hotspotHotter(HotspotCriterion c, double a, double b) {
    return hotspotCriterionIsMin(c) ? (a < b) : (a > b);
}

/// 심각도 — 뜨거운 방향으로 양수화한 값. 가중 중심 계산에 쓴다.
/// (σ3 = −500 → 500, σ3 = +20 → −20). 부호가 반대인 요소는 호출부가 0 으로 클램프한다.
inline double hotspotSeverity(HotspotCriterion c, double v) {
    return hotspotCriterionIsMin(c) ? -v : v;
}

/// 기준에 짝이 되는 변형률 측도 이름 (JSON `strain_measure`)
const char* hotspotStrainMeasureName(HotspotCriterion c);

/// 요소 값 배열의 '미기록' 표식. 🔴 음수 표식(−DBL_MAX)을 쓰면 안 된다 —
/// σ1·σ3 은 정상값이 음수일 수 있어 `v < 0` 검사가 요소를 통째로 버린다.
inline double hotspotUnrecorded() { return std::numeric_limits<double>::quiet_NaN(); }
inline bool hotspotIsUnrecorded(double v) { return std::isnan(v); }

/**
 * @brief 핫스팟 군집 분석 설정
 *
 * 계획: docs/hotspot-cluster-plan.md
 */
struct HotspotClusterConfig {
    bool enabled = false;

    /// 파트별 상위 백분위 (%) — 이 비율의 요소만 군집 대상
    double top_percent = 5.0;

    /// 거리 임계값 = distance_factor × 파트 대표 요소 크기
    double distance_factor = 1.5;

    /// 이 개수 미만의 덩어리는 노이즈로 버린다
    int min_cluster_elements = 5;

    /// 선별 기준량 (한 번 호출에 하나). 여러 기준은 호출부가 돌린다.
    HotspotCriterion criterion = HotspotCriterion::VonMises;

    /// 파트당 보고할 최대 덩어리 수 (0 = 무제한)
    int max_clusters_per_part = 20;
};

/**
 * @brief 핫스팟 덩어리 하나
 *
 * 모든 평균은 **부피 가중**이다. 요소 크기가 다를 때 산술평균은
 * 작은 요소를 과대평가한다 (메시가 조밀한 응력 집중부가 실제보다 크게 반영됨).
 */
struct HotspotCluster {
    int rank = 0;                       ///< 최대 응력 내림차순 순위 (1-based)
    int element_count = 0;

    double center[3] = {0, 0, 0};       ///< 응력×부피 가중 중심 (초기 형상 기준)
    double radius_enclosing = 0.0;      ///< 중심 → 구성 요소의 최원 절점 거리 (정확)
    double radius_rms = 0.0;            ///< 부피 가중 RMS 반경 (뭉침 정도)
    double volume = 0.0;                ///< 덩어리 총 부피

    double stress_mean = 0.0;           ///< 부피 가중 평균 (기준량 값, 부호 유지)
    double stress_max = 0.0;            ///< 뜨거운 방향의 극값 — σ3 기준이면 **최솟값**

    bool strain_available = false;      ///< 덱에 변형률 텐서가 없으면 false
    double strain_mean = 0.0;           ///< 부피 가중 평균 (기준에 짝인 변형률 측도)
    double strain_max = 0.0;            ///< 뜨거운 방향의 극값 (σ3 기준이면 ε3 최솟값)

    int32_t peak_element_id = 0;        ///< 최대 응력 요소 (사용자 ID)
    double peak_time = 0.0;             ///< 그 최대가 발생한 시각
};

/**
 * @brief 파트 하나의 핫스팟 군집 결과
 */
struct PartHotspotResult {
    int32_t part_id = 0;
    std::string part_name;

    std::string criterion;              ///< 선별 기준량 이름 (hotspotCriterionName)
    std::string direction;              ///< "max" | "min" — stress_max/threshold 의 방향
    std::string strain_measure;         ///< "equivalent" | "max_principal" | "min_principal"
    double top_percent = 0.0;
    double threshold_value = 0.0;       ///< 상위 백분위 컷 값. max 방향이면 이 이상, min 방향이면 이 이하가 선별

    double element_size_ref = 0.0;      ///< 파트 대표 요소 크기 (부피 중앙값의 세제곱근)
    double distance_threshold = 0.0;    ///< 실제 적용된 거리 임계값

    int element_count_total = 0;        ///< 파트의 전체 솔리드 요소 수
    int element_count_selected = 0;     ///< 상위 백분위로 선별된 요소 수
    int element_count_clustered = 0;    ///< 최소 크기 필터 통과 후 덩어리에 속한 요소 수

    bool strain_available = false;

    std::vector<HotspotCluster> clusters;
};

// ────────────────────────────────────────────────────────────────
// 기하 계산 (공개 — 단위 시험 대상)
// ────────────────────────────────────────────────────────────────

/**
 * @brief 8절점 솔리드의 부피와 도심을 등매개 사상으로 정확히 계산
 *
 * 부피와 도심의 정의는 다음과 같다.
 * @code
 *   V = ∫∫∫ det(J) dξ dη dζ            over [-1,1]^3
 *   c = (1/V) ∫∫∫ x(ξ,η,ζ) det(J) dξ dη dζ
 * @endcode
 *
 * 3선형(trilinear) 육면체에서 det(J) 는 ξ,η,ζ 각각에 대해 2차,
 * x·det(J) 는 3차이므로 **2×2×2 가우스 구적으로 정확하다**
 * (n점 가우스는 2n−1 차까지 정확).
 *
 * 🔴 5-사면체 분해(`computeSolidVolume`)는 면이 뒤틀린 육면체에서 근사다.
 *    솔버가 쓰는 요소 정의는 등매개 사상이므로 이쪽이 옳다.
 *
 * LS-DYNA 는 tet/wedge/pyramid 를 절점이 겹친 hex8 로 싣는다. 절점이 겹쳐도
 * det(J) 는 여전히 각 변수에 대해 2차 다항식이므로 같은 구적이 그대로 성립한다
 * — 축퇴 유형별 분기가 필요 없다.
 *
 * @param p       8개 절점 좌표 (LS-DYNA hex8 순서)
 * @param volume  [out] 부호 있는 부피. 뒤집힌 요소면 음수
 * @param cx,cy,cz [out] 도심
 * @return 부피의 절댓값이 유효(> 0)하면 true
 */
bool computeSolidVolumeAndCentroid(const Node* p,
                                   double& volume,
                                   double& cx, double& cy, double& cz);

/**
 * @brief 3선형 육면체의 부피 — 등매개 2×2×2 가우스 (좌표만 받는 저수준 판)
 *
 * 축퇴 판정(고유 절점 수)은 하지 않는다. 호출부가 4고유(tet)를 걸러낸 뒤
 * 5/6/7/8 고유에 대해서만 부를 것.
 *
 * `computeSolidVolumeAndCentroid` 와 동일한 구적을 공유하므로 두 경로가
 * 서로 다른 부피를 내는 일이 없다.
 *
 * @param xyz 8개 절점 좌표 (LS-DYNA hex8 순서), [i][0..2] = x,y,z
 * @return 부호 있는 부피
 */
double isoparametricHexVolume(const double xyz[8][3]);

/**
 * @brief 대칭 2계 텐서의 등가(von Mises) 값
 *
 * 응력: σ_eq = sqrt( 0.5·[(σxx−σyy)² + (σyy−σzz)² + (σzz−σxx)²] + 3·(σxy²+σyz²+σzx²) )
 *
 * 변형률에 같은 식을 쓰면 공학전단(γ)/텐서전단(ε) 규약 차이로 값이 달라진다.
 * d3plot 의 변형률 성분은 **텐서 성분**이므로 등가변형률은 다음을 쓴다.
 * @code
 *   ε_eq = sqrt( (2/3) · e'_ij e'_ij )
 *   e'_ij e'_ij = e'xx² + e'yy² + e'zz² + 2·(exy² + eyz² + ezx²)
 * @endcode
 * 여기서 e' 는 편차 성분(e_ij − δ_ij·tr(e)/3). 단축 인장(비압축)에서
 * ε_eq = ε_axial 이 되도록 하는 표준 정의다.
 */
double equivalentStress(double xx, double yy, double zz,
                        double xy, double yz, double zx);
double equivalentStrain(double xx, double yy, double zz,
                        double xy, double yz, double zx);

// ────────────────────────────────────────────────────────────────
// 군집화 (공개 — 단위 시험 대상)
// ────────────────────────────────────────────────────────────────

/**
 * @brief 요소 하나의 군집 입력
 */
struct ClusterElement {
    int32_t element_id = 0;    ///< 사용자 ID
    size_t  element_idx = 0;   ///< 메시 내부 인덱스 (절점 조회용)
    double  x = 0, y = 0, z = 0;
    double  volume = 0.0;
    double  value = 0.0;       ///< 선별 기준량의 시간축 극값 (부호 유지)
    double  peak_time = 0.0;
    double  strain = 0.0;
    bool    has_strain = false;
};

/**
 * @brief 거리 임계값 기반 단일 연결 군집화
 *
 * 요소 중심 간 거리가 @p threshold 이내면 같은 덩어리로 묶는다.
 * 균일 공간 격자(cell = threshold)로 이웃을 찾고 Union-Find 로 병합하므로
 * 기대 시간 복잡도는 O(n) 이다 — 전쌍 비교(O(n²))를 쓰지 않는다.
 *
 * @return 요소별 군집 라벨. 같은 값이면 같은 덩어리
 */
std::vector<int> clusterByDistance(const std::vector<ClusterElement>& elems,
                                   double threshold);

/**
 * @brief 파트 대표 요소 크기
 *
 * 부피 **중앙값**의 세제곱근을 쓴다. 평균은 소수의 큰 요소에 끌려가므로
 * 임계 거리가 과대해져 서로 다른 덩어리가 하나로 붙는다.
 *
 * @return 유효한 부피가 없으면 0
 */
double representativeElementSize(std::vector<double> volumes);

// ────────────────────────────────────────────────────────────────
// 최상위 진입점
// ────────────────────────────────────────────────────────────────

/**
 * @brief 파트별 핫스팟 군집 계산
 *
 * @param mesh          메시 (초기 형상 기준으로 도심을 낸다 — 계획서 §5)
 * @param elem_max_vm   요소별 기준량의 시간축 극값 (cfg.criterion 기준). 크기 = 솔리드 요소 수.
 *                      NaN(`hotspotUnrecorded()`) 은 '미기록' 이므로 제외한다.
 *                      🔴 음수는 정상값이다 — σ1·σ3 에서 걸러내면 안 된다.
 * @param elem_max_time 그 극값이 난 시각 (크기 같음, 비어 있으면 0 으로 본다)
 * @param elem_strain   같은 시점의 짝 변형률 (VM→등가, σ1→ε1, σ3→ε3. 비어 있으면 미보고)
 * @param part_names    파트 ID → 이름 (없으면 빈 이름)
 * @param cfg           설정
 *
 * 🔴 요소 연결성(`Element::node_ids`)에 든 값은 **사용자 절점 ID 가 아니라
 *    LS-DYNA 내부 1-based 인덱스**다. 반드시 `mesh.nodes[node_ids[n] - 1]` 로
 *    변환한다. `real_node_ids` 역맵을 쓰면 그 배열이 비항등인 덱에서
 *    요소가 통째로 사라진다(실덱 실측 2.2%).
 */
std::vector<PartHotspotResult> computeHotspotClusters(
    const data::Mesh& mesh,
    const std::vector<double>& elem_max_vm,
    const std::vector<double>& elem_max_time,
    const std::vector<double>& elem_strain,
    const std::map<int32_t, std::string>& part_names,
    const HotspotClusterConfig& cfg);

}  // namespace analysis
}  // namespace kood3plot
