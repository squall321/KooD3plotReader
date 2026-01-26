/**
 * @file BinaryWriter.cpp
 * @brief Implementation of BinaryWriter class
 */

#include "kood3plot/writer/BinaryWriter.h"
#include <cstring>
#include <algorithm>

namespace kood3plot {
namespace writer {

// ============================================================
// Constructor / Destructor
// ============================================================

BinaryWriter::BinaryWriter()
    : system_endian_(detect_system_endian())
{
    update_swap_flag();
}

BinaryWriter::~BinaryWriter() {
    close();
}

BinaryWriter::BinaryWriter(BinaryWriter&& other) noexcept
    : file_(std::move(other.file_))
    , filepath_(std::move(other.filepath_))
    , precision_(other.precision_)
    , target_endian_(other.target_endian_)
    , system_endian_(other.system_endian_)
    , needs_swap_(other.needs_swap_)
    , bytes_written_(other.bytes_written_)
    , last_error_(std::move(other.last_error_))
{
    other.bytes_written_ = 0;
}

BinaryWriter& BinaryWriter::operator=(BinaryWriter&& other) noexcept {
    if (this != &other) {
        close();
        file_ = std::move(other.file_);
        filepath_ = std::move(other.filepath_);
        precision_ = other.precision_;
        target_endian_ = other.target_endian_;
        system_endian_ = other.system_endian_;
        needs_swap_ = other.needs_swap_;
        bytes_written_ = other.bytes_written_;
        last_error_ = std::move(other.last_error_);
        other.bytes_written_ = 0;
    }
    return *this;
}

// ============================================================
// File Operations
// ============================================================

ErrorCode BinaryWriter::open(const std::string& filepath) {
    close();

    file_.open(filepath, std::ios::binary | std::ios::out);
    if (!file_.is_open()) {
        last_error_ = "Failed to open file for writing: " + filepath;
        return ErrorCode::IO_ERROR;
    }

    filepath_ = filepath;
    bytes_written_ = 0;
    update_swap_flag();

    return ErrorCode::SUCCESS;
}

void BinaryWriter::close() {
    if (file_.is_open()) {
        file_.close();
    }
}

bool BinaryWriter::is_open() const {
    return file_.is_open();
}

size_t BinaryWriter::tell() const {
    if (!file_.is_open()) return 0;
    return static_cast<size_t>(const_cast<std::ofstream&>(file_).tellp());
}

void BinaryWriter::seek(size_t position) {
    if (file_.is_open()) {
        file_.seekp(static_cast<std::streamoff>(position), std::ios::beg);
    }
}

bool BinaryWriter::good() const {
    return file_.is_open() && file_.good();
}

// ============================================================
// Endian Detection and Handling
// ============================================================

Endian BinaryWriter::detect_system_endian() {
    union {
        uint32_t i;
        char c[4];
    } test = {0x01020304};

    return (test.c[0] == 1) ? Endian::BIG : Endian::LITTLE;
}

void BinaryWriter::update_swap_flag() {
    needs_swap_ = (system_endian_ != target_endian_);
}

uint32_t BinaryWriter::swap32(uint32_t value) {
    return ((value & 0xFF000000) >> 24) |
           ((value & 0x00FF0000) >> 8)  |
           ((value & 0x0000FF00) << 8)  |
           ((value & 0x000000FF) << 24);
}

uint64_t BinaryWriter::swap64(uint64_t value) {
    return ((value & 0xFF00000000000000ULL) >> 56) |
           ((value & 0x00FF000000000000ULL) >> 40) |
           ((value & 0x0000FF0000000000ULL) >> 24) |
           ((value & 0x000000FF00000000ULL) >> 8)  |
           ((value & 0x00000000FF000000ULL) << 8)  |
           ((value & 0x0000000000FF0000ULL) << 24) |
           ((value & 0x000000000000FF00ULL) << 40) |
           ((value & 0x00000000000000FFULL) << 56);
}

// ============================================================
// Write Functions - Single Values
// ============================================================

void BinaryWriter::write_int(int32_t value) {
    uint32_t v;
    std::memcpy(&v, &value, sizeof(v));
    if (needs_swap_) {
        v = swap32(v);
    }
    file_.write(reinterpret_cast<const char*>(&v), sizeof(v));
    bytes_written_ += sizeof(v);
}

void BinaryWriter::write_uint(uint32_t value) {
    if (needs_swap_) {
        value = swap32(value);
    }
    file_.write(reinterpret_cast<const char*>(&value), sizeof(value));
    bytes_written_ += sizeof(value);
}

void BinaryWriter::write_int64(int64_t value) {
    uint64_t v;
    std::memcpy(&v, &value, sizeof(v));
    if (needs_swap_) {
        v = swap64(v);
    }
    file_.write(reinterpret_cast<const char*>(&v), sizeof(v));
    bytes_written_ += sizeof(v);
}

void BinaryWriter::write_float(double value) {
    if (precision_ == Precision::SINGLE) {
        write_float32(static_cast<float>(value));
    } else {
        write_double(value);
    }
}

void BinaryWriter::write_double(double value) {
    uint64_t v;
    std::memcpy(&v, &value, sizeof(v));
    if (needs_swap_) {
        v = swap64(v);
    }
    file_.write(reinterpret_cast<const char*>(&v), sizeof(v));
    bytes_written_ += sizeof(v);
}

void BinaryWriter::write_float32(float value) {
    uint32_t v;
    std::memcpy(&v, &value, sizeof(v));
    if (needs_swap_) {
        v = swap32(v);
    }
    file_.write(reinterpret_cast<const char*>(&v), sizeof(v));
    bytes_written_ += sizeof(v);
}

// ============================================================
// Write Functions - Arrays
// ============================================================

void BinaryWriter::write_int_array(const std::vector<int32_t>& values) {
    write_int_array(values.data(), values.size());
}

void BinaryWriter::write_int_array(const int32_t* values, size_t count) {
    if (!needs_swap_) {
        // Direct write
        file_.write(reinterpret_cast<const char*>(values), count * sizeof(int32_t));
        bytes_written_ += count * sizeof(int32_t);
    } else {
        // Swap each value
        for (size_t i = 0; i < count; ++i) {
            write_int(values[i]);
        }
    }
}

void BinaryWriter::write_float_array(const std::vector<float>& values) {
    write_float_array(values.data(), values.size());
}

void BinaryWriter::write_float_array(const float* values, size_t count) {
    if (precision_ == Precision::SINGLE) {
        if (!needs_swap_) {
            file_.write(reinterpret_cast<const char*>(values), count * sizeof(float));
            bytes_written_ += count * sizeof(float);
        } else {
            for (size_t i = 0; i < count; ++i) {
                write_float32(values[i]);
            }
        }
    } else {
        // Convert to double
        for (size_t i = 0; i < count; ++i) {
            write_double(static_cast<double>(values[i]));
        }
    }
}

void BinaryWriter::write_double_array(const std::vector<double>& values) {
    write_double_array(values.data(), values.size());
}

void BinaryWriter::write_double_array(const double* values, size_t count) {
    if (precision_ == Precision::DOUBLE) {
        if (!needs_swap_) {
            file_.write(reinterpret_cast<const char*>(values), count * sizeof(double));
            bytes_written_ += count * sizeof(double);
        } else {
            for (size_t i = 0; i < count; ++i) {
                write_double(values[i]);
            }
        }
    } else {
        // Convert to float
        for (size_t i = 0; i < count; ++i) {
            write_float32(static_cast<float>(values[i]));
        }
    }
}

// ============================================================
// Write Functions - Strings
// ============================================================

void BinaryWriter::write_string(const std::string& str, size_t length) {
    // Create buffer with spaces
    std::vector<char> buffer(length, ' ');

    // Copy string (truncate if too long)
    size_t copy_len = std::min(str.size(), length);
    std::memcpy(buffer.data(), str.c_str(), copy_len);

    file_.write(buffer.data(), length);
    bytes_written_ += length;
}

// ============================================================
// Write Functions - Raw Data
// ============================================================

void BinaryWriter::write_raw(const void* data, size_t size) {
    file_.write(reinterpret_cast<const char*>(data), size);
    bytes_written_ += size;
}

void BinaryWriter::write_padding(size_t num_bytes) {
    std::vector<char> zeros(num_bytes, 0);
    file_.write(zeros.data(), num_bytes);
    bytes_written_ += num_bytes;
}

void BinaryWriter::write_zero_words(size_t num_words) {
    size_t word_size = get_word_size();
    write_padding(num_words * word_size);
}

} // namespace writer
} // namespace kood3plot
