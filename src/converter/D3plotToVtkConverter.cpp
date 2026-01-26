/**
 * @file D3plotToVtkConverter.cpp
 * @brief Implementation of D3plotToVtkConverter class
 */

#include "kood3plot/converter/D3plotToVtkConverter.h"
#include <iostream>
#include <sstream>
#include <iomanip>

namespace kood3plot {
namespace converter {

D3plotToVtkConverter::D3plotToVtkConverter() {
}

D3plotToVtkConverter::~D3plotToVtkConverter() {
}

void D3plotToVtkConverter::setOptions(const D3plotToVtkOptions& options) {
    options_ = options;
}

std::string D3plotToVtkConverter::getLastError() const {
    return last_error_;
}

D3plotToVtkResult D3plotToVtkConverter::convert(
    const data::ControlData& control,
    const data::Mesh& mesh,
    const data::StateData& state,
    const std::string& output_path)
{
    D3plotToVtkResult result;
    last_error_.clear();

    if (options_.verbose) {
        std::cout << "[D3plotToVtkConverter] Converting to VTK: " << output_path << "\n";
    }

    // Build VTK mesh
    VtkMesh vtk_mesh = buildVtkMesh(control, mesh, state);

    // Write VTK file
    VtkWriter writer(output_path);
    VtkWriterOptions writer_opts;
    writer_opts.verbose = options_.verbose;
    writer_opts.format = options_.vtk_format;
    writer.setOptions(writer_opts);

    auto err = writer.write(vtk_mesh);
    if (err != ErrorCode::SUCCESS) {
        result.success = false;
        result.error_message = writer.getLastError();
        last_error_ = result.error_message;
        return result;
    }

    // Success
    result.success = true;
    result.num_nodes = mesh.nodes.size();
    result.num_cells = vtk_mesh.cell_types.size();
    result.num_point_arrays = vtk_mesh.point_data.size();
    result.num_cell_arrays = vtk_mesh.cell_data.size();
    result.bytes_written = writer.getBytesWritten();
    result.output_files.push_back(output_path);

    return result;
}

D3plotToVtkResult D3plotToVtkConverter::convertSeries(
    const data::ControlData& control,
    const data::Mesh& mesh,
    const std::vector<data::StateData>& states,
    const std::string& output_base)
{
    D3plotToVtkResult result;
    last_error_.clear();

    for (size_t i = 0; i < states.size(); ++i) {
        // Generate filename: output_base + "_" + index + ".vtk"
        std::ostringstream oss;
        oss << output_base << "_" << std::setw(4) << std::setfill('0') << i << ".vtk";
        std::string output_path = oss.str();

        auto state_result = convert(control, mesh, states[i], output_path);
        if (!state_result.success) {
            result.success = false;
            result.error_message = state_result.error_message;
            last_error_ = result.error_message;
            return result;
        }

        result.output_files.push_back(output_path);
        result.bytes_written += state_result.bytes_written;
    }

    result.success = true;
    result.num_nodes = mesh.nodes.size();
    result.num_cells = mesh.num_solids + mesh.num_thick_shells + mesh.num_beams + mesh.num_shells;

    return result;
}

VtkMesh D3plotToVtkConverter::buildVtkMesh(
    const data::ControlData& control,
    const data::Mesh& mesh,
    const data::StateData& state)
{
    VtkMesh vtk_mesh;
    vtk_mesh.title = options_.title;
    vtk_mesh.time = state.time;

    // Convert nodes to points
    vtk_mesh.num_points = mesh.nodes.size();
    vtk_mesh.points.reserve(mesh.nodes.size() * 3);

    for (const auto& node : mesh.nodes) {
        vtk_mesh.points.push_back(node.x);
        vtk_mesh.points.push_back(node.y);
        vtk_mesh.points.push_back(node.z);
    }

    // Convert elements to cells
    // Order: solids, thick_shells, beams, shells (same as D3plot)
    vtk_mesh.num_cells = mesh.num_solids + mesh.num_thick_shells + mesh.num_beams + mesh.num_shells;

    size_t offset = 0;

    // Solids (8-node hexahedra)
    for (size_t i = 0; i < mesh.num_solids; ++i) {
        const auto& elem = mesh.solids[i];
        vtk_mesh.offsets.push_back(offset);

        for (auto node_id : elem.node_ids) {
            vtk_mesh.connectivity.push_back(node_id - 1);  // Convert to 0-based
            offset++;
        }

        vtk_mesh.cell_types.push_back(static_cast<int>(VtkCellType::HEXAHEDRON));
    }

    // Thick shells (8-node hexahedra)
    for (size_t i = 0; i < mesh.num_thick_shells; ++i) {
        const auto& elem = mesh.thick_shells[i];
        vtk_mesh.offsets.push_back(offset);

        for (auto node_id : elem.node_ids) {
            vtk_mesh.connectivity.push_back(node_id - 1);
            offset++;
        }

        vtk_mesh.cell_types.push_back(static_cast<int>(VtkCellType::HEXAHEDRON));
    }

    // Beams (2-node lines)
    for (size_t i = 0; i < mesh.num_beams; ++i) {
        const auto& elem = mesh.beams[i];
        vtk_mesh.offsets.push_back(offset);

        for (auto node_id : elem.node_ids) {
            vtk_mesh.connectivity.push_back(node_id - 1);
            offset++;
        }

        vtk_mesh.cell_types.push_back(static_cast<int>(VtkCellType::LINE));
    }

    // Shells (4-node quads)
    for (size_t i = 0; i < mesh.num_shells; ++i) {
        const auto& elem = mesh.shells[i];
        vtk_mesh.offsets.push_back(offset);

        for (auto node_id : elem.node_ids) {
            vtk_mesh.connectivity.push_back(node_id - 1);
            offset++;
        }

        vtk_mesh.cell_types.push_back(static_cast<int>(VtkCellType::QUAD));
    }

    // Add point data
    addPointData(vtk_mesh, control, mesh, state);

    // Add cell data
    addCellData(vtk_mesh, control, mesh, state);

    return vtk_mesh;
}

void D3plotToVtkConverter::addPointData(
    VtkMesh& vtk_mesh,
    const data::ControlData& control,
    const data::Mesh& mesh,
    const data::StateData& state)
{
    size_t num_nodes = mesh.nodes.size();

    // Displacement
    if (options_.export_displacement && !state.node_displacements.empty()) {
        VtkDataArray disp_array;
        disp_array.name = "displacement";
        disp_array.num_components = 3;
        disp_array.data = state.node_displacements;
        vtk_mesh.point_data.push_back(disp_array);
    }

    // Velocity
    if (options_.export_velocity && !state.node_velocities.empty()) {
        VtkDataArray vel_array;
        vel_array.name = "velocity";
        vel_array.num_components = 3;
        vel_array.data = state.node_velocities;
        vtk_mesh.point_data.push_back(vel_array);
    }

    // Acceleration
    if (options_.export_acceleration && !state.node_accelerations.empty()) {
        VtkDataArray acc_array;
        acc_array.name = "acceleration";
        acc_array.num_components = 3;
        acc_array.data = state.node_accelerations;
        vtk_mesh.point_data.push_back(acc_array);
    }
}

void D3plotToVtkConverter::addCellData(
    VtkMesh& vtk_mesh,
    const data::ControlData& control,
    const data::Mesh& mesh,
    const data::StateData& state)
{
    // Stress data
    if (options_.export_stress) {
        // Solid stress
        if (control.NV3D > 0 && !state.solid_data.empty()) {
            VtkDataArray stress_array;
            stress_array.name = "stress";
            stress_array.num_components = 6;  // Voigt notation
            stress_array.data.reserve(mesh.num_solids * 6);

            for (size_t i = 0; i < mesh.num_solids; ++i) {
                size_t offset = i * control.NV3D;
                // D3plot solid stress: Sxx, Syy, Szz, Sxy, Syz, Szx
                for (int j = 0; j < 6; ++j) {
                    stress_array.data.push_back(state.solid_data[offset + j]);
                }
            }

            vtk_mesh.cell_data.push_back(stress_array);
        }

        // TODO: Add shell stress, beam stress if needed
    }

    // Effective plastic strain (if available)
    if (options_.export_plastic_strain && control.NV3D >= 7) {
        VtkDataArray eff_pstrain_array;
        eff_pstrain_array.name = "effective_plastic_strain";
        eff_pstrain_array.num_components = 1;
        eff_pstrain_array.data.reserve(mesh.num_solids);

        for (size_t i = 0; i < mesh.num_solids; ++i) {
            size_t offset = i * control.NV3D;
            // Effective plastic strain is typically at index 6 (after 6 stress components)
            eff_pstrain_array.data.push_back(state.solid_data[offset + 6]);
        }

        vtk_mesh.cell_data.push_back(eff_pstrain_array);
    }
}

VtkCellType D3plotToVtkConverter::elementTypeToVtkCellType(ElementType type) {
    switch (type) {
        case ElementType::BEAM:
            return VtkCellType::LINE;
        case ElementType::SHELL:
            return VtkCellType::QUAD;
        case ElementType::THICK_SHELL:
            return VtkCellType::HEXAHEDRON;
        case ElementType::SOLID:
            return VtkCellType::HEXAHEDRON;
        default:
            return VtkCellType::HEXAHEDRON;
    }
}

} // namespace converter
} // namespace kood3plot
