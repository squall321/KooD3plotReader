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
        extra << ",\n  \"motion_analysis\": [";
        for (size_t i = 0; i < motion_analysis.size(); ++i) {
            if (i > 0) extra << ",";
            const auto& m = motion_analysis[i];
            extra << "\n    {\"part_id\": " << m.part_id
                  << ", \"part_name\": \"" << m.part_name << "\""
                  << ", \"peak_velocity\": " << std::fixed << std::setprecision(6) << m.peak_velocity_magnitude
                  << ", \"peak_acceleration\": " << m.peak_acceleration_magnitude
                  << ", \"max_displacement\": " << m.max_displacement_magnitude
                  << ", \"num_points\": " << m.data.size() << "}";
        }
        extra << "\n  ]";

        // Element quality
        extra << ",\n  \"element_quality\": [";
        for (size_t i = 0; i < element_quality.size(); ++i) {
            if (i > 0) extra << ",";
            const auto& q = element_quality[i];
            extra << "\n    {\"part_id\": " << q.part_id
                  << ", \"part_name\": \"" << q.part_name << "\""
                  << ", \"element_type\": \"" << q.element_type << "\""
                  << ", \"num_elements\": " << q.num_elements
                  << ", \"aspect_measured\": " << (q.aspect_measured ? "true" : "false")
                  << ", \"peak_aspect_ratio\": " << std::fixed << std::setprecision(4) << q.peak_aspect_ratio
                  << ", \"aspect_unavailable_count\": " << q.max_aspect_unavailable_count
                  << ", \"jacobian_measured\": " << (q.jacobian_measured ? "true" : "false")
                  << ", \"min_jacobian\": " << q.min_jacobian
                  << ", \"jacobian_unavailable_count\": " << q.max_jacobian_unavailable_count
                  << ", \"warpage_measured\": " << (q.warpage_measured ? "true" : "false")
                  << ", \"peak_warpage\": " << q.peak_warpage
                  << ", \"skewness_measured\": " << (q.skewness_measured ? "true" : "false")
                  << ", \"peak_skewness\": " << q.peak_skewness
                  << ", \"volume_measured\": " << (q.volume_measured ? "true" : "false")
                  << ", \"min_volume_change\": " << q.min_volume_change
                  << ", \"max_volume_change\": " << q.max_volume_change
                  << ", \"max_negative_jacobian_count\": " << q.max_negative_jacobian_count
                  << ", \"data\": [";
            for (size_t j = 0; j < q.data.size(); ++j) {
                if (j > 0) extra << ", ";
                const auto& tp = q.data[j];
                extra << "{\"time\": " << std::setprecision(8) << tp.time
                      << ", \"ar_max\": " << std::setprecision(4) << tp.aspect_ratio_max
                      << ", \"ar_avg\": " << tp.aspect_ratio_avg
                      << ", \"jac_measured\": " << (tp.jacobian_measured ? "true" : "false")
                      << ", \"jac_min\": " << tp.jacobian_min
                      << ", \"jac_avg\": " << tp.jacobian_avg
                      << ", \"skew_max\": " << tp.skewness_max
                      << ", \"warp_max\": " << tp.warpage_max
                      << ", \"vol_min\": " << tp.volume_change_min
                      << ", \"vol_max\": " << tp.volume_change_max
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
            double gmax = -1e300, gmin = 1e300;
            double t_max = 0.0, t_min = 0.0;
            int32_t e_max = 0, e_min = 0;
            for (const auto& tp : b.data) {
                if (tp.max_value > gmax) { gmax = tp.max_value; t_max = tp.time; e_max = tp.max_element_id; }
                if (tp.min_value < gmin) { gmin = tp.min_value; t_min = tp.time; e_min = tp.min_element_id; }
            }
            extra << "\n    {\"part_id\": " << b.part_id
                  << ", \"quantity\": \"" << b.quantity << "\""
                  << ", \"num_points\": " << b.data.size()
                  << ", \"peak_max\": " << std::fixed << std::setprecision(6) << gmax
                  << ", \"peak_max_time\": " << t_max
                  << ", \"peak_max_element_id\": " << e_max
                  << ", \"peak_min\": " << gmin
                  << ", \"peak_min_time\": " << t_min
                  << ", \"peak_min_element_id\": " << e_min
                  << "}";
        }
        extra << "\n  ]";

        // 표면 변형률 — 지금까지 JSON 에 아예 안 실려서 CSV 를 열지 않으면
        // 값을 볼 방법이 없었다. has_strain_tensor/note 를 함께 실어 '미계측'
        // 과 '0 이었음' 을 구분할 수 있게 한다.
        extra << ",\n  \"surface_strain_analysis\": [";
        for (size_t i = 0; i < surface_strain_analysis.size(); ++i) {
            if (i > 0) extra << ",";
            const auto& s = surface_strain_analysis[i];
            extra << "\n    {\"description\": \"" << s.description << "\""
                  << ", \"reference_direction\": [" << std::fixed << std::setprecision(6)
                  << s.reference_direction.x << ", " << s.reference_direction.y << ", "
                  << s.reference_direction.z << "]"
                  << ", \"angle_threshold_degrees\": " << s.angle_threshold_degrees
                  << ", \"num_faces\": " << s.num_faces
                  << ", \"has_strain_tensor\": " << (s.has_strain_tensor ? "true" : "false")
                  << ", \"note\": \"" << s.note << "\""
                  << ", \"data\": [";
            for (size_t j = 0; j < s.data.size(); ++j) {
                if (j > 0) extra << ", ";
                const auto& tp = s.data[j];
                extra << "{\"time\": " << std::setprecision(8) << tp.time
                      << ", \"normal_max\": " << tp.normal_strain_max
                      << ", \"normal_min\": " << tp.normal_strain_min
                      << ", \"normal_avg\": " << tp.normal_strain_avg
                      << ", \"shear_max\": " << tp.shear_strain_max
                      << ", \"e1_max\": " << tp.max_principal_strain_max
                      << ", \"e1_max_element_id\": " << tp.max_principal_strain_max_element_id
                      << ", \"e3_min\": " << tp.min_principal_strain_min
                      << ", \"e3_min_element_id\": " << tp.min_principal_strain_min_element_id
                      << ", \"evm_max\": " << tp.vm_strain_max
                      << ", \"evm_max_element_id\": " << tp.vm_strain_max_element_id
                      << ", \"eff_plastic_max\": " << tp.eff_plastic_strain_max
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

    // Analysis jobs
    std::vector<AnalysisJob> analysis_jobs;

    // Render jobs
    std::vector<RenderJob> render_jobs;

    // Section view jobs (software-rasterized, VTK-free)
    std::vector<SectionViewJobSpec> section_views;

    // Per-part section render jobs (LSPrePost renderAllPartSections)
    std::vector<PartSectionRenderJob> part_section_renders;

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
