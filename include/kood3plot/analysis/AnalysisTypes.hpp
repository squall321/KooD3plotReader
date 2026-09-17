/**
 * @file AnalysisTypes.hpp
 * @brief Extended type definitions for unified analysis system
 * @author KooD3plot Development Team
 * @date 2025-12-04
 *
 * Provides extended analysis types for the unified YAML configuration system.
 * Includes job-based analysis, motion analysis, and surface strain analysis.
 */

#pragma once

#include "kood3plot/analysis/VectorMath.hpp"
#include "kood3plot/analysis/AnalysisResult.hpp"
#include <array>
#include <string>
#include <vector>
#include <cstdint>
#include <limits>

namespace kood3plot {
namespace analysis {

// ============================================================
// Analysis Job Types
// ============================================================

/**
 * @brief Analysis job type enumeration
 */
enum class AnalysisJobType {
    VON_MISES,              ///< Von Mises stress analysis
    EFF_PLASTIC_STRAIN,     ///< Effective plastic strain analysis
    SURFACE_STRESS,         ///< Direction-based surface stress
    SURFACE_STRAIN,         ///< Direction-based surface strain
    PART_MOTION,            ///< Part motion analysis (displacement/velocity/acceleration)
    ELEMENT_QUALITY,        ///< Element quality metrics (aspect ratio, Jacobian, etc.)
    BEAM_FORCE,             ///< Beam resultants (axial force, shear, moment, torsion)
    COMPREHENSIVE           ///< Multiple quantities in one job
};

/**
 * @brief Convert job type to string
 */
inline std::string jobTypeToString(AnalysisJobType type) {
    switch (type) {
        case AnalysisJobType::VON_MISES: return "von_mises";
        case AnalysisJobType::EFF_PLASTIC_STRAIN: return "eff_plastic_strain";
        case AnalysisJobType::SURFACE_STRESS: return "surface_stress";
        case AnalysisJobType::SURFACE_STRAIN: return "surface_strain";
        case AnalysisJobType::BEAM_FORCE: return "beam_force";
        case AnalysisJobType::PART_MOTION: return "part_motion";
        case AnalysisJobType::ELEMENT_QUALITY: return "element_quality";
        case AnalysisJobType::COMPREHENSIVE: return "comprehensive";
        default: return "unknown";
    }
}

/**
 * @brief Parse job type from string
 */
inline AnalysisJobType parseJobType(const std::string& str) {
    if (str == "von_mises") return AnalysisJobType::VON_MISES;
    if (str == "eff_plastic_strain") return AnalysisJobType::EFF_PLASTIC_STRAIN;
    if (str == "surface_stress") return AnalysisJobType::SURFACE_STRESS;
    if (str == "surface_strain") return AnalysisJobType::SURFACE_STRAIN;
    if (str == "beam_force" || str == "beam") return AnalysisJobType::BEAM_FORCE;
    if (str == "part_motion") return AnalysisJobType::PART_MOTION;
    if (str == "element_quality") return AnalysisJobType::ELEMENT_QUALITY;
    if (str == "comprehensive") return AnalysisJobType::COMPREHENSIVE;
    return AnalysisJobType::VON_MISES; // default
}

// ============================================================
// Motion Analysis Data Structures
// ============================================================

/**
 * @brief Motion time point data (single state)
 */
struct MotionTimePoint {
    double time = 0.0;

    // Average values (center of mass motion)
    Vec3 avg_displacement{0, 0, 0};
    Vec3 avg_velocity{0, 0, 0};
    Vec3 avg_acceleration{0, 0, 0};

    // Maximum displacement
    double max_displacement_magnitude = 0.0;
    int32_t max_displacement_node_id = 0;

    // Displacement magnitudes
    double avg_displacement_magnitude = 0.0;
    double avg_velocity_magnitude = 0.0;
    double avg_acceleration_magnitude = 0.0;
};

/**
 * @brief Part motion statistics (time history)
 */
struct PartMotionStats {
    int32_t part_id = 0;
    std::string part_name;
    std::vector<MotionTimePoint> data;

    // Global statistics (computed after analysis)
    double peak_velocity_magnitude = 0.0;
    double peak_acceleration_magnitude = 0.0;
    double final_displacement_magnitude = 0.0;
    double max_displacement_magnitude = 0.0;

    /**
     * @brief Compute global statistics from time series data
     */
    void computeGlobalStats() {
        peak_velocity_magnitude = 0.0;
        peak_acceleration_magnitude = 0.0;
        max_displacement_magnitude = 0.0;

        for (const auto& point : data) {
            if (point.avg_velocity_magnitude > peak_velocity_magnitude) {
                peak_velocity_magnitude = point.avg_velocity_magnitude;
            }
            if (point.avg_acceleration_magnitude > peak_acceleration_magnitude) {
                peak_acceleration_magnitude = point.avg_acceleration_magnitude;
            }
            if (point.max_displacement_magnitude > max_displacement_magnitude) {
                max_displacement_magnitude = point.max_displacement_magnitude;
            }
        }

        if (!data.empty()) {
            final_displacement_magnitude = data.back().avg_displacement_magnitude;
        }
    }

    size_t size() const { return data.size(); }
    bool empty() const { return data.empty(); }
};

// ============================================================
// Surface Strain Data Structures
// ============================================================

/**
 * @brief Surface strain time point data
 */
struct SurfaceStrainTimePoint {
    double time = 0.0;

    // Normal strain statistics
    double normal_strain_max = 0.0;
    double normal_strain_min = 0.0;
    double normal_strain_avg = 0.0;
    int32_t normal_strain_max_element_id = 0;

    // Shear strain statistics
    double shear_strain_max = 0.0;
    double shear_strain_avg = 0.0;
    int32_t shear_strain_max_element_id = 0;

    // 최대 주변형률 ε1 (인장)
    double max_principal_strain_max = 0.0;
    double max_principal_strain_min = 0.0;
    double max_principal_strain_avg = 0.0;
    int32_t max_principal_strain_max_element_id = 0;

    // 최소 주변형률 ε3 (압축) — 최소값이 worst
    double min_principal_strain_max = 0.0;
    double min_principal_strain_min = 0.0;
    double min_principal_strain_avg = 0.0;
    int32_t min_principal_strain_min_element_id = 0;

