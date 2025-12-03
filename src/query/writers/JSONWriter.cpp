/**
 * @file JSONWriter.cpp
 * @brief Implementation of JSONWriter class
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 */

#include "JSONWriter.h"
#include <sstream>
#include <iomanip>
#include <ctime>
#include <chrono>

namespace kood3plot {
namespace query {
namespace writers {

// ============================================================
// PIMPL Implementation Struct
// ============================================================

struct JSONWriter::Impl {
    std::string filename;
    std::ofstream file;
    int precision = 6;
    bool pretty_print = true;
    std::string indent = "  ";
    bool include_statistics = true;
    bool first_element = true;

    Impl(const std::string& fname) : filename(fname) {
        file.open(fname);
    }

    ~Impl() {
        if (file.is_open()) {
            file.close();
        }
    }
};

// ============================================================
// Constructors and Destructor
// ============================================================

JSONWriter::JSONWriter(const std::string& filename)
    : pImpl(std::make_unique<Impl>(filename))
{
}

JSONWriter::~JSONWriter() = default;

// ============================================================
// Configuration
// ============================================================

void JSONWriter::setSpec(const OutputSpec& spec) {
    pImpl->precision = spec.getPrecision();
    pImpl->include_statistics = spec.includeStatistics();
}

void JSONWriter::setPrecision(int precision) {
    pImpl->precision = precision;
}

void JSONWriter::setPrettyPrint(bool enable) {
    pImpl->pretty_print = enable;
}

void JSONWriter::setIndent(const std::string& indent) {
    pImpl->indent = indent;
}

void JSONWriter::setIncludeStatistics(bool enable) {
    pImpl->include_statistics = enable;
}

// ============================================================
// Writing Methods
// ============================================================

void JSONWriter::write(const QueryResult& result) {
    if (!isOpen()) return;

    pImpl->file << "{";
    if (pImpl->pretty_print) pImpl->file << "\n";

    // Write metadata
    writeIndent(1);
    pImpl->file << "\"metadata\": {";
    if (pImpl->pretty_print) pImpl->file << "\n";

    auto all_metadata = result.getAllMetadata();
    all_metadata["source_file"] = result.getSourceFile();
    all_metadata["query_description"] = result.getQueryDescription();
    all_metadata["data_points"] = std::to_string(result.size());

    // Add timestamp
    auto now = std::chrono::system_clock::now();
    auto time = std::chrono::system_clock::to_time_t(now);
    std::ostringstream timestamp;
    timestamp << std::put_time(std::gmtime(&time), "%Y-%m-%dT%H:%M:%SZ");
    all_metadata["generated_at"] = timestamp.str();

    bool first = true;
    for (const auto& [key, value] : all_metadata) {
        if (!first) {
            pImpl->file << ",";
            if (pImpl->pretty_print) pImpl->file << "\n";
        }
        writeIndent(2);
        pImpl->file << "\"" << escapeString(key) << "\": \"" << escapeString(value) << "\"";
        first = false;
    }

    if (pImpl->pretty_print) pImpl->file << "\n";
    writeIndent(1);
    pImpl->file << "},";
    if (pImpl->pretty_print) pImpl->file << "\n";

    // Write statistics
    if (pImpl->include_statistics && !result.empty()) {
        writeIndent(1);
        pImpl->file << "\"statistics\": {";
        if (pImpl->pretty_print) pImpl->file << "\n";

        auto all_stats = result.getAllStatistics();
        first = true;
        for (const auto& [qty_name, stats] : all_stats) {
            if (!first) {
                pImpl->file << ",";
                if (pImpl->pretty_print) pImpl->file << "\n";
            }
            writeIndent(2);
            pImpl->file << "\"" << escapeString(qty_name) << "\": {";
            if (pImpl->pretty_print) pImpl->file << "\n";

            writeIndent(3);
            pImpl->file << "\"min\": " << formatDouble(stats.min_value) << ",";
            if (pImpl->pretty_print) pImpl->file << "\n";

            writeIndent(3);
            pImpl->file << "\"max\": " << formatDouble(stats.max_value) << ",";
            if (pImpl->pretty_print) pImpl->file << "\n";

            writeIndent(3);
            pImpl->file << "\"mean\": " << formatDouble(stats.mean_value) << ",";
            if (pImpl->pretty_print) pImpl->file << "\n";

            writeIndent(3);
            pImpl->file << "\"std_dev\": " << formatDouble(stats.std_dev) << ",";
            if (pImpl->pretty_print) pImpl->file << "\n";

            writeIndent(3);
            pImpl->file << "\"sum\": " << formatDouble(stats.sum) << ",";
            if (pImpl->pretty_print) pImpl->file << "\n";

            writeIndent(3);
            pImpl->file << "\"median\": " << formatDouble(stats.median) << ",";
            if (pImpl->pretty_print) pImpl->file << "\n";

            writeIndent(3);
            pImpl->file << "\"count\": " << stats.count << ",";
            if (pImpl->pretty_print) pImpl->file << "\n";

            writeIndent(3);
            pImpl->file << "\"min_element_id\": " << stats.min_element_id << ",";
            if (pImpl->pretty_print) pImpl->file << "\n";

            writeIndent(3);
            pImpl->file << "\"max_element_id\": " << stats.max_element_id;
            if (pImpl->pretty_print) pImpl->file << "\n";

            writeIndent(2);
            pImpl->file << "}";
            first = false;
        }

        if (pImpl->pretty_print) pImpl->file << "\n";
        writeIndent(1);
        pImpl->file << "},";
        if (pImpl->pretty_print) pImpl->file << "\n";
    }

    // Write data array
    writeIndent(1);
    pImpl->file << "\"data\": [";
    if (pImpl->pretty_print) pImpl->file << "\n";

    const auto& data_points = result.getDataPoints();
    for (size_t i = 0; i < data_points.size(); ++i) {
        const auto& pt = data_points[i];

        writeIndent(2);
        pImpl->file << "{";

        pImpl->file << "\"element_id\": " << pt.element_id;
        pImpl->file << ", \"part_id\": " << pt.part_id;
        pImpl->file << ", \"state_index\": " << pt.state_index;
        pImpl->file << ", \"time\": " << formatDouble(pt.time);

        for (const auto& [qty_name, value] : pt.values) {
            pImpl->file << ", \"" << escapeString(qty_name) << "\": " << formatDouble(value);
        }

        pImpl->file << "}";

        if (i < data_points.size() - 1) {
            pImpl->file << ",";
        }
        if (pImpl->pretty_print) pImpl->file << "\n";
    }

    writeIndent(1);
    pImpl->file << "]";
    if (pImpl->pretty_print) pImpl->file << "\n";

    pImpl->file << "}" << std::endl;
}

void JSONWriter::writeMetadata(const std::map<std::string, std::string>& metadata) {
    // Used when writing metadata separately
    if (!isOpen()) return;

    pImpl->file << "\"metadata\": {";
    if (pImpl->pretty_print) pImpl->file << "\n";

    bool first = true;
    for (const auto& [key, value] : metadata) {
        if (!first) {
            pImpl->file << ",";
            if (pImpl->pretty_print) pImpl->file << "\n";
        }
        writeIndent(1);
        pImpl->file << "\"" << escapeString(key) << "\": \"" << escapeString(value) << "\"";
        first = false;
    }

    if (pImpl->pretty_print) pImpl->file << "\n";
    pImpl->file << "}";
}

void JSONWriter::writeStatistics(const std::map<std::string, QuantityStatistics>& stats) {
    if (!isOpen()) return;

    pImpl->file << "\"statistics\": {";
    if (pImpl->pretty_print) pImpl->file << "\n";

    bool first = true;
    for (const auto& [qty_name, stat] : stats) {
        if (!first) {
            pImpl->file << ",";
            if (pImpl->pretty_print) pImpl->file << "\n";
        }
        writeIndent(1);
        pImpl->file << "\"" << escapeString(qty_name) << "\": {";
        pImpl->file << "\"min\": " << formatDouble(stat.min_value);
        pImpl->file << ", \"max\": " << formatDouble(stat.max_value);
        pImpl->file << ", \"mean\": " << formatDouble(stat.mean_value);
        pImpl->file << "}";
        first = false;
    }

    if (pImpl->pretty_print) pImpl->file << "\n";
    pImpl->file << "}";
}

void JSONWriter::writeData(const std::vector<ResultDataPoint>& data_points) {
    if (!isOpen()) return;

    pImpl->file << "\"data\": [";
    if (pImpl->pretty_print) pImpl->file << "\n";

    for (size_t i = 0; i < data_points.size(); ++i) {
        const auto& pt = data_points[i];

        writeIndent(1);
        pImpl->file << "{";
        pImpl->file << "\"element_id\": " << pt.element_id;
        pImpl->file << ", \"part_id\": " << pt.part_id;
        pImpl->file << ", \"state_index\": " << pt.state_index;
        pImpl->file << ", \"time\": " << formatDouble(pt.time);

        for (const auto& [qty_name, value] : pt.values) {
            pImpl->file << ", \"" << escapeString(qty_name) << "\": " << formatDouble(value);
        }

        pImpl->file << "}";
        if (i < data_points.size() - 1) pImpl->file << ",";
        if (pImpl->pretty_print) pImpl->file << "\n";
    }

    pImpl->file << "]";
}

void JSONWriter::flush() {
    if (pImpl->file.is_open()) {
        pImpl->file.flush();
    }
}

void JSONWriter::close() {
    if (pImpl->file.is_open()) {
        pImpl->file.close();
    }
}

// ============================================================
// Query Methods
// ============================================================

bool JSONWriter::isOpen() const {
    return pImpl->file.is_open();
}

std::string JSONWriter::getFilename() const {
    return pImpl->filename;
}

// ============================================================
// Private Helper Methods
// ============================================================

std::string JSONWriter::formatDouble(double value) const {
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(pImpl->precision) << value;
    return oss.str();
}

std::string JSONWriter::escapeString(const std::string& str) const {
    std::ostringstream oss;
    for (char c : str) {
        switch (c) {
            case '"':  oss << "\\\""; break;
            case '\\': oss << "\\\\"; break;
            case '\b': oss << "\\b"; break;
            case '\f': oss << "\\f"; break;
            case '\n': oss << "\\n"; break;
            case '\r': oss << "\\r"; break;
            case '\t': oss << "\\t"; break;
            default:   oss << c; break;
        }
    }
    return oss.str();
}

void JSONWriter::writeIndent(int level) {
    if (pImpl->pretty_print) {
        for (int i = 0; i < level; ++i) {
            pImpl->file << pImpl->indent;
        }
    }
}

void JSONWriter::writeValue(double value) {
    pImpl->file << formatDouble(value);
}

void JSONWriter::writeValue(const std::string& value) {
    pImpl->file << "\"" << escapeString(value) << "\"";
}

void JSONWriter::writeValue(int32_t value) {
    pImpl->file << value;
}

} // namespace writers
} // namespace query
} // namespace kood3plot
