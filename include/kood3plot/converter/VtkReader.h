/**
 * @file VtkReader.h
 * @brief VTK file reader for converting to D3plot format
 *
 * Supports:
 * - Legacy VTK format (.vtk) - ASCII and binary
 * - XML VTK Unstructured Grid format (.vtu)
 */

#pragma once

#include "kood3plot/Types.hpp"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"
#include <string>
#include <vector>
#include <map>
#include <memory>

namespace kood3plot {
namespace converter {

/**
 * @brief VTK file format types
 */
enum class VtkFormat {
    UNKNOWN,
    LEGACY_ASCII,      ///< Legacy VTK ASCII format
    LEGACY_BINARY,     ///< Legacy VTK binary format
    XML_VTU,           ///< XML Unstructured Grid (.vtu)
    XML_VTU_SERIES     ///< XML VTU series (.pvd)
};

/**
 * @brief VTK cell types (subset commonly used)
 */
enum class VtkCellType {
    VERTEX = 1,
    LINE = 3,
    TRIANGLE = 5,
    QUAD = 9,
    TETRA = 10,
    HEXAHEDRON = 12,
    WEDGE = 13,
    PYRAMID = 14,
    QUADRATIC_TETRA = 24,
    QUADRATIC_HEXAHEDRON = 25
};

/**
 * @brief Data array from VTK file
 */
struct VtkDataArray {
    std::string name;                    ///< Array name (e.g., "displacement", "stress")
    int num_components;                  ///< Number of components (1=scalar, 3=vector, 6=tensor)
    std::vector<double> data;            ///< Flattened data values
    bool is_point_data;                  ///< True if point/node data, false if cell/element data
};

/**
 * @brief VTK mesh data structure
 */
struct VtkMesh {
    // Geometry
    std::vector<double> points;          ///< Node coordinates (x,y,z flattened)
    size_t num_points;                   ///< Number of points

    // Topology
    std::vector<int32_t> connectivity;   ///< Cell connectivity (flattened)
    std::vector<int32_t> offsets;        ///< Cell offsets into connectivity
    std::vector<int32_t> cell_types;     ///< VTK cell type for each cell
    size_t num_cells;                    ///< Number of cells

    // Data arrays
    std::vector<VtkDataArray> point_data;  ///< Point/node data arrays
    std::vector<VtkDataArray> cell_data;   ///< Cell/element data arrays

    // Metadata
    double time;                         ///< Time value (if available)
    std::string title;                   ///< Title or description
};

/**
 * @brief Options for VTK reading
 */
struct VtkReaderOptions {
    bool verbose = false;                ///< Print progress messages
    bool read_point_data = true;         ///< Read point/node data arrays
    bool read_cell_data = true;          ///< Read cell/element data arrays
    std::vector<std::string> array_filter;  ///< Only read these arrays (empty = all)
};

/**
 * @brief VTK file reader class
 */
class VtkReader {
public:
    /**
     * @brief Constructor
     * @param filepath Path to VTK file
     */
    explicit VtkReader(const std::string& filepath);

    /**
     * @brief Destructor
     */
    ~VtkReader();

    // Non-copyable
    VtkReader(const VtkReader&) = delete;
    VtkReader& operator=(const VtkReader&) = delete;

    // Movable
    VtkReader(VtkReader&&) noexcept;
    VtkReader& operator=(VtkReader&&) noexcept;

    /**
     * @brief Set reader options
     */
    void setOptions(const VtkReaderOptions& options);

    /**
     * @brief Detect file format
     * @return Detected VTK format
     */
    VtkFormat detectFormat();

    /**
     * @brief Read the VTK file
     * @return ErrorCode::SUCCESS on success
     */
    ErrorCode read();

    /**
     * @brief Get the parsed mesh data
     * @return Reference to VTK mesh data
     */
    const VtkMesh& getMesh() const;

    /**
     * @brief Get last error message
     */
    std::string getLastError() const;

    /**
     * @brief Get list of point data array names
     */
    std::vector<std::string> getPointDataArrayNames() const;

    /**
     * @brief Get list of cell data array names
     */
    std::vector<std::string> getCellDataArrayNames() const;

    /**
     * @brief Read a series of VTK files (for time series)
     * @param filepaths List of VTK file paths
     * @return Vector of VTK meshes
     */
    static std::vector<VtkMesh> readSeries(
        const std::vector<std::string>& filepaths,
        const VtkReaderOptions& options = VtkReaderOptions());

    /**
     * @brief Read VTU series from .pvd file
     * @param pvd_path Path to .pvd file
     * @return Vector of VTK meshes with time values
     */
    static std::vector<VtkMesh> readPvdSeries(
        const std::string& pvd_path,
        const VtkReaderOptions& options = VtkReaderOptions());

private:
    class Impl;
    std::unique_ptr<Impl> pImpl;
};

} // namespace converter
} // namespace kood3plot
