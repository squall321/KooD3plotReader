#pragma once

/**
 * @file OutputSpec.h
 * @brief Output specification interface for the KooD3plot Query System
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 *
 * OutputSpec provides flexible configuration for query result output:
 * - Format selection (CSV, JSON, HDF5, Parquet)
 * - Field selection (which columns to include)
 * - Aggregation methods (min, max, mean, sum, etc.)
 * - Formatting options (precision, scientific notation)
 * - Coordinate systems (global, part-local, element-local)
 * - Units specification
 * - Header and metadata options
 *
 * Example usage:
 * @code
 * OutputSpec spec;
 * spec.format(OutputFormat::CSV)
 *     .precision(6)
 *     .includeHeader(true)
 *     .includeMetadata(true)
 *     .fields({"part_id", "element_id", "von_mises", "time"});
 * @endcode
 */

#include "QueryTypes.h"
#include <vector>
#include <string>
#include <optional>
#include <map>

namespace kood3plot {
namespace query {

/**
 * @class OutputSpec
 * @brief Specifies how query results should be formatted and written
 *
 * This class configures all aspects of output generation:
 * - File format and compression
 * - Data fields and ordering
 * - Numerical formatting
 * - Aggregation and reduction
 * - Metadata inclusion
 */
class OutputSpec {
public:
    // ============================================================
    // Constructors
    // ============================================================

    /**
     * @brief Default constructor (CSV format, default settings)
     */
    OutputSpec();

    /**
     * @brief Copy constructor
     */
    OutputSpec(const OutputSpec& other);

    /**
     * @brief Move constructor
     */
    OutputSpec(OutputSpec&& other) noexcept;

    /**
     * @brief Assignment operator
     */
    OutputSpec& operator=(const OutputSpec& other);

    /**
     * @brief Move assignment operator
     */
    OutputSpec& operator=(OutputSpec&& other) noexcept;

    /**
     * @brief Destructor
     */
    ~OutputSpec();

    // ============================================================
    // Format Selection
    // ============================================================

    /**
     * @brief Set output format
     * @param fmt Output format (CSV, JSON, HDF5, Parquet)
     * @return Reference to this spec for method chaining
     *
     * Example:
     * @code
     * spec.format(OutputFormat::CSV);
     * spec.format(OutputFormat::JSON);
     * @endcode
     */
    OutputSpec& format(OutputFormat fmt);

    /**
     * @brief Enable compression
     * @param enable Enable/disable compression
     * @return Reference to this spec
     *
     * Compression method depends on format:
     * - CSV: gzip
     * - JSON: gzip
     * - HDF5: built-in compression
     * - Parquet: snappy
     */
    OutputSpec& compress(bool enable = true);

    // ============================================================
    // Field Selection
    // ============================================================

    /**
     * @brief Set output fields (columns)
     * @param field_names List of field names to include
     * @return Reference to this spec
     *
     * Standard field names:
     * - "part_id", "part_name"
     * - "element_id", "element_type"
     * - "node_id"
     * - "time", "state_index"
     * - "x", "y", "z" (coordinates)
     * - Quantity names (e.g., "von_mises", "effective_strain")
     *
     * Example:
     * @code
     * spec.fields({"part_id", "element_id", "von_mises", "time"});
     * @endcode
     */
    OutputSpec& fields(const std::vector<std::string>& field_names);

    /**
     * @brief Add single field to output
     * @param field_name Field name to add
     * @return Reference to this spec
     */
    OutputSpec& addField(const std::string& field_name);

    /**
     * @brief Include all available fields
     * @return Reference to this spec
     */
    OutputSpec& allFields();

    /**
     * @brief Include default fields for common crash analysis
     * @return Reference to this spec
     *
     * Includes: part_id, element_id, time, von_mises, effective_strain, displacement
     */
    OutputSpec& defaultFields();

    // ============================================================
    // Aggregation Methods
    // ============================================================

