/**
 * @file HDF5Writer.h
 * @brief HDF5 format writer for V3 Query System
 * @author KooD3plot V3 Development Team
 * @date 2025-11-22
 * @version 3.0.0
 *
 * Writes query results to HDF5 format for efficient storage and
 * fast access to large datasets.
 *
 * Note: Requires HDF5 library for full functionality. Without HDF5,
 * this writer will produce a binary placeholder file.
 */

#pragma once

#include <string>
#include <vector>
#include <memory>
#include <fstream>
#include <map>

// Forward declaration
namespace kood3plot {
namespace query {
class QueryResult;
}
}

namespace kood3plot {
namespace query {
namespace writers {

/**
 * @brief HDF5 compression type
 */
enum class HDF5Compression {
    NONE,       ///< No compression
    GZIP,       ///< GZIP compression (deflate)
    SZIP,       ///< SZIP compression
    LZF         ///< LZF compression (fast)
};

/**
 * @brief HDF5 dataset chunking options
 */
struct HDF5ChunkOptions {
    bool enabled = true;          ///< Enable chunking
    size_t chunk_rows = 1000;     ///< Number of rows per chunk
    size_t chunk_cols = 0;        ///< Number of cols per chunk (0 = auto)
};

/**
 * @class HDF5Writer
 * @brief Writes query results to HDF5 format
 *
 * HDF5 (Hierarchical Data Format version 5) provides:
 * - Efficient storage for large datasets
 * - Fast random access
 * - Compression support
 * - Hierarchical organization
 * - Metadata support
 *
 * Example usage:
 * @code
 * HDF5Writer writer;
 * writer.setCompression(HDF5Compression::GZIP, 6);
 * writer.write(result, "output.h5");
 * @endcode
 *
 * HDF5 file structure:
 * /metadata
 *   - query_time
 *   - source_file
 *   - total_records
 * /data
 *   - element_id [dataset]
 *   - time [dataset]
 *   - von_mises [dataset]
 *   - ... (other quantities)
 * /statistics
 *   - min, max, mean, std_dev
 */
class HDF5Writer {
public:
    HDF5Writer();
    ~HDF5Writer();
    HDF5Writer(const HDF5Writer&) = delete;
    HDF5Writer& operator=(const HDF5Writer&) = delete;

    // ============================================================
    // Configuration
    // ============================================================

    /**
     * @brief Set compression options
     * @param type Compression algorithm
     * @param level Compression level (1-9 for GZIP, 0 = default)
     */
    void setCompression(HDF5Compression type, int level = 6);

    /**
     * @brief Set chunking options
     * @param options Chunk configuration
     */
    void setChunking(const HDF5ChunkOptions& options);

    /**
     * @brief Enable/disable shuffle filter (improves compression)
     * @param enable Enable shuffle
     */
    void setShuffle(bool enable);

    /**
     * @brief Set Fletcher32 checksum
     * @param enable Enable checksum
     */
    void setChecksum(bool enable);

    // ============================================================
    // Writing
    // ============================================================

    /**
     * @brief Write query result to HDF5 file
     * @param result Query result to write
     * @param filepath Output file path
     * @return true on success
     */
    bool write(const QueryResult& result, const std::string& filepath);

    /**
     * @brief Write multiple results to single HDF5 file
     * @param results Vector of query results
     * @param group_names Names for each result group
     * @param filepath Output file path
     * @return true on success
     */
    bool writeMultiple(const std::vector<QueryResult>& results,
                       const std::vector<std::string>& group_names,
                       const std::string& filepath);

    /**
     * @brief Append result to existing HDF5 file
     * @param result Query result to append
     * @param filepath Existing file path
     * @param group_name Group name for new data
     * @return true on success
     */
    bool append(const QueryResult& result,
                const std::string& filepath,
                const std::string& group_name);

    // ============================================================
    // Status
    // ============================================================

    /**
     * @brief Check if HDF5 library is available
     * @return true if HDF5 support is compiled in
     */
    static bool isHDF5Available();

    /**
     * @brief Get last error message
     * @return Error message
     */
    std::string getLastError() const;

    /**
     * @brief Get bytes written
     * @return Number of bytes written
     */
    size_t getBytesWritten() const;

private:
    struct Impl;
    std::unique_ptr<Impl> pImpl;

    bool writeMetadata(std::ostream& out, const QueryResult& result);
    bool writeDatasets(std::ostream& out, const QueryResult& result);
    bool writeStatistics(std::ostream& out, const QueryResult& result);
};

} // namespace writers
} // namespace query
} // namespace kood3plot
