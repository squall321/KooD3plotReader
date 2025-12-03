/**
 * @file 02_integration_test.cpp
 * @brief V3 Query System Integration Test
 * @date 2025-11-21
 *
 * This program tests the V3 Query System with a real d3plot file:
 * - Part selection
 * - Time selection
 * - Quantity extraction
 * - CSV output
 */

#include <iostream>
#include <iomanip>
#include <string>

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/query/D3plotQuery.h"
#include "kood3plot/query/PartSelector.h"
#include "kood3plot/query/QuantitySelector.h"
#include "kood3plot/query/TimeSelector.h"
#include "kood3plot/query/QueryResult.h"

using namespace kood3plot;
using namespace kood3plot::query;

int main(int argc, char* argv[]) {
    std::cout << "===========================================\n";
    std::cout << "V3 Query System Integration Test\n";
    std::cout << "===========================================\n\n";

    // Check command line arguments
    std::string filepath;
    if (argc > 1) {
        filepath = argv[1];
    } else {
        filepath = "/home/koopark/cursor/pyKooCAE/occProject/Generators/dist/Examples/5.SimulationModify/Macro/d3plot";
    }

    std::cout << "Loading d3plot: " << filepath << "\n\n";

    try {
        // Open d3plot file
        D3plotReader reader(filepath);
        auto err = reader.open();
        if (err != ErrorCode::SUCCESS) {
            std::cerr << "Failed to open d3plot: " << error_to_string(err) << std::endl;
            return 1;
        }

        std::cout << "File opened successfully!\n";
        std::cout << "  Number of states: " << reader.get_num_states() << "\n";

        // Get time values
        auto times = reader.get_time_values();
        std::cout << "  Time range: ";
        if (!times.empty()) {
            std::cout << times.front() << " - " << times.back() << "\n";
        }
        std::cout << "\n";

        // Get control data for element counts
        const auto& ctrl = reader.get_control_data();
        std::cout << "Element counts:\n";
        std::cout << "  Solids: " << ctrl.NEL8 << "\n";
        std::cout << "  Shells: " << ctrl.NEL4 << "\n";
        std::cout << "  Beams: " << ctrl.NEL2 << "\n";
        std::cout << "  NV3D (vars/solid): " << ctrl.NV3D << "\n";
        std::cout << "  NV2D (vars/shell): " << ctrl.NV2D << "\n\n";

        // Test 1: Basic query - von Mises stress at last state
        std::cout << "===========================================\n";
        std::cout << "Test 1: Von Mises Stress at Last State\n";
        std::cout << "===========================================\n";

        D3plotQuery query1(reader);
        query1.selectAllParts()
              .selectQuantities(QuantitySelector::vonMises())
              .selectTime(TimeSelector::lastState());

        std::cout << "Query: " << query1.getDescription() << "\n\n";

        // Execute query
        auto result1 = query1.execute();

        std::cout << "Results:\n";
        std::cout << "  Data points: " << result1.size() << "\n";

        if (!result1.empty()) {
            auto stats = result1.getStatistics("von_mises");
            std::cout << "  Von Mises Statistics:\n";
            std::cout << "    Min: " << std::fixed << std::setprecision(3) << stats.min_value
                      << " (elem " << stats.min_element_id << ")\n";
            std::cout << "    Max: " << stats.max_value
                      << " (elem " << stats.max_element_id << ")\n";
            std::cout << "    Mean: " << stats.mean_value << "\n";
            std::cout << "    StdDev: " << stats.std_dev << "\n";

            // Show first few data points
            std::cout << "\n  First 5 data points:\n";
            size_t show_count = std::min(result1.size(), size_t(5));
            for (size_t i = 0; i < show_count; ++i) {
                const auto& pt = result1[i];
                std::cout << "    Elem " << pt.element_id
                          << " Part " << pt.part_id
                          << " t=" << pt.time
                          << " vm=" << pt.getValueOr("von_mises") << "\n";
            }
        }

        // Write to CSV
        std::string csv_file = "v3_test_vonmises.csv";
        query1.writeCSV(csv_file);
        std::cout << "\n  Written to: " << csv_file << "\n";

        // Write to JSON
        std::string json_file = "v3_test_vonmises.json";
        query1.writeJSON(json_file);
        std::cout << "  Written to: " << json_file << "\n\n";

        // Test 2: Multiple quantities at all states
        std::cout << "===========================================\n";
        std::cout << "Test 2: Common Crash Quantities (All States)\n";
        std::cout << "===========================================\n";

        D3plotQuery query2(reader);
        query2.selectAllParts()
              .selectQuantities(QuantitySelector::commonCrash())  // von_mises, eff_strain, displacement
              .selectTime(TimeSelector::allStates());

        std::cout << "Query: " << query2.getDescription() << "\n\n";

        auto result2 = query2.execute();
        std::cout << "Results:\n";
        std::cout << "  Data points: " << result2.size() << "\n";

        // Get all quantity names
        auto qty_names = result2.getQuantityNames();
        std::cout << "  Quantities: ";
        for (const auto& name : qty_names) {
            std::cout << name << " ";
        }
        std::cout << "\n\n";

        // Show statistics for each quantity
        for (const auto& name : qty_names) {
            auto stats = result2.getStatistics(name);
            std::cout << "  " << name << ":\n";
            std::cout << "    Range: [" << stats.min_value << ", " << stats.max_value << "]\n";
            std::cout << "    Mean: " << stats.mean_value << "\n";
        }

        csv_file = "v3_test_common_crash.csv";
        query2.writeCSV(csv_file);
        std::cout << "\n  Written to: " << csv_file << "\n\n";

        // Test 3: Time history for specific elements
        std::cout << "===========================================\n";
        std::cout << "Test 3: Time History (First 10 Elements)\n";
        std::cout << "===========================================\n";

        // Get element IDs from result1
        auto elem_ids = result1.getElementIds();
        if (!elem_ids.empty()) {
            // Get history for first element
            int32_t first_elem = elem_ids[0];
            auto history = result2.getElementHistory(first_elem);

            std::cout << "Element " << first_elem << " time history:\n";
            std::cout << "  Time points: " << history.times.size() << "\n";

            if (!history.times.empty()) {
                std::cout << "  Sample (first 3 and last):\n";
                size_t n = history.times.size();
                for (size_t i = 0; i < std::min(size_t(3), n); ++i) {
                    std::cout << "    t=" << history.times[i];
                    for (const auto& [qty, vals] : history.quantity_histories) {
                        if (i < vals.size()) {
                            std::cout << " " << qty << "=" << vals[i];
                        }
                    }
                    std::cout << "\n";
                }
                if (n > 3) {
                    std::cout << "    ...\n";
                    std::cout << "    t=" << history.times[n-1];
                    for (const auto& [qty, vals] : history.quantity_histories) {
                        if (n-1 < vals.size()) {
                            std::cout << " " << qty << "=" << vals[n-1];
                        }
                    }
                    std::cout << "\n";
                }
            }
        }

        std::cout << "\n===========================================\n";
        std::cout << "All tests completed successfully!\n";
        std::cout << "===========================================\n";

        reader.close();

    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
