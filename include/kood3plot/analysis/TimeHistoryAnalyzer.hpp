/**
 * @file TimeHistoryAnalyzer.hpp
 * @brief Unified time history analysis for d3plot files
 * @author KooD3plot Development Team
 * @date 2024-12-04
 * @version 1.0.0
 *
 * Integrates all analysis modules (PartAnalyzer, SurfaceExtractor, SurfaceStressAnalyzer)
 * to provide a comprehensive analysis output in JSON format.
 */

#pragma once

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/PartAnalyzer.hpp"
#include "kood3plot/analysis/SurfaceExtractor.hpp"
#include "kood3plot/analysis/SurfaceStressAnalyzer.hpp"
#include "kood3plot/analysis/AnalysisResult.hpp"
#include "kood3plot/analysis/VectorMath.hpp"
#include <vector>
#include <string>
#include <functional>
#include <memory>

namespace kood3plot {
namespace analysis {

// ============================================================
// Analysis Configuration
// ============================================================

/**
 * @brief Surface analysis specification
 *
 * Defines a direction-based surface analysis request.
 */
struct SurfaceAnalysisSpec {
    std::string description;              ///< Human-readable description (e.g., "Bottom surface")
    Vec3 direction;                       ///< Reference direction vector
    double angle_threshold_degrees = 45.0; ///< Maximum angle from reference direction
    std::vector<int32_t> part_ids;        ///< Parts to include (empty = all)

    SurfaceAnalysisSpec() = default;

    SurfaceAnalysisSpec(const std::string& desc, const Vec3& dir, double angle = 45.0)
        : description(desc), direction(dir), angle_threshold_degrees(angle) {}

    SurfaceAnalysisSpec(const std::string& desc, const Vec3& dir, double angle,
                        const std::vector<int32_t>& parts)
        : description(desc), direction(dir), angle_threshold_degrees(angle), part_ids(parts) {}
};

/**
 * @brief Analysis configuration
 *
 * Specifies what analysis to perform.
 */
struct AnalysisConfig {
    // File path
    std::string d3plot_path;

    // What to analyze
    bool analyze_stress = true;          ///< Analyze Von Mises stress history
    bool analyze_strain = true;          ///< Analyze effective plastic strain history
    bool analyze_acceleration = false;   ///< Analyze average acceleration (disabled by default)

    // Stress component for part analysis
    StressComponent stress_component = StressComponent::VON_MISES;

    // Parts to analyze (empty = all parts)
    std::vector<int32_t> part_ids;

    // Surface analysis specifications
    std::vector<SurfaceAnalysisSpec> surface_specs;

    // Output configuration
    std::string output_json_path;        ///< Path for JSON output (empty = don't save)
    std::string output_csv_prefix;       ///< Prefix for CSV files (empty = don't export)

    // Performance options
    bool verbose = false;                ///< Print progress messages to stdout

    /**
     * @brief Add a surface analysis specification
     */
    void addSurfaceAnalysis(const std::string& desc, const Vec3& dir, double angle = 45.0) {
        surface_specs.emplace_back(desc, dir, angle);
    }

    /**
     * @brief Add surface analysis for specific parts
     */
    void addSurfaceAnalysis(const std::string& desc, const Vec3& dir, double angle,
                            const std::vector<int32_t>& parts) {
        surface_specs.emplace_back(desc, dir, angle, parts);
    }

    /**
     * @brief Create default configuration for common analysis
     */
    static AnalysisConfig createDefault(const std::string& d3plot_path) {
        AnalysisConfig config;
        config.d3plot_path = d3plot_path;
        config.analyze_stress = true;
        config.analyze_strain = true;
        config.analyze_acceleration = false;
        return config;
    }

    /**
     * @brief Create configuration with bottom surface analysis
     */
    static AnalysisConfig withBottomSurface(const std::string& d3plot_path, double angle = 45.0) {
        AnalysisConfig config = createDefault(d3plot_path);
        config.addSurfaceAnalysis("Bottom surface (-Z)", Vec3(0, 0, -1), angle);
        return config;
    }

