/**
 * @file RenderConfig.cpp
 * @brief Configuration parser implementation
 */

#include "kood3plot/render/RenderConfig.h"
#include "kood3plot/render/GeometryAnalyzer.h"
#include "kood3plot/D3plotReader.hpp"
#include <fstream>
#include <sstream>
#include <iostream>
#include <cctype>
#include <stdexcept>

namespace kood3plot {
namespace render {

// ============================================================
// Simple JSON Parser (no external dependencies)
// ============================================================

namespace {

// Helper: Trim whitespace
std::string trim(const std::string& str) {
    size_t start = 0;
    while (start < str.size() && std::isspace(str[start])) ++start;
    size_t end = str.size();
    while (end > start && std::isspace(str[end - 1])) --end;
    return str.substr(start, end - start);
}

// Helper: Skip whitespace in stream
void skipWhitespace(std::istringstream& iss) {
    while (iss.good() && std::isspace(iss.peek())) {
        iss.get();
    }
}

// Helper: Parse JSON string value
std::string parseJSONString(std::istringstream& iss) {
    skipWhitespace(iss);
    if (iss.peek() != '"') return "";
    iss.get(); // skip opening "

    std::string result;
    while (iss.good() && iss.peek() != '"') {
        char c = iss.get();
        if (c == '\\' && iss.good()) {
            c = iss.get();
            if (c == 'n') result += '\n';
            else if (c == 't') result += '\t';
            else result += c;
        } else {
            result += c;
        }
    }

    if (iss.good()) iss.get(); // skip closing "
    return result;
}

// Helper: Parse JSON number
double parseJSONNumber(std::istringstream& iss) {
    skipWhitespace(iss);
    double value = 0.0;
    iss >> value;
    return value;
}

// Helper: Parse JSON boolean
bool parseJSONBool(std::istringstream& iss) {
    skipWhitespace(iss);
    std::string value;
    while (iss.good() && std::isalpha(iss.peek())) {
        value += iss.get();
    }
    return (value == "true");
}

} // anonymous namespace

// ============================================================
// Implementation Structure
// ============================================================

struct RenderConfig::Impl {
    RenderConfigData data;
    std::string last_error;
};

// ============================================================
// Constructor / Destructor
// ============================================================

RenderConfig::RenderConfig() : pImpl(std::make_unique<Impl>()) {}

RenderConfig::~RenderConfig() = default;

// Move constructor
RenderConfig::RenderConfig(RenderConfig&& other) noexcept
    : pImpl(std::move(other.pImpl)) {}

// Move assignment operator
RenderConfig& RenderConfig::operator=(RenderConfig&& other) noexcept {
    if (this != &other) {
        pImpl = std::move(other.pImpl);
    }
    return *this;
}

// ============================================================
// Loading - Simplified JSON parser
// ============================================================

bool RenderConfig::loadFromJSON(const std::string& file_path) {
    std::ifstream ifs(file_path);
    if (!ifs.is_open()) {
        pImpl->last_error = "Cannot open file: " + file_path;
        return false;
    }

    std::string json_str((std::istreambuf_iterator<char>(ifs)),
                         std::istreambuf_iterator<char>());
    return loadFromJSONString(json_str);
}

bool RenderConfig::loadFromJSONString(const std::string& json_str) {
    try {
        // Very simplified JSON parser - looks for key patterns
        // In production, use nlohmann/json or similar

        pImpl->data = RenderConfigData();

        // Parse analysis section
        size_t analysis_pos = json_str.find("\"analysis\"");
        if (analysis_pos != std::string::npos) {
            size_t data_path_pos = json_str.find("\"data_path\"", analysis_pos);
            if (data_path_pos != std::string::npos) {
                size_t colon = json_str.find(":", data_path_pos);
                size_t quote1 = json_str.find("\"", colon + 1);
                size_t quote2 = json_str.find("\"", quote1 + 1);
                if (quote1 != std::string::npos && quote2 != std::string::npos) {
                    pImpl->data.analysis.data_path = json_str.substr(quote1 + 1, quote2 - quote1 - 1);
                }
            }

            size_t output_path_pos = json_str.find("\"output_path\"", analysis_pos);
            if (output_path_pos != std::string::npos) {
                size_t colon = json_str.find(":", output_path_pos);
                size_t quote1 = json_str.find("\"", colon + 1);
                size_t quote2 = json_str.find("\"", quote1 + 1);
                if (quote1 != std::string::npos && quote2 != std::string::npos) {
                    pImpl->data.analysis.output_path = json_str.substr(quote1 + 1, quote2 - quote1 - 1);
                }
            }
        }

        // Parse fringe section
        size_t fringe_pos = json_str.find("\"fringe\"");
        if (fringe_pos != std::string::npos) {
            size_t type_pos = json_str.find("\"type\"", fringe_pos);
            if (type_pos != std::string::npos) {
                size_t colon = json_str.find(":", type_pos);
                size_t quote1 = json_str.find("\"", colon + 1);
                size_t quote2 = json_str.find("\"", quote1 + 1);
                if (quote1 != std::string::npos && quote2 != std::string::npos) {
                    pImpl->data.fringe.type = json_str.substr(quote1 + 1, quote2 - quote1 - 1);
                }
            }

            size_t min_pos = json_str.find("\"min\"", fringe_pos);
            if (min_pos != std::string::npos) {
                size_t colon = json_str.find(":", min_pos);
                std::string num_str = json_str.substr(colon + 1, 20);
                pImpl->data.fringe.min = std::stod(trim(num_str));
            }

            size_t max_pos = json_str.find("\"max\"", fringe_pos);
            if (max_pos != std::string::npos) {
                size_t colon = json_str.find(":", max_pos);
                std::string num_str = json_str.substr(colon + 1, 20);
                pImpl->data.fringe.max = std::stod(trim(num_str));
            }

            size_t auto_pos = json_str.find("\"auto_range\"", fringe_pos);
            if (auto_pos != std::string::npos) {
                size_t colon = json_str.find(":", auto_pos);
                std::string bool_str = json_str.substr(colon + 1, 10);
                pImpl->data.fringe.auto_range = (trim(bool_str).find("true") != std::string::npos);
            }
        }

        // Parse output section
        size_t output_pos = json_str.find("\"output\"");
        if (output_pos != std::string::npos) {
            size_t movie_pos = json_str.find("\"movie\"", output_pos);
            if (movie_pos != std::string::npos) {
                size_t colon = json_str.find(":", movie_pos);
                std::string bool_str = json_str.substr(colon + 1, 10);
                pImpl->data.output.movie = (trim(bool_str).find("true") != std::string::npos);
            }

            size_t images_pos = json_str.find("\"images\"", output_pos);
            if (images_pos != std::string::npos) {
                size_t colon = json_str.find(":", images_pos);
                std::string bool_str = json_str.substr(colon + 1, 10);
                pImpl->data.output.images = (trim(bool_str).find("true") != std::string::npos);
            }

            size_t width_pos = json_str.find("\"width\"", output_pos);
            if (width_pos != std::string::npos) {
                size_t colon = json_str.find(":", width_pos);
                std::string num_str = json_str.substr(colon + 1, 20);
                pImpl->data.output.width = std::stoi(trim(num_str));
            }

            size_t height_pos = json_str.find("\"height\"", output_pos);
            if (height_pos != std::string::npos) {
                size_t colon = json_str.find(":", height_pos);
                std::string num_str = json_str.substr(colon + 1, 20);
                pImpl->data.output.height = std::stoi(trim(num_str));
            }

            size_t fps_pos = json_str.find("\"fps\"", output_pos);
            if (fps_pos != std::string::npos) {
                size_t colon = json_str.find(":", fps_pos);
                std::string num_str = json_str.substr(colon + 1, 20);
                pImpl->data.output.fps = std::stoi(trim(num_str));
            }
        }

        // Parse view section
        size_t view_pos = json_str.find("\"view\"");
        if (view_pos != std::string::npos) {
            size_t orientation_pos = json_str.find("\"orientation\"", view_pos);
            if (orientation_pos != std::string::npos) {
                size_t colon = json_str.find(":", orientation_pos);
                size_t quote1 = json_str.find("\"", colon + 1);
                size_t quote2 = json_str.find("\"", quote1 + 1);
                if (quote1 != std::string::npos && quote2 != std::string::npos) {
                    pImpl->data.view.orientation = json_str.substr(quote1 + 1, quote2 - quote1 - 1);
                }
            }

            size_t zoom_pos = json_str.find("\"zoom_factor\"", view_pos);
            if (zoom_pos != std::string::npos) {
                size_t colon = json_str.find(":", zoom_pos);
                std::string num_str = json_str.substr(colon + 1, 20);
                pImpl->data.view.zoom_factor = std::stod(trim(num_str));
            }

            size_t auto_fit_pos = json_str.find("\"auto_fit\"", view_pos);
            if (auto_fit_pos != std::string::npos) {
                size_t colon = json_str.find(":", auto_fit_pos);
                std::string bool_str = json_str.substr(colon + 1, 10);
                pImpl->data.view.auto_fit = (trim(bool_str).find("true") != std::string::npos);
            }
        }

        return true;

    } catch (const std::exception& e) {
        pImpl->last_error = std::string("JSON parsing error: ") + e.what();
        return false;
    }
}

// Helper: Parse list of strings from YAML array notation
static std::vector<std::string> parseYAMLArray(const std::string& value) {
    std::vector<std::string> result;
    if (value.empty() || value[0] != '[') return result;

    std::string content = value.substr(1);
    size_t end_bracket = content.find(']');
    if (end_bracket != std::string::npos) {
        content = content.substr(0, end_bracket);
    }

    std::istringstream iss(content);
    std::string item;
    while (std::getline(iss, item, ',')) {
        size_t start = 0;
        while (start < item.size() && std::isspace(item[start])) ++start;
        size_t end = item.size();
        while (end > start && std::isspace(item[end - 1])) --end;
        item = item.substr(start, end - start);

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
static std::vector<double> parseNumberArray(const std::string& value) {
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

bool RenderConfig::loadFromYAML(const std::string& file_path) {
    std::ifstream ifs(file_path);
    if (!ifs.is_open()) {
        pImpl->last_error = "Cannot open file: " + file_path;
        return false;
    }

    try {
        pImpl->data = RenderConfigData();
        std::string line;
        std::string current_section;
        std::string current_subsection;

        while (std::getline(ifs, line)) {
            // Skip comments and empty lines
            if (line.empty() || line[0] == '#') continue;

            size_t first = line.find_first_not_of(" \t");
            if (first == std::string::npos) continue;

            std::string content = line.substr(first);
            int indent = first;

            // Check for list item
            bool is_list_item = (content[0] == '-' && (content.size() == 1 || content[1] == ' '));
            if (is_list_item) {
                content = content.substr(1);
                size_t pos = 0;
                while (pos < content.size() && content[pos] == ' ') ++pos;
                content = content.substr(pos);
            }

            size_t colon = content.find(':');
            if (colon == std::string::npos) continue;

            std::string key = trim(content.substr(0, colon));
            std::string value = trim(content.substr(colon + 1));

            // Remove quotes
            if (!value.empty() && value[0] == '"') {
                value = value.substr(1);
                size_t end = value.find('"');
                if (end != std::string::npos) {
                    value = value.substr(0, end);
                }
            }

            // Root level
            if (indent == 0) {
                current_section = key;
                current_subsection = "";
                continue;
            }

            // Analysis
            if (current_section == "analysis") {
                if (key == "run_ids" && value.find('[') != std::string::npos) {
                    pImpl->data.analysis.run_ids = parseYAMLArray(value);
                } else if (key == "data_path") {
                    pImpl->data.analysis.data_path = value;
                } else if (key == "output_path") {
                    pImpl->data.analysis.output_path = value;
                } else if (key == "cache_path") {
                    pImpl->data.analysis.cache_path = value;
                } else if (key == "lsprepost") {
                    current_subsection = "lsprepost";
                } else if (current_subsection == "lsprepost") {
                    if (key == "executable") pImpl->data.analysis.lsprepost.executable = value;
                    else if (key == "options") pImpl->data.analysis.lsprepost.options = value;
                    else if (key == "timeout") pImpl->data.analysis.lsprepost.timeout = std::stoi(value);
                } else if (is_list_item && !value.empty()) {
                    pImpl->data.analysis.run_ids.push_back(value);
                }
            }
            // Fringe
            else if (current_section == "fringe") {
                if (key == "type") pImpl->data.fringe.type = value;
                else if (key == "colormap") pImpl->data.fringe.colormap = value;
                else if (key == "auto_range") pImpl->data.fringe.auto_range = (value == "true");
                else if (key == "min") pImpl->data.fringe.min = std::stod(value);
                else if (key == "max") pImpl->data.fringe.max = std::stod(value);
                else if (key == "range") current_subsection = "range";
                else if (current_subsection == "range") {
                    if (key == "min") pImpl->data.fringe.min = std::stod(value);
                    else if (key == "max") pImpl->data.fringe.max = std::stod(value);
                }
            }
            // Output
            else if (current_section == "output") {
                if (key == "movie") {
                    if (!value.empty()) {
                        pImpl->data.output.movie = (value == "true");
                        pImpl->data.output.movie_settings.enabled = (value == "true");
                    }
                    current_subsection = "movie";
                } else if (key == "images") {
                    pImpl->data.output.images = (value == "true");
                } else if (key == "width") {
                    pImpl->data.output.width = std::stoi(value);
                } else if (key == "height") {
                    pImpl->data.output.height = std::stoi(value);
                } else if (key == "fps") {
                    pImpl->data.output.fps = std::stoi(value);
                } else if (key == "format") {
                    pImpl->data.output.format = value;
                } else if (current_subsection == "movie") {
                    if (key == "enabled") pImpl->data.output.movie_settings.enabled = (value == "true");
                    else if (key == "resolution") {
                        auto res = parseNumberArray(value);
                        if (res.size() >= 2) {
                            pImpl->data.output.movie_settings.width = static_cast<int>(res[0]);
                            pImpl->data.output.movie_settings.height = static_cast<int>(res[1]);
                        }
                    }
                    else if (key == "fps") pImpl->data.output.movie_settings.fps = std::stoi(value);
                    else if (key == "codec") pImpl->data.output.movie_settings.codec = value;
                }
            }
            // Sections
            else if (current_section == "sections") {
                if (is_list_item) {
                    // New section item
                    SectionConfig new_section;
                    pImpl->data.sections.push_back(new_section);
                    current_subsection = "section_item";
                }
                if (!pImpl->data.sections.empty()) {
                    auto& section = pImpl->data.sections.back();
                    if (key == "auto_mode") {
                        section.auto_mode = stringToAutoSectionMode(value);
                    } else if (key == "auto_params") {
                        current_subsection = "auto_params";
                    } else if (current_subsection == "auto_params") {
                        if (key == "orientation") section.auto_params.orientation = value;
                        else if (key == "position") section.auto_params.position = value;
                        else if (key == "custom_ratio") section.auto_params.custom_ratio = std::stod(value);
                        else if (key == "count") section.auto_params.count = std::stoi(value);
                        else if (key == "spacing") section.auto_params.spacing = std::stod(value);
                        else if (key == "offset_percent") section.auto_params.offset_percent = std::stod(value);
                    } else if (key == "part") {
                        current_subsection = "part";
                    } else if (current_subsection == "part") {
                        if (key == "name") section.part.name = value;
                        else if (key == "id") section.part.id = std::stoi(value);
                    }
                }
            }
            // Processing
            else if (current_section == "processing") {
                if (key == "parallel") current_subsection = "parallel";
                else if (current_subsection == "parallel") {
                    if (key == "enabled") pImpl->data.processing.parallel.enabled = (value == "true");
                    else if (key == "max_threads") pImpl->data.processing.parallel.max_threads = std::stoi(value);
                }
            }
            // View
            else if (current_section == "view") {
                if (key == "orientation") pImpl->data.view.orientation = value;
                else if (key == "zoom_factor") pImpl->data.view.zoom_factor = std::stod(value);
                else if (key == "auto_fit") pImpl->data.view.auto_fit = (value == "true");
            }
        }

        return true;

    } catch (const std::exception& e) {
        pImpl->last_error = std::string("YAML parsing error: ") + e.what();
        return false;
    }
}

// ============================================================
// Saving
// ============================================================

bool RenderConfig::saveToJSON(const std::string& file_path, bool pretty) const {
    std::ofstream ofs(file_path);
    if (!ofs.is_open()) {
        return false;
    }

    ofs << toJSONString(pretty);
    return true;
}

std::string RenderConfig::toJSONString(bool pretty) const {
    std::ostringstream json;
    std::string indent = pretty ? "  " : "";
    std::string nl = pretty ? "\n" : "";

    json << "{" << nl;

    // Analysis section
    json << indent << "\"analysis\": {" << nl;
    json << indent << indent << "\"data_path\": \"" << pImpl->data.analysis.data_path << "\"," << nl;
    json << indent << indent << "\"output_path\": \"" << pImpl->data.analysis.output_path << "\"" << nl;
    json << indent << "}," << nl;

    // Fringe section
    json << indent << "\"fringe\": {" << nl;
    json << indent << indent << "\"type\": \"" << pImpl->data.fringe.type << "\"," << nl;
    json << indent << indent << "\"min\": " << pImpl->data.fringe.min << "," << nl;
    json << indent << indent << "\"max\": " << pImpl->data.fringe.max << "," << nl;
    json << indent << indent << "\"auto_range\": " << (pImpl->data.fringe.auto_range ? "true" : "false") << nl;
    json << indent << "}," << nl;

    // Output section
    json << indent << "\"output\": {" << nl;
    json << indent << indent << "\"movie\": " << (pImpl->data.output.movie ? "true" : "false") << "," << nl;
    json << indent << indent << "\"images\": " << (pImpl->data.output.images ? "true" : "false") << "," << nl;
    json << indent << indent << "\"width\": " << pImpl->data.output.width << "," << nl;
    json << indent << indent << "\"height\": " << pImpl->data.output.height << "," << nl;
    json << indent << indent << "\"fps\": " << pImpl->data.output.fps << nl;
    json << indent << "}," << nl;

    // View section
    json << indent << "\"view\": {" << nl;
    json << indent << indent << "\"orientation\": \"" << pImpl->data.view.orientation << "\"," << nl;
    json << indent << indent << "\"zoom_factor\": " << pImpl->data.view.zoom_factor << "," << nl;
    json << indent << indent << "\"auto_fit\": " << (pImpl->data.view.auto_fit ? "true" : "false") << nl;
    json << indent << "}" << nl;

    json << "}" << nl;

    return json.str();
}

bool RenderConfig::saveToYAML(const std::string& file_path) const {
    std::ofstream ofs(file_path);
    if (!ofs.is_open()) {
        return false;
    }

    // Analysis section
    ofs << "analysis:\n";
    ofs << "  data_path: " << pImpl->data.analysis.data_path << "\n";
    ofs << "  output_path: " << pImpl->data.analysis.output_path << "\n";
    if (!pImpl->data.analysis.run_ids.empty()) {
        ofs << "  run_ids:\n";
        for (const auto& id : pImpl->data.analysis.run_ids) {
            ofs << "    - " << id << "\n";
        }
    }
    ofs << "\n";

    // Fringe section
    ofs << "fringe:\n";
    ofs << "  type: " << pImpl->data.fringe.type << "\n";
    ofs << "  min: " << pImpl->data.fringe.min << "\n";
    ofs << "  max: " << pImpl->data.fringe.max << "\n";
    ofs << "  auto_range: " << (pImpl->data.fringe.auto_range ? "true" : "false") << "\n";
    ofs << "\n";

    // Output section
    ofs << "output:\n";
    ofs << "  movie: " << (pImpl->data.output.movie ? "true" : "false") << "\n";
    ofs << "  images: " << (pImpl->data.output.images ? "true" : "false") << "\n";
    ofs << "  width: " << pImpl->data.output.width << "\n";
    ofs << "  height: " << pImpl->data.output.height << "\n";
    ofs << "  fps: " << pImpl->data.output.fps << "\n";
    ofs << "  format: " << pImpl->data.output.format << "\n";
    ofs << "\n";

    // View section
    ofs << "view:\n";
    ofs << "  orientation: " << pImpl->data.view.orientation << "\n";
    ofs << "  zoom_factor: " << pImpl->data.view.zoom_factor << "\n";
    ofs << "  auto_fit: " << (pImpl->data.view.auto_fit ? "true" : "false") << "\n";
    ofs << "\n";

    // Sections (if any)
    if (!pImpl->data.sections.empty()) {
        ofs << "sections:\n";
        for (const auto& section : pImpl->data.sections) {
            ofs << "  - ";

            // Part info
            if (section.part.id > 0 || !section.part.name.empty()) {
                ofs << "part:\n";
                if (!section.part.name.empty()) {
                    ofs << "      name: " << section.part.name << "\n    ";
                }
                if (section.part.id > 0) {
                    ofs << "      id: " << section.part.id << "\n    ";
                }
            }

            // Auto-section mode
            ofs << "auto_mode: " << autoSectionModeToString(section.auto_mode) << "\n";

            // Auto-section parameters (if not manual)
            if (section.auto_mode != AutoSectionMode::MANUAL) {
                ofs << "    auto_params:\n";
                ofs << "      orientation: " << section.auto_params.orientation << "\n";
                ofs << "      position: " << section.auto_params.position << "\n";
                ofs << "      custom_ratio: " << section.auto_params.custom_ratio << "\n";
                ofs << "      count: " << section.auto_params.count << "\n";
                ofs << "      spacing: " << section.auto_params.spacing << "\n";
                ofs << "      offset_percent: " << section.auto_params.offset_percent << "\n";
            }

            // Manual planes (if any)
            if (!section.planes.empty()) {
                ofs << "    planes:\n";
                for (const auto& plane : section.planes) {
                    ofs << "      - point: [" << plane.point[0] << ", "
                        << plane.point[1] << ", " << plane.point[2] << "]\n";
                    ofs << "        normal: [" << plane.normal[0] << ", "
                        << plane.normal[1] << ", " << plane.normal[2] << "]\n";
                }
            }
        }
    }

    return true;
}

// ============================================================
// Auto-Section Generation
// ============================================================

void RenderConfig::generateAutoSections(D3plotReader& reader, size_t state_index) {
    for (auto& section : pImpl->data.sections) {
        // Skip manual sections
        if (section.auto_mode == AutoSectionMode::MANUAL) {
            continue;
        }

        // Calculate bounding box based on part ID
        BoundingBox bbox;
        if (section.part.id > 0) {
            // Calculate bounds for specific part
            bbox = GeometryAnalyzer::calculatePartBounds(reader, section.part.id, state_index);
        } else {
            // Calculate bounds for entire model
            bbox = GeometryAnalyzer::calculateModelBounds(reader, state_index);
        }

        // Generate planes based on auto_mode
        std::vector<SectionPlane> planes;

        switch (section.auto_mode) {
            case AutoSectionMode::SINGLE: {
                SectionPosition pos = GeometryAnalyzer::stringToPosition(section.auto_params.position);
                planes.push_back(GeometryAnalyzer::createSectionPlane(
                    bbox,
                    section.auto_params.orientation,
                    pos,
                    section.auto_params.custom_ratio
                ));
                break;
            }

            case AutoSectionMode::EVEN_SPACED:
                planes = GeometryAnalyzer::createEvenSections(
                    bbox,
                    section.auto_params.orientation,
                    section.auto_params.count
                );
                break;

            case AutoSectionMode::UNIFORM_SPACING:
                planes = GeometryAnalyzer::createUniformSections(
                    bbox,
                    section.auto_params.orientation,
                    section.auto_params.spacing
                );
                break;

            case AutoSectionMode::STANDARD_3:
                planes = GeometryAnalyzer::createStandard3Sections(
                    bbox,
                    section.auto_params.orientation
                );
                break;

            case AutoSectionMode::OFFSET_EDGES:
                planes = GeometryAnalyzer::createOffsetSections(
                    bbox,
                    section.auto_params.orientation,
                    section.auto_params.offset_percent
                );
                break;

            default:
                break;
        }

        // Store generated planes
        section.planes = planes;
    }
}

// ============================================================
// Conversion
// ============================================================

RenderOptions RenderConfig::toRenderOptions(int section_index) const {
    RenderOptions options;

    // Fringe settings
    options.fringe_type = stringToFringeType(pImpl->data.fringe.type);
    options.auto_fringe_range = pImpl->data.fringe.auto_range;
    options.fringe_min = pImpl->data.fringe.min;
    options.fringe_max = pImpl->data.fringe.max;

    // Output settings
    options.create_animation = pImpl->data.output.movie;
    options.generate_images = pImpl->data.output.images;
    options.generate_movie = pImpl->data.output.movie;
    options.image_width = pImpl->data.output.width;
    options.image_height = pImpl->data.output.height;
    options.fps = pImpl->data.output.fps;
    options.video_format = VideoFormat::MP4; // Default

    // View settings
    options.view = stringToViewOrientation(pImpl->data.view.orientation);
    options.zoom_factor = pImpl->data.view.zoom_factor;
    options.use_auto_fit = pImpl->data.view.auto_fit;

    // Section planes
    if (!pImpl->data.sections.empty() && section_index >= 0 &&
        section_index < static_cast<int>(pImpl->data.sections.empty())) {
        const auto& section = pImpl->data.sections[section_index];
        options.section_planes = section.planes;
        if (section.part.id > 0) {
            options.part_id = section.part.id;
        }
    }

    return options;
}

std::vector<RenderOptions> RenderConfig::toAllRenderOptions() const {
    std::vector<RenderOptions> all_options;

    if (pImpl->data.sections.empty()) {
        // No sections defined, return default options
        all_options.push_back(toRenderOptions(-1));
    } else {
        // Create options for each section
        for (size_t i = 0; i < pImpl->data.sections.size(); ++i) {
            all_options.push_back(toRenderOptions(i));
        }
    }

    return all_options;
}

std::vector<std::tuple<std::string, std::string, RenderOptions>>
RenderConfig::createBatchJobs() const {
    std::vector<std::tuple<std::string, std::string, RenderOptions>> jobs;

    for (const auto& run_id : pImpl->data.analysis.run_ids) {
        std::string d3plot_path = pImpl->data.analysis.data_path + "/" + run_id + "/d3plot";

        auto all_options = toAllRenderOptions();
        for (size_t i = 0; i < all_options.size(); ++i) {
            std::string output_path = pImpl->data.analysis.output_path + "/" +
                                     run_id + "_section_" + std::to_string(i) + ".mp4";
            jobs.emplace_back(d3plot_path, output_path, all_options[i]);
        }
    }

    return jobs;
}

// ============================================================
// Access
// ============================================================

const RenderConfigData& RenderConfig::getData() const {
    return pImpl->data;
}

void RenderConfig::setData(const RenderConfigData& data) {
    pImpl->data = data;
}

std::string RenderConfig::getLastError() const {
    return pImpl->last_error;
}

bool RenderConfig::validate() const {
    // Basic validation
    if (pImpl->data.analysis.data_path.empty()) {
        return false;
    }
    if (pImpl->data.analysis.output_path.empty()) {
        return false;
    }
    return true;
}

// ============================================================
// Helper Methods - Type Conversions
// ============================================================

FringeType RenderConfig::stringToFringeType(const std::string& type) const {
    // Stress components (LSPrePost IDs: 1-6)
    if (type == "x_stress" || type == "stress_xx" || type == "sigma_xx") return FringeType::STRESS_XX;
    if (type == "y_stress" || type == "stress_yy" || type == "sigma_yy") return FringeType::STRESS_YY;
    if (type == "z_stress" || type == "stress_zz" || type == "sigma_zz") return FringeType::STRESS_ZZ;
    if (type == "xy_stress" || type == "stress_xy" || type == "sigma_xy") return FringeType::STRESS_XY;
    if (type == "yz_stress" || type == "stress_yz" || type == "sigma_yz") return FringeType::STRESS_YZ;
    if (type == "zx_stress" || type == "xz_stress" || type == "stress_xz" || type == "stress_zx" || type == "sigma_xz") return FringeType::STRESS_XZ;

    // Plastic strain (LSPrePost ID: 7)
    if (type == "effective_plastic_strain" || type == "plastic_strain") return FringeType::EFFECTIVE_PLASTIC_STRAIN;

    // Pressure (LSPrePost ID: 8)
    if (type == "pressure") return FringeType::PRESSURE;

    // Von Mises stress (LSPrePost ID: 9)
    if (type == "von_mises" || type == "von_mises_stress") return FringeType::VON_MISES;

    // Max shear stress (LSPrePost ID: 13)
    if (type == "max_shear_stress") return FringeType::MAX_SHEAR_STRESS;

    // Principal stresses (LSPrePost IDs: 14-16)
    if (type == "principal_stress_1" || type == "principal_1") return FringeType::PRINCIPAL_STRESS_1;
    if (type == "principal_stress_2" || type == "principal_2") return FringeType::PRINCIPAL_STRESS_2;
    if (type == "principal_stress_3" || type == "principal_3") return FringeType::PRINCIPAL_STRESS_3;

    // Displacement components (LSPrePost IDs: 17-20)
    if (type == "x_displacement" || type == "displacement_x" || type == "disp_x") return FringeType::DISPLACEMENT_X;
    if (type == "y_displacement" || type == "displacement_y" || type == "disp_y") return FringeType::DISPLACEMENT_Y;
    if (type == "z_displacement" || type == "displacement_z" || type == "disp_z") return FringeType::DISPLACEMENT_Z;
    if (type == "result_displacement" || type == "displacement" || type == "resultant_displacement") return FringeType::DISPLACEMENT;

    // Velocity and Acceleration (LSPrePost IDs: 23-24)
    if (type == "result_acceleration" || type == "acceleration") return FringeType::ACCELERATION;
    if (type == "result_velocity" || type == "velocity") return FringeType::VELOCITY;

    // Energy (LSPrePost ID: 43)
    if (type == "hourglass_energy_density") return FringeType::HOURGLASS_ENERGY_DENSITY;

    // Strain components (LSPrePost IDs: 57-62)
    if (type == "x_strain" || type == "strain_xx") return FringeType::STRAIN_XX;
    if (type == "y_strain" || type == "strain_yy") return FringeType::STRAIN_YY;
    if (type == "z_strain" || type == "strain_zz") return FringeType::STRAIN_ZZ;
    if (type == "xy_strain" || type == "strain_xy") return FringeType::STRAIN_XY;
    if (type == "yz_strain" || type == "strain_yz") return FringeType::STRAIN_YZ;
    if (type == "zx_strain" || type == "xz_strain" || type == "strain_xz" || type == "strain_zx") return FringeType::STRAIN_XZ;

    // Shell properties (LSPrePost ID: 67)
    if (type == "shell_thickness" || type == "thickness") return FringeType::SHELL_THICKNESS;

    // Principal strains (LSPrePost IDs: 77-79)
    if (type == "principal_strain_1") return FringeType::PRINCIPAL_STRAIN_1;
    if (type == "principal_strain_2") return FringeType::PRINCIPAL_STRAIN_2;
    if (type == "principal_strain_3") return FringeType::PRINCIPAL_STRAIN_3;

    // Effective strain (LSPrePost ID: 80)
    if (type == "effective_strain") return FringeType::EFFECTIVE_STRAIN;

    // Advanced properties (LSPrePost IDs: 520-530)
    if (type == "triaxiality") return FringeType::TRIAXIALITY;
    if (type == "normalized_mean_stress") return FringeType::NORMALIZED_MEAN_STRESS;
    if (type == "strain_energy_density") return FringeType::STRAIN_ENERGY_DENSITY;
    if (type == "volumetric_strain") return FringeType::VOLUMETRIC_STRAIN;
    if (type == "signed_von_mises") return FringeType::SIGNED_VON_MISES;

    return FringeType::VON_MISES; // Default
}

std::string RenderConfig::fringeTypeToString(FringeType type) const {
    switch (type) {
        // Stress components
        case FringeType::STRESS_XX: return "stress_xx";
        case FringeType::STRESS_YY: return "stress_yy";
        case FringeType::STRESS_ZZ: return "stress_zz";
        case FringeType::STRESS_XY: return "stress_xy";
        case FringeType::STRESS_YZ: return "stress_yz";
        case FringeType::STRESS_XZ: return "stress_xz";

        // Plastic strain
        case FringeType::EFFECTIVE_PLASTIC_STRAIN: return "plastic_strain";

        // Pressure
        case FringeType::PRESSURE: return "pressure";

        // Von Mises
        case FringeType::VON_MISES: return "von_mises";

        // Max shear stress
        case FringeType::MAX_SHEAR_STRESS: return "max_shear_stress";

        // Principal stresses
        case FringeType::PRINCIPAL_STRESS_1: return "principal_stress_1";
        case FringeType::PRINCIPAL_STRESS_2: return "principal_stress_2";
        case FringeType::PRINCIPAL_STRESS_3: return "principal_stress_3";

        // Displacement
        case FringeType::DISPLACEMENT_X: return "displacement_x";
        case FringeType::DISPLACEMENT_Y: return "displacement_y";
        case FringeType::DISPLACEMENT_Z: return "displacement_z";
        case FringeType::DISPLACEMENT: return "displacement";

        // Velocity and Acceleration
        case FringeType::ACCELERATION: return "acceleration";
        case FringeType::VELOCITY: return "velocity";

        // Energy
        case FringeType::HOURGLASS_ENERGY_DENSITY: return "hourglass_energy_density";

        // Strain components
        case FringeType::STRAIN_XX: return "strain_xx";
        case FringeType::STRAIN_YY: return "strain_yy";
        case FringeType::STRAIN_ZZ: return "strain_zz";
        case FringeType::STRAIN_XY: return "strain_xy";
        case FringeType::STRAIN_YZ: return "strain_yz";
        case FringeType::STRAIN_XZ: return "strain_xz";

        // Shell properties
        case FringeType::SHELL_THICKNESS: return "shell_thickness";

        // Principal strains
        case FringeType::PRINCIPAL_STRAIN_1: return "principal_strain_1";
        case FringeType::PRINCIPAL_STRAIN_2: return "principal_strain_2";
        case FringeType::PRINCIPAL_STRAIN_3: return "principal_strain_3";

        // Effective strain
        case FringeType::EFFECTIVE_STRAIN: return "effective_strain";

        // Advanced properties
        case FringeType::TRIAXIALITY: return "triaxiality";
        case FringeType::NORMALIZED_MEAN_STRESS: return "normalized_mean_stress";
        case FringeType::STRAIN_ENERGY_DENSITY: return "strain_energy_density";
        case FringeType::VOLUMETRIC_STRAIN: return "volumetric_strain";
        case FringeType::SIGNED_VON_MISES: return "signed_von_mises";

        default: return "von_mises";
    }
}

ViewOrientation RenderConfig::stringToViewOrientation(const std::string& orientation) const {
    if (orientation == "front") return ViewOrientation::FRONT;
    if (orientation == "back") return ViewOrientation::BACK;
    if (orientation == "left") return ViewOrientation::LEFT;
    if (orientation == "right") return ViewOrientation::RIGHT;
    if (orientation == "top") return ViewOrientation::TOP;
    if (orientation == "bottom") return ViewOrientation::BOTTOM;
    if (orientation == "iso" || orientation == "isometric") return ViewOrientation::ISOMETRIC;
    return ViewOrientation::FRONT; // Default
}

std::string RenderConfig::viewOrientationToString(ViewOrientation orientation) const {
    switch (orientation) {
        case ViewOrientation::FRONT: return "front";
        case ViewOrientation::BACK: return "back";
        case ViewOrientation::LEFT: return "left";
        case ViewOrientation::RIGHT: return "right";
        case ViewOrientation::TOP: return "top";
        case ViewOrientation::BOTTOM: return "bottom";
        case ViewOrientation::ISOMETRIC: return "iso";
        case ViewOrientation::CUSTOM: return "custom";
        default: return "front";
    }
}

VideoFormat RenderConfig::stringToVideoFormat(const std::string& format) const {
    if (format == "MP4/H264" || format == "mp4" || format == "h264" || format == "MP4") return VideoFormat::MP4;
    if (format == "WMV" || format == "wmv") return VideoFormat::WMV;
    if (format == "AVI" || format == "avi") return VideoFormat::AVI;
    return VideoFormat::MP4; // Default
}

std::string RenderConfig::videoFormatToString(VideoFormat format) const {
    switch (format) {
        case VideoFormat::MP4: return "MP4";
        case VideoFormat::WMV: return "WMV";
        case VideoFormat::AVI: return "AVI";
        default: return "MP4";
    }
}

AutoSectionMode RenderConfig::stringToAutoSectionMode(const std::string& mode) const {
    // Convert to lowercase for case-insensitive comparison
    std::string lower_mode = mode;
    for (auto& c : lower_mode) c = std::tolower(c);

    if (lower_mode == "single") return AutoSectionMode::SINGLE;
    if (lower_mode == "even_spaced") return AutoSectionMode::EVEN_SPACED;
    if (lower_mode == "uniform_spacing") return AutoSectionMode::UNIFORM_SPACING;
    if (lower_mode == "standard_3") return AutoSectionMode::STANDARD_3;
    if (lower_mode == "offset_edges") return AutoSectionMode::OFFSET_EDGES;
    if (lower_mode == "manual") return AutoSectionMode::MANUAL;
    return AutoSectionMode::MANUAL; // Default
}

std::string RenderConfig::autoSectionModeToString(AutoSectionMode mode) const {
    switch (mode) {
        case AutoSectionMode::MANUAL: return "manual";
        case AutoSectionMode::SINGLE: return "single";
        case AutoSectionMode::EVEN_SPACED: return "even_spaced";
        case AutoSectionMode::UNIFORM_SPACING: return "uniform_spacing";
        case AutoSectionMode::STANDARD_3: return "standard_3";
        case AutoSectionMode::OFFSET_EDGES: return "offset_edges";
        default: return "manual";
    }
}

} // namespace render
} // namespace kood3plot
