#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/render/GeometryAnalyzer.h"
#include "kood3plot/render/D3plotCache.h"
#include <iostream>
#include <chrono>

using namespace kood3plot;
using namespace kood3plot::render;

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <d3plot_path>\n";
        return 1;
    }

    std::string d3plot_path = argv[1];

    std::cout << "==============================================\n";
    std::cout << "  D3plot Cache Performance Test\n";
    std::cout << "==============================================\n\n";

    try {
        // Open D3plot file
        D3plotReader reader(d3plot_path);
        reader.open();

        auto& cache = getGlobalCache();
        cache.clear(); // Start with empty cache

        std::cout << "Testing bounding box calculations with caching...\n\n";

        // Test 1: First call (cache miss - should be slow)
        std::cout << "--- Test 1: First call (cache miss) ---\n";
        auto start1 = std::chrono::high_resolution_clock::now();
        auto bbox1 = GeometryAnalyzer::calculateModelBounds(reader, 0);
        auto end1 = std::chrono::high_resolution_clock::now();
        auto duration1 = std::chrono::duration_cast<std::chrono::microseconds>(end1 - start1).count();

        std::cout << "Bounding Box: ["
                  << bbox1.min[0] << ", " << bbox1.max[0] << "] x ["
                  << bbox1.min[1] << ", " << bbox1.max[1] << "] x ["
                  << bbox1.min[2] << ", " << bbox1.max[2] << "]\n";
        std::cout << "Time: " << duration1 << " microseconds\n\n";

        // Test 2: Second call (cache hit - should be fast)
        std::cout << "--- Test 2: Second call (cache hit) ---\n";
        auto start2 = std::chrono::high_resolution_clock::now();
        auto bbox2 = GeometryAnalyzer::calculateModelBounds(reader, 0);
        auto end2 = std::chrono::high_resolution_clock::now();
        auto duration2 = std::chrono::duration_cast<std::chrono::microseconds>(end2 - start2).count();

        std::cout << "Bounding Box: ["
                  << bbox2.min[0] << ", " << bbox2.max[0] << "] x ["
                  << bbox2.min[1] << ", " << bbox2.max[1] << "] x ["
                  << bbox2.min[2] << ", " << bbox2.max[2] << "]\n";
        std::cout << "Time: " << duration2 << " microseconds\n\n";

        // Test 3: Multiple calls
        std::cout << "--- Test 3: 10 more calls (all cache hits) ---\n";
        auto start3 = std::chrono::high_resolution_clock::now();
        for (int i = 0; i < 10; ++i) {
            GeometryAnalyzer::calculateModelBounds(reader, 0);
        }
        auto end3 = std::chrono::high_resolution_clock::now();
        auto duration3 = std::chrono::duration_cast<std::chrono::microseconds>(end3 - start3).count();

        std::cout << "Total time for 10 calls: " << duration3 << " microseconds\n";
        std::cout << "Average per call: " << (duration3 / 10) << " microseconds\n\n";

        // Performance comparison
        std::cout << "==============================================\n";
        std::cout << "  Performance Summary\n";
        std::cout << "==============================================\n";
        std::cout << "First call (no cache):  " << duration1 << " μs\n";
        std::cout << "Second call (cached):   " << duration2 << " μs\n";
        std::cout << "Speedup:                " << (duration1 / (double)duration2) << "x faster\n\n";

        // Cache statistics
        std::cout << "==============================================\n";
        std::cout << "  Cache Statistics\n";
        std::cout << "==============================================\n";
        cache.printStats();

        // Verify correctness
        if (bbox1.min[0] == bbox2.min[0] && bbox1.max[0] == bbox2.max[0] &&
            bbox1.min[1] == bbox2.min[1] && bbox1.max[1] == bbox2.max[1] &&
            bbox1.min[2] == bbox2.min[2] && bbox1.max[2] == bbox2.max[2]) {
            std::cout << "✓ Cached result matches original calculation\n";
        } else {
            std::cout << "✗ ERROR: Cached result does not match!\n";
            return 1;
        }

    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
