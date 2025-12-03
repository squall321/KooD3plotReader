/**
 * @file test_family_file.cpp
 * @brief Test reading a single family file (d3plot01) with correct offset
 */

#include "kood3plot/core/BinaryReader.hpp"
#include "kood3plot/parsers/ControlDataParser.hpp"
#include "kood3plot/parsers/StateDataParser.hpp"
#include <iostream>
#include <iomanip>
#include <cmath>

int main(int argc, char* argv[]) {
    std::string base_file = "results/d3plot";
    std::string family_file = "results/d3plot01";

    if (argc > 1) {
        base_file = argv[1];
    }
    if (argc > 2) {
        family_file = argv[2];
    }

    std::cout << "=== Family File Test ===\n";
    std::cout << "Base file: " << base_file << "\n";
    std::cout << "Family file: " << family_file << "\n\n";

    // Step 1: Open base file and parse control data
    auto base_reader = std::make_shared<kood3plot::core::BinaryReader>(base_file);
    auto err = base_reader->open();

    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open base file\n";
        return 1;
    }

    kood3plot::parsers::ControlDataParser ctrl_parser(base_reader);
    auto control_data = ctrl_parser.parse();

    std::cout << "Control data loaded from base file\n";
    std::cout << "  NUMNP: " << control_data.NUMNP << "\n";
    std::cout << "  State size: " << (1 + control_data.NGLBV + control_data.NND + control_data.ENN) << " words\n\n";

    // Step 2: Open family file with known format
    auto family_reader = std::make_shared<kood3plot::core::BinaryReader>(family_file);
    err = family_reader->open_family_file(base_reader->get_precision(), base_reader->get_endian());

    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open family file\n";
        return 1;
    }

    std::cout << "Family file size: " << family_reader->get_file_size_words() << " words ("
              << (family_reader->get_file_size_words() * family_reader->get_word_size() / (1024*1024)) << " MB)\n\n";

    // Step 3: Parse states from family file (is_family_file = true)
    kood3plot::parsers::StateDataParser state_parser(family_reader, control_data, true);  // <-- key fix
    auto states = state_parser.parse_all();

    std::cout << "Found " << states.size() << " states in family file\n\n";

    // Step 4: Show first 20 states
    std::cout << "=== First 20 States ===\n";
    std::cout << std::fixed << std::setprecision(6);
    std::cout << "State   Time            Node1_Ux        Node1_Uy        Node1_Uz        MaxDisp\n";
    std::cout << "-----   ----------      ------------    ------------    ------------    ------------\n";

    int show_count = std::min(20, (int)states.size());
    for (int i = 0; i < show_count; ++i) {
        const auto& state = states[i];

        // Find max displacement
        double max_disp = 0.0;
        for (size_t j = 0; j + 2 < state.node_displacements.size(); j += 3) {
            double ux = state.node_displacements[j];
            double uy = state.node_displacements[j+1];
            double uz = state.node_displacements[j+2];
            double mag = std::sqrt(ux*ux + uy*uy + uz*uz);
            if (mag > max_disp) max_disp = mag;
        }

        std::cout << std::setw(5) << i << "   ";
        std::cout << std::setw(14) << state.time << "    ";

        if (state.node_displacements.size() >= 3) {
            std::cout << std::setw(12) << state.node_displacements[0] << "    ";
            std::cout << std::setw(12) << state.node_displacements[1] << "    ";
            std::cout << std::setw(12) << state.node_displacements[2] << "    ";
        } else {
            std::cout << "NO DATA                                            ";
        }
        std::cout << std::setw(12) << max_disp << "\n";
    }

    // Step 5: Check time monotonicity
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
        std::cout << "✓ Time values are MONOTONICALLY INCREASING (GOOD!)\n";
        std::cout << "Time range: " << states.front().time << " -> " << states.back().time << "\n";
    } else if (states.size() > 0) {
        std::cout << "✗ Time values have discontinuities (BAD)\n";
    }

    base_reader->close();
    family_reader->close();

    std::cout << "\n✓ Test complete\n";
    return 0;
}
