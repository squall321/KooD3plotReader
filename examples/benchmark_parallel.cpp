/**
 * @file benchmark_parallel.cpp
 * @brief Benchmark state-level vs element-level parallelization
 */

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/SinglePassAnalyzer.hpp"
#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
#include <iostream>
#include <chrono>
#include <iomanip>

using namespace kood3plot;
using namespace kood3plot::analysis;

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <d3plot_path>" << std::endl;
        return 1;
    }

    std::string d3plot_path = argv[1];

    // Open file
    D3plotReader reader(d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Failed to open " << d3plot_path << std::endl;
        return 1;
    }

    std::cout << "=== SinglePassAnalyzer Benchmark ===" << std::endl;
    std::cout << std::endl;

    // Configuration
    AnalysisConfig config;
    config.d3plot_path = d3plot_path;
    config.analyze_stress = true;
    config.analyze_strain = true;

    // ========================================
    // Test 1: State-level parallel (NEW - optimized)
    // ========================================
    {
        std::cout << "1. State-level parallel (NEW)..." << std::flush;

        D3plotReader reader1(d3plot_path);
        reader1.open();
        SinglePassAnalyzer analyzer1(reader1);
        analyzer1.setUseStateLevelParallel(true);  // Use state-level (default)

        auto start = std::chrono::high_resolution_clock::now();
        auto result1 = analyzer1.analyze(config);
        auto end = std::chrono::high_resolution_clock::now();

        auto duration1 = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
        std::cout << " " << duration1 << " ms" << std::endl;

        // Show sample results
        if (!result1.stress_history.empty() && !result1.stress_history[0].data.empty()) {
            auto& first_part = result1.stress_history[0];
            double max_stress = 0;
            for (const auto& tp : first_part.data) {
                if (tp.max_value > max_stress) max_stress = tp.max_value;
            }
            std::cout << "   Part " << first_part.part_id << " max stress: "
                      << std::fixed << std::setprecision(2) << max_stress << " MPa" << std::endl;
        }
    }

    // ========================================
    // Test 2: Element-level parallel (LEGACY)
    // ========================================
    {
        std::cout << "2. Element-level parallel (LEGACY)..." << std::flush;

        D3plotReader reader2(d3plot_path);
        reader2.open();
        SinglePassAnalyzer analyzer2(reader2);
        analyzer2.setUseStateLevelParallel(false);  // Use element-level (legacy)

        auto start = std::chrono::high_resolution_clock::now();
        auto result2 = analyzer2.analyze(config);
        auto end = std::chrono::high_resolution_clock::now();

        auto duration2 = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
        std::cout << " " << duration2 << " ms" << std::endl;

        // Show sample results
        if (!result2.stress_history.empty() && !result2.stress_history[0].data.empty()) {
            auto& first_part = result2.stress_history[0];
            double max_stress = 0;
            for (const auto& tp : first_part.data) {
                if (tp.max_value > max_stress) max_stress = tp.max_value;
            }
            std::cout << "   Part " << first_part.part_id << " max stress: "
                      << std::fixed << std::setprecision(2) << max_stress << " MPa" << std::endl;
        }
    }

    // ========================================
    // Test 3: Direct API calls
    // ========================================
    {
        std::cout << "\n3. Direct API comparison:" << std::endl;

        D3plotReader reader3(d3plot_path);
        reader3.open();
        SinglePassAnalyzer analyzer3(reader3);

        // analyzeParallel (state-level)
        auto start1 = std::chrono::high_resolution_clock::now();
        D3plotReader r3a(d3plot_path);
        r3a.open();
        SinglePassAnalyzer a3a(r3a);
        auto result3a = a3a.analyzeParallel(config);
        auto end1 = std::chrono::high_resolution_clock::now();
        auto dur1 = std::chrono::duration_cast<std::chrono::milliseconds>(end1 - start1).count();

        // analyzeLegacy (element-level)
        auto start2 = std::chrono::high_resolution_clock::now();
        D3plotReader r3b(d3plot_path);
        r3b.open();
        SinglePassAnalyzer a3b(r3b);
        auto result3b = a3b.analyzeLegacy(config);
        auto end2 = std::chrono::high_resolution_clock::now();
        auto dur2 = std::chrono::duration_cast<std::chrono::milliseconds>(end2 - start2).count();

        std::cout << "   analyzeParallel(): " << dur1 << " ms" << std::endl;
        std::cout << "   analyzeLegacy():   " << dur2 << " ms" << std::endl;
        std::cout << "   Speedup: " << std::fixed << std::setprecision(2)
                  << (double)dur2 / dur1 << "x" << std::endl;
    }

    std::cout << "\n=== Benchmark Complete ===" << std::endl;

    return 0;
}
