/**
 * @file StreamingQuery.hpp
 * @brief Streaming query system for large-scale d3plot processing
 *
 * This module provides memory-efficient alternatives to the standard query system.
 * Instead of loading all data into memory, it processes data in chunks or streams
 * results one-by-one, enabling analysis of very large d3plot files.
 *
 * Usage patterns:
 *
 * 1. Iterator-based streaming (lowest memory):
 * @code
 * StreamingQuery query(reader);
 * query.selectParts({1, 2, 3})
 *      .selectQuantities({"von_mises"})
 *      .selectTime(TimeSelector::allStates());
 *
 * for (auto it = query.begin(); it != query.end(); ++it) {
 *     const auto& point = *it;
 *     // Process one point at a time
 * }
 * @endcode
 *
 * 2. Chunk-based processing (balanced):
 * @code
 * query.forEachChunk(10000, [](const std::vector<ResultDataPoint>& chunk) {
 *     // Process chunk of 10000 points
 * });
 * @endcode
 *
 * 3. Direct streaming to file (fastest for export):
 * @code
 * query.streamToCSV("output.csv");
 * @endcode
 *
 * @author KooD3plot V3 Development Team
 * @date 2025-12-02
 * @version 3.1.0
 */

#pragma once

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/query/PartSelector.h"
#include "kood3plot/query/QuantitySelector.h"
#include "kood3plot/query/TimeSelector.h"
#include "kood3plot/query/ValueFilter.h"
#include "kood3plot/query/OutputSpec.h"
#include "kood3plot/query/QueryResult.h"

#include <memory>
#include <functional>
#include <string>
#include <vector>
#include <optional>
#include <atomic>
#include <fstream>
#include <chrono>

namespace kood3plot {
namespace query {

// Forward declarations
class StreamingQuery;
class StreamingQueryIterator;

/**
 * @brief Streaming progress callback signature
 * @param current Current progress (elements processed)
 * @param total Total elements (estimated)
 * @param message Status message
 *
 * Note: This is different from the ProgressCallback in QueryTypes.h
 * which uses (int, int, const std::string&) for compatibility.
 */
using StreamingProgressCallback = std::function<void(size_t current, size_t total, const std::string& message)>;

/**
 * @brief Chunk processing callback signature
 * @param chunk Vector of data points in this chunk
 * @param chunk_index Index of the current chunk (0-based)
 * @return true to continue, false to stop processing
 */
using ChunkCallback = std::function<bool(const std::vector<ResultDataPoint>& chunk, size_t chunk_index)>;

/**
 * @brief Single-point processing callback signature
 * @param point The current data point
 * @param index Index of the current point (0-based)
 * @return true to continue, false to stop processing
 */
using PointCallback = std::function<bool(const ResultDataPoint& point, size_t index)>;

/**
 * @brief Streaming query configuration
 */
struct StreamingConfig {
    /// Chunk size for batch processing (default: 10000)
    size_t chunk_size = 10000;

    /// Enable progress reporting
    bool report_progress = true;

    /// Progress report interval (every N points)
    size_t progress_interval = 100000;

    /// Buffer size for file I/O (bytes)
    size_t io_buffer_size = 1024 * 1024;  // 1MB

    /// Number of states to prefetch (0 = no prefetch)
    size_t state_prefetch = 0;

    /// Skip invalid/NaN values
    bool skip_invalid = true;

    /// Maximum memory usage hint (bytes, 0 = unlimited)
    size_t max_memory_hint = 0;

    /// Use memory-mapped I/O when available
    bool use_mmap = false;
};

/**
 * @brief Streaming query statistics
 */
struct StreamingStats {
    /// Total points processed
    size_t points_processed = 0;

    /// Total points filtered out
    size_t points_filtered = 0;

    /// Total states processed
    size_t states_processed = 0;

    /// Total bytes written (for file output)
    size_t bytes_written = 0;

    /// Processing time (milliseconds)
    double processing_time_ms = 0.0;

    /// Peak memory usage (bytes, if available)
    size_t peak_memory_bytes = 0;

    /// Was processing cancelled?
    bool cancelled = false;

    /// Error message (if any)
    std::string error_message;
};

/**
 * @brief Iterator for streaming through query results
 *
 * This iterator processes data lazily, loading only one state at a time.
 * It implements the input iterator concept for range-based for loops.
 */
class StreamingQueryIterator {
public:
    // Iterator traits
    using iterator_category = std::input_iterator_tag;
    using value_type = ResultDataPoint;
    using difference_type = std::ptrdiff_t;
    using pointer = const ResultDataPoint*;
    using reference = const ResultDataPoint&;

