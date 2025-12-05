/**
 * @file AnalysisConfigParser.hpp
 * @brief YAML configuration parser for analysis settings
 * @author KooD3plot Development Team
 * @date 2025-12-04
 *
 * Provides YAML configuration loading for TimeHistoryAnalyzer.
 * Supports combined analysis + render configurations.
 *
 * Example YAML:
 * @code
 * # KooD3plot Analysis Configuration
 * input:
 *   d3plot: "results/d3plot"
 *
 * output:
 *   directory: "./analysis_output"
 *   json: true
 *   csv: true
 *
 * analysis:
 *   stress: true
 *   strain: true
 *   parts: []  # empty = all parts
 *
 * surfaces:
 *   - name: "Bottom surface"
 *     direction: [0, 0, -1]
 *     angle: 45.0
 *   - name: "Top surface"
 *     direction: [0, 0, 1]
 *     angle: 45.0
 *
 * performance:
 *   threads: 0  # 0 = auto
 *   verbose: true
 * @endcode
 */

#pragma once

#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
#include <string>
#include <vector>

namespace kood3plot {
namespace analysis {

/**
 * @brief Extended analysis configuration with additional options
 */
struct ExtendedAnalysisConfig : public AnalysisConfig {
    // Output settings
    std::string output_directory;
    bool output_json = true;
    bool output_csv = true;

    // Performance settings
    int num_threads = 0;  // 0 = auto (use all available cores)
};

/**
 * @brief YAML configuration parser for analysis
 */
class AnalysisConfigParser {
public:
    /**
     * @brief Load configuration from YAML file
     * @param file_path Path to YAML file
     * @param config Output configuration
     * @return true if successful
     */
    static bool loadFromYAML(const std::string& file_path, ExtendedAnalysisConfig& config);

    /**
     * @brief Load configuration from YAML string
     * @param yaml_content YAML content string
     * @param config Output configuration
     * @return true if successful
     */
    static bool loadFromYAMLString(const std::string& yaml_content, ExtendedAnalysisConfig& config);

    /**
     * @brief Save configuration to YAML file
     * @param file_path Path to YAML file
     * @param config Configuration to save
     * @return true if successful
     */
    static bool saveToYAML(const std::string& file_path, const ExtendedAnalysisConfig& config);

    /**
     * @brief Generate example YAML configuration
     * @return Example YAML string
     */
    static std::string generateExampleYAML();

    /**
     * @brief Get last error message
     */
    static const std::string& getLastError();

private:
    static std::string last_error_;

    // Helper functions
    static std::string trim(const std::string& str);
    static std::vector<double> parseDoubleArray(const std::string& str);
    static std::vector<int32_t> parseIntArray(const std::string& str);
};

} // namespace analysis
} // namespace kood3plot
