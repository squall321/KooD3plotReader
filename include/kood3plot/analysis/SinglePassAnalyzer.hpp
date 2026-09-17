/**
 * @file SinglePassAnalyzer.hpp
 * @brief High-performance single-pass analysis for d3plot files
 * @author KooD3plot Development Team
 * @date 2024-12-04
 *
 * This analyzer reads each state only once and performs all analyses
 * (stress, strain, surface stress) in a single pass, achieving ~47x
 * speedup compared to the naive multi-pass approach.
 *
 * Performance comparison:
 * - Multi-pass: ~46,624 state reads for 992 states, 23 parts
 * - Single-pass: 992 state reads (one per state)
 */

#pragma once

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/AnalysisResult.hpp"
#include "kood3plot/analysis/SurfaceExtractor.hpp"
#include "kood3plot/analysis/VectorMath.hpp"
#include "kood3plot/analysis/HotspotClusterAnalyzer.hpp"
#include <map>
#include <vector>
#include <unordered_map>
#include <functional>
#include <atomic>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace kood3plot {
namespace analysis {

// Forward declarations (defined in TimeHistoryAnalyzer.hpp)
struct SurfaceAnalysisSpec;
struct AnalysisConfig;

/**
 * @brief Thread-local statistics accumulator for a part
 */
struct PartStateStats {
    double stress_max = -std::numeric_limits<double>::max();
    double stress_min = std::numeric_limits<double>::max();
    double stress_sum = 0.0;
    int32_t stress_max_elem = 0;
    int32_t stress_min_elem = 0;
    size_t stress_count = 0;

    double strain_max = -std::numeric_limits<double>::max();
    double strain_min = std::numeric_limits<double>::max();
    double strain_sum = 0.0;
    int32_t strain_max_elem = 0;
    size_t strain_count = 0;

    // Principal stress (computed from same stress tensor as von_mises)
    double max_principal_max = -std::numeric_limits<double>::max();
    double max_principal_min = std::numeric_limits<double>::max();
    double max_principal_sum = 0.0;
    int32_t max_principal_max_elem = 0;

    double min_principal_max = -std::numeric_limits<double>::max();  // most tensile σ3
    double min_principal_min = std::numeric_limits<double>::max();   // most compressive σ3
    double min_principal_sum = 0.0;
    int32_t min_principal_min_elem = 0;  // track most compressive

    size_t principal_count = 0;

    // Principal strain (only when ISTRN != 0 and strain tensor is available)
    double max_principal_strain_max = -std::numeric_limits<double>::max();
    double max_principal_strain_min = std::numeric_limits<double>::max();
    double max_principal_strain_sum = 0.0;
    int32_t max_principal_strain_max_elem = 0;

    double min_principal_strain_max = -std::numeric_limits<double>::max();
    double min_principal_strain_min = std::numeric_limits<double>::max();
    double min_principal_strain_sum = 0.0;
    int32_t min_principal_strain_min_elem = 0;

    size_t principal_strain_count = 0;

    // von Mises 등가 변형률. 응력용 vonMises() 와 공식이 다르다 —
    // 응력은 sqrt(3/2 · s:s), 변형률은 sqrt(2/3 · e_dev:e_dev).
    // 같은 함수를 쓰면 계수가 틀린다.
    double vm_strain_max = -std::numeric_limits<double>::max();
    double vm_strain_min = std::numeric_limits<double>::max();
    double vm_strain_sum = 0.0;
    int32_t vm_strain_max_elem = 0;

    void reset() {
        stress_max = -std::numeric_limits<double>::max();
        stress_min = std::numeric_limits<double>::max();
        stress_sum = 0.0;
        stress_max_elem = 0;
        stress_min_elem = 0;
        stress_count = 0;

        strain_max = -std::numeric_limits<double>::max();
        strain_min = std::numeric_limits<double>::max();
        strain_sum = 0.0;
        strain_max_elem = 0;
        strain_count = 0;

        max_principal_max = -std::numeric_limits<double>::max();
        max_principal_min = std::numeric_limits<double>::max();
        max_principal_sum = 0.0;
        max_principal_max_elem = 0;

        min_principal_max = -std::numeric_limits<double>::max();
        min_principal_min = std::numeric_limits<double>::max();
        min_principal_sum = 0.0;
        min_principal_min_elem = 0;

        principal_count = 0;

        vm_strain_max = -std::numeric_limits<double>::max();
        vm_strain_min = std::numeric_limits<double>::max();
        vm_strain_sum = 0.0;
        vm_strain_max_elem = 0;
        max_principal_strain_max = -std::numeric_limits<double>::max();
        max_principal_strain_min = std::numeric_limits<double>::max();
        max_principal_strain_sum = 0.0;
        max_principal_strain_max_elem = 0;

        min_principal_strain_max = -std::numeric_limits<double>::max();
        min_principal_strain_min = std::numeric_limits<double>::max();
        min_principal_strain_sum = 0.0;
        min_principal_strain_min_elem = 0;

        principal_strain_count = 0;
    }