    // von Mises 등가 변형률 ε_vm = sqrt(2/3·e_dev:e_dev)
    double vm_strain_max = 0.0;
    double vm_strain_min = 0.0;
    double vm_strain_avg = 0.0;
    int32_t vm_strain_max_element_id = 0;

    // 유효소성변형률 — 변형률 텐서와 **다른 양**이다. 예전 구현은 이 값을
    // normal_strain 자리에 넣고 0.577 배를 shear 라 불렀다(둘 다 오표기).
    // 이제 제 이름으로 분리해 싣는다. 텐서가 없어도 이 값은 항상 나온다.
    double eff_plastic_strain_max = 0.0;
    double eff_plastic_strain_min = 0.0;
    double eff_plastic_strain_avg = 0.0;
    int32_t eff_plastic_strain_max_element_id = 0;
};

/**
 * @brief Surface strain analysis statistics
 */
struct SurfaceStrainStats {
    std::string description;
    Vec3 reference_direction{0, 0, 0};
    double angle_threshold_degrees = 45.0;
    std::vector<int32_t> part_ids;
    int32_t num_faces = 0;
    std::vector<SurfaceStrainTimePoint> data;

    /// d3plot 에 변형률 텐서가 실려 있었는지 (*DATABASE_EXTENT_BINARY STRFLG).
    /// false 면 normal/shear/주변형률/ε_vm 은 전부 0 이고 eff_plastic 만 유효하다.
    bool has_strain_tensor = false;
    /// 텐서가 없을 때 그 이유. 보고서가 '0 이었음' 으로 오독하지 않도록 남긴다.
    std::string note;

    size_t size() const { return data.size(); }
    bool empty() const { return data.empty(); }

    /**
     * @brief Get global maximum normal strain
     */
    double globalMaxNormalStrain() const {
        double max_val = -std::numeric_limits<double>::infinity();
        for (const auto& tp : data) {
            if (tp.normal_strain_max > max_val) max_val = tp.normal_strain_max;
        }
        return max_val;
    }
};

// ============================================================
// Element Quality Data Structures
// ============================================================

/**
 * @brief Per-state element quality statistics for a part
 */
struct ElementQualityTimePoint {
    double time = 0.0;

    // Aspect ratio (max_edge / min_edge, ideal = 1.0).
    // aspect_measured=false 면 값이 없다 — 축퇴 요소뿐인 파트다.
    // 예전에는 축퇴 요소에 1e6 을 넣어서, tet 가 하나라도 섞이면 파트 전체가
    // "AR=1000000 > 10 → crit" 으로 찍혔다.
    bool aspect_measured = false;
    double aspect_ratio_max = 0.0;
    double aspect_ratio_avg = 0.0;
    int32_t worst_aspect_ratio_elem = 0;
    int32_t n_aspect_unavailable = 0;

    // Scaled Jacobian (정육면체=1.0, 찌그러질수록 0, 음수=뒤집힘).
    // jacobian_measured=false 면 아래 두 값은 의미 없다 — 셸 파트이거나
    // 솔리드가 전부 축퇴(tet/wedge 를 hex8 로 저장)라 정의되지 않은 경우다.
    // 예전에는 체적 부호 ±1 만 넣어 '완벽(1.0)' 으로 보였다.
    bool jacobian_measured = false;
    double jacobian_min = 1.0;
    double jacobian_avg = 1.0;
    int32_t worst_jacobian_elem = 0;
    int32_t n_jacobian_unavailable = 0;  ///< 축퇴로 scaled Jacobian 미정의인 요소 수

    // Warpage angle (degrees, ideal = 0) — **셸 전용 지표**.
    // Skewness (0 = ideal, 1 = degenerate) — 현재 구현은 셸 4절점 기준.
    // 솔리드만 있는 파트에서는 계산 자체를 안 하므로 measured=false 다.
    // 예전에는 플래그가 없어 기본값 0.0 이 그대로 나갔고, 보고서에서
    // '뒤틀림 0 · 왜곡도 0 = 완벽한 메시' 로 읽혔다 (실측 Test_006 은
    // 23 파트 전부 솔리드인데 두 지표가 전 스텝 0.00000 이었다).
    bool warpage_measured = false;
    double warpage_max = 0.0;
    double warpage_avg = 0.0;
    int32_t worst_warpage_elem = 0;

    bool skewness_measured = false;
    double skewness_max = 0.0;
    double skewness_avg = 0.0;
    int32_t worst_skewness_elem = 0;

    // Volume/area change from initial (ratio: 1.0 = no change).
    // 축퇴 솔리드는 hex 5-사면체 분해가 성립하지 않아 체적 자체가 못 믿을 값이다
    // → volume_measured=false 로 두고 값에 손대지 않는다.
    bool volume_measured = false;
    double volume_change_min = 1.0;   // most compressed
    double volume_change_max = 1.0;   // most expanded
    int32_t worst_volume_change_elem = 0;

    // Count of degraded elements
    int32_t n_negative_jacobian = 0;  // elements with negative Jacobian
    int32_t n_high_aspect = 0;        // elements with aspect ratio > 5
};

/**
 * @brief Element quality time-history for a part
 */
struct ElementQualityStats {
    int32_t part_id = 0;
    std::string part_name;
    std::string element_type;        ///< "shell", "solid"
    size_t num_elements = 0;
    std::vector<ElementQualityTimePoint> data;

    // Peak values across all time
    bool aspect_measured = false;
    double peak_aspect_ratio = 0.0;
    int32_t max_aspect_unavailable_count = 0;
    bool jacobian_measured = false;   ///< false 면 min_jacobian 은 미산출 (표기는 "—")
    double min_jacobian = 1.0;
    int32_t max_jacobian_unavailable_count = 0;
    bool warpage_measured = false;
    double peak_warpage = 0.0;
    bool skewness_measured = false;
    double peak_skewness = 0.0;
    bool volume_measured = false;
    double min_volume_change = 1.0;
    double max_volume_change = 1.0;
    int32_t max_negative_jacobian_count = 0;