    /**
     * @brief Set aggregation method
     * @param agg Aggregation type (NONE, MIN, MAX, MEAN, SUM, etc.)
     * @return Reference to this spec
     *
     * Aggregation reduces multiple values to single value:
     * - NONE: No aggregation (all values)
     * - MIN: Minimum value over time/elements
     * - MAX: Maximum value over time/elements
     * - MEAN: Average value
     * - SUM: Sum of values
     * - FIRST: First value encountered
     * - LAST: Last value encountered
     *
     * Example:
     * @code
     * spec.aggregation(AggregationType::MAX);  // Max von_mises over time
     * @endcode
     */
    OutputSpec& aggregation(AggregationType agg);

    /**
     * @brief Set per-field aggregation methods
     * @param field_agg_map Map of field name to aggregation type
     * @return Reference to this spec
     *
     * Example:
     * @code
     * spec.perFieldAggregation({
     *     {"von_mises", AggregationType::MAX},
     *     {"effective_strain", AggregationType::MAX},
     *     {"displacement", AggregationType::LAST}
     * });
     * @endcode
     */
    OutputSpec& perFieldAggregation(const std::map<std::string, AggregationType>& field_agg_map);

    // ============================================================
    // Numerical Formatting
    // ============================================================

    /**
     * @brief Set numerical precision (decimal places)
     * @param prec Number of decimal places
     * @return Reference to this spec
     *
     * Example:
     * @code
     * spec.precision(6);  // 123.456789
     * spec.precision(2);  // 123.46
     * @endcode
     */
    OutputSpec& precision(int prec);

    /**
     * @brief Use scientific notation
     * @param enable Enable/disable scientific notation
     * @return Reference to this spec
     *
     * Example:
     * @code
     * spec.scientificNotation(true);  // 1.234568e+02
     * @endcode
     */
    OutputSpec& scientificNotation(bool enable = true);

    /**
     * @brief Use fixed-point notation
     * @param enable Enable/disable fixed-point notation
     * @return Reference to this spec
     *
     * Example:
     * @code
     * spec.fixedNotation(true);  // 123.456789
     * @endcode
     */
    OutputSpec& fixedNotation(bool enable = true);

    // ============================================================
    // Coordinate Systems
    // ============================================================

    /**
     * @brief Set coordinate system for output
     * @param coord_sys Coordinate system (GLOBAL, PART_LOCAL, ELEMENT_LOCAL)
     * @return Reference to this spec
     *
     * Example:
     * @code
     * spec.coordinateSystem(CoordinateSystem::GLOBAL);
     * @endcode
     */
    OutputSpec& coordinateSystem(CoordinateSystem coord_sys);

    // ============================================================
    // Units
    // ============================================================

    /**
     * @brief Set length unit
     * @param unit Length unit (mm, m, in, etc.)
     * @return Reference to this spec
     */
    OutputSpec& lengthUnit(const std::string& unit);

    /**
     * @brief Set time unit
     * @param unit Time unit (ms, s, us, etc.)
     * @return Reference to this spec
     */
    OutputSpec& timeUnit(const std::string& unit);

    /**
     * @brief Set stress unit
     * @param unit Stress unit (MPa, Pa, psi, etc.)
     * @return Reference to this spec
     */
    OutputSpec& stressUnit(const std::string& unit);

    /**
     * @brief Set mass unit
     * @param unit Mass unit (kg, g, ton, etc.)
     * @return Reference to this spec
     */
    OutputSpec& massUnit(const std::string& unit);

    // ============================================================
    // Header and Metadata
    // ============================================================

    /**
     * @brief Include header row (for CSV/table formats)
     * @param include Include/exclude header
     * @return Reference to this spec
     */
    OutputSpec& includeHeader(bool include = true);

    /**
     * @brief Include metadata section
     * @param include Include/exclude metadata
     * @return Reference to this spec
     *
     * Metadata includes:
     * - Query specification (parts, quantities, time range)
     * - D3plot file information
     * - Generation timestamp
     * - Units
     * - Coordinate system
     */
    OutputSpec& includeMetadata(bool include = true);

    /**
     * @brief Include statistics in output (JSON only)
     * @param include Enable/disable statistics section
     * @return Reference to this spec
     *
     * When enabled, JSON output includes a statistics section with
     * min, max, mean, std_dev, sum, median for each quantity.
     */
    OutputSpec& includeStatisticsSection(bool include = true);

    /**
     * @brief Add custom metadata field
     * @param key Metadata key
     * @param value Metadata value
     * @return Reference to this spec
     */
    OutputSpec& addMetadata(const std::string& key, const std::string& value);

