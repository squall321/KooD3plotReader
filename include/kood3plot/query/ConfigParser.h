/**
 * @file ConfigParser.h
 * @brief YAML/JSON configuration file parser for V3 Query System
 * @author KooD3plot V3 Development Team
 * @date 2025-11-22
 * @version 3.0.0
 *
 * Provides configuration file parsing for query specifications.
 * Supports both YAML and JSON formats.
 */

#pragma once

#include <string>
#include <memory>
#include <vector>
#include <map>
#include <variant>
#include <optional>
#include <limits>

namespace kood3plot {
namespace query {

// Forward declarations
class PartSelector;
class QuantitySelector;
class TimeSelector;
class ValueFilter;
class OutputSpec;
class SpatialSelector;

/**
 * @brief Configuration value types
 */
using ConfigValue = std::variant<
    std::nullptr_t,
    bool,
    int64_t,
    double,
    std::string,
    std::vector<std::string>,
    std::vector<double>,
    std::vector<int64_t>
>;

/**
 * @brief Configuration node for hierarchical config
 */
class ConfigNode {
public:
    ConfigNode();
    ~ConfigNode();
    ConfigNode(const ConfigNode& other);
    ConfigNode(ConfigNode&& other) noexcept;
    ConfigNode& operator=(const ConfigNode& other);
    ConfigNode& operator=(ConfigNode&& other) noexcept;

    // Value access
    bool isNull() const;
    bool isScalar() const;
    bool isArray() const;
    bool isMap() const;

    // Get scalar values
    bool asBool(bool default_val = false) const;
    int64_t asInt(int64_t default_val = 0) const;
    double asDouble(double default_val = 0.0) const;
    std::string asString(const std::string& default_val = "") const;

    // Get array values
    std::vector<std::string> asStringArray() const;
    std::vector<double> asDoubleArray() const;
    std::vector<int64_t> asIntArray() const;

    // Map access
    bool hasKey(const std::string& key) const;
    ConfigNode operator[](const std::string& key) const;
    ConfigNode operator[](size_t index) const;
    std::vector<std::string> keys() const;
    size_t size() const;

    // Iteration support
    class Iterator;
    Iterator begin() const;
    Iterator end() const;

    // Internal use
    void setValue(const ConfigValue& val);
    void setChild(const std::string& key, const ConfigNode& child);
    void appendChild(const ConfigNode& child);

private:
    struct Impl;
    std::unique_ptr<Impl> pImpl;
};

/**
 * @brief Query configuration structure
 *
 * Represents a complete query specification from config file.
 */
struct QueryConfig {
    // File info
    std::string d3plot_path;
    std::vector<std::string> d3plot_files;

    // Selectors
    std::vector<std::string> parts;      // Part names/IDs
    std::vector<std::string> quantities; // Quantity names
    std::vector<int> state_indices;      // State indices
    double time_start = 0.0;
    double time_end = -1.0;  // -1 = all
    int time_step = 1;

    // Spatial selection
    bool has_spatial = false;
    std::string spatial_type;
    std::vector<double> spatial_params;

    // Filters
    double min_value = std::numeric_limits<double>::lowest();
    double max_value = std::numeric_limits<double>::max();

    // Output
    std::string output_path;
    std::string output_format = "csv";  // csv, json, hdf5

    // Template
    std::string template_name;
    std::map<std::string, std::string> template_params;

    // Options
    bool include_metadata = true;
    bool include_statistics = true;
    bool verbose = false;
};

/**
 * @brief Configuration file parser
 *
 * Parses YAML and JSON configuration files for query specifications.
 *
 * Example YAML:
 * @code
 * d3plot: "/path/to/d3plot"
 * parts:
 *   - "Hood"
 *   - "Bumper"
 * quantities:
 *   - "von_mises"
 *   - "displacement"
 * time:
 *   start: 0.0
 *   end: 0.1
 *   step: 2
 * output:
 *   path: "results.csv"
 *   format: "csv"
 * @endcode
 */
class ConfigParser {
public:
    ConfigParser();
    ~ConfigParser();
    ConfigParser(const ConfigParser&) = delete;
    ConfigParser& operator=(const ConfigParser&) = delete;

    // ============================================================
    // Parsing
    // ============================================================

    /**
     * @brief Parse configuration from YAML file
     */
    QueryConfig parseYAML(const std::string& filepath);

    /**
     * @brief Parse configuration from JSON file
     */
    QueryConfig parseJSON(const std::string& filepath);

    /**
     * @brief Parse configuration from YAML string
     */
    QueryConfig parseYAMLString(const std::string& yaml_content);

    /**
     * @brief Parse configuration from JSON string
     */
    QueryConfig parseJSONString(const std::string& json_content);

    /**
     * @brief Auto-detect format and parse
     */
    QueryConfig parse(const std::string& filepath);

    // ============================================================
    // Selector Creation
    // ============================================================

    /**
     * @brief Create PartSelector from config
     */
    PartSelector createPartSelector(const QueryConfig& config);

    /**
     * @brief Create QuantitySelector from config
     */
    QuantitySelector createQuantitySelector(const QueryConfig& config);

    /**
     * @brief Create TimeSelector from config
     */
    TimeSelector createTimeSelector(const QueryConfig& config);

    /**
     * @brief Create ValueFilter from config
     */
    ValueFilter createValueFilter(const QueryConfig& config);

    /**
     * @brief Create OutputSpec from config
     */
    OutputSpec createOutputSpec(const QueryConfig& config);

    /**
     * @brief Create SpatialSelector from config
     */
    SpatialSelector createSpatialSelector(const QueryConfig& config);

    // ============================================================
    // Error Handling
    // ============================================================

    /**
     * @brief Get last error message
     */
    std::string getLastError() const;

    /**
     * @brief Check if last parse was successful
     */
    bool isValid() const;

    /**
     * @brief Get validation warnings
     */
    std::vector<std::string> getWarnings() const;

private:
    struct Impl;
    std::unique_ptr<Impl> pImpl;

    QueryConfig parseNode(const ConfigNode& root);
    void validateConfig(QueryConfig& config);
};

/**
 * @brief Factory functions for config creation
 */
namespace ConfigFactory {

/**
 * @brief Create QueryConfig from command line arguments
 */
QueryConfig fromArgs(int argc, char* argv[]);

/**
 * @brief Create QueryConfig from environment variables
 */
QueryConfig fromEnv();

/**
 * @brief Merge two configurations (second overrides first)
 */
QueryConfig merge(const QueryConfig& base, const QueryConfig& override_cfg);

} // namespace ConfigFactory

} // namespace query
} // namespace kood3plot
