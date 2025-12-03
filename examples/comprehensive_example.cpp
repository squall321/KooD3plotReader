/**
 * @file comprehensive_example.cpp
 * @brief Comprehensive CLI example for part-wise stress/strain extraction
 * @author KooD3plot Development Team
 * @date 2025-12-02
 *
 * Usage:
 *   ./comprehensive_example <d3plot_path> <output_dir> [--parts part1,part2,...]
 *
 * Example:
 *   ./comprehensive_example /path/to/d3plot ./results --parts 1,2,3
 */

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/PartAnalyzer.hpp"
#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <cstring>
#include <filesystem>
#include <iomanip>

namespace fs = std::filesystem;
using namespace kood3plot;
using namespace kood3plot::analysis;

/**
 * @brief Parse comma-separated part IDs
 */
std::vector<int32_t> parse_part_ids(const std::string& part_str) {
    std::vector<int32_t> part_ids;
    std::stringstream ss(part_str);
    std::string token;

    while (std::getline(ss, token, ',')) {
        try {
            part_ids.push_back(std::stoi(token));
        } catch (...) {
            std::cerr << "Warning: Invalid part ID '" << token << "', skipping\n";
        }
    }

    return part_ids;
}

/**
 * @brief Write part time history to CSV
 */
void write_part_history_csv(const std::string& filepath,
                            const PartTimeHistory& history,
                            const std::string& quantity_name) {
    std::ofstream ofs(filepath);
    if (!ofs) {
        std::cerr << "Failed to open " << filepath << "\n";
        return;
    }

    // Header
    ofs << "Time,Max_" << quantity_name << ",Min_" << quantity_name
        << ",Avg_" << quantity_name << ",Max_Element_ID\n";

    // Data rows
    size_t num_states = history.times.size();
    for (size_t i = 0; i < num_states; ++i) {
        ofs << std::fixed << std::setprecision(6)
            << history.times[i] << ","
            << history.max_values[i] << ","
            << history.min_values[i] << ","
            << history.avg_values[i] << ","
            << history.max_elem_ids[i] << "\n";
    }

    ofs.close();
    std::cout << "  Written: " << filepath << " (" << num_states << " states)\n";
}

/**
 * @brief Print usage
 */
void print_usage(const char* prog_name) {
    std::cout << "Usage:\n";
    std::cout << "  " << prog_name << " <d3plot_path> <output_dir> [--parts part1,part2,...]\n\n";
    std::cout << "Arguments:\n";
    std::cout << "  d3plot_path   Path to d3plot file\n";
    std::cout << "  output_dir    Directory to save CSV results\n";
    std::cout << "  --parts       Optional: Comma-separated part IDs (e.g., 1,2,3)\n";
    std::cout << "                If not specified, all parts will be analyzed\n\n";
    std::cout << "Example:\n";
    std::cout << "  " << prog_name << " /path/to/d3plot ./results --parts 1,2,3\n";
    std::cout << "  " << prog_name << " d3plot ./output\n";
}

