#pragma once

#include "kood3plot/Types.hpp"
#include "kood3plot/core/Endian.hpp"
#include <string>
#include <fstream>
#include <vector>

namespace kood3plot {
namespace core {

/**
 * @brief Low-level binary file reader with automatic format detection
 */
class BinaryReader {
public:
    /**
     * @brief Constructor
     * @param filepath Path to the d3plot file
     */
    explicit BinaryReader(const std::string& filepath);

    /**
     * @brief Destructor
     */
    ~BinaryReader();

    // Delete copy constructor and assignment
    BinaryReader(const BinaryReader&) = delete;
    BinaryReader& operator=(const BinaryReader&) = delete;

    /**
     * @brief Open the file and detect format
     * @return ErrorCode indicating success or failure
     */
    ErrorCode open();

    /**
     * @brief Open a family file with known format (no format detection)
     * @param precision Known precision from base file
     * @param endian Known endianness from base file
     * @return ErrorCode indicating success or failure
     */
    ErrorCode open_family_file(Precision precision, Endian endian);

    /**
     * @brief Close the file
     */
    void close();

    /**
     * @brief Check if file is open
     */
    bool is_open() const;

    /**
     * @brief Get detected precision
     */
    Precision get_precision() const { return precision_; }

    /**
     * @brief Get detected endianness
     */
    Endian get_endian() const { return endian_; }

    /**
     * @brief Get word size in bytes
     */
    int32_t get_word_size() const { return word_size_; }

    /**
     * @brief Get file size in bytes
     */
    size_t get_file_size() const { return file_size_; }

    /**
     * @brief Get file size in words
     */
    size_t get_file_size_words() const { return file_size_ / word_size_; }

    /**
     * @brief Get LS-DYNA version (read from word 14)
     */
    double get_version() const;

    /**
     * @brief Read integer at word address
     */
    int32_t read_int(size_t word_address);

    /**
     * @brief Read float at word address
     */
    float read_float(size_t word_address);

    /**
     * @brief Read double at word address
     */
    double read_double(size_t word_address);

    /**
     * @brief Read array of integers
     */
    std::vector<int32_t> read_int_array(size_t word_address, size_t count);

    /**
     * @brief Read array of floats
     */
    std::vector<float> read_float_array(size_t word_address, size_t count);

    /**
     * @brief Read array of doubles
     */
    std::vector<double> read_double_array(size_t word_address, size_t count);

private:
    /**
     * @brief Detect file format (precision and endianness)
     */
    void detect_format();

    /**
     * @brief Check if version value is valid
     */
    bool is_valid_version(double version) const;

    std::string filepath_;
    std::ifstream file_;
    Precision precision_;
    Endian endian_;
    int32_t word_size_;
    size_t file_size_;
};

} // namespace core
} // namespace kood3plot
