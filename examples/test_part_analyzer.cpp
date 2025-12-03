/**
 * @file test_part_analyzer.cpp
 * @brief Test for PartAnalyzer class - Part-based time series analysis
 */
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/PartAnalyzer.hpp"
#include <iostream>
#include <iomanip>

using namespace kood3plot;
using namespace kood3plot::analysis;

int main(int argc, char* argv[]) {
    std::string d3plot_path = "results/d3plot";
    if (argc > 1) {
        d3plot_path = argv[1];
    }

    std::cout << "=== PartAnalyzer Test ===\n\n";
    std::cout << "D3plot path: " << d3plot_path << "\n\n";

    // Open d3plot file
    D3plotReader reader(d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Failed to open d3plot file\n";
        return 1;
    }

    // Create and initialize PartAnalyzer
    PartAnalyzer analyzer(reader);
    if (!analyzer.initialize()) {
        std::cerr << "Failed to initialize PartAnalyzer: " << analyzer.get_last_error() << "\n";
        return 1;
    }

    // List all parts
    const auto& parts = analyzer.get_parts();
    std::cout << "=== Part List (" << parts.size() << " parts) ===\n";
    std::cout << std::setw(10) << "Part ID" << std::setw(15) << "Name" << std::setw(15) << "Elements" << "\n";
    std::cout << std::string(40, '-') << "\n";
    for (const auto& part : parts) {
        std::cout << std::setw(10) << part.part_id
                  << std::setw(15) << part.name
                  << std::setw(15) << part.num_elements << "\n";
    }
    std::cout << "\n";

    // Analyze a single state for first few parts
    if (!parts.empty()) {
        std::cout << "=== Single State Analysis (State 0) ===\n";

        auto state0 = reader.read_state(0);
        std::cout << "Time: " << state0.time << " sec\n";
        std::cout << "Solid data size: " << state0.solid_data.size() << "\n\n";

        std::cout << std::setw(10) << "Part ID"
                  << std::setw(15) << "Max VM Stress"
                  << std::setw(15) << "Min VM Stress"
                  << std::setw(15) << "Avg VM Stress"
                  << std::setw(15) << "Max Elem ID" << "\n";
        std::cout << std::string(70, '-') << "\n";

        // Analyze first 5 parts (or all if fewer)
        size_t num_to_analyze = std::min(size_t(5), parts.size());
        for (size_t i = 0; i < num_to_analyze; ++i) {
            auto stats = analyzer.analyze_state(parts[i].part_id, state0, StressComponent::VON_MISES);
            std::cout << std::setw(10) << stats.part_id
                      << std::setw(15) << std::scientific << std::setprecision(3) << stats.stress_max
                      << std::setw(15) << stats.stress_min
                      << std::setw(15) << stats.stress_avg
                      << std::setw(15) << stats.max_element_id << "\n";
        }
        std::cout << "\n";
    }

    // Analyze time history for one part (quick test with first 10 states)
    if (!parts.empty()) {
        int32_t test_part_id = parts[0].part_id;
        std::cout << "=== Time History (Part " << test_part_id << ", first 10 states) ===\n\n";

        auto times = reader.get_time_values();
        size_t num_states_to_show = std::min(size_t(10), times.size());

        std::cout << std::setw(6) << "State"
                  << std::setw(15) << "Time"
                  << std::setw(15) << "Max VM Stress"
                  << std::setw(15) << "Avg VM Stress" << "\n";
        std::cout << std::string(51, '-') << "\n";

        for (size_t s = 0; s < num_states_to_show; ++s) {
            auto state = reader.read_state(s);
            auto stats = analyzer.analyze_state(test_part_id, state, StressComponent::VON_MISES);
            std::cout << std::setw(6) << s
                      << std::setw(15) << std::scientific << std::setprecision(4) << stats.time
                      << std::setw(15) << stats.stress_max
                      << std::setw(15) << stats.stress_avg << "\n";
        }
        std::cout << "\n";
    }

    // Export single part history to CSV
    if (!parts.empty() && argc > 2) {
        std::string output_csv = argv[2];
        std::cout << "=== Exporting to CSV: " << output_csv << " ===\n";

        // Analyze first part completely
        auto history = analyzer.analyze_part(parts[0].part_id, StressComponent::VON_MISES);
        if (analyzer.export_to_csv(history, output_csv)) {
            std::cout << "[OK] Exported " << history.times.size() << " time steps to " << output_csv << "\n";
        } else {
            std::cout << "[FAIL] " << analyzer.get_last_error() << "\n";
        }
    }

    std::cout << "\n=== Test Complete ===\n";
    return 0;
}
