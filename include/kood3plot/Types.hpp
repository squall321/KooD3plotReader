#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace kood3plot {

/**
 * @brief Precision mode for floating point data
 */
enum class Precision : uint8_t {
    SINGLE = 4,  ///< Single precision (4 bytes per word)
    DOUBLE = 8   ///< Double precision (8 bytes per word)
};

/**
 * @brief Byte order (endianness)
 */
enum class Endian : uint8_t {
    LITTLE = 0,  ///< Little-endian (Intel x86/x64)
    BIG = 1      ///< Big-endian (SPARC, PowerPC)
};

/**
 * @brief Element type enumeration
 */
enum class ElementType : uint8_t {
    BEAM = 0,         ///< 2-node beam element
    SHELL = 1,        ///< 4-node shell element
    THICK_SHELL = 2,  ///< 8-node thick shell element
    SOLID = 3         ///< 8-node solid element
};

/**
 * @brief Material model type
 */
enum class MaterialModel : int32_t {
    ELASTIC = 1,
    ORTHOTROPIC_ELASTIC = 2,
    KINEMATIC_PLASTIC = 3,
    // Add more as needed from LS-DYNA documentation
    UNKNOWN = -1
};

/**
 * @brief Node data structure
 */
struct Node {
    int32_t id;           ///< Node ID
    double x;             ///< X coordinate
    double y;             ///< Y coordinate
    double z;             ///< Z coordinate
};

/**
 * @brief Element connectivity (indices to Node array)
 */
struct Element {
    int32_t id;                      ///< Element ID
    ElementType type;                ///< Element type
    int32_t material_id;             ///< Material ID
    std::vector<int32_t> node_ids;   ///< Node IDs (2 for beam, 4 for shell, 8 for solid/thick_shell)
};

/**
 * @brief Time history point data
 */
struct TimeState {
    double time;                           ///< Simulation time
    std::vector<double> node_displacements; ///< Node displacements (Ux, Uy, Uz, Vx, Vy, Vz, Ax, Ay, Az per node)
    std::vector<double> element_stresses;   ///< Element stresses (varies by element type)
    std::vector<double> element_strains;    ///< Element strains (varies by element type)
};

/**
 * @brief File format information
 */
struct FileFormat {
    Precision precision;  ///< Single or double precision
    Endian endian;        ///< Little or big endian
    int32_t word_size;    ///< Word size in bytes (4 or 8)
    double version;       ///< LS-DYNA version (e.g., 971.0)
    std::string title;    ///< File title from control section
};

/**
 * @brief Error codes
 */
enum class ErrorCode : int32_t {
    SUCCESS = 0,
    FILE_NOT_FOUND = -1,
    INVALID_FORMAT = -2,
    UNSUPPORTED_VERSION = -3,
    CORRUPTED_DATA = -4,
    MEMORY_ERROR = -5,
    IO_ERROR = -6,
    UNKNOWN_ERROR = -99
};

/**
 * @brief Convert error code to string description
 */
inline std::string error_to_string(ErrorCode err) {
    switch (err) {
        case ErrorCode::SUCCESS:
            return "Success";
        case ErrorCode::FILE_NOT_FOUND:
            return "File not found";
        case ErrorCode::INVALID_FORMAT:
            return "Invalid d3plot format";
        case ErrorCode::UNSUPPORTED_VERSION:
            return "Unsupported LS-DYNA version";
        case ErrorCode::CORRUPTED_DATA:
            return "Corrupted data detected";
        case ErrorCode::MEMORY_ERROR:
            return "Memory allocation error";
        case ErrorCode::IO_ERROR:
            return "I/O error";
        default:
            return "Unknown error";
    }
}

} // namespace kood3plot
