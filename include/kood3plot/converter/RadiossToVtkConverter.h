/**
 * @file RadiossToVtkConverter.h
 * @brief OpenRadioss animation to VTK converter
 * @author KooD3plot V2 Development Team
 * @date 2026-01-24
 * @version 2.0.0
 */

#pragma once

#include "kood3plot/converter/RadiossReader.h"
#include "kood3plot/converter/VtkReader.h"
#include "kood3plot/converter/VtkWriter.h"
#include <string>

namespace kood3plot {
namespace converter {

/**
 * @brief Options for Radioss to VTK conversion
 */
struct RadiossToVtkOptions {
    std::string title;                     ///< VTK dataset title
    bool export_displacement = true;       ///< Export displacement vectors
    bool export_velocity = true;           ///< Export velocity vectors
    bool export_acceleration = true;       ///< Export acceleration vectors
    bool export_stress = true;             ///< Export stress tensors
    bool export_strain = true;             ///< Export strain tensors
    bool export_plastic_strain = true;     ///< Export plastic strain
    bool verbose = false;                  ///< Verbose output
    VtkFormat vtk_format = VtkFormat::LEGACY_ASCII;  ///< Output format
};

/**
 * @brief Result of Radioss to VTK conversion
 */
struct RadiossToVtkResult {
    bool success = false;
    std::string error_message;
    size_t num_nodes = 0;
    size_t num_cells = 0;
    size_t num_point_arrays = 0;
    size_t num_cell_arrays = 0;
    size_t bytes_written = 0;
    std::vector<std::string> output_files;
};

/**
 * @brief Converts OpenRadioss animation files to VTK format
 */
class RadiossToVtkConverter {
public:
    RadiossToVtkConverter();
    ~RadiossToVtkConverter();

    /**
     * @brief Set conversion options
     */
    void setOptions(const RadiossToVtkOptions& options);

    /**
     * @brief Convert single Radioss state to VTK
     * @param header Radioss header information
     * @param mesh Radioss mesh geometry
     * @param state Radioss state data
     * @param output_path Output VTK file path
     * @return Conversion result
     */
    RadiossToVtkResult convert(
        const RadiossHeader& header,
        const RadiossMesh& mesh,
        const RadiossState& state,
        const std::string& output_path);

    /**
     * @brief Convert multiple Radioss states to VTK time series
     * @param header Radioss header information
     * @param mesh Radioss mesh geometry
     * @param states Vector of state data
     * @param output_base Base output path (will add _0000.vtk, _0001.vtk, etc.)
     * @return Conversion result
     */
    RadiossToVtkResult convertSeries(
        const RadiossHeader& header,
        const RadiossMesh& mesh,
        const std::vector<RadiossState>& states,
        const std::string& output_base);

    /**
     * @brief Get last error message
     */
    std::string getLastError() const;

private:
    RadiossToVtkOptions options_;
    std::string last_error_;

    /**
     * @brief Build VTK mesh from Radioss data
     */
    VtkMesh buildVtkMesh(
        const RadiossHeader& header,
        const RadiossMesh& mesh,
        const RadiossState& state);

    /**
     * @brief Add point data arrays to VTK mesh
     */
    void addPointData(
        VtkMesh& vtk_mesh,
        const RadiossHeader& header,
        const RadiossMesh& mesh,
        const RadiossState& state);

    /**
     * @brief Add cell data arrays to VTK mesh
     */
    void addCellData(
        VtkMesh& vtk_mesh,
        const RadiossHeader& header,
        const RadiossMesh& mesh,
        const RadiossState& state);
};

} // namespace converter
} // namespace kood3plot
