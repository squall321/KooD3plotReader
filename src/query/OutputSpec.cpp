/**
 * @file OutputSpec.cpp
 * @brief Implementation of OutputSpec class
 * @author KooD3plot V3 Development Team
 * @date 2025-11-21
 * @version 3.0.0
 */

#include "kood3plot/query/OutputSpec.h"
#include <sstream>
#include <algorithm>

namespace kood3plot {
namespace query {

// ============================================================
// PIMPL Implementation Struct
// ============================================================

/**
 * @brief Implementation details for OutputSpec
 */
struct OutputSpec::Impl {
    /// Output format
    OutputFormat format = OutputFormat::CSV;

    /// Compression enabled
    bool compressed = false;

    /// Selected fields
    std::vector<std::string> fields;

    /// Use all fields flag
    bool use_all_fields = false;

    /// Default aggregation method
    AggregationType aggregation = AggregationType::NONE;

    /// Per-field aggregation
    std::map<std::string, AggregationType> field_aggregation;

    /// Numerical precision
    int precision = 6;

    /// Use scientific notation
    bool scientific_notation = false;

    /// Use fixed notation
    bool fixed_notation = false;

    /// Coordinate system
    CoordinateSystem coord_system = CoordinateSystem::GLOBAL;

    /// Units
    std::map<std::string, std::string> units = {
        {"length", "mm"},
        {"time", "ms"},
        {"stress", "MPa"},
        {"mass", "kg"}
    };

    /// Include header
    bool include_header = true;

    /// Include metadata
    bool include_metadata = false;

    /// Custom metadata
    std::map<std::string, std::string> metadata;

    /// CSV delimiter
    char csv_delimiter = ',';

    /// CSV quote character
    char csv_quote = '"';

    /// JSON pretty print
    bool json_pretty = true;

    /// JSON indentation
    int json_indent = 2;

