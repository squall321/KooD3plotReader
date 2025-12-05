/**
 * @file AnalysisResult.hpp
 * @brief Data structures for analysis results and JSON serialization
 * @author KooD3plot Development Team
 * @date 2024-12-04
 * @version 1.0.0
 *
 * Provides structures for storing analysis results and converting to/from JSON format.
 */

#pragma once

#include "VectorMath.hpp"
#include <string>
#include <vector>
#include <map>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <ctime>
#include <stdexcept>

namespace kood3plot {
namespace analysis {

// ============================================================
// Time Series Data Structures
// ============================================================

/**
 * @brief Single time point data for statistical quantities
 */
struct TimePointStats {
    double time = 0.0;          ///< Simulation time
    double max_value = 0.0;     ///< Maximum value
    double min_value = 0.0;     ///< Minimum value
    double avg_value = 0.0;     ///< Average value
    double rms_value = 0.0;     ///< RMS value (optional)
    int32_t max_element_id = 0; ///< Element ID with max value
    int32_t min_element_id = 0; ///< Element ID with min value
};

/**
 * @brief Time series statistics for a single part
 */
struct PartTimeSeriesStats {
    int32_t part_id = 0;             ///< Part ID
    std::string part_name;           ///< Part name (if available)
    std::string quantity;            ///< Quantity name (e.g., "von_mises", "eff_plastic_strain")
    std::string unit;                ///< Unit (e.g., "MPa", "mm/s^2")
    std::vector<TimePointStats> data; ///< Time series data

    /**
     * @brief Get number of time points
     */
    size_t size() const { return data.size(); }

    /**
     * @brief Check if empty
     */
    bool empty() const { return data.empty(); }

    /**
     * @brief Get global maximum across all time points
     */
    double globalMax() const {
        double max_val = -std::numeric_limits<double>::infinity();
        for (const auto& tp : data) {
            if (tp.max_value > max_val) max_val = tp.max_value;
        }
        return max_val;
    }

    /**
     * @brief Get global minimum across all time points
     */
    double globalMin() const {
        double min_val = std::numeric_limits<double>::infinity();
        for (const auto& tp : data) {
            if (tp.min_value < min_val) min_val = tp.min_value;
        }
        return min_val;
    }

    /**
     * @brief Get time of global maximum
     */
    double timeOfGlobalMax() const {
        double max_val = -std::numeric_limits<double>::infinity();
        double time_at_max = 0.0;
        for (const auto& tp : data) {
            if (tp.max_value > max_val) {
                max_val = tp.max_value;
                time_at_max = tp.time;
            }
        }
        return time_at_max;
    }
};

/**
 * @brief Single time point data for surface stress analysis
 */
struct SurfaceTimePointStats {
    double time = 0.0;

    // Normal stress statistics
    double normal_stress_max = 0.0;
    double normal_stress_min = 0.0;
    double normal_stress_avg = 0.0;
    int32_t normal_stress_max_element_id = 0;

    // Shear stress statistics
    double shear_stress_max = 0.0;
    double shear_stress_avg = 0.0;
    int32_t shear_stress_max_element_id = 0;
};

/**
 * @brief Surface analysis statistics for a specific direction
 */
struct SurfaceAnalysisStats {
    std::string description;              ///< Human-readable description
    Vec3 reference_direction;             ///< Reference direction vector
    double angle_threshold_degrees = 0.0; ///< Angle threshold in degrees
    std::vector<int32_t> part_ids;        ///< Parts included in analysis
    int32_t num_faces = 0;                ///< Number of faces analyzed
    std::vector<SurfaceTimePointStats> data; ///< Time series data

    /**
     * @brief Get number of time points
     */
    size_t size() const { return data.size(); }

