/**
 * @file UnifiedConfigParser.cpp
 * @brief Unified YAML configuration parser implementation
 */

#include "kood3plot/analysis/UnifiedConfigParser.hpp"
#include "kood3plot/D3plotReader.hpp"
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cctype>
#include <iostream>
#include <filesystem>
#include <unordered_map>
#include <set>

namespace {

/**
 * @brief Parse part names from LS-DYNA keyword file (*PART section)
 * @param keyword_path Path to keyword file (.k, .key, .dyn)
 * @return Map of part ID to part name
 */
std::unordered_map<int32_t, std::string> parsePartNamesFromKeyword(const std::string& keyword_path) {
    std::unordered_map<int32_t, std::string> part_names;

    std::ifstream ifs(keyword_path);
    if (!ifs.is_open()) {
        return part_names;
    }

    std::string line;
    bool in_part_section = false;
    std::string current_title;
    int line_in_part = 0;

    while (std::getline(ifs, line)) {
        // Skip empty lines and comments
        if (line.empty() || line[0] == '$') continue;

        // Check for *PART keyword
        if (line[0] == '*') {
            std::string upper_line = line;
            std::transform(upper_line.begin(), upper_line.end(), upper_line.begin(), ::toupper);

            if (upper_line.find("*PART") != std::string::npos &&
                upper_line.find("*PART_") == std::string::npos) {
                // Found *PART (not *PART_INERTIA etc.)
                in_part_section = true;
                line_in_part = 0;
                current_title.clear();
                continue;
            } else {
                in_part_section = false;
            }
        }

        if (in_part_section) {
            line_in_part++;

            if (line_in_part == 1) {
                // First line after *PART is the title (heading/name)
                current_title = line;
                // Trim whitespace
                size_t start = current_title.find_first_not_of(" \t\r\n");
                size_t end = current_title.find_last_not_of(" \t\r\n");
                if (start != std::string::npos && end != std::string::npos) {
                    current_title = current_title.substr(start, end - start + 1);
                }
            } else if (line_in_part == 2) {
                // Second line contains: PID, SECID, MID, ...
                // PID is first field (columns 1-10 in fixed format, or first comma-separated)
                try {
                    int32_t pid;
                    if (line.find(',') != std::string::npos) {
                        // Comma-separated format
                        size_t comma = line.find(',');
                        pid = std::stoi(line.substr(0, comma));
                    } else {
                        // Fixed format (columns 1-10)
                        std::string pid_str = line.substr(0, 10);
                        // Trim whitespace
                        size_t start = pid_str.find_first_not_of(" \t");
                        if (start != std::string::npos) {
                            pid = std::stoi(pid_str.substr(start));
                        } else {
                            continue;
                        }
                    }

                    if (!current_title.empty()) {
                        part_names[pid] = current_title;
                    }
                } catch (...) {
                    // Parse error, skip
                }

                in_part_section = false;  // Reset for next *PART
            }
        }
    }

    return part_names;
}

/**
 * @brief Find keyword file next to d3plot
 * @param d3plot_path Path to d3plot file
 * @return Path to keyword file, or empty if not found
 */
std::string findKeywordFile(const std::string& d3plot_path) {
    namespace fs = std::filesystem;

    fs::path d3plot(d3plot_path);
    fs::path dir = d3plot.parent_path();

    // Common keyword file extensions
    std::vector<std::string> extensions = {".k", ".key", ".dyn", ".K", ".KEY", ".DYN"};

    // Try same name with keyword extension
    std::string stem = d3plot.stem().string();
    // Remove d3plot suffix if present
    if (stem.find("d3plot") != std::string::npos) {
        size_t pos = stem.find("d3plot");
        stem = stem.substr(0, pos);
        if (!stem.empty() && (stem.back() == '_' || stem.back() == '-' || stem.back() == '.')) {
            stem.pop_back();
        }
    }

    for (const auto& ext : extensions) {
        // Try with stem
        if (!stem.empty()) {
            fs::path candidate = dir / (stem + ext);
            if (fs::exists(candidate)) {
                return candidate.string();
            }
        }

        // Try main.k, input.k, etc.
        for (const std::string& name : {"main", "input", "model", "keyword"}) {
            fs::path candidate = dir / (name + ext);
            if (fs::exists(candidate)) {
                return candidate.string();
            }
        }
    }

    // Try to find any .k file in the directory
    try {
        for (const auto& entry : fs::directory_iterator(dir)) {
            if (entry.is_regular_file()) {
                std::string ext = entry.path().extension().string();
                std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
                if (ext == ".k" || ext == ".key" || ext == ".dyn") {
                    return entry.path().string();
                }
            }
        }
    } catch (...) {
        // Directory iteration failed
    }

    return "";
}

// Global cache for part names (loaded once per d3plot path)
std::unordered_map<std::string, std::unordered_map<int32_t, std::string>> g_part_name_cache;

} // anonymous namespace