    /// End iterator constructor
    StreamingQueryIterator();

    /// Begin iterator constructor
    StreamingQueryIterator(StreamingQuery* query);

    /// Copy constructor
    StreamingQueryIterator(const StreamingQueryIterator& other);

    /// Move constructor
    StreamingQueryIterator(StreamingQueryIterator&& other) noexcept;

    /// Destructor
    ~StreamingQueryIterator();

    /// Dereference operator
    reference operator*() const;

    /// Arrow operator
    pointer operator->() const;

    /// Pre-increment operator
    StreamingQueryIterator& operator++();

    /// Post-increment operator
    StreamingQueryIterator operator++(int);

    /// Equality comparison
    bool operator==(const StreamingQueryIterator& other) const;

    /// Inequality comparison
    bool operator!=(const StreamingQueryIterator& other) const;

    /// Check if iterator is valid
    bool valid() const;

    /// Get current index
    size_t index() const;

private:
    struct Impl;
    std::shared_ptr<Impl> pImpl;

    void advance();
    void loadNextState();
};

/**
 * @brief Memory-efficient streaming query for large d3plot files
 *
 * This class provides an alternative to D3plotQuery that processes data
 * incrementally rather than loading everything into memory. It's designed
 * for d3plot files that are too large to fit in RAM.
 */
class StreamingQuery {
public:
    /**
     * @brief Constructor
     * @param reader D3plotReader reference (must remain valid)
     */
    explicit StreamingQuery(D3plotReader& reader);

    /// Copy constructor (deleted - streaming queries are not copyable)
    StreamingQuery(const StreamingQuery&) = delete;

    /// Move constructor
    StreamingQuery(StreamingQuery&& other) noexcept;

    /// Copy assignment (deleted)
    StreamingQuery& operator=(const StreamingQuery&) = delete;

    /// Move assignment
    StreamingQuery& operator=(StreamingQuery&& other) noexcept;

    /// Destructor
    ~StreamingQuery();

    // ============================================================
    // Configuration (Builder pattern)
    // ============================================================

    /**
     * @brief Set streaming configuration
     */
    StreamingQuery& config(const StreamingConfig& cfg);

    /**
     * @brief Set chunk size for batch processing
     */
    StreamingQuery& chunkSize(size_t size);

    /**
     * @brief Enable/disable progress reporting
     */
    StreamingQuery& reportProgress(bool enable);

    /**
     * @brief Set progress callback
     */
    StreamingQuery& onProgress(StreamingProgressCallback callback);

    // ============================================================
    // Selection (same API as D3plotQuery)
    // ============================================================

    /**
     * @brief Select parts by selector
     */
    StreamingQuery& selectParts(const PartSelector& selector);

    /**
     * @brief Select parts by IDs
     */
    StreamingQuery& selectParts(const std::vector<int32_t>& part_ids);

    /**
     * @brief Select all parts
     */
    StreamingQuery& selectAllParts();

    /**
     * @brief Select quantities
     */
    StreamingQuery& selectQuantities(const QuantitySelector& selector);

    /**
     * @brief Select quantities by names
     */
    StreamingQuery& selectQuantities(const std::vector<std::string>& names);

    /**
     * @brief Select time steps
     */
    StreamingQuery& selectTime(const TimeSelector& selector);

    /**
     * @brief Select time steps by indices
     */
    StreamingQuery& selectTime(const std::vector<int>& state_indices);

    /**
     * @brief Set value filter
     */
    StreamingQuery& whereValue(const ValueFilter& filter);

    // ============================================================
    // Iteration
    // ============================================================

    /**
     * @brief Get iterator to first element
     */
    StreamingQueryIterator begin();

    /**
     * @brief Get end iterator
     */
    StreamingQueryIterator end();

    // ============================================================
    // Chunk-based Processing
    // ============================================================

    /**
     * @brief Process data in chunks
     * @param chunk_size Size of each chunk
     * @param callback Function to call for each chunk
     * @return Statistics about the processing
     */
    StreamingStats forEachChunk(size_t chunk_size, ChunkCallback callback);

    /**
     * @brief Process data in chunks (uses configured chunk size)
     */
    StreamingStats forEachChunk(ChunkCallback callback);

    /**
     * @brief Process each data point
     * @param callback Function to call for each point
     * @return Statistics about the processing
     */
    StreamingStats forEach(PointCallback callback);

    // ============================================================
    // Direct File Output (Most Efficient)
    // ============================================================