    /**
     * @brief Check if empty
     */
    bool empty() const { return data.empty(); }
};

// ============================================================
// Metadata
// ============================================================

/**
 * @brief Analysis metadata
 */
struct AnalysisMetadata {
    std::string d3plot_path;             ///< Path to d3plot file
    std::string analysis_date;           ///< Analysis date/time (ISO 8601)
    std::string kood3plot_version;       ///< Library version
    int32_t num_states = 0;              ///< Number of states analyzed
    double start_time = 0.0;             ///< First state time
    double end_time = 0.0;               ///< Last state time
    std::vector<int32_t> analyzed_parts; ///< List of analyzed part IDs

    /**
     * @brief Set analysis date to current time
     */
    void setCurrentDate() {
        std::time_t now = std::time(nullptr);
        char buf[64];
        std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", std::gmtime(&now));
        analysis_date = buf;
    }
};

// ============================================================
// Main Analysis Result
// ============================================================

/**
 * @brief Complete analysis result container
 *
 * Stores all analysis results and provides JSON serialization/deserialization.
 *
 * Usage:
 * @code
 * AnalysisResult result;
 * result.metadata.d3plot_path = "path/to/d3plot";
 * result.metadata.setCurrentDate();
 *
 * // Add stress history for part 1
 * PartTimeSeriesStats stress;
 * stress.part_id = 1;
 * stress.quantity = "von_mises";
 * // ... fill data ...
 * result.stress_history.push_back(stress);
 *
 * // Save to JSON
 * result.saveToFile("analysis_result.json");
 * @endcode
 */
struct AnalysisResult {
    AnalysisMetadata metadata;

    // Time series data
    std::vector<PartTimeSeriesStats> stress_history;       ///< Von Mises stress history
    std::vector<PartTimeSeriesStats> strain_history;       ///< Effective plastic strain history
    std::vector<PartTimeSeriesStats> acceleration_history; ///< Average acceleration history

    // Surface analysis
    std::vector<SurfaceAnalysisStats> surface_analysis;

    // ============================================================
    // JSON Serialization
    // ============================================================

    /**
     * @brief Convert to JSON string
     * @param pretty Use pretty printing (indentation)
     * @return JSON string
     */
    std::string toJSON(bool pretty = true) const {
        std::ostringstream oss;
        std::string indent = pretty ? "  " : "";
        std::string nl = pretty ? "\n" : "";

        oss << "{" << nl;

        // Metadata
        oss << indent << "\"metadata\": {" << nl;
        oss << indent << indent << "\"d3plot_path\": \"" << escapeJSON(metadata.d3plot_path) << "\"," << nl;
        oss << indent << indent << "\"analysis_date\": \"" << metadata.analysis_date << "\"," << nl;
        oss << indent << indent << "\"kood3plot_version\": \"" << metadata.kood3plot_version << "\"," << nl;
        oss << indent << indent << "\"num_states\": " << metadata.num_states << "," << nl;
        oss << indent << indent << "\"start_time\": " << std::fixed << std::setprecision(8) << metadata.start_time << "," << nl;
        oss << indent << indent << "\"end_time\": " << metadata.end_time << "," << nl;
        oss << indent << indent << "\"analyzed_parts\": " << arrayToJSON(metadata.analyzed_parts) << nl;
        oss << indent << "}," << nl;

        // Stress history
        oss << indent << "\"stress_history\": " << partStatsArrayToJSON(stress_history, pretty, indent) << "," << nl;

        // Strain history
        oss << indent << "\"strain_history\": " << partStatsArrayToJSON(strain_history, pretty, indent) << "," << nl;

        // Acceleration history
        oss << indent << "\"acceleration_history\": " << partStatsArrayToJSON(acceleration_history, pretty, indent) << "," << nl;

        // Surface analysis
        oss << indent << "\"surface_analysis\": " << surfaceStatsArrayToJSON(surface_analysis, pretty, indent) << nl;

        oss << "}";

        return oss.str();
    }

    /**
     * @brief Save to JSON file
     * @param filepath Output file path
     * @return true if successful
     */
    bool saveToFile(const std::string& filepath) const {
        std::ofstream file(filepath);
        if (!file) {
            return false;
        }
        file << toJSON(true);
        file.close();
        return true;
    }