    // ============================================================
    // CSV-Specific Options
    // ============================================================

    /**
     * @brief Set CSV delimiter
     * @param delimiter Delimiter character (default: ',')
     * @return Reference to this spec
     *
     * Example:
     * @code
     * spec.csvDelimiter(',');   // Comma-separated
     * spec.csvDelimiter('\t');  // Tab-separated
     * @endcode
     */
    OutputSpec& csvDelimiter(char delimiter);

    /**
     * @brief Set CSV quote character
     * @param quote Quote character for strings (default: '"')
     * @return Reference to this spec
     */
    OutputSpec& csvQuote(char quote);

    // ============================================================
    // JSON-Specific Options
    // ============================================================

    /**
     * @brief Pretty-print JSON output
     * @param enable Enable/disable pretty printing
     * @return Reference to this spec
     */
    OutputSpec& jsonPrettyPrint(bool enable = true);

    /**
     * @brief Set JSON indentation size
     * @param spaces Number of spaces for indentation
     * @return Reference to this spec
     */
    OutputSpec& jsonIndent(int spaces);

    // ============================================================
    // Query Methods
    // ============================================================

    /**
     * @brief Get output format
     * @return Output format
     */
    OutputFormat getFormat() const;

    /**
     * @brief Get selected fields
     * @return Vector of field names
     */
    std::vector<std::string> getFields() const;

    /**
     * @brief Get aggregation type
     * @return Aggregation type
     */
    AggregationType getAggregation() const;

    /**
     * @brief Get aggregation for specific field
     * @param field_name Field name
     * @return Aggregation type for field (or default if not specified)
     */
    AggregationType getFieldAggregation(const std::string& field_name) const;

    /**
     * @brief Get numerical precision
     * @return Number of decimal places
     */
    int getPrecision() const;

    /**
     * @brief Check if compression is enabled
     * @return true if compression enabled
     */
    bool isCompressed() const;

    /**
     * @brief Check if header should be included
     * @return true if header should be included
     */
    bool hasHeader() const;

    /**
     * @brief Check if metadata should be included
     * @return true if metadata should be included
     */
    bool hasMetadata() const;

    /**
     * @brief Check if statistics should be included
     * @return true if statistics section should be included
     */
    bool includeStatistics() const;

    /**
     * @brief Get coordinate system
     * @return Coordinate system
     */
    CoordinateSystem getCoordinateSystem() const;

    /**
     * @brief Get all units
     * @return Map of unit types to unit strings
     */
    std::map<std::string, std::string> getUnits() const;

    /**
     * @brief Get description of output spec (for debugging)
     * @return String describing the output specification
     */
    std::string getDescription() const;

    // ============================================================
    // Validation
    // ============================================================

    /**
     * @brief Validate output specification
     * @return true if specification is valid
     *
     * Checks:
     * - At least one field is specified
     * - Format is supported
     * - Field names are valid
     */
    bool validate() const;

    /**
     * @brief Get validation errors
     * @return Vector of error messages (empty if valid)
     */
    std::vector<std::string> getValidationErrors() const;

    // ============================================================
    // Static Factory Methods
    // ============================================================

    /**
     * @brief Create CSV output spec with default settings
     * @return OutputSpec configured for CSV
     */
    static OutputSpec csv();

    /**
     * @brief Create JSON output spec with default settings
     * @return OutputSpec configured for JSON
     */
    static OutputSpec json();

    /**
     * @brief Create HDF5 output spec with default settings
     * @return OutputSpec configured for HDF5
     */
    static OutputSpec hdf5();

    /**
     * @brief Create output spec for crash analysis
     * @return OutputSpec with common crash analysis fields
     */
    static OutputSpec crashAnalysis();

    /**
     * @brief Create minimal output spec (part_id, element_id, value)
     * @return OutputSpec with minimal fields
     */
    static OutputSpec minimal();

private:
    // ============================================================
    // Private Implementation
    // ============================================================

    /**
     * @brief Implementation struct (PIMPL pattern)
     */
    struct Impl;
    std::unique_ptr<Impl> pImpl;
};

} // namespace query
} // namespace kood3plot