    void computeGlobalStats() {
        aspect_measured = false;
        peak_aspect_ratio = 0;
        max_aspect_unavailable_count = 0;
        jacobian_measured = false;
        min_jacobian = 1.0;
        max_jacobian_unavailable_count = 0;
        warpage_measured = false;
        peak_warpage = 0;
        skewness_measured = false;
        peak_skewness = 0;
        volume_measured = false;
        min_volume_change = 1.0;
        max_volume_change = 1.0;
        max_negative_jacobian_count = 0;

        for (const auto& tp : data) {
            if (tp.aspect_measured) {
                if (tp.aspect_ratio_max > peak_aspect_ratio)
                    peak_aspect_ratio = tp.aspect_ratio_max;
                aspect_measured = true;
            }
            if (tp.n_aspect_unavailable > max_aspect_unavailable_count)
                max_aspect_unavailable_count = tp.n_aspect_unavailable;
            if (tp.jacobian_measured) {
                // 측정된 스텝끼리만 비교한다. 미측정 스텝의 기본값 1.0 을
                // 섞으면 '최악' 이 낙관적으로 흐려진다.
                if (!jacobian_measured || tp.jacobian_min < min_jacobian) {
                    min_jacobian = tp.jacobian_min;
                }
                jacobian_measured = true;
            }
            if (tp.n_jacobian_unavailable > max_jacobian_unavailable_count)
                max_jacobian_unavailable_count = tp.n_jacobian_unavailable;
            if (tp.warpage_measured) {
                if (tp.warpage_max > peak_warpage) peak_warpage = tp.warpage_max;
                warpage_measured = true;
            }
            if (tp.skewness_measured) {
                if (tp.skewness_max > peak_skewness) peak_skewness = tp.skewness_max;
                skewness_measured = true;
            }
            if (tp.volume_measured) {
                if (!volume_measured || tp.volume_change_min < min_volume_change)
                    min_volume_change = tp.volume_change_min;
                if (!volume_measured || tp.volume_change_max > max_volume_change)
                    max_volume_change = tp.volume_change_max;
                volume_measured = true;
            }
            if (tp.n_negative_jacobian > max_negative_jacobian_count)
                max_negative_jacobian_count = tp.n_negative_jacobian;
        }
    }

    size_t size() const { return data.size(); }
    bool empty() const { return data.empty(); }
};

// ============================================================
// Analysis Job Definition
// ============================================================

/**
 * @brief Surface specification for surface analysis jobs
 */
struct SurfaceSpec {
    Vec3 direction{0, 0, -1};    ///< Normal direction
    double angle = 45.0;         ///< Angle threshold in degrees
};

/**
 * @brief Custom Report 의 세트 후처리 사양 (YAML set_reports 항목 하나)
 *
 * LS-DYNA *SET_ 정의(파트/노드/세그먼트)를 참조해 그 세트만의 피크 지표와
 * 세트-격리 뷰(3면 탑뷰 영상·피크 스냅샷)를 만든다. 이후 상대 거동 등
 * 새 분석은 여기에 새 블록(필드)을 추가하는 방식으로 확장한다 — 기존
 * 블록과 독립이어야 한다.
 */
struct SetReportSpec {
    std::string name;                 ///< 표시 이름 (산출물 폴더명으로도 사용)
    std::string set_type = "part";    ///< part | node | segment
    int32_t set_id = 0;               ///< *SET_ 의 SID (0 = 세트 파일 참조 없음)

    /// 세트 파일 없이 YAML 에서 직접 고르는 경로 — 셋 다 합집합으로 동작한다.
    ///   parts:         [1, 2, 3]            직접 파트 ID
    ///   part_patterns: ["PKG*", "Front\\Metal"]  이름 글롭(정확명도 패턴으로 동작)
    std::vector<int32_t> part_ids;
    std::vector<std::string> part_patterns;

    /// 연동 세그먼트 셋 (*SET_SEGMENT SID). 지정하면 렌더 위에 해당 세그먼트
    /// 영역을 하이라이트하고 그 영역의 현재 프레임 최대값을 글자로 쓴다.
    std::vector<int32_t> highlight_segment_sets;

    /// 집계할 필드. 비우면 가용 전부 (von_mises, eff_plastic_strain, σ1/σ3, ε 계열)
    std::vector<std::string> fields;

    // ---- 뷰 (P2) ----
    std::vector<std::string> planes = {"xy", "yz", "zx"};
    bool video = true;                ///< 전 상태 컨투어 영상
    bool peak_snapshot = true;        ///< 필드별 피크 시각 스냅샷 PNG
    int width = 1280;
    int height = 720;
    int max_frames = 0;               ///< 0 = 전 상태, N = 균등 다운샘플
};

/// 세트 이름 → 파일시스템 안전 폴더명 (산출물·렌더 경로 공용 규약)
inline std::string sanitizeSetName(const std::string& name) {
    std::string out;
    for (char c : name) {
        const unsigned char u = static_cast<unsigned char>(c);
        out.push_back((std::isalnum(u) || c == '-' || c == '_') ? c : '_');
    }
    return out.empty() ? std::string("set") : out;
}

/**
 * @brief 세트 하나·필드 하나의 집계 결과 (시계열 + 피크)
 */
struct SetFieldResult {
    std::string field;                ///< "von_mises" 등
    bool measured = false;            ///< false 면 아래 값은 의미 없음 (note 참조)
    std::string note;                 ///< 미계측 사유 등

    double peak = 0.0;                ///< 피크 값 (압축 필드는 최소값)
    double peak_time = 0.0;
    int32_t peak_state = -1;          ///< 피크가 난 상태 인덱스 (뷰 스냅샷용)
    int32_t peak_element_id = 0;
    int32_t peak_part_id = 0;

    std::vector<double> times;        ///< 상태별 시각
    std::vector<double> values;       ///< 상태별 세트 극값 (원해상도, 다운샘플 없음)
};

/**
 * @brief 세트 하나의 Custom Report 결과
 */
struct SetReportResult {
    std::string name;
    std::string set_type;
    int32_t set_id = 0;
    std::string title;                        ///< *SET_..._TITLE 의 제목

    std::vector<int32_t> resolved_parts;      ///< 메시와 교집합된 파트 (part set)

    /// 지표 산출 방식 — "parts"(파트 이력 집계) | "nodes"(절점 직접 스윕) |
    /// "segments"(부모 요소 직접 스윕). finalize 는 parts 만 처리하고
    /// 나머지는 computeDirectSetMetrics 가 채운다.
    std::string metric_source = "parts";
    /// node 세트: 해석된 내부 절점 인덱스 (0-based)
    std::vector<int32_t> resolved_node_idx;
    /// segment 세트: 부모 solid 요소 내부 인덱스 (0-based)
    std::vector<int32_t> parent_elem_idx;

