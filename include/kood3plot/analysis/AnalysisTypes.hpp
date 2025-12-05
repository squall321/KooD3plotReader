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
        case AnalysisJobType::PART_MOTION: return "part_motion";
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
    if (str == "part_motion") return AnalysisJobType::PART_MOTION;
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
        if (type == AnalysisJobType::PART_MOTION) {
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
    double position = 0.5;      ///< Position (0-1 normalized or absolute)
    bool normalized = true;     ///< Is position normalized?
    std::string position_auto;  ///< Auto position: "center", "edge_min", "edge_max", etc.
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

    // State selection
    std::vector<int> states;  ///< Empty = all, -1 = last state

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

    /**
     * @brief Check if any motion analysis results exist
     */
    bool hasMotionAnalysis() const { return !motion_analysis.empty(); }

    /**
     * @brief Check if any surface strain results exist
     */
    bool hasSurfaceStrainAnalysis() const { return !surface_strain_analysis.empty(); }

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
    int num_threads = 0;  ///< 0 = auto
    bool verbose = true;
    bool cache_geometry = true;

    // Analysis jobs
    std::vector<AnalysisJob> analysis_jobs;

    // Render jobs
    std::vector<RenderJob> render_jobs;

    /**
     * @brief Check if any analysis jobs exist
     */
    bool hasAnalysisJobs() const { return !analysis_jobs.empty(); }

    /**
     * @brief Check if any render jobs exist
     */
    bool hasRenderJobs() const { return !render_jobs.empty(); }

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
