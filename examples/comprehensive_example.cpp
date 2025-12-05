/**
 * @file comprehensive_example.cpp
 * @brief Comprehensive CLI for d3plot analysis with YAML configuration
 * @author KooD3plot Development Team
 * @date 2025-12-04
 *
 * This tool uses TimeHistoryAnalyzer (SinglePassAnalyzer) for high-performance
 * analysis (~47x faster than multi-pass approach).
 *
 * Usage:
 *   ./comprehensive_example --config analysis.yaml
 *   ./comprehensive_example --config analysis.yaml --threads 4
 *   ./comprehensive_example --generate-config > my_config.yaml
 *   ./comprehensive_example <d3plot_path> <output_dir>  # Legacy mode
 */

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
#include "kood3plot/analysis/AnalysisResult.hpp"
#include "kood3plot/analysis/AnalysisConfigParser.hpp"
#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <cstring>
#include <filesystem>
#include <iomanip>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace fs = std::filesystem;
using namespace kood3plot;
using namespace kood3plot::analysis;

/**
 * @brief Write part time series to CSV
 */
void write_part_csv(const std::string& filepath, const PartTimeSeriesStats& stats) {
    std::ofstream ofs(filepath);
    if (!ofs) {
        std::cerr << "Failed to open " << filepath << "\n";
        return;
    }

    ofs << "Time,Max_" << stats.quantity << ",Min_" << stats.quantity
        << ",Avg_" << stats.quantity << ",Max_Element_ID,Min_Element_ID\n";

    for (const auto& point : stats.data) {
        ofs << std::fixed << std::setprecision(6)
            << point.time << ","
            << point.max_value << ","
            << point.min_value << ","
            << point.avg_value << ","
            << point.max_element_id << ","
            << point.min_element_id << "\n";
    }

    ofs.close();
    std::cout << "  Written: " << filepath << " (" << stats.data.size() << " states)\n";
}

/**
 * @brief Write surface analysis to CSV
 */
void write_surface_csv(const std::string& filepath, const SurfaceAnalysisStats& stats) {
    std::ofstream ofs(filepath);
    if (!ofs) {
        std::cerr << "Failed to open " << filepath << "\n";
        return;
    }

    ofs << "Time,Normal_Max,Normal_Min,Normal_Avg,Normal_Max_ElemID,"
        << "Shear_Max,Shear_Avg,Shear_Max_ElemID\n";

    for (const auto& point : stats.data) {
        ofs << std::fixed << std::setprecision(6)
            << point.time << ","
            << point.normal_stress_max << ","
            << point.normal_stress_min << ","
            << point.normal_stress_avg << ","
            << point.normal_stress_max_element_id << ","
            << point.shear_stress_max << ","
            << point.shear_stress_avg << ","
            << point.shear_stress_max_element_id << "\n";
    }

    ofs.close();
    std::cout << "  Written: " << filepath << " (" << stats.data.size() << " states)\n";
}

/**
 * @brief Export results to files
 */
void export_results(const AnalysisResult& result, const ExtendedAnalysisConfig& config) {
    std::string output_dir = config.output_directory;
    if (output_dir.empty()) {
        output_dir = "./analysis_output";
    }

    // Create subdirectories
    std::string stress_dir = output_dir + "/stress";
    std::string strain_dir = output_dir + "/strain";
    std::string surface_dir = output_dir + "/surface";

    fs::create_directories(stress_dir);
    fs::create_directories(strain_dir);
    fs::create_directories(surface_dir);

    // Export stress history
    if (config.output_csv && !result.stress_history.empty()) {
        std::cout << "Exporting stress history:\n";
        for (const auto& stats : result.stress_history) {
            std::string filename = stress_dir + "/part_" + std::to_string(stats.part_id) + "_von_mises.csv";
            write_part_csv(filename, stats);
        }
        std::cout << "\n";
    }

    // Export strain history
    if (config.output_csv && !result.strain_history.empty()) {
        std::cout << "Exporting strain history:\n";
        for (const auto& stats : result.strain_history) {
            std::string filename = strain_dir + "/part_" + std::to_string(stats.part_id) + "_eff_plastic_strain.csv";
            write_part_csv(filename, stats);
        }
        std::cout << "\n";
    }

    // Export surface stress history
    if (config.output_csv && !result.surface_analysis.empty()) {
        std::cout << "Exporting surface stress history:\n";
        for (const auto& stats : result.surface_analysis) {
            std::string safe_name = stats.description;
            for (char& c : safe_name) {
                if (c == ' ' || c == '/' || c == '\\' || c == '(' || c == ')') c = '_';
            }
            std::string filename = surface_dir + "/" + safe_name + ".csv";
            write_surface_csv(filename, stats);
        }
        std::cout << "\n";
    }

    // Export JSON summary
    if (config.output_json) {
        std::string json_path = output_dir + "/analysis_result.json";
        if (result.saveToFile(json_path)) {
            std::cout << "JSON summary: " << json_path << "\n\n";
        }
    }
}

