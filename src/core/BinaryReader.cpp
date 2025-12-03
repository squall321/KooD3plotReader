#include "kood3plot/core/BinaryReader.hpp"
#include "kood3plot/core/Endian.hpp"
#include <stdexcept>
#include <cstring>

namespace kood3plot {
namespace core {

BinaryReader::BinaryReader(const std::string& filepath)
    : filepath_(filepath)
    , precision_(Precision::SINGLE)
    , endian_(Endian::LITTLE)
    , word_size_(4)
    , file_size_(0) {
}

BinaryReader::~BinaryReader() {
    close();
}

ErrorCode BinaryReader::open() {
    // Open file in binary mode
    file_.open(filepath_, std::ios::binary | std::ios::in);

    if (!file_.is_open()) {
        return ErrorCode::FILE_NOT_FOUND;
    }

    // Check file size
    file_.seekg(0, std::ios::end);
    file_size_ = static_cast<size_t>(file_.tellg());
    file_.seekg(0, std::ios::beg);

    if (file_size_ < 64 * 8) {  // Minimum size for control data
        file_.close();
        return ErrorCode::INVALID_FORMAT;
    }

    // Detect format (precision and endianness)
    try {
        detect_format();
    } catch (const std::exception&) {
        file_.close();
        return ErrorCode::INVALID_FORMAT;
    }

    return ErrorCode::SUCCESS;
}

void BinaryReader::close() {
    if (file_.is_open()) {
        file_.close();
    }
}

ErrorCode BinaryReader::open_family_file(Precision precision, Endian endian) {
    // Open family file with known format (no detection needed)
    file_.open(filepath_, std::ios::binary);

    if (!file_) {
        return ErrorCode::FILE_NOT_FOUND;
    }

    // Get file size
    file_.seekg(0, std::ios::end);
    file_size_ = static_cast<size_t>(file_.tellg());
    file_.seekg(0, std::ios::beg);

    // Use provided format
    precision_ = precision;
    endian_ = endian;
    word_size_ = (precision == Precision::SINGLE) ? 4 : 8;

    return ErrorCode::SUCCESS;
}

bool BinaryReader::is_open() const {
    return file_.is_open();
}

double BinaryReader::get_version() const {
    // Read version from word 14 (const method - read without caching)
    if (!file_.is_open()) {
        return 0.0;
    }

    const size_t version_word_addr = 14;

    // Save current position
    auto saved_pos = const_cast<std::ifstream&>(file_).tellg();

    double version = 0.0;
    if (precision_ == Precision::SINGLE) {
        const_cast<std::ifstream&>(file_).seekg(version_word_addr * 4, std::ios::beg);
        float val;
        const_cast<std::ifstream&>(file_).read(reinterpret_cast<char*>(&val), sizeof(float));
        if (endian_ != EndianUtils::get_system_endian()) {
            val = EndianUtils::swap_bytes(val);
        }
        version = static_cast<double>(val);
    } else {
        const_cast<std::ifstream&>(file_).seekg(version_word_addr * 8, std::ios::beg);
        const_cast<std::ifstream&>(file_).read(reinterpret_cast<char*>(&version), sizeof(double));
        if (endian_ != EndianUtils::get_system_endian()) {
            version = EndianUtils::swap_bytes(version);
        }
    }

    // Restore position
    const_cast<std::ifstream&>(file_).seekg(saved_pos);

    return version;
}

void BinaryReader::detect_format() {
    // Version is stored at word address 14 (0-indexed: word 15)
    // We'll try all 4 combinations: single/double × little/big endian

    const size_t version_word_addr = 14;

    // Try 1: Single precision, little endian
    {
        file_.seekg(version_word_addr * 4, std::ios::beg);
        float value;
        file_.read(reinterpret_cast<char*>(&value), sizeof(float));

        if (is_valid_version(static_cast<double>(value))) {
            precision_ = Precision::SINGLE;
            endian_ = Endian::LITTLE;
            word_size_ = 4;
            return;
        }
    }

    // Try 2: Single precision, big endian (swap bytes)
    {
        file_.seekg(version_word_addr * 4, std::ios::beg);
        float value;
        file_.read(reinterpret_cast<char*>(&value), sizeof(float));
        value = EndianUtils::swap_bytes(value);

        if (is_valid_version(static_cast<double>(value))) {
            precision_ = Precision::SINGLE;
            endian_ = Endian::BIG;
            word_size_ = 4;
            return;
        }
    }

    // Try 3: Double precision, little endian
    {
        file_.seekg(version_word_addr * 8, std::ios::beg);
        double value;
        file_.read(reinterpret_cast<char*>(&value), sizeof(double));

        if (is_valid_version(value)) {
            precision_ = Precision::DOUBLE;
            endian_ = Endian::LITTLE;
            word_size_ = 8;
            return;
        }
    }

    // Try 4: Double precision, big endian (swap bytes)
    {
        file_.seekg(version_word_addr * 8, std::ios::beg);
        double value;
        file_.read(reinterpret_cast<char*>(&value), sizeof(double));
        value = EndianUtils::swap_bytes(value);

        if (is_valid_version(value)) {
            precision_ = Precision::DOUBLE;
            endian_ = Endian::BIG;
            word_size_ = 8;
            return;
        }
    }

    // If we get here, format detection failed
    throw std::runtime_error("Unable to detect d3plot format");
}

bool BinaryReader::is_valid_version(double version) const {
    // LS-DYNA versions typically range from 900 to 1500+
    // Also check for reasonable values (not NaN, not Inf)
    return (version >= 900.0 && version <= 2000.0);
}

int32_t BinaryReader::read_int(size_t word_address) {
    if (!file_.is_open()) {
        throw std::runtime_error("File not open");
    }

    // Clear any error flags before seeking (eof, fail, bad)
    // This is critical for multiple reads from the same file
    file_.clear();

    // Seek to byte position
    size_t byte_offset = word_address * word_size_;
    file_.seekg(byte_offset, std::ios::beg);

    int32_t value;
    file_.read(reinterpret_cast<char*>(&value), sizeof(int32_t));

    // Swap bytes if needed
    Endian system_endian = EndianUtils::get_system_endian();
    if (EndianUtils::needs_swap(endian_, system_endian)) {
        value = EndianUtils::swap_bytes(value);
    }

    return value;
}

float BinaryReader::read_float(size_t word_address) {
    if (!file_.is_open()) {
        throw std::runtime_error("File not open");
    }

    // Clear any error flags before seeking (eof, fail, bad)
    // This is critical for multiple reads from the same file
    file_.clear();

    // For single precision files, read 4 bytes
    // For double precision files, read 8 bytes and convert
    size_t byte_offset = word_address * word_size_;
    file_.seekg(byte_offset, std::ios::beg);

    if (precision_ == Precision::SINGLE) {
        float value;
        file_.read(reinterpret_cast<char*>(&value), sizeof(float));

        // Swap bytes if needed
        Endian system_endian = EndianUtils::get_system_endian();
        if (EndianUtils::needs_swap(endian_, system_endian)) {
            value = EndianUtils::swap_bytes(value);
        }

        return value;
    } else {
        // Double precision - read as double and convert
        double value;
        file_.read(reinterpret_cast<char*>(&value), sizeof(double));

        // Swap bytes if needed
        Endian system_endian = EndianUtils::get_system_endian();
        if (EndianUtils::needs_swap(endian_, system_endian)) {
            value = EndianUtils::swap_bytes(value);
        }

        return static_cast<float>(value);
    }
}

double BinaryReader::read_double(size_t word_address) {
    if (!file_.is_open()) {
        throw std::runtime_error("File not open");
    }

    // Check file boundary
    size_t byte_offset = word_address * word_size_;
    if (byte_offset + word_size_ > file_size_) {
        throw std::runtime_error("Read beyond end of file at word " + std::to_string(word_address));
    }

    // Clear any error flags before seeking (eof, fail, bad)
    // This is critical for multiple reads from the same file
    file_.clear();

    file_.seekg(byte_offset, std::ios::beg);

    if (precision_ == Precision::DOUBLE) {
        double value;
        file_.read(reinterpret_cast<char*>(&value), sizeof(double));

        // Swap bytes if needed
        Endian system_endian = EndianUtils::get_system_endian();
        if (EndianUtils::needs_swap(endian_, system_endian)) {
            value = EndianUtils::swap_bytes(value);
        }

        return value;
    } else {
        // Single precision - read as float and convert
        float value;
        file_.read(reinterpret_cast<char*>(&value), sizeof(float));

        // Swap bytes if needed
        Endian system_endian = EndianUtils::get_system_endian();
        if (EndianUtils::needs_swap(endian_, system_endian)) {
            value = EndianUtils::swap_bytes(value);
        }

        return static_cast<double>(value);
    }
}

std::vector<int32_t> BinaryReader::read_int_array(size_t word_address, size_t count) {
    if (!file_.is_open()) {
        throw std::runtime_error("File not open");
    }

    // Clear any error flags before seeking (eof, fail, bad)
    // This is critical for multiple reads from the same file
    file_.clear();

    std::vector<int32_t> result(count);

    size_t byte_offset = word_address * word_size_;
    file_.seekg(byte_offset, std::ios::beg);

    // Read all values at once
    file_.read(reinterpret_cast<char*>(result.data()), count * sizeof(int32_t));

    // Swap bytes if needed
    Endian system_endian = EndianUtils::get_system_endian();
    if (EndianUtils::needs_swap(endian_, system_endian)) {
        for (size_t i = 0; i < count; ++i) {
            result[i] = EndianUtils::swap_bytes(result[i]);
        }
    }

    return result;
}

std::vector<float> BinaryReader::read_float_array(size_t word_address, size_t count) {
    if (!file_.is_open()) {
        throw std::runtime_error("File not open");
    }

    std::vector<float> result(count);

    size_t byte_offset = word_address * word_size_;
    file_.seekg(byte_offset, std::ios::beg);

    if (precision_ == Precision::SINGLE) {
        // Read as float array
        file_.read(reinterpret_cast<char*>(result.data()), count * sizeof(float));

        // Swap bytes if needed
        Endian system_endian = EndianUtils::get_system_endian();
        if (EndianUtils::needs_swap(endian_, system_endian)) {
            for (size_t i = 0; i < count; ++i) {
                result[i] = EndianUtils::swap_bytes(result[i]);
            }
        }
    } else {
        // Double precision - read as double and convert
        std::vector<double> temp(count);
        file_.read(reinterpret_cast<char*>(temp.data()), count * sizeof(double));

        // Swap bytes if needed
        Endian system_endian = EndianUtils::get_system_endian();
        if (EndianUtils::needs_swap(endian_, system_endian)) {
            for (size_t i = 0; i < count; ++i) {
                temp[i] = EndianUtils::swap_bytes(temp[i]);
            }
        }

        // Convert to float
        for (size_t i = 0; i < count; ++i) {
            result[i] = static_cast<float>(temp[i]);
        }
    }

    return result;
}

std::vector<double> BinaryReader::read_double_array(size_t word_address, size_t count) {
    if (!file_.is_open()) {
        throw std::runtime_error("File not open");
    }

    // Clear any error flags before seeking (eof, fail, bad)
    // This is critical for multiple reads from the same file
    file_.clear();

    std::vector<double> result(count);

    size_t byte_offset = word_address * word_size_;
    file_.seekg(byte_offset, std::ios::beg);

    if (precision_ == Precision::DOUBLE) {
        // Read as double array
        file_.read(reinterpret_cast<char*>(result.data()), count * sizeof(double));

        // Swap bytes if needed
        Endian system_endian = EndianUtils::get_system_endian();
        if (EndianUtils::needs_swap(endian_, system_endian)) {
            for (size_t i = 0; i < count; ++i) {
                result[i] = EndianUtils::swap_bytes(result[i]);
            }
        }
    } else {
        // Single precision - read as float and convert
        std::vector<float> temp(count);
        file_.read(reinterpret_cast<char*>(temp.data()), count * sizeof(float));

        // Swap bytes if needed
        Endian system_endian = EndianUtils::get_system_endian();
        if (EndianUtils::needs_swap(endian_, system_endian)) {
            for (size_t i = 0; i < count; ++i) {
                temp[i] = EndianUtils::swap_bytes(temp[i]);
            }
        }

        // Convert to double
        for (size_t i = 0; i < count; ++i) {
            result[i] = static_cast<double>(temp[i]);
        }
    }

    return result;
}

} // namespace core
} // namespace kood3plot
