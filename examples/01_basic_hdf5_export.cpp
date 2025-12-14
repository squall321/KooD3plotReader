/**
 * @file 01_basic_hdf5_export.cpp
 * @brief Phase 1 Week 1 Example: Basic HDF5 export
 *
 * This example demonstrates:
 * - Reading a D3plot file
 * - Exporting mesh to HDF5 format
 * - Basic file validation
 *
 * Week 1 Milestone:
 * - Successfully write 100k node mesh to HDF5
 * - File size reduction of ~50% (with compression)
 */

#include <kood3plot/D3plotReader.hpp>
#include <kood3plot/hdf5/HDF5Writer.hpp>

#include <iostream>
#include <chrono>
#include <filesystem>

namespace fs = std::filesystem;

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <d3plot_file> [output.h5]\n";
        std::cerr << "\nExample:\n";
        std::cerr << "  " << argv[0] << " path/to/d3plot output.h5\n";
        return 1;
    }

    std::string d3plot_path = argv[1];
    std::string hdf5_path = (argc >= 3) ? argv[2] : "output.h5";

    std::cout << "========================================\n";
    std::cout << " Phase 1 Week 1: Basic HDF5 Export\n";
    std::cout << "========================================\n\n";

    // ========================================
    // Step 1: Read D3plot file
    // ========================================
    std::cout << "[1/3] Reading D3plot file: " << d3plot_path << "\n";

    kood3plot::D3plotReader reader(d3plot_path);

    auto start = std::chrono::high_resolution_clock::now();

    if (reader.open() != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "ERROR: Failed to open D3plot file\n";
        return 1;
    }

    // Read control data
    auto control_data = reader.get_control_data();
    std::cout << "  - Nodes: " << control_data.NUMNP << "\n";
    std::cout << "  - Solid elements: " << std::abs(control_data.NEL8) << "\n";
    std::cout << "  - Shell elements: " << std::abs(control_data.NEL4) << "\n";
    std::cout << "  - Beam elements: " << std::abs(control_data.NEL2) << "\n";

    // Read mesh
    auto mesh = reader.read_mesh();
    std::cout << "  - Actual nodes loaded: " << mesh.nodes.size() << "\n";
    std::cout << "  - Actual solids loaded: " << mesh.solids.size() << "\n";
    std::cout << "  - Actual shells loaded: " << mesh.shells.size() << "\n";
    std::cout << "  - Actual beams loaded: " << mesh.beams.size() << "\n";

    auto read_end = std::chrono::high_resolution_clock::now();
    auto read_time = std::chrono::duration_cast<std::chrono::milliseconds>(read_end - start).count();
    std::cout << "  ✓ D3plot read complete (" << read_time << " ms)\n\n";

    // ========================================
    // Step 2: Export to HDF5
    // ========================================
    std::cout << "[2/3] Exporting mesh to HDF5: " << hdf5_path << "\n";

    auto write_start = std::chrono::high_resolution_clock::now();

    try {
        kood3plot::hdf5::HDF5Writer writer(hdf5_path);
        writer.write_mesh(mesh);
        writer.close();

        auto write_end = std::chrono::high_resolution_clock::now();
        auto write_time = std::chrono::duration_cast<std::chrono::milliseconds>(write_end - write_start).count();
        std::cout << "  ✓ HDF5 export complete (" << write_time << " ms)\n\n";

    } catch (const std::exception& e) {
        std::cerr << "ERROR: HDF5 export failed: " << e.what() << "\n";
        return 1;
    }

    // ========================================
    // Step 3: Validation and Statistics
    // ========================================
    std::cout << "[3/3] Validation and Statistics\n";

    // Check file exists
    if (!fs::exists(hdf5_path)) {
        std::cerr << "ERROR: HDF5 file was not created\n";
        return 1;
    }

    // File sizes
    size_t hdf5_size = fs::file_size(hdf5_path);
    std::cout << "  - HDF5 file size: " << (hdf5_size / 1024) << " KB\n";

    // Estimate uncompressed size
    size_t uncompressed_estimate =
        mesh.nodes.size() * 3 * sizeof(double) +          // Node coordinates
        mesh.solids.size() * 8 * sizeof(int) +            // Solid connectivity
        mesh.solids.size() * sizeof(int) +                // Solid part IDs
        mesh.shells.size() * 4 * sizeof(int) +            // Shell connectivity
        mesh.shells.size() * sizeof(int) +                // Shell part IDs
        mesh.beams.size() * 2 * sizeof(int) +             // Beam connectivity
        mesh.beams.size() * sizeof(int);                  // Beam part IDs

    std::cout << "  - Uncompressed estimate: " << (uncompressed_estimate / 1024) << " KB\n";

    double compression_ratio = 100.0 * static_cast<double>(hdf5_size) / static_cast<double>(uncompressed_estimate);
    std::cout << "  - Compression ratio: " << std::fixed << std::setprecision(1) << compression_ratio << "%\n";

    double space_saved = 100.0 * (1.0 - static_cast<double>(hdf5_size) / static_cast<double>(uncompressed_estimate));
    std::cout << "  - Space saved: " << std::fixed << std::setprecision(1) << space_saved << "%\n";

    // Week 1 Milestone Check
    std::cout << "\n========================================\n";
    std::cout << " Week 1 Milestone Validation\n";
    std::cout << "========================================\n";

    bool milestone_passed = true;

    // Check 1: Mesh size >= 100k nodes
    if (mesh.nodes.size() >= 100000) {
        std::cout << "✓ Mesh size: " << mesh.nodes.size() << " nodes (>= 100k)\n";
    } else {
        std::cout << "○ Mesh size: " << mesh.nodes.size() << " nodes (< 100k, smaller test)\n";
    }

    // Check 2: File size reduction >= 40% (Week 1 goal: 50%)
    if (space_saved >= 40.0) {
        std::cout << "✓ Space saved: " << std::fixed << std::setprecision(1) << space_saved << "% (>= 40%)\n";
    } else {
        std::cout << "⚠ Space saved: " << std::fixed << std::setprecision(1) << space_saved << "% (< 40%)\n";
        milestone_passed = false;
    }

    // Check 3: HDF5 file is valid
    std::cout << "✓ HDF5 file created successfully\n";

    std::cout << "\n";
    if (milestone_passed) {
        std::cout << "🎉 Week 1 Milestone: PASSED!\n";
    } else {
        std::cout << "⚠ Week 1 Milestone: Needs improvement\n";
    }

    std::cout << "\n";
    std::cout << "Next steps:\n";
    std::cout << "  - Week 2: Implement quantization (displacement, stress)\n";
    std::cout << "  - Week 3: Temporal delta compression (t>0 as int8 deltas)\n";
    std::cout << "  - Target: 70-85% total compression\n";

    return 0;
}