namespace kood3plot {
namespace analysis {

std::string UnifiedConfigParser::last_error_;

std::string UnifiedConfigParser::trim(const std::string& str) {
    size_t start = 0;
    while (start < str.size() && std::isspace(str[start])) ++start;
    size_t end = str.size();
    while (end > start && std::isspace(str[end - 1])) --end;
    return str.substr(start, end - start);
}

std::vector<double> UnifiedConfigParser::parseDoubleArray(const std::string& str) {
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

std::vector<int32_t> UnifiedConfigParser::parseIntArray(const std::string& str) {
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
        std::string trimmed = trim(token);
        if (trimmed.empty()) continue;
        try {
            result.push_back(std::stoi(trimmed));
        } catch (...) {}
    }

    return result;
}

std::vector<std::string> UnifiedConfigParser::parseStringArray(const std::string& str) {
    std::vector<std::string> result;
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
        std::string trimmed = trim(token);
        // Remove quotes
        if (!trimmed.empty() && (trimmed[0] == '"' || trimmed[0] == '\'')) {
            trimmed = trimmed.substr(1);
        }
        if (!trimmed.empty() && (trimmed.back() == '"' || trimmed.back() == '\'')) {
            trimmed.pop_back();
        }
        if (!trimmed.empty()) {
            result.push_back(trimmed);
        }
    }

