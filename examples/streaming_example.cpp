/**
 * @file streaming_example.cpp
 * @brief Example showing memory-efficient streaming query for large d3plot files
 *
 * This example demonstrates the StreamingQuery class which processes data
 * incrementally rather than loading everything into memory - perfect for
 * very large d3plot files that would otherwise cause out-of-memory errors.
 *
 * Usage:
 *   ./streaming_example <d3plot_path> [output_dir]
 *
 * @author KooD3plot Team
 * @date 2025-12-02
 */

#include <iostream>
#include <iomanip>
#include <chrono>
#include <filesystem>

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/query/StreamingQuery.hpp"

using namespace kood3plot;
using namespace kood3plot::query;

namespace fs = std::filesystem;

int main(int argc, char* argv[]) {
    // Parse arguments
    if (argc < 2) {
        std::cout << "Usage: " << argv[0] << " <d3plot_path> [output_dir]\n";
        std::cout << "\n";
        std::cout << "This example demonstrates memory-efficient streaming query.\n";
        std::cout << "Unlike standard query which loads all data into memory,\n";
        std::cout << "streaming query processes one state at a time.\n";
        return 1;
    }

    std::string d3plot_path = argv[1];
    std::string output_dir = argc > 2 ? argv[2] : "streaming_output";

    fs::create_directories(output_dir);

    std::cout << "==========================================================\n";
    std::cout << " StreamingQuery Example - Memory-Efficient Processing\n";
    std::cout << "==========================================================\n\n";

    // Open d3plot
    D3plotReader reader(d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Failed to open: " << d3plot_path << "\n";
        return 1;
    }

    auto control = reader.get_control_data();
    auto mesh = reader.read_mesh();
    std::cout << "d3plot file: " << d3plot_path << "\n";
    std::cout << "  Solid elements: " << mesh.num_solids << "\n";
    std::cout << "  Shell elements: " << mesh.num_shells << "\n";
    std::cout << "  Time steps: " << reader.get_num_states() << "\n";

    // =========================================================
    // Example 1: Streaming to CSV file
    // =========================================================
    std::cout << "\n--- Example 1: Stream directly to CSV ---\n";
    {
        StreamingQuery query(reader);

        // Configure query
        query.selectAllParts()
             .selectQuantities(QuantitySelector::vonMises())
             .selectTime(TimeSelector::allStates())
             .reportProgress(true)
             .onProgress([](size_t current, size_t total, const std::string& msg) {
                 std::cout << "\r  Progress: " << current << "/" << total << " " << msg;
                 std::cout.flush();
             });

        std::string output_file = output_dir + "/von_mises_all_states.csv";

        auto stats = query.streamToCSV(output_file);

        std::cout << "\n";
        std::cout << "  Output: " << output_file << "\n";
        std::cout << "  Points written: " << stats.points_processed << "\n";
        std::cout << "  Bytes written: " << stats.bytes_written << "\n";
        std::cout << "  Time: " << stats.processing_time_ms << " ms\n";
    }

    // =========================================================
    // Example 2: Find maximum value (memory-efficient)
    // =========================================================
    std::cout << "\n--- Example 2: Find maximum Von Mises stress ---\n";
    {
        StreamingQuery query(reader);

        query.selectAllParts()
             .selectQuantities(QuantitySelector::vonMises())
             .selectTime(TimeSelector::allStates());

        auto max_point = query.findMax("von_mises");

        if (max_point) {
            std::cout << "  Max Von Mises: " << std::scientific << std::setprecision(4)
                      << max_point->values.at("von_mises") << "\n";
            std::cout << "  Element ID: " << max_point->element_id << "\n";
            std::cout << "  Part ID: " << max_point->part_id << "\n";
            std::cout << "  At time: " << std::fixed << std::setprecision(6) << max_point->time << "\n";
        }
    }

    // =========================================================
    // Example 3: Chunk-based processing
    // =========================================================
    std::cout << "\n--- Example 3: Chunk-based processing ---\n";
    {
        StreamingQuery query(reader);

        query.selectAllParts()
             .selectQuantities(QuantitySelector::vonMises())
             .selectTime(TimeSelector::lastState());  // Last state only

        size_t total_points = 0;
        double sum = 0.0;
        double max_val = 0.0;

        // Process in chunks of 5000 points
        auto stats = query.forEachChunk(5000,
            [&](const std::vector<ResultDataPoint>& chunk, size_t chunk_idx) {
                // Process each chunk
                for (const auto& point : chunk) {
                    auto it = point.values.find("von_mises");
                    if (it != point.values.end()) {
                        sum += it->second;
                        if (it->second > max_val) {
                            max_val = it->second;
                        }
                    }
                }
                total_points += chunk.size();
                return true;  // Continue processing
            });

        double avg = total_points > 0 ? sum / total_points : 0.0;

        std::cout << "  Chunks processed: " << (stats.points_processed / 5000 + 1) << "\n";
        std::cout << "  Total points: " << total_points << "\n";
        std::cout << "  Average Von Mises: " << std::scientific << avg << "\n";
        std::cout << "  Max Von Mises: " << max_val << "\n";
    }

    // =========================================================
    // Example 4: Calculate statistics without loading all data
    // =========================================================
    std::cout << "\n--- Example 4: Online statistics (Welford's algorithm) ---\n";
    {
        StreamingQuery query(reader);

        query.selectAllParts()
             .selectQuantities(QuantitySelector::vonMises())
             .selectTime(TimeSelector::allStates());

        auto stats = query.calculateStats("von_mises");

        std::cout << "  Count: " << stats.count << "\n";
        std::cout << "  Min: " << std::scientific << stats.min_value
                  << " (element " << stats.min_element_id << ")\n";
        std::cout << "  Max: " << stats.max_value
                  << " (element " << stats.max_element_id << ")\n";
        std::cout << "  Mean: " << stats.mean_value << "\n";
        std::cout << "  StdDev: " << stats.std_dev << "\n";
        std::cout << "  Range: " << stats.range << "\n";
    }

    // =========================================================
    // Example 5: Get Top N values
    // =========================================================
    std::cout << "\n--- Example 5: Top 5 Von Mises values ---\n";
    {
        StreamingQuery query(reader);

        query.selectAllParts()
             .selectQuantities(QuantitySelector::vonMises())
             .selectTime(TimeSelector::allStates());

        auto top5 = query.topN("von_mises", 5);

        std::cout << "  Rank | Element | Part | Time     | Von Mises\n";
        std::cout << "  -----|---------|------|----------|------------\n";
        for (size_t i = 0; i < top5.size(); ++i) {
            const auto& p = top5[i];
            auto vm = p.values.at("von_mises");
            std::cout << "  " << std::setw(4) << (i + 1)
                      << " | " << std::setw(7) << p.element_id
                      << " | " << std::setw(4) << p.part_id
                      << " | " << std::fixed << std::setprecision(4) << std::setw(8) << p.time
                      << " | " << std::scientific << std::setprecision(4) << vm << "\n";
        }
    }

    // =========================================================
    // Memory comparison
    // =========================================================
    std::cout << "\n==========================================================\n";
    std::cout << " Memory Comparison\n";
    std::cout << "==========================================================\n";

    StreamingQuery query_for_estimate(reader);
    query_for_estimate.selectAllParts()
                      .selectQuantities(QuantitySelector::vonMises())
                      .selectTime(TimeSelector::allStates());

    size_t estimated_size = query_for_estimate.estimateSize();
    size_t estimated_memory = query_for_estimate.estimateMemoryBytes();

    std::cout << "  Estimated data points: " << estimated_size << "\n";
    std::cout << "  If loaded all at once: ~" << (estimated_memory / 1024 / 1024) << " MB\n";
    std::cout << "  With streaming: ~" << (query_for_estimate.estimateMemoryBytes() / estimated_size / 1024) << " KB per point\n";
    std::cout << "\n";
    std::cout << "StreamingQuery processes one state at a time, keeping memory\n";
    std::cout << "usage constant regardless of file size!\n";

    std::cout << "\n==========================================================\n";
    std::cout << " Done!\n";
    std::cout << "==========================================================\n";

    return 0;
}