    void merge(const PartStateStats& other) {
        if (other.stress_max > stress_max) {
            stress_max = other.stress_max;
            stress_max_elem = other.stress_max_elem;
        }
        if (other.stress_min < stress_min) {
            stress_min = other.stress_min;
            stress_min_elem = other.stress_min_elem;
        }
        stress_sum += other.stress_sum;
        stress_count += other.stress_count;

        if (other.strain_max > strain_max) {
            strain_max = other.strain_max;
            strain_max_elem = other.strain_max_elem;
        }
        if (other.strain_min < strain_min) {
            strain_min = other.strain_min;
        }
        strain_sum += other.strain_sum;
        strain_count += other.strain_count;

        if (other.max_principal_max > max_principal_max) {
            max_principal_max = other.max_principal_max;
            max_principal_max_elem = other.max_principal_max_elem;
        }
        if (other.max_principal_min < max_principal_min) {
            max_principal_min = other.max_principal_min;
        }
        max_principal_sum += other.max_principal_sum;

        if (other.min_principal_min < min_principal_min) {
            min_principal_min = other.min_principal_min;
            min_principal_min_elem = other.min_principal_min_elem;
        }
        if (other.min_principal_max > min_principal_max) {
            min_principal_max = other.min_principal_max;
        }
        min_principal_sum += other.min_principal_sum;

        principal_count += other.principal_count;

        // von Mises 등가 변형률 — 병합에서 빠지면 초기값(-DBL_MAX)이 그대로
        // 결과로 나간다. 실제로 그렇게 나와서 잡았다.
        if (other.vm_strain_max > vm_strain_max) {
            vm_strain_max = other.vm_strain_max;
            vm_strain_max_elem = other.vm_strain_max_elem;
        }
        if (other.vm_strain_min < vm_strain_min) {
            vm_strain_min = other.vm_strain_min;
        }
        vm_strain_sum += other.vm_strain_sum;

        if (other.max_principal_strain_max > max_principal_strain_max) {
            max_principal_strain_max = other.max_principal_strain_max;
            max_principal_strain_max_elem = other.max_principal_strain_max_elem;
        }
        if (other.max_principal_strain_min < max_principal_strain_min) {
            max_principal_strain_min = other.max_principal_strain_min;
        }
        max_principal_strain_sum += other.max_principal_strain_sum;

        if (other.min_principal_strain_min < min_principal_strain_min) {
            min_principal_strain_min = other.min_principal_strain_min;
            min_principal_strain_min_elem = other.min_principal_strain_min_elem;
        }
        if (other.min_principal_strain_max > min_principal_strain_max) {
            min_principal_strain_max = other.min_principal_strain_max;
        }
        min_principal_strain_sum += other.min_principal_strain_sum;

        principal_strain_count += other.principal_strain_count;
    }
};

/**
 * @brief Progress callback type
 */
using SinglePassProgressCallback = std::function<void(
    size_t current_state,
    size_t total_states,
    const std::string& message
)>;

/**
 * @brief High-performance single-pass analyzer
 *
 * Reads each state only once and performs all analyses simultaneously.
 * Uses OpenMP for parallel processing of elements within each state.
 */
class SinglePassAnalyzer {
public:
    /**
     * @brief Constructor
     * @param reader D3plotReader reference (must be opened)
     */
    explicit SinglePassAnalyzer(D3plotReader& reader);

    /**
     * @brief Destructor
     */
    ~SinglePassAnalyzer() = default;

    /**
     * @brief Run complete analysis in single pass (auto-selects best method)
     * @param config Analysis configuration
     * @return AnalysisResult containing all data
     */
    AnalysisResult analyze(const AnalysisConfig& config);

