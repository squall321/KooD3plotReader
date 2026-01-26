/**
 * @file VtkToD3plotConverter.cpp
 * @brief Implementation of VTK to D3plot converter
 */

#include "kood3plot/converter/VtkToD3plotConverter.h"
#include <iostream>
#include <algorithm>
#include <cmath>
#include <set>

namespace kood3plot {
namespace converter {

// ============================================================
// Data Mapping Utilities
// ============================================================

namespace DataMappingUtils {

std::string detectDisplacementArray(const std::vector<VtkDataArray>& arrays) {
    std::vector<std::string> patterns = {
        "DISPLACEMENT", "DISP", "U", "DEFORMATION", "DEF"
    };

    for (const auto& arr : arrays) {
        if (arr.num_components != 3) continue;

        std::string upper_name = arr.name;
        std::transform(upper_name.begin(), upper_name.end(), upper_name.begin(), ::toupper);

        for (const auto& pattern : patterns) {
            if (upper_name.find(pattern) != std::string::npos) {
                return arr.name;
            }
        }
    }

    return "";
}

std::string detectVelocityArray(const std::vector<VtkDataArray>& arrays) {
    std::vector<std::string> patterns = {
        "VELOCITY", "VEL", "V"
    };

    for (const auto& arr : arrays) {
        if (arr.num_components != 3) continue;

        std::string upper_name = arr.name;
        std::transform(upper_name.begin(), upper_name.end(), upper_name.begin(), ::toupper);

        for (const auto& pattern : patterns) {
            if (upper_name.find(pattern) != std::string::npos) {
                return arr.name;
            }
        }
    }

    return "";
}

std::string detectStressArray(const std::vector<VtkDataArray>& arrays) {
    std::vector<std::string> patterns = {
        "STRESS", "SIGMA", "S"
    };

    for (const auto& arr : arrays) {
        // Stress tensor: 6 components (symmetric) or 9 (full)
        if (arr.num_components != 6 && arr.num_components != 9) continue;

        std::string upper_name = arr.name;
        std::transform(upper_name.begin(), upper_name.end(), upper_name.begin(), ::toupper);

        for (const auto& pattern : patterns) {
            if (upper_name.find(pattern) != std::string::npos) {
                return arr.name;
            }
        }
    }

    // Also check for von Mises (scalar)
    for (const auto& arr : arrays) {
        if (arr.num_components != 1) continue;

        std::string upper_name = arr.name;
        std::transform(upper_name.begin(), upper_name.end(), upper_name.begin(), ::toupper);

        if (upper_name.find("VONMISES") != std::string::npos ||
            upper_name.find("VON_MISES") != std::string::npos ||
            upper_name.find("MISES") != std::string::npos) {
            return arr.name;
        }
    }

    return "";
}

std::string detectStrainArray(const std::vector<VtkDataArray>& arrays) {
    std::vector<std::string> patterns = {
        "STRAIN", "EPSILON", "EPS", "E"
    };

    for (const auto& arr : arrays) {
        if (arr.num_components != 6 && arr.num_components != 9) continue;

        std::string upper_name = arr.name;
        std::transform(upper_name.begin(), upper_name.end(), upper_name.begin(), ::toupper);

        for (const auto& pattern : patterns) {
            if (upper_name.find(pattern) != std::string::npos) {
                return arr.name;
            }
        }
    }

    return "";
}

ElementType vtkCellToElementType(VtkCellType vtk_type) {
    switch (vtk_type) {
        case VtkCellType::HEXAHEDRON:
        case VtkCellType::QUADRATIC_HEXAHEDRON:
            return ElementType::SOLID;

        case VtkCellType::TETRA:
        case VtkCellType::QUADRATIC_TETRA:
        case VtkCellType::WEDGE:
        case VtkCellType::PYRAMID:
            return ElementType::SOLID;  // Treat as degenerate hex

        case VtkCellType::QUAD:
        case VtkCellType::TRIANGLE:
            return ElementType::SHELL;

        case VtkCellType::LINE:
            return ElementType::BEAM;

        default:
            // Unknown cell types are treated as solids
            return ElementType::SOLID;
    }
}

int getNodesPerCell(VtkCellType vtk_type) {
    switch (vtk_type) {
        case VtkCellType::VERTEX: return 1;
        case VtkCellType::LINE: return 2;
        case VtkCellType::TRIANGLE: return 3;
        case VtkCellType::QUAD: return 4;
        case VtkCellType::TETRA: return 4;
        case VtkCellType::HEXAHEDRON: return 8;
        case VtkCellType::WEDGE: return 6;
        case VtkCellType::PYRAMID: return 5;
        case VtkCellType::QUADRATIC_TETRA: return 10;
        case VtkCellType::QUADRATIC_HEXAHEDRON: return 20;
        default: return 0;
    }
}

} // namespace DataMappingUtils

// ============================================================
// Implementation Class
// ============================================================

class VtkToD3plotConverter::Impl {
public:
    ConversionOptions options;
    std::string last_error;

