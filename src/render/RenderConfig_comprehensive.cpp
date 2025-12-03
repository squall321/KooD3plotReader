/**
 * @file RenderConfig_comprehensive.cpp
 * @brief Comprehensive YAML parser for RenderConfig
 * @author KooD3plot Development Team
 * @date 2025-11-25
 *
 * This file contains the enhanced YAML parser that supports the comprehensive
 * configuration format from KooDynaPostProcessor.
 */

#include "kood3plot/render/RenderConfig.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <algorithm>
#include <cctype>

namespace kood3plot {
namespace render {

// ============================================================
// Enhanced YAML Parser Utilities
// ============================================================

namespace {

struct YAMLNode {
    std::string key;
    std::string value;
    int indent;
    bool is_list_item;
};

// Helper: Parse YAML line
YAMLNode parseYAMLLine(const std::string& line) {
    YAMLNode node;
    node.is_list_item = false;

    // Count leading whitespace
    size_t first = 0;
    while (first < line.size() && (line[first] == ' ' || line[first] == '\t')) {
        ++first;
    }
    node.indent = first;

    if (first >= line.size()) return node;

    std::string content = line.substr(first);

    // Check for list item
    if (content[0] == '-' && (content.size() == 1 || content[1] == ' ')) {
        node.is_list_item = true;
        content = content.substr(1);
        // Trim leading whitespace after '-'
        size_t pos = 0;
        while (pos < content.size() && content[pos] == ' ') ++pos;
        content = content.substr(pos);
    }

    // Find colon
    size_t colon = content.find(':');
    if (colon != std::string::npos) {
        node.key = content.substr(0, colon);
        if (colon + 1 < content.size()) {
            node.value = content.substr(colon + 1);
            // Trim leading whitespace
            size_t vstart = 0;
            while (vstart < node.value.size() && node.value[vstart] == ' ') ++vstart;
            node.value = node.value.substr(vstart);

            // Remove quotes
            if (!node.value.empty() && node.value[0] == '"') {
                node.value = node.value.substr(1);
                size_t end = node.value.find('"');
                if (end != std::string::npos) {
                    node.value = node.value.substr(0, end);
                }
            }
        }
    } else {
        node.value = content;
    }

    return node;
}

// Helper: Parse list of strings from YAML array notation
// Example: ["value1", "value2", "value3"]
std::vector<std::string> parseYAMLArray(const std::string& value) {
    std::vector<std::string> result;
    if (value.empty() || value[0] != '[') return result;

    std::string content = value.substr(1);
    size_t end_bracket = content.find(']');
    if (end_bracket != std::string::npos) {
        content = content.substr(0, end_bracket);
    }

    // Split by comma
    std::istringstream iss(content);
    std::string item;
    while (std::getline(iss, item, ',')) {
        // Trim whitespace
        size_t start = 0;
        while (start < item.size() && std::isspace(item[start])) ++start;
        size_t end = item.size();
        while (end > start && std::isspace(item[end - 1])) --end;
        item = item.substr(start, end - start);

        // Remove quotes
        if (!item.empty() && item[0] == '"') {
            item = item.substr(1);
            if (!item.empty() && item[item.size() - 1] == '"') {
                item = item.substr(0, item.size() - 1);
            }
        }

        if (!item.empty()) {
            result.push_back(item);
        }
    }

    return result;
}

// Helper: Parse number array [1920, 1080]
std::vector<double> parseNumberArray(const std::string& value) {
    std::vector<double> result;
    if (value.empty() || value[0] != '[') return result;

    std::string content = value.substr(1);
    size_t end_bracket = content.find(']');
    if (end_bracket != std::string::npos) {
        content = content.substr(0, end_bracket);
    }

    std::istringstream iss(content);
    std::string item;
    while (std::getline(iss, item, ',')) {
        try {
            result.push_back(std::stod(item));
        } catch (...) {}
    }

    return result;
}

} // anonymous namespace

// ============================================================
// Comprehensive YAML Loader Implementation
// ============================================================

bool RenderConfig::loadFromYAML(const std::string& file_path) {
    std::ifstream ifs(file_path);
    if (!ifs.is_open()) {
        pImpl->last_error = "Cannot open file: " + file_path;
        return false;
    }

    try {
        pImpl->data = RenderConfigData();  // Reset

        std::string line;
        std::string current_section;
        std::string current_subsection;
        int section_indent = 0;
        int subsection_indent = 0;

        // For parsing sections
        SectionConfig current_section_config;
        OrientationConfig current_orientation;
        bool in_sections = false;
        bool in_section_item = false;
        bool in_orientations = false;
        bool in_orientation_item = false;

        while (std::getline(ifs, line)) {
            // Skip comments and empty lines
            if (line.empty() || line.find_first_not_of(" \t") == std::string::npos) continue;
            if (line.find('#') == 0) continue;

            YAMLNode node = parseYAMLLine(line);
            if (node.key.empty() && node.value.empty()) continue;

            // Root level sections
            if (node.indent == 0) {
                current_section = node.key;
                section_indent = 0;
                current_subsection = "";

                if (current_section == "sections") {
                    in_sections = true;
                } else {
                    in_sections = false;
                }

                continue;
            }

            // ============================================================
            // Analysis section
            // ============================================================
            if (current_section == "analysis") {
                if (node.key == "run_ids") {
                    // Can be array notation or list
                    if (node.value.find('[') != std::string::npos) {
                        pImpl->data.analysis.run_ids = parseYAMLArray(node.value);
                    }
                } else if (node.key == "data_path") {
                    pImpl->data.analysis.data_path = node.value;
                } else if (node.key == "output_path") {
                    pImpl->data.analysis.output_path = node.value;
                } else if (node.key == "cache_path") {
                    pImpl->data.analysis.cache_path = node.value;
                } else if (node.key == "lsprepost" || current_subsection == "lsprepost") {
                    if (node.key == "lsprepost") {
                        current_subsection = "lsprepost";
                    } else if (node.key == "executable") {
                        pImpl->data.analysis.lsprepost.executable = node.value;
                    } else if (node.key == "options") {
                        pImpl->data.analysis.lsprepost.options = node.value;
                    } else if (node.key == "timeout") {
                        pImpl->data.analysis.lsprepost.timeout = std::stoi(node.value);
                    }
                } else if (node.is_list_item && !node.value.empty()) {
                    // List item for run_ids
                    pImpl->data.analysis.run_ids.push_back(node.value);
                }
            }

            // ============================================================
            // Fringe section
            // ============================================================
            else if (current_section == "fringe") {
                if (node.key == "type") {
                    pImpl->data.fringe.type = node.value;
                } else if (node.key == "min") {
                    pImpl->data.fringe.min = std::stod(node.value);
                } else if (node.key == "max") {
                    pImpl->data.fringe.max = std::stod(node.value);
                } else if (node.key == "auto_range") {
                    pImpl->data.fringe.auto_range = (node.value == "true");
                } else if (node.key == "colormap") {
                    pImpl->data.fringe.colormap = node.value;
                } else if (node.key == "range" || current_subsection == "range") {
                    if (node.key == "range") {
                        current_subsection = "range";
                    } else if (node.key == "min") {
                        pImpl->data.fringe.min = std::stod(node.value);
                    } else if (node.key == "max") {
                        pImpl->data.fringe.max = std::stod(node.value);
                    }
                }
            }

            // ============================================================
            // Output section
            // ============================================================
            else if (current_section == "output") {
                if (node.key == "movie" || current_subsection == "movie") {
                    if (node.key == "movie") {
                        current_subsection = "movie";
                        if (!node.value.empty()) {
                            pImpl->data.output.movie_settings.enabled = (node.value == "true");
                        }
                    } else if (node.key == "enabled") {
                        pImpl->data.output.movie_settings.enabled = (node.value == "true");
                    } else if (node.key == "resolution") {
                        auto res = parseNumberArray(node.value);
                        if (res.size() >= 2) {
                            pImpl->data.output.movie_settings.width = static_cast<int>(res[0]);
                            pImpl->data.output.movie_settings.height = static_cast<int>(res[1]);
                        }
                    } else if (node.key == "fps") {
                        pImpl->data.output.movie_settings.fps = std::stoi(node.value);
                    } else if (node.key == "codec") {
                        pImpl->data.output.movie_settings.codec = node.value;
                    }
                } else if (node.key == "images" || current_subsection == "images") {
                    if (node.key == "images") {
                        current_subsection = "images";
                        if (!node.value.empty()) {
                            pImpl->data.output.image_settings.enabled = (node.value == "true");
                        }
                    } else if (node.key == "enabled") {
                        pImpl->data.output.image_settings.enabled = (node.value == "true");
                    } else if (node.key == "format") {
                        pImpl->data.output.image_settings.format = node.value;
                    } else if (node.key == "resolution") {
                        auto res = parseNumberArray(node.value);
                        if (res.size() >= 2) {
                            pImpl->data.output.image_settings.width = static_cast<int>(res[0]);
                            pImpl->data.output.image_settings.height = static_cast<int>(res[1]);
                        }
                    } else if (node.key == "timesteps") {
                        pImpl->data.output.image_settings.timesteps = node.value;
                    }
                } else if (node.key == "data" || current_subsection == "data") {
                    if (node.key == "data") {
                        current_subsection = "data";
                    } else if (node.key == "enabled") {
                        pImpl->data.output.data_settings.enabled = (node.value == "true");
                    } else if (node.key == "format") {
                        pImpl->data.output.data_settings.format = node.value;
                    } else if (node.key == "include") {
                        // List follows
                    } else if (node.is_list_item && !node.value.empty()) {
                        pImpl->data.output.data_settings.include.push_back(node.value);
                    }
                } else if (node.key == "comparison" || current_subsection == "comparison") {
                    if (node.key == "comparison") {
                        current_subsection = "comparison";
                    } else if (node.key == "enabled") {
                        pImpl->data.output.comparison.enabled = (node.value == "true");
                    } else if (node.key == "baseline") {
                        pImpl->data.output.comparison.baseline = node.value;
                    } else if (node.key == "generate_html") {
                        pImpl->data.output.comparison.generate_html = (node.value == "true");
                    } else if (node.key == "generate_csv") {
                        pImpl->data.output.comparison.generate_csv = (node.value == "true");
                    } else if (node.key == "include_plots") {
                        pImpl->data.output.comparison.include_plots = (node.value == "true");
                    }
                }
            }

            // ============================================================
            // Processing section
            // ============================================================
            else if (current_section == "processing") {
                if (node.key == "parallel" || current_subsection == "parallel") {
                    if (node.key == "parallel") {
                        current_subsection = "parallel";
                    } else if (node.key == "enabled") {
                        pImpl->data.processing.parallel.enabled = (node.value == "true");
                    } else if (node.key == "max_threads") {
                        pImpl->data.processing.parallel.max_threads = std::stoi(node.value);
                    }
                } else if (node.key == "cache" || current_subsection == "cache") {
                    if (node.key == "cache") {
                        current_subsection = "cache";
                    } else if (node.key == "enabled") {
                        pImpl->data.processing.cache.enabled = (node.value == "true");
                    } else if (node.key == "cache_bounding_boxes") {
                        pImpl->data.processing.cache.cache_bounding_boxes = (node.value == "true");
                    } else if (node.key == "cache_sections") {
                        pImpl->data.processing.cache.cache_sections = (node.value == "true");
                    }
                } else if (node.key == "memory" || current_subsection == "memory") {
                    if (node.key == "memory") {
                        current_subsection = "memory";
                    } else if (node.key == "max_memory_mb") {
                        pImpl->data.processing.memory.max_memory_mb = std::stoi(node.value);
                    } else if (node.key == "chunk_size") {
                        pImpl->data.processing.memory.chunk_size = std::stoi(node.value);
                    } else if (node.key == "cleanup_threshold") {
                        pImpl->data.processing.memory.cleanup_threshold = std::stod(node.value);
                    }
                } else if (node.key == "retry" || current_subsection == "retry") {
                    if (node.key == "retry") {
                        current_subsection = "retry";
                    } else if (node.key == "enabled") {
                        pImpl->data.processing.retry.enabled = (node.value == "true");
                    } else if (node.key == "max_attempts") {
                        pImpl->data.processing.retry.max_attempts = std::stoi(node.value);
                    } else if (node.key == "delay_seconds") {
                        pImpl->data.processing.retry.delay_seconds = std::stoi(node.value);
                    }
                }
            }

            // ============================================================
            // Logging section
            // ============================================================
            else if (current_section == "logging") {
                if (node.key == "level") {
                    pImpl->data.logging.level = node.value;
                } else if (node.key == "file") {
                    pImpl->data.logging.file = node.value;
                } else if (node.key == "console") {
                    pImpl->data.logging.console = (node.value == "true");
                }
            }

            // ============================================================
            // View section
            // ============================================================
            else if (current_section == "view") {
                if (node.key == "orientation") {
                    pImpl->data.view.orientation = node.value;
                } else if (node.key == "zoom_factor") {
                    pImpl->data.view.zoom_factor = std::stod(node.value);
                } else if (node.key == "auto_fit") {
                    pImpl->data.view.auto_fit = (node.value == "true");
                }
            }
        }

        return true;

    } catch (const std::exception& e) {
        pImpl->last_error = std::string("YAML parsing error: ") + e.what();
        return false;
    }
}

} // namespace render
} // namespace kood3plot