    /**
     * @brief Run analysis with progress callback (auto-selects best method)
     * @param config Analysis configuration
     * @param callback Progress callback
     * @return AnalysisResult containing all data
     */
    AnalysisResult analyze(const AnalysisConfig& config,
                           SinglePassProgressCallback callback);

    /**
     * @brief Run analysis with state-level parallelization (optimized)
     *
     * This method parallelizes the outer state loop instead of the inner
     * element loop, reducing OpenMP overhead from O(num_states) to O(1).
     *
     * Performance: ~2-4x faster than element-level parallelization for
     * large numbers of states (>100) with many parts.
     *
     * @param config Analysis configuration
     * @return AnalysisResult containing all data
     */
    AnalysisResult analyzeParallel(const AnalysisConfig& config);

    /**
     * @brief Run analysis with state-level parallelization with callback
     * @param config Analysis configuration
     * @param callback Progress callback
     * @return AnalysisResult containing all data
     */
    AnalysisResult analyzeParallel(const AnalysisConfig& config,
                                   SinglePassProgressCallback callback);

    /**
     * @brief Run analysis with pre-loaded states (no redundant file I/O)
     * @param config Analysis configuration
     * @param all_states Pre-loaded state data
     * @param callback Progress callback (optional)
     * @return AnalysisResult containing all data
     */
    AnalysisResult analyzeWithStates(const AnalysisConfig& config,
                                     const std::vector<data::StateData>& all_states,
                                     SinglePassProgressCallback callback = nullptr);

    /**
     * @brief Run analysis with element-level parallelization (legacy)
     *
     * This is the original implementation that parallelizes the inner
     * element loop. Kept for compatibility and comparison purposes.
     *
     * @param config Analysis configuration
     * @return AnalysisResult containing all data
     */
    AnalysisResult analyzeLegacy(const AnalysisConfig& config);

    /// 요소별 시간축 극값 (accumulateElementExtremes 결과), 기준별.
    /// 값이 NaN 인 항목은 '미기록' 이다 — 0 이나 음수와 구분해야 한다.
    /// 요청하지 않은 기준이면 빈 배열들이 든 정적 객체를 돌려준다.
    const ElementExtremes& elementExtremes(HotspotCriterion c) const;   // 솔리드
    const ElementExtremes& elementExtremes(HotspotElementKind k, HotspotCriterion c) const;
    using ExtremesKey = std::pair<HotspotElementKind, HotspotCriterion>;
    const std::map<ExtremesKey, ElementExtremes>& allElementExtremes() const { return elem_extremes_; }

    /// 셸 요소별 초기 두께 (첫 상태의 두께 워드, IOSHL(4)). 없으면 비움.
    const std::vector<double>& shellThickness() const { return shell_thickness_; }

    /// 요소별 누적 소성일 밀도 w_p = ∫σ_vm dε_p [응력 단위 = 에너지/부피].
    /// 기준량(criterion)과 무관한 양이라 요소 종류별로 하나만 둔다.
    /// 비어 있으면 미계산 — 0 으로 채우지 않는다(계산 못 함과 진짜 0 을 구분).
    const std::vector<double>& plasticWorkDensity(HotspotElementKind k) const;

    /// 요소별 유효소성변형률 ε_p 의 **이력 최댓값** [무차원].
    /// 소성역 절대량(항복을 넘은 요소 수·부피)의 재료다. 클러스터 선별(top_percent)과
    /// 무관하게 파트 전체를 대상으로 집계해야 물리량이 된다.
    /// 비어 있으면 미계산 — 0 으로 채우지 않는다.
    ///
    /// 마지막 프레임이 아니라 이력 최댓값을 쓴다. ε_p 가 이론상 단조라지만 실덱에서
    /// 감소하는 전이를 확인했다 (docs/hotspot_envelope_3d/context-notes.md).
    const std::vector<double>& plasticStrainMax(HotspotElementKind k) const;

