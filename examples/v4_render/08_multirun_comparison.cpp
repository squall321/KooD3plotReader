/**
 * @file 08_multirun_comparison.cpp
 * @brief Demonstrate multi-run parallel processing and comparison analysis
 *
 * This example shows:
 * - Parallel processing of multiple simulation runs
 * - Progress monitoring
 * - Comparison analysis and reporting
 * - ThreadPool usage for efficient processing
 */

#include <kood3plot/D3plotReader.hpp>
#include <kood3plot/render/MultiRunProcessor.h>
#include <kood3plot/render/RenderConfig.h>
#include <iostream>
#include <filesystem>

using namespace kood3plot;
using namespace kood3plot::render;

int main(int argc, char* argv[]) {
    std::cout << "==============================================\n";
    std::cout << "  KooD3plot V4: Multi-Run Comparison Demo\n";
    std::cout << "==============================================\n\n";

    // Check arguments
    std::string d3plot_path = (argc > 1) ? argv[1] : "results/d3plot";
    std::string lsprepost_path = (argc > 2) ? argv[2] : "installed/lsprepost/lspp412_mesa";

    if (!std::filesystem::exists(d3plot_path)) {
        std::cerr << "ERROR: D3plot file not found: " << d3plot_path << "\n";
        std::cerr << "Usage: " << argv[0] << " [d3plot_path] [lsprepost_path]\n";
        return 1;
    }

    try {
        // ================================================================
        // Example 1: Parallel Processing of Multiple Runs
        // ================================================================
        std::cout << "\n--- Example 1: Parallel Processing (Simulated Multiple Runs) ---\n\n";

        // Create processor with 4 threads
        MultiRunProcessor processor(lsprepost_path, 4);

        // Configure options
        ProcessorOptions opts;
        opts.enable_parallel = true;
        opts.max_threads = 4;
        opts.verbose = true;
        processor.setOptions(opts);

        // Simulate multiple runs with different configurations
        // In a real scenario, these would be different simulation runs
        std::vector<std::string> run_names = {
            "baseline",
            "variant_A",
            "variant_B",
            "variant_C"
        };

        std::vector<std::string> fringe_types = {
            "von_mises",
            "displacement",
            "effective_strain",
            "pressure"
        };

        for (size_t i = 0; i < run_names.size(); ++i) {
            RunData run;
            run.run_id = run_names[i];
            run.d3plot_path = d3plot_path;  // Same d3plot for demo
            run.output_dir = "multirun_output/" + run_names[i];

            // Configure rendering for this run
            RenderConfigData data;
            data.analysis.data_path = d3plot_path;
            data.fringe.type = fringe_types[i];
            data.fringe.auto_range = true;
            data.output.movie = true;
            data.output.width = 1280;
            data.output.height = 720;
            data.view.orientation = "iso";

            // Add a center section
            SectionConfig section;
            section.auto_mode = AutoSectionMode::SINGLE;
            section.auto_params.orientation = "Z";
            section.auto_params.position = "center";
            data.sections.push_back(section);

            run.config.setData(data);
            processor.addRun(std::move(run));
        }

        std::cout << "Added " << processor.getRunCount() << " runs for processing\n\n";

        // Set up progress callback
        auto progress_callback = [](const MultiRunProgressStatus& status) {
            // This gets called when progress updates
            // You can use this for custom progress reporting
        };

        processor.setProgressCallback(progress_callback);

        // Process all runs in parallel
        processor.processInParallel(progress_callback);

        // ================================================================
        // Example 2: Check Results
        // ================================================================
        std::cout << "\n--- Example 2: Results Summary ---\n\n";

        auto results = processor.getResults();

        std::cout << "Completed runs: " << results.size() << "\n\n";

        for (const auto& pair : results) {
            const std::string& run_id = pair.first;
            const RunResult& result = pair.second;

            std::cout << "Run: " << run_id << "\n";
            std::cout << "  Status: " << (result.success ? "SUCCESS" : "FAILED") << "\n";
            std::cout << "  Time: " << std::fixed << std::setprecision(2)
                      << result.processing_time_sec << " seconds\n";

            if (!result.success) {
                std::cout << "  Error: " << result.error_message << "\n";
            } else {
                std::cout << "  Files generated: " << result.generated_files.size() << "\n";
                for (const auto& file : result.generated_files) {
                    std::cout << "    - " << file << "\n";
                }
            }
            std::cout << "\n";
        }

        // ================================================================
        // Example 3: Error Handling
        // ================================================================
        std::cout << "\n--- Example 3: Error Handling ---\n\n";

        if (processor.hasErrors()) {
            std::cout << "Some runs failed. Error details:\n\n";

            auto errors = processor.getErrors();
            for (const auto& pair : errors) {
                std::cout << "Run: " << pair.first << "\n";
                std::cout << "  Error: " << pair.second << "\n\n";
            }
        } else {
            std::cout << "All runs completed successfully!\n";
        }

        // ================================================================
        // Example 4: Generate Comparison Report
        // ================================================================
        std::cout << "\n--- Example 4: Comparison Analysis ---\n\n";

        auto comparisons = processor.generateComparisons();
        std::cout << "Generated " << comparisons.size() << " comparison(s)\n\n";

        for (const auto& comp : comparisons) {
            std::cout << "Section: " << comp.section_label << "\n";
            std::cout << "  Runs compared: " << comp.results.size() << "\n";
            std::cout << "  Run IDs: ";
            for (const auto& r : comp.results) {
                std::cout << r.first << " ";
            }
            std::cout << "\n\n";
        }

        // Save comparison report
        std::string report_file = "multirun_output/comparison_report.txt";
        processor.saveComparisonReport(report_file);
        std::cout << "Saved comparison report to: " << report_file << "\n\n";

        // Save results to CSV
        std::string csv_file = "multirun_output/results.csv";
        processor.saveResultsCSV(csv_file);
        std::cout << "Saved results to CSV: " << csv_file << "\n\n";

        // ================================================================
        // Example 5: Sequential Processing (for comparison)
        // ================================================================
        std::cout << "\n--- Example 5: Sequential vs Parallel Performance ---\n\n";

        MultiRunProcessor seq_processor(lsprepost_path, 1);
        seq_processor.setOptions(opts);

        // Add a couple of runs for timing comparison
        for (int i = 0; i < 2; ++i) {
            RunData run;
            run.run_id = "seq_test_" + std::to_string(i);
            run.d3plot_path = d3plot_path;
            run.output_dir = "multirun_output/seq_test_" + std::to_string(i);

            RenderConfigData data;
            data.analysis.data_path = d3plot_path;
            data.fringe.type = "von_mises";
            data.output.movie = true;
            data.view.orientation = "iso";

            SectionConfig section;
            section.auto_mode = AutoSectionMode::SINGLE;
            section.auto_params.orientation = "Z";
            section.auto_params.position = "center";
            data.sections.push_back(section);

            run.config.setData(data);
            seq_processor.addRun(std::move(run));
        }

        std::cout << "Processing 2 runs sequentially for timing...\n";
        seq_processor.processSequentially();

        std::cout << "\nNOTE: Parallel processing provides significant speedup\n";
        std::cout << "      when processing many runs simultaneously!\n";

        // ================================================================
        // Summary
        // ================================================================
        std::cout << "\n==============================================\n";
        std::cout << "  Summary\n";
        std::cout << "==============================================\n\n";

        std::cout << "Key Features Demonstrated:\n";
        std::cout << "  ✓ ThreadPool-based parallel processing\n";
        std::cout << "  ✓ Real-time progress monitoring\n";
        std::cout << "  ✓ Error handling and recovery\n";
        std::cout << "  ✓ Comparison analysis across runs\n";
        std::cout << "  ✓ Report generation (TXT, CSV)\n\n";

        std::cout << "Generated Files:\n";
        std::cout << "  - multirun_output/[run_id]/section_*.mp4  : Rendered animations\n";
        std::cout << "  - multirun_output/comparison_report.txt   : Comparison report\n";
        std::cout << "  - multirun_output/results.csv             : Results summary\n\n";

        std::cout << "Use Cases:\n";
        std::cout << "  1. Design optimization (compare design variants)\n";
        std::cout << "  2. Parameter studies (vary material properties)\n";
        std::cout << "  3. Validation (compare against experiments)\n";
        std::cout << "  4. Uncertainty quantification (multiple samples)\n\n";

    } catch (const std::exception& e) {
        std::cerr << "ERROR: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
