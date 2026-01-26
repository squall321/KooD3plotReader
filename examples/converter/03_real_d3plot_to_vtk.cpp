/**
 * @file 03_real_d3plot_to_vtk.cpp
 * @brief Real d3plot simulation data to VTK time series conversion
 *
 * This example demonstrates:
 * 1. Reading actual simulation d3plot files (with multiple states)
 * 2. Converting all states to VTK time series
 * 3. Creating a .pvd file for ParaView
 *
 * Usage:
 *   ./converter_real_d3plot d3plot output_dir
 */

#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <filesystem>
#include <string>
#include <chrono>

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/converter/D3plotToVtkConverter.h"

using namespace kood3plot;
using namespace kood3plot::converter;
namespace fs = std::filesystem;

// Create ParaView Data (.pvd) file for time series
bool createPvdFile(const std::string& pvd_path,
                   const std::vector<std::string>& vtk_files,
                   const std::vector<double>& times)
{
    std::ofstream pvd(pvd_path);
    if (!pvd.is_open()) {
        std::cerr << "Failed to create PVD file: " << pvd_path << "\n";
        return false;
    }

    pvd << "<?xml version=\"1.0\"?>\n";
    pvd << "<VTKFile type=\"Collection\" version=\"0.1\" byte_order=\"LittleEndian\">\n";
    pvd << "  <Collection>\n";

    for (size_t i = 0; i < vtk_files.size(); ++i) {
        fs::path vtk_path(vtk_files[i]);
        std::string filename = vtk_path.filename().string();

        pvd << "    <DataSet timestep=\"" << times[i]
            << "\" group=\"\" part=\"0\" file=\"" << filename << "\"/>\n";
    }

    pvd << "  </Collection>\n";
    pvd << "</VTKFile>\n";

    pvd.close();
    return true;
}

int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cout << "Usage: " << argv[0] << " <d3plot_file> <output_dir>\n";
        std::cout << "Example: " << argv[0] << " examples/results/d3plot vtk_output\n";
        return 1;
    }

    std::string d3plot_path = argv[1];
    std::string output_dir = argv[2];

    std::cout << "========================================\n";
    std::cout << " D3plot to VTK Time Series Converter\n";
    std::cout << "========================================\n\n";

    // Create output directory
    try {
        fs::create_directories(output_dir);
    } catch (const std::exception& e) {
        std::cerr << "Error creating output directory: " << e.what() << "\n";
        return 1;
    }

    // ========================================
    // Step 1: Read D3plot file
    // ========================================
    std::cout << "[Step 1] Reading D3plot file: " << d3plot_path << "\n";

    auto start_time = std::chrono::high_resolution_clock::now();

    D3plotReader reader(d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error opening D3plot file\n";
        return 1;
    }

    auto control = reader.get_control_data();
    auto mesh = reader.read_mesh();

    std::cout << "  Title: " << control.TITLE << "\n";
    std::cout << "  Nodes: " << control.NUMNP << "\n";
    std::cout << "  Solids: " << std::abs(control.NEL8) << "\n";
    std::cout << "  Shells: " << std::abs(control.NEL4) << "\n";
    std::cout << "  Beams: " << std::abs(control.NEL2) << "\n";
    std::cout << "  Thick shells: " << std::abs(control.NELT) << "\n";

    // Read all states
    std::cout << "\n[Step 2] Reading all states...\n";
    auto states = reader.read_all_states();
    reader.close();

    auto read_time = std::chrono::high_resolution_clock::now();
    auto read_duration = std::chrono::duration_cast<std::chrono::milliseconds>(read_time - start_time);

    std::cout << "  Total states: " << states.size() << "\n";
    if (!states.empty()) {
        std::cout << "  Time range: " << states.front().time
                  << " - " << states.back().time << " s\n";
    }
    std::cout << "  Read time: " << read_duration.count() << " ms\n";

    // ========================================
    // Step 3: Convert to VTK time series
    // ========================================
    std::cout << "\n[Step 3] Converting to VTK time series...\n";

    D3plotToVtkOptions options;
    options.title = control.TITLE.empty() ? "D3plot Simulation" : control.TITLE;
    options.export_displacement = (control.IU > 0);
    options.export_velocity = (control.IV > 0);
    options.export_acceleration = (control.IA > 0);
    options.export_stress = (control.NV3D > 0 || control.NV2D > 0 || control.NV1D > 0);
    options.export_plastic_strain = (control.NV3D >= 7);
    options.verbose = false;

    D3plotToVtkConverter converter;
    converter.setOptions(options);

    std::vector<std::string> vtk_files;
    std::vector<double> times;

    auto convert_start = std::chrono::high_resolution_clock::now();

    for (size_t i = 0; i < states.size(); ++i) {
        // Generate filename: output_dir/state_XXXX.vtk
        std::ostringstream oss;
        oss << output_dir << "/state_"
            << std::setw(4) << std::setfill('0') << i << ".vtk";
        std::string vtk_path = oss.str();

        auto result = converter.convert(control, mesh, states[i], vtk_path);
        if (!result.success) {
            std::cerr << "Error converting state " << i << ": "
                      << result.error_message << "\n";
            return 1;
        }

        vtk_files.push_back(vtk_path);
        times.push_back(states[i].time);

        if (i % 10 == 0 || i == states.size() - 1) {
            std::cout << "  Converted state " << i << "/" << states.size()
                      << " (t=" << states[i].time << "s)\n";
        }
    }

    auto convert_time = std::chrono::high_resolution_clock::now();
    auto convert_duration = std::chrono::duration_cast<std::chrono::milliseconds>(convert_time - convert_start);

    std::cout << "  Convert time: " << convert_duration.count() << " ms\n";
    std::cout << "  Average: " << (convert_duration.count() / (double)states.size())
              << " ms/state\n";

    // ========================================
    // Step 4: Create PVD file for ParaView
    // ========================================
    std::cout << "\n[Step 4] Creating ParaView Data (.pvd) file...\n";

    std::string pvd_path = output_dir + "/simulation.pvd";
    if (!createPvdFile(pvd_path, vtk_files, times)) {
        std::cerr << "Error creating PVD file\n";
        return 1;
    }

    std::cout << "  Created: " << pvd_path << "\n";

    // ========================================
    // Summary
    // ========================================
    auto total_time = std::chrono::high_resolution_clock::now();
    auto total_duration = std::chrono::duration_cast<std::chrono::milliseconds>(total_time - start_time);

    std::cout << "\n========================================\n";
    std::cout << " Conversion Complete!\n";
    std::cout << "========================================\n";
    std::cout << "  Output directory: " << output_dir << "\n";
    std::cout << "  VTK files: " << vtk_files.size() << "\n";
    std::cout << "  ParaView file: " << pvd_path << "\n";
    std::cout << "  Total time: " << total_duration.count() << " ms\n";
    std::cout << "\nOpen in ParaView:\n";
    std::cout << "  paraview " << pvd_path << "\n";
    std::cout << "========================================\n";

    return 0;
}
