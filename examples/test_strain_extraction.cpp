#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/query/D3plotQuery.h"
#include "kood3plot/query/PartSelector.h"
#include "kood3plot/query/QuantitySelector.h"
#include "kood3plot/query/TimeSelector.h"
#include "kood3plot/query/OutputSpec.h"
#include <iostream>
#include <chrono>
#include <set>
#include <cmath>

using namespace kood3plot;
using namespace kood3plot::query;

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <d3plot_path>\n";
        return 1;
    }

    std::string d3plot_path = argv[1];

    std::cout << "==============================================\n";
    std::cout << "  Max Strain History Extraction Test (V3 Query)\n";
    std::cout << "==============================================\n\n";

    try {
        // Open D3plot file
        D3plotReader reader(d3plot_path);
        reader.open();

        auto control = reader.get_control_data();

        // Get state count using time values
        auto time_values = reader.get_time_values();
        size_t num_states = time_values.size();

        std::cout << "Total states: " << num_states << "\n";
        std::cout << "Solid elements: " << std::abs(control.NEL8) << "\n";
        std::cout << "Shell elements: " << control.NEL4 << "\n\n";

        // Read mesh to get all part IDs
        auto mesh = reader.read_mesh();
        std::set<int32_t> part_ids;

        for (auto pid : mesh.solid_parts) {
            if (pid > 0) part_ids.insert(pid);
        }
        for (auto pid : mesh.shell_parts) {
            if (pid > 0) part_ids.insert(pid);
        }

        std::cout << "Found " << part_ids.size() << " unique parts\n";
        std::cout << "Part IDs: ";
        int count = 0;
        for (auto pid : part_ids) {
            std::cout << pid;
            if (++count < static_cast<int>(part_ids.size())) std::cout << ", ";
            if (count >= 10) {
                std::cout << "... (showing first 10)";
                break;
            }
        }
        std::cout << "\n\n";

        // Test 1: Extract max strain for all parts, all timesteps
        std::cout << "--- Test: Extract Effective Plastic Strain for All Parts ---\n";
        std::cout << "Processing " << part_ids.size() << " parts x "
                  << num_states << " states...\n\n";

        auto start = std::chrono::high_resolution_clock::now();

        // Create query for all parts, all timesteps using V3 Query API
        D3plotQuery query(reader);

        // Select all parts and strain data
        query.selectAllParts()
             .selectQuantities({"plastic_strain"})
             .selectTime(TimeSelector::allStates());

        // Execute query
        auto result = query.execute();

        auto end = std::chrono::high_resolution_clock::now();
        auto duration_ms = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

        std::cout << "==============================================\n";
        std::cout << "  Results\n";
        std::cout << "==============================================\n";
        std::cout << "Total extraction time: " << duration_ms << " ms\n";
        std::cout << "                       " << (duration_ms / 1000.0) << " seconds\n\n";

        // Calculate statistics using QueryResult API
        size_t total_values = result.size();

        std::cout << "Total data points extracted: " << total_values << "\n";
        if (total_values > 0) {
            std::cout << "Time per 1000 values: " << (duration_ms * 1000.0 / total_values) << " ms\n";
            std::cout << "Throughput: " << (total_values / (duration_ms / 1000.0)) << " values/sec\n\n";
        }

        // Get statistics for plastic strain
        auto stats = result.getStatistics("plastic_strain");

        std::cout << "Plastic Strain Statistics:\n";
        std::cout << "------------------------------------------------\n";
        std::cout << "  Min: " << stats.min_value << " (Element " << stats.min_element_id
                  << " at state " << stats.min_state_index << ")\n";
        std::cout << "  Max: " << stats.max_value << " (Element " << stats.max_element_id
                  << " at state " << stats.max_state_index << ")\n";
        std::cout << "  Mean: " << stats.mean_value << "\n";
        std::cout << "  Std Dev: " << stats.std_dev << "\n";
        std::cout << "  Count: " << stats.count << "\n\n";

        // Show sample data (first 10 data points)
        std::cout << "Sample data (first 10 data points):\n";
        std::cout << "------------------------------------------------\n";

        const auto& data_points = result.getDataPoints();
        size_t sample_count = std::min(data_points.size(), size_t(10));

        for (size_t i = 0; i < sample_count; ++i) {
            const auto& point = data_points[i];
            std::cout << "  Element " << point.element_id
                      << " (Part " << point.part_id << ")"
                      << " State " << point.state_index
                      << " Time " << point.time
                      << " Strain " << point.getValueOr("plastic_strain", 0.0) << "\n";
        }
        std::cout << "\n";

        // Find max strain element
        auto max_point = result.findMax("plastic_strain");
        if (max_point.has_value()) {
            std::cout << "Maximum plastic strain location:\n";
            std::cout << "------------------------------------------------\n";
            std::cout << "  Element: " << max_point->element_id << "\n";
            std::cout << "  Part: " << max_point->part_id << "\n";
            std::cout << "  State: " << max_point->state_index << "\n";
            std::cout << "  Time: " << max_point->time << " sec\n";
            std::cout << "  Strain: " << max_point->getValueOr("plastic_strain", 0.0) << "\n\n";
        }

        std::cout << "==============================================\n";
        std::cout << "  Test Complete!\n";
        std::cout << "==============================================\n";

    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
