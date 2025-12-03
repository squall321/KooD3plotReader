#include "kood3plot/D3plotReader.hpp"
#include <iostream>
#include <iomanip>

int main(int argc, char* argv[]) {
    std::string filepath = "../results/d3plot";

    if (argc > 1) {
        filepath = argv[1];
    }

    std::cout << "Simple D3plot Reader Example" << std::endl;
    std::cout << "============================" << std::endl;
    std::cout << "File: " << filepath << std::endl << std::endl;

    // Create reader
    kood3plot::D3plotReader reader(filepath);

    // Open file
    auto err = reader.open();
    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open file: " << kood3plot::error_to_string(err) << std::endl;
        return 1;
    }

    std::cout << "✓ File opened successfully" << std::endl;

    // Get file format
    auto format = reader.get_file_format();
    std::cout << "\n[File Format]" << std::endl;
    std::cout << "  Precision: " << (format.precision == kood3plot::Precision::SINGLE ? "Single" : "Double") << std::endl;
    std::cout << "  Endian: " << (format.endian == kood3plot::Endian::LITTLE ? "Little" : "Big") << "-endian" << std::endl;
    std::cout << "  Word size: " << format.word_size << " bytes" << std::endl;
    std::cout << "  Version: " << format.version << std::endl;

    // Get control data
    auto cd = reader.get_control_data();
    std::cout << "\n[Model Info]" << std::endl;
    std::cout << "  Nodes: " << cd.NUMNP << std::endl;
    std::cout << "  Solids: " << std::abs(cd.NEL8) << std::endl;
    std::cout << "  Thick shells: " << cd.NELT << std::endl;
    std::cout << "  Beams: " << cd.NEL2 << std::endl;
    std::cout << "  Shells: " << cd.NEL4 << std::endl;

    // Read mesh
    std::cout << "\n[Reading Mesh...]" << std::endl;
    try {
        auto mesh = reader.read_mesh();
        std::cout << "✓ Mesh loaded: " << mesh.get_num_nodes() << " nodes, "
                  << mesh.get_num_elements() << " elements" << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "✗ Failed to read mesh: " << e.what() << std::endl;
        return 1;
    }

    // Read all states
    std::cout << "\n[Reading States...]" << std::endl;
    try {
        auto states = reader.read_all_states();
        std::cout << "✓ Loaded " << states.size() << " time states" << std::endl;

        if (!states.empty()) {
            std::cout << "\n[Time History]" << std::endl;
            std::cout << std::fixed << std::setprecision(6);

            // Show first 5 states
            size_t show_count = std::min(size_t(5), states.size());
            std::cout << "  First " << show_count << " states:" << std::endl;
            for (size_t i = 0; i < show_count; ++i) {
                std::cout << "    State " << std::setw(3) << i << ": t = " << states[i].time << std::endl;
            }

            // Show last 3 if there are more than 5
            if (states.size() > 5) {
                std::cout << "  ..." << std::endl;
                std::cout << "  Last 3 states:" << std::endl;
                for (size_t i = states.size() - 3; i < states.size(); ++i) {
                    std::cout << "    State " << std::setw(3) << i << ": t = " << states[i].time << std::endl;
                }
            }

            // Show data sizes for first state
            std::cout << "\n[State Data Sizes (State 0)]" << std::endl;
            const auto& state0 = states[0];
            std::cout << "  Global vars: " << state0.global_vars.size() << std::endl;
            std::cout << "  Node displacements: " << state0.node_displacements.size() << std::endl;
            std::cout << "  Node velocities: " << state0.node_velocities.size() << std::endl;
            std::cout << "  Node accelerations: " << state0.node_accelerations.size() << std::endl;
            std::cout << "  Solid data: " << state0.solid_data.size() << std::endl;
        }
    } catch (const std::exception& e) {
        std::cerr << "✗ Failed to read states: " << e.what() << std::endl;
    }

    reader.close();
    std::cout << "\n✓ Reader closed" << std::endl;

    return 0;
}
