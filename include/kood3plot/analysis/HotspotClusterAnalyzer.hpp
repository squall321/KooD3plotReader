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
    /// 최대 전단 응력 τ_max = (σ1 − σ3)/2. 볼 전단처럼 전단으로 깨지는
    /// 메커니즘은 von Mises 로 보이지 않는다 (정수압 성분에 가려진다).
    /// 주응력에서 유도하므로 좌표계에 무관한 불변량이다.
    MaxShear = 3,
    /// 축별 수직응력 σxx / σyy / σzz. 보드 굽힘처럼 **방향이 정해진** 인장으로
    /// 깨지는 메커니즘용이다. 주응력은 방향을 잃어버려 "어느 축으로 당겨졌나" 를
    /// 답하지 못한다.
    ///
    /// 🔴 **전역 좌표계** 성분이다. d3plot 규격상 솔리드·셸 모두 응력은
    ///    "true stress in the global system" 으로 기록된다(요소 좌표계는 굽힘
    ///    모멘트 등 합력에만 해당). 다만 `*DATABASE_EXTENT_BINARY` 의 CMPFLG=1 로
    ///    재료 좌표계 출력을 켠 덱에서는 의미가 달라지는데, 이 리더는 CMPFLG 를
    ///    읽지 않으므로 **구분하지 못한다**. 그런 덱에서는 쓰지 말 것.
    XTension = 4,
    YTension = 5,
    ZTension = 6,
};

/// 기준량 슬롯 수. 요소별 극값 배열이 이 크기로 잡히지만, **요청된 기준만**
/// 실제로 할당된다(slot[k] == nullptr 이면 건너뜀). 새 기준을 enum 에 추가하면
/// 여기도 늘려야 한다 — 안 늘리면 test_capabilities 가 잡는다.
inline constexpr int kHotspotCritSlots = 7;

/// 군집 대상 요소 종류. 기하(부피/면적)와 대표 크기 정의가 다르다.
enum class HotspotElementKind {
    Solid = 0,        ///< 8절점 솔리드 (tet/wedge/pyramid 축퇴 포함)
    ThickShell = 1,   ///< 8절점 두꺼운 셸 — 적분점 층별 응력
    Shell = 2,        ///< 4절점 셸 (삼각형 축퇴 포함) — 적분점 층별 응력
};

/// 종류 → JSON `element_type` 이름 ("solid" / "thick_shell" / "shell")
const char* hotspotElementKindName(HotspotElementKind k);

/// 문자열 → 기준. "von_mises" / "max_principal" / "min_principal" (대소문자·'-' 무시).
/// 모르는 이름이면 false 를 돌려주고 @p out 은 건드리지 않는다.
bool parseHotspotCriterion(const std::string& name, HotspotCriterion& out);

/// 기준 → 정규 이름 (JSON `criterion` 필드에 쓰는 값)
const char* hotspotCriterionName(HotspotCriterion c);

/// 지원하는 기준 전체. **목록을 손으로 적지 않는다** — 이름과 파서를 왕복시켜
/// 유도한다(name → parse → 같은 값이면 지원). 그래서 enum 에 값만 추가하고
/// 이름이나 파서 배선을 빠뜨리면 그 항목은 목록에서 **빠진 채로 드러난다**.
/// `--capabilities` 가 이걸 쓰므로, 배선 누락이 조용히 숨지 않는다.
std::vector<HotspotCriterion> allHotspotCriteria();

/// 이름 목록 → 기준 목록. 순서 유지·중복 제거. 모르는 이름은 @p unknown 에 모은다.
/// 비어 있거나 전부 모르는 이름이면 **빈 벡터** — 폴백은 호출부가 정한다.
std::vector<HotspotCriterion> parseHotspotCriteria(const std::vector<std::string>& names,
                                                   std::vector<std::string>* unknown = nullptr);

