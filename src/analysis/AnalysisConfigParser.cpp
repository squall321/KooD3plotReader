/**
 * @file AnalysisConfigParser.cpp
 * @brief YAML configuration parser implementation
 */

#include "kood3plot/analysis/AnalysisConfigParser.hpp"
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cctype>
#include <iostream>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace kood3plot {
namespace analysis {

std::string AnalysisConfigParser::last_error_;

std::string AnalysisConfigParser::trim(const std::string& str) {
    size_t start = 0;
    while (start < str.size() && std::isspace(str[start])) ++start;
    size_t end = str.size();
    while (end > start && std::isspace(str[end - 1])) --end;
    return str.substr(start, end - start);
}

std::vector<double> AnalysisConfigParser::parseDoubleArray(const std::string& str) {
    std::vector<double> result;
    std::string s = str;

    // Remove brackets
    size_t start = s.find('[');
    size_t end = s.find(']');
    if (start != std::string::npos && end != std::string::npos) {
        s = s.substr(start + 1, end - start - 1);
    }

    std::istringstream iss(s);
    std::string token;
    while (std::getline(iss, token, ',')) {
        try {
            result.push_back(std::stod(trim(token)));
        } catch (...) {}
    }

    return result;
}

std::vector<int32_t> AnalysisConfigParser::parseIntArray(const std::string& str) {
    std::vector<int32_t> result;
    std::string s = str;

    // Remove brackets
    size_t start = s.find('[');
    size_t end = s.find(']');
    if (start != std::string::npos && end != std::string::npos) {
        s = s.substr(start + 1, end - start - 1);
    }

    std::istringstream iss(s);
    std::string token;
    while (std::getline(iss, token, ',')) {
        try {
            result.push_back(std::stoi(trim(token)));
        } catch (...) {}
    }

    return result;
}

bool AnalysisConfigParser::loadFromYAML(const std::string& file_path, ExtendedAnalysisConfig& config) {
    std::ifstream ifs(file_path);
    if (!ifs.is_open()) {
        last_error_ = "Cannot open file: " + file_path;
        return false;
    }

    std::ostringstream oss;
    oss << ifs.rdbuf();
    return loadFromYAMLString(oss.str(), config);
}

bool AnalysisConfigParser::loadFromYAMLString(const std::string& yaml_content, ExtendedAnalysisConfig& config) {
    std::istringstream iss(yaml_content);
    std::string line;

    // Reset config
    config = ExtendedAnalysisConfig();

    std::string current_section;
    bool in_surfaces = false;
    SurfaceAnalysisSpec current_surface;
    bool has_current_surface = false;

    auto flush_surface = [&]() {
        if (has_current_surface && !current_surface.description.empty()) {
            config.surface_specs.push_back(current_surface);
        }
        current_surface = SurfaceAnalysisSpec();
        has_current_surface = false;
    };

    while (std::getline(iss, line)) {
        // Skip comments and empty lines
        size_t comment_pos = line.find('#');
        if (comment_pos != std::string::npos) {
            line = line.substr(0, comment_pos);
        }

        std::string trimmed = trim(line);
        if (trimmed.empty()) continue;

        // Count indent
        size_t indent = 0;
        while (indent < line.size() && (line[indent] == ' ' || line[indent] == '\t')) {
            indent++;
        }

        // Check for list item (surface spec)
        bool is_list_item = (trimmed[0] == '-');
        if (is_list_item) {
            trimmed = trim(trimmed.substr(1));
        }

        // Parse key:value
        size_t colon_pos = trimmed.find(':');
        if (colon_pos == std::string::npos) continue;

        std::string key = trim(trimmed.substr(0, colon_pos));
        std::string value = trim(trimmed.substr(colon_pos + 1));

        // Remove quotes from value
        if (!value.empty() && (value[0] == '"' || value[0] == '\'')) {
            char quote = value[0];
            value = value.substr(1);
            size_t end_quote = value.find(quote);
            if (end_quote != std::string::npos) {
                value = value.substr(0, end_quote);
            }
        }

        // Root level sections
        if (indent == 0) {
            if (in_surfaces) {
                flush_surface();
                in_surfaces = false;
            }
            current_section = key;
            if (key == "surfaces") {
                in_surfaces = true;
            }
            continue;
        }

        // Handle surfaces list items
        if (in_surfaces && is_list_item) {
            flush_surface();
            has_current_surface = true;
            if (key == "name") {
                current_surface.description = value;
            }
            continue;
        }

        if (in_surfaces && has_current_surface) {
            if (key == "name") {
                current_surface.description = value;
            } else if (key == "direction") {
                auto vec = parseDoubleArray(value);
                if (vec.size() >= 3) {
                    current_surface.direction = Vec3(vec[0], vec[1], vec[2]);
                }
            } else if (key == "angle") {
                try { current_surface.angle_threshold_degrees = std::stod(value); } catch (...) {}
            } else if (key == "parts") {
                current_surface.part_ids = parseIntArray(value);
            }
            continue;
        }

        // Input section
        if (current_section == "input") {
            if (key == "d3plot") {
                config.d3plot_path = value;
            }
        }
        // Output section
        else if (current_section == "output") {
            if (key == "directory") {
                config.output_directory = value;
            } else if (key == "json") {
                config.output_json = (value == "true" || value == "1" || value == "yes");
            } else if (key == "csv") {
                config.output_csv = (value == "true" || value == "1" || value == "yes");
            }
        }
        // Analysis section
        else if (current_section == "analysis") {
            if (key == "stress") {
                config.analyze_stress = (value == "true" || value == "1" || value == "yes");
            } else if (key == "strain") {
                config.analyze_strain = (value == "true" || value == "1" || value == "yes");
            } else if (key == "parts") {
                config.part_ids = parseIntArray(value);
            }
        }
        // Performance section
        else if (current_section == "performance") {
            if (key == "threads") {
                try { config.num_threads = std::stoi(value); } catch (...) {}
            } else if (key == "verbose") {
                config.verbose = (value == "true" || value == "1" || value == "yes");
            }
        }
    }

    // Flush last surface if any
    if (in_surfaces) {
        flush_surface();
    }

    return true;
}

bool AnalysisConfigParser::saveToYAML(const std::string& file_path, const ExtendedAnalysisConfig& config) {
    std::ofstream ofs(file_path);
    if (!ofs.is_open()) {
        last_error_ = "Cannot open file for writing: " + file_path;
        return false;
    }

    ofs << "# KooD3plot Analysis Configuration\n";
    ofs << "# Generated automatically\n\n";

    // Input section
    ofs << "input:\n";
    ofs << "  d3plot: \"" << config.d3plot_path << "\"\n\n";

    // Output section
    ofs << "output:\n";
    ofs << "  directory: \"" << config.output_directory << "\"\n";
    ofs << "  json: " << (config.output_json ? "true" : "false") << "\n";
    ofs << "  csv: " << (config.output_csv ? "true" : "false") << "\n\n";

    // Analysis section
    ofs << "analysis:\n";
    ofs << "  stress: " << (config.analyze_stress ? "true" : "false") << "\n";
    ofs << "  strain: " << (config.analyze_strain ? "true" : "false") << "\n";
    ofs << "  parts: [";
    for (size_t i = 0; i < config.part_ids.size(); ++i) {
        if (i > 0) ofs << ", ";
        ofs << config.part_ids[i];
    }
    ofs << "]\n\n";

    // Surfaces section
    if (!config.surface_specs.empty()) {
        ofs << "surfaces:\n";
        for (const auto& spec : config.surface_specs) {
            ofs << "  - name: \"" << spec.description << "\"\n";
            ofs << "    direction: [" << spec.direction.x << ", "
                << spec.direction.y << ", " << spec.direction.z << "]\n";
            ofs << "    angle: " << spec.angle_threshold_degrees << "\n";
            if (!spec.part_ids.empty()) {
                ofs << "    parts: [";
                for (size_t i = 0; i < spec.part_ids.size(); ++i) {
                    if (i > 0) ofs << ", ";
                    ofs << spec.part_ids[i];
                }
                ofs << "]\n";
            }
        }
        ofs << "\n";
    }

    // Performance section
    ofs << "performance:\n";
    ofs << "  threads: " << config.num_threads << "  # 0 = auto\n";
    ofs << "  verbose: " << (config.verbose ? "true" : "false") << "\n";

    return true;
}

std::string AnalysisConfigParser::generateExampleYAML() {
    std::ostringstream oss;

    oss << "# ============================================================\n";
    oss << "# KooD3plot Analysis Configuration\n";
    oss << "# ============================================================\n";
    oss << "# This file configures stress/strain and surface analysis.\n";
    oss << "# Can be used with: kood3plot_analyze --config analysis.yaml\n";
    oss << "# ============================================================\n\n";

    oss << "# Input file settings\n";
    oss << "input:\n";
    oss << "  d3plot: \"results/d3plot\"  # Path to d3plot base file\n\n";

    oss << "# Output settings\n";
    oss << "output:\n";
    oss << "  directory: \"./analysis_output\"  # Output directory\n";
    oss << "  json: true   # Export JSON summary\n";
    oss << "  csv: true    # Export CSV time histories\n\n";

    oss << "# Analysis settings\n";
    oss << "analysis:\n";
    oss << "  stress: true   # Von Mises stress analysis\n";
    oss << "  strain: true   # Effective plastic strain analysis\n";
    oss << "  parts: []      # Part IDs to analyze (empty = all)\n";
    oss << "  # parts: [1, 2, 3]  # Example: specific parts only\n\n";

    oss << "# Surface stress analysis\n";
    oss << "# Define surfaces by normal direction and angle threshold\n";
    oss << "surfaces:\n";
    oss << "  - name: \"Bottom surface (-Z)\"\n";
    oss << "    direction: [0, 0, -1]  # Normal direction\n";
    oss << "    angle: 45.0            # Max angle from normal (degrees)\n";
    oss << "    # parts: []            # Optional: specific parts only\n\n";
    oss << "  - name: \"Top surface (+Z)\"\n";
    oss << "    direction: [0, 0, 1]\n";
    oss << "    angle: 45.0\n\n";
    oss << "  - name: \"Front surface (+X)\"\n";
    oss << "    direction: [1, 0, 0]\n";
    oss << "    angle: 45.0\n\n";
    oss << "  - name: \"Back surface (-X)\"\n";
    oss << "    direction: [-1, 0, 0]\n";
    oss << "    angle: 45.0\n\n";

    oss << "# Performance settings\n";
    oss << "performance:\n";
    oss << "  threads: 0     # 0 = auto (use all cores)\n";
    oss << "  verbose: true  # Print progress messages\n";

    return oss.str();
}

const std::string& AnalysisConfigParser::getLastError() {
    return last_error_;
}

} // namespace analysis
} // namespace kood3plot
