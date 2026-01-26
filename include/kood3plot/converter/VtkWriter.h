/**
 * @file VtkWriter.h
 * @brief VTK file writer
 * @author KooD3plot V2 Development Team
 * @date 2026-01-23
 * @version 2.0.0
 */

#pragma once

#include "kood3plot/converter/VtkReader.h"
#include "kood3plot/Types.hpp"
#include <string>
#include <fstream>

namespace kood3plot {
namespace converter {

/**
 * @brief VTK writer options
 */
struct VtkWriterOptions {
    bool verbose = false;                   ///< Verbose output
    VtkFormat format = VtkFormat::LEGACY_ASCII;  ///< Output format
    bool write_binary = false;              ///< Write binary format (ASCII if false)
};

/**
 * @brief VTK file writer class
 */
class VtkWriter {
public:
    /**
     * @brief Constructor
     * @param filepath Path to output VTK file
     */
    explicit VtkWriter(const std::string& filepath);

    /**
     * @brief Destructor
     */
    ~VtkWriter();

    // Non-copyable
    VtkWriter(const VtkWriter&) = delete;
    VtkWriter& operator=(const VtkWriter&) = delete;

    /**
     * @brief Set writer options
     */
    void setOptions(const VtkWriterOptions& options);

    /**
     * @brief Write VTK mesh to file
     * @param mesh VTK mesh data to write
     * @return ErrorCode::SUCCESS on success
     */
    ErrorCode write(const VtkMesh& mesh);

    /**
     * @brief Get last error message
     */
    std::string getLastError() const;

    /**
     * @brief Get bytes written
     */
    size_t getBytesWritten() const;

private:
    std::string filepath_;
    VtkWriterOptions options_;
    std::string last_error_;
    size_t bytes_written_ = 0;
    std::ofstream file_;

    // Write functions for different formats
    ErrorCode writeLegacyAscii(const VtkMesh& mesh);

    // Helper functions
    void writeLine(const std::string& line);
    std::string vtkCellTypeToString(VtkCellType type);
};

} // namespace converter
} // namespace kood3plot
