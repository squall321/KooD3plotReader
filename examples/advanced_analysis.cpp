/**
 * @file advanced_analysis.cpp
 * @brief Example program for comprehensive d3plot analysis
 * @author KooD3plot Development Team
 * @date 2024-12-04
 *
 * This example demonstrates how to use the TimeHistoryAnalyzer to:
 * 1. Analyze stress and strain history per part
 * 2. Analyze surface stress on direction-filtered exterior faces
 * 3. Output results to JSON and CSV formats
 *
 * Usage:
 *   ./advanced_analysis <d3plot_path> [output_prefix]
 *
 * Example:
 *   ./advanced_analysis results/d3plot analysis_output
 */

#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
#include "kood3plot/D3plotReader.hpp"
#include <iostream>
#include <iomanip>
#include <string>

using namespace kood3plot;
using namespace kood3plot::analysis;

void print_usage(const char* program_name) {
    std::cerr << "Usage: " << program_name << " <d3plot_path> [output_prefix]\n";
    std::cerr << "\n";
    std::cerr << "Arguments:\n";
    std::cerr << "  d3plot_path    Path to the d3plot base file\n";
    std::cerr << "  output_prefix  Prefix for output files (default: 'analysis')\n";
    std::cerr << "\n";
    std::cerr << "Outputs:\n";
    std::cerr << "  <prefix>.json          Complete analysis in JSON format\n";
    std::cerr << "  <prefix>_stress.csv    Stress history per part\n";
    std::cerr << "  <prefix>_strain.csv    Strain history per part\n";
    std::cerr << "  <prefix>_surface.csv   Surface stress history\n";
}

int main(int argc, char* argv[]) {
    // Parse arguments
    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }

    std::string d3plot_path = argv[1];
    std::string output_prefix = (argc >= 3) ? argv[2] : "analysis";

    std::cout << "========================================\n";
    std::cout << "Advanced D3plot Analysis\n";
    std::cout << "========================================\n\n";

    std::cout << "Input: " << d3plot_path << "\n";
    std::cout << "Output prefix: " << output_prefix << "\n\n";

    // Configure analysis
    AnalysisConfig config;
    config.d3plot_path = d3plot_path;

    // Enable stress and strain analysis
    config.analyze_stress = true;
    config.analyze_strain = true;
    config.analyze_acceleration = false;  // Not implemented yet

    // Add surface analyses for multiple directions
    config.addSurfaceAnalysis("Bottom surface (-Z)", Vec3(0, 0, -1), 45.0);
    config.addSurfaceAnalysis("Top surface (+Z)", Vec3(0, 0, 1), 45.0);
    config.addSurfaceAnalysis("Front surface (+X)", Vec3(1, 0, 0), 45.0);
    config.addSurfaceAnalysis("Back surface (-X)", Vec3(-1, 0, 0), 45.0);

    // Set output files
    config.output_json_path = output_prefix + ".json";
    config.output_csv_prefix = output_prefix;
    config.verbose = true;

    // Run analysis with progress callback
    std::cout << "Starting analysis...\n";
    std::cout << "----------------------------------------\n";

    TimeHistoryAnalyzer analyzer;
    AnalysisResult result = analyzer.analyze(config,
        [](const std::string& phase, size_t current, size_t total,
           const std::string& message) {
            if (current == 0 || current == total || current % 10 == 0) {
                std::cout << "[" << phase << "] " << message;
                if (total > 1) {
                    std::cout << " (" << current + 1 << "/" << total << ")";
                }
                std::cout << "\n";
            }
        }
    );

    std::cout << "----------------------------------------\n\n";

    // Check result
    if (!analyzer.wasSuccessful()) {
        std::cerr << "Analysis failed: " << analyzer.getLastError() << "\n";
        return 1;
    }

    // Print summary
    std::cout << "Analysis Summary:\n";
    std::cout << "----------------------------------------\n";
    std::cout << std::fixed << std::setprecision(6);

    std::cout << "Metadata:\n";
    std::cout << "  Version: " << result.metadata.kood3plot_version << "\n";
    std::cout << "  States: " << result.metadata.num_states << "\n";
    std::cout << "  Time range: " << result.metadata.start_time << " to "
              << result.metadata.end_time << "\n";
    std::cout << "  Parts analyzed: " << result.metadata.analyzed_parts.size() << "\n";

    // Stress history summary
    std::cout << "\nStress History:\n";
    for (const auto& part : result.stress_history) {
        std::cout << "  Part " << part.part_id;
        if (!part.part_name.empty()) {
            std::cout << " (" << part.part_name << ")";
        }
        std::cout << ": max=" << part.globalMax()
                  << " at t=" << part.timeOfGlobalMax() << "\n";
    }

    // Strain history summary
    std::cout << "\nStrain History:\n";
    for (const auto& part : result.strain_history) {
        std::cout << "  Part " << part.part_id;
        if (!part.part_name.empty()) {
            std::cout << " (" << part.part_name << ")";
        }
        std::cout << ": max=" << part.globalMax()
                  << " at t=" << part.timeOfGlobalMax() << "\n";
    }

    // Surface analysis summary
    std::cout << "\nSurface Analysis:\n";
    for (const auto& surf : result.surface_analysis) {
        std::cout << "  " << surf.description << ":\n";
        std::cout << "    Faces: " << surf.num_faces << "\n";
        std::cout << "    Direction: (" << surf.reference_direction.x << ", "
                  << surf.reference_direction.y << ", "
                  << surf.reference_direction.z << ")\n";

        if (!surf.data.empty()) {
            // Find global max normal stress
            double max_normal = -1e300;
            double time_of_max = 0;
            for (const auto& tp : surf.data) {
                if (tp.normal_stress_max > max_normal) {
                    max_normal = tp.normal_stress_max;
                    time_of_max = tp.time;
                }
            }
            std::cout << "    Max normal stress: " << max_normal
                      << " at t=" << time_of_max << "\n";
        }
    }

    std::cout << "\nOutput files:\n";
    std::cout << "  JSON: " << config.output_json_path << "\n";
    std::cout << "  CSV files: " << config.output_csv_prefix << "_*.csv\n";
    std::cout << "\n========================================\n";
    std::cout << "Analysis complete!\n";

    return 0;
}