    // ========================================
    // Conversion Functions
    // ========================================

    ConversionResult convert(const VtkMesh& vtk_mesh, const std::string& output_path) {
        ConversionResult result;

        // Step 1: Build D3plot mesh from VTK
        data::Mesh d3_mesh;
        data::ControlData control;

        auto err = buildMesh(vtk_mesh, d3_mesh, control);
        if (err != ErrorCode::SUCCESS) {
            result.error_message = last_error;
            return result;
        }

        // Step 2: Build state data from VTK arrays
        std::vector<data::StateData> states;
        err = buildStates(vtk_mesh, control, states, result);
        if (err != ErrorCode::SUCCESS) {
            result.error_message = last_error;
            return result;
        }

        // Step 3: Write D3plot file
        err = writeD3plot(control, d3_mesh, states, output_path, result);
        if (err != ErrorCode::SUCCESS) {
            result.error_message = last_error;
            return result;
        }

        result.success = true;
        return result;
    }

    ConversionResult convertSeries(const std::vector<VtkMesh>& vtk_meshes,
                                   const std::string& output_path) {
        ConversionResult result;

        if (vtk_meshes.empty()) {
            result.error_message = "No VTK meshes provided";
            return result;
        }

        // Use first mesh for geometry
        const VtkMesh& first_mesh = vtk_meshes[0];

        // Build D3plot mesh from first VTK mesh
        data::Mesh d3_mesh;
        data::ControlData control;

        auto err = buildMesh(first_mesh, d3_mesh, control);
        if (err != ErrorCode::SUCCESS) {
            result.error_message = last_error;
            return result;
        }

        // Build states from all meshes
        std::vector<data::StateData> states;
        states.reserve(vtk_meshes.size());

        for (const auto& vtk_mesh : vtk_meshes) {
            data::StateData state;
            state.time = vtk_mesh.time;

            // Map point data
            mapPointData(vtk_mesh, control, state, result);

            // Map cell data
            mapCellData(vtk_mesh, control, state, result);

            states.push_back(std::move(state));
        }

        result.num_states = states.size();

        // Write D3plot file
        err = writeD3plot(control, d3_mesh, states, output_path, result);
        if (err != ErrorCode::SUCCESS) {
            result.error_message = last_error;
            return result;
        }

        result.success = true;
        return result;
    }

    // ========================================
    // Mesh Building
    // ========================================