int main(int argc, char* argv[]) {
    std::cout << "=============================================================\n";
    std::cout << "KooD3plot Comprehensive Example\n";
    std::cout << "Part-wise Stress/Strain Extraction Tool\n";
    std::cout << "=============================================================\n\n";

    // Parse arguments
    if (argc < 3) {
        print_usage(argv[0]);
        return 1;
    }

    std::string d3plot_path = argv[1];
    std::string output_dir = argv[2];
    std::vector<int32_t> requested_parts;

    // Parse optional --parts argument
    for (int i = 3; i < argc; ++i) {
        if (std::strcmp(argv[i], "--parts") == 0 && i + 1 < argc) {
            requested_parts = parse_part_ids(argv[i + 1]);
            break;
        }
    }

    // Create output directory
    try {
        fs::create_directories(output_dir);
        std::cout << "Output directory: " << output_dir << "\n\n";
    } catch (const std::exception& e) {
        std::cerr << "Failed to create output directory: " << e.what() << "\n";
        return 1;
    }

    // =========================================================
    // Step 1: Open d3plot file
    // =========================================================
    std::cout << "[1/4] Opening d3plot file...\n";
    D3plotReader reader(d3plot_path);

    if (reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Failed to open d3plot file: " << d3plot_path << "\n";
        return 1;
    }

    std::cout << "  File opened successfully\n";
    std::cout << "  Number of states: " << reader.get_num_states() << "\n\n";

    // =========================================================
    // Step 2: Initialize PartAnalyzer
    // =========================================================
    std::cout << "[2/4] Initializing PartAnalyzer...\n";
    PartAnalyzer analyzer(reader);

    if (!analyzer.initialize()) {
        std::cerr << "Failed to initialize PartAnalyzer\n";
        return 1;
    }

    const auto& all_parts = analyzer.get_parts();
    std::cout << "  Found " << all_parts.size() << " parts in model\n";

    // Print part list
    std::cout << "  Parts:\n";
    for (const auto& part : all_parts) {
        std::cout << "    - Part " << part.part_id << ": " << part.name
                  << " (" << part.num_elements << " elements)\n";
    }
    std::cout << "\n";

    // Determine which parts to analyze
    std::vector<int32_t> parts_to_analyze;
    if (requested_parts.empty()) {
        // Analyze all parts
        for (const auto& part : all_parts) {
            parts_to_analyze.push_back(part.part_id);
        }
        std::cout << "  Analyzing ALL parts\n\n";
    } else {
        // Analyze only requested parts
        parts_to_analyze = requested_parts;
        std::cout << "  Analyzing " << parts_to_analyze.size() << " requested parts\n\n";
    }

    // =========================================================
    // Step 3: Extract stress data (Von Mises)
    // =========================================================
    std::cout << "[3/4] Extracting Von Mises stress per part...\n";
    std::string stress_dir = output_dir + "/stress";
    fs::create_directories(stress_dir);

    for (int32_t part_id : parts_to_analyze) {
        std::cout << "  Part " << part_id << "...\n";

        try {
            // Analyze Von Mises stress history
            auto history = analyzer.analyze_part(part_id, StressComponent::VON_MISES);

            // Write to CSV
            std::string filename = stress_dir + "/part_" + std::to_string(part_id) + "_von_mises.csv";
            write_part_history_csv(filename, history, "VonMises");

        } catch (const std::exception& e) {
            std::cerr << "    Error analyzing part " << part_id << ": " << e.what() << "\n";
        }
    }
    std::cout << "\n";

    // =========================================================
    // Step 4: Extract strain data (Effective Plastic Strain)
    // =========================================================
    std::cout << "[4/7] Extracting Effective Plastic Strain per part...\n";
    std::string strain_dir = output_dir + "/strain";
    fs::create_directories(strain_dir);

    for (int32_t part_id : parts_to_analyze) {
        std::cout << "  Part " << part_id << "...\n";

        try {
            // Analyze effective plastic strain history
            auto history = analyzer.analyze_part(part_id, StressComponent::EFF_PLASTIC);

            // Write to CSV
            std::string filename = strain_dir + "/part_" + std::to_string(part_id) + "_eff_plastic_strain.csv";
            write_part_history_csv(filename, history, "EffPlasticStrain");

        } catch (const std::exception& e) {
            std::cerr << "    Error analyzing part " << part_id << ": " << e.what() << "\n";
        }
    }
    std::cout << "\n";

    // =========================================================
    // Step 5: Extract normal stress components (XX, YY, ZZ)
    // =========================================================
    std::cout << "[5/7] Extracting normal stress components per part...\n";
    std::string normal_stress_dir = output_dir + "/normal_stress";
    fs::create_directories(normal_stress_dir);

    for (int32_t part_id : parts_to_analyze) {
        std::cout << "  Part " << part_id << "...\n";

        try {
            // XX component
            auto history_xx = analyzer.analyze_part(part_id, StressComponent::XX);
            std::string filename_xx = normal_stress_dir + "/part_" + std::to_string(part_id) + "_stress_xx.csv";
            write_part_history_csv(filename_xx, history_xx, "StressXX");

            // YY component
            auto history_yy = analyzer.analyze_part(part_id, StressComponent::YY);
            std::string filename_yy = normal_stress_dir + "/part_" + std::to_string(part_id) + "_stress_yy.csv";
            write_part_history_csv(filename_yy, history_yy, "StressYY");

            // ZZ component
            auto history_zz = analyzer.analyze_part(part_id, StressComponent::ZZ);
            std::string filename_zz = normal_stress_dir + "/part_" + std::to_string(part_id) + "_stress_zz.csv";
            write_part_history_csv(filename_zz, history_zz, "StressZZ");

        } catch (const std::exception& e) {
            std::cerr << "    Error analyzing part " << part_id << ": " << e.what() << "\n";
        }
    }
    std::cout << "\n";

    // =========================================================
    // Step 6: Extract shear stress components (XY, YZ, ZX)
    // =========================================================
    std::cout << "[6/7] Extracting shear stress components per part...\n";
    std::string shear_stress_dir = output_dir + "/shear_stress";
    fs::create_directories(shear_stress_dir);

    for (int32_t part_id : parts_to_analyze) {
        std::cout << "  Part " << part_id << "...\n";

        try {
            // XY component
            auto history_xy = analyzer.analyze_part(part_id, StressComponent::XY);
            std::string filename_xy = shear_stress_dir + "/part_" + std::to_string(part_id) + "_stress_xy.csv";
            write_part_history_csv(filename_xy, history_xy, "StressXY");

            // YZ component
            auto history_yz = analyzer.analyze_part(part_id, StressComponent::YZ);
            std::string filename_yz = shear_stress_dir + "/part_" + std::to_string(part_id) + "_stress_yz.csv";
            write_part_history_csv(filename_yz, history_yz, "StressYZ");

            // ZX component
            auto history_zx = analyzer.analyze_part(part_id, StressComponent::ZX);
            std::string filename_zx = shear_stress_dir + "/part_" + std::to_string(part_id) + "_stress_zx.csv";
            write_part_history_csv(filename_zx, history_zx, "StressZX");

        } catch (const std::exception& e) {
            std::cerr << "    Error analyzing part " << part_id << ": " << e.what() << "\n";
        }
    }
    std::cout << "\n";

    // =========================================================
    // Step 7: Extract elastic strain tensor (if ISTRN != 0)
    // =========================================================
    std::cout << "[7/7] Extracting elastic strain tensor per part...\n";

    // Check if strain data is available
    auto control_data = reader.get_control_data();
    if (control_data.ISTRN != 0) {
        std::cout << "  ISTRN = " << control_data.ISTRN << " (strain data available)\n";

        std::string elastic_strain_dir = output_dir + "/elastic_strain";
        fs::create_directories(elastic_strain_dir);

        for (int32_t part_id : parts_to_analyze) {
            std::cout << "  Part " << part_id << "...\n";

            try {
                // XX component
                auto history_exx = analyzer.analyze_part(part_id, StressComponent::STRAIN_XX);
                std::string filename_exx = elastic_strain_dir + "/part_" + std::to_string(part_id) + "_strain_xx.csv";
                write_part_history_csv(filename_exx, history_exx, "StrainXX");

                // YY component
                auto history_eyy = analyzer.analyze_part(part_id, StressComponent::STRAIN_YY);
                std::string filename_eyy = elastic_strain_dir + "/part_" + std::to_string(part_id) + "_strain_yy.csv";
                write_part_history_csv(filename_eyy, history_eyy, "StrainYY");

                // ZZ component
                auto history_ezz = analyzer.analyze_part(part_id, StressComponent::STRAIN_ZZ);
                std::string filename_ezz = elastic_strain_dir + "/part_" + std::to_string(part_id) + "_strain_zz.csv";
                write_part_history_csv(filename_ezz, history_ezz, "StrainZZ");

                // XY component
                auto history_exy = analyzer.analyze_part(part_id, StressComponent::STRAIN_XY);
                std::string filename_exy = elastic_strain_dir + "/part_" + std::to_string(part_id) + "_strain_xy.csv";
                write_part_history_csv(filename_exy, history_exy, "StrainXY");

                // YZ component
                auto history_eyz = analyzer.analyze_part(part_id, StressComponent::STRAIN_YZ);
                std::string filename_eyz = elastic_strain_dir + "/part_" + std::to_string(part_id) + "_strain_yz.csv";
                write_part_history_csv(filename_eyz, history_eyz, "StrainYZ");

                // ZX component
                auto history_ezx = analyzer.analyze_part(part_id, StressComponent::STRAIN_ZX);
                std::string filename_ezx = elastic_strain_dir + "/part_" + std::to_string(part_id) + "_strain_zx.csv";
                write_part_history_csv(filename_ezx, history_ezx, "StrainZX");

            } catch (const std::exception& e) {
                std::cerr << "    Error analyzing part " << part_id << ": " << e.what() << "\n";
            }
        }
    } else {
        std::cout << "  ISTRN = 0 (no strain data in d3plot file)\n";
        std::cout << "  Skipping elastic strain extraction.\n";
    }
    std::cout << "\n";

    // =========================================================
    // Summary
    // =========================================================
    std::cout << "=============================================================\n";
    std::cout << "Analysis Complete!\n";
    std::cout << "=============================================================\n";
    std::cout << "Results saved to: " << output_dir << "\n";
    std::cout << "  - Von Mises stress: " << stress_dir << "/\n";
    std::cout << "  - Effective plastic strain: " << strain_dir << "/\n";
    std::cout << "  - Normal stress (XX, YY, ZZ): " << normal_stress_dir << "/\n";
    std::cout << "  - Shear stress (XY, YZ, ZX): " << shear_stress_dir << "/\n";

    int total_files = parts_to_analyze.size() * 7;
    if (control_data.ISTRN != 0) {
        std::string elastic_strain_dir = output_dir + "/elastic_strain";
        std::cout << "  - Elastic strain (XX, YY, ZZ, XY, YZ, ZX): " << elastic_strain_dir << "/\n";
        total_files += parts_to_analyze.size() * 6;
    }

    std::cout << "  Total parts analyzed: " << parts_to_analyze.size() << "\n";
    std::cout << "  Total files created: " << total_files << "\n";
    std::cout << "=============================================================\n";

    return 0;
}
