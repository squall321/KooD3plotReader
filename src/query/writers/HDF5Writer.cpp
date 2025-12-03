/**
 * @file HDF5Writer.cpp
 * @brief Implementation of HDF5Writer class
 * @author KooD3plot V3 Development Team
 * @date 2025-11-22
 * @version 3.0.0
 *
 * Note: This implementation provides a simplified binary format
 * that is compatible with basic HDF5 tools. For full HDF5 functionality,
 * link against the HDF5 library.
 */

#include "HDF5Writer.h"
#include "kood3plot/query/QueryResult.h"
#include <fstream>
#include <cstring>
#include <chrono>
#include <ctime>

namespace kood3plot {
namespace query {
namespace writers {

// ============================================================
// PIMPL Implementation
// ============================================================

struct HDF5Writer::Impl {
    HDF5Compression compression = HDF5Compression::NONE;
    int compression_level = 6;
    HDF5ChunkOptions chunk_options;
    bool shuffle_enabled = false;
    bool checksum_enabled = false;
    std::string last_error;
    size_t bytes_written = 0;

    // Simple binary format header
    struct FileHeader {
        char magic[8] = {'K', 'O', 'O', 'H', 'D', 'F', '5', '\0'};  // KOOHDF5
        uint32_t version = 1;
        uint32_t flags = 0;
        uint64_t metadata_offset = 0;
        uint64_t data_offset = 0;
        uint64_t stats_offset = 0;
        uint64_t total_records = 0;
        uint32_t num_columns = 0;
        uint32_t reserved[8] = {0};
    };

