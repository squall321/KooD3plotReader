/**
 * @file unified_analyzer.cpp
 * @brief Unified CLI for d3plot analysis with YAML configuration
 * @author KooD3plot Development Team
 * @date 2025-12-04
 *
 * This tool uses UnifiedAnalyzer with job-based YAML configuration.
 *
 * Usage:
 *   ./unified_analyzer --config analysis.yaml
 *   ./unified_analyzer --config analysis.yaml --threads 4
 *   ./unified_analyzer --config analysis.yaml --analysis-only
 *   ./unified_analyzer --generate-config > my_config.yaml
 */

#include "kood3plot/analysis/UnifiedAnalyzer.hpp"
#include "kood3plot/analysis/UnifiedConfigParser.hpp"
#include <iostream>
#include <fstream>
#include <filesystem>
#include <iomanip>
#include <chrono>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace fs = std::filesystem;
using namespace kood3plot;
using namespace kood3plot::analysis;

/**
 * @brief Write part time series to CSV
 */
void writePartCSV(const std::string& filepath, const PartTimeSeriesStats& stats) {
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
 * @brief Write motion analysis to CSV
 */
void writeMotionCSV(const std::string& filepath, const PartMotionStats& stats) {
    std::ofstream ofs(filepath);
    if (!ofs) {
        std::cerr << "Failed to open " << filepath << "\n";
        return;
    }

    ofs << "Time,Avg_Disp_X,Avg_Disp_Y,Avg_Disp_Z,Avg_Disp_Mag,"
        << "Avg_Vel_X,Avg_Vel_Y,Avg_Vel_Z,Avg_Vel_Mag,"
        << "Avg_Acc_X,Avg_Acc_Y,Avg_Acc_Z,Avg_Acc_Mag,"
        << "Max_Disp_Mag,Max_Disp_Node_ID\n";

    for (const auto& point : stats.data) {
        ofs << std::fixed << std::setprecision(6)
            << point.time << ","
            << point.avg_displacement.x << ","
            << point.avg_displacement.y << ","
            << point.avg_displacement.z << ","
            << point.avg_displacement_magnitude << ","
            << point.avg_velocity.x << ","
            << point.avg_velocity.y << ","
            << point.avg_velocity.z << ","
            << point.avg_velocity_magnitude << ","
            << point.avg_acceleration.x << ","
            << point.avg_acceleration.y << ","
            << point.avg_acceleration.z << ","
            << point.avg_acceleration_magnitude << ","
            << point.max_displacement_magnitude << ","
            << point.max_displacement_node_id << "\n";
    }

    ofs.close();
    std::cout << "  Written: " << filepath << " (" << stats.data.size() << " states)\n";
}

/**
 * @brief Write surface analysis to CSV
 */
void writeSurfaceCSV(const std::string& filepath, const SurfaceAnalysisStats& stats) {
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
 * @brief Write surface strain to CSV
 */
void writeSurfaceStrainCSV(const std::string& filepath, const SurfaceStrainStats& stats) {
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
            << point.normal_strain_max << ","
            << point.normal_strain_min << ","
            << point.normal_strain_avg << ","
            << point.normal_strain_max_element_id << ","
            << point.shear_strain_max << ","
            << point.shear_strain_avg << ","
            << point.shear_strain_max_element_id << "\n";
    }

    ofs.close();
    std::cout << "  Written: " << filepath << " (" << stats.data.size() << " states)\n";
}

/**
 * @brief Export results to files
 */
void exportResults(const ExtendedAnalysisResult& result, const UnifiedConfig& config) {
    std::string output_dir = config.output_directory;
    if (output_dir.empty()) {
        output_dir = "./analysis_output";
    }

    // Create subdirectories
    std::string stress_dir = output_dir + "/stress";
    std::string strain_dir = output_dir + "/strain";
    std::string motion_dir = output_dir + "/motion";
    std::string surface_dir = output_dir + "/surface";

    fs::create_directories(stress_dir);
    fs::create_directories(strain_dir);
    fs::create_directories(motion_dir);
    fs::create_directories(surface_dir);

    // Export stress history
    if (config.output_csv && !result.stress_history.empty()) {
        std::cout << "\nExporting stress history:\n";
        for (const auto& stats : result.stress_history) {
            std::string filename = stress_dir + "/part_" + std::to_string(stats.part_id) + "_von_mises.csv";
            writePartCSV(filename, stats);
        }
    }

    // Export strain history
    if (config.output_csv && !result.strain_history.empty()) {
        std::cout << "\nExporting strain history:\n";
        for (const auto& stats : result.strain_history) {
            std::string filename = strain_dir + "/part_" + std::to_string(stats.part_id) + "_eff_plastic_strain.csv";
            writePartCSV(filename, stats);
        }
    }

    // Export motion analysis
    if (config.output_csv && !result.motion_analysis.empty()) {
        std::cout << "\nExporting motion analysis:\n";
        for (const auto& stats : result.motion_analysis) {
            std::string filename = motion_dir + "/part_" + std::to_string(stats.part_id) + "_motion.csv";
            writeMotionCSV(filename, stats);
        }
    }

    // Export surface stress
    if (config.output_csv && !result.surface_analysis.empty()) {
        std::cout << "\nExporting surface stress:\n";
        for (const auto& stats : result.surface_analysis) {
            std::string safe_name = stats.description;
            for (char& c : safe_name) {
                if (c == ' ' || c == '/' || c == '\\' || c == '(' || c == ')') c = '_';
            }
            std::string filename = surface_dir + "/" + safe_name + "_stress.csv";
            writeSurfaceCSV(filename, stats);
        }
    }

    // Export surface strain
    if (config.output_csv && !result.surface_strain_analysis.empty()) {
        std::cout << "\nExporting surface strain:\n";
        for (const auto& stats : result.surface_strain_analysis) {
            std::string safe_name = stats.description;
            for (char& c : safe_name) {
                if (c == ' ' || c == '/' || c == '\\' || c == '(' || c == ')') c = '_';
            }
            std::string filename = surface_dir + "/" + safe_name + "_strain.csv";
            writeSurfaceStrainCSV(filename, stats);
        }
    }

    // Export JSON summary
    if (config.output_json) {
        std::string json_path = output_dir + "/analysis_result.json";
        if (result.saveToFile(json_path)) {
            std::cout << "\nJSON summary: " << json_path << "\n";
        }
    }
}

/**
 * @brief Print usage
 */
void printUsage(const char* prog_name) {
    std::cout << "=============================================================\n";
    std::cout << "KooD3plot Unified Analyzer (v2.0)\n";
    std::cout << "=============================================================\n\n";

    std::cout << "Usage:\n";
    std::cout << "  " << prog_name << " --config <yaml_file> [options]\n";
    std::cout << "  " << prog_name << " --generate-config\n\n";

    std::cout << "Options:\n";
    std::cout << "  --config <file>     Load configuration from YAML file\n";
    std::cout << "  --threads N         Set number of OpenMP threads (0=auto)\n";
    std::cout << "  --analysis-only     Run only analysis jobs (skip rendering)\n";
    std::cout << "  --render-only       Run only render jobs (skip analysis)\n";
    std::cout << "  --generate-config   Print example YAML configuration\n";
    std::cout << "  --help              Show this help message\n\n";

    std::cout << "Features:\n";
    std::cout << "  - Job-based analysis configuration\n";
    std::cout << "  - Von Mises stress, effective plastic strain\n";
    std::cout << "  - Motion analysis (displacement, velocity, acceleration)\n";
    std::cout << "  - Surface stress and strain analysis\n";
    std::cout << "  - Section view rendering (with LSPrePost)\n";
    std::cout << "  - CSV and JSON output\n\n";

    std::cout << "Examples:\n";
    std::cout << "  # Generate example config and run\n";
    std::cout << "  " << prog_name << " --generate-config > my_analysis.yaml\n";
    std::cout << "  " << prog_name << " --config my_analysis.yaml\n\n";

    std::cout << "  # Analysis only (no rendering)\n";
    std::cout << "  " << prog_name << " --config full_workflow.yaml --analysis-only\n";
}

/**
 * @brief Print summary
 */
void printSummary(const ExtendedAnalysisResult& result, const UnifiedConfig& config, double elapsed_seconds) {
    std::cout << "\n=============================================================\n";
    std::cout << "Analysis Complete!\n";
    std::cout << "=============================================================\n";
    std::cout << "Metadata:\n";
    std::cout << "  States analyzed: " << result.metadata.num_states << "\n";
    std::cout << "  Time range: " << result.metadata.start_time << " to "
              << result.metadata.end_time << "\n";
    std::cout << "  Parts analyzed: " << result.metadata.analyzed_parts.size() << "\n";
    std::cout << "  Elapsed time: " << std::fixed << std::setprecision(2) << elapsed_seconds << " seconds\n\n";

    std::cout << "Results saved to: " << config.output_directory << "\n";
    std::cout << "  - Stress history: " << result.stress_history.size() << " parts\n";
    std::cout << "  - Strain history: " << result.strain_history.size() << " parts\n";
    std::cout << "  - Motion analysis: " << result.motion_analysis.size() << " parts\n";
    std::cout << "  - Surface stress: " << result.surface_analysis.size() << " surfaces\n";
    std::cout << "  - Surface strain: " << result.surface_strain_analysis.size() << " surfaces\n";
    std::cout << "=============================================================\n";
}

int main(int argc, char* argv[]) {
    // Parse command line arguments
    std::string config_file;
    int num_threads = 0;
    bool generate_config = false;
    bool analysis_only = false;
    bool render_only = false;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];

        if (arg == "--help" || arg == "-h") {
            printUsage(argv[0]);
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
        else if (arg == "--analysis-only") {
            analysis_only = true;
        }
        else if (arg == "--render-only") {
            render_only = true;
        }
    }

    // Handle --generate-config
    if (generate_config) {
        std::cout << UnifiedConfigParser::generateExampleYAML();
        return 0;
    }

    // Require config file
    if (config_file.empty()) {
        printUsage(argv[0]);
        return 1;
    }

    // Load configuration
    UnifiedConfig config;
    std::cout << "Loading configuration from: " << config_file << "\n";
    if (!UnifiedConfigParser::loadFromYAML(config_file, config)) {
        std::cerr << "Failed to load config: " << UnifiedConfigParser::getLastError() << "\n";
        return 1;
    }

    // Validate
    if (!UnifiedConfigParser::validate(config)) {
        std::cerr << "Invalid configuration: " << UnifiedConfigParser::getLastError() << "\n";
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

    // Print configuration
    std::cout << "\n";
    std::cout << "=============================================================\n";
    std::cout << "KooD3plot Unified Analyzer (v2.0)\n";
    std::cout << "=============================================================\n";
    std::cout << "Input: " << config.d3plot_path << "\n";
    std::cout << "Output: " << config.output_directory << "\n";
    std::cout << "Analysis jobs: " << config.analysis_jobs.size() << "\n";
    std::cout << "Render jobs: " << config.render_jobs.size() << "\n";
    std::cout << "=============================================================\n\n";

    // Run analysis
    auto start_time = std::chrono::high_resolution_clock::now();

    if (!render_only && config.hasAnalysisJobs()) {
        UnifiedAnalyzer analyzer;
        ExtendedAnalysisResult result = analyzer.analyze(config,
            [](const std::string& msg) {
                std::cout << msg << "\n";
            }
        );

        if (!analyzer.wasSuccessful()) {
            std::cerr << "Analysis failed: " << analyzer.getLastError() << "\n";
            return 1;
        }

        // Export results
        exportResults(result, config);

        auto end_time = std::chrono::high_resolution_clock::now();
        double elapsed = std::chrono::duration<double>(end_time - start_time).count();

        // Print summary
        printSummary(result, config, elapsed);
    }

    // Run rendering (if V4 Render is available and not analysis_only)
    if (!analysis_only && config.hasRenderJobs()) {
        std::cout << "\n[NOTE] Render jobs require V4 Render with LSPrePost.\n";
        std::cout << "Render jobs defined: " << config.render_jobs.size() << "\n";
        // TODO: Integrate with V4 Render system
    }

    return 0;
}
