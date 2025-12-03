#pragma once

#include "kood3plot/Types.hpp"
#include <cstdint>
#include <cstring>

namespace kood3plot {
namespace core {

/**
 * @brief Endianness detection and byte swapping utilities
 */
class EndianUtils {
public:
    /**
     * @brief Detect system endianness at runtime
     */
    static inline Endian get_system_endian() {
        // Use union trick to detect endianness
        union {
            uint32_t i;
            uint8_t bytes[4];
        } test = { 0x01020304 };

        // Little-endian: bytes[0] = 0x04
        // Big-endian:    bytes[0] = 0x01
        return (test.bytes[0] == 0x04) ? Endian::LITTLE : Endian::BIG;
    }

    /**
     * @brief Swap bytes for 16-bit value
     */
    static inline uint16_t swap_bytes(uint16_t value) {
        return (value >> 8) | (value << 8);
    }

    /**
     * @brief Swap bytes for 32-bit value
     */
    static inline uint32_t swap_bytes(uint32_t value) {
        return ((value >> 24) & 0x000000FF) |
               ((value >> 8)  & 0x0000FF00) |
               ((value << 8)  & 0x00FF0000) |
               ((value << 24) & 0xFF000000);
    }

    /**
     * @brief Swap bytes for 64-bit value
     */
    static inline uint64_t swap_bytes(uint64_t value) {
        return ((value >> 56) & 0x00000000000000FFULL) |
               ((value >> 40) & 0x000000000000FF00ULL) |
               ((value >> 24) & 0x0000000000FF0000ULL) |
               ((value >> 8)  & 0x00000000FF000000ULL) |
               ((value << 8)  & 0x000000FF00000000ULL) |
               ((value << 24) & 0x0000FF0000000000ULL) |
               ((value << 40) & 0x00FF000000000000ULL) |
               ((value << 56) & 0xFF00000000000000ULL);
    }

    /**
     * @brief Swap bytes for float (32-bit)
     */
    static inline float swap_bytes(float value) {
        uint32_t temp;
        std::memcpy(&temp, &value, sizeof(float));
        temp = swap_bytes(temp);
        float result;
        std::memcpy(&result, &temp, sizeof(float));
        return result;
    }

    /**
     * @brief Swap bytes for double (64-bit)
     */
    static inline double swap_bytes(double value) {
        uint64_t temp;
        std::memcpy(&temp, &value, sizeof(double));
        temp = swap_bytes(temp);
        double result;
        std::memcpy(&result, &temp, sizeof(double));
        return result;
    }

    /**
     * @brief Swap bytes for int32_t
     */
    static inline int32_t swap_bytes(int32_t value) {
        uint32_t temp;
        std::memcpy(&temp, &value, sizeof(int32_t));
        temp = swap_bytes(temp);
        int32_t result;
        std::memcpy(&result, &temp, sizeof(int32_t));
        return result;
    }

    /**
     * @brief Check if byte swap is needed based on file and system endianness
     */
    static inline bool needs_swap(Endian file_endian, Endian system_endian) {
        return file_endian != system_endian;
    }
};

} // namespace core
} // namespace kood3plot
