/**
 * @file VtkToRadiossConverter.h
 * @brief VTK to OpenRadioss animation file converter
 * @author KooD3plot V2 Development Team
 * @date 2026-01-25
 * @version 2.0.0
 */

#pragma once

#include "kood3plot/converter/VtkReader.h"
#include "kood3plot/converter/RadiossWriter.h"
#include <string>
#include <vector>

namespace kood3plot {
namespace converter {

/**
 * @brief Options for VTK to Radioss conversion
 */
struct VtkToRadiossOptions {
    std::string title = "KooD3plot VTK to Radioss Conversion";
    bool convert_displacement = true;
    bool convert_velocity = true;
    bool convert_stress = true;
    bool verbose = false;
};

/**
 * @brief Result of VTK to Radioss conversion
 */
struct VtkToRadiossResult {
    bool success = false;
    std::string error_message;
    size_t num_nodes = 0;
    size_t num_elements = 0;
    size_t num_states = 0;
    size_t bytes_written = 0;
};

/**
 * @brief Converts VTK files to OpenRadioss animation format
 */
class VtkToRadiossConverter {
public:
    VtkToRadiossConverter();
    ~VtkToRadiossConverter();

    /**
     * @brief Set conversion options
     */
    void setOptions(const VtkToRadiossOptions& options);

    /**
     * @brief Convert single VTK file to Radioss
     * @param vtk_mesh VTK mesh data
     * @param output_base Base path for output (e.g., "output/A0")
     * @return Conversion result
     */
    VtkToRadiossResult convert(const VtkMesh& vtk_mesh, const std::string& output_base);

    /**
     * @brief Convert multiple VTK files (time series) to Radioss
     * @param vtk_meshes Vector of VTK mesh data for each timestep
     * @param output_base Base path for output
     * @return Conversion result
     */
    VtkToRadiossResult convertSeries(
        const std::vector<VtkMesh>& vtk_meshes,
        const std::string& output_base);

    /**
     * @brief Get last error message
     */
    std::string getLastError() const { return last_error_; }

private:
    VtkToRadiossOptions options_;
    std::string last_error_;

    /**
     * @brief Build Radioss header from VTK mesh
     */
    RadiossHeader buildHeader(const VtkMesh& vtk_mesh);

    /**
     * @brief Build Radioss mesh from VTK mesh
     */
    RadiossMesh buildMesh(const VtkMesh& vtk_mesh);

    /**
     * @brief Build Radioss state from VTK mesh
     */
    RadiossState buildState(const VtkMesh& vtk_mesh);

    /**
     * @brief Find data array by name (case-insensitive partial match)
     */
    const VtkDataArray* findDataArray(
        const std::vector<VtkDataArray>& arrays,
        const std::string& name_pattern);
};

} // namespace converter
} // namespace kood3plot
