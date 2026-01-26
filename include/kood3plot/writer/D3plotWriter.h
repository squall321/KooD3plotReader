/**
 * @file D3plotWriter.h
 * @brief High-level d3plot file writer
 * @author KooD3plot V2 Development Team
 * @date 2026-01-22
 * @version 2.0.0
 *
 * This class writes LS-DYNA d3plot binary files from ControlData, Mesh, and StateData.
 * It supports:
 * - Single/Double precision output
 * - Little/Big endian output
 * - Multi-file output (automatic splitting)
 * - All element types (solid, shell, beam, thick shell)
 */

#pragma once

#include "kood3plot/Types.hpp"
#include "kood3plot/data/ControlData.hpp"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"
#include "kood3plot/writer/BinaryWriter.h"

#include <string>
#include <vector>
#include <memory>

namespace kood3plot {
namespace writer {

/**
 * @brief Options for D3plotWriter
 */
struct WriterOptions {
    Precision precision = Precision::SINGLE;    ///< Output precision
    Endian endian = Endian::LITTLE;             ///< Output endianness
    size_t max_file_size = 2ULL * 1024 * 1024 * 1024; ///< Max file size before split (2GB)
    bool write_narbs = true;                    ///< Write NARBS section if available
    bool verbose = false;                       ///< Verbose output
};

/**
 * @brief High-level d3plot writer
 *
 * Usage:
 * @code
 * D3plotWriter writer("output.d3plot");
 * writer.setControlData(control);
 * writer.setMesh(mesh);
 * writer.setStates(states);
 * writer.write();
 * @endcode
 */
class D3plotWriter {
public:
    /**
     * @brief Constructor
     * @param output_path Base path for output file(s)
     */
    explicit D3plotWriter(const std::string& output_path);

    /**
     * @brief Destructor
     */
    ~D3plotWriter();

    // Disable copy
    D3plotWriter(const D3plotWriter&) = delete;
    D3plotWriter& operator=(const D3plotWriter&) = delete;

    // ========================================
    // Configuration
    // ========================================

    /**
     * @brief Set writer options
     */
    void setOptions(const WriterOptions& options);

    /**
     * @brief Get current options
     */
    const WriterOptions& getOptions() const;

    /**
     * @brief Set output precision
     */
    void setPrecision(Precision prec);

    /**
     * @brief Set output endianness
     */
    void setEndian(Endian endian);

    /**
     * @brief Set maximum file size for multi-file output
     * @param bytes Maximum bytes per file (default: 2GB)
     */
    void setMaxFileSize(size_t bytes);

    // ========================================
    // Data Input
    // ========================================

    /**
     * @brief Set control data (model metadata)
     * @param control Control data structure
     */
    void setControlData(const data::ControlData& control);

    /**
     * @brief Set mesh data (geometry)
     * @param mesh Mesh structure
     */
    void setMesh(const data::Mesh& mesh);

    /**
     * @brief Add a single state
     * @param state State data to add
     */
    void addState(const data::StateData& state);

    /**
     * @brief Set all states at once
     * @param states Vector of state data
     */
    void setStates(const std::vector<data::StateData>& states);

    /**
     * @brief Clear all states
     */
    void clearStates();

    // ========================================
    // Writing
    // ========================================

    /**
     * @brief Write all data to d3plot file(s)
     * @return ErrorCode::SUCCESS on success
     */
    ErrorCode write();

    /**
     * @brief Write geometry only (no states)
     * @return ErrorCode::SUCCESS on success
     */
    ErrorCode writeGeometryOnly();

    // ========================================
    // Status and Info
    // ========================================

    /**
     * @brief Get last error message
     */
    std::string getLastError() const;

    /**
     * @brief Get total bytes written
     */
    size_t getWrittenBytes() const;

    /**
     * @brief Get list of output files created
     */
    std::vector<std::string> getOutputFiles() const;

    /**
     * @brief Get number of states written
     */
    size_t getStatesWritten() const;

private:
    class Impl;
    std::unique_ptr<Impl> pImpl;
};

} // namespace writer
} // namespace kood3plot