    /// 덩어리별 `max_t(mean_e)` — 매 시각 가중평균을 구하고 그 시간축 극값.
    ///
    /// 기본 보고값 `stress_mean` 은 `mean_e(max_t)` 라 서로 다른 시각의 피크를
    /// 한 덩어리로 합성한다(항상 과대평가 쪽). 이쪽은 같은 시각에 실제로 걸린
    /// 하중이다. 상태를 한 번 더 훑으므로 2패스다.
    ///
    /// @param all_states  1패스와 같은 상태 배열
    /// @param kind        요소 종류
    /// @param crit        기준량 (min 방향이면 시간축 최소를 찾는다)
    /// @param members     덩어리별 (요소 인덱스, 가중 측도) — HotspotCluster 의 member_*
    /// @param out_value   [출력] 덩어리별 극값. 구하지 못하면 NaN
    /// @param out_time    [출력] 그 극값이 난 시각
    ///
    /// 상태 루프는 **한 번만** 돈다 — 덩어리마다 따로 훑지 않는다.
    void clusterTimeAggregate(
        const std::vector<data::StateData>& all_states,
        HotspotElementKind kind,
        HotspotCriterion crit,
        const std::vector<std::pair<std::vector<size_t>, std::vector<double>>>& members,
        std::vector<double>& out_value,
        std::vector<double>& out_time) const;
    /// 셸 계열 층 번호 해석 — "mid_inner_outer" | "index"
    const std::string& layerScheme() const { return layer_scheme_; }

    /// 설정의 이름 목록 → 기준 목록. 모르는 이름은 경고, 전부 무효면 von_mises 폴백.
    /// 같은 설정을 여러 곳에서 해석하므로 경고는 한 곳(누적 패스)에서만 낸다 — @p warn.
    static std::vector<HotspotCriterion> resolveHotspotCriteria(const std::vector<std::string>& names,
                                                                bool warn = true);


    /**
     * @brief Run analysis with element-level parallelization with callback
     * @param config Analysis configuration
     * @param callback Progress callback
     * @return AnalysisResult containing all data
     */
    AnalysisResult analyzeLegacy(const AnalysisConfig& config,
                                 SinglePassProgressCallback callback);

    /**
     * @brief Set whether to use state-level parallelization by default
     * @param enable true to use state-level (new), false for element-level (legacy)
     */
    void setUseStateLevelParallel(bool enable) { use_state_level_parallel_ = enable; }

    /**
     * @brief Check if state-level parallelization is enabled
     */
    bool isStateLevelParallel() const { return use_state_level_parallel_; }

    /**
     * @brief Get last error message
     */
    const std::string& getLastError() const { return last_error_; }

    /**
     * @brief Check if analysis was successful
     */
    bool wasSuccessful() const { return success_; }

    /// 침식(요소 삭제) 요약 — 통계에서 제외한 요소가 있었다는 사실을 호출부가 알린다.
    /// 삭제가 없으면 count 는 0, 시각은 NaN.
    struct ErosionSummary {
        size_t max_deleted_solids = 0;  ///< 한 상태에서 삭제된 solid 최대 개수
        double first_time = std::numeric_limits<double>::quiet_NaN();  ///< 첫 삭제가 나온 시각
        size_t first_state = 0;         ///< 첫 삭제가 나온 상태 번호 (0-based)
    };
    const ErosionSummary& erosionSummary() const { return erosion_; }

private:
    D3plotReader& reader_;
    std::string last_error_;
    bool success_ = false;
    bool use_state_level_parallel_ = true;  // Default to optimized state-level parallelization

    // Geometry data (read once)
    data::Mesh mesh_;
    int32_t nv3d_ = 0;  // Values per solid element
    size_t num_solid_elements_ = 0;
    size_t num_states_ = 0;  // Number of states (set after read_all_states)
    bool has_strain_tensor_ = false;  // true when ISTRN != 0 and nv3d >= 13

    // Element to part mapping
    std::vector<int32_t> elem_to_part_;  // elem_index -> part_id
    std::unordered_map<int32_t, size_t> elem_id_to_index_;

    ErosionSummary erosion_;  ///< 침식 요약 (recordErosionSummary 가 채운다)

    // ── 요소별 시간축 극값 (핫스팟 군집용), 기준별 ──
    // elem_index -> 값. config.hotspot_enabled 일 때만 채워진다.
    // 🔴 미기록/범위밖은 NaN. 0 으로 두면 '응력 0' 과, 음수로 두면 σ1·σ3 의
    //    정상 음수값과 구분이 안 된다.
    std::map<ExtremesKey, ElementExtremes> elem_extremes_;