/**
 * @brief Print usage
 */
void print_usage(const char* prog_name) {
    std::cout << "=============================================================\n";
    std::cout << "KooD3plot Comprehensive Analysis Tool (SinglePassAnalyzer)\n";
    std::cout << "=============================================================\n\n";

    std::cout << "Usage:\n";
    std::cout << "  " << prog_name << " --config <yaml_file> [--threads N]\n";
    std::cout << "  " << prog_name << " --generate-config\n";
    std::cout << "  " << prog_name << " <d3plot_path> <output_dir>  # Legacy mode\n\n";

    std::cout << "Options:\n";
    std::cout << "  --config <file>     Load configuration from YAML file\n";
    std::cout << "  --threads N         Set number of OpenMP threads (0=auto)\n";
    std::cout << "  --generate-config   Print example YAML configuration\n";
    std::cout << "  --help              Show this help message\n\n";

    std::cout << "Features:\n";
    std::cout << "  - Single-pass analysis (~47x faster than multi-pass)\n";
    std::cout << "  - OpenMP parallel processing\n";
    std::cout << "  - Part-wise stress/strain time history\n";
    std::cout << "  - Direction-based surface stress analysis\n";
    std::cout << "  - CSV and JSON output\n\n";

    std::cout << "Examples:\n";
    std::cout << "  # Generate example config and run\n";
    std::cout << "  " << prog_name << " --generate-config > my_analysis.yaml\n";
    std::cout << "  " << prog_name << " --config my_analysis.yaml\n\n";

    std::cout << "  # Quick analysis with default surfaces\n";
    std::cout << "  " << prog_name << " results/d3plot ./output\n";
}

/**
 * @brief Print summary
 */
void print_summary(const AnalysisResult& result, const ExtendedAnalysisConfig& config) {
    std::cout << "=============================================================\n";
    std::cout << "Analysis Complete!\n";
    std::cout << "=============================================================\n";
    std::cout << "Metadata:\n";
    std::cout << "  States analyzed: " << result.metadata.num_states << "\n";
    std::cout << "  Time range: " << result.metadata.start_time << " to "
              << result.metadata.end_time << "\n";
    std::cout << "  Parts analyzed: " << result.metadata.analyzed_parts.size() << "\n\n";

    std::cout << "Results saved to: " << config.output_directory << "\n";
    std::cout << "  - Stress history: " << result.stress_history.size() << " parts\n";
    std::cout << "  - Strain history: " << result.strain_history.size() << " parts\n";
    std::cout << "  - Surface stress: " << result.surface_analysis.size() << " surfaces\n\n";

    // Print peak stress values
    if (!result.stress_history.empty()) {
        std::cout << "Peak Stress Values:\n";
        for (const auto& stats : result.stress_history) {
            double global_max = -std::numeric_limits<double>::max();
            double time_at_max = 0;
            for (const auto& point : stats.data) {
                if (point.max_value > global_max) {
                    global_max = point.max_value;
                    time_at_max = point.time;
                }
            }
            std::cout << "  Part " << std::setw(3) << stats.part_id << ": "
                      << std::fixed << std::setprecision(2) << std::setw(10) << global_max
                      << " MPa at t=" << std::setprecision(6) << time_at_max << "\n";
        }
    }

    std::cout << "=============================================================\n";
}

