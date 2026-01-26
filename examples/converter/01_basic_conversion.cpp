/**
 * @file 01_basic_conversion.cpp
 * @brief Basic VTK to D3plot conversion example
 *
 * This example demonstrates:
 * 1. Creating a simple VTK file programmatically
 * 2. Converting VTK mesh to D3plot format
 * 3. Reading back and verifying the converted file
 *
 * Usage:
 *   ./converter_basic_test [output_d3plot]
 */

#include <iostream>
#include <fstream>
#include <iomanip>
#include <cmath>
#include <string>

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/converter/VtkReader.h"
#include "kood3plot/converter/VtkToD3plotConverter.h"

using namespace kood3plot;
using namespace kood3plot::converter;

// Create a simple VTK Legacy ASCII file with a cube
bool createTestVtkFile(const std::string& filepath) {
    std::ofstream file(filepath);
    if (!file.is_open()) {
        std::cerr << "Failed to create VTK file: " << filepath << "\n";
        return false;
    }

    file << "# vtk DataFile Version 3.0\n";
    file << "Test cube for VTK to D3plot conversion\n";
    file << "ASCII\n";
    file << "DATASET UNSTRUCTURED_GRID\n";
    file << "\n";

    // 8 nodes for a unit cube
    file << "POINTS 8 float\n";
    file << "0.0 0.0 0.0\n";
    file << "1.0 0.0 0.0\n";
    file << "1.0 1.0 0.0\n";
    file << "0.0 1.0 0.0\n";
    file << "0.0 0.0 1.0\n";
    file << "1.0 0.0 1.0\n";
    file << "1.0 1.0 1.0\n";
    file << "0.0 1.0 1.0\n";
    file << "\n";

    // 1 hexahedron cell (8 nodes + size prefix)
    file << "CELLS 1 9\n";
    file << "8 0 1 2 3 4 5 6 7\n";
    file << "\n";

    // Cell type: VTK_HEXAHEDRON = 12
    file << "CELL_TYPES 1\n";
    file << "12\n";
    file << "\n";

    // Point data: displacement vectors
    file << "POINT_DATA 8\n";
    file << "VECTORS displacement float\n";
    file << "0.0 0.0 0.0\n";
    file << "0.0 0.0 0.0\n";
    file << "0.0 0.0 0.0\n";
    file << "0.0 0.0 0.0\n";
    file << "0.0 0.0 0.1\n";  // Top nodes displaced in Z
    file << "0.0 0.0 0.1\n";
    file << "0.0 0.0 0.1\n";
    file << "0.0 0.0 0.1\n";
    file << "\n";

    // Cell data: stress tensor (6 components in Voigt notation)
    file << "CELL_DATA 1\n";
    file << "TENSORS stress float\n";
    // Full 3x3 tensor (VTK format: row by row)
    // [Sxx, Sxy, Sxz]
    // [Syx, Syy, Syz]
    // [Szx, Szy, Szz]
    file << "-100.0 0.0 0.0\n";
    file << "0.0 -100.0 0.0\n";
    file << "0.0 0.0 200.0\n";

    file.close();
    return true;
}

