/**
 * @file VtkToD3plotConverter.h
 * @brief Convert VTK data to D3plot format
 *
 * Maps VTK mesh and data arrays to LS-DYNA d3plot structures.
 */

#pragma once

#include "kood3plot/converter/VtkReader.h"
#include "kood3plot/data/ControlData.hpp"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"
#include "kood3plot/writer/D3plotWriter.h"
#include <string>
#include <vector>
#include <map>
#include <memory>

namespace kood3plot {
namespace converter {

/**
 * @brief Data mapping configuration
 */
struct DataMapping {
    std::string vtk_name;           ///< VTK array name
    std::string d3plot_type;        ///< D3plot data type (displacement, velocity, stress, etc.)
    int component_offset = 0;       ///< Starting component index
    int num_components = -1;        ///< Number of components to use (-1 = all)
};

/**
 * @brief Conversion options
 */
struct ConversionOptions {
    std::string title = "VTK Converted";  ///< Output title
    bool verbose = false;                  ///< Print progress

    // Data mapping
    std::vector<DataMapping> point_data_mappings;   ///< Point data mappings
    std::vector<DataMapping> cell_data_mappings;    ///< Cell data mappings

    // Auto-detection settings
    bool auto_detect_displacement = true;   ///< Auto-detect displacement arrays
    bool auto_detect_velocity = true;       ///< Auto-detect velocity arrays
    bool auto_detect_stress = true;         ///< Auto-detect stress arrays

    // Output settings
    Precision precision = Precision::SINGLE;
    Endian endian = Endian::LITTLE;
    size_t max_file_size = 0;              ///< Max file size for splitting (0 = no limit)
};

/**
 * @brief Conversion result statistics
 */
struct ConversionResult {
    bool success = false;
    std::string error_message;

    // Statistics
    size_t num_nodes = 0;
    size_t num_solids = 0;
    size_t num_shells = 0;
    size_t num_beams = 0;
    size_t num_states = 0;
    size_t bytes_written = 0;
    std::vector<std::string> output_files;

    // Mapped data
    std::vector<std::string> mapped_point_arrays;
    std::vector<std::string> mapped_cell_arrays;
    std::vector<std::string> unmapped_arrays;
};

/**
 * @brief VTK to D3plot converter class
 */
class VtkToD3plotConverter {
public:
    /**
     * @brief Constructor
     */
    VtkToD3plotConverter();

    /**
     * @brief Destructor
     */
    ~VtkToD3plotConverter();

    // Non-copyable
    VtkToD3plotConverter(const VtkToD3plotConverter&) = delete;
    VtkToD3plotConverter& operator=(const VtkToD3plotConverter&) = delete;

    /**
     * @brief Set conversion options
     */
    void setOptions(const ConversionOptions& options);

    /**
     * @brief Convert single VTK mesh to D3plot
     * @param vtk_mesh Source VTK mesh
     * @param output_path Output d3plot path
     * @return Conversion result
     */
    ConversionResult convert(const VtkMesh& vtk_mesh, const std::string& output_path);

    /**
     * @brief Convert VTK time series to D3plot
     * @param vtk_meshes Vector of VTK meshes (one per timestep)
     * @param output_path Output d3plot path
     * @return Conversion result
     */
    ConversionResult convertSeries(
        const std::vector<VtkMesh>& vtk_meshes,
        const std::string& output_path);

    /**
     * @brief Convert VTK file(s) to D3plot (convenience function)
     * @param input_paths Input VTK file path(s)
     * @param output_path Output d3plot path
     * @param options Conversion options
     * @return Conversion result
     */
    static ConversionResult convertFiles(
        const std::vector<std::string>& input_paths,
        const std::string& output_path,
        const ConversionOptions& options = ConversionOptions());

    /**
     * @brief Get last error message
     */
    std::string getLastError() const;

private:
    class Impl;
    std::unique_ptr<Impl> pImpl;
};

/**
 * @brief Utility functions for data mapping
 */
namespace DataMappingUtils {

/**
 * @brief Detect displacement array from VTK data
 * @param arrays Available data arrays
 * @return Array name or empty string if not found
 */
std::string detectDisplacementArray(const std::vector<VtkDataArray>& arrays);

/**
 * @brief Detect velocity array from VTK data
 */
std::string detectVelocityArray(const std::vector<VtkDataArray>& arrays);

/**
 * @brief Detect stress tensor array from VTK data
 */
std::string detectStressArray(const std::vector<VtkDataArray>& arrays);

/**
 * @brief Detect strain tensor array from VTK data
 */
std::string detectStrainArray(const std::vector<VtkDataArray>& arrays);

/**
 * @brief Convert VTK cell type to D3plot element type
 * @param vtk_type VTK cell type
 * @return D3plot element type
 */
ElementType vtkCellToElementType(VtkCellType vtk_type);

/**
 * @brief Get number of nodes for VTK cell type
 */
int getNodesPerCell(VtkCellType vtk_type);

} // namespace DataMappingUtils

} // namespace converter
} // namespace kood3plot