    /**
     * @brief Stream results directly to CSV file
     * @param filename Output filename
     * @param spec Output specification (optional)
     * @return Statistics about the processing
     */
    StreamingStats streamToCSV(const std::string& filename,
                               const OutputSpec& spec = OutputSpec::csv());

    /**
     * @brief Stream results directly to JSON file
     * @param filename Output filename
     * @param spec Output specification (optional)
     * @return Statistics about the processing
     */
    StreamingStats streamToJSON(const std::string& filename,
                                const OutputSpec& spec = OutputSpec::json());

    /**
     * @brief Stream results to custom writer
     *
     * The writer interface:
     * - writeHeader(fields) - called once at start
     * - writeRow(point) - called for each data point
     * - writeFooter(stats) - called once at end
     */
    template<typename Writer>
    StreamingStats streamTo(Writer& writer);

    // ============================================================
    // Aggregation (Memory-Efficient)
    // ============================================================

    /**
     * @brief Find maximum value without loading all data
     * @param quantity_name Name of the quantity
     * @return Data point with maximum value
     */
    std::optional<ResultDataPoint> findMax(const std::string& quantity_name);

    /**
     * @brief Find minimum value without loading all data
     * @param quantity_name Name of the quantity
     * @return Data point with minimum value
     */
    std::optional<ResultDataPoint> findMin(const std::string& quantity_name);

    /**
     * @brief Calculate statistics without loading all data
     * @param quantity_name Name of the quantity
     * @return Statistics (uses online algorithm)
     */
    QuantityStatistics calculateStats(const std::string& quantity_name);

    /**
     * @brief Get top N values
     * @param quantity_name Name of the quantity
     * @param n Number of top values
     * @return Vector of top N data points (sorted descending)
     */
    std::vector<ResultDataPoint> topN(const std::string& quantity_name, size_t n);

    /**
     * @brief Get bottom N values
     * @param quantity_name Name of the quantity
     * @param n Number of bottom values
     * @return Vector of bottom N data points (sorted ascending)
     */
    std::vector<ResultDataPoint> bottomN(const std::string& quantity_name, size_t n);

    // ============================================================
    // Control
    // ============================================================

    /**
     * @brief Cancel ongoing streaming operation
     *
     * This can be called from another thread to stop processing.
     */
    void cancel();

    /**
     * @brief Check if processing was cancelled
     */
    bool isCancelled() const;

    /**
     * @brief Reset cancel flag for reuse
     */
    void resetCancel();

    // ============================================================
    // Information
    // ============================================================

    /**
     * @brief Estimate total number of data points
     */
    size_t estimateSize() const;

    /**
     * @brief Estimate memory requirement for full load
     */
    size_t estimateMemoryBytes() const;

    /**
     * @brief Get description of the query
     */
    std::string getDescription() const;

    /**
     * @brief Get last processing statistics
     */
    StreamingStats getLastStats() const;

private:
    struct Impl;
    std::unique_ptr<Impl> pImpl;

    friend class StreamingQueryIterator;

    // Internal processing methods
    void processState(int state_index,
                      const std::function<void(ResultDataPoint&&)>& emitter);
};

/**
 * @brief RAII wrapper for streaming to file with automatic cleanup
 */
class StreamingFileWriter {
public:
    explicit StreamingFileWriter(const std::string& filename,
                                 OutputFormat format = OutputFormat::CSV);
    ~StreamingFileWriter();

    void writeHeader(const std::vector<std::string>& fields);
    void writeRow(const ResultDataPoint& point);
    void writeFooter(const StreamingStats& stats);

    void flush();
    void close();

    size_t bytesWritten() const;

private:
    struct Impl;
    std::unique_ptr<Impl> pImpl;
};

// ============================================================
// Template Implementation
// ============================================================

template<typename Writer>
StreamingStats StreamingQuery::streamTo(Writer& writer) {
    StreamingStats stats;
    auto start_time = std::chrono::high_resolution_clock::now();

    // Get field names from first chunk
    std::vector<std::string> fields;
    bool header_written = false;

    forEach([&](const ResultDataPoint& point, size_t index) {
        if (!header_written) {
            // Extract field names from first point
            fields = {"element_id", "part_id", "state", "time"};
            for (const auto& kv : point.values) {
                fields.push_back(kv.first);
            }
            writer.writeHeader(fields);
            header_written = true;
        }

        writer.writeRow(point);
        stats.points_processed++;

        return !isCancelled();
    });

    writer.writeFooter(stats);

    auto end_time = std::chrono::high_resolution_clock::now();
    stats.processing_time_ms = std::chrono::duration<double, std::milli>(
        end_time - start_time).count();

    return stats;
}

} // namespace query
} // namespace kood3plot