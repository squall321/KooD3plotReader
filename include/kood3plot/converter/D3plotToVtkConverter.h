/**
 * @file D3plotToVtkConverter.h
 * @brief D3plot to VTK converter
 * @author KooD3plot V2 Development Team
 * @date 2026-01-23
 * @version 2.0.0
 */

#pragma once

#include "kood3plot/converter/VtkReader.h"
#include "kood3plot/converter/VtkWriter.h"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"
#include "kood3plot/data/ControlData.hpp"
#include "kood3plot/Types.hpp"
#include <string>
#include <vector>

namespace kood3plot {
namespace converter {

/**
 * @brief D3plot to VTK conversion options
 */
struct D3plotToVtkOptions {
    std::string title = "D3plot Data";    ///< VTK file title
    bool verbose = false;                  ///< Verbose output

    // Data export options
    bool export_displacement = true;       ///< Export nodal displacement
    bool export_velocity = true;           ///< Export nodal velocity
    bool export_acceleration = false;      ///< Export nodal acceleration
    bool export_stress = true;             ///< Export element stress
    bool export_strain = false;            ///< Export element strain
    bool export_plastic_strain = false;    ///< Export element plastic strain

    // VTK writer options
    VtkFormat vtk_format = VtkFormat::LEGACY_ASCII;
};

/**
 * @brief D3plot to VTK conversion result
 */
struct D3plotToVtkResult {
    bool success = false;
    std::string error_message;

    // Statistics
    size_t num_nodes = 0;
    size_t num_cells = 0;
    size_t num_point_arrays = 0;
    size_t num_cell_arrays = 0;
    size_t bytes_written = 0;
    std::vector<std::string> output_files;
};

/**
 * @brief D3plot to VTK converter class
 */
class D3plotToVtkConverter {
public:
    /**
     * @brief Constructor
     */
    D3plotToVtkConverter();

    /**
     * @brief Destructor
     */
    ~D3plotToVtkConverter();

    // Non-copyable
    D3plotToVtkConverter(const D3plotToVtkConverter&) = delete;
    D3plotToVtkConverter& operator=(const D3plotToVtkConverter&) = delete;

    /**
     * @brief Set conversion options
     */
    void setOptions(const D3plotToVtkOptions& options);

    /**
     * @brief Convert D3plot mesh and state to VTK
     * @param control Control data
     * @param mesh Mesh geometry
     * @param state State data
     * @param output_path Output VTK file path
     * @return Conversion result
     */
    D3plotToVtkResult convert(
        const data::ControlData& control,
        const data::Mesh& mesh,
        const data::StateData& state,
        const std::string& output_path);

    /**
     * @brief Convert D3plot mesh and multiple states to VTK series
     * @param control Control data
     * @param mesh Mesh geometry
     * @param states Vector of state data
     * @param output_base Base output path (e.g., "output" → "output_0.vtk", "output_1.vtk", ...)
     * @return Conversion result
     */
    D3plotToVtkResult convertSeries(
        const data::ControlData& control,
        const data::Mesh& mesh,
        const std::vector<data::StateData>& states,
        const std::string& output_base);

    /**
     * @brief Get last error message
     */
    std::string getLastError() const;

private:
    D3plotToVtkOptions options_;
    std::string last_error_;

    // Conversion helpers
    VtkMesh buildVtkMesh(
        const data::ControlData& control,
        const data::Mesh& mesh,
        const data::StateData& state);

    void addPointData(
        VtkMesh& vtk_mesh,
        const data::ControlData& control,
        const data::Mesh& mesh,
        const data::StateData& state);

    void addCellData(
        VtkMesh& vtk_mesh,
        const data::ControlData& control,
        const data::Mesh& mesh,
        const data::StateData& state);

    VtkCellType elementTypeToVtkCellType(ElementType type);
};

} // namespace converter
} // namespace kood3plot