    /// 해석된 하이라이트 세그먼트 셋 (렌더 오버레이 입력)
    struct HighlightSet {
        int32_t sid = 0;
        std::string title;
        std::vector<std::array<int32_t, 4>> segments;   ///< 실 절점 ID 4개 (tria 는 n4==n3)
    };
    std::vector<HighlightSet> highlights;
    std::vector<int32_t> missing_parts;       ///< 세트에는 있으나 메시에 없는 파트
    size_t num_nodes = 0;                     ///< node set 멤버 수
    size_t num_segments = 0;                  ///< segment set 멤버 수
    std::vector<std::string> notes;           ///< 경고·스킵 사유 (무음 금지)

    std::vector<SetFieldResult> fields;
};

/**
 * @brief Single analysis job definition
 */
struct AnalysisJob {
    std::string name;                      ///< Job name (human-readable)
    AnalysisJobType type = AnalysisJobType::VON_MISES;
    std::vector<int32_t> part_ids;         ///< Parts to analyze (empty = all)
    std::string part_pattern;              ///< Part name pattern filter (e.g., "BATTERY*", "*CELL*")

    // Surface analysis options
    SurfaceSpec surface;

    // Motion analysis options
    bool calc_displacement = true;
    bool calc_velocity = true;
    bool calc_acceleration = true;

    // Comprehensive analysis: list of quantities
    std::vector<std::string> quantities;

    // Output options
    std::string output_prefix;

    /**
     * @brief Check if this job requires stress data
     */
    bool requiresStress() const {
        if (type == AnalysisJobType::VON_MISES || type == AnalysisJobType::SURFACE_STRESS) {
            return true;
        }
        if (type == AnalysisJobType::COMPREHENSIVE) {
            for (const auto& q : quantities) {
                if (q == "von_mises") return true;
            }
        }
        return false;
    }

    /**
     * @brief Check if this job requires strain data
     */
    bool requiresStrain() const {
        if (type == AnalysisJobType::EFF_PLASTIC_STRAIN || type == AnalysisJobType::SURFACE_STRAIN) {
            return true;
        }
        if (type == AnalysisJobType::COMPREHENSIVE) {
            for (const auto& q : quantities) {
                if (q == "eff_plastic_strain") return true;
            }
        }
        return false;
    }

    /**
     * @brief Check if this job requires node displacement data
     */
    bool requiresDisplacement() const {
        if (type == AnalysisJobType::PART_MOTION || type == AnalysisJobType::ELEMENT_QUALITY) {
            return true;
        }
        if (type == AnalysisJobType::COMPREHENSIVE) {
            for (const auto& q : quantities) {
                if (q == "avg_displacement" || q == "max_displacement" ||
                    q == "avg_velocity" || q == "avg_acceleration") {
                    return true;
                }
            }
        }
        return false;
    }
};

// ============================================================
// Render Job Types (for V4 Render integration)
// ============================================================

/**
 * @brief Render job type enumeration
 */
enum class RenderJobType {
    SECTION_VIEW,       ///< Single section view animation
    MULTI_SECTION,      ///< Multiple sections comparison
    PART_VIEW,          ///< Part isolation view
    FULL_MODEL,         ///< Full model view
    TIME_COMPARISON     ///< Side-by-side time comparison
};

/**
 * @brief Output format for render jobs
 */
enum class RenderOutputFormat {
    MP4,
    PNG,
    JPG,
    GIF
};

/**
 * @brief Section specification for render jobs
 */
struct RenderSectionSpec {
    char axis = 'z';           ///< Section axis (x, y, z)
    double position = 0.5;      ///< Position (0-1 normalized or absolute, e.g., 0.25 = 25%)
    bool normalized = true;     ///< Is position normalized (0-1)?
    std::string position_auto;  ///< Auto position: "center", "min", "max", or percentage like "25%"

    /**
     * @brief Parse position string (e.g., "center", "min", "max", "25%", "0.5")
     */
    static RenderSectionSpec fromPositionString(char axis, const std::string& pos_str) {
        RenderSectionSpec spec;
        spec.axis = axis;
        spec.normalized = true;

        if (pos_str == "center") {
            spec.position = 0.5;
            spec.position_auto = "center";
        } else if (pos_str == "min") {
            spec.position = 0.0;
            spec.position_auto = "min";
        } else if (pos_str == "max") {
            spec.position = 1.0;
            spec.position_auto = "max";
        } else if (pos_str.back() == '%') {
            // Parse percentage (e.g., "25%")
            try {
                double pct = std::stod(pos_str.substr(0, pos_str.size() - 1));
                spec.position = pct / 100.0;
                spec.position_auto = pos_str;
            } catch (...) {
                spec.position = 0.5;
            }
        } else {
            // Parse as decimal (e.g., "0.25")
            try {
                spec.position = std::stod(pos_str);
            } catch (...) {
                spec.position = 0.5;
            }
        }
        return spec;
    }
};

/**
 * @brief Fringe range specification
 */
struct FringeRange {
    double min = 0.0;
    double max = 0.0;  ///< 0 = auto
    bool is_auto() const { return max == 0.0; }
};

/**
 * @brief Render output specification
 */
struct RenderOutputSpec {
    RenderOutputFormat format = RenderOutputFormat::MP4;
    std::string filename;
    std::string directory;
    std::string filename_pattern;  ///< For multi-file output: "state_{state}.png"
    int fps = 30;
    std::array<int, 2> resolution = {1920, 1080};
};

/**
 * @brief Single render job definition
 */
struct RenderJob {
    std::string name;
    RenderJobType type = RenderJobType::SECTION_VIEW;

    // Fringe settings
    std::string fringe_type;  ///< "von_mises", "eff_plastic_strain", etc.
    FringeRange fringe_range;

    // Section settings
    std::vector<RenderSectionSpec> sections;

    // Part selection
    std::vector<int32_t> parts;  ///< Empty = all parts
    std::string part_pattern;    ///< Part name pattern filter (e.g., "CELL*", "*BATTERY*")

    // State selection
    std::vector<int> states;  ///< Empty = all, -1 = last state

    // View override (empty = auto-select based on section axis or ISOMETRIC)
    std::string view_str;  ///< "right", "front", "top", "iso", "left", "bottom", "back"

