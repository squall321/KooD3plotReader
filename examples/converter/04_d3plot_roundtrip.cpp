/**
 * @file 04_d3plot_roundtrip.cpp
 * @brief Real d3plot roundtrip conversion test: D3plot → VTK → D3plot
 *
 * This example demonstrates data integrity through roundtrip conversion
 * using actual simulation data:
 * 1. Read original d3plot file
 * 2. Convert D3plot → VTK
 * 3. Convert VTK → D3plot
 * 4. Compare original and final d3plot data
 *
 * Usage:
 *   ./converter_d3plot_roundtrip <d3plot_file> [num_states]
 */

#include <iostream>
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
bool approxEqual(double a, double b, double tolerance = 1e-4) {
    return std::abs(a - b) < tolerance;
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cout << "Usage: " << argv[0] << " <d3plot_file> [num_states]\n";
        std::cout << "Example: " << argv[0] << " examples/results/d3plot 5\n";
        return 1;
    }

    std::string d3plot_original = argv[1];
    int max_states = (argc >= 3) ? std::stoi(argv[2]) : 5;

    std::string vtk_temp = "roundtrip_temp.vtk";
    std::string d3plot_final = "roundtrip_final.d3plot";

    std::cout << "========================================\n";
    std::cout << " D3plot Roundtrip Conversion Test\n";
    std::cout << " D3plot → VTK → D3plot\n";
    std::cout << "========================================\n\n";

    // ========================================
    // Step 1: Read original D3plot
    // ========================================
    std::cout << "[Step 1] Reading original D3plot file: " << d3plot_original << "\n";

    D3plotReader reader1(d3plot_original);
    if (reader1.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error opening original D3plot\n";
        return 1;
    }

    auto control1 = reader1.get_control_data();
    auto mesh1 = reader1.read_mesh();
    auto states1 = reader1.read_all_states();
    reader1.close();

    // Limit number of states for faster testing
    if (states1.size() > (size_t)max_states) {
        states1.resize(max_states);
    }

    std::cout << "  Title: " << control1.TITLE << "\n";
    std::cout << "  Nodes: " << control1.NUMNP << "\n";
    std::cout << "  Solids: " << std::abs(control1.NEL8) << "\n";
    std::cout << "  Shells: " << std::abs(control1.NEL4) << "\n";
    std::cout << "  States: " << states1.size() << "\n";
    if (!states1.empty()) {
        std::cout << "  Time range: " << states1.front().time
                  << " - " << states1.back().time << " s\n";
    }
    std::cout << "\n";

    // ========================================
    // Step 2: Convert D3plot → VTK (first state only for simplicity)
    // ========================================
    std::cout << "[Step 2] Converting D3plot → VTK...\n";

    D3plotToVtkOptions d3plot_to_vtk_opts;
    d3plot_to_vtk_opts.title = "Roundtrip Test";
    d3plot_to_vtk_opts.export_displacement = (control1.IU > 0);
    d3plot_to_vtk_opts.export_velocity = (control1.IV > 0);
    d3plot_to_vtk_opts.export_stress = (control1.NV3D > 0);

    D3plotToVtkConverter d3plot_to_vtk;
    d3plot_to_vtk.setOptions(d3plot_to_vtk_opts);

    auto conv_result1 = d3plot_to_vtk.convert(control1, mesh1, states1[0], vtk_temp);
    if (!conv_result1.success) {
        std::cerr << "Error converting D3plot → VTK: " << conv_result1.error_message << "\n";
        return 1;
    }

    std::cout << "  Converted to VTK: " << vtk_temp << "\n";
    std::cout << "  Nodes: " << conv_result1.num_nodes << "\n";
    std::cout << "  Cells: " << conv_result1.num_cells << "\n";
    std::cout << "  Point arrays: " << conv_result1.num_point_arrays << "\n";
    std::cout << "  Cell arrays: " << conv_result1.num_cell_arrays << "\n\n";

    // ========================================
    // Step 3: Read VTK
    // ========================================
    std::cout << "[Step 3] Reading VTK file...\n";

    VtkReader vtk_reader(vtk_temp);
    auto result = vtk_reader.read();
    if (result != ErrorCode::SUCCESS) {
        std::cerr << "Error reading VTK: " << vtk_reader.getLastError() << "\n";
        return 1;
    }

    const auto& vtk_mesh = vtk_reader.getMesh();
    std::cout << "  Points: " << (vtk_mesh.points.size() / 3) << "\n";
    std::cout << "  Cells: " << vtk_mesh.cell_types.size() << "\n";
    std::cout << "  Point data arrays: " << vtk_mesh.point_data.size() << "\n";
    std::cout << "  Cell data arrays: " << vtk_mesh.cell_data.size() << "\n\n";

    // ========================================
    // Step 4: Convert VTK → D3plot
    // ========================================
    std::cout << "[Step 4] Converting VTK → D3plot...\n";

    ConversionOptions vtk_to_d3plot_opts;
    vtk_to_d3plot_opts.title = "Roundtrip Result";
    vtk_to_d3plot_opts.precision = Precision::SINGLE;
    vtk_to_d3plot_opts.endian = Endian::LITTLE;

    VtkToD3plotConverter vtk_to_d3plot;
    vtk_to_d3plot.setOptions(vtk_to_d3plot_opts);

    auto conv_result2 = vtk_to_d3plot.convert(vtk_mesh, d3plot_final);
    if (!conv_result2.success) {
        std::cerr << "Error converting VTK → D3plot: " << conv_result2.error_message << "\n";
        return 1;
    }

    std::cout << "  Converted to D3plot: " << d3plot_final << "\n";
    std::cout << "  Nodes: " << conv_result2.num_nodes << "\n";
    std::cout << "  Solids: " << conv_result2.num_solids << "\n\n";

    // ========================================
    // Step 5: Read final D3plot and compare
    // ========================================
    std::cout << "[Step 5] Reading final D3plot and comparing...\n";

    D3plotReader reader2(d3plot_final);
    if (reader2.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error opening final D3plot\n";
        return 1;
    }

    auto control2 = reader2.get_control_data();
    auto mesh2 = reader2.read_mesh();
    auto states2 = reader2.read_all_states();
    reader2.close();

    // Compare mesh size
    bool size_match = true;
    if (mesh1.nodes.size() != mesh2.nodes.size()) {
        std::cout << "  ✗ Node count mismatch: " << mesh1.nodes.size()
                  << " vs " << mesh2.nodes.size() << "\n";
        size_match = false;
    }
    if (mesh1.num_solids != mesh2.num_solids) {
        std::cout << "  ✗ Solid count mismatch: " << mesh1.num_solids
                  << " vs " << mesh2.num_solids << "\n";
        size_match = false;
    }

    if (size_match) {
        std::cout << "  ✓ Mesh size match: " << mesh1.nodes.size() << " nodes, "
                  << mesh1.num_solids << " solids\n";
    }

    // Compare node coordinates (sample first 100 nodes)
    bool coord_match = true;
    size_t num_check_nodes = std::min(size_t(100), mesh1.nodes.size());
    size_t coord_mismatches = 0;

    for (size_t i = 0; i < num_check_nodes; ++i) {
        const auto& n1 = mesh1.nodes[i];
        const auto& n2 = mesh2.nodes[i];

        if (!approxEqual(n1.x, n2.x) || !approxEqual(n1.y, n2.y) || !approxEqual(n1.z, n2.z)) {
            if (coord_mismatches < 5) {  // Show first 5 mismatches
                std::cout << "  ✗ Node " << i << " mismatch: ("
                          << n1.x << ", " << n1.y << ", " << n1.z << ") vs ("
                          << n2.x << ", " << n2.y << ", " << n2.z << ")\n";
            }
            coord_mismatches++;
            coord_match = false;
        }
    }

    if (coord_match) {
        std::cout << "  ✓ Node coordinates match (checked " << num_check_nodes << " nodes)\n";
    } else {
        std::cout << "  ✗ Node coordinate mismatches: " << coord_mismatches
                  << " / " << num_check_nodes << "\n";
    }

    // Compare connectivity (sample first 100 elements)
    bool conn_match = true;
    size_t num_check_elems = std::min(size_t(100), mesh1.solids.size());
    size_t conn_mismatches = 0;

    for (size_t i = 0; i < num_check_elems; ++i) {
        const auto& e1 = mesh1.solids[i];
        const auto& e2 = mesh2.solids[i];

        if (e1.node_ids.size() != e2.node_ids.size()) {
            conn_mismatches++;
            conn_match = false;
            continue;
        }

        for (size_t j = 0; j < e1.node_ids.size(); ++j) {
            if (e1.node_ids[j] != e2.node_ids[j]) {
                if (conn_mismatches < 5) {
                    std::cout << "  ✗ Element " << i << " connectivity mismatch at node " << j << "\n";
                }
                conn_mismatches++;
                conn_match = false;
                break;
            }
        }
    }

    if (conn_match) {
        std::cout << "  ✓ Element connectivity match (checked " << num_check_elems << " elements)\n";
    } else {
        std::cout << "  ✗ Connectivity mismatches: " << conn_mismatches
                  << " / " << num_check_elems << "\n";
    }

    // Compare state data (displacement)
    bool disp_match = true;
    if (!states1.empty() && !states2.empty()) {
        const auto& s1 = states1[0];
        const auto& s2 = states2[0];

        if (s1.node_displacements.size() != s2.node_displacements.size()) {
            std::cout << "  ✗ Displacement data size mismatch: " << s1.node_displacements.size()
                      << " vs " << s2.node_displacements.size() << "\n";
            disp_match = false;
        } else {
            size_t num_check_disp = std::min(size_t(300), s1.node_displacements.size());  // First 100 nodes * 3
            size_t disp_mismatches = 0;

            for (size_t i = 0; i < num_check_disp; ++i) {
                if (!approxEqual(s1.node_displacements[i], s2.node_displacements[i])) {
                    if (disp_mismatches < 5) {
                        std::cout << "  ✗ Displacement mismatch at index " << i << ": "
                                  << s1.node_displacements[i] << " vs " << s2.node_displacements[i] << "\n";
                    }
                    disp_mismatches++;
                    disp_match = false;
                }
            }

            if (disp_match) {
                std::cout << "  ✓ Displacement data match (checked " << (num_check_disp / 3) << " nodes)\n";
            } else {
                std::cout << "  ✗ Displacement mismatches: " << disp_mismatches
                          << " / " << num_check_disp << "\n";
            }
        }
    }

    // Compare stress data
    bool stress_match = true;
    if (!states1.empty() && !states2.empty() && control1.NV3D > 0) {
        const auto& s1 = states1[0];
        const auto& s2 = states2[0];

        if (s1.solid_data.size() != s2.solid_data.size()) {
            std::cout << "  ✗ Stress data size mismatch: " << s1.solid_data.size()
                      << " vs " << s2.solid_data.size() << "\n";
            stress_match = false;
        } else {
            size_t num_check_stress = std::min(size_t(100 * control1.NV3D), s1.solid_data.size());
            size_t stress_mismatches = 0;

            for (size_t i = 0; i < num_check_stress; ++i) {
                if (!approxEqual(s1.solid_data[i], s2.solid_data[i])) {
                    if (stress_mismatches < 5) {
                        std::cout << "  ✗ Stress mismatch at index " << i << ": "
                                  << s1.solid_data[i] << " vs " << s2.solid_data[i] << "\n";
                    }
                    stress_mismatches++;
                    stress_match = false;
                }
            }

            if (stress_match) {
                std::cout << "  ✓ Stress data match (checked " << (num_check_stress / control1.NV3D) << " elements)\n";
            } else {
                std::cout << "  ✗ Stress mismatches: " << stress_mismatches
                          << " / " << num_check_stress << "\n";
            }
        }
    }

    std::cout << "\n========================================\n";
    if (size_match && coord_match && conn_match && disp_match && stress_match) {
        std::cout << " ✓ D3PLOT ROUNDTRIP TEST PASSED\n";
        std::cout << " All critical data preserved\n";
    } else {
        std::cout << " ⚠ D3PLOT ROUNDTRIP TEST COMPLETED WITH WARNINGS\n";
        std::cout << " Some data mismatches detected (check details above)\n";
    }
    std::cout << "========================================\n";

    // Cleanup temporary files
    std::remove(vtk_temp.c_str());
    std::remove(d3plot_final.c_str());

    return (size_match && coord_match && conn_match) ? 0 : 1;
}