    ErrorCode buildMesh(const VtkMesh& vtk_mesh, data::Mesh& d3_mesh, data::ControlData& control) {
        if (options.verbose) {
            std::cout << "[Converter] Building mesh from " << vtk_mesh.num_points
                      << " points, " << vtk_mesh.num_cells << " cells\n";
        }

        // Set title
        control.TITLE = options.title;
        if (!vtk_mesh.title.empty()) {
            control.TITLE = vtk_mesh.title;
        }

        // Convert nodes
        d3_mesh.nodes.resize(vtk_mesh.num_points);
        for (size_t i = 0; i < vtk_mesh.num_points; ++i) {
            d3_mesh.nodes[i].id = static_cast<int32_t>(i + 1);  // 1-based
            d3_mesh.nodes[i].x = vtk_mesh.points[i * 3 + 0];
            d3_mesh.nodes[i].y = vtk_mesh.points[i * 3 + 1];
            d3_mesh.nodes[i].z = vtk_mesh.points[i * 3 + 2];
        }

        control.NUMNP = static_cast<int32_t>(vtk_mesh.num_points);
        control.NDIM = 5;  // Standard 3D

        // Categorize elements by type
        std::vector<std::pair<size_t, VtkCellType>> solids, shells, beams;

        size_t conn_offset = 0;
        for (size_t i = 0; i < vtk_mesh.num_cells; ++i) {
            int cell_type = vtk_mesh.cell_types.empty() ?
                            static_cast<int>(VtkCellType::HEXAHEDRON) :
                            vtk_mesh.cell_types[i];

            auto elem_type = DataMappingUtils::vtkCellToElementType(static_cast<VtkCellType>(cell_type));

            switch (elem_type) {
                case ElementType::SOLID:
                    solids.push_back({i, static_cast<VtkCellType>(cell_type)});
                    break;
                case ElementType::SHELL:
                    shells.push_back({i, static_cast<VtkCellType>(cell_type)});
                    break;
                case ElementType::BEAM:
                    beams.push_back({i, static_cast<VtkCellType>(cell_type)});
                    break;
                default:
                    break;
            }
        }

        // Convert solid elements
        convertSolids(vtk_mesh, solids, d3_mesh);
        control.NEL8 = static_cast<int32_t>(d3_mesh.solids.size());
        control.NUMMAT8 = control.NEL8 > 0 ? 1 : 0;
        control.NV3D = 7;  // 6 stress components + effective plastic strain

        // Convert shell elements
        convertShells(vtk_mesh, shells, d3_mesh);
        control.NEL4 = static_cast<int32_t>(d3_mesh.shells.size());
        control.NUMMAT4 = control.NEL4 > 0 ? 1 : 0;
        control.NV2D = 33;  // Standard shell variables

        // Convert beam elements
        convertBeams(vtk_mesh, beams, d3_mesh);
        control.NEL2 = static_cast<int32_t>(d3_mesh.beams.size());
        control.NUMMAT2 = control.NEL2 > 0 ? 1 : 0;
        control.NV1D = 6;  // Standard beam variables

        // Set other control data
        control.NELT = 0;  // No thick shells
        control.NUMMATT = 0;
        control.NV3DT = 0;
        control.NGLBV = 6;  // Standard global vars
        control.NARBS = 0;  // No arbitrary numbering
        control.EXTRA = 0;

        // Count materials/parts
        std::set<int32_t> parts;
        for (const auto& p : d3_mesh.solid_parts) parts.insert(p);
        for (const auto& p : d3_mesh.shell_parts) parts.insert(p);
        for (const auto& p : d3_mesh.beam_parts) parts.insert(p);
        control.NMMAT = static_cast<int32_t>(parts.size());
        if (control.NMMAT == 0) control.NMMAT = 1;

        // Compute derived values
        control.compute_derived_values();

        if (options.verbose) {
            std::cout << "[Converter] Created: "
                      << d3_mesh.solids.size() << " solids, "
                      << d3_mesh.shells.size() << " shells, "
                      << d3_mesh.beams.size() << " beams\n";
        }

        return ErrorCode::SUCCESS;
    }

    void convertSolids(const VtkMesh& vtk_mesh,
                       const std::vector<std::pair<size_t, VtkCellType>>& solid_cells,
                       data::Mesh& d3_mesh) {
        d3_mesh.solids.reserve(solid_cells.size());
        d3_mesh.solid_parts.reserve(solid_cells.size());

        for (const auto& [cell_idx, cell_type] : solid_cells) {
            Element elem;
            elem.id = static_cast<int32_t>(d3_mesh.solids.size() + 1);
            elem.type = ElementType::SOLID;

            // Get node IDs from connectivity
            size_t start_offset = cell_idx > 0 && !vtk_mesh.offsets.empty() ?
                                  vtk_mesh.offsets[cell_idx - 1] : 0;
            size_t end_offset = !vtk_mesh.offsets.empty() ?
                                vtk_mesh.offsets[cell_idx] :
                                vtk_mesh.connectivity.size();

            std::vector<int32_t> vtk_nodes;
            for (size_t j = start_offset; j < end_offset; ++j) {
                vtk_nodes.push_back(vtk_mesh.connectivity[j] + 1);  // Convert to 1-based
            }

            // Map to 8-node hex (pad with duplicates if needed)
            elem.node_ids.resize(8);
            mapToHex8(vtk_nodes, cell_type, elem.node_ids);

            d3_mesh.solids.push_back(elem);
            d3_mesh.solid_parts.push_back(1);  // Default part ID
        }

        d3_mesh.num_solids = d3_mesh.solids.size();
    }

