/**
 * @file RadiossWriter.h
 * @brief OpenRadioss animation file (A00/A01) writer
 * @author KooD3plot V2 Development Team
 * @date 2026-01-25
 * @version 2.0.0
 */

#pragma once

#include "kood3plot/converter/RadiossReader.h"
#include <string>
#include <fstream>
#include <vector>

namespace kood3plot {
namespace converter {

/**
 * @brief Options for writing Radioss animation files
 */
struct RadiossWriterOptions {
    std::string title = "KooD3plot Conversion";
    bool write_velocity = true;
    bool write_displacement = true;
    bool write_acceleration = false;
    bool write_stress = true;
    bool write_plastic_strain = true;
    bool verbose = false;
};

/**
 * @brief Writes OpenRadioss animation files (A00/A01/...)
 *
 * File format based on OpenRadioss genani.F source code analysis.
 */
class RadiossWriter {
public:
    /**
     * @brief Constructor
     * @param base_path Base path for output files (e.g., "output/A0")
     *                  Will create A00, A01, A02, ...
     */
    RadiossWriter(const std::string& base_path);
    ~RadiossWriter();

    /**
     * @brief Set writer options
     */
    void setOptions(const RadiossWriterOptions& options);

    /**
     * @brief Write A00 file (header + geometry)
     * @param header Header information
     * @param mesh Mesh geometry
     * @return Error code
     */
    ErrorCode writeHeader(const RadiossHeader& header, const RadiossMesh& mesh);

    /**
     * @brief Write state file (A01, A02, ...)
     * @param state_index State index (1 for A01, 2 for A02, ...)
     * @param state State data
     * @return Error code
     */
    ErrorCode writeState(size_t state_index, const RadiossState& state);

    /**
     * @brief Write all states
     * @param states Vector of state data
     * @return Error code
     */
    ErrorCode writeAllStates(const std::vector<RadiossState>& states);

    /**
     * @brief Get last error message
     */
    std::string getLastError() const { return last_error_; }

    /**
     * @brief Get total bytes written
     */
    size_t getBytesWritten() const { return bytes_written_; }

private:
    std::string base_path_;
    std::string a00_path_;
    RadiossWriterOptions options_;
    RadiossHeader header_;
    std::string last_error_;
    size_t bytes_written_ = 0;

    std::ofstream file_;

    // Binary writing helpers
    template<typename T>
    void writeBinary(T value);

    void writeBinaryArray(const void* data, size_t size);

    /**
     * @brief Write fixed-length string (81 bytes, null-padded)
     */
    void writeString(const std::string& str, size_t length = 81);

    /**
     * @brief Get state file path
     */
    std::string getStateFilePath(size_t state_index) const;
};

} // namespace converter
} // namespace kood3plot
