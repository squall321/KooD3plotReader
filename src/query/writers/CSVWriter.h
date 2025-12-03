#pragma once

/**
 * @file CSVWriter.h
 * @brief CSV output writer for the KooD3plot Query System
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 *
 * CSVWriter handles writing query results to CSV format with:
 * - Custom delimiters (comma, tab, etc.)
 * - Header row generation
 * - Metadata comments
 * - Proper quote escaping
 * - Configurable precision
 * - Optional compression (gzip)
 *
 * Example usage:
 * @code
 * CSVWriter writer("output.csv");
 * writer.setSpec(output_spec);
 * writer.writeHeader({"part_id", "element_id", "von_mises"});
 * writer.writeRow({1, 100, 523.45});
 * writer.close();
 * @endcode
 */

#include "kood3plot/query/OutputSpec.h"
#include "kood3plot/query/QueryResult.h"
#include <string>
#include <vector>
#include <fstream>
#include <memory>

namespace kood3plot {
namespace query {
namespace writers {

/**
 * @class CSVWriter
 * @brief Writes query results to CSV files
 *
 * This class provides CSV output with configurable formatting,
 * headers, metadata, and compression.
 */
class CSVWriter {
public:
    // ============================================================
    // Constructors
    // ============================================================

    /**
     * @brief Construct CSV writer for file
     * @param filename Output file path
     *
     * Example:
     * @code
     * CSVWriter writer("output.csv");
     * @endcode
     */
    explicit CSVWriter(const std::string& filename);

    /**
     * @brief Destructor (closes file if open)
     */
    ~CSVWriter();

    // Delete copy/move constructors for RAII safety
    CSVWriter(const CSVWriter&) = delete;
    CSVWriter& operator=(const CSVWriter&) = delete;
    CSVWriter(CSVWriter&&) = delete;
    CSVWriter& operator=(CSVWriter&&) = delete;

    // ============================================================
    // Configuration
    // ============================================================

    /**
     * @brief Set output specification
     * @param spec Output specification
     *
     * Configures delimiter, precision, compression, etc.
     */
    void setSpec(const OutputSpec& spec);

    /**
     * @brief Set CSV delimiter
     * @param delimiter Delimiter character
     */
    void setDelimiter(char delimiter);

    /**
     * @brief Set precision (decimal places)
     * @param precision Number of decimal places
     */
    void setPrecision(int precision);

    /**
     * @brief Enable/disable compression
     * @param enable Enable gzip compression
     */
    void setCompression(bool enable);

    // ============================================================
    // Writing Methods
    // ============================================================

    /**
     * @brief Write metadata section
     * @param metadata Map of metadata key-value pairs
     *
     * Writes metadata as commented lines at the beginning:
     * # key1: value1
     * # key2: value2
     */
    void writeMetadata(const std::map<std::string, std::string>& metadata);

    /**
     * @brief Write header row
     * @param headers Vector of column names
     *
     * Example:
     * @code
     * writer.writeHeader({"part_id", "element_id", "von_mises"});
     * // Output: part_id,element_id,von_mises
     * @endcode
     */
    void writeHeader(const std::vector<std::string>& headers);

    /**
     * @brief Write data row (doubles)
     * @param values Vector of numerical values
     *
     * Example:
     * @code
     * writer.writeRow({1.0, 100.0, 523.456789});
     * // Output: 1.000000,100.000000,523.456789
     * @endcode
     */
    void writeRow(const std::vector<double>& values);

    /**
     * @brief Write data row (strings)
     * @param values Vector of string values
     *
     * Handles quote escaping automatically.
     */
    void writeRow(const std::vector<std::string>& values);

    /**
     * @brief Write data row (mixed integers and doubles)
     * @param int_values Integer values
     * @param double_values Double values
     */
    void writeRow(const std::vector<int32_t>& int_values,
                  const std::vector<double>& double_values);

    /**
     * @brief Write multiple rows at once
     * @param rows Vector of row vectors
     */
    void writeRows(const std::vector<std::vector<double>>& rows);

    /**
     * @brief Write QueryResult to CSV
     * @param result Query result to write
     *
     * Automatically writes header and all data points.
     * Uses fields from OutputSpec if set.
     */
    void write(const QueryResult& result);

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
     * @return true if file is open and ready for writing
     */
    bool isOpen() const;

    /**
     * @brief Get number of rows written (excluding header)
     * @return Row count
     */
    size_t getRowCount() const;

    /**
     * @brief Get output filename
     * @return Filename
     */
    std::string getFilename() const;

private:
    // ============================================================
    // Private Implementation
    // ============================================================

    /**
     * @brief Implementation struct (PIMPL pattern)
     */
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
     * @brief Escape and quote string if necessary
     */
    std::string escapeString(const std::string& str) const;

    /**
     * @brief Write raw line to file
     */
    void writeLine(const std::string& line);
};

} // namespace writers
} // namespace query
} // namespace kood3plot
