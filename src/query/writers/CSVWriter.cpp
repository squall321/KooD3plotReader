/**
 * @file CSVWriter.cpp
 * @brief Implementation of CSVWriter class
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 */

#include "CSVWriter.h"
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <algorithm>

namespace kood3plot {
namespace query {
namespace writers {

// ============================================================
// PIMPL Implementation Struct
// ============================================================

/**
 * @brief Implementation details for CSVWriter
 */
struct CSVWriter::Impl {
    /// Output file stream
    std::ofstream file;

    /// Output filename
    std::string filename;

    /// CSV delimiter
    char delimiter = ',';

    /// CSV quote character
    char quote = '"';

    /// Numerical precision
    int precision = 6;

    /// Use scientific notation
    bool scientific = false;

    /// Compression enabled (not yet implemented)
    bool compressed = false;

    /// Row counter
    size_t row_count = 0;

    /**
     * @brief Check if file is open
     */
    bool isOpen() const {
        return file.is_open();
    }
};

// ============================================================
// Constructors and Destructor
// ============================================================

CSVWriter::CSVWriter(const std::string& filename)
    : pImpl(std::make_unique<Impl>())
{
    pImpl->filename = filename;
    pImpl->file.open(filename);

    if (!pImpl->file.is_open()) {
        throw std::runtime_error("Failed to open CSV file for writing: " + filename);
    }
}

CSVWriter::~CSVWriter() {
    if (pImpl && pImpl->isOpen()) {
        close();
    }
}

// ============================================================
// Configuration
// ============================================================

void CSVWriter::setSpec(const OutputSpec& spec) {
    pImpl->precision = spec.getPrecision();

    // Get CSV-specific settings from spec
    // Note: OutputSpec doesn't expose these yet, using defaults
    pImpl->delimiter = ',';  // TODO: Get from spec
    pImpl->quote = '"';      // TODO: Get from spec
    pImpl->compressed = spec.isCompressed();
}

void CSVWriter::setDelimiter(char delimiter) {
    pImpl->delimiter = delimiter;
}

void CSVWriter::setPrecision(int precision) {
    pImpl->precision = std::max(0, std::min(precision, 15));
}

void CSVWriter::setCompression(bool enable) {
    if (enable && pImpl->row_count > 0) {
        throw std::runtime_error("Cannot enable compression after writing has started");
    }
    pImpl->compressed = enable;
    // TODO: Implement gzip compression in Phase 2
}

// ============================================================
// Writing Methods
// ============================================================

void CSVWriter::writeMetadata(const std::map<std::string, std::string>& metadata) {
    if (!pImpl->isOpen()) {
        throw std::runtime_error("File is not open");
    }

    for (const auto& [key, value] : metadata) {
        writeLine("# " + key + ": " + value);
    }

    // Add blank line after metadata
    if (!metadata.empty()) {
        writeLine("#");
    }
}

void CSVWriter::writeHeader(const std::vector<std::string>& headers) {
    if (!pImpl->isOpen()) {
        throw std::runtime_error("File is not open");
    }

    if (headers.empty()) {
        return;
    }

    std::ostringstream oss;
    for (size_t i = 0; i < headers.size(); ++i) {
        if (i > 0) {
            oss << pImpl->delimiter;
        }
        oss << headers[i];  // Column names don't need quoting
    }

    writeLine(oss.str());
}

void CSVWriter::writeRow(const std::vector<double>& values) {
    if (!pImpl->isOpen()) {
        throw std::runtime_error("File is not open");
    }

    if (values.empty()) {
        return;
    }

    std::ostringstream oss;
    for (size_t i = 0; i < values.size(); ++i) {
        if (i > 0) {
            oss << pImpl->delimiter;
        }
        oss << formatDouble(values[i]);
    }

    writeLine(oss.str());
    pImpl->row_count++;
}

void CSVWriter::writeRow(const std::vector<std::string>& values) {
    if (!pImpl->isOpen()) {
        throw std::runtime_error("File is not open");
    }

    if (values.empty()) {
        return;
    }

    std::ostringstream oss;
    for (size_t i = 0; i < values.size(); ++i) {
        if (i > 0) {
            oss << pImpl->delimiter;
        }
        oss << escapeString(values[i]);
    }

    writeLine(oss.str());
    pImpl->row_count++;
}

void CSVWriter::writeRow(const std::vector<int32_t>& int_values,
                        const std::vector<double>& double_values) {
    if (!pImpl->isOpen()) {
        throw std::runtime_error("File is not open");
    }

    std::ostringstream oss;
    bool first = true;

    // Write integer values
    for (int32_t val : int_values) {
        if (!first) oss << pImpl->delimiter;
        oss << val;
        first = false;
    }

    // Write double values
    for (double val : double_values) {
        if (!first) oss << pImpl->delimiter;
        oss << formatDouble(val);
        first = false;
    }

    writeLine(oss.str());
    pImpl->row_count++;
}

void CSVWriter::writeRows(const std::vector<std::vector<double>>& rows) {
    for (const auto& row : rows) {
        writeRow(row);
    }
}

void CSVWriter::write(const QueryResult& result) {
    if (!pImpl->isOpen()) {
        throw std::runtime_error("File is not open");
    }

    if (result.empty()) {
        return;
    }

    // Get data points
    const auto& data_points = result.getDataPoints();
    if (data_points.empty()) {
        return;
    }

    // Determine fields to write
    // Default fields: part_id, element_id, state_index, time, then all value fields
    std::vector<std::string> headers;
    headers.push_back("part_id");
    headers.push_back("element_id");
    headers.push_back("state_index");
    headers.push_back("time");

    // Collect all value field names from first data point
    std::vector<std::string> value_fields;
    if (!data_points.empty()) {
        for (const auto& [key, value] : data_points[0].values) {
            value_fields.push_back(key);
        }
        // Sort for consistent output
        std::sort(value_fields.begin(), value_fields.end());
    }

    for (const auto& field : value_fields) {
        headers.push_back(field);
    }

    // Write header
    writeHeader(headers);

    // Write data rows
    for (const auto& pt : data_points) {
        std::vector<double> row;
        row.push_back(static_cast<double>(pt.part_id));
        row.push_back(static_cast<double>(pt.element_id));
        row.push_back(static_cast<double>(pt.state_index));
        row.push_back(pt.time);

        for (const auto& field : value_fields) {
            auto it = pt.values.find(field);
            if (it != pt.values.end()) {
                row.push_back(it->second);
            } else {
                row.push_back(0.0);  // Default value if field missing
            }
        }

        writeRow(row);
    }
}

void CSVWriter::flush() {
    if (pImpl->isOpen()) {
        pImpl->file.flush();
    }
}

void CSVWriter::close() {
    if (pImpl->isOpen()) {
        pImpl->file.close();
    }
}

// ============================================================
// Query Methods
// ============================================================

bool CSVWriter::isOpen() const {
    return pImpl->isOpen();
}

size_t CSVWriter::getRowCount() const {
    return pImpl->row_count;
}

std::string CSVWriter::getFilename() const {
    return pImpl->filename;
}

// ============================================================
// Private Helper Methods
// ============================================================

std::string CSVWriter::formatDouble(double value) const {
    std::ostringstream oss;

    if (pImpl->scientific) {
        oss << std::scientific;
    } else {
        oss << std::fixed;
    }

    oss << std::setprecision(pImpl->precision) << value;
    return oss.str();
}

std::string CSVWriter::escapeString(const std::string& str) const {
    // Check if string needs quoting
    bool needs_quotes = false;

    if (str.find(pImpl->delimiter) != std::string::npos ||
        str.find(pImpl->quote) != std::string::npos ||
        str.find('\n') != std::string::npos ||
        str.find('\r') != std::string::npos) {
        needs_quotes = true;
    }

    if (!needs_quotes) {
        return str;
    }

    // Build quoted and escaped string
    std::string result;
    result.push_back(pImpl->quote);

    for (char c : str) {
        if (c == pImpl->quote) {
            // Double the quote character to escape it
            result.push_back(pImpl->quote);
            result.push_back(pImpl->quote);
        } else {
            result.push_back(c);
        }
    }

    result.push_back(pImpl->quote);
    return result;
}

void CSVWriter::writeLine(const std::string& line) {
    pImpl->file << line << '\n';
}

} // namespace writers
} // namespace query
} // namespace kood3plot