    /**
     * @brief Load from JSON file
     * @param filepath Input file path
     * @return AnalysisResult loaded from file
     * @throws std::runtime_error on parse error
     *
     * Note: This is a simplified parser. For production use, consider using
     * a proper JSON library like nlohmann/json.
     */
    static AnalysisResult loadFromFile(const std::string& filepath) {
        std::ifstream file(filepath);
        if (!file) {
            throw std::runtime_error("Cannot open file: " + filepath);
        }

        std::stringstream buffer;
        buffer << file.rdbuf();
        std::string json = buffer.str();

        return parseJSON(json);
    }

    // ============================================================
    // CSV Export (Convenience Methods)
    // ============================================================

    /**
     * @brief Export stress history to CSV
     * @param filepath Output file path
     * @return true if successful
     */
    bool exportStressToCSV(const std::string& filepath) const {
        return exportPartStatsToCSV(stress_history, filepath);
    }

    /**
     * @brief Export strain history to CSV
     * @param filepath Output file path
     * @return true if successful
     */
    bool exportStrainToCSV(const std::string& filepath) const {
        return exportPartStatsToCSV(strain_history, filepath);
    }

    /**
     * @brief Export surface analysis to CSV
     * @param filepath Output file path
     * @return true if successful
     */
    bool exportSurfaceToCSV(const std::string& filepath) const {
        if (surface_analysis.empty()) return false;

        std::ofstream file(filepath);
        if (!file) return false;

        // Header
        file << "Time";
        for (size_t i = 0; i < surface_analysis.size(); ++i) {
            file << ",Surface" << i << "_NormalMax";
            file << ",Surface" << i << "_NormalAvg";
            file << ",Surface" << i << "_ShearMax";
            file << ",Surface" << i << "_ShearAvg";
        }
        file << "\n";

        // Find maximum number of time points
        size_t max_points = 0;
        for (const auto& surf : surface_analysis) {
            if (surf.data.size() > max_points) max_points = surf.data.size();
        }

        // Data rows
        for (size_t t = 0; t < max_points; ++t) {
            bool first = true;
            for (const auto& surf : surface_analysis) {
                if (t < surf.data.size()) {
                    if (first) {
                        file << std::fixed << std::setprecision(8) << surf.data[t].time;
                        first = false;
                    }
                    file << "," << surf.data[t].normal_stress_max;
                    file << "," << surf.data[t].normal_stress_avg;
                    file << "," << surf.data[t].shear_stress_max;
                    file << "," << surf.data[t].shear_stress_avg;
                } else {
                    file << ",,,,";
                }
            }
            file << "\n";
        }

        return true;
    }

private:
    // ============================================================
    // JSON Helper Functions
    // ============================================================

    static std::string escapeJSON(const std::string& str) {
        std::ostringstream oss;
        for (char c : str) {
            switch (c) {
                case '"': oss << "\\\""; break;
                case '\\': oss << "\\\\"; break;
                case '\n': oss << "\\n"; break;
                case '\r': oss << "\\r"; break;
                case '\t': oss << "\\t"; break;
                default: oss << c;
            }
        }
        return oss.str();
    }

    template<typename T>
    static std::string arrayToJSON(const std::vector<T>& arr) {
        std::ostringstream oss;
        oss << "[";
        for (size_t i = 0; i < arr.size(); ++i) {
            if (i > 0) oss << ", ";
            oss << arr[i];
        }
        oss << "]";
        return oss.str();
    }

    static std::string vec3ToJSON(const Vec3& v) {
        std::ostringstream oss;
        oss << std::fixed << std::setprecision(6);
        oss << "[" << v.x << ", " << v.y << ", " << v.z << "]";
        return oss.str();
    }

    static std::string timePointToJSON(const TimePointStats& tp, const std::string& indent) {
        std::ostringstream oss;
        oss << std::fixed << std::setprecision(8);
        oss << "{";
        oss << "\"time\": " << tp.time << ", ";
        oss << "\"max\": " << tp.max_value << ", ";
        oss << "\"min\": " << tp.min_value << ", ";
        oss << "\"avg\": " << tp.avg_value << ", ";
        oss << "\"max_element_id\": " << tp.max_element_id << ", ";
        oss << "\"min_element_id\": " << tp.min_element_id;
        oss << "}";
        return oss.str();
    }

