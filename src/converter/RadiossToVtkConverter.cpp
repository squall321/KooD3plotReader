/**
 * @file RadiossToVtkConverter.cpp
 * @brief Implementation of RadiossToVtkConverter class
 */

#include "kood3plot/converter/RadiossToVtkConverter.h"
#include <iostream>
#include <sstream>
#include <iomanip>

namespace kood3plot {
namespace converter {

RadiossToVtkConverter::RadiossToVtkConverter() {
}

RadiossToVtkConverter::~RadiossToVtkConverter() {
}

void RadiossToVtkConverter::setOptions(const RadiossToVtkOptions& options) {
    options_ = options;
}

std::string RadiossToVtkConverter::getLastError() const {
    return last_error_;
}

RadiossToVtkResult RadiossToVtkConverter::convert(
    const RadiossHeader& header,
    const RadiossMesh& mesh,
    const RadiossState& state,
    const std::string& output_path)
{
    RadiossToVtkResult result;
    last_error_.clear();

    if (options_.verbose) {
        std::cout << "[RadiossToVtkConverter] Converting to VTK: " << output_path << "\n";
    }

    // Build VTK mesh
    VtkMesh vtk_mesh = buildVtkMesh(header, mesh, state);

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

RadiossToVtkResult RadiossToVtkConverter::convertSeries(
    const RadiossHeader& header,
    const RadiossMesh& mesh,
    const std::vector<RadiossState>& states,
    const std::string& output_base)
{
    RadiossToVtkResult result;
    last_error_.clear();

    for (size_t i = 0; i < states.size(); ++i) {
        // Generate filename: output_base + "_" + index + ".vtk"
        std::ostringstream oss;
        oss << output_base << "_" << std::setw(4) << std::setfill('0') << i << ".vtk";
        std::string output_path = oss.str();

        auto state_result = convert(header, mesh, states[i], output_path);
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
    result.num_cells = mesh.solids.size() + mesh.shells.size() + mesh.beams.size();

    return result;
}

VtkMesh RadiossToVtkConverter::buildVtkMesh(
    const RadiossHeader& header,
    const RadiossMesh& mesh,
    const RadiossState& state)
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
    // Order: solids, shells, beams
    vtk_mesh.num_cells = mesh.solids.size() + mesh.shells.size() + mesh.beams.size();

    size_t offset = 0;

    // Solids (8-node hexahedra)
    for (const auto& elem : mesh.solids) {
        vtk_mesh.offsets.push_back(offset);

        for (auto node_id : elem.node_ids) {
            vtk_mesh.connectivity.push_back(node_id - 1);  // Convert to 0-based
            offset++;
        }

        vtk_mesh.cell_types.push_back(static_cast<int>(VtkCellType::HEXAHEDRON));
    }

    // Shells (4-node quads)
    for (const auto& elem : mesh.shells) {
        vtk_mesh.offsets.push_back(offset);

        for (auto node_id : elem.node_ids) {
            vtk_mesh.connectivity.push_back(node_id - 1);
            offset++;
        }

        vtk_mesh.cell_types.push_back(static_cast<int>(VtkCellType::QUAD));
    }

    // Beams (2-node lines)
    for (const auto& elem : mesh.beams) {
        vtk_mesh.offsets.push_back(offset);

        for (auto node_id : elem.node_ids) {
            vtk_mesh.connectivity.push_back(node_id - 1);
            offset++;
        }

        vtk_mesh.cell_types.push_back(static_cast<int>(VtkCellType::LINE));
    }

    // Add point data
    addPointData(vtk_mesh, header, mesh, state);

    // Add cell data
    addCellData(vtk_mesh, header, mesh, state);

    return vtk_mesh;
}

void RadiossToVtkConverter::addPointData(
    VtkMesh& vtk_mesh,
    const RadiossHeader& header,
    const RadiossMesh& mesh,
    const RadiossState& state)
{
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

void RadiossToVtkConverter::addCellData(
    VtkMesh& vtk_mesh,
    const RadiossHeader& header,
    const RadiossMesh& mesh,
    const RadiossState& state)
{
    // Stress data (if available)
    if (options_.export_stress && !state.solid_stress.empty()) {
        VtkDataArray stress_array;
        stress_array.name = "stress";
        stress_array.num_components = 6;  // Voigt notation
        stress_array.data = state.solid_stress;
        vtk_mesh.cell_data.push_back(stress_array);
    }

    // Shell stress
    if (options_.export_stress && !state.shell_stress.empty()) {
        VtkDataArray stress_array;
        stress_array.name = "shell_stress";
        stress_array.num_components = 6;
        stress_array.data = state.shell_stress;
        vtk_mesh.cell_data.push_back(stress_array);
    }

    // Plastic strain
    if (options_.export_plastic_strain && !state.plastic_strain.empty()) {
        VtkDataArray pstrain_array;
        pstrain_array.name = "plastic_strain";
        pstrain_array.num_components = 1;
        pstrain_array.data = state.plastic_strain;
        vtk_mesh.cell_data.push_back(pstrain_array);
    }

    // Strain data
    if (options_.export_strain && !state.solid_strain.empty()) {
        VtkDataArray strain_array;
        strain_array.name = "strain";
        strain_array.num_components = 6;
        strain_array.data = state.solid_strain;
        vtk_mesh.cell_data.push_back(strain_array);
    }
}

} // namespace converter
} // namespace kood3plot
