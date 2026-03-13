/**
 * @file SectionViewConfig.cpp
 * @brief SectionViewConfig implementation with hand-rolled YAML line parser
 *
 * Uses the same line-by-line approach as UnifiedConfigParser — no yaml-cpp needed.
 */

#include "kood3plot/section_render/SectionViewConfig.hpp"
#include <algorithm>
#include <cctype>
#include <fstream>
#include <sstream>

namespace kood3plot {
namespace section_render {

// ============================================================
// buildPlane
// ============================================================

SectionPlane SectionViewConfig::buildPlane() const
{
    if (use_axis) {
        return SectionPlane::fromAxis(axis, point);
    } else {
        return SectionPlane::fromNormal(normal, point);
    }
}

// ============================================================
// Simple YAML parsing helpers (local to this file)
// ============================================================

namespace {

std::string trim(const std::string& s)
{
    size_t b = s.find_first_not_of(" \t\r\n");
    if (b == std::string::npos) return "";
    size_t e = s.find_last_not_of(" \t\r\n");
    return s.substr(b, e - b + 1);
}

// Strip inline comment
std::string stripComment(const std::string& s)
{
    size_t pos = s.find('#');
    return (pos != std::string::npos) ? s.substr(0, pos) : s;
}

// Count leading spaces (indentation level)
int indent(const std::string& s)
{
    int n = 0;
    for (char c : s) {
        if (c == ' ') ++n;
        else break;
    }
    return n;
}

// key: value split
bool splitKV(const std::string& line, std::string& key, std::string& value)
{
    size_t pos = line.find(':');
    if (pos == std::string::npos) return false;
    key   = trim(line.substr(0, pos));
    value = trim(stripComment(line.substr(pos + 1)));
    return true;
}

bool parseBool(const std::string& s)
{
    std::string lower(s.size(), '\0');
    std::transform(s.begin(), s.end(), lower.begin(),
                   [](unsigned char c){ return static_cast<char>(std::tolower(c)); });
    return lower == "true" || lower == "yes" || lower == "1";
}

// Parse [1, 2, 3] into int vector
std::vector<int32_t> parseIntList(const std::string& s)
{
    std::vector<int32_t> result;
    std::string inner = s;
    if (!inner.empty() && inner.front() == '[') inner.erase(0,1);
    if (!inner.empty() && inner.back()  == ']') inner.pop_back();
    std::istringstream iss(inner);
    std::string token;
    while (std::getline(iss, token, ',')) {
        std::string t = trim(token);
        if (!t.empty()) {
            try { result.push_back(std::stoi(t)); } catch(...) {}
        }
    }
    return result;
}

// Parse ["str1", "str2"] into string vector
std::vector<std::string> parseStrList(const std::string& s)
{
    std::vector<std::string> result;
    std::string inner = s;
    if (!inner.empty() && inner.front() == '[') inner.erase(0,1);
    if (!inner.empty() && inner.back()  == ']') inner.pop_back();
    std::istringstream iss(inner);
    std::string token;
    while (std::getline(iss, token, ',')) {
        std::string t = trim(token);
        // Remove surrounding quotes
        if (t.size() >= 2 &&
            ((t.front()=='"' && t.back()=='"') ||
             (t.front()=='\'' && t.back()=='\'')))
            t = t.substr(1, t.size()-2);
        if (!t.empty()) result.push_back(t);
    }
    return result;
}

// Parse [x, y, z] into Vec3
Vec3 parseVec3(const std::string& s)
{
    auto v = parseIntList(s);  // reuse (floats work too via atof)
    // Actually use float version:
    Vec3 out{0,0,0};
    std::string inner = s;
    if (!inner.empty() && inner.front() == '[') inner.erase(0,1);
    if (!inner.empty() && inner.back()  == ']') inner.pop_back();
    std::istringstream iss(inner);
    std::string token;
    int idx = 0;
    while (std::getline(iss, token, ',') && idx < 3) {
        try {
            double val = std::stod(trim(token));
            if (idx==0) out.x=val; else if (idx==1) out.y=val; else out.z=val;
        } catch(...) {}
        ++idx;
    }
    return out;
    (void)v;
}

FieldSelector parseField(const std::string& s)
{
    std::string lower(s.size(), '\0');
    std::transform(s.begin(), s.end(), lower.begin(),
                   [](unsigned char c){ return static_cast<char>(std::tolower(c)); });
    if (lower == "eps" || lower == "eff_plastic_strain" || lower == "effective_plastic_strain")
        return FieldSelector::EffectivePlasticStrain;
    if (lower == "displacement" || lower == "disp")
        return FieldSelector::DisplacementMagnitude;
    if (lower == "pressure")
        return FieldSelector::PressureStress;
    if (lower == "max_shear" || lower == "maxshear")
        return FieldSelector::MaxShearStress;
    return FieldSelector::VonMises;  // default
}

} // anonymous namespace

// ============================================================
// loadFromString
// ============================================================

bool SectionViewConfig::loadFromString(const std::string& yaml_block)
{
    std::istringstream iss(yaml_block);
    std::string line;

    // Track which sub-section we're in
    std::string section;   // "plane", "target_parts", "background_parts", "output"
    PartMatcher* cur_matcher = nullptr;

    while (std::getline(iss, line)) {
        std::string stripped = stripComment(line);
        std::string t = trim(stripped);
        if (t.empty()) continue;

        int ind = indent(stripped);

        std::string key, value;
        if (!splitKV(t, key, value)) continue;

        // Top-level keys (indent == 0 or 2 depending on whether caller stripped the header)
        if (key == "plane")            { section = "plane";            cur_matcher = nullptr; continue; }
        if (key == "target_parts")     { section = "target_parts";     cur_matcher = &target_parts; continue; }
        if (key == "background_parts") { section = "background_parts"; cur_matcher = &background_parts; continue; }
        if (key == "output")           { section = "output";           cur_matcher = nullptr; continue; }

        // Top-level scalar keys
        if (section.empty() || ind <= 2) {
            if (key == "field")          { field = parseField(value); section = ""; continue; }
            if (key == "colormap")       { colormap = ColorMap::parseType(value); section = ""; continue; }
            if (key == "global_range")   { global_range = parseBool(value); section = ""; continue; }
            if (key == "scale_factor")   { try { scale_factor = std::stod(value); } catch(...) {} section = ""; continue; }
            if (key == "supersampling")  { try { supersampling = std::stoi(value); } catch(...) {} section = ""; continue; }
            if (key == "auto_center")    { auto_center = parseBool(value); section = ""; continue; }
            if (key == "auto_slab")      { auto_slab = parseBool(value); section = ""; continue; }
            if (key == "slab_thickness") { try { slab_thickness = std::stod(value); } catch(...) {} section = ""; continue; }
            if (key == "fade_distance")  { try { fade_distance  = std::stod(value); } catch(...) {} section = ""; continue; }
        }

        // Plane sub-keys
        if (section == "plane") {
            if (key == "axis" && !value.empty()) {
                use_axis = true;
                axis = static_cast<char>(std::tolower(static_cast<unsigned char>(value[0])));
            } else if (key == "normal") {
                use_axis = false;
                normal = parseVec3(value);
            } else if (key == "point") {
                point = parseVec3(value);
            }
            continue;
        }

        // Part matcher sub-keys
        if (cur_matcher && (section == "target_parts" || section == "background_parts")) {
            if (key == "ids") {
                for (int32_t id : parseIntList(value))
                    cur_matcher->addById(id);
            } else if (key == "patterns") {
                for (const auto& pat : parseStrList(value))
                    cur_matcher->addByPattern(pat);
            } else if (key == "keywords") {
                for (const auto& kw : parseStrList(value))
                    cur_matcher->addByKeyword(kw);
            }
            continue;
        }

        // Output sub-keys
        if (section == "output") {
            if (key == "width")      { try { width  = std::stoi(value); } catch(...) {} }
            if (key == "height")     { try { height = std::stoi(value); } catch(...) {} }
            if (key == "png_frames") { png_frames = parseBool(value); }
            if (key == "mp4")        { mp4 = parseBool(value); }
            if (key == "fps")        { try { fps = std::stoi(value); } catch(...) {} }
            if (key == "output_dir") {
                output_dir = value;
                // Strip surrounding quotes
                if (output_dir.size() >= 2 &&
                    ((output_dir.front()=='"' && output_dir.back()=='"') ||
                     (output_dir.front()=='\'' && output_dir.back()=='\'')))
                    output_dir = output_dir.substr(1, output_dir.size()-2);
            }
            continue;
        }
    }
    return true;
}

// ============================================================
// loadFromFile
// ============================================================

bool SectionViewConfig::loadFromFile(const std::string& filepath)
{
    std::ifstream ifs(filepath);
    if (!ifs.is_open()) return false;

    std::ostringstream oss;
    oss << ifs.rdbuf();
    std::string content = oss.str();

    // Extract the section_render: block (everything after the key)
    size_t pos = content.find("section_render:");
    if (pos != std::string::npos)
        content = content.substr(pos + std::string("section_render:").size());

    return loadFromString(content);
}

// ============================================================
// loadFromYaml (compat stub)
// ============================================================

bool SectionViewConfig::loadFromYaml(const void* yaml_node)
{
    if (!yaml_node) return false;
    // Treat as pointer to std::string containing the YAML block
    const auto* str = static_cast<const std::string*>(yaml_node);
    return loadFromString(*str);
}

// ============================================================
// exampleYaml
// ============================================================

std::string SectionViewConfig::exampleYaml()
{
    return R"(section_render:
  plane:
    axis: z                    # x | y | z  (or use normal: for arbitrary cut)
    # normal: [0.0, 0.0, 1.0]
    point: [0.0, 0.0, 0.0]    # cut plane passes through this point
  auto_center: true            # auto-move cut point to mesh AABB center along cut axis
  auto_slab: true              # auto-compute slab_thickness from element edge lengths (state 0)
  slab_thickness: 0.0          # +-margin (model units); 0=exact, auto_slab overrides if > 0
  target_parts:
    ids: [1, 2, 3]             # contour coloring (field value -> colormap)
    # patterns: ["*battery*"]
    # keywords: ["cell"]
  background_parts:            # flat categorical color per part
    ids: []                    # empty = auto (all non-target parts become background)
  field: von_mises             # von_mises | eps | displacement | pressure | max_shear
  colormap: fringe             # fringe | rainbow | jet | coolwarm | grayscale
  global_range: true           # red=global max, blue=global min (false=per-frame scale)
  scale_factor: 1.2
  supersampling: 2
  output:
    width: 1920
    height: 1080
    png_frames: true
    mp4: true
    fps: 24
    output_dir: "section_views"
)";
}

} // namespace section_render
} // namespace kood3plot
