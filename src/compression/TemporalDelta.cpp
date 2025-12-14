/**
 * @file TemporalDelta.cpp
 * @brief Implementation of temporal delta compression (Week 3 placeholder)
 */

#include "kood3plot/compression/TemporalDelta.hpp"
#include <stdexcept>

namespace kood3plot {
namespace compression {

// ============================================================
// TemporalDeltaEncoder
// ============================================================

std::vector<float> TemporalDeltaEncoder::encode(
    const std::vector<std::vector<float>>& data)
{
    if (data.empty()) {
        return {};
    }

    const size_t num_frames = data.size();
    const size_t values_per_frame = data[0].size();

    // Store first frame as-is, then deltas for subsequent frames
    std::vector<float> encoded;
    encoded.reserve(num_frames * values_per_frame);

    // First frame: store raw values
    for (float v : data[0]) {
        encoded.push_back(v);
    }

    // Subsequent frames: store deltas
    for (size_t frame = 1; frame < num_frames; ++frame) {
        for (size_t i = 0; i < values_per_frame; ++i) {
            encoded.push_back(data[frame][i] - data[frame - 1][i]);
        }
    }

    // Update metadata
    metadata_.original_size = num_frames * values_per_frame * sizeof(float);
    metadata_.compressed_size = encoded.size() * sizeof(float);
    metadata_.num_frames = num_frames;
    metadata_.num_values_per_frame = values_per_frame;
    metadata_.compression_ratio = static_cast<double>(metadata_.original_size) /
                                  static_cast<double>(metadata_.compressed_size);

    return encoded;
}

std::vector<std::vector<float>> TemporalDeltaEncoder::decode(
    const std::vector<float>& encoded,
    size_t num_frames,
    size_t values_per_frame)
{
    if (encoded.size() != num_frames * values_per_frame) {
        throw std::invalid_argument("Encoded data size mismatch");
    }

    std::vector<std::vector<float>> decoded(num_frames);
    for (auto& frame : decoded) {
        frame.resize(values_per_frame);
    }

    // First frame: copy raw values
    for (size_t i = 0; i < values_per_frame; ++i) {
        decoded[0][i] = encoded[i];
    }

    // Subsequent frames: accumulate deltas
    for (size_t frame = 1; frame < num_frames; ++frame) {
        size_t offset = frame * values_per_frame;
        for (size_t i = 0; i < values_per_frame; ++i) {
            decoded[frame][i] = decoded[frame - 1][i] + encoded[offset + i];
        }
    }

    return decoded;
}

// ============================================================
// QuantizedDeltaEncoder
// ============================================================

std::vector<int16_t> QuantizedDeltaEncoder::encode(
    const std::vector<std::vector<uint16_t>>& data)
{
    if (data.empty()) {
        return {};
    }

    const size_t num_frames = data.size();
    const size_t values_per_frame = data[0].size();

    std::vector<int16_t> encoded;
    encoded.reserve(num_frames * values_per_frame);

    // First frame: store as signed (for consistency)
    for (uint16_t v : data[0]) {
        encoded.push_back(static_cast<int16_t>(v));
    }

    // Subsequent frames: store deltas
    for (size_t frame = 1; frame < num_frames; ++frame) {
        for (size_t i = 0; i < values_per_frame; ++i) {
            int32_t delta = static_cast<int32_t>(data[frame][i]) -
                           static_cast<int32_t>(data[frame - 1][i]);
            encoded.push_back(static_cast<int16_t>(delta));
        }
    }

    // Update metadata
    metadata_.original_size = num_frames * values_per_frame * sizeof(uint16_t);
    metadata_.compressed_size = encoded.size() * sizeof(int16_t);
    metadata_.num_frames = num_frames;
    metadata_.num_values_per_frame = values_per_frame;
    metadata_.compression_ratio = 1.0; // Same size before further compression

    return encoded;
}

std::vector<std::vector<uint16_t>> QuantizedDeltaEncoder::decode(
    const std::vector<int16_t>& encoded,
    size_t num_frames,
    size_t values_per_frame)
{
    if (encoded.size() != num_frames * values_per_frame) {
        throw std::invalid_argument("Encoded data size mismatch");
    }

    std::vector<std::vector<uint16_t>> decoded(num_frames);
    for (auto& frame : decoded) {
        frame.resize(values_per_frame);
    }

    // First frame
    for (size_t i = 0; i < values_per_frame; ++i) {
        decoded[0][i] = static_cast<uint16_t>(encoded[i]);
    }

    // Subsequent frames
    for (size_t frame = 1; frame < num_frames; ++frame) {
        size_t offset = frame * values_per_frame;
        for (size_t i = 0; i < values_per_frame; ++i) {
            int32_t value = static_cast<int32_t>(decoded[frame - 1][i]) +
                           static_cast<int32_t>(encoded[offset + i]);
            decoded[frame][i] = static_cast<uint16_t>(value);
        }
    }

    return decoded;
}

// ============================================================
// XORDeltaEncoder
// ============================================================

std::vector<uint16_t> XORDeltaEncoder::encode(
    const std::vector<std::vector<uint16_t>>& data)
{
    if (data.empty()) {
        return {};
    }

    const size_t num_frames = data.size();
    const size_t values_per_frame = data[0].size();

    std::vector<uint16_t> encoded;
    encoded.reserve(num_frames * values_per_frame);

    // First frame: store raw values
    for (uint16_t v : data[0]) {
        encoded.push_back(v);
    }

    // Subsequent frames: store XOR with previous frame
    for (size_t frame = 1; frame < num_frames; ++frame) {
        for (size_t i = 0; i < values_per_frame; ++i) {
            encoded.push_back(data[frame][i] ^ data[frame - 1][i]);
        }
    }

    // Update metadata
    metadata_.original_size = num_frames * values_per_frame * sizeof(uint16_t);
    metadata_.compressed_size = encoded.size() * sizeof(uint16_t);
    metadata_.num_frames = num_frames;
    metadata_.num_values_per_frame = values_per_frame;
    metadata_.compression_ratio = 1.0;

    return encoded;
}

std::vector<std::vector<uint16_t>> XORDeltaEncoder::decode(
    const std::vector<uint16_t>& encoded,
    size_t num_frames,
    size_t values_per_frame)
{
    if (encoded.size() != num_frames * values_per_frame) {
        throw std::invalid_argument("Encoded data size mismatch");
    }

    std::vector<std::vector<uint16_t>> decoded(num_frames);
    for (auto& frame : decoded) {
        frame.resize(values_per_frame);
    }

    // First frame
    for (size_t i = 0; i < values_per_frame; ++i) {
        decoded[0][i] = encoded[i];
    }

    // Subsequent frames: XOR accumulate
    for (size_t frame = 1; frame < num_frames; ++frame) {
        size_t offset = frame * values_per_frame;
        for (size_t i = 0; i < values_per_frame; ++i) {
            decoded[frame][i] = decoded[frame - 1][i] ^ encoded[offset + i];
        }
    }

    return decoded;
}

} // namespace compression
} // namespace kood3plot
