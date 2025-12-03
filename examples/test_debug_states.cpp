/**
 * @file test_debug_states.cpp
 * @brief Debug state data parsing - check time values and continuity
 */

#include "kood3plot/D3plotReader.hpp"
#include <iostream>
#include <iomanip>
#include <algorithm>
#include <cmath>

int main(int argc, char* argv[]) {
    std::string filepath = "results/d3plot";

    if (argc > 1) {
        filepath = argv[1];
    }

    std::cout << "=== D3plot State Data Debug ===\n";
    std::cout << "File: " << filepath << "\n\n";

    kood3plot::D3plotReader reader(filepath);
    auto err = reader.open();

    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open file\n";
        return 1;
    }

    // Get control data
    auto cd = reader.get_control_data();
    std::cout << "=== Control Data ===\n";
    std::cout << "NUMNP (nodes): " << cd.NUMNP << "\n";
    std::cout << "NDIM: " << cd.NDIM << "\n";
    std::cout << "NGLBV: " << cd.NGLBV << "\n";
    std::cout << "NND: " << cd.NND << " (nodal data words per state)\n";
    std::cout << "ENN: " << cd.ENN << " (element data words per state)\n";
    std::cout << "IT: " << cd.IT << " (temperature flag)\n";
    std::cout << "IU: " << cd.IU << " (displacement flag)\n";
    std::cout << "IV: " << cd.IV << " (velocity flag)\n";
    std::cout << "IA: " << cd.IA << " (acceleration flag)\n";
    std::cout << "NEL8: " << cd.NEL8 << "\n";
    std::cout << "NEL4: " << cd.NEL4 << "\n";
    std::cout << "NEL2: " << cd.NEL2 << "\n";
    std::cout << "NV3D: " << cd.NV3D << " (vars per solid elem)\n";
    std::cout << "NV2D: " << cd.NV2D << " (vars per shell elem)\n";
    std::cout << "EXTRA: " << cd.EXTRA << "\n";
    std::cout << "NARBS: " << cd.NARBS << "\n";

    // Calculate expected state size
    size_t state_size = 1 + cd.NGLBV + cd.NND + cd.ENN;
    std::cout << "\nExpected state size (words): " << state_size << "\n";
    std::cout << "= 1 (time) + " << cd.NGLBV << " (globals) + " << cd.NND << " (nodal) + " << cd.ENN << " (element)\n\n";

    // Read all states
    std::cout << "=== Reading States ===\n";
    auto states = reader.read_all_states();

    std::cout << "\nTotal states read: " << states.size() << "\n\n";

    // Show first 30 states
    std::cout << "=== First 30 States ===\n";
    std::cout << std::fixed << std::setprecision(6);
    std::cout << "State   Time          Nodes       Disp_Size   First_Disp_X    First_Disp_Y    First_Disp_Z\n";
    std::cout << "-----   ----------    ------      ---------   ------------    ------------    ------------\n";

    int show_count = std::min(30, (int)states.size());
    for (int i = 0; i < show_count; ++i) {
        const auto& state = states[i];

        std::cout << std::setw(5) << i << "   ";
        std::cout << std::setw(12) << state.time << "    ";

        // Check displacement data size
        size_t expected_disp_size = cd.NUMNP * cd.NDIM;
        std::cout << std::setw(6) << (state.node_displacements.size() / 3) << "      ";
        std::cout << std::setw(9) << state.node_displacements.size() << "   ";

        if (!state.node_displacements.empty()) {
            // First node displacement
            std::cout << std::setw(12) << state.node_displacements[0] << "    ";
            std::cout << std::setw(12) << state.node_displacements[1] << "    ";
            std::cout << std::setw(12) << state.node_displacements[2];
        } else {
            std::cout << "NO DATA";
        }
        std::cout << "\n";
    }

    // Check time value continuity
    std::cout << "\n=== Time Continuity Check ===\n";
    int discontinuities = 0;
    double prev_time = -1e30;

    for (size_t i = 0; i < states.size(); ++i) {
        if (states[i].time < prev_time) {
            discontinuities++;
            if (discontinuities <= 10) {
                std::cout << "DISCONTINUITY at state " << i << ": time "
                          << prev_time << " -> " << states[i].time << "\n";
            }
        }
        prev_time = states[i].time;
    }

    if (discontinuities > 10) {
        std::cout << "... and " << (discontinuities - 10) << " more discontinuities\n";
    }

    std::cout << "\nTotal discontinuities: " << discontinuities << "\n";

    if (discontinuities == 0) {
        std::cout << "✓ Time values are monotonically increasing (GOOD)\n";
    } else {
        std::cout << "✗ Time values are NOT monotonically increasing (BUG!)\n";
    }

    // Check last few states
    std::cout << "\n=== Last 10 States ===\n";
    std::cout << "State   Time          Disp_Size   Max_Disp\n";
    std::cout << "-----   ----------    ---------   --------\n";

    int start = std::max(0, (int)states.size() - 10);
    for (int i = start; i < (int)states.size(); ++i) {
        const auto& state = states[i];

        std::cout << std::setw(5) << i << "   ";
        std::cout << std::setw(12) << state.time << "    ";
        std::cout << std::setw(9) << state.node_displacements.size() << "   ";

        // Find max displacement magnitude
        double max_disp = 0.0;
        for (size_t j = 0; j + 2 < state.node_displacements.size(); j += 3) {
            double ux = state.node_displacements[j];
            double uy = state.node_displacements[j+1];
            double uz = state.node_displacements[j+2];
            double mag = std::sqrt(ux*ux + uy*uy + uz*uz);
            if (mag > max_disp) max_disp = mag;
        }
        std::cout << std::setw(12) << max_disp << "\n";
    }

    reader.close();
    std::cout << "\n✓ Debug complete\n";

    return 0;
}