int main(int argc, char* argv[]) {
    // Parse command line arguments
    std::string config_file;
    std::string d3plot_path;
    std::string output_dir;
    int num_threads = 0;
    bool generate_config = false;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];

        if (arg == "--help" || arg == "-h") {
            print_usage(argv[0]);
            return 0;
        }
        else if (arg == "--generate-config") {
            generate_config = true;
        }
        else if (arg == "--config" && i + 1 < argc) {
            config_file = argv[++i];
        }
        else if (arg == "--threads" && i + 1 < argc) {
            try {
                num_threads = std::stoi(argv[++i]);
            } catch (...) {
                std::cerr << "Invalid thread count\n";
                return 1;
            }
        }
        else if (d3plot_path.empty()) {
            d3plot_path = arg;
        }
        else if (output_dir.empty()) {
            output_dir = arg;
        }
    }

    // Handle --generate-config
    if (generate_config) {
        std::cout << AnalysisConfigParser::generateExampleYAML();
        return 0;
    }

    // Load configuration
    ExtendedAnalysisConfig config;

    if (!config_file.empty()) {
        // Load from YAML
        std::cout << "Loading configuration from: " << config_file << "\n";
        if (!AnalysisConfigParser::loadFromYAML(config_file, config)) {
            std::cerr << "Failed to load config: " << AnalysisConfigParser::getLastError() << "\n";
            return 1;
        }
    }
    else if (!d3plot_path.empty() && !output_dir.empty()) {
        // Legacy mode: d3plot_path output_dir
        config.d3plot_path = d3plot_path;
        config.output_directory = output_dir;
        config.analyze_stress = true;
        config.analyze_strain = true;
        config.output_json = true;
        config.output_csv = true;
        config.verbose = true;

        // Add default surfaces
        config.addSurfaceAnalysis("Bottom surface (-Z)", Vec3(0, 0, -1), 45.0);
        config.addSurfaceAnalysis("Top surface (+Z)", Vec3(0, 0, 1), 45.0);
        config.addSurfaceAnalysis("Front surface (+X)", Vec3(1, 0, 0), 45.0);
        config.addSurfaceAnalysis("Back surface (-X)", Vec3(-1, 0, 0), 45.0);
    }
    else {
        print_usage(argv[0]);
        return 1;
    }

    // Override threads if specified on command line
    if (num_threads > 0) {
        config.num_threads = num_threads;
    }

    // Set OpenMP threads
#ifdef _OPENMP
    if (config.num_threads > 0) {
        omp_set_num_threads(config.num_threads);
        std::cout << "Using " << config.num_threads << " threads\n";
    } else {
        std::cout << "Using " << omp_get_max_threads() << " threads (auto)\n";
    }
#endif

    // Create output directory
    try {
        fs::create_directories(config.output_directory);
    } catch (const std::exception& e) {
        std::cerr << "Failed to create output directory: " << e.what() << "\n";
        return 1;
    }

    std::cout << "\n";
    std::cout << "=============================================================\n";
    std::cout << "KooD3plot Analysis (SinglePassAnalyzer)\n";
    std::cout << "=============================================================\n";
    std::cout << "Input: " << config.d3plot_path << "\n";
    std::cout << "Output: " << config.output_directory << "\n";
    std::cout << "Stress: " << (config.analyze_stress ? "ON" : "OFF") << "\n";
    std::cout << "Strain: " << (config.analyze_strain ? "ON" : "OFF") << "\n";
    std::cout << "Surfaces: " << config.surface_specs.size() << "\n";
    if (!config.part_ids.empty()) {
        std::cout << "Parts: ";
        for (size_t i = 0; i < config.part_ids.size(); ++i) {
            if (i > 0) std::cout << ", ";
            std::cout << config.part_ids[i];
        }
        std::cout << "\n";
    } else {
        std::cout << "Parts: ALL\n";
    }
    std::cout << "=============================================================\n\n";

    // Run analysis
    TimeHistoryAnalyzer analyzer;
    AnalysisResult result = analyzer.analyze(config,
        [](const std::string& phase, size_t current, size_t total,
           const std::string& msg) {
            std::cout << "[" << phase << "] " << msg << "\n";
        }
    );

    if (!analyzer.wasSuccessful()) {
        std::cerr << "Analysis failed: " << analyzer.getLastError() << "\n";
        return 1;
    }

    std::cout << "\n";

    // Export results
    export_results(result, config);

    // Print summary
    print_summary(result, config);

    return 0;
}
