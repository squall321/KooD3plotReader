/**
 * @file UnifiedConfigParser.hpp
 * @brief Unified YAML configuration parser for analysis and rendering
 * @author KooD3plot Development Team
 * @date 2025-12-04
 *
 * Provides YAML configuration loading for the unified analysis system.
 * Supports both analysis_jobs and render_jobs in a single configuration file.
 *
 * Example YAML (v2.0):
 * @code
 * version: "2.0"
 *
 * input:
 *   d3plot: "results/d3plot"
 *
 * output:
 *   directory: "./analysis_output"
 *   json: true
 *   csv: true
 *
 * performance:
 *   threads: 0
 *   verbose: true
 *
 * analysis_jobs:
 *   - name: "Stress Analysis"
 *     type: von_mises
 *     parts: [1, 2, 3]
 *     output_prefix: "stress"
 *
 *   - name: "Motion Analysis"
 *     type: part_motion
 *     parts: []
 *     quantities:
 *       - avg_displacement
 *       - avg_velocity
 *     output_prefix: "motion"
 *
 * render_jobs:
 *   - name: "Section View"
 *     type: section_view
 *     fringe: von_mises
 *     section:
 *       axis: z
 *       position: center
 *     states: all
 *     output:
 *       format: mp4
 *       filename: "section.mp4"
 * @endcode
 */

#pragma once

#include "kood3plot/analysis/AnalysisTypes.hpp"
#include <string>
#include <vector>

namespace kood3plot {
namespace analysis {

/**
 * @brief Unified YAML configuration parser
 *
 * Parses YAML configuration files for the unified analysis system.
 * Supports v1.0 (legacy) and v2.0 (job-based) formats.
 */
class UnifiedConfigParser {
public:
    /**
     * @brief Load configuration from YAML file
     * @param file_path Path to YAML file
     * @param config Output configuration
     * @return true if successful
     */
    static bool loadFromYAML(const std::string& file_path, UnifiedConfig& config);

    /**
     * @brief Load configuration from YAML string
     * @param yaml_content YAML content string
     * @param config Output configuration
     * @return true if successful
     */
    static bool loadFromYAMLString(const std::string& yaml_content, UnifiedConfig& config);

    /**
     * @brief Save configuration to YAML file
     * @param file_path Path to YAML file
     * @param config Configuration to save
     * @return true if successful
     */
    static bool saveToYAML(const std::string& file_path, const UnifiedConfig& config);

    /**
     * @brief Generate example YAML configuration (v2.0)
     * @return Example YAML string
     */
    static std::string generateExampleYAML();

    /**
     * @brief Generate minimal YAML configuration
     * @param d3plot_path Path to d3plot file
     * @return Minimal YAML string
     */
    static std::string generateMinimalYAML(const std::string& d3plot_path);

    /**
     * @brief Get last error message
     */
    static const std::string& getLastError();

    /**
     * @brief Validate configuration
     * @param config Configuration to validate
     * @return true if valid
     */
    static bool validate(const UnifiedConfig& config);

private:
    static std::string last_error_;

    // Helper functions
    static std::string trim(const std::string& str);
    static std::vector<double> parseDoubleArray(const std::string& str);
    static std::vector<int32_t> parseIntArray(const std::string& str);
    static std::vector<std::string> parseStringArray(const std::string& str);
    static bool parseBool(const std::string& str);

    // Section parsers
    static bool parseInputSection(const std::string& content, UnifiedConfig& config);
    static bool parseOutputSection(const std::string& content, UnifiedConfig& config);
    static bool parsePerformanceSection(const std::string& content, UnifiedConfig& config);
    static bool parseAnalysisJobs(const std::string& content, UnifiedConfig& config);
    static bool parseRenderJobs(const std::string& content, UnifiedConfig& config);

    // Job parsers
    static bool parseAnalysisJob(const std::vector<std::string>& lines, size_t& idx, AnalysisJob& job);
    static bool parseRenderJob(const std::vector<std::string>& lines, size_t& idx, RenderJob& job);
};

} // namespace analysis
} // namespace kood3plot
