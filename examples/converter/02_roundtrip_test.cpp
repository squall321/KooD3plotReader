/**
 * @file 02_roundtrip_test.cpp
 * @brief Roundtrip conversion test: VTK → D3plot → VTK
 *
 * This example demonstrates data integrity through roundtrip conversion:
 * 1. Create VTK file with known data
 * 2. Convert VTK → D3plot
 * 3. Convert D3plot → VTK
 * 4. Compare original and final VTK data
 *
 * Usage:
 *   ./converter_roundtrip_test
 */

#include <iostream>
#include <fstream>
#include <iomanip>
#include <cmath>
#include <string>

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/converter/VtkReader.h"
#include "kood3plot/converter/VtkWriter.h"
#include "kood3plot/converter/VtkToD3plotConverter.h"
#include "kood3plot/converter/D3plotToVtkConverter.h"

using namespace kood3plot;
using namespace kood3plot::converter;

// Helper to compare floating point values
bool approxEqual(double a, double b, double tolerance = 1e-5) {
    return std::abs(a - b) < tolerance;
}

// Create a test VTK file with a cube and data
bool createTestVtkFile(const std::string& filepath) {
    std::ofstream file(filepath);
    if (!file.is_open()) {
        std::cerr << "Failed to create VTK file: " << filepath << "\n";
        return false;
    }

    file << "# vtk DataFile Version 3.0\n";
    file << "Roundtrip test cube\n";
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

    // 1 hexahedron cell
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
    file << "0.1 0.0 0.0\n";
    file << "0.1 0.1 0.0\n";
    file << "0.0 0.1 0.0\n";
    file << "0.0 0.0 0.2\n";
    file << "0.1 0.0 0.2\n";
    file << "0.1 0.1 0.2\n";
    file << "0.0 0.1 0.2\n";
    file << "\n";

    // Cell data: stress tensor (6 components in Voigt notation)
    file << "CELL_DATA 1\n";
    file << "TENSORS stress float\n";
    file << "-100.0 10.0 5.0\n";
    file << "10.0 -200.0 15.0\n";
    file << "5.0 15.0 300.0\n";

    file.close();
    return true;
}