    // Output settings
    RenderOutputSpec output;
};

// ============================================================
// Extended Analysis Result
// ============================================================

/**
 * @brief Extended analysis result with motion and surface strain
 */
struct ExtendedAnalysisResult : public AnalysisResult {
    // Additional results
    std::vector<PartMotionStats> motion_analysis;
    std::vector<SurfaceStrainStats> surface_strain_analysis;
    /// Custom Report 세트 결과
    std::vector<SetReportResult> set_report_results;
    /// 빔 단면력 (축력·전단·모멘트·비틀림) 파트별 시계열
    std::vector<PartTimeSeriesStats> beam_analysis;
    std::vector<ElementQualityStats> element_quality;

    /**
     * @brief Check if any motion analysis results exist
     */
    bool hasMotionAnalysis() const { return !motion_analysis.empty(); }

    /**
     * @brief Check if any surface strain results exist
     */
    bool hasSurfaceStrainAnalysis() const { return !surface_strain_analysis.empty(); }

    /**
     * @brief Check if any element quality results exist
     */
    bool hasElementQuality() const { return !element_quality.empty(); }

    /**
     * @brief Save extended result to JSON (includes motion, surface strain, element quality)
     */
    bool saveExtendedToFile(const std::string& filepath) const {
        std::ofstream file(filepath);
        if (!file) return false;
        file << toExtendedJSON();
        return true;
    }