    static std::string partStatsToJSON(const PartTimeSeriesStats& stats, bool pretty, const std::string& base_indent) {
        std::ostringstream oss;
        std::string nl = pretty ? "\n" : "";
        std::string ind = base_indent;
        std::string ind2 = ind + (pretty ? "  " : "");
        std::string ind3 = ind2 + (pretty ? "  " : "");

        oss << "{" << nl;
        oss << ind2 << "\"part_id\": " << stats.part_id << "," << nl;
        oss << ind2 << "\"part_name\": \"" << escapeJSON(stats.part_name) << "\"," << nl;
        oss << ind2 << "\"quantity\": \"" << stats.quantity << "\"," << nl;
        oss << ind2 << "\"unit\": \"" << stats.unit << "\"," << nl;
        oss << ind2 << "\"num_points\": " << stats.data.size() << "," << nl;

        if (!stats.data.empty()) {
            oss << ind2 << "\"global_max\": " << std::fixed << std::setprecision(8) << stats.globalMax() << "," << nl;
            oss << ind2 << "\"global_min\": " << stats.globalMin() << "," << nl;
            oss << ind2 << "\"time_of_max\": " << stats.timeOfGlobalMax() << "," << nl;
        }

        oss << ind2 << "\"data\": [";

        // Limit output for readability (first 10, last 10 if > 20)
        size_t n = stats.data.size();
        if (n <= 20 || !pretty) {
            for (size_t i = 0; i < n; ++i) {
                if (i > 0) oss << ", ";
                if (pretty) oss << nl << ind3;
                oss << timePointToJSON(stats.data[i], ind3);
            }
        } else {
            // Show first 10
            for (size_t i = 0; i < 10; ++i) {
                if (i > 0) oss << ", ";
                oss << nl << ind3 << timePointToJSON(stats.data[i], ind3);
            }
            oss << "," << nl << ind3 << "\"...(omitted " << (n - 20) << " entries)...\"";
            // Show last 10
            for (size_t i = n - 10; i < n; ++i) {
                oss << "," << nl << ind3 << timePointToJSON(stats.data[i], ind3);
            }
        }

        if (pretty && !stats.data.empty()) oss << nl << ind2;
        oss << "]" << nl;
        oss << ind << "}";

        return oss.str();
    }

    static std::string partStatsArrayToJSON(const std::vector<PartTimeSeriesStats>& arr, bool pretty, const std::string& indent) {
        std::ostringstream oss;
        std::string nl = pretty ? "\n" : "";

        oss << "[";
        for (size_t i = 0; i < arr.size(); ++i) {
            if (i > 0) oss << ",";
            if (pretty) oss << nl << indent << "  ";
            oss << partStatsToJSON(arr[i], pretty, indent + "  ");
        }
        if (pretty && !arr.empty()) oss << nl << indent;
        oss << "]";

        return oss.str();
    }

    static std::string surfaceTimePointToJSON(const SurfaceTimePointStats& tp) {
        std::ostringstream oss;
        oss << std::fixed << std::setprecision(8);
        oss << "{";
        oss << "\"time\": " << tp.time << ", ";
        oss << "\"normal_stress\": {";
        oss << "\"max\": " << tp.normal_stress_max << ", ";
        oss << "\"min\": " << tp.normal_stress_min << ", ";
        oss << "\"avg\": " << tp.normal_stress_avg << ", ";
        oss << "\"max_element_id\": " << tp.normal_stress_max_element_id << "}, ";
        oss << "\"shear_stress\": {";
        oss << "\"max\": " << tp.shear_stress_max << ", ";
        oss << "\"avg\": " << tp.shear_stress_avg << ", ";
        oss << "\"max_element_id\": " << tp.shear_stress_max_element_id << "}";
        oss << "}";
        return oss.str();
    }