    void convertShells(const VtkMesh& vtk_mesh,
                       const std::vector<std::pair<size_t, VtkCellType>>& shell_cells,
                       data::Mesh& d3_mesh) {
        d3_mesh.shells.reserve(shell_cells.size());
        d3_mesh.shell_parts.reserve(shell_cells.size());

        for (const auto& [cell_idx, cell_type] : shell_cells) {
            Element elem;
            elem.id = static_cast<int32_t>(d3_mesh.shells.size() + 1);
            elem.type = ElementType::SHELL;

            size_t start_offset = cell_idx > 0 && !vtk_mesh.offsets.empty() ?
                                  vtk_mesh.offsets[cell_idx - 1] : 0;
            size_t end_offset = !vtk_mesh.offsets.empty() ?
                                vtk_mesh.offsets[cell_idx] :
                                vtk_mesh.connectivity.size();

            elem.node_ids.resize(4);
            size_t node_count = 0;
            for (size_t j = start_offset; j < end_offset && node_count < 4; ++j) {
                elem.node_ids[node_count++] = vtk_mesh.connectivity[j] + 1;
            }

            // Pad triangles with duplicate node
            if (cell_type == VtkCellType::TRIANGLE) {
                elem.node_ids[3] = elem.node_ids[2];
            }

            d3_mesh.shells.push_back(elem);
            d3_mesh.shell_parts.push_back(1);
        }

        d3_mesh.num_shells = d3_mesh.shells.size();
    }

    void convertBeams(const VtkMesh& vtk_mesh,
                      const std::vector<std::pair<size_t, VtkCellType>>& beam_cells,
                      data::Mesh& d3_mesh) {
        d3_mesh.beams.reserve(beam_cells.size());
        d3_mesh.beam_parts.reserve(beam_cells.size());

        for (const auto& [cell_idx, cell_type] : beam_cells) {
            Element elem;
            elem.id = static_cast<int32_t>(d3_mesh.beams.size() + 1);
            elem.type = ElementType::BEAM;

            size_t start_offset = cell_idx > 0 && !vtk_mesh.offsets.empty() ?
                                  vtk_mesh.offsets[cell_idx - 1] : 0;

            elem.node_ids.resize(2);
            elem.node_ids[0] = vtk_mesh.connectivity[start_offset] + 1;
            elem.node_ids[1] = vtk_mesh.connectivity[start_offset + 1] + 1;

            d3_mesh.beams.push_back(elem);
            d3_mesh.beam_parts.push_back(1);
        }

        d3_mesh.num_beams = d3_mesh.beams.size();
    }