/// 요소별 시간축 극값 묶음 (기준 하나분). 크기는 전부 솔리드 요소 수.
struct ElementExtremes {
    std::vector<double> value;   ///< 극값. NaN = 미기록
    std::vector<double> time;    ///< 그 극값이 난 시각
    std::vector<double> strain;  ///< 같은 시각의 짝 변형률. 비어 있으면 미보고
    /// 셸·두꺼운 셸: 극값이 난 적분점 층 (d3plot 저장 순서, 0부터). 솔리드는 비움.
    /// MAXINT=3·NUMDS≥0 이면 0=중립면, 1=안쪽 면, 2=바깥쪽 면.
    std::vector<int8_t> layer;
};

/// 뜨거운 방향이 '작은 값' 인 기준이면 true (현재 MinPrincipal 만)
inline bool hotspotCriterionIsMin(HotspotCriterion c) {
    // τ_max = (σ1−σ3)/2 는 정의상 ≥ 0 이고 클수록 위험하다 — max 방향.
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

    /// 소성역으로 셀 ε_p 임계. 기본 0 은 "0 보다 크면 소성" 이라는 뜻이다.
    /// d3plot 의 ε_p 는 이미 소성분만 담으므로 0 초과가 곧 항복 이후다.
    /// 수치 잡음을 걸러내려면 1e-6 같은 값을 준다.
    double yield_eps_threshold = 0.0;

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
    double volume = 0.0;                ///< 덩어리 총 부피 (셸은 면적×두께 — 두께가 있을 때만 유효)
    bool   has_area = false;            ///< 셸이면 true — area 를 출력한다
    double area = 0.0;                  ///< 셸: 덩어리 총 면적
    bool   volume_valid = true;         ///< false 면 volume 을 출력하지 않는다 (두께 없는 셸)

    double stress_mean = 0.0;           ///< 부피 가중 평균 (기준량 값, 부호 유지)
    double stress_max = 0.0;            ///< 뜨거운 방향의 극값 — σ3 기준이면 **최솟값**

    bool strain_available = false;      ///< 덱에 변형률 텐서가 없으면 false
    double strain_mean = 0.0;           ///< 부피 가중 평균 (기준에 짝인 변형률 측도)
    double strain_max = 0.0;            ///< 뜨거운 방향의 극값 (σ3 기준이면 ε3 최솟값)

    /// 소성일 w_p = ∫σ_vm dε_p 를 시간 적분한 값. 짧게 튄 탄성 응력은
    /// Δε_p = 0 이라 기여하지 않는다 — 실제 손상에 비례하는 리스크 척도.
    // ── 시간 집계 (2패스로 채움) ────────────────────────────────────
    // stress_mean 은 `mean_e(max_t)` 다 — 요소별 **시간축 극값**을 먼저 구하고
    // 공간 평균한다. 서로 다른 시각의 피크를 한 덩어리로 합성하므로, 실제로
    // 동시에 그만큼 버틴 적이 없는 상태다. 정의상 항상 과대평가 쪽이다.
    //
    // mean_timemax 는 `max_t(mean_e)` — 매 시각 덩어리 평균을 구하고 그 시간 극값.
    // 같은 시각에 실제로 걸린 하중이다. 항상 mean_timemax ≤ stress_mean 이다
    // (min 방향이면 부등호가 뒤집힌다 = 덜 극단적).
    bool   mean_timemax_available = false;
    double mean_timemax = 0.0;          ///< max_t( Σv_i(t)·V_i / ΣV_i )
    double mean_timemax_time = 0.0;     ///< 그 극값이 난 시각

    /// 2패스 시간집계용 구성 요소 — JSON 으로 내보내지 않는다 (크기).
    std::vector<size_t> member_idx;     ///< 해당 요소 종류 배열 내 인덱스
    std::vector<double> member_vol;     ///< 같은 순서의 가중 측도 (부피/면적×두께)

    bool   energy_available = false;    ///< false 면 적분 못 함 (출력에서 뺀다)
    double energy_total = 0.0;          ///< Σ w_p·V — 덩어리 총 소성일 [에너지]
    double energy_max = 0.0;            ///< 요소별 밀도 최댓값 [에너지/부피]
    double energy_mean = 0.0;           ///< 부피 가중 평균 밀도 [에너지/부피]

    int32_t peak_element_id = 0;        ///< 최대 응력 요소 (사용자 ID)
    double peak_time = 0.0;             ///< 그 최대가 발생한 시각
    int    peak_layer = -1;             ///< 셸·두꺼운 셸: 피크 요소의 극값 층. 솔리드 −1
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
    std::string element_type;           ///< "solid" | "thick_shell" | "shell"
    /// 평균·중심 가중에 쓴 측도: "volume" | "area_x_thickness" | "area"
    std::string weight_measure;
    /// 셸 층 번호 해석: "mid_inner_outer"(0 중립·1 안쪽·2 바깥쪽) | "index" | "" (솔리드)
    std::string layer_scheme;
    bool   bbox_valid = false;          ///< 파트 경계상자 (초기 형상, 파트 요소의 절점 기준)
    double bbox_min[3] = {0, 0, 0};
    double bbox_max[3] = {0, 0, 0};
    double top_percent = 0.0;
    double threshold_value = 0.0;       ///< 상위 백분위 컷 값. max 방향이면 이 이상, min 방향이면 이 이하가 선별
    /// 파트에서 가장 뜨거운 값 (선별 요소 중 극값). 컷값과 같으면 **평탄 분포** —
    /// 상위 X% 가 동률 속 임의 부분집합이라 '흩어진 핫스팟' 으로 읽으면 안 된다.
    bool   value_extreme_valid = false;
    double value_extreme = 0.0;
    /// 컷값과 같은 값(상대 1e-9)인데 선별되지 **못한** 요소 수. 0 보다 크면 선별 경계가
    /// 동률 속에서 요소 순번으로 임의로 갈렸다.
    int    cut_ties_unselected = 0;
    /// 선별 값이 전부 같고(극값 = 컷값) 경계 너머에도 같은 값이 있다 — 평탄 분포.
    /// 상위 선별 전체가 임의 부분집합이라 덩어리의 **위치·개수에 의미가 없다**.
    bool   uniform = false;

    double element_size_ref = 0.0;      ///< 파트 대표 요소 크기 (부피 중앙값의 세제곱근)
    double distance_threshold = 0.0;    ///< 실제 적용된 거리 임계값

    int element_count_total = 0;        ///< 파트의 전체 솔리드 요소 수
    int element_count_selected = 0;     ///< 상위 백분위로 선별된 요소 수
    int element_count_clustered = 0;    ///< 최소 크기 필터 통과 후 덩어리에 속한 요소 수

    bool strain_available = false;

    // ── 소성역 절대량 — top_percent 와 무관하다 ─────────────────────
    // 클러스터의 volume·energy_total 은 상위 top_percent **개수컷**으로 고른
    // 요소들만 합한 값이라 3%→5% 로 바꾸면 따라 변한다. 물리량이 아니다.
    // 판정에 필요한 건 "항복을 넘은 영역이 얼마나 넓은가" 이고, 그건 파트 전체를
    // 대상으로 세야 한다 (docs/postproc_gap_2026-09/plan.md §P1-1).
    //
    // ε_p 가 없는 덱에서는 plastic_zone_available = false 이고 나머지는 쓰지 않는다.
    bool   plastic_zone_available = false;
    double yield_eps_threshold = 0.0;   ///< ε_p 가 이 값을 넘으면 소성으로 센다
    int    n_yield = 0;                 ///< ε_p > 임계 인 요소 수 (파트 전체 기준)
    double vol_yield = 0.0;             ///< 그 요소들의 부피(셸이면 면적×두께) 합
    double vol_total = 0.0;             ///< 파트 전체 요소의 같은 측도 합
    double sum_eps_vol = 0.0;           ///< Σ ε_p·V — 소성 변형의 총량
    double max_eps = 0.0;               ///< 파트 전체 ε_p 이력 최댓값
    double plastic_work_total = 0.0;    ///< Σ w_p·V — 파트 전체 소성일 [에너지]
    bool   plastic_work_available = false;

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
 * @brief 4절점 셸의 면적과 도심 — 쌍선형 등매개 곡면
 *
 * @code
 *   A = ∫∫ |x_ξ × x_η| dξ dη            over [-1,1]^2
 *   c = (1/A) ∫∫ x(ξ,η) |x_ξ × x_η| dξ dη
 * @endcode
 *
 * 평면 사각형에서 |x_ξ × x_η| 는 ξ,η 에 대해 1차이고 x·|…| 는 각 변수 2차라
 * **2점 가우스로 정확하다**. 뒤틀린(비평면) 사각형은 피적분함수에 제곱근이 들어가
 * 다항식이 아니므로 정확한 구적이 없다 — 4점 가우스를 쓴다(수렴은 단위 시험에서 실측).
 *
 * 삼각형(LS-DYNA 는 4번 절점을 3번과 같게 싣는다)은 닫힌식으로 푼다.
 * 고유 절점 판정은 솔리드와 같이 절점 id 로 한다.
 *
 * @param p      4개 절점 (LS-DYNA shell 순서)
 * @param area   [out] 면적 (≥ 0)
 * @return 면적이 유효(> 0)하면 true
 */
bool computeShellAreaAndCentroid(const Node* p,
                                 double& area,
                                 double& cx, double& cy, double& cz);

/**
 * @brief 육면체의 세 쌍 대면(對面) 도심 간 거리 중 최소값
 *
 * 두꺼운 셸의 **면내 크기** 추정에 쓴다: `√(V / h_min)`.
 * 절점 순서(1-4 → 5-8 이 두께 방향이라는 가정)에 의존하지 않도록 세 방향 중 가장
 * 짧은 쪽을 두께로 본다. 정육면체에서는 √(a³/a) = a 로 ∛V 와 같다.
 */
double hexMinFaceSeparation(const Node* p);

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
    int     layer = -1;        ///< 셸·두꺼운 셸 극값 층
    double  area = 0.0;        ///< 셸 면적 (가중 volume 과 별도로 보고용)
    double  energy = 0.0;      ///< 누적 소성일 밀도 w_p = ∫σ_vm dε_p [에너지/부피]
    bool    has_energy = false;///< false 면 적분 못 함 — 0 으로 쓰지 않는다
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

/**
 * @brief 요소 종류별 핫스팟 군집 — 셸·두꺼운 셸 지원판
 *
 * | 종류 | 기하 | 가중 | 대표 크기 |
 * |---|---|---|---|
 * | Solid | 등매개 부피·도심 | 부피 | ∛(부피 중앙값) — 기존과 동일 |
 * | ThickShell | 등매개 부피·도심 | 부피 | 중앙값 √(V / h_min) — 면내 크기 |
 * | Shell | 쌍선형 곡면 면적·도심 | 면적×두께 (두께 없으면 면적) | √(면적 중앙값) |
 *
 * 🔴 얇은 요소에서 ∛V 를 쓰면 대표 크기가 면내 간격보다 작아져 거리 임계에 이웃이
 *    걸리지 않는다 → 덩어리가 전부 흩어져 최소 크기 필터에 다 걸린다. 셸 계열은 면내 크기를 쓴다.
 *
 * @param ex               요소별 극값 (value/time/strain/layer). 크기 = 해당 종류 요소 수
 * @param shell_thickness  Shell 전용 — 요소별 초기 두께. 비었거나 파트 안에 0 이하가 있으면
 *                         그 파트는 면적 가중으로 떨어진다(`weight_measure="area"`).
 * @param layer_scheme     셸 계열 층 번호 해석 ("mid_inner_outer" | "index")
 */
std::vector<PartHotspotResult> computeHotspotClusters(
    const data::Mesh& mesh,
    HotspotElementKind kind,
    const ElementExtremes& ex,
    const std::vector<double>& shell_thickness,
    const std::string& layer_scheme,
    const std::map<int32_t, std::string>& part_names,
    const HotspotClusterConfig& cfg,
    /// 요소별 누적 소성일 밀도. 비어 있으면 에너지 미계산으로 보고한다.
    /// 기준량과 무관한 양이라 ElementExtremes 와 따로 받는다(기준마다 복제 방지).
    const std::vector<double>& elem_energy = {},
    /// 요소별 ε_p 이력 최댓값. 비어 있으면 소성역 절대량을 보고하지 않는다.
    const std::vector<double>& elem_eps = {});

}  // namespace analysis
}  // namespace kood3plot
