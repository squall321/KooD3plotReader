/**
 * @file test_base_file_only.cpp
 * @brief Test reading states from base file (d3plot) only - no family files
 */

#include "kood3plot/core/BinaryReader.hpp"
#include "kood3plot/parsers/ControlDataParser.hpp"
#include "kood3plot/parsers/StateDataParser.hpp"
#include <iostream>
#include <iomanip>
#include <cmath>

int main(int argc, char* argv[]) {
    std::string filepath = "results/d3plot";

    if (argc > 1) {
        filepath = argv[1];
    }

    std::cout << "=== Base File Only State Test ===\n";
    std::cout << "File: " << filepath << "\n\n";

    // Open base file only
    auto reader = std::make_shared<kood3plot::core::BinaryReader>(filepath);
    auto err = reader->open();

    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open file\n";
        return 1;
    }

    std::cout << "File size: " << reader->get_file_size_words() << " words ("
              << (reader->get_file_size_words() * reader->get_word_size() / (1024*1024)) << " MB)\n\n";

    // Parse control data
    kood3plot::parsers::ControlDataParser ctrl_parser(reader);
    auto control_data = ctrl_parser.parse();

    std::cout << "=== Control Data ===\n";
    std::cout << "NUMNP: " << control_data.NUMNP << "\n";
    std::cout << "NDIM: " << control_data.NDIM << "\n";
    std::cout << "NGLBV: " << control_data.NGLBV << "\n";
    std::cout << "NND: " << control_data.NND << "\n";
    std::cout << "ENN: " << control_data.ENN << "\n";
    std::cout << "IT/IU/IV/IA: " << control_data.IT << "/" << control_data.IU
              << "/" << control_data.IV << "/" << control_data.IA << "\n";
    std::cout << "NEL8: " << control_data.NEL8 << "\n";
    std::cout << "NARBS: " << control_data.NARBS << "\n";
    std::cout << "EXTRA: " << control_data.EXTRA << "\n";

    // Calculate state size
    size_t state_size = 1 + control_data.NGLBV + control_data.NND + control_data.ENN;
    std::cout << "\nState size: " << state_size << " words\n";
    std::cout << "= 1 (time) + " << control_data.NGLBV << " (globals) + "
              << control_data.NND << " (nodal) + " << control_data.ENN << " (element)\n";

    // Parse states
    std::cout << "\n=== Parsing States ===\n";
    kood3plot::parsers::StateDataParser state_parser(reader, control_data);
    auto states = state_parser.parse_all();

    std::cout << "Found " << states.size() << " states in base file\n\n";

    // Show first 20 states
    std::cout << "=== First 20 States ===\n";
    std::cout << std::fixed << std::setprecision(6);
    std::cout << "State   Time            DispSize    Node1_Ux        Node1_Uy        Node1_Uz\n";
    std::cout << "-----   ----------      --------    ------------    ------------    ------------\n";

    int show_count = std::min(20, (int)states.size());
    for (int i = 0; i < show_count; ++i) {
        const auto& state = states[i];
        std::cout << std::setw(5) << i << "   ";
        std::cout << std::setw(14) << state.time << "    ";
        std::cout << std::setw(8) << state.node_displacements.size() << "    ";

        if (state.node_displacements.size() >= 3) {
            // First node displacement (using NDIM for stride)
            int ndim = control_data.NDIM;
            std::cout << std::setw(12) << state.node_displacements[0] << "    ";
            std::cout << std::setw(12) << state.node_displacements[1] << "    ";
            std::cout << std::setw(12) << state.node_displacements[2];
        }
        std::cout << "\n";
    }

    // Check time monotonicity
    std::cout << "\n=== Time Monotonicity Check ===\n";
    int discontinuities = 0;
    double prev_time = -1e30;

    for (size_t i = 0; i < states.size(); ++i) {
        if (states[i].time < prev_time) {
            discontinuities++;
            if (discontinuities <= 5) {
                std::cout << "DISCONTINUITY at state " << i << ": "
                          << prev_time << " -> " << states[i].time << "\n";
            }
        }
        prev_time = states[i].time;
    }

    if (discontinuities > 5) {
        std::cout << "... and " << (discontinuities - 5) << " more\n";
    }

    std::cout << "\nTotal discontinuities: " << discontinuities << "\n";
    if (discontinuities == 0 && states.size() > 0) {
        std::cout << "✓ Time values are monotonically increasing (GOOD)\n";
        std::cout << "Time range: " << states.front().time << " -> " << states.back().time << "\n";
    } else if (states.size() > 0) {
        std::cout << "✗ Time values have discontinuities (BAD)\n";
    }

    reader->close();
    std::cout << "\n✓ Test complete\n";

    return 0;
}
