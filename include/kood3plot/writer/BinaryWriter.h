/**
 * @file BinaryWriter.h
 * @brief Low-level binary file writing with endian and precision support
 * @author KooD3plot V2 Development Team
 * @date 2026-01-22
 * @version 2.0.0
 */

#pragma once

#include "kood3plot/Types.hpp"
#include <string>
#include <fstream>
#include <vector>
#include <cstdint>

namespace kood3plot {
namespace writer {

/**
 * @brief Low-level binary writer with automatic endian conversion and precision handling
 *
 * This class provides the foundation for writing d3plot files with support for:
 * - Single/Double precision floating point
 * - Little/Big endian byte ordering
 * - Automatic byte swapping when needed
 */
class BinaryWriter {
public:
    /**
     * @brief Constructor
     */
    BinaryWriter();

    /**
     * @brief Destructor - ensures file is closed
     */
    ~BinaryWriter();

    // Disable copy
    BinaryWriter(const BinaryWriter&) = delete;
    BinaryWriter& operator=(const BinaryWriter&) = delete;

    // Enable move
    BinaryWriter(BinaryWriter&& other) noexcept;
    BinaryWriter& operator=(BinaryWriter&& other) noexcept;

    /**
     * @brief Open file for writing
     * @param filepath Path to output file
     * @return ErrorCode::SUCCESS on success
     */
    ErrorCode open(const std::string& filepath);

    /**
     * @brief Close the file
     */
    void close();

    /**
     * @brief Check if file is open
     */
    bool is_open() const;

    /**
     * @brief Get current write position
     */
    size_t tell() const;

    /**
     * @brief Seek to absolute position
     */
    void seek(size_t position);

    /**
     * @brief Get total bytes written
     */
    size_t get_bytes_written() const { return bytes_written_; }

    // ========================================
    // Configuration
    // ========================================

    /**
     * @brief Set output precision (single or double)
     */
    void set_precision(Precision prec) { precision_ = prec; }

    /**
     * @brief Get current precision setting
     */
    Precision get_precision() const { return precision_; }

    /**
     * @brief Set output endianness
     */
    void set_endian(Endian endian) { target_endian_ = endian; }

    /**
     * @brief Get current endian setting
     */
    Endian get_endian() const { return target_endian_; }

    /**
     * @brief Get word size in bytes (4 for single, 8 for double)
     */
    int get_word_size() const { return precision_ == Precision::SINGLE ? 4 : 8; }

    // ========================================
    // Write Functions - Single Values
    // ========================================

    /**
     * @brief Write a 32-bit integer
     */
    void write_int(int32_t value);

    /**
     * @brief Write a 32-bit unsigned integer
     */
    void write_uint(uint32_t value);

    /**
     * @brief Write a 64-bit integer
     */
    void write_int64(int64_t value);

    /**
     * @brief Write a floating point value (respects precision setting)
     * If precision is SINGLE, writes as float (4 bytes)
     * If precision is DOUBLE, writes as double (8 bytes)
     */
    void write_float(double value);

    /**
     * @brief Write a double value (always 8 bytes)
     */
    void write_double(double value);

    /**
     * @brief Write a single precision float (always 4 bytes)
     */
    void write_float32(float value);

    // ========================================
    // Write Functions - Arrays
    // ========================================

    /**
     * @brief Write array of 32-bit integers
     */
    void write_int_array(const std::vector<int32_t>& values);
    void write_int_array(const int32_t* values, size_t count);

    /**
     * @brief Write array of floating point values (respects precision setting)
     */
    void write_float_array(const std::vector<float>& values);
    void write_float_array(const float* values, size_t count);

    /**
     * @brief Write array of double values (respects precision setting)
     * Converts to float if precision is SINGLE
     */
    void write_double_array(const std::vector<double>& values);
    void write_double_array(const double* values, size_t count);

    // ========================================
    // Write Functions - Strings
    // ========================================

    /**
     * @brief Write a fixed-length string (padded with spaces)
     * @param str String to write
     * @param length Fixed length in bytes
     */
    void write_string(const std::string& str, size_t length);

    // ========================================
    // Write Functions - Raw Data
    // ========================================

    /**
     * @brief Write raw bytes
     */
    void write_raw(const void* data, size_t size);

    /**
     * @brief Write padding (zeros)
     */
    void write_padding(size_t num_bytes);

    /**
     * @brief Write N words of zeros
     */
    void write_zero_words(size_t num_words);

    // ========================================
    // Error Handling
    // ========================================

    /**
     * @brief Get last error message
     */
    std::string get_last_error() const { return last_error_; }

    /**
     * @brief Check if last operation was successful
     */
    bool good() const;

private:
    std::ofstream file_;
    std::string filepath_;
    Precision precision_ = Precision::SINGLE;
    Endian target_endian_ = Endian::LITTLE;
    Endian system_endian_;
    bool needs_swap_ = false;
    size_t bytes_written_ = 0;
    std::string last_error_;

    /**
     * @brief Detect system endianness
     */
    Endian detect_system_endian();

    /**
     * @brief Update swap flag based on settings
     */
    void update_swap_flag();

    /**
     * @brief Swap bytes of a 32-bit value
     */
    static uint32_t swap32(uint32_t value);

    /**
     * @brief Swap bytes of a 64-bit value
     */
    static uint64_t swap64(uint64_t value);
};

} // namespace writer
} // namespace kood3plot