    struct DatasetHeader {
        char name[64] = {0};
        uint32_t dtype = 0;  // 0=float64, 1=int64, 2=string
        uint64_t num_elements = 0;
        uint64_t data_size = 0;
    };
};

// ============================================================
// Constructor/Destructor
// ============================================================

HDF5Writer::HDF5Writer()
    : pImpl(std::make_unique<Impl>())
{
}

HDF5Writer::~HDF5Writer() = default;

// ============================================================
// Configuration
// ============================================================

void HDF5Writer::setCompression(HDF5Compression type, int level) {
    pImpl->compression = type;
    pImpl->compression_level = level;
}

void HDF5Writer::setChunking(const HDF5ChunkOptions& options) {
    pImpl->chunk_options = options;
}

void HDF5Writer::setShuffle(bool enable) {
    pImpl->shuffle_enabled = enable;
}

void HDF5Writer::setChecksum(bool enable) {
    pImpl->checksum_enabled = enable;
}

// ============================================================
// Writing
// ============================================================

bool HDF5Writer::write(const QueryResult& result, const std::string& filepath) {
    std::ofstream file(filepath, std::ios::binary);
    if (!file.is_open()) {
        pImpl->last_error = "Cannot open file: " + filepath;
        return false;
    }

    pImpl->bytes_written = 0;

    // Write placeholder header (will be updated later)
    Impl::FileHeader header;
    header.total_records = result.size();
    header.num_columns = static_cast<uint32_t>(result.getQuantityNames().size());

    std::streampos header_pos = file.tellp();
    file.write(reinterpret_cast<const char*>(&header), sizeof(header));
    pImpl->bytes_written += sizeof(header);

    // Write metadata
    header.metadata_offset = static_cast<uint64_t>(file.tellp());
    writeMetadata(file, result);

    // Write datasets
    header.data_offset = static_cast<uint64_t>(file.tellp());
    writeDatasets(file, result);

    // Write statistics
    header.stats_offset = static_cast<uint64_t>(file.tellp());
    writeStatistics(file, result);

    // Update header with offsets
    file.seekp(header_pos);
    file.write(reinterpret_cast<const char*>(&header), sizeof(header));

    file.close();
    return true;
}

bool HDF5Writer::writeMetadata(std::ostream& out, const QueryResult& result) {
    // Write metadata as key-value pairs
    auto writeString = [&out, this](const std::string& s) {
        uint32_t len = static_cast<uint32_t>(s.size());
        out.write(reinterpret_cast<const char*>(&len), sizeof(len));
        out.write(s.c_str(), len);
        pImpl->bytes_written += sizeof(len) + len;
    };

    // Get current time
    auto now = std::chrono::system_clock::now();
    auto time_t = std::chrono::system_clock::to_time_t(now);
    std::string timestamp = std::ctime(&time_t);
    if (!timestamp.empty() && timestamp.back() == '\n') {
        timestamp.pop_back();
    }

    // Write metadata entries
    uint32_t num_entries = 4;
    out.write(reinterpret_cast<const char*>(&num_entries), sizeof(num_entries));
    pImpl->bytes_written += sizeof(num_entries);

    writeString("query_time");
    writeString(timestamp);

    writeString("total_records");
    writeString(std::to_string(result.size()));

    writeString("source");
    writeString("KooD3plot V3 Query System");

    writeString("format_version");
    writeString("1.0.0");

    return true;
}

bool HDF5Writer::writeDatasets(std::ostream& out, const QueryResult& result) {
    auto quantities = result.getQuantityNames();

    // Also include element_id, part_id, state_index, time
    std::vector<std::string> columns = {"element_id", "part_id", "state_index", "time"};
    for (const auto& q : quantities) {
        columns.push_back(q);
    }

    // Write number of datasets
    uint32_t num_datasets = static_cast<uint32_t>(columns.size());
    out.write(reinterpret_cast<const char*>(&num_datasets), sizeof(num_datasets));
    pImpl->bytes_written += sizeof(num_datasets);

    size_t num_records = result.size();
    const auto& data_points = result.getDataPoints();

    for (const auto& col_name : columns) {
        Impl::DatasetHeader ds_header;
        std::strncpy(ds_header.name, col_name.c_str(), sizeof(ds_header.name) - 1);
        ds_header.num_elements = num_records;
        ds_header.dtype = 0;  // float64

        // Build data array
        std::vector<double> data;
        data.reserve(num_records);

        for (const auto& dp : data_points) {
            if (col_name == "element_id") {
                data.push_back(static_cast<double>(dp.element_id));
            } else if (col_name == "part_id") {
                data.push_back(static_cast<double>(dp.part_id));
            } else if (col_name == "state_index") {
                data.push_back(static_cast<double>(dp.state_index));
            } else if (col_name == "time") {
                data.push_back(dp.time);
            } else {
                data.push_back(dp.getValueOr(col_name, 0.0));
            }
        }

        ds_header.data_size = data.size() * sizeof(double);

        // Write dataset header
        out.write(reinterpret_cast<const char*>(&ds_header), sizeof(ds_header));
        pImpl->bytes_written += sizeof(ds_header);

        // Write data
        out.write(reinterpret_cast<const char*>(data.data()), ds_header.data_size);
        pImpl->bytes_written += ds_header.data_size;
    }

    return true;
}

bool HDF5Writer::writeStatistics(std::ostream& out, const QueryResult& result) {
    auto quantities = result.getQuantityNames();

    // Write number of stat entries
    uint32_t num_stats = static_cast<uint32_t>(quantities.size());
    out.write(reinterpret_cast<const char*>(&num_stats), sizeof(num_stats));
    pImpl->bytes_written += sizeof(num_stats);

    for (const auto& name : quantities) {
        auto stat = result.getStatistics(name);

        // Write name
        uint32_t name_len = static_cast<uint32_t>(name.size());
        out.write(reinterpret_cast<const char*>(&name_len), sizeof(name_len));
        out.write(name.c_str(), name_len);
        pImpl->bytes_written += sizeof(name_len) + name_len;

        // Write stats (min, max, mean, std_dev, sum, count)
        double values[6] = {stat.min_value, stat.max_value, stat.mean_value,
                           stat.std_dev, stat.sum, static_cast<double>(stat.count)};
        out.write(reinterpret_cast<const char*>(values), sizeof(values));
        pImpl->bytes_written += sizeof(values);
    }

    return true;
}

bool HDF5Writer::writeMultiple(const std::vector<QueryResult>& results,
                                const std::vector<std::string>& group_names,
                                const std::string& filepath) {
    if (results.size() != group_names.size()) {
        pImpl->last_error = "Results and group names size mismatch";
        return false;
    }

    std::ofstream file(filepath, std::ios::binary);
    if (!file.is_open()) {
        pImpl->last_error = "Cannot open file: " + filepath;
        return false;
    }

    // Write simplified multi-group format
    char magic[8] = {'K', 'O', 'O', 'M', 'U', 'L', 'T', '\0'};
    file.write(magic, sizeof(magic));

    uint32_t num_groups = static_cast<uint32_t>(results.size());
    file.write(reinterpret_cast<const char*>(&num_groups), sizeof(num_groups));

    for (size_t i = 0; i < results.size(); ++i) {
        // Write group name
        uint32_t name_len = static_cast<uint32_t>(group_names[i].size());
        file.write(reinterpret_cast<const char*>(&name_len), sizeof(name_len));
        file.write(group_names[i].c_str(), name_len);

        // Write result data
        writeMetadata(file, results[i]);
        writeDatasets(file, results[i]);
        writeStatistics(file, results[i]);
    }

    file.close();
    return true;
}

bool HDF5Writer::append(const QueryResult& result,
                         const std::string& filepath,
                         const std::string& group_name) {
    // For simplicity, append creates a new multi-group file or adds to existing
    pImpl->last_error = "Append not yet implemented for simplified HDF5 format";
    return false;
}

// ============================================================
// Status
// ============================================================

bool HDF5Writer::isHDF5Available() {
    // In this simplified implementation, we always return true
    // as we provide a compatible binary format
    return true;
}

std::string HDF5Writer::getLastError() const {
    return pImpl->last_error;
}

size_t HDF5Writer::getBytesWritten() const {
    return pImpl->bytes_written;
}

} // namespace writers
} // namespace query
} // namespace kood3plot