    // ── 셸·두꺼운 셸 (핫스팟 군집용 제어값, ls-dyna_database.txt 1918–2075) ──
    size_t  num_shell_elements_ = 0;     ///< NEL4
    size_t  num_tshell_elements_ = 0;    ///< NELT
    int32_t nv2d_ = 0, nv3dt_ = 0;
    int32_t maxint_ = 0, neips_ = 0, ndim_ = 0, numds_ = 0;
    int32_t ioshl_[4] = {0, 0, 0, 0};
    std::vector<double> shell_thickness_;
    /// 요소 종류별 누적 소성일 밀도 (위 plasticWorkDensity 참조)
    std::map<HotspotElementKind, std::vector<double>> elem_plastic_work_;
    /// 요소별 ε_p 이력 최댓값. 소성역 절대량(n_yield/vol_yield/max_eps)의 재료.
    /// 소성일과 달리 상태가 1개뿐인 덱에서도 채워진다.
    std::map<HotspotElementKind, std::vector<double>> elem_eps_max_;
    std::string layer_scheme_;

    // Part information
    std::vector<int32_t> part_ids_;  // Unique part IDs
    std::unordered_map<int32_t, size_t> part_id_to_result_index_;

    // Surface data (for surface stress analysis)
    std::vector<std::vector<Face>> surface_faces_;  // Per surface spec
    std::vector<SurfaceAnalysisSpec> surface_specs_;

    // Results storage
    std::vector<PartTimeSeriesStats> stress_results_;
    std::vector<PartTimeSeriesStats> strain_results_;
    std::vector<PartTimeSeriesStats> max_principal_results_;
    std::vector<PartTimeSeriesStats> min_principal_results_;
    std::vector<PartTimeSeriesStats> vm_strain_results_;
    std::vector<PartTimeSeriesStats> max_principal_strain_results_;
    std::vector<PartTimeSeriesStats> min_principal_strain_results_;
    std::vector<SurfaceAnalysisStats> surface_results_;

    // ========================================
    // Initialization
    // ========================================

    /**
     * @brief Initialize analyzer (read mesh, build mappings)
     */
    bool initialize(const AnalysisConfig& config);

    /**
     * @brief Build element to part mapping
     */
    void buildElementMapping();

    /**
     * @brief Initialize result storage
     */
    void initializeResults(size_t num_states, const AnalysisConfig& config);

    /**
     * @brief Extract surfaces for surface stress analysis
     */
    void extractSurfaces(const AnalysisConfig& config);

    // ========================================
    // Single-pass analysis
    // ========================================

    /**
     * @brief Process a single state (all analyses)
     * @param state_idx State index
     * @param state State data
     * @param config Analysis configuration
     */
    void processState(size_t state_idx,
                      const data::StateData& state,
                      const AnalysisConfig& config);

    /**
     * @brief Analyze all parts for stress/strain (OpenMP element-level parallel - legacy)
     */
    void analyzePartStats(size_t state_idx,
                          const data::StateData& state,
                          bool analyze_stress,
                          bool analyze_strain);

    /**
     * @brief Analyze all parts for stress/strain (sequential - for state-level parallel)
     */
    void analyzePartStatsSequential(size_t state_idx,
                                    const data::StateData& state,
                                    bool analyze_stress,
                                    bool analyze_strain);

    /**
     * @brief Analyze surface stress for all surface specs (OpenMP element-level parallel - legacy)
     */
    void analyzeSurfaceStats(size_t state_idx,
                             const data::StateData& state);

    /**
     * @brief Analyze surface stress for all surface specs (sequential - for state-level parallel)
     */
    void analyzeSurfaceStatsSequential(size_t state_idx,
                                       const data::StateData& state);

    /// 이 상태에 살아 있는 요소가 하나도 없는 파트(전량 침식)의 시점을 NaN 으로 표시한다.
    /// 0 이나 ±DBL_MAX 로 위장하지 않는다 — JSON 에는 null 로 나간다.
    void markUnmeasuredParts(size_t state_idx,
                             const std::vector<PartStateStats>& part_stats,
                             bool analyze_stress,
                             bool analyze_strain);

    /// 상태 배열을 훑어 침식 요약을 채운다 (통계 제외 사실을 남기기 위한 것).
    void recordErosionSummary(const std::vector<data::StateData>& all_states);