    /**
     * @brief Create configuration with top and bottom surface analysis
     */
    static AnalysisConfig withTopBottomSurfaces(const std::string& d3plot_path, double angle = 45.0) {
        AnalysisConfig config = createDefault(d3plot_path);
        config.addSurfaceAnalysis("Bottom surface (-Z)", Vec3(0, 0, -1), angle);
        config.addSurfaceAnalysis("Top surface (+Z)", Vec3(0, 0, 1), angle);
        return config;
    }
};

// ============================================================
// Progress Callback
// ============================================================

/**
 * @brief Progress callback function type
 *
 * @param phase Current analysis phase name
 * @param current Current step within phase
 * @param total Total steps in phase
 * @param message Human-readable progress message
 */
using AnalysisProgressCallback = std::function<void(
    const std::string& phase,
    size_t current,
    size_t total,
    const std::string& message
)>;

// ============================================================
// TimeHistoryAnalyzer Class
// ============================================================

/**
 * @brief Unified time history analyzer
 *
 * Combines multiple analysis modules to provide comprehensive
 * d3plot analysis with JSON output.
 *
 * Usage:
 * @code
 * // Create configuration
 * auto config = AnalysisConfig::withBottomSurface("d3plot");
 * config.output_json_path = "analysis_result.json";
 *
 * // Run analysis
 * TimeHistoryAnalyzer analyzer;
 * AnalysisResult result = analyzer.analyze(config);
 *
 * // Or with progress callback
 * result = analyzer.analyze(config, [](const std::string& phase,
 *     size_t current, size_t total, const std::string& msg) {
 *     std::cout << phase << ": " << msg << " (" << current << "/" << total << ")\n";
 * });
 * @endcode
 */
class TimeHistoryAnalyzer {
public:
    /**
     * @brief Default constructor
     */
    TimeHistoryAnalyzer() = default;

    /**
     * @brief Destructor
     */
    ~TimeHistoryAnalyzer() = default;

    /**
     * @brief Run complete analysis
     * @param config Analysis configuration
     * @return AnalysisResult containing all analysis data
     */
    AnalysisResult analyze(const AnalysisConfig& config);

    /**
     * @brief Run analysis with progress callback
     * @param config Analysis configuration
     * @param callback Progress callback function
     * @return AnalysisResult containing all analysis data
     */
    AnalysisResult analyze(const AnalysisConfig& config, AnalysisProgressCallback callback);

    /**
     * @brief Get last error message
     */
    const std::string& getLastError() const { return last_error_; }

    /**
     * @brief Check if last analysis was successful
     */
    bool wasSuccessful() const { return success_; }

private:
    std::string last_error_;
    bool success_ = false;

    // Internal analysis methods
    void analyzeStressHistory(
        D3plotReader& reader,
        PartAnalyzer& part_analyzer,
        const AnalysisConfig& config,
        AnalysisResult& result,
        AnalysisProgressCallback callback
    );

    void analyzeStrainHistory(
        D3plotReader& reader,
        PartAnalyzer& part_analyzer,
        const AnalysisConfig& config,
        AnalysisResult& result,
        AnalysisProgressCallback callback
    );

    void analyzeAccelerationHistory(
        D3plotReader& reader,
        const AnalysisConfig& config,
        AnalysisResult& result,
        AnalysisProgressCallback callback
    );

    void analyzeSurfaceStress(
        D3plotReader& reader,
        const AnalysisConfig& config,
        AnalysisResult& result,
        AnalysisProgressCallback callback
    );

    /**
     * @brief Convert PartTimeHistory to PartTimeSeriesStats
     */
    PartTimeSeriesStats convertToStats(
        const PartTimeHistory& history,
        const std::string& quantity,
        const std::string& unit
    );

    /**
     * @brief Fill metadata in result
     */
    void fillMetadata(
        D3plotReader& reader,
        const AnalysisConfig& config,
        AnalysisResult& result
    );
};

} // namespace analysis
} // namespace kood3plot