    static std::string surfaceStatsToJSON(const SurfaceAnalysisStats& stats, bool pretty, const std::string& base_indent) {
        std::ostringstream oss;
        std::string nl = pretty ? "\n" : "";
        std::string ind = base_indent;
        std::string ind2 = ind + (pretty ? "  " : "");
        std::string ind3 = ind2 + (pretty ? "  " : "");

        oss << "{" << nl;
        oss << ind2 << "\"description\": \"" << escapeJSON(stats.description) << "\"," << nl;
        oss << ind2 << "\"reference_direction\": " << vec3ToJSON(stats.reference_direction) << "," << nl;
        oss << ind2 << "\"angle_threshold_degrees\": " << stats.angle_threshold_degrees << "," << nl;
        oss << ind2 << "\"part_ids\": " << arrayToJSON(stats.part_ids) << "," << nl;
        oss << ind2 << "\"num_faces\": " << stats.num_faces << "," << nl;
        oss << ind2 << "\"data\": [";

        size_t n = stats.data.size();
        if (n <= 20 || !pretty) {
            for (size_t i = 0; i < n; ++i) {
                if (i > 0) oss << ", ";
                if (pretty) oss << nl << ind3;
                oss << surfaceTimePointToJSON(stats.data[i]);
            }
        } else {
            for (size_t i = 0; i < 10; ++i) {
                if (i > 0) oss << ", ";
                oss << nl << ind3 << surfaceTimePointToJSON(stats.data[i]);
            }
            oss << "," << nl << ind3 << "\"...(omitted " << (n - 20) << " entries)...\"";
            for (size_t i = n - 10; i < n; ++i) {
                oss << "," << nl << ind3 << surfaceTimePointToJSON(stats.data[i]);
            }
        }

        if (pretty && !stats.data.empty()) oss << nl << ind2;
        oss << "]" << nl;
        oss << ind << "}";

        return oss.str();
    }

    static std::string surfaceStatsArrayToJSON(const std::vector<SurfaceAnalysisStats>& arr, bool pretty, const std::string& indent) {
        std::ostringstream oss;
        std::string nl = pretty ? "\n" : "";

        oss << "[";
        for (size_t i = 0; i < arr.size(); ++i) {
            if (i > 0) oss << ",";
            if (pretty) oss << nl << indent << "  ";
            oss << surfaceStatsToJSON(arr[i], pretty, indent + "  ");
        }
        if (pretty && !arr.empty()) oss << nl << indent;
        oss << "]";

        return oss.str();
    }

    // CSV export helper
    bool exportPartStatsToCSV(const std::vector<PartTimeSeriesStats>& stats, const std::string& filepath) const {
        if (stats.empty()) return false;

        std::ofstream file(filepath);
        if (!file) return false;

        // Header
        file << "Time";
        for (const auto& part : stats) {
            file << ",Part" << part.part_id << "_Max";
            file << ",Part" << part.part_id << "_Min";
            file << ",Part" << part.part_id << "_Avg";
        }
        file << "\n";

        // Find maximum number of time points
        size_t max_points = 0;
        for (const auto& part : stats) {
            if (part.data.size() > max_points) max_points = part.data.size();
        }

        // Data rows
        for (size_t t = 0; t < max_points; ++t) {
            bool first = true;
            for (const auto& part : stats) {
                if (t < part.data.size()) {
                    if (first) {
                        file << std::fixed << std::setprecision(8) << part.data[t].time;
                        first = false;
                    }
                    file << "," << part.data[t].max_value;
                    file << "," << part.data[t].min_value;
                    file << "," << part.data[t].avg_value;
                } else {
                    file << ",,,";
                }
            }
            file << "\n";
        }

        return true;
    }

    // Simplified JSON parser (placeholder - use proper library for production)
    static AnalysisResult parseJSON(const std::string& json) {
        // This is a placeholder. For production use, implement a proper parser
        // or use nlohmann/json library.
        AnalysisResult result;
        // TODO: Implement JSON parsing
        (void)json;  // Suppress unused warning
        return result;
    }
};

} // namespace analysis
} // namespace kood3plot
