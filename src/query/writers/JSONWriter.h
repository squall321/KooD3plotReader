#pragma once

/**
 * @file JSONWriter.h
 * @brief JSON output writer for the KooD3plot Query System
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 *
 * JSONWriter handles writing query results to JSON format with:
 * - Pretty printing (indentation)
 * - Compact mode for smaller files
 * - Metadata inclusion
 * - Statistics summary
 * - Configurable precision
 *
 * Output format:
 * @code
 * {
 *   "metadata": {
 *     "source_file": "crash.d3plot",
 *     "query_description": "Von Mises stress at last state",
 *     "generated_at": "2025-11-21T12:00:00Z"
 *   },
 *   "statistics": {
 *     "von_mises": { "min": 0.0, "max": 1000.0, "mean": 500.0 }
 *   },
 *   "data": [
 *     {"element_id": 1, "part_id": 1, "time": 0.01, "von_mises": 523.4},
 *     ...
 *   ]
 * }
 * @endcode
 */

#include "kood3plot/query/OutputSpec.h"
#include "kood3plot/query/QueryResult.h"
#include <string>
#include <vector>
#include <map>
#include <fstream>
#include <memory>

namespace kood3plot {
namespace query {
namespace writers {

/**
 * @class JSONWriter
 * @brief Writes query results to JSON files
 */
class JSONWriter {
public:
    // ============================================================
    // Constructors
    // ============================================================

    /**
     * @brief Construct JSON writer for file
     * @param filename Output file path
     */
    explicit JSONWriter(const std::string& filename);

    /**
     * @brief Destructor (closes file if open)
     */
    ~JSONWriter();

    // Delete copy/move constructors for RAII safety
    JSONWriter(const JSONWriter&) = delete;
    JSONWriter& operator=(const JSONWriter&) = delete;
    JSONWriter(JSONWriter&&) = delete;
    JSONWriter& operator=(JSONWriter&&) = delete;

    // ============================================================
    // Configuration
    // ============================================================

    /**
     * @brief Set output specification
     * @param spec Output specification
     */
    void setSpec(const OutputSpec& spec);

    /**
     * @brief Set precision (decimal places)
     * @param precision Number of decimal places
     */
    void setPrecision(int precision);

    /**
     * @brief Enable/disable pretty printing
     * @param enable Enable indented output
     */
    void setPrettyPrint(bool enable);

    /**
     * @brief Set indentation string (for pretty printing)
     * @param indent Indentation string (e.g., "  " or "\t")
     */
    void setIndent(const std::string& indent);

    /**
     * @brief Include statistics in output
     * @param enable Include statistics section
     */
    void setIncludeStatistics(bool enable);

    // ============================================================
    // Writing Methods
    // ============================================================

    /**
     * @brief Write complete QueryResult to JSON
     * @param result Query result to write
     *
     * This is the main method - writes metadata, statistics, and data.
     */
    void write(const QueryResult& result);

    /**
     * @brief Write metadata section
     * @param metadata Map of metadata key-value pairs
     */
    void writeMetadata(const std::map<std::string, std::string>& metadata);

    /**
     * @brief Write statistics section
     * @param stats Map of quantity name to statistics
     */
    void writeStatistics(const std::map<std::string, QuantityStatistics>& stats);

    /**
     * @brief Write data array
     * @param data_points Vector of data points
     */
    void writeData(const std::vector<ResultDataPoint>& data_points);

    /**
     * @brief Flush buffer to disk
     */
    void flush();

    /**
     * @brief Close file
     */
    void close();

    // ============================================================
    // Query Methods
    // ============================================================

    /**
     * @brief Check if file is open
     * @return true if file is open
     */
    bool isOpen() const;

    /**
     * @brief Get output filename
     * @return Filename
     */
    std::string getFilename() const;

private:
    // ============================================================
    // Private Implementation
    // ============================================================

    struct Impl;
    std::unique_ptr<Impl> pImpl;

    // ============================================================
    // Private Helper Methods
    // ============================================================

    /**
     * @brief Format double value according to precision
     */
    std::string formatDouble(double value) const;

    /**
     * @brief Escape JSON string
     */
    std::string escapeString(const std::string& str) const;

    /**
     * @brief Write indentation
     */
    void writeIndent(int level);

    /**
     * @brief Write JSON value (double)
     */
    void writeValue(double value);

    /**
     * @brief Write JSON value (string)
     */
    void writeValue(const std::string& value);

    /**
     * @brief Write JSON value (integer)
     */
    void writeValue(int32_t value);
};

} // namespace writers
} // namespace query
} // namespace kood3plot