int main(int argc, char* argv[]) {
    std::string vtk_original = "roundtrip_original.vtk";
    std::string d3plot_temp = "roundtrip_temp.d3plot";
    std::string vtk_final = "roundtrip_final.vtk";

    std::cout << "========================================\n";
    std::cout << " Roundtrip Conversion Test\n";
    std::cout << " VTK → D3plot → VTK\n";
    std::cout << "========================================\n\n";

    // ========================================
    // Step 1: Create original VTK file
    // ========================================
    std::cout << "[Step 1] Creating original VTK file...\n";

    if (!createTestVtkFile(vtk_original)) {
        return 1;
    }
    std::cout << "  Created: " << vtk_original << "\n\n";

    // ========================================
    // Step 2: Read original VTK
    // ========================================
    std::cout << "[Step 2] Reading original VTK file...\n";

    VtkReader reader1(vtk_original);
    auto result = reader1.read();
    if (result != ErrorCode::SUCCESS) {
        std::cerr << "Error reading VTK: " << reader1.getLastError() << "\n";
        return 1;
    }

    const auto& vtk_mesh1 = reader1.getMesh();
    std::cout << "  Points: " << (vtk_mesh1.points.size() / 3) << "\n";
    std::cout << "  Cells: " << vtk_mesh1.cell_types.size() << "\n";
    std::cout << "  Point data arrays: " << vtk_mesh1.point_data.size() << "\n";
    std::cout << "  Cell data arrays: " << vtk_mesh1.cell_data.size() << "\n\n";

    // ========================================
    // Step 3: Convert VTK → D3plot
    // ========================================
    std::cout << "[Step 3] Converting VTK → D3plot...\n";

    ConversionOptions vtk_to_d3plot_opts;
    vtk_to_d3plot_opts.title = "Roundtrip Test";
    vtk_to_d3plot_opts.precision = Precision::SINGLE;
    vtk_to_d3plot_opts.endian = Endian::LITTLE;

    VtkToD3plotConverter vtk_to_d3plot;
    vtk_to_d3plot.setOptions(vtk_to_d3plot_opts);

    auto conv_result1 = vtk_to_d3plot.convert(vtk_mesh1, d3plot_temp);
    if (!conv_result1.success) {
        std::cerr << "Error converting VTK → D3plot: " << conv_result1.error_message << "\n";
        return 1;
    }

    std::cout << "  Converted: " << d3plot_temp << "\n";
    std::cout << "  Nodes: " << conv_result1.num_nodes << "\n";
    std::cout << "  Solids: " << conv_result1.num_solids << "\n\n";

    // ========================================
    // Step 4: Read D3plot
    // ========================================
    std::cout << "[Step 4] Reading D3plot file...\n";

    D3plotReader d3plot_reader(d3plot_temp);
    if (d3plot_reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error opening D3plot\n";
        return 1;
    }

    auto control = d3plot_reader.get_control_data();
    auto mesh = d3plot_reader.read_mesh();
    auto states = d3plot_reader.read_all_states();
    d3plot_reader.close();

    std::cout << "  Title: " << control.TITLE << "\n";
    std::cout << "  Nodes: " << control.NUMNP << "\n";
    std::cout << "  Solids: " << std::abs(control.NEL8) << "\n";
    std::cout << "  States: " << states.size() << "\n\n";

    // ========================================
    // Step 5: Convert D3plot → VTK
    // ========================================
    std::cout << "[Step 5] Converting D3plot → VTK...\n";

    D3plotToVtkOptions d3plot_to_vtk_opts;
    d3plot_to_vtk_opts.title = "Roundtrip Result";
    d3plot_to_vtk_opts.export_displacement = true;
    d3plot_to_vtk_opts.export_stress = true;

    D3plotToVtkConverter d3plot_to_vtk;
    d3plot_to_vtk.setOptions(d3plot_to_vtk_opts);

    auto conv_result2 = d3plot_to_vtk.convert(control, mesh, states[0], vtk_final);
    if (!conv_result2.success) {
        std::cerr << "Error converting D3plot → VTK: " << conv_result2.error_message << "\n";
        return 1;
    }

    std::cout << "  Converted: " << vtk_final << "\n";
    std::cout << "  Nodes: " << conv_result2.num_nodes << "\n";
    std::cout << "  Cells: " << conv_result2.num_cells << "\n\n";

    // ========================================
    // Step 6: Read final VTK and compare
    // ========================================
    std::cout << "[Step 6] Reading final VTK and comparing...\n";

    VtkReader reader2(vtk_final);
    result = reader2.read();
    if (result != ErrorCode::SUCCESS) {
        std::cerr << "Error reading final VTK: " << reader2.getLastError() << "\n";
        return 1;
    }

    const auto& vtk_mesh2 = reader2.getMesh();

    // Compare geometry
    bool geometry_match = true;
    if (vtk_mesh1.points.size() != vtk_mesh2.points.size()) {
        std::cout << "  ✗ Point count mismatch: " << vtk_mesh1.points.size()
                  << " vs " << vtk_mesh2.points.size() << "\n";
        geometry_match = false;
    } else {
        for (size_t i = 0; i < vtk_mesh1.points.size(); ++i) {
            if (!approxEqual(vtk_mesh1.points[i], vtk_mesh2.points[i])) {
                std::cout << "  ✗ Point " << (i / 3) << " mismatch at component " << (i % 3) << ": "
                          << vtk_mesh1.points[i] << " vs " << vtk_mesh2.points[i] << "\n";
                geometry_match = false;
                break;
            }
        }
    }

    if (geometry_match) {
        std::cout << "  ✓ Geometry match: All " << (vtk_mesh1.points.size() / 3) << " points match\n";
    }

    // Compare displacement data
    bool displacement_match = true;
    if (!vtk_mesh1.point_data.empty() && !vtk_mesh2.point_data.empty()) {
        const auto& disp1 = vtk_mesh1.point_data[0];  // displacement
        const auto& disp2 = vtk_mesh2.point_data[0];

        if (disp1.data.size() != disp2.data.size()) {
            std::cout << "  ✗ Displacement data size mismatch: " << disp1.data.size()
                      << " vs " << disp2.data.size() << "\n";
            displacement_match = false;
        } else {
            for (size_t i = 0; i < disp1.data.size(); ++i) {
                if (!approxEqual(disp1.data[i], disp2.data[i])) {
                    std::cout << "  ✗ Displacement mismatch at index " << i << ": "
                              << disp1.data[i] << " vs " << disp2.data[i] << "\n";
                    displacement_match = false;
                    break;
                }
            }
        }
    }

    if (displacement_match) {
        std::cout << "  ✓ Displacement match: All " << (vtk_mesh1.point_data[0].data.size() / 3)
                  << " vectors match\n";
    }

    // Compare stress data
    bool stress_match = true;
    if (!vtk_mesh1.cell_data.empty() && !vtk_mesh2.cell_data.empty()) {
        const auto& stress1 = vtk_mesh1.cell_data[0];  // stress
        const auto& stress2 = vtk_mesh2.cell_data[0];

        if (stress1.data.size() != stress2.data.size()) {
            std::cout << "  ✗ Stress data size mismatch: " << stress1.data.size()
                      << " vs " << stress2.data.size() << "\n";
            stress_match = false;
        } else {
            for (size_t i = 0; i < stress1.data.size(); ++i) {
                if (!approxEqual(stress1.data[i], stress2.data[i])) {
                    std::cout << "  ✗ Stress mismatch at index " << i << ": "
                              << stress1.data[i] << " vs " << stress2.data[i] << "\n";
                    stress_match = false;
                    break;
                }
            }
        }
    }

    if (stress_match) {
        std::cout << "  ✓ Stress match: All " << (vtk_mesh1.cell_data[0].data.size() / 6)
                  << " tensors match\n";
    }

    std::cout << "\n========================================\n";
    if (geometry_match && displacement_match && stress_match) {
        std::cout << " ✓ ROUNDTRIP TEST PASSED\n";
        std::cout << " All data preserved through conversion\n";
    } else {
        std::cout << " ✗ ROUNDTRIP TEST FAILED\n";
        std::cout << " Data mismatch detected\n";
    }
    std::cout << "========================================\n";

    // Cleanup temporary files
    std::remove(vtk_original.c_str());
    std::remove(d3plot_temp.c_str());
    std::remove(vtk_final.c_str());

    return (geometry_match && displacement_match && stress_match) ? 0 : 1;
}