    std::string toExtendedJSON() const {
        // Start with base JSON but inject additional sections before closing brace
        std::string base = toJSON(true);

        // Find the last "]" + newline before closing "}" and append additional sections
        std::ostringstream extra;

        // Motion analysis
        // 수치는 전부 jnum — std::fixed 는 (1) 1e-6 미만을 "0.000000" 으로 지우고
        // (2) NaN/inf 를 JSON 이 아닌 nan/inf 로 써서 파일 전체를 못 읽게 만든다.
        // 게다가 한 번 건 std::fixed 는 이 스트림의 뒤 섹션 전부에 계속 걸린다.
        extra << ",\n  \"motion_analysis\": [";
        for (size_t i = 0; i < motion_analysis.size(); ++i) {
            if (i > 0) extra << ",";
            const auto& m = motion_analysis[i];
            extra << "\n    {\"part_id\": " << m.part_id
                  << ", \"part_name\": \"" << escapeJSON(m.part_name) << "\""
                  << ", \"peak_velocity\": " << jnum(m.peak_velocity_magnitude)
                  << ", \"peak_acceleration\": " << jnum(m.peak_acceleration_magnitude)
                  << ", \"max_displacement\": " << jnum(m.max_displacement_magnitude)
                  << ", \"num_points\": " << m.data.size() << "}";
        }
        extra << "\n  ]";

        // Element quality
        extra << ",\n  \"element_quality\": [";
        for (size_t i = 0; i < element_quality.size(); ++i) {
            if (i > 0) extra << ",";
            const auto& q = element_quality[i];
            extra << "\n    {\"part_id\": " << q.part_id
                  << ", \"part_name\": \"" << escapeJSON(q.part_name) << "\""
                  << ", \"element_type\": \"" << escapeJSON(q.element_type) << "\""
                  << ", \"num_elements\": " << q.num_elements
                  << ", \"aspect_measured\": " << (q.aspect_measured ? "true" : "false")
                  << ", \"peak_aspect_ratio\": " << jnum(q.peak_aspect_ratio)
                  << ", \"aspect_unavailable_count\": " << q.max_aspect_unavailable_count
                  << ", \"jacobian_measured\": " << (q.jacobian_measured ? "true" : "false")
                  << ", \"min_jacobian\": " << jnum(q.min_jacobian)
                  << ", \"jacobian_unavailable_count\": " << q.max_jacobian_unavailable_count
                  << ", \"warpage_measured\": " << (q.warpage_measured ? "true" : "false")
                  << ", \"peak_warpage\": " << jnum(q.peak_warpage)
                  << ", \"skewness_measured\": " << (q.skewness_measured ? "true" : "false")
                  << ", \"peak_skewness\": " << jnum(q.peak_skewness)
                  << ", \"volume_measured\": " << (q.volume_measured ? "true" : "false")
                  << ", \"min_volume_change\": " << jnum(q.min_volume_change)
                  << ", \"max_volume_change\": " << jnum(q.max_volume_change)
                  << ", \"max_negative_jacobian_count\": " << q.max_negative_jacobian_count
                  << ", \"data\": [";
            // 상태별 지표도 '미산출' 과 '측정해서 그 값' 을 구분해서 쓴다.
            // 예전에는 jac_measured 만 실어서, 종횡비·체적·왜곡도·뒤틀림은
            // 구조체 기본값(AR 0.0 · 체적비 1.0 · 0.0)이 그대로 값처럼 나갔다.
            // 파트 요약표는 파트 단위 플래그를 보고 "—" 를 찍는데, 그래프는
            // 이 data[] 를 그대로 그려 tet 파트가 'AR=0 · 체적 변화 없음(1.0)'
            // 이라는 없는 사실을 보여줬다. CSV 는 같은 경우를 빈 칸으로 둔다.
            auto qnum = [](bool measured, double v) {
                return measured ? jnum(v) : std::string("null");
            };
            for (size_t j = 0; j < q.data.size(); ++j) {
                if (j > 0) extra << ", ";
                const auto& tp = q.data[j];
                extra << "{\"time\": " << jnum(tp.time)
                      << ", \"ar_measured\": " << (tp.aspect_measured ? "true" : "false")
                      << ", \"ar_max\": " << qnum(tp.aspect_measured, tp.aspect_ratio_max)
                      << ", \"ar_avg\": " << qnum(tp.aspect_measured, tp.aspect_ratio_avg)
                      << ", \"jac_measured\": " << (tp.jacobian_measured ? "true" : "false")
                      << ", \"jac_min\": " << qnum(tp.jacobian_measured, tp.jacobian_min)
                      << ", \"jac_avg\": " << qnum(tp.jacobian_measured, tp.jacobian_avg)
                      << ", \"skew_measured\": " << (tp.skewness_measured ? "true" : "false")
                      << ", \"skew_max\": " << qnum(tp.skewness_measured, tp.skewness_max)
                      << ", \"warp_measured\": " << (tp.warpage_measured ? "true" : "false")
                      << ", \"warp_max\": " << qnum(tp.warpage_measured, tp.warpage_max)
                      << ", \"vol_measured\": " << (tp.volume_measured ? "true" : "false")
                      << ", \"vol_min\": " << qnum(tp.volume_measured, tp.volume_change_min)
                      << ", \"vol_max\": " << qnum(tp.volume_measured, tp.volume_change_max)
                      << ", \"n_neg_jac\": " << tp.n_negative_jacobian
                      << ", \"n_high_ar\": " << tp.n_high_aspect
                      << "}";
            }
            extra << "]}";
        }
        extra << "\n  ]";

        // 빔 단면력
        extra << ",\n  \"beam_analysis\": [";
        for (size_t i = 0; i < beam_analysis.size(); ++i) {
            if (i > 0) extra << ",";
            const auto& b = beam_analysis[i];
            // 비유한값은 비교가 전부 false 라 초기값 -1e300 이 그대로 '피크' 로
            // 나갔다(1e300 이 소수 6자리로 찍혀 300자리 숫자가 되기도 했다).
            // 유한값만 보고, 하나도 없으면 값이 아니라 null 을 쓴다.
            double gmax = 0.0, gmin = 0.0;
            double t_max = 0.0, t_min = 0.0;
            int32_t e_max = 0, e_min = 0;
            bool has_max = false, has_min = false;
            for (const auto& tp : b.data) {
                if (std::isfinite(tp.max_value) && (!has_max || tp.max_value > gmax)) {
                    gmax = tp.max_value; t_max = tp.time; e_max = tp.max_element_id; has_max = true;
                }
                if (std::isfinite(tp.min_value) && (!has_min || tp.min_value < gmin)) {
                    gmin = tp.min_value; t_min = tp.time; e_min = tp.min_element_id; has_min = true;
                }
            }
            extra << "\n    {\"part_id\": " << b.part_id
                  << ", \"quantity\": \"" << escapeJSON(b.quantity) << "\""
                  << ", \"num_points\": " << b.data.size()
                  << ", \"peak_max\": " << (has_max ? jnum(gmax) : "null")
                  << ", \"peak_max_time\": " << (has_max ? jnum(t_max) : "null")
                  << ", \"peak_max_element_id\": " << e_max
                  << ", \"peak_min\": " << (has_min ? jnum(gmin) : "null")
                  << ", \"peak_min_time\": " << (has_min ? jnum(t_min) : "null")
                  << ", \"peak_min_element_id\": " << e_min
                  << "}";
        }
        extra << "\n  ]";

        // Custom Report 세트 결과
        extra << ",\n  \"set_reports\": [";
        for (size_t i = 0; i < set_report_results.size(); ++i) {
            if (i > 0) extra << ",";
            const auto& sr = set_report_results[i];
            extra << "\n    {\"name\": \"" << escapeJSON(sr.name) << "\""
                  << ", \"set_type\": \"" << escapeJSON(sr.set_type) << "\""
                  << ", \"set_id\": " << sr.set_id
                  << ", \"title\": \"" << escapeJSON(sr.title) << "\""
                  << ", \"resolved_parts\": [";
            for (size_t j = 0; j < sr.resolved_parts.size(); ++j) {
                if (j > 0) extra << ", ";
                extra << sr.resolved_parts[j];
            }
            extra << "], \"missing_parts\": [";
            for (size_t j = 0; j < sr.missing_parts.size(); ++j) {
                if (j > 0) extra << ", ";
                extra << sr.missing_parts[j];
            }
            extra << "], \"notes\": [";
            for (size_t j = 0; j < sr.notes.size(); ++j) {
                if (j > 0) extra << ", ";
                extra << "\"" << escapeJSON(sr.notes[j]) << "\"";
            }
            extra << "], \"fields\": [";
            for (size_t j = 0; j < sr.fields.size(); ++j) {
                if (j > 0) extra << ",";
                const auto& f = sr.fields[j];
                extra << "\n      {\"field\": \"" << escapeJSON(f.field) << "\""
                      << ", \"measured\": " << (f.measured ? "true" : "false");
                if (f.measured) {
                    extra << ", \"peak\": " << jnum(f.peak)
                          << ", \"peak_time\": " << jnum(f.peak_time)
                          << ", \"peak_element_id\": " << f.peak_element_id
                          << ", \"peak_part_id\": " << f.peak_part_id
                          << ", \"num_points\": " << f.values.size();
                } else {
                    extra << ", \"note\": \"" << escapeJSON(f.note) << "\"";
                }
                extra << "}";
            }
            extra << "\n    ]}";
        }
        extra << "\n  ]";

        // 표면 변형률 — 지금까지 JSON 에 아예 안 실려서 CSV 를 열지 않으면
        // 값을 볼 방법이 없었다. has_strain_tensor/note 를 함께 실어 '미계측'
        // 과 '0 이었음' 을 구분할 수 있게 한다.
        extra << ",\n  \"surface_strain_analysis\": [";
        for (size_t i = 0; i < surface_strain_analysis.size(); ++i) {
            if (i > 0) extra << ",";
            const auto& s = surface_strain_analysis[i];
            extra << "\n    {\"description\": \"" << escapeJSON(s.description) << "\""
                  << ", \"reference_direction\": ["
                  << jnum(s.reference_direction.x) << ", " << jnum(s.reference_direction.y) << ", "
                  << jnum(s.reference_direction.z) << "]"
                  << ", \"angle_threshold_degrees\": " << jnum(s.angle_threshold_degrees)
                  << ", \"num_faces\": " << s.num_faces
                  << ", \"has_strain_tensor\": " << (s.has_strain_tensor ? "true" : "false")
                  << ", \"note\": \"" << escapeJSON(s.note) << "\""
                  << ", \"data\": [";
            for (size_t j = 0; j < s.data.size(); ++j) {
                if (j > 0) extra << ", ";
                const auto& tp = s.data[j];
                extra << "{\"time\": " << jnum(tp.time)
                      << ", \"normal_max\": " << jnum(tp.normal_strain_max)
                      << ", \"normal_min\": " << jnum(tp.normal_strain_min)
                      << ", \"normal_avg\": " << jnum(tp.normal_strain_avg)
                      << ", \"shear_max\": " << jnum(tp.shear_strain_max)
                      << ", \"e1_max\": " << jnum(tp.max_principal_strain_max)
                      << ", \"e1_max_element_id\": " << tp.max_principal_strain_max_element_id
                      << ", \"e3_min\": " << jnum(tp.min_principal_strain_min)
                      << ", \"e3_min_element_id\": " << tp.min_principal_strain_min_element_id
                      << ", \"evm_max\": " << jnum(tp.vm_strain_max)
                      << ", \"evm_max_element_id\": " << tp.vm_strain_max_element_id
                      << ", \"eff_plastic_max\": " << jnum(tp.eff_plastic_strain_max)
                      << "}";
            }
            extra << "]}";
        }
        extra << "\n  ]";

        // Insert before closing brace
        size_t close_brace = base.rfind('}');
        if (close_brace != std::string::npos) {
            base.insert(close_brace, extra.str() + "\n");
        }
        return base;
    }