int main(int argc, char* argv[]) {
    std::string output_path = (argc >= 2) ? argv[1] : "vtk_converted.d3plot";
    std::string vtk_path = "test_cube.vtk";

    std::cout << "========================================\n";
    std::cout << " VTK to D3plot Converter - Basic Test\n";
    std::cout << "========================================\n\n";

    // ========================================
    // Step 1: Create test VTK file
    // ========================================
    std::cout << "[Step 1] Creating test VTK file...\n";

    if (!createTestVtkFile(vtk_path)) {
        return 1;
    }
    std::cout << "  Created: " << vtk_path << "\n\n";

    // ========================================
    // Step 2: Read VTK file
    // ========================================
    std::cout << "[Step 2] Reading VTK file...\n";

    VtkReader vtk_reader(vtk_path);
    auto format = vtk_reader.detectFormat();
    std::cout << "  Format: " << static_cast<int>(format) << " (1=Legacy ASCII)\n";

    auto result = vtk_reader.read();
    if (result != ErrorCode::SUCCESS) {
        std::cerr << "Error reading VTK file: " << vtk_reader.getLastError() << "\n";
        return 1;
    }

    const auto& vtk_mesh = vtk_reader.getMesh();
    std::cout << "  Points: " << (vtk_mesh.points.size() / 3) << "\n";
    std::cout << "  Cells: " << vtk_mesh.cell_types.size() << "\n";
    std::cout << "  Point data arrays: " << vtk_mesh.point_data.size() << "\n";
    std::cout << "  Cell data arrays: " << vtk_mesh.cell_data.size() << "\n\n";

    // ========================================
    // Step 3: Convert to D3plot
    // ========================================
    std::cout << "[Step 3] Converting to D3plot format...\n";

    ConversionOptions options;
    options.title = "VTK Converted Cube";
    options.auto_detect_displacement = true;
    options.auto_detect_velocity = true;
    options.auto_detect_stress = true;
    options.precision = Precision::SINGLE;
    options.endian = Endian::LITTLE;

    VtkToD3plotConverter converter;
    converter.setOptions(options);

    auto conv_result = converter.convert(vtk_mesh, output_path);
    if (!conv_result.success) {
        std::cerr << "Error converting: " << conv_result.error_message << "\n";
        return 1;
    }
    std::cout << "  Nodes converted: " << conv_result.num_nodes << "\n";
    std::cout << "  Solids converted: " << conv_result.num_solids << "\n";
    std::cout << "  Shells converted: " << conv_result.num_shells << "\n";
    std::cout << "  Beams converted: " << conv_result.num_beams << "\n";
    std::cout << "  States written: " << conv_result.num_states << "\n";
    std::cout << "  Output: " << output_path << "\n\n";

    // ========================================
    // Step 4: Verify by reading back
    // ========================================
    std::cout << "[Step 4] Verifying converted D3plot...\n";

    D3plotReader reader(output_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error: Cannot read back converted file\n";
        return 1;
    }

    auto control = reader.get_control_data();
    auto mesh = reader.read_mesh();
    auto states = reader.read_all_states();
    reader.close();

    std::cout << "  Title: " << control.TITLE << "\n";
    std::cout << "  Nodes: " << control.NUMNP << "\n";
    std::cout << "  Solids: " << std::abs(control.NEL8) << "\n";
    std::cout << "  Shells: " << std::abs(control.NEL4) << "\n";
    std::cout << "  States: " << states.size() << "\n";

    // Print node coordinates
    std::cout << "\n  Node coordinates:\n";
    for (size_t i = 0; i < std::min(size_t(4), mesh.nodes.size()); ++i) {
        const auto& n = mesh.nodes[i];
        std::cout << "    Node " << n.id << ": ("
                  << std::fixed << std::setprecision(3)
                  << n.x << ", " << n.y << ", " << n.z << ")\n";
    }
    if (mesh.nodes.size() > 4) {
        std::cout << "    ... (" << mesh.nodes.size() - 4 << " more nodes)\n";
    }

    // Print state data
    if (!states.empty()) {
        const auto& state = states[0];
        std::cout << "\n  State 0 (t=" << state.time << "):\n";

        if (!state.node_displacements.empty()) {
            std::cout << "    Displacements (first 4 nodes):\n";
            for (size_t i = 0; i < std::min(size_t(4), state.node_displacements.size() / 3); ++i) {
                std::cout << "      Node " << (i + 1) << ": ("
                          << state.node_displacements[i * 3] << ", "
                          << state.node_displacements[i * 3 + 1] << ", "
                          << state.node_displacements[i * 3 + 2] << ")\n";
            }
        }

        if (!state.solid_data.empty() && control.NV3D > 0) {
            std::cout << "    Solid stress (element 1):\n";
            std::cout << "      Sxx=" << state.solid_data[0]
                      << " Syy=" << state.solid_data[1]
                      << " Szz=" << state.solid_data[2] << "\n";
        }
    }

    std::cout << "\n========================================\n";
    std::cout << " VTK to D3plot conversion successful!\n";
    std::cout << "========================================\n";

    // Cleanup test VTK file
    std::remove(vtk_path.c_str());

    return 0;
}
