/**
 * @file RadiossReader.h
 * @brief OpenRadioss animation file (A00/A01) reader
 * @author KooD3plot V2 Development Team
 * @date 2026-01-23
 * @version 2.0.0
 *
 * NOTE: Radioss A00 file format is not officially documented.
 * This implementation is based on reverse engineering of anim_to_vtk
 * and community knowledge.
 *
 * File structure (preliminary):
 * - A00: Header + geometry data
 * - A01, A02, ...: State data (displacement, velocity, stress, etc.)
 */

#pragma once

#include "kood3plot/Types.hpp"
#include <string>
#include <vector>
#include <fstream>

namespace kood3plot {
namespace converter {

/**
 * @brief Radioss animation file header
 */
struct RadiossHeader {
    std::string title;              ///< Simulation title (81 chars)
    int32_t num_nodes;              ///< Number of nodes
    int32_t num_solids;             ///< Number of solid elements
    int32_t num_shells;             ///< Number of shell elements
    int32_t num_beams;              ///< Number of beam elements
    int32_t num_states;             ///< Number of time states

    // Variable flags
    bool has_displacement;
    bool has_velocity;
    bool has_acceleration;
    bool has_stress;
    bool has_strain;
    bool has_plastic_strain;

    // Precision
    int word_size;                  ///< 4 (single) or 8 (double)
};

/**
 * @brief Radioss mesh geometry
 */
struct RadiossMesh {
    std::vector<Node> nodes;
    std::vector<Element> solids;
    std::vector<Element> shells;
    std::vector<Element> beams;

    // Part information
    std::vector<int32_t> solid_parts;
    std::vector<int32_t> shell_parts;
    std::vector<int32_t> beam_parts;
};

/**
 * @brief Radioss state data (one timestep)
 */
struct RadiossState {
    double time;

    // Nodal data
    std::vector<double> node_displacements;  ///< 3 * num_nodes
    std::vector<double> node_velocities;     ///< 3 * num_nodes
    std::vector<double> node_accelerations;  ///< 3 * num_nodes

    // Element data
    std::vector<double> solid_stress;        ///< 6 * num_solids (Voigt)
    std::vector<double> shell_stress;        ///< 6 * num_shells
    std::vector<double> solid_strain;        ///< 6 * num_solids
    std::vector<double> shell_strain;        ///< 6 * num_shells
    std::vector<double> plastic_strain;      ///< num_elements
};

/**
 * @brief OpenRadioss animation file reader
 */
class RadiossReader {
public:
    /**
     * @brief Constructor
     * @param a00_filepath Path to A00 file (header + geometry)
     */
    explicit RadiossReader(const std::string& a00_filepath);

    /**
     * @brief Destructor
     */
    ~RadiossReader();

    // Non-copyable
    RadiossReader(const RadiossReader&) = delete;
    RadiossReader& operator=(const RadiossReader&) = delete;

    /**
     * @brief Open and parse A00 file
     * @return ErrorCode::SUCCESS on success
     */
    ErrorCode open();

    /**
     * @brief Read all state files (A01, A02, ...)
     * @param max_states Maximum number of states to read (0 = all)
     * @return Vector of state data
     */
    std::vector<RadiossState> readAllStates(size_t max_states = 0);

    /**
     * @brief Read specific state file
     * @param state_index State index (1-based: A01=1, A02=2, ...)
     * @return State data
     */
    RadiossState readState(size_t state_index);

    /**
     * @brief Get header information
     */
    const RadiossHeader& getHeader() const { return header_; }

    /**
     * @brief Get mesh geometry
     */
    const RadiossMesh& getMesh() const { return mesh_; }

    /**
     * @brief Get last error message
     */
    std::string getLastError() const { return last_error_; }

    /**
     * @brief Close all files
     */
    void close();

private:
    std::string a00_path_;
    std::string base_path_;         ///< Base path without extension (e.g., "sim/A00" -> "sim/A0")

    RadiossHeader header_;
    RadiossMesh mesh_;

    std::ifstream file_;
    std::string last_error_;

    // Parsing functions
    ErrorCode parseHeader();
    ErrorCode parseGeometry();
    ErrorCode parseStateFile(const std::string& filepath, RadiossState& state);

    // Helper functions
    std::string getStateFilePath(size_t state_index) const;
    bool stateFileExists(size_t state_index) const;

    // Endian handling
    bool need_swap_ = false;  ///< True if file endian != host endian

    static void swapBytes(void* data, size_t size);
    static void swapArray(void* data, size_t elem_size, size_t count);

    // Binary reading helpers
    template<typename T>
    T readBinary();

    template<typename T>
    T readBinaryFrom(std::ifstream& f);

    void readBinaryArray(void* data, size_t size);

    /**
     * @brief Read fixed-length string (null-padded)
     * @param length String length in bytes
     * @return Parsed string (without null padding)
     */
    std::string readString(size_t length);
};

} // namespace converter
} // namespace kood3plot