    /**
     * @brief Export motion analysis to CSV
     */
    bool exportMotionToCSV(const std::string& filepath) const {
        if (motion_analysis.empty()) return false;

        std::ofstream file(filepath);
        if (!file) return false;

        // Header
        file << "Time";
        for (const auto& part : motion_analysis) {
            file << ",Part" << part.part_id << "_DispMag";
            file << ",Part" << part.part_id << "_VelMag";
            file << ",Part" << part.part_id << "_AccMag";
        }
        file << "\n";

        // Find max points
        size_t max_points = 0;
        for (const auto& part : motion_analysis) {
            if (part.data.size() > max_points) max_points = part.data.size();
        }

        // Data rows
        for (size_t t = 0; t < max_points; ++t) {
            bool first = true;
            for (const auto& part : motion_analysis) {
                if (t < part.data.size()) {
                    if (first) {
                        file << std::fixed << std::setprecision(8) << part.data[t].time;
                        first = false;
                    }
                    file << "," << part.data[t].avg_displacement_magnitude;
                    file << "," << part.data[t].avg_velocity_magnitude;
                    file << "," << part.data[t].avg_acceleration_magnitude;
                } else {
                    file << ",,,";
                }
            }
            file << "\n";
        }

        return true;
    }

    /**
     * @brief Export surface strain to CSV
     */
    bool exportSurfaceStrainToCSV(const std::string& filepath) const {
        if (surface_strain_analysis.empty()) return false;

        std::ofstream file(filepath);
        if (!file) return false;

        // Header
        file << "Time";
        for (size_t i = 0; i < surface_strain_analysis.size(); ++i) {
            file << ",Surface" << i << "_NormalMax";
            file << ",Surface" << i << "_NormalAvg";
            file << ",Surface" << i << "_ShearMax";
        }
        file << "\n";

        // Find max points
        size_t max_points = 0;
        for (const auto& surf : surface_strain_analysis) {
            if (surf.data.size() > max_points) max_points = surf.data.size();
        }

        // Data rows
        for (size_t t = 0; t < max_points; ++t) {
            bool first = true;
            for (const auto& surf : surface_strain_analysis) {
                if (t < surf.data.size()) {
                    if (first) {
                        file << std::fixed << std::setprecision(8) << surf.data[t].time;
                        first = false;
                    }
                    file << "," << surf.data[t].normal_strain_max;
                    file << "," << surf.data[t].normal_strain_avg;
                    file << "," << surf.data[t].shear_strain_max;
                } else {
                    file << ",,,";
                }
            }
            file << "\n";
        }

        return true;
    }
};

// ============================================================
// Section View Jobs (software-rasterized, VTK-free)
// ============================================================

/**
 * @brief A single software-rasterized section view job.
 *
 * The configuration is stored verbatim as a YAML block string so that
 * the core library (libkood3plot) does not need to include the
 * section_render headers.  The real parser lives in
 * kood3plot_section_render (SectionViewConfig::loadFromString).
 */
struct SectionViewJobSpec {
    std::string name;          ///< Human-readable job name
    bool        enabled = true;
    std::string yaml_block;    ///< Raw YAML text (indented, no "section_render:" header)
};

/**
 * @brief Per-part section render job (uses LSPrePostRenderer::renderAllPartSections)
 *
 * Generates per-part section views with genselect-based fringe isolation
 * (target part fringed, others in mesh color) and optional iso clip views.
 * Output structure: <output_directory>/part_{id}_{name}/section_{axis}.mp4
 *                                                  + iso_clip_{axis}.mp4
 *
 * If part_ids is empty, the analyzer auto-fills it from the analysis result
 * (all parts that produced stress/strain/motion data).
 */
struct PartSectionRenderJob {
    std::string name = "Part Section Renders";
    bool enabled = true;
    std::vector<int32_t> part_ids;          ///< empty = auto (all parts from analysis)
    /// Each entry is "x","y","z" or signed "+x","-x","+y","-y","+z","-z".
    /// Signed forms flip the cut normal — useful to control which side stays
    /// visible after the slice and which direction sliding sweeps in.
    std::vector<std::string> axes{"x", "y", "z"};
    std::string fringe_type = "von_mises";  ///< von_mises | eff_plastic_strain | displacement | ...
    bool section_view = true;               ///< drawcut + projectview per part
    bool iso_clip_view = true;              ///< isometric + clipplane per part
    double section_position = 0.5;          ///< 0..1 within part bbox
    double section_margin = -0.3;           ///< zin margin for section_view
    double iso_clip_margin = -0.3;          ///< zin margin for iso_clip_view (negative = zoom out)
    int edge_width = 2;
    int crf = 23;                           ///< H264 CRF for ffmpeg re-encode
    bool reverse_cut = true;                ///< Flip cut side so interior faces the camera
    // ── Sliding section view ──
    bool sliding_view = false;              ///< Master toggle for sliding videos
    bool sliding_section_style = true;      ///< Generate section-style sliding (drawcut + projectview)
    bool sliding_iso_style = true;          ///< Generate iso-style sliding (clipplane + isometric)
    int sliding_steps = 20;                 ///< Cut positions across part bbox
    bool sliding_near_to_far = true;        ///< true: bbox.max → bbox.min
    double sliding_pad = 0.05;              ///< Padding fraction outside bbox
    bool sliding_freeze_time = false;       ///< Phase B: freeze sim time at peak_state
    double sliding_peak_time = -1.0;        ///< Phase B: explicit peak time (-1 = auto)
    std::string output_directory = "renders/part_sections";
    std::vector<int32_t> resolution{1280, 720};
    int fps = 24;
};

// ============================================================
// Unified Configuration
// ============================================================

/**
 * @brief Unified configuration for analysis and rendering
 */
struct UnifiedConfig {
    std::string version = "2.0";