    void mapToHex8(const std::vector<int32_t>& vtk_nodes,
                   VtkCellType cell_type,
                   std::vector<int32_t>& hex_nodes) {
        switch (cell_type) {
            case VtkCellType::HEXAHEDRON:
                // Direct mapping (VTK and LS-DYNA use same node ordering)
                for (size_t i = 0; i < 8 && i < vtk_nodes.size(); ++i) {
                    hex_nodes[i] = vtk_nodes[i];
                }
                break;

            case VtkCellType::TETRA:
                // Tet to degenerate hex: duplicate nodes
                if (vtk_nodes.size() >= 4) {
                    hex_nodes[0] = vtk_nodes[0];
                    hex_nodes[1] = vtk_nodes[1];
                    hex_nodes[2] = vtk_nodes[2];
                    hex_nodes[3] = vtk_nodes[2];  // Duplicate
                    hex_nodes[4] = vtk_nodes[3];
                    hex_nodes[5] = vtk_nodes[3];  // Duplicate
                    hex_nodes[6] = vtk_nodes[3];  // Duplicate
                    hex_nodes[7] = vtk_nodes[3];  // Duplicate
                }
                break;

            case VtkCellType::WEDGE:
                // Wedge to degenerate hex
                if (vtk_nodes.size() >= 6) {
                    hex_nodes[0] = vtk_nodes[0];
                    hex_nodes[1] = vtk_nodes[1];
                    hex_nodes[2] = vtk_nodes[2];
                    hex_nodes[3] = vtk_nodes[2];  // Duplicate
                    hex_nodes[4] = vtk_nodes[3];
                    hex_nodes[5] = vtk_nodes[4];
                    hex_nodes[6] = vtk_nodes[5];
                    hex_nodes[7] = vtk_nodes[5];  // Duplicate
                }
                break;

            case VtkCellType::PYRAMID:
                // Pyramid to degenerate hex
                if (vtk_nodes.size() >= 5) {
                    hex_nodes[0] = vtk_nodes[0];
                    hex_nodes[1] = vtk_nodes[1];
                    hex_nodes[2] = vtk_nodes[2];
                    hex_nodes[3] = vtk_nodes[3];
                    hex_nodes[4] = vtk_nodes[4];
                    hex_nodes[5] = vtk_nodes[4];  // Duplicate apex
                    hex_nodes[6] = vtk_nodes[4];  // Duplicate apex
                    hex_nodes[7] = vtk_nodes[4];  // Duplicate apex
                }
                break;

            default:
                // Fill with whatever we have
                for (size_t i = 0; i < 8; ++i) {
                    hex_nodes[i] = vtk_nodes.empty() ? 1 :
                                   vtk_nodes[std::min(i, vtk_nodes.size() - 1)];
                }
                break;
        }
    }

    // ========================================
    // State Data Mapping
    // ========================================

    ErrorCode buildStates(const VtkMesh& vtk_mesh,
                          const data::ControlData& control,
                          std::vector<data::StateData>& states,
                          ConversionResult& result) {
        data::StateData state;
        state.time = vtk_mesh.time;

        // Initialize global variables
        state.global_vars.resize(control.NGLBV, 0.0);

        // Map point data (displacement, velocity)
        mapPointData(vtk_mesh, control, state, result);

        // Map cell data (stress, strain)
        mapCellData(vtk_mesh, control, state, result);

        states.push_back(std::move(state));
        result.num_states = 1;

        return ErrorCode::SUCCESS;
    }

    void mapPointData(const VtkMesh& vtk_mesh,
                      const data::ControlData& control,
                      data::StateData& state,
                      ConversionResult& result) {
        // Auto-detect and map displacement
        if (options.auto_detect_displacement) {
            std::string disp_name = DataMappingUtils::detectDisplacementArray(vtk_mesh.point_data);
            if (!disp_name.empty()) {
                for (const auto& arr : vtk_mesh.point_data) {
                    if (arr.name == disp_name) {
                        state.node_displacements = arr.data;
                        result.mapped_point_arrays.push_back(disp_name + " -> displacement");

                        // Set control flags
                        const_cast<data::ControlData&>(control).IU = 1;
                        break;
                    }
                }
            }
        }

        // Auto-detect and map velocity
        if (options.auto_detect_velocity) {
            std::string vel_name = DataMappingUtils::detectVelocityArray(vtk_mesh.point_data);
            if (!vel_name.empty()) {
                for (const auto& arr : vtk_mesh.point_data) {
                    if (arr.name == vel_name) {
                        state.node_velocities = arr.data;
                        result.mapped_point_arrays.push_back(vel_name + " -> velocity");

                        const_cast<data::ControlData&>(control).IV = 1;
                        break;
                    }
                }
            }
        }

        // Apply custom mappings
        for (const auto& mapping : options.point_data_mappings) {
            for (const auto& arr : vtk_mesh.point_data) {
                if (arr.name == mapping.vtk_name) {
                    if (mapping.d3plot_type == "displacement") {
                        state.node_displacements = arr.data;
                        const_cast<data::ControlData&>(control).IU = 1;
                    } else if (mapping.d3plot_type == "velocity") {
                        state.node_velocities = arr.data;
                        const_cast<data::ControlData&>(control).IV = 1;
                    } else if (mapping.d3plot_type == "acceleration") {
                        state.node_accelerations = arr.data;
                        const_cast<data::ControlData&>(control).IA = 1;
                    } else if (mapping.d3plot_type == "temperature") {
                        state.node_temperatures = arr.data;
                        const_cast<data::ControlData&>(control).IT = 1;
                    }
                    result.mapped_point_arrays.push_back(mapping.vtk_name + " -> " + mapping.d3plot_type);
                    break;
                }
            }
        }

        // Ensure displacements are properly sized
        if (state.node_displacements.empty() && control.IU > 0) {
            state.node_displacements.resize(control.NUMNP * 3, 0.0);
        }
        if (state.node_velocities.empty() && control.IV > 0) {
            state.node_velocities.resize(control.NUMNP * 3, 0.0);
        }
    }

