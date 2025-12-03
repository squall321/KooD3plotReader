/**
 * @file find_states.cpp
 * @brief Find actual state boundaries by looking for time patterns
 */

#include "kood3plot/core/BinaryReader.hpp"
#include "kood3plot/parsers/ControlDataParser.hpp"
#include <iostream>
#include <iomanip>
#include <cmath>
#include <vector>
#include <algorithm>

int main(int argc, char* argv[]) {
    std::string base_file = "results/d3plot";
    std::string family_file = "results/d3plot01";

    if (argc > 1) base_file = argv[1];
    if (argc > 2) family_file = argv[2];

    std::cout << "=== Find States Test ===\n\n";

    // Open base file
    auto base_reader = std::make_shared<kood3plot::core::BinaryReader>(base_file);
    auto err = base_reader->open();
    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open base file\n";
        return 1;
    }

    // Parse control data
    kood3plot::parsers::ControlDataParser ctrl_parser(base_reader);
    auto cd = ctrl_parser.parse();

    std::cout << "Control Data:\n";
    std::cout << "  NUMNP = " << cd.NUMNP << "\n";
    std::cout << "  NDIM = " << cd.NDIM << " (effective = " << (cd.NDIM >= 4 ? 3 : cd.NDIM) << ")\n";
    std::cout << "  NGLBV = " << cd.NGLBV << "\n";
    std::cout << "  NND = " << cd.NND << " (should be ≈ " << (3 * (cd.IU + cd.IV + cd.IA) * cd.NUMNP) << ")\n";
    std::cout << "  ENN = " << cd.ENN << "\n";
    std::cout << "  IT/IU/IV/IA = " << cd.IT << "/" << cd.IU << "/" << cd.IV << "/" << cd.IA << "\n";
    std::cout << "  ISTRN = " << cd.ISTRN << "\n";

    // Calculated state size
    size_t state_size = 1 + cd.NGLBV + cd.NND + cd.ENN;
    std::cout << "\n  Calculated state size: " << state_size << " words\n";
    std::cout << "  = 1 (time) + " << cd.NGLBV << " (global) + " << cd.NND << " (nodal) + " << cd.ENN << " (element)\n\n";

    // Open family file
    auto family_reader = std::make_shared<kood3plot::core::BinaryReader>(family_file);
    err = family_reader->open_family_file(base_reader->get_precision(), base_reader->get_endian());
    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open family file\n";
        return 1;
    }

    size_t file_words = family_reader->get_file_size_words();
    std::cout << "Family file size: " << file_words << " words\n";
    std::cout << "Expected states: " << (file_words / state_size) << "\n\n";

    // Try to find actual time values
    // LS-DYNA typically outputs time in small increments (0.0001, 0.0002, ...)
    // Look for monotonically increasing small positive values
    std::cout << "=== Searching for Time Values ===\n";
    std::cout << "Looking for monotonically increasing values in range [0, 0.1]\n\n";

    std::vector<std::pair<size_t, double>> time_candidates;

    for (size_t i = 0; i < std::min(file_words, (size_t)100000); ++i) {
        double val = family_reader->read_double(i);

        // Time values at state 0 are typically 0.0 or small positive
        // Subsequent time values increase monotonically
        if (val >= 0.0 && val < 0.2 && val != 0.0) {
            // Check if this could be a reasonable time value
            // by looking at surrounding context
            bool is_potential_time = false;

            // Time is usually isolated (surrounded by different scale values)
            if (i > 0 && i + 1 < file_words) {
                double prev = family_reader->read_double(i - 1);
                double next = family_reader->read_double(i + 1);

                // Previous value might be element data (larger), next is global var
                if (std::abs(prev) > 10 || std::abs(next) > 10) {
                    is_potential_time = true;
                }
            }

            if (is_potential_time) {
                time_candidates.push_back({i, val});
                if (time_candidates.size() >= 30) break;
            }
        }
    }

    std::cout << "Found " << time_candidates.size() << " potential time values:\n";
    for (size_t j = 0; j < std::min(time_candidates.size(), (size_t)30); ++j) {
        std::cout << "  Word " << time_candidates[j].first << ": " << time_candidates[j].second << "\n";
    }

    // Also check expected state positions
    std::cout << "\n=== Check Expected State Positions ===\n";
    for (int state = 0; state < 5; ++state) {
        size_t offset = state * state_size;
        if (offset < file_words) {
            double time = family_reader->read_double(offset);
            double next_val = (offset + 1 < file_words) ? family_reader->read_double(offset + 1) : 0;
            std::cout << "State " << state << " @ word " << offset << ": time = " << time;
            std::cout << ", next word = " << next_val << "\n";
        }
    }

    // Check if there might be padding or extra data
    // Try different state sizes
    std::cout << "\n=== Try Different State Sizes ===\n";
    std::vector<size_t> test_sizes = {
        state_size,               // Current calculation
        state_size + 1,           // +1 word padding
        state_size + 512,         // 512-word padding
        state_size + (512 - state_size % 512),  // Aligned to 512
        file_words / 19,          // Assuming 19 states (from raw dump)
        file_words / 21,          // Assuming 21 states (from test_family_file)
        file_words / 52,          // Assuming more states
    };

    for (size_t test_size : test_sizes) {
        if (test_size == 0) continue;
        std::cout << "\nTesting state size = " << test_size << " words:\n";

        // Check first 5 states
        bool looks_good = true;
        double prev_time = -1;
        for (int state = 0; state < 5; ++state) {
            size_t offset = state * test_size;
            if (offset >= file_words) break;

            double time = family_reader->read_double(offset);
            std::cout << "  State " << state << " @ " << offset << ": time = " << time;

            // Check if monotonically increasing
            if (state > 0 && time <= prev_time) {
                std::cout << " [NOT MONOTONIC!]";
                looks_good = false;
            }
            prev_time = time;
            std::cout << "\n";
        }

        if (looks_good) {
            std::cout << "  ✓ This size looks promising!\n";
        }
    }

    base_reader->close();
    family_reader->close();

    std::cout << "\n✓ Test complete\n";
    return 0;
}