    // Input
    std::string d3plot_path;

    // Output
    std::string output_directory = "./analysis_output";
    bool output_json = true;
    bool output_csv = true;

    // Performance
    int num_threads = 0;  ///< 0 = auto (analysis/read threads)
    int render_threads = 1;  ///< Parallel LSPrePost instances (default 1, separate from analysis)
    int sv_threads = 2;  ///< Parallel section view renderers (default 2)
    bool verbose = true;
    bool cache_geometry = true;

    // LSPrePost path (for render jobs)
    // Fallback order:
    // 1. YAML lsprepost_path value
    // 2. Linux: {exe_dir}/../lsprepost/lsprepost
    // 3. Windows: {exe_dir}/../lsprepost/lspp412_win64.exe
    // 4. System PATH: "lsprepost"
    std::string lsprepost_path;

    // 표면 방향 분석 기본값. surface_stress/surface_strain 잡을 하나도 안 적으면
    // ±Z 두 방향(각도 surface_default_angle)을 자동으로 넣는다. 낙하/충격 해석은
    // 바닥면과 상면이 사실상 항상 관심 대상이라 기본으로 뽑아 두는 편이 낫다.
    // 필요 없으면 surface_defaults: false 로 끈다.
    bool surface_defaults = true;
    double surface_default_angle = 45.0;

    // Custom Report: 세트 정의 파일 (비우면 d3plot 근처 키워드 파일 자동 탐색)
    std::string sets_file;
    // Custom Report: 세트 후처리 사양
    std::vector<SetReportSpec> set_reports;

    // ── 핫스팟 군집 (docs/hotspot-cluster-plan.md) ──
    // 파트 내 상위 백분위 요소를 공간 군집화해 덩어리 단위로 보고.
    // 🔴 키 이름 주의 — 이 저장소의 YAML 파서는 일부 값을 문서 전체 대상
    //    정규식으로 훑으므로, 블록 안에 parts:/threads: 같은 흔한 키를 쓰면
    //    전역 설정을 가로챈다. 접두사 있는 이름만 쓸 것.
    bool   hotspot_enabled = false;
    double hotspot_top_percent = 5.0;
    double hotspot_distance_factor = 1.5;
    int    hotspot_min_elements = 5;
    int    hotspot_max_clusters = 20;
    /// 선별 기준량 이름 목록. "von_mises" | "max_principal" | "min_principal".
    /// 여러 개면 파트×기준 항목이 각각 나온다. 기본은 von_mises 단독(기존 출력 불변).
    std::vector<std::string> hotspot_criteria = {"von_mises"};

    /// 덩어리 평균의 시간 집계 방식.
    ///  - "elemmax_then_mean"  (기본) `mean_e(max_t)` — 요소별 시간 극값의 공간 평균.
    ///                         서로 다른 시각의 피크를 합성하므로 **항상 과대평가** 쪽.
    ///  - "mean_then_timemax"  `max_t(mean_e)` — 같은 시각에 실제로 걸린 하중.
    ///  - "both"               둘 다 보고.
    ///
    /// 🔴 "mean_then_timemax" 와 "both" 는 **출력이 같다**. `stress_mean`(=mean_e(max_t))
    ///    은 1패스의 부산물이라 어차피 나오고, 둘 다 `mean_timemax` 를 추가한다.
    ///    이름을 갈라 둔 것은 의도를 적기 위해서지 동작이 다르기 때문이 아니다 —
    ///    "mean_then_timemax 를 골랐는데 왜 stress_mean 도 있나" 로 헷갈리지 않도록
    ///    여기 적어 둔다.
    /// 기본을 바꾸지 않는 이유: 기존 산출물과의 비교가 깨지면 안 되기 때문이다.
    std::string hotspot_time_aggregate = "elemmax_then_mean";

    // Analysis jobs
    std::vector<AnalysisJob> analysis_jobs;

    // Render jobs
    std::vector<RenderJob> render_jobs;

    // Section view jobs (software-rasterized, VTK-free)
    std::vector<SectionViewJobSpec> section_views;

    // Per-part section render jobs (LSPrePost renderAllPartSections)
    std::vector<PartSectionRenderJob> part_section_renders;

    /// 설정을 읽다가 **그대로 실행하면 안 되는** 것을 만났을 때의 사유.
    /// 이 수제 파서가 못 읽는 문법(인라인 매핑 등)을 만나면 해당 잡을 빼고
    /// 여기에 사유를 남긴다. 산출물(metadata.config_issues)에 실어서, 로그를
    /// 못 보는 소비처도 '이 잡은 설정대로 돌지 않았다' 를 알 수 있게 한다.
    std::vector<std::string> config_issues;

    /**
     * @brief Check if any analysis jobs exist
     */
    bool hasAnalysisJobs() const { return !analysis_jobs.empty(); }

    /**
     * @brief Check if any render jobs exist
     */
    bool hasRenderJobs() const { return !render_jobs.empty(); }

    /**
     * @brief Check if any section view jobs exist
     */
    bool hasSectionViews() const { return !section_views.empty(); }

    /**
     * @brief Check if any per-part section render jobs exist
     */
    bool hasPartSectionRenders() const { return !part_section_renders.empty(); }

    /**
     * @brief Check if stress data is needed by any job
     */
    bool needsStressData() const {
        for (const auto& job : analysis_jobs) {
            if (job.requiresStress()) return true;
        }
        return false;
    }

    /**
     * @brief Check if strain data is needed by any job
     */
    bool needsStrainData() const {
        for (const auto& job : analysis_jobs) {
            if (job.requiresStrain()) return true;
        }
        return false;
    }

    /**
     * @brief Check if displacement data is needed by any job
     */
    bool needsDisplacementData() const {
        for (const auto& job : analysis_jobs) {
            if (job.requiresDisplacement()) return true;
        }
        return false;
    }

    /**
     * @brief Get all unique part IDs from all jobs
     */
    std::vector<int32_t> getAllPartIds() const {
        std::vector<int32_t> all_parts;
        for (const auto& job : analysis_jobs) {
            for (int32_t pid : job.part_ids) {
                bool found = false;
                for (int32_t existing : all_parts) {
                    if (existing == pid) { found = true; break; }
                }
                if (!found) all_parts.push_back(pid);
            }
        }
        return all_parts;
    }
};

} // namespace analysis
} // namespace kood3plot