    return result;
}

bool UnifiedConfigParser::parseBool(const std::string& str) {
    std::string lower = str;
    std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
    return (lower == "true" || lower == "1" || lower == "yes" || lower == "on");
}

bool UnifiedConfigParser::loadFromYAML(const std::string& file_path, UnifiedConfig& config) {
    std::ifstream ifs(file_path);
    if (!ifs.is_open()) {
        last_error_ = "Cannot open file: " + file_path;
        return false;
    }

    std::ostringstream oss;
    oss << ifs.rdbuf();
    return loadFromYAMLString(oss.str(), config);
}

bool UnifiedConfigParser::loadFromYAMLString(const std::string& yaml_content, UnifiedConfig& config) {
    std::istringstream iss(yaml_content);
    std::string line;

    // Reset config
    config = UnifiedConfig();

    // Parse into lines
    std::vector<std::string> lines;
    while (std::getline(iss, line)) {
        // Remove comments
        size_t comment_pos = line.find('#');
        if (comment_pos != std::string::npos) {
            line = line.substr(0, comment_pos);
        }
        lines.push_back(line);
    }

    std::string current_section;
    bool in_analysis_jobs = false;
    bool in_render_jobs = false;
    AnalysisJob current_analysis_job;
    RenderJob current_render_job;
    bool has_current_analysis_job = false;
    bool has_current_render_job = false;

    // Sub-section tracking
    std::string sub_section;  // "surface", "output", "section", "fringe_range"

    auto flush_analysis_job = [&]() {
        if (has_current_analysis_job && !current_analysis_job.name.empty()) {
            config.analysis_jobs.push_back(current_analysis_job);
        }
        current_analysis_job = AnalysisJob();
        has_current_analysis_job = false;
        sub_section.clear();
    };

    auto flush_render_job = [&]() {
        if (has_current_render_job && !current_render_job.name.empty()) {
            config.render_jobs.push_back(current_render_job);
        }
        current_render_job = RenderJob();
        has_current_render_job = false;
        sub_section.clear();
    };

    for (size_t i = 0; i < lines.size(); ++i) {
        const std::string& raw_line = lines[i];
        std::string trimmed = trim(raw_line);
        if (trimmed.empty()) continue;

        // Count indent
        size_t indent = 0;
        while (indent < raw_line.size() && (raw_line[indent] == ' ' || raw_line[indent] == '\t')) {
            indent++;
        }

        // Check for list item
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

        // Root level sections (indent == 0)
        if (indent == 0) {
            if (in_analysis_jobs) flush_analysis_job();
            if (in_render_jobs) flush_render_job();

            in_analysis_jobs = false;
            in_render_jobs = false;
            current_section = key;

            if (key == "analysis_jobs") {
                in_analysis_jobs = true;
            } else if (key == "render_jobs") {
                in_render_jobs = true;
            } else if (key == "version") {
                config.version = value;
            }
            continue;
        }

        // Handle analysis_jobs list items
        if (in_analysis_jobs && is_list_item && indent <= 2) {
            flush_analysis_job();
            has_current_analysis_job = true;
            if (key == "name") {
                current_analysis_job.name = value;
            }
            continue;
        }

        // Handle render_jobs list items
        if (in_render_jobs && is_list_item && indent <= 2) {
            flush_render_job();
            has_current_render_job = true;
            if (key == "name") {
                current_render_job.name = value;
            }
            continue;
        }

        // Parse analysis job properties
        if (in_analysis_jobs && has_current_analysis_job) {
            // Check for sub-sections
            if (value.empty()) {
                sub_section = key;
                continue;
            }

            if (sub_section == "surface") {
                if (key == "direction") {
                    auto vec = parseDoubleArray(value);
                    if (vec.size() >= 3) {
                        current_analysis_job.surface.direction = Vec3(vec[0], vec[1], vec[2]);
                    }
                } else if (key == "angle") {
                    try { current_analysis_job.surface.angle = std::stod(value); } catch (...) {}
                }
            } else {
                // Top-level job properties
                if (key == "name") {
                    current_analysis_job.name = value;
                } else if (key == "type") {
                    current_analysis_job.type = parseJobType(value);
                } else if (key == "parts") {
                    current_analysis_job.part_ids = parseIntArray(value);
                } else if (key == "part_pattern") {
                    current_analysis_job.part_pattern = value;
                } else if (key == "output_prefix") {
                    current_analysis_job.output_prefix = value;
                } else if (key == "quantities") {
                    current_analysis_job.quantities = parseStringArray(value);
                }
            }
            continue;
        }

        // Parse render job properties
        if (in_render_jobs && has_current_render_job) {
            // Reset sub_section when back at job-property indent (≤4, non-list, non-empty value).
            // Sub-section content is at indent 6; job-level properties are at indent 4.
            // Without this, "states:" after "section:" block is silently ignored.
            if (!is_list_item && indent <= 4 && !value.empty() && !sub_section.empty()) {
                sub_section.clear();
            }

            // Check for sub-sections
            if (value.empty()) {
                sub_section = key;
                // Initialize section spec for single section sub-section
                if (key == "section") {
                    current_render_job.sections.clear();
                    current_render_job.sections.push_back(RenderSectionSpec());
                }
                // "sections" (plural) is an array - don't initialize here
                continue;
            }

            // Handle sections array (each item starts with "- axis:")
            if (sub_section == "sections" && is_list_item) {
                // New section item in the array
                current_render_job.sections.push_back(RenderSectionSpec());
                RenderSectionSpec& sec = current_render_job.sections.back();
                if (key == "axis" && !value.empty()) {
                    sec.axis = std::tolower(value[0]);
                }
                continue;
            }

            // Continue parsing current section in sections array
            if (sub_section == "sections" && !current_render_job.sections.empty()) {
                RenderSectionSpec& sec = current_render_job.sections.back();
                if (key == "axis" && !value.empty()) {
                    sec.axis = std::tolower(value[0]);
                } else if (key == "position") {
                    sec = RenderSectionSpec::fromPositionString(sec.axis, value);
                }
                continue;
            }

            if (sub_section == "section") {
                if (current_render_job.sections.empty()) {
                    current_render_job.sections.push_back(RenderSectionSpec());
                }
                RenderSectionSpec& sec = current_render_job.sections.back();
                if (key == "axis") {
                    if (!value.empty()) sec.axis = std::tolower(value[0]);
                } else if (key == "position") {
                    // Use the new fromPositionString helper
                    sec = RenderSectionSpec::fromPositionString(sec.axis, value);
                }
            } else if (sub_section == "fringe_range") {
                if (key == "min") {
                    try { current_render_job.fringe_range.min = std::stod(value); } catch (...) {}
                } else if (key == "max") {
                    try { current_render_job.fringe_range.max = std::stod(value); } catch (...) {}
                }
            } else if (sub_section == "output") {
                if (key == "format") {
                    std::string lower = value;
                    std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
                    if (lower == "mp4") current_render_job.output.format = RenderOutputFormat::MP4;
                    else if (lower == "png") current_render_job.output.format = RenderOutputFormat::PNG;
                    else if (lower == "jpg" || lower == "jpeg") current_render_job.output.format = RenderOutputFormat::JPG;
                    else if (lower == "gif") current_render_job.output.format = RenderOutputFormat::GIF;
                } else if (key == "filename") {
                    current_render_job.output.filename = value;
                } else if (key == "directory") {
                    current_render_job.output.directory = value;
                } else if (key == "filename_pattern") {
                    current_render_job.output.filename_pattern = value;
                } else if (key == "fps") {
                    try { current_render_job.output.fps = std::stoi(value); } catch (...) {}
                } else if (key == "resolution") {
                    auto res = parseIntArray(value);
                    if (res.size() >= 2) {
                        current_render_job.output.resolution = {res[0], res[1]};
                    }
                }
            } else {
                // Top-level render job properties
                if (key == "name") {
                    current_render_job.name = value;
                } else if (key == "type") {
                    std::string lower = value;
                    std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
                    if (lower == "section_view") current_render_job.type = RenderJobType::SECTION_VIEW;
                    else if (lower == "multi_section") current_render_job.type = RenderJobType::MULTI_SECTION;
                    else if (lower == "part_view") current_render_job.type = RenderJobType::PART_VIEW;
                    else if (lower == "full_model") current_render_job.type = RenderJobType::FULL_MODEL;
                } else if (key == "fringe") {
                    current_render_job.fringe_type = value;
                } else if (key == "parts") {
                    current_render_job.parts = parseIntArray(value);
                } else if (key == "part_pattern") {
                    current_render_job.part_pattern = value;
                } else if (key == "states") {
                    if (value == "all") {
                        current_render_job.states.clear();  // empty = all
                    } else {
                        current_render_job.states = parseIntArray(value);
                    }
                } else if (key == "view") {
                    current_render_job.view_str = value;
                }
            }
            continue;
        }

        // Parse input section
        if (current_section == "input") {
            if (key == "d3plot") {
                config.d3plot_path = value;
            }
        }
        // Parse output section
        else if (current_section == "output") {
            if (key == "directory") {
                config.output_directory = value;
            } else if (key == "json") {
                config.output_json = parseBool(value);
            } else if (key == "csv") {
                config.output_csv = parseBool(value);
            }
        }
        // Parse performance section
        else if (current_section == "performance") {
            if (key == "threads") {
                try { config.num_threads = std::stoi(value); } catch (...) {}
            } else if (key == "render_threads") {
                try { config.render_threads = std::stoi(value); } catch (...) {}
            } else if (key == "verbose") {
                config.verbose = parseBool(value);
            } else if (key == "cache_geometry") {
                config.cache_geometry = parseBool(value);
            } else if (key == "lsprepost_path" || key == "lsprepost") {
                config.lsprepost_path = value;
            }
        }
    }

    // Flush remaining jobs
    if (in_analysis_jobs) flush_analysis_job();
    if (in_render_jobs) flush_render_job();

    return true;
}

bool UnifiedConfigParser::saveToYAML(const std::string& file_path, const UnifiedConfig& config) {
    std::ofstream ofs(file_path);
    if (!ofs.is_open()) {
        last_error_ = "Cannot open file for writing: " + file_path;
        return false;
    }

    ofs << "# KooD3plot Unified Configuration\n";
    ofs << "# Generated automatically\n\n";
    ofs << "version: \"" << config.version << "\"\n\n";

    // Input section
    ofs << "input:\n";
    ofs << "  d3plot: \"" << config.d3plot_path << "\"\n\n";

    // Output section
    ofs << "output:\n";
    ofs << "  directory: \"" << config.output_directory << "\"\n";
    ofs << "  json: " << (config.output_json ? "true" : "false") << "\n";
    ofs << "  csv: " << (config.output_csv ? "true" : "false") << "\n\n";

    // Performance section
    ofs << "performance:\n";
    ofs << "  threads: " << config.num_threads << "\n";
    ofs << "  render_threads: " << config.render_threads << "\n";
    ofs << "  verbose: " << (config.verbose ? "true" : "false") << "\n";
    ofs << "  cache_geometry: " << (config.cache_geometry ? "true" : "false") << "\n";
    if (!config.lsprepost_path.empty()) {
        ofs << "  lsprepost_path: \"" << config.lsprepost_path << "\"\n";
    }
    ofs << "\n";

    // Analysis jobs
    if (!config.analysis_jobs.empty()) {
        ofs << "analysis_jobs:\n";
        for (const auto& job : config.analysis_jobs) {
            ofs << "  - name: \"" << job.name << "\"\n";
            ofs << "    type: " << jobTypeToString(job.type) << "\n";
            ofs << "    parts: [";
            for (size_t i = 0; i < job.part_ids.size(); ++i) {
                if (i > 0) ofs << ", ";
                ofs << job.part_ids[i];
            }
            ofs << "]\n";

            if (job.type == AnalysisJobType::SURFACE_STRESS || job.type == AnalysisJobType::SURFACE_STRAIN) {
                ofs << "    surface:\n";
                ofs << "      direction: [" << job.surface.direction.x << ", "
                    << job.surface.direction.y << ", " << job.surface.direction.z << "]\n";
                ofs << "      angle: " << job.surface.angle << "\n";
            }

            if (!job.quantities.empty()) {
                ofs << "    quantities:\n";
                for (const auto& q : job.quantities) {
                    ofs << "      - " << q << "\n";
                }
            }

            ofs << "    output_prefix: \"" << job.output_prefix << "\"\n\n";
        }
    }

    // Render jobs
    if (!config.render_jobs.empty()) {
        ofs << "render_jobs:\n";
        for (const auto& job : config.render_jobs) {
            ofs << "  - name: \"" << job.name << "\"\n";

            std::string type_str;
            switch (job.type) {
                case RenderJobType::SECTION_VIEW: type_str = "section_view"; break;
                case RenderJobType::MULTI_SECTION: type_str = "multi_section"; break;
                case RenderJobType::PART_VIEW: type_str = "part_view"; break;
                case RenderJobType::FULL_MODEL: type_str = "full_model"; break;
                default: type_str = "section_view";
            }
            ofs << "    type: " << type_str << "\n";
            ofs << "    fringe: " << job.fringe_type << "\n";

            if (!job.sections.empty()) {
                ofs << "    section:\n";
                const auto& sec = job.sections[0];
                ofs << "      axis: " << sec.axis << "\n";
                if (!sec.position_auto.empty()) {
                    ofs << "      position: " << sec.position_auto << "\n";
                } else {
                    ofs << "      position: " << sec.position << "\n";
                }
            }

            if (job.states.empty()) {
                ofs << "    states: all\n";
            } else {
                ofs << "    states: [";
                for (size_t i = 0; i < job.states.size(); ++i) {
                    if (i > 0) ofs << ", ";
                    ofs << job.states[i];
                }
                ofs << "]\n";
            }

            ofs << "    output:\n";
            std::string format_str;
            switch (job.output.format) {
                case RenderOutputFormat::MP4: format_str = "mp4"; break;
                case RenderOutputFormat::PNG: format_str = "png"; break;
                case RenderOutputFormat::JPG: format_str = "jpg"; break;
                case RenderOutputFormat::GIF: format_str = "gif"; break;
            }
            ofs << "      format: " << format_str << "\n";
            ofs << "      filename: \"" << job.output.filename << "\"\n";
            ofs << "      fps: " << job.output.fps << "\n";
            ofs << "      resolution: [" << job.output.resolution[0] << ", " << job.output.resolution[1] << "]\n\n";
        }
    }

    return true;
}

std::string UnifiedConfigParser::generateExampleYAML() {
    std::ostringstream oss;

    oss << "# ============================================================\n";
    oss << "# KooD3plot Unified Configuration (v2.0)\n";
    oss << "# ============================================================\n";
    oss << "# This file configures both analysis and rendering jobs.\n";
    oss << "# Run with: ./unified_analyzer --config config.yaml\n";
    oss << "# ============================================================\n\n";

    oss << "version: \"2.0\"\n\n";

    oss << "# Input file settings\n";
    oss << "input:\n";
    oss << "  d3plot: \"results/d3plot\"\n\n";

    oss << "# Output settings\n";
    oss << "output:\n";
    oss << "  directory: \"./analysis_output\"\n";
    oss << "  json: true\n";
    oss << "  csv: true\n\n";

    oss << "# Performance settings\n";
    oss << "performance:\n";
    oss << "  threads: 0           # 0 = auto (use all cores for analysis/read)\n";
    oss << "  render_threads: 1    # Parallel LSPrePost instances (default 1)\n";
    oss << "  verbose: true\n";
    oss << "  cache_geometry: true\n";
    oss << "  # lsprepost_path: \"/path/to/lsprepost\"  # Optional: custom LSPrePost path\n";
    oss << "  # Linux default: {exe_dir}/../lsprepost/lsprepost\n";
    oss << "  # Windows default: {exe_dir}/../lsprepost/lspp412_win64.exe\n\n";

    oss << "# ============================================================\n";
    oss << "# Analysis Jobs (C++ SinglePassAnalyzer)\n";
    oss << "# ============================================================\n";
    oss << "analysis_jobs:\n";
    oss << "  # Von Mises stress analysis\n";
    oss << "  - name: \"All Parts Stress\"\n";
    oss << "    type: von_mises\n";
    oss << "    parts: []  # empty = all parts\n";
    oss << "    output_prefix: \"stress\"\n\n";

    oss << "  # Effective plastic strain\n";
    oss << "  - name: \"Critical Parts Strain\"\n";
    oss << "    type: eff_plastic_strain\n";
    oss << "    parts: [1, 2, 3]\n";
    oss << "    output_prefix: \"strain\"\n\n";

    oss << "  # Motion analysis (velocity/acceleration)\n";
    oss << "  - name: \"Part Motion\"\n";
    oss << "    type: part_motion\n";
    oss << "    parts: [100, 101]\n";
    oss << "    quantities:\n";
    oss << "      - avg_displacement\n";
    oss << "      - avg_velocity\n";
    oss << "      - avg_acceleration\n";
    oss << "    output_prefix: \"motion\"\n\n";

    oss << "  # Surface stress analysis\n";
    oss << "  - name: \"Bottom Surface Stress\"\n";
    oss << "    type: surface_stress\n";
    oss << "    parts: []\n";
    oss << "    surface:\n";
    oss << "      direction: [0, 0, -1]\n";
    oss << "      angle: 45.0\n";
    oss << "    output_prefix: \"bottom_surface\"\n\n";

    oss << "  # Surface strain analysis\n";
    oss << "  - name: \"Top Surface Strain\"\n";
    oss << "    type: surface_strain\n";
    oss << "    parts: []\n";
    oss << "    surface:\n";
    oss << "      direction: [0, 0, 1]\n";
    oss << "      angle: 45.0\n";
    oss << "    output_prefix: \"top_strain\"\n\n";

    oss << "  # Element quality analysis (track mesh degradation over time)\n";
    oss << "  - name: \"Element Quality\"\n";
    oss << "    type: element_quality\n";
    oss << "    parts: []  # empty = all parts\n";
    oss << "    output_prefix: \"quality\"\n\n";

    oss << "  # Comprehensive analysis (multiple quantities)\n";
    oss << "  - name: \"Full Part Analysis\"\n";
    oss << "    type: comprehensive\n";
    oss << "    parts: [10]\n";
    oss << "    quantities:\n";
    oss << "      - von_mises\n";
    oss << "      - eff_plastic_strain\n";
    oss << "      - avg_velocity\n";
    oss << "    output_prefix: \"part10_full\"\n\n";

    oss << "# ============================================================\n";
    oss << "# Render Jobs (LSPrePost Backend)\n";
    oss << "# ============================================================\n";
    oss << "render_jobs:\n";
    oss << "  # Section view animation\n";
    oss << "  - name: \"Z-Section Animation\"\n";
    oss << "    type: section_view\n";
    oss << "    fringe: von_mises\n";
    oss << "    section:\n";
    oss << "      axis: z\n";
    oss << "      position: center\n";
    oss << "    states: all\n";
    oss << "    output:\n";
    oss << "      format: mp4\n";
    oss << "      filename: \"section_vonmises.mp4\"\n";
    oss << "      fps: 30\n";
    oss << "      resolution: [1920, 1080]\n\n";

    oss << "  # Final state snapshot\n";
    oss << "  - name: \"Final State\"\n";
    oss << "    type: section_view\n";
    oss << "    fringe: eff_plastic_strain\n";
    oss << "    section:\n";
    oss << "      axis: z\n";
    oss << "      position: center\n";
    oss << "    states: [-1]  # -1 = last state\n";
    oss << "    output:\n";
    oss << "      format: png\n";
    oss << "      filename: \"final_strain.png\"\n";

    return oss.str();
}

std::string UnifiedConfigParser::generateMinimalYAML(const std::string& d3plot_path) {
    std::ostringstream oss;

    oss << "# KooD3plot Minimal Configuration\n";
    oss << "version: \"2.0\"\n\n";

    oss << "input:\n";
    oss << "  d3plot: \"" << d3plot_path << "\"\n\n";

    oss << "output:\n";
    oss << "  directory: \"./analysis_output\"\n";
    oss << "  json: true\n";
    oss << "  csv: true\n\n";

    oss << "analysis_jobs:\n";
    oss << "  - name: \"All Parts Stress\"\n";
    oss << "    type: von_mises\n";
    oss << "    parts: []\n";
    oss << "    output_prefix: \"stress\"\n";

    return oss.str();
}

const std::string& UnifiedConfigParser::getLastError() {
    return last_error_;
}

bool UnifiedConfigParser::validate(const UnifiedConfig& config) {
    if (config.d3plot_path.empty()) {
        last_error_ = "d3plot path is required";
        return false;
    }

    if (config.analysis_jobs.empty() && config.render_jobs.empty()) {
        last_error_ = "At least one analysis_job or render_job is required";
        return false;
    }

    // Validate analysis jobs
    for (const auto& job : config.analysis_jobs) {
        if (job.name.empty()) {
            last_error_ = "Analysis job name is required";
            return false;
        }
    }

    // Validate render jobs
    for (const auto& job : config.render_jobs) {
        if (job.name.empty()) {
            last_error_ = "Render job name is required";
            return false;
        }
    }

    return true;
}

// ============================================================
// Pattern Matching Utility Functions
// ============================================================

bool UnifiedConfigParser::matchPattern(const std::string& name, const std::string& pattern) {
    if (pattern.empty()) return true;  // Empty pattern matches all

    // Simple wildcard matching: * matches any sequence, ? matches single char
    size_t n = name.size();
    size_t p = pattern.size();

    std::vector<std::vector<bool>> dp(n + 1, std::vector<bool>(p + 1, false));
    dp[0][0] = true;

    // Handle patterns starting with *
    for (size_t j = 1; j <= p; ++j) {
        if (pattern[j - 1] == '*') {
            dp[0][j] = dp[0][j - 1];
        }
    }

    for (size_t i = 1; i <= n; ++i) {
        for (size_t j = 1; j <= p; ++j) {
            if (pattern[j - 1] == '*') {
                dp[i][j] = dp[i][j - 1] || dp[i - 1][j];
            } else if (pattern[j - 1] == '?' ||
                       std::toupper(pattern[j - 1]) == std::toupper(name[i - 1])) {
                dp[i][j] = dp[i - 1][j - 1];
            }
        }
    }

    return dp[n][p];
}

std::vector<int32_t> UnifiedConfigParser::filterPartsByPattern(
    const D3plotReader& reader,
    const std::string& pattern) {

    std::vector<int32_t> matching_parts;

    if (pattern.empty()) {
        return matching_parts;  // Empty = no filter (caller should use all parts)
    }

    // Check if pattern looks like a part ID (numeric: "1,2,3" or "10-20")
    bool is_numeric = true;
    for (char c : pattern) {
        if (!std::isdigit(c) && c != '-' && c != ',' && c != ' ') {
            is_numeric = false;
            break;
        }
    }

    if (is_numeric) {
        // Parse as part ID range (e.g., "1,2,3" or "10-20")
        matching_parts = parseIntArray("[" + pattern + "]");
        return matching_parts;
    }

    // Pattern contains wildcards - try to load part names from keyword file
    std::string d3plot_path = reader.getFilePath();

    // Check cache first
    if (g_part_name_cache.find(d3plot_path) == g_part_name_cache.end()) {
        // Try to find and parse keyword file
        std::string keyword_path = findKeywordFile(d3plot_path);
        if (!keyword_path.empty()) {
            g_part_name_cache[d3plot_path] = parsePartNamesFromKeyword(keyword_path);
            std::cerr << "[UnifiedConfigParser] Loaded part names from: " << keyword_path << std::endl;
        } else {
            // No keyword file found - use empty map
            g_part_name_cache[d3plot_path] = {};
            std::cerr << "[UnifiedConfigParser] No keyword file found for part names. "
                      << "Using fallback Part_N names." << std::endl;
        }
    }

    const auto& part_names = g_part_name_cache[d3plot_path];

    // Get all part IDs from mesh
    D3plotReader& mutable_reader = const_cast<D3plotReader&>(reader);
    auto mesh = mutable_reader.read_mesh();

    // Collect unique part IDs
    std::set<int32_t> all_part_ids;
    for (int32_t pid : mesh.solid_parts) all_part_ids.insert(pid);
    for (int32_t pid : mesh.shell_parts) all_part_ids.insert(pid);
    for (int32_t pid : mesh.beam_parts) all_part_ids.insert(pid);
    for (int32_t pid : mesh.thick_shell_parts) all_part_ids.insert(pid);

    // Match each part against pattern
    for (int32_t pid : all_part_ids) {
        std::string name;

        // Try to get name from keyword file
        auto it = part_names.find(pid);
        if (it != part_names.end()) {
            name = it->second;
        } else {
            // Fallback: use Part_N format
            name = "Part_" + std::to_string(pid);
        }

        if (matchPattern(name, pattern)) {
            matching_parts.push_back(pid);
        }
    }

    return matching_parts;
}

} // namespace analysis
} // namespace kood3plot
