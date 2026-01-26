/**
 * @file 05_radioss_to_vtk.cpp
 * @brief OpenRadioss animation file (A00/A01) to VTK conversion example
 *
 * This example demonstrates:
 * 1. Reading OpenRadioss A00 (header + geometry)
 * 2. Reading A01, A02, ... state files
 * 3. Converting to VTK time series
 * 4. Creating a .pvd file for ParaView
 *
 * Usage:
 *   ./converter_radioss_to_vtk <A00_file> <output_dir>
 * Example:
 *   ./converter_radioss_to_vtk results/A00 vtk_output
 */

#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <filesystem>
#include <string>
#include <chrono>

#include "kood3plot/converter/RadiossReader.h"
#include "kood3plot/converter/RadiossToVtkConverter.h"

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
        std::cout << "Usage: " << argv[0] << " <A00_file> <output_dir>\n";
        std::cout << "Example: " << argv[0] << " results/A00 vtk_output\n";
        return 1;
    }

    std::string a00_path = argv[1];
    std::string output_dir = argv[2];

    std::cout << "========================================\n";
    std::cout << " OpenRadioss to VTK Converter\n";
    std::cout << "========================================\n\n";

    // Create output directory
    try {
        fs::create_directories(output_dir);
    } catch (const std::exception& e) {
        std::cerr << "Error creating output directory: " << e.what() << "\n";
        return 1;
    }

    // ========================================
    // Step 1: Read OpenRadioss A00 file
    // ========================================
    std::cout << "[Step 1] Reading Radioss A00 file: " << a00_path << "\n";

    auto start_time = std::chrono::high_resolution_clock::now();

    RadiossReader reader(a00_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error opening Radioss A00 file: " << reader.getLastError() << "\n";
        return 1;
    }

    auto header = reader.getHeader();
    auto mesh = reader.getMesh();

    std::cout << "  Title: " << header.title << "\n";
    std::cout << "  Nodes: " << header.num_nodes << "\n";
    std::cout << "  Solids: " << header.num_solids << "\n";
    std::cout << "  Shells: " << header.num_shells << "\n";
    std::cout << "  Beams: " << header.num_beams << "\n";
    std::cout << "  Word size: " << header.word_size << " bytes\n";

    // Read all state files
    std::cout << "\n[Step 2] Reading all state files (A01, A02, ...)...\n";
    auto states = reader.readAllStates();

    auto read_time = std::chrono::high_resolution_clock::now();
    auto read_duration = std::chrono::duration_cast<std::chrono::milliseconds>(read_time - start_time);

    std::cout << "  Total states: " << states.size() << "\n";
    if (!states.empty()) {
        std::cout << "  Time range: " << states.front().time
                  << " - " << states.back().time << " s\n";
    }
    std::cout << "  Read time: " << read_duration.count() << " ms\n";

    reader.close();

    // ========================================
    // Step 3: Convert to VTK time series
    // ========================================
    std::cout << "\n[Step 3] Converting to VTK time series...\n";

    RadiossToVtkOptions options;
    options.title = header.title.empty() ? "Radioss Simulation" : header.title;
    options.export_displacement = header.has_displacement;
    options.export_velocity = header.has_velocity;
    options.export_acceleration = header.has_acceleration;
    options.export_stress = header.has_stress;
    options.export_plastic_strain = header.has_plastic_strain;
    options.verbose = false;

    RadiossToVtkConverter converter;
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

        auto result = converter.convert(header, mesh, states[i], vtk_path);
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
    if (states.size() > 0) {
        std::cout << "  Average: " << (convert_duration.count() / (double)states.size())
                  << " ms/state\n";
    }

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
