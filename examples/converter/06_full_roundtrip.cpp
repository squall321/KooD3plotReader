/**
 * @file 06_full_roundtrip.cpp
 * @brief Full roundtrip conversion test: D3plot → VTK → Radioss → VTK → D3plot
 *
 * This example demonstrates the complete 3-way conversion chain:
 * 1. D3plot → VTK (D3plotToVtkConverter)
 * 2. VTK → Radioss A00 (VtkToRadiossConverter)
 * 3. Radioss A00 → VTK (RadiossToVtkConverter)
 * 4. VTK → D3plot (VtkToD3plotConverter)
 *
 * Usage:
 *   ./converter_full_roundtrip <d3plot_path> <output_dir>
 */

#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <filesystem>
#include <chrono>
#include <cmath>

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/converter/D3plotToVtkConverter.h"
#include "kood3plot/converter/VtkToD3plotConverter.h"
#include "kood3plot/converter/VtkToRadiossConverter.h"
#include "kood3plot/converter/RadiossToVtkConverter.h"
#include "kood3plot/converter/RadiossReader.h"
#include "kood3plot/converter/RadiossWriter.h"

using namespace kood3plot;
using namespace kood3plot::converter;
namespace fs = std::filesystem;

void printSeparator(const std::string& title) {
    std::cout << "\n========================================\n";
    std::cout << " " << title << "\n";
    std::cout << "========================================\n";
}