    void mapCellData(const VtkMesh& vtk_mesh,
                     const data::ControlData& control,
                     data::StateData& state,
                     ConversionResult& result) {
        // Auto-detect stress for solid elements
        if (options.auto_detect_stress && std::abs(control.NEL8) > 0) {
            std::string stress_name = DataMappingUtils::detectStressArray(vtk_mesh.cell_data);
            if (!stress_name.empty()) {
                for (const auto& arr : vtk_mesh.cell_data) {
                    if (arr.name == stress_name) {
                        mapStressToSolids(arr, control, state);
                        result.mapped_cell_arrays.push_back(stress_name + " -> solid_stress");
                        break;
                    }
                }
            }
        }

        // Initialize solid data if not mapped
        int nel8 = std::abs(control.NEL8);
        if (state.solid_data.empty() && nel8 > 0) {
            state.solid_data.resize(nel8 * control.NV3D, 0.0);
        }

        // Initialize shell data
        if (state.shell_data.empty() && control.NEL4 > 0) {
            state.shell_data.resize(control.NEL4 * control.NV2D, 0.0);
        }

        // Initialize beam data
        if (state.beam_data.empty() && control.NEL2 > 0) {
            state.beam_data.resize(control.NEL2 * control.NV1D, 0.0);
        }
    }

    void mapStressToSolids(const VtkDataArray& stress_arr,
                           const data::ControlData& control,
                           data::StateData& state) {
        int nel8 = std::abs(control.NEL8);
        int nv3d = control.NV3D;

        state.solid_data.resize(nel8 * nv3d, 0.0);

        // D3plot stress order: Sxx, Syy, Szz, Sxy, Syz, Szx
        // VTK tensor order may vary (often: Sxx, Syy, Szz, Sxy, Syz, Sxz or Voigt notation)

        size_t src_stride = stress_arr.num_components;

        for (int e = 0; e < nel8 && e < static_cast<int>(stress_arr.data.size() / src_stride); ++e) {
            size_t src_offset = e * src_stride;
            size_t dst_offset = e * nv3d;

            if (src_stride == 6) {
                // Voigt notation: Sxx, Syy, Szz, Sxy, Syz, Szx (or Sxz)
                state.solid_data[dst_offset + 0] = stress_arr.data[src_offset + 0];  // Sxx
                state.solid_data[dst_offset + 1] = stress_arr.data[src_offset + 1];  // Syy
                state.solid_data[dst_offset + 2] = stress_arr.data[src_offset + 2];  // Szz
                state.solid_data[dst_offset + 3] = stress_arr.data[src_offset + 3];  // Sxy
                state.solid_data[dst_offset + 4] = stress_arr.data[src_offset + 4];  // Syz
                state.solid_data[dst_offset + 5] = stress_arr.data[src_offset + 5];  // Szx
            } else if (src_stride == 9) {
                // Full tensor: row-major [Sxx, Sxy, Sxz, Syx, Syy, Syz, Szx, Szy, Szz]
                state.solid_data[dst_offset + 0] = stress_arr.data[src_offset + 0];  // Sxx
                state.solid_data[dst_offset + 1] = stress_arr.data[src_offset + 4];  // Syy
                state.solid_data[dst_offset + 2] = stress_arr.data[src_offset + 8];  // Szz
                state.solid_data[dst_offset + 3] = stress_arr.data[src_offset + 1];  // Sxy
                state.solid_data[dst_offset + 4] = stress_arr.data[src_offset + 5];  // Syz
                state.solid_data[dst_offset + 5] = stress_arr.data[src_offset + 6];  // Szx
            } else if (src_stride == 1) {
                // Scalar (e.g., von Mises) - store in effective plastic strain slot or first slot
                state.solid_data[dst_offset + 6] = stress_arr.data[src_offset];
            }

            // Compute von Mises if we have full tensor
            if (src_stride >= 6) {
                double sxx = state.solid_data[dst_offset + 0];
                double syy = state.solid_data[dst_offset + 1];
                double szz = state.solid_data[dst_offset + 2];
                double sxy = state.solid_data[dst_offset + 3];
                double syz = state.solid_data[dst_offset + 4];
                double szx = state.solid_data[dst_offset + 5];

                // Von Mises = sqrt(0.5 * ((sxx-syy)^2 + (syy-szz)^2 + (szz-sxx)^2 + 6*(sxy^2 + syz^2 + szx^2)))
                double vm = std::sqrt(0.5 * (
                    (sxx-syy)*(sxx-syy) + (syy-szz)*(syy-szz) + (szz-sxx)*(szz-sxx) +
                    6.0 * (sxy*sxy + syz*syz + szx*szx)
                ));

                // Store in slot 6 (effective plastic strain in d3plot, but often used for von Mises)
                if (nv3d > 6) {
                    state.solid_data[dst_offset + 6] = vm / 1e6;  // Often scaled
                }
            }
        }
    }

