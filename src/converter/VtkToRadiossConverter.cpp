/**
 * @file VtkToRadiossConverter.cpp
 * @brief Implementation of VTK to OpenRadioss converter
 */

#include "kood3plot/converter/VtkToRadiossConverter.h"
#include <algorithm>
#include <cctype>
#include <iostream>

namespace kood3plot {
namespace converter {

VtkToRadiossConverter::VtkToRadiossConverter() {
}

VtkToRadiossConverter::~VtkToRadiossConverter() {
}

void VtkToRadiossConverter::setOptions(const VtkToRadiossOptions& options) {
    options_ = options;
}

VtkToRadiossResult VtkToRadiossConverter::convert(
    const VtkMesh& vtk_mesh,
    const std::string& output_base)
{
    VtkToRadiossResult result;
    last_error_.clear();

    // Build Radioss structures from VTK
    RadiossHeader header = buildHeader(vtk_mesh);
    RadiossMesh mesh = buildMesh(vtk_mesh);
    RadiossState state = buildState(vtk_mesh);

    // Write Radioss files
    RadiossWriter writer(output_base);
    RadiossWriterOptions writer_opts;
    writer_opts.title = options_.title;
    writer_opts.write_displacement = options_.convert_displacement;
    writer_opts.write_velocity = options_.convert_velocity;
    writer_opts.write_stress = options_.convert_stress;
    writer_opts.verbose = options_.verbose;
    writer.setOptions(writer_opts);

    // Write A00 (header + geometry)
    auto err = writer.writeHeader(header, mesh);
    if (err != ErrorCode::SUCCESS) {
        result.success = false;
        result.error_message = writer.getLastError();
        last_error_ = result.error_message;
        return result;
    }

    // Write A01 (first state)
    err = writer.writeState(1, state);
    if (err != ErrorCode::SUCCESS) {
        result.success = false;
        result.error_message = writer.getLastError();
        last_error_ = result.error_message;
        return result;
    }

    result.success = true;
    result.num_nodes = mesh.nodes.size();
    result.num_elements = mesh.shells.size() + mesh.solids.size();
    result.num_states = 1;
    result.bytes_written = writer.getBytesWritten();

    return result;
}

VtkToRadiossResult VtkToRadiossConverter::convertSeries(
    const std::vector<VtkMesh>& vtk_meshes,
    const std::string& output_base)
{
    VtkToRadiossResult result;
    last_error_.clear();

    if (vtk_meshes.empty()) {
        result.success = false;
        result.error_message = "No VTK meshes provided";
        last_error_ = result.error_message;
        return result;
    }

    // Build header and mesh from first timestep
    const VtkMesh& first_mesh = vtk_meshes[0];
    RadiossHeader header = buildHeader(first_mesh);
    RadiossMesh mesh = buildMesh(first_mesh);

    // Write Radioss files
    RadiossWriter writer(output_base);
    RadiossWriterOptions writer_opts;
    writer_opts.title = options_.title;
    writer_opts.write_displacement = options_.convert_displacement;
    writer_opts.write_velocity = options_.convert_velocity;
    writer_opts.write_stress = options_.convert_stress;
    writer_opts.verbose = options_.verbose;
    writer.setOptions(writer_opts);

    // Write A00 (header + geometry)
    auto err = writer.writeHeader(header, mesh);
    if (err != ErrorCode::SUCCESS) {
        result.success = false;
        result.error_message = writer.getLastError();
        last_error_ = result.error_message;
        return result;
    }

    // Write state files (A01, A02, ...)
    for (size_t i = 0; i < vtk_meshes.size(); ++i) {
        RadiossState state = buildState(vtk_meshes[i]);

        err = writer.writeState(i + 1, state);
        if (err != ErrorCode::SUCCESS) {
            result.success = false;
            result.error_message = writer.getLastError();
            last_error_ = result.error_message;
            return result;
        }
    }

    result.success = true;
    result.num_nodes = mesh.nodes.size();
    result.num_elements = mesh.shells.size() + mesh.solids.size();
    result.num_states = vtk_meshes.size();
    result.bytes_written = writer.getBytesWritten();

    return result;
}

RadiossHeader VtkToRadiossConverter::buildHeader(const VtkMesh& vtk_mesh) {
    RadiossHeader header;

    header.title = options_.title;
    header.num_nodes = static_cast<int32_t>(vtk_mesh.num_points);
    header.word_size = 4;  // float32

    // Count element types
    header.num_shells = 0;
    header.num_solids = 0;
    header.num_beams = 0;

    for (size_t i = 0; i < vtk_mesh.cell_types.size(); ++i) {
        VtkCellType cell_type = static_cast<VtkCellType>(vtk_mesh.cell_types[i]);
        switch (cell_type) {
            case VtkCellType::QUAD:
            case VtkCellType::TRIANGLE:
                header.num_shells++;
                break;
            case VtkCellType::HEXAHEDRON:
            case VtkCellType::TETRA:
            case VtkCellType::WEDGE:
            case VtkCellType::PYRAMID:
                header.num_solids++;
                break;
            case VtkCellType::LINE:
                header.num_beams++;
                break;
            default:
                break;
        }
    }

    // Check for data arrays
    header.has_displacement = (findDataArray(vtk_mesh.point_data, "disp") != nullptr);
    header.has_velocity = (findDataArray(vtk_mesh.point_data, "vel") != nullptr);
    header.has_acceleration = (findDataArray(vtk_mesh.point_data, "acc") != nullptr);
    header.has_stress = (findDataArray(vtk_mesh.cell_data, "stress") != nullptr);
    header.has_strain = (findDataArray(vtk_mesh.cell_data, "strain") != nullptr);
    header.has_plastic_strain = (findDataArray(vtk_mesh.cell_data, "plastic") != nullptr);

    return header;
}

RadiossMesh VtkToRadiossConverter::buildMesh(const VtkMesh& vtk_mesh) {
    RadiossMesh mesh;

    // Convert points to nodes
    mesh.nodes.resize(vtk_mesh.num_points);
    for (size_t i = 0; i < vtk_mesh.num_points; ++i) {
        Node node;
        node.id = static_cast<int32_t>(i + 1);  // 1-based
        node.x = vtk_mesh.points[i * 3 + 0];
        node.y = vtk_mesh.points[i * 3 + 1];
        node.z = vtk_mesh.points[i * 3 + 2];
        mesh.nodes[i] = node;
    }

    // Convert cells to elements
    size_t conn_offset = 0;
    for (size_t i = 0; i < vtk_mesh.cell_types.size(); ++i) {
        VtkCellType cell_type = static_cast<VtkCellType>(vtk_mesh.cell_types[i]);

        // Get number of nodes for this cell
        size_t num_nodes = 0;
        if (i + 1 < vtk_mesh.offsets.size()) {
            num_nodes = vtk_mesh.offsets[i + 1] - vtk_mesh.offsets[i];
        } else {
            num_nodes = vtk_mesh.connectivity.size() - vtk_mesh.offsets[i];
        }

        Element elem;
        elem.id = static_cast<int32_t>(i + 1);

        // Copy node IDs (convert to 1-based)
        for (size_t j = 0; j < num_nodes; ++j) {
            elem.node_ids.push_back(vtk_mesh.connectivity[conn_offset + j] + 1);
        }
        conn_offset += num_nodes;

        switch (cell_type) {
            case VtkCellType::QUAD:
            case VtkCellType::TRIANGLE:
                elem.type = ElementType::SHELL;
                mesh.shells.push_back(elem);
                mesh.shell_parts.push_back(1);  // Default part
                break;
            case VtkCellType::HEXAHEDRON:
            case VtkCellType::TETRA:
            case VtkCellType::WEDGE:
            case VtkCellType::PYRAMID:
                elem.type = ElementType::SOLID;
                mesh.solids.push_back(elem);
                mesh.solid_parts.push_back(1);
                break;
            case VtkCellType::LINE:
                elem.type = ElementType::BEAM;
                mesh.beams.push_back(elem);
                mesh.beam_parts.push_back(1);
                break;
            default:
                break;
        }
    }

    return mesh;
}

RadiossState VtkToRadiossConverter::buildState(const VtkMesh& vtk_mesh) {
    RadiossState state;
    state.time = vtk_mesh.time;

    // Find and convert displacement
    const VtkDataArray* disp = findDataArray(vtk_mesh.point_data, "disp");
    if (disp && options_.convert_displacement) {
        state.node_displacements = disp->data;
    }

    // Find and convert velocity
    const VtkDataArray* vel = findDataArray(vtk_mesh.point_data, "vel");
    if (vel && options_.convert_velocity) {
        state.node_velocities = vel->data;
    }

    // Find and convert acceleration
    const VtkDataArray* acc = findDataArray(vtk_mesh.point_data, "acc");
    if (acc) {
        state.node_accelerations = acc->data;
    }

    // Find and convert stress
    // Count element types to determine where to store stress
    int32_t num_solids = 0, num_shells = 0;
    for (size_t i = 0; i < vtk_mesh.cell_types.size(); ++i) {
        VtkCellType cell_type = static_cast<VtkCellType>(vtk_mesh.cell_types[i]);
        if (cell_type == VtkCellType::HEXAHEDRON || cell_type == VtkCellType::TETRA ||
            cell_type == VtkCellType::WEDGE || cell_type == VtkCellType::PYRAMID) {
            num_solids++;
        } else if (cell_type == VtkCellType::QUAD || cell_type == VtkCellType::TRIANGLE) {
            num_shells++;
        }
    }

    const VtkDataArray* stress = findDataArray(vtk_mesh.cell_data, "stress");
    if (stress && options_.convert_stress) {
        // If we have solids but no shells, assume stress is for solids
        if (num_solids > 0 && num_shells == 0) {
            state.solid_stress = stress->data;
        } else {
            state.shell_stress = stress->data;
        }
    }

    // Find and convert plastic strain
    const VtkDataArray* pstrain = findDataArray(vtk_mesh.cell_data, "plastic");
    if (pstrain) {
        state.plastic_strain = pstrain->data;
    }

    return state;
}

const VtkDataArray* VtkToRadiossConverter::findDataArray(
    const std::vector<VtkDataArray>& arrays,
    const std::string& name_pattern)
{
    // Convert pattern to lowercase for comparison
    std::string pattern_lower = name_pattern;
    std::transform(pattern_lower.begin(), pattern_lower.end(),
                   pattern_lower.begin(), ::tolower);

    for (const auto& arr : arrays) {
        std::string name_lower = arr.name;
        std::transform(name_lower.begin(), name_lower.end(),
                       name_lower.begin(), ::tolower);

        // Check if pattern is contained in array name
        if (name_lower.find(pattern_lower) != std::string::npos) {
            return &arr;
        }
    }

    return nullptr;
}

} // namespace converter
} // namespace kood3plot