int main(int argc, char* argv[]) {
    std::string d3plot_path;
    std::string output_dir = "roundtrip_output";

    if (argc >= 2) {
        d3plot_path = argv[1];
    } else {
        d3plot_path = "examples/results/d3plot";
    }

    if (argc >= 3) {
        output_dir = argv[2];
    }

    std::cout << "========================================\n";
    std::cout << " Full Roundtrip Conversion Test\n";
    std::cout << " D3plot → VTK → Radioss → VTK → D3plot\n";
    std::cout << "========================================\n";
    std::cout << "Input: " << d3plot_path << "\n";
    std::cout << "Output: " << output_dir << "\n";

    // Create output directories
    fs::create_directories(output_dir);
    fs::create_directories(output_dir + "/step1_vtk");
    fs::create_directories(output_dir + "/step2_radioss");
    fs::create_directories(output_dir + "/step3_vtk");
    fs::create_directories(output_dir + "/step4_d3plot");

    auto total_start = std::chrono::high_resolution_clock::now();

    // ========================================
    // Step 1: D3plot → VTK
    // ========================================
    printSeparator("Step 1: D3plot → VTK");

    D3plotReader d3plot_reader(d3plot_path);
    if (d3plot_reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error opening D3plot: " << d3plot_path << "\n";
        return 1;
    }

    auto control = d3plot_reader.get_control_data();
    auto mesh = d3plot_reader.read_mesh();
    auto states = d3plot_reader.read_all_states();

    std::cout << "D3plot loaded:\n";
    std::cout << "  Nodes: " << mesh.get_num_nodes() << "\n";
    std::cout << "  Solids: " << mesh.solids.size() << "\n";
    std::cout << "  Shells: " << mesh.shells.size() << "\n";
    std::cout << "  States: " << states.size() << "\n";

    if (states.empty()) {
        std::cerr << "Error: No states in D3plot\n";
        return 1;
    }

    // Convert first state only for speed
    D3plotToVtkOptions d3_to_vtk_opts;
    d3_to_vtk_opts.export_displacement = true;
    d3_to_vtk_opts.export_velocity = true;
    d3_to_vtk_opts.export_stress = true;

    D3plotToVtkConverter d3_to_vtk;
    d3_to_vtk.setOptions(d3_to_vtk_opts);

    std::string vtk1_path = output_dir + "/step1_vtk/state_0000.vtk";
    auto vtk1_result = d3_to_vtk.convert(control, mesh, states[0], vtk1_path);

    if (!vtk1_result.success) {
        std::cerr << "Error: " << vtk1_result.error_message << "\n";
        return 1;
    }

    std::cout << "VTK written: " << vtk1_path << "\n";
    std::cout << "  Nodes: " << vtk1_result.num_nodes << "\n";
    std::cout << "  Cells: " << vtk1_result.num_cells << "\n";
    std::cout << "  Point arrays: " << vtk1_result.num_point_arrays << "\n";
    std::cout << "  Cell arrays: " << vtk1_result.num_cell_arrays << "\n";

    d3plot_reader.close();

    // Read VTK file for next step
    VtkReader vtk1_reader(vtk1_path);
    if (vtk1_reader.read() != ErrorCode::SUCCESS) {
        std::cerr << "Error reading VTK: " << vtk1_reader.getLastError() << "\n";
        return 1;
    }
    VtkMesh vtk1_mesh = vtk1_reader.getMesh();

    // ========================================
    // Step 2: VTK → Radioss A00
    // ========================================
    printSeparator("Step 2: VTK → Radioss A00");

    VtkToRadiossOptions vtk_to_radioss_opts;
    vtk_to_radioss_opts.title = "KooD3plot Roundtrip Test";
    vtk_to_radioss_opts.convert_displacement = true;
    vtk_to_radioss_opts.convert_velocity = true;
    vtk_to_radioss_opts.convert_stress = true;
    vtk_to_radioss_opts.verbose = true;

    VtkToRadiossConverter vtk_to_radioss;
    vtk_to_radioss.setOptions(vtk_to_radioss_opts);

    std::string radioss_base = output_dir + "/step2_radioss/A0";
    auto radioss_result = vtk_to_radioss.convert(vtk1_mesh, radioss_base);

    if (!radioss_result.success) {
        std::cerr << "Error: " << radioss_result.error_message << "\n";
        return 1;
    }

    std::cout << "Radioss A00 written: " << radioss_base << "0\n";
    std::cout << "Radioss A01 written: " << radioss_base << "1\n";
    std::cout << "  Nodes: " << radioss_result.num_nodes << "\n";
    std::cout << "  Elements: " << radioss_result.num_elements << "\n";
    std::cout << "  States: " << radioss_result.num_states << "\n";

    // ========================================
    // Step 3: Radioss A00 → VTK
    // ========================================
    printSeparator("Step 3: Radioss A00 → VTK");

    std::string a00_path = radioss_base + "0";
    RadiossReader radioss_reader(a00_path);
    if (radioss_reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error opening Radioss: " << radioss_reader.getLastError() << "\n";
        return 1;
    }

    auto radioss_header = radioss_reader.getHeader();
    auto radioss_mesh = radioss_reader.getMesh();
    auto radioss_states = radioss_reader.readAllStates();

    std::cout << "Radioss loaded:\n";
    std::cout << "  Title: " << radioss_header.title << "\n";
    std::cout << "  Nodes: " << radioss_header.num_nodes << "\n";
    std::cout << "  Shells: " << radioss_header.num_shells << "\n";
    std::cout << "  States: " << radioss_states.size() << "\n";

    radioss_reader.close();

    // Convert to VTK
    RadiossToVtkOptions radioss_to_vtk_opts;
    radioss_to_vtk_opts.export_displacement = true;
    radioss_to_vtk_opts.export_velocity = true;
    radioss_to_vtk_opts.export_stress = true;

    RadiossToVtkConverter radioss_to_vtk;
    radioss_to_vtk.setOptions(radioss_to_vtk_opts);

    std::string vtk2_path = output_dir + "/step3_vtk/state_0000.vtk";

    if (!radioss_states.empty()) {
        auto vtk2_result = radioss_to_vtk.convert(
            radioss_header, radioss_mesh, radioss_states[0], vtk2_path);

        if (!vtk2_result.success) {
            std::cerr << "Error: " << vtk2_result.error_message << "\n";
            return 1;
        }

        std::cout << "VTK written: " << vtk2_path << "\n";
        std::cout << "  Nodes: " << vtk2_result.num_nodes << "\n";
        std::cout << "  Cells: " << vtk2_result.num_cells << "\n";
    }

    // Read VTK for final step
    VtkReader vtk2_reader(vtk2_path);
    if (vtk2_reader.read() != ErrorCode::SUCCESS) {
        std::cerr << "Error reading VTK: " << vtk2_reader.getLastError() << "\n";
        return 1;
    }
    VtkMesh vtk2_mesh = vtk2_reader.getMesh();

    // ========================================
    // Step 4: VTK → D3plot
    // ========================================
    printSeparator("Step 4: VTK → D3plot");

    ConversionOptions vtk_to_d3_opts;
    vtk_to_d3_opts.title = "Roundtrip Test Output";
    vtk_to_d3_opts.auto_detect_displacement = true;
    vtk_to_d3_opts.auto_detect_stress = true;

    VtkToD3plotConverter vtk_to_d3;
    vtk_to_d3.setOptions(vtk_to_d3_opts);

    std::string d3plot_out = output_dir + "/step4_d3plot/d3plot";
    ConversionResult d3_result = vtk_to_d3.convert(vtk2_mesh, d3plot_out);

    if (!d3_result.success) {
        std::cerr << "Error: " << d3_result.error_message << "\n";
        return 1;
    }

    std::cout << "D3plot written: " << d3plot_out << "\n";
    std::cout << "  Nodes: " << d3_result.num_nodes << "\n";
    std::cout << "  Solids: " << d3_result.num_solids << "\n";
    std::cout << "  Shells: " << d3_result.num_shells << "\n";
    std::cout << "  States: " << d3_result.num_states << "\n";

    // ========================================
    // Validation
    // ========================================
    printSeparator("Validation");

    // Re-open original and final D3plot for comparison
    D3plotReader original_reader(d3plot_path);
    D3plotReader final_reader(d3plot_out);

    if (original_reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Cannot re-open original D3plot\n";
        return 1;
    }

    if (final_reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Cannot open final D3plot\n";
        return 1;
    }

    auto orig_mesh = original_reader.read_mesh();
    auto final_mesh = final_reader.read_mesh();

    std::cout << "Comparing original vs final:\n";
    std::cout << "  Original nodes: " << orig_mesh.get_num_nodes() << "\n";
    std::cout << "  Final nodes:    " << final_mesh.get_num_nodes() << "\n";
    std::cout << "  Original solids: " << orig_mesh.solids.size() << "\n";
    std::cout << "  Final solids:    " << final_mesh.solids.size() << "\n";
    std::cout << "  Original shells: " << orig_mesh.shells.size() << "\n";
    std::cout << "  Final shells:    " << final_mesh.shells.size() << "\n";

    // Compare node coordinates (sample)
    size_t min_nodes = std::min(orig_mesh.nodes.size(), final_mesh.nodes.size());
    size_t sample_count = std::min(size_t(100), min_nodes);
    double max_coord_error = 0.0;

    for (size_t i = 0; i < sample_count; ++i) {
        double dx = std::abs(orig_mesh.nodes[i].x - final_mesh.nodes[i].x);
        double dy = std::abs(orig_mesh.nodes[i].y - final_mesh.nodes[i].y);
        double dz = std::abs(orig_mesh.nodes[i].z - final_mesh.nodes[i].z);
        max_coord_error = std::max(max_coord_error, std::max(dx, std::max(dy, dz)));
    }

    std::cout << "  Max coordinate error (sample): " << max_coord_error << "\n";

    bool pass = (max_coord_error < 1e-3);
    std::cout << "\n  Result: " << (pass ? "PASS" : "FAIL") << "\n";

    original_reader.close();
    final_reader.close();

    // ========================================
    // Summary
    // ========================================
    auto total_end = std::chrono::high_resolution_clock::now();
    auto total_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        total_end - total_start).count();

    printSeparator("Summary");
    std::cout << "Conversion chain completed!\n";
    std::cout << "  D3plot → VTK → Radioss → VTK → D3plot\n\n";
    std::cout << "Output files:\n";
    std::cout << "  " << vtk1_path << "\n";
    std::cout << "  " << radioss_base << "0 (A00)\n";
    std::cout << "  " << radioss_base << "1 (A01)\n";
    std::cout << "  " << vtk2_path << "\n";
    std::cout << "  " << d3plot_out << "\n";
    std::cout << "\nTotal time: " << total_ms << " ms\n";
    std::cout << "========================================\n";

    return pass ? 0 : 1;
}