    // ========================================
    // Writing
    // ========================================

    ErrorCode writeD3plot(const data::ControlData& control,
                          const data::Mesh& mesh,
                          const std::vector<data::StateData>& states,
                          const std::string& output_path,
                          ConversionResult& result) {
        if (options.verbose) {
            std::cout << "[Converter] Writing D3plot to: " << output_path << "\n";
        }

        writer::D3plotWriter writer(output_path);

        writer::WriterOptions write_opts;
        write_opts.precision = options.precision;
        write_opts.endian = options.endian;
        write_opts.verbose = options.verbose;
        write_opts.max_file_size = options.max_file_size;

        writer.setOptions(write_opts);
        writer.setControlData(control);
        writer.setMesh(mesh);
        writer.setStates(states);

        auto err = writer.write();
        if (err != ErrorCode::SUCCESS) {
            last_error = writer.getLastError();
            return err;
        }

        result.num_nodes = control.NUMNP;
        result.num_solids = std::abs(control.NEL8);
        result.num_shells = control.NEL4;
        result.num_beams = control.NEL2;
        result.bytes_written = writer.getWrittenBytes();
        result.output_files = writer.getOutputFiles();

        return ErrorCode::SUCCESS;
    }
};

// ============================================================
// VtkToD3plotConverter Public Methods
// ============================================================

VtkToD3plotConverter::VtkToD3plotConverter()
    : pImpl(std::make_unique<Impl>())
{
}

VtkToD3plotConverter::~VtkToD3plotConverter() = default;

void VtkToD3plotConverter::setOptions(const ConversionOptions& options) {
    pImpl->options = options;
}

ConversionResult VtkToD3plotConverter::convert(const VtkMesh& vtk_mesh,
                                                const std::string& output_path) {
    return pImpl->convert(vtk_mesh, output_path);
}

ConversionResult VtkToD3plotConverter::convertSeries(
    const std::vector<VtkMesh>& vtk_meshes,
    const std::string& output_path) {
    return pImpl->convertSeries(vtk_meshes, output_path);
}

ConversionResult VtkToD3plotConverter::convertFiles(
    const std::vector<std::string>& input_paths,
    const std::string& output_path,
    const ConversionOptions& options) {

    VtkReaderOptions read_opts;
    read_opts.verbose = options.verbose;

    // Read all input files
    std::vector<VtkMesh> meshes;
    for (const auto& path : input_paths) {
        VtkReader reader(path);
        reader.setOptions(read_opts);

        if (reader.read() == ErrorCode::SUCCESS) {
            meshes.push_back(reader.getMesh());
        } else {
            ConversionResult result;
            result.error_message = "Failed to read: " + path + " - " + reader.getLastError();
            return result;
        }
    }

    // Convert
    VtkToD3plotConverter converter;
    converter.setOptions(options);

    if (meshes.size() == 1) {
        return converter.convert(meshes[0], output_path);
    } else {
        return converter.convertSeries(meshes, output_path);
    }
}

std::string VtkToD3plotConverter::getLastError() const {
    return pImpl->last_error;
}

} // namespace converter
} // namespace kood3plot
