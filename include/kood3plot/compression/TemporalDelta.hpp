/**
 * @file TemporalDelta.hpp
 * @brief Temporal delta compression for time-series data (Week 3)
 *
 * This module provides compression algorithms that exploit temporal
 * correlation between adjacent time steps in simulation data.
 */

#pragma once

#include <vector>
#include <cstdint>
#include <array>

namespace kood3plot {
namespace compression {

/**
 * @brief Delta compression metadata
 */
struct DeltaMetadata {
    size_t original_size = 0;       ///< Original data size in bytes
    size_t compressed_size = 0;     ///< Compressed data size in bytes
    size_t num_frames = 0;          ///< Number of time frames
    size_t num_values_per_frame = 0;///< Values per frame
    double compression_ratio = 1.0;  ///< Compression ratio achieved
};

/**
 * @brief Temporal delta encoder for float data
 *
 * Computes differences between consecutive frames and stores
 * the deltas, which typically have smaller entropy and compress better.
 */
class TemporalDeltaEncoder {
public:
    /**
     * @brief Encode time-series data using delta compression
     * @param data Vector of frames, each containing values for all nodes/elements
     * @return Encoded delta data
     */
    std::vector<float> encode(const std::vector<std::vector<float>>& data);

    /**
     * @brief Decode delta-compressed data back to original
     * @param encoded Encoded delta data
     * @param num_frames Number of frames
     * @param values_per_frame Number of values per frame
     * @return Reconstructed original data
     */
    std::vector<std::vector<float>> decode(
        const std::vector<float>& encoded,
        size_t num_frames,
        size_t values_per_frame
    );

    /**
     * @brief Get compression metadata from last encode operation
     */
    const DeltaMetadata& getMetadata() const { return metadata_; }

private:
    DeltaMetadata metadata_;
};

/**
 * @brief Temporal delta encoder for quantized 16-bit data
 *
 * Works with pre-quantized data for even better compression.
 */
class QuantizedDeltaEncoder {
public:
    /**
     * @brief Encode quantized time-series data
     * @param data Vector of frames with quantized values
     * @return Encoded delta data as 16-bit differences
     */
    std::vector<int16_t> encode(const std::vector<std::vector<uint16_t>>& data);

    /**
     * @brief Decode delta-compressed quantized data
     * @param encoded Encoded delta data
     * @param num_frames Number of frames
     * @param values_per_frame Number of values per frame
     * @return Reconstructed quantized data
     */
    std::vector<std::vector<uint16_t>> decode(
        const std::vector<int16_t>& encoded,
        size_t num_frames,
        size_t values_per_frame
    );

    /**
     * @brief Get compression metadata
     */
    const DeltaMetadata& getMetadata() const { return metadata_; }

private:
    DeltaMetadata metadata_;
};

/**
 * @brief XOR-based delta for integer data
 *
 * For data where XOR produces more compressible output than subtraction.
 */
class XORDeltaEncoder {
public:
    std::vector<uint16_t> encode(const std::vector<std::vector<uint16_t>>& data);
    std::vector<std::vector<uint16_t>> decode(
        const std::vector<uint16_t>& encoded,
        size_t num_frames,
        size_t values_per_frame
    );

    const DeltaMetadata& getMetadata() const { return metadata_; }

private:
    DeltaMetadata metadata_;
};

} // namespace compression
} // namespace kood3plot