    // ========================================
    // Stress/Strain extraction
    // ========================================

    /**
     * @brief Extract Von Mises stress for an element
     */
    double extractVonMises(const std::vector<double>& solid_data, size_t elem_idx);

    /**
     * @brief Extract effective plastic strain for an element
     */
    double extractEffPlasticStrain(const std::vector<double>& solid_data, size_t elem_idx);

    /**
     * @brief Extract stress tensor for an element
     */
    StressTensor extractStressTensor(const std::vector<double>& solid_data, size_t elem_idx);

    /**
     * @brief Extract strain tensor for an element (only when has_strain_tensor_)
     * @note Uses StressTensor struct for eigenvalue computation (same math for any symmetric 3x3 tensor)
     */
    StressTensor extractStrainTensor(const std::vector<double>& solid_data, size_t elem_idx);

    /// von Mises 등가 변형률 ε_eq = sqrt(2/3 · e_dev:e_dev)
    static double vonMisesStrainOf(const StressTensor& e) {
        const double em = (e.xx + e.yy + e.zz) / 3.0;
        const double dxx = e.xx - em, dyy = e.yy - em, dzz = e.zz - em;
        return std::sqrt(2.0 / 3.0 * (dxx * dxx + dyy * dyy + dzz * dzz +
                                      2.0 * (e.xy * e.xy + e.yz * e.yz + e.zx * e.zx)));
    }


    // ========================================
    // Peak element tensor extraction
    // ========================================

    /**
     * @brief Extract full tensor history for peak elements (per-part)
     *
     * Identifies elements with peak von Mises, σ1, σ3 per part and
     * extracts their full 6-component stress tensor history from all states.
     */
    void extractPeakElementTensors(
        const std::vector<data::StateData>& all_states,
        AnalysisResult& result);

    /**
     * @brief 요소별 시간축 극값 누적 (2차 경량 패스), 요청한 기준 전부
     *
     * extractPeakElementTensors 와 같은 방식 — buildResult 이후 all_states 를
     * 다시 훑는다. 🔴 상태 루프 안에서 누적하면 안 된다. 기본 경로가
     * `#pragma omp parallel for` 를 **상태 루프**에 걸고 있어(cpp:91, cpp:184)
     * 여러 상태가 같은 elem_idx 를 동시에 갱신하면 데이터 경쟁이 된다.
     * 여기서는 **elem_idx 로 병렬화**하고 상태를 안쪽에서 돌므로
     * 각 스레드가 자기 요소만 써서 경쟁이 원천적으로 없다.
     *
     * 기준별 극값 방향: von Mises·σ1 은 max, σ3 은 **min**.
     * 주응력은 σ1·σ3 중 하나라도 요청됐을 때 (요소,상태)당 **한 번만** 분해한다.
     * 짝 변형률: VM→등가변형률, σ1→ε1, σ3→ε3 — 모두 극값이 난 시각의 값.
     */
    void accumulateElementExtremes(const std::vector<data::StateData>& all_states,
                                   const std::vector<HotspotCriterion>& criteria);

    /**
     * @brief 셸·두꺼운 셸의 요소별 시간축 극값 — 적분점 층 중 가장 뜨거운 층
     *
     * 층 k 의 응력은 요소 시작 + k·P (P = 6·IOSHL(1)+IOSHL(2)+NEIPS).
     * 굽힘 최대는 표면 층이라 중립면만 보면 놓친다. 층 순서 해석에 결과가 좌우되지 않는다.
     *
     * 🔴 배치를 규격 공식으로 자기 검증한다. NV2D/NV3DT 가 공식과 맞지 않으면
     *    추측해서 읽지 않고 건너뛴다(틀린 오프셋은 그럴듯한 숫자를 조용히 낸다).
     */
    void accumulateLayeredExtremes(const std::vector<data::StateData>& all_states,
                                   const std::vector<HotspotCriterion>& criteria,
                                   HotspotElementKind kind);

    // ========================================
    // Result finalization
    // ========================================

    /**
     * @brief Build final AnalysisResult from accumulated data
     */
    AnalysisResult buildResult(const AnalysisConfig& config);

    /**
     * @brief Fill metadata in result
     */
    void fillMetadata(AnalysisResult& result, const AnalysisConfig& config);
};

} // namespace analysis
} // namespace kood3plot