    /// Include statistics section (JSON)
    bool include_statistics = true;
};

// ============================================================
// Constructors and Destructor
// ============================================================

OutputSpec::OutputSpec()
    : pImpl(std::make_unique<Impl>())
{
    // Set default fields
    pImpl->fields = {"part_id", "element_id", "time"};
}

OutputSpec::OutputSpec(const OutputSpec& other)
    : pImpl(std::make_unique<Impl>(*other.pImpl))
{
}

OutputSpec::OutputSpec(OutputSpec&& other) noexcept
    : pImpl(std::move(other.pImpl))
{
}

OutputSpec& OutputSpec::operator=(const OutputSpec& other) {
    if (this != &other) {
        pImpl = std::make_unique<Impl>(*other.pImpl);
    }
    return *this;
}

OutputSpec& OutputSpec::operator=(OutputSpec&& other) noexcept {
    if (this != &other) {
        pImpl = std::move(other.pImpl);
    }
    return *this;
}

OutputSpec::~OutputSpec() = default;

// ============================================================
// Format Selection
// ============================================================

OutputSpec& OutputSpec::format(OutputFormat fmt) {
    pImpl->format = fmt;
    return *this;
}

OutputSpec& OutputSpec::compress(bool enable) {
    pImpl->compressed = enable;
    return *this;
}

// ============================================================
// Field Selection
// ============================================================

OutputSpec& OutputSpec::fields(const std::vector<std::string>& field_names) {
    pImpl->fields = field_names;
    pImpl->use_all_fields = false;
    return *this;
}

OutputSpec& OutputSpec::addField(const std::string& field_name) {
    // Check if field already exists
    auto it = std::find(pImpl->fields.begin(), pImpl->fields.end(), field_name);
    if (it == pImpl->fields.end()) {
        pImpl->fields.push_back(field_name);
    }
    pImpl->use_all_fields = false;
    return *this;
}

OutputSpec& OutputSpec::allFields() {
    pImpl->use_all_fields = true;
    pImpl->fields.clear();
    return *this;
}

OutputSpec& OutputSpec::defaultFields() {
    pImpl->fields = {
        "part_id",
        "element_id",
        "time",
        "von_mises",
        "effective_strain",
        "displacement"
    };
    pImpl->use_all_fields = false;
    return *this;
}

// ============================================================
// Aggregation Methods
// ============================================================

OutputSpec& OutputSpec::aggregation(AggregationType agg) {
    pImpl->aggregation = agg;
    return *this;
}

OutputSpec& OutputSpec::perFieldAggregation(const std::map<std::string, AggregationType>& field_agg_map) {
    pImpl->field_aggregation = field_agg_map;
    return *this;
}

// ============================================================
// Numerical Formatting
// ============================================================

OutputSpec& OutputSpec::precision(int prec) {
    pImpl->precision = std::max(0, std::min(prec, 15));  // Clamp to 0-15
    return *this;
}

OutputSpec& OutputSpec::scientificNotation(bool enable) {
    pImpl->scientific_notation = enable;
    if (enable) {
        pImpl->fixed_notation = false;
    }
    return *this;
}

OutputSpec& OutputSpec::fixedNotation(bool enable) {
    pImpl->fixed_notation = enable;
    if (enable) {
        pImpl->scientific_notation = false;
    }
    return *this;
}

// ============================================================
// Coordinate Systems
// ============================================================

OutputSpec& OutputSpec::coordinateSystem(CoordinateSystem coord_sys) {
    pImpl->coord_system = coord_sys;
    return *this;
}

// ============================================================
// Units
// ============================================================

OutputSpec& OutputSpec::lengthUnit(const std::string& unit) {
    pImpl->units["length"] = unit;
    return *this;
}

OutputSpec& OutputSpec::timeUnit(const std::string& unit) {
    pImpl->units["time"] = unit;
    return *this;
}

OutputSpec& OutputSpec::stressUnit(const std::string& unit) {
    pImpl->units["stress"] = unit;
    return *this;
}

OutputSpec& OutputSpec::massUnit(const std::string& unit) {
    pImpl->units["mass"] = unit;
    return *this;
}

// ============================================================
// Header and Metadata
// ============================================================

OutputSpec& OutputSpec::includeHeader(bool include) {
    pImpl->include_header = include;
    return *this;
}

OutputSpec& OutputSpec::includeMetadata(bool include) {
    pImpl->include_metadata = include;
    return *this;
}

OutputSpec& OutputSpec::includeStatisticsSection(bool include) {
    pImpl->include_statistics = include;
    return *this;
}

OutputSpec& OutputSpec::addMetadata(const std::string& key, const std::string& value) {
    pImpl->metadata[key] = value;
    pImpl->include_metadata = true;  // Auto-enable metadata if adding custom fields
    return *this;
}

// ============================================================
// CSV-Specific Options
// ============================================================

OutputSpec& OutputSpec::csvDelimiter(char delimiter) {
    pImpl->csv_delimiter = delimiter;
    return *this;
}

OutputSpec& OutputSpec::csvQuote(char quote) {
    pImpl->csv_quote = quote;
    return *this;
}

// ============================================================
// JSON-Specific Options
// ============================================================

OutputSpec& OutputSpec::jsonPrettyPrint(bool enable) {
    pImpl->json_pretty = enable;
    return *this;
}

OutputSpec& OutputSpec::jsonIndent(int spaces) {
    pImpl->json_indent = std::max(0, std::min(spaces, 8));  // Clamp to 0-8
    return *this;
}

// ============================================================
// Query Methods
// ============================================================

OutputFormat OutputSpec::getFormat() const {
    return pImpl->format;
}

std::vector<std::string> OutputSpec::getFields() const {
    return pImpl->fields;
}

AggregationType OutputSpec::getAggregation() const {
    return pImpl->aggregation;
}

AggregationType OutputSpec::getFieldAggregation(const std::string& field_name) const {
    auto it = pImpl->field_aggregation.find(field_name);
    if (it != pImpl->field_aggregation.end()) {
        return it->second;
    }
    return pImpl->aggregation;  // Return default if not specified
}

int OutputSpec::getPrecision() const {
    return pImpl->precision;
}

bool OutputSpec::isCompressed() const {
    return pImpl->compressed;
}

bool OutputSpec::hasHeader() const {
    return pImpl->include_header;
}

bool OutputSpec::hasMetadata() const {
    return pImpl->include_metadata;
}

bool OutputSpec::includeStatistics() const {
    return pImpl->include_statistics;
}

CoordinateSystem OutputSpec::getCoordinateSystem() const {
    return pImpl->coord_system;
}

std::map<std::string, std::string> OutputSpec::getUnits() const {
    return pImpl->units;
}

std::string OutputSpec::getDescription() const {
    std::ostringstream oss;

    // Format
    oss << "Format: ";
    switch (pImpl->format) {
        case OutputFormat::CSV:     oss << "CSV"; break;
        case OutputFormat::JSON:    oss << "JSON"; break;
        case OutputFormat::HDF5:    oss << "HDF5"; break;
        case OutputFormat::PARQUET: oss << "Parquet"; break;
        case OutputFormat::BINARY:  oss << "Binary"; break;
        case OutputFormat::XML:     oss << "XML"; break;
        default:                    oss << "Unknown"; break;
    }

    if (pImpl->compressed) {
        oss << " (compressed)";
    }
    oss << "\n";

    // Fields
    oss << "Fields: ";
    if (pImpl->use_all_fields) {
        oss << "All fields";
    } else if (pImpl->fields.empty()) {
        oss << "None specified";
    } else {
        oss << "[";
        for (size_t i = 0; i < pImpl->fields.size(); ++i) {
            if (i > 0) oss << ", ";
            oss << pImpl->fields[i];
        }
        oss << "]";
    }
    oss << "\n";

    // Aggregation
    oss << "Aggregation: ";
    switch (pImpl->aggregation) {
        case AggregationType::NONE:        oss << "None"; break;
        case AggregationType::MIN:         oss << "MIN"; break;
        case AggregationType::MAX:         oss << "MAX"; break;
        case AggregationType::MEAN:        oss << "MEAN"; break;
        case AggregationType::MEDIAN:      oss << "MEDIAN"; break;
        case AggregationType::STDDEV:      oss << "STDDEV"; break;
        case AggregationType::HISTORY:     oss << "HISTORY"; break;
        case AggregationType::SPATIAL_MAX: oss << "SPATIAL_MAX"; break;
        case AggregationType::CUSTOM:      oss << "CUSTOM"; break;
        default:                           oss << "Unknown"; break;
    }
    oss << "\n";

    // Precision
    oss << "Precision: " << pImpl->precision;
    if (pImpl->scientific_notation) {
        oss << " (scientific)";
    } else if (pImpl->fixed_notation) {
        oss << " (fixed)";
    }
    oss << "\n";

    // Coordinate system
    oss << "Coordinate System: ";
    switch (pImpl->coord_system) {
        case CoordinateSystem::GLOBAL:     oss << "Global"; break;
        case CoordinateSystem::LOCAL:      oss << "Element-local"; break;
        case CoordinateSystem::PART_LOCAL: oss << "Part-local"; break;
        default:                           oss << "Unknown"; break;
    }
    oss << "\n";

    // Units
    oss << "Units: length=" << pImpl->units.at("length")
        << ", time=" << pImpl->units.at("time")
        << ", stress=" << pImpl->units.at("stress")
        << "\n";

    // Options
    oss << "Options: ";
    oss << "header=" << (pImpl->include_header ? "yes" : "no");
    oss << ", metadata=" << (pImpl->include_metadata ? "yes" : "no");

    return oss.str();
}

// ============================================================
// Validation
// ============================================================

bool OutputSpec::validate() const {
    return getValidationErrors().empty();
}

std::vector<std::string> OutputSpec::getValidationErrors() const {
    std::vector<std::string> errors;

    // Check if fields are specified (unless use_all_fields is true)
    if (!pImpl->use_all_fields && pImpl->fields.empty()) {
        errors.push_back("No output fields specified");
    }

    // Check if format is supported
    if (pImpl->format != OutputFormat::CSV &&
        pImpl->format != OutputFormat::JSON &&
        pImpl->format != OutputFormat::HDF5 &&
        pImpl->format != OutputFormat::PARQUET) {
        errors.push_back("Unsupported output format");
    }

    // Check precision range
    if (pImpl->precision < 0 || pImpl->precision > 15) {
        errors.push_back("Precision out of range (0-15)");
    }

    // TODO: Add more validation as needed
    // - Field name validation
    // - Unit validation
    // - Format-specific checks

    return errors;
}

// ============================================================
// Static Factory Methods
// ============================================================

OutputSpec OutputSpec::csv() {
    OutputSpec spec;
    spec.format(OutputFormat::CSV)
        .includeHeader(true)
        .precision(6);
    return spec;
}

OutputSpec OutputSpec::json() {
    OutputSpec spec;
    spec.format(OutputFormat::JSON)
        .jsonPrettyPrint(true)
        .precision(6);
    return spec;
}

OutputSpec OutputSpec::hdf5() {
    OutputSpec spec;
    spec.format(OutputFormat::HDF5)
        .compress(true)
        .precision(6);
    return spec;
}

OutputSpec OutputSpec::crashAnalysis() {
    OutputSpec spec;
    spec.format(OutputFormat::CSV)
        .defaultFields()
        .includeHeader(true)
        .includeMetadata(true)
        .precision(6)
        .addMetadata("analysis_type", "crash");
    return spec;
}

OutputSpec OutputSpec::minimal() {
    OutputSpec spec;
    spec.format(OutputFormat::CSV)
        .fields({"part_id", "element_id", "value"})
        .includeHeader(false)
        .precision(6);
    return spec;
}

} // namespace query
} // namespace kood3plot
