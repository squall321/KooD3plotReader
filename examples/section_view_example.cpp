/**
 * @file section_view_example.cpp
 * @brief Standalone CLI for software-rasterized section view rendering
 *
 * This tool runs section_views jobs directly against a d3plot file, bypassing
 * LSPrePost. It requires the project to be built with
 * -DKOOD3PLOT_BUILD_SECTION_RENDER=ON.
 *
 * Usage:
 *   section_view_example --d3plot path/to/d3plot [options]
 *
 * Options:
 *   --d3plot <path>        Path to d3plot file (required)
 *   --config <path>        YAML config file with section_views block
 *   --generate-config      Print example YAML to stdout and exit
 *   --axis <x|y|z>         Cutting plane axis (default: z)
 *   --field <name>         Field to render: von_mises|eps|displacement|
 *                          pressure|max_shear  (default: von_mises)
 *   --output-dir <dir>     Output directory (default: section_views)
 *   --width <px>           Image width  (default: 1920)
 *   --height <px>          Image height (default: 1080)
 *   --no-mp4               Skip MP4 assembly (PNG frames only)
 *   --fps <n>              Frames per second for MP4 (default: 24)
 *
 * Quick example (no config file needed):
 *   section_view_example --d3plot /data/case01/d3plot --axis z \
 *                         --field von_mises --output-dir out/
 */

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/section_render/SectionViewConfig.hpp"
#include "kood3plot/section_render/SectionViewRenderer.hpp"
#include "kood3plot/section_render/NodalAverager.hpp"  // FieldSelector

#include <algorithm>
#include <cctype>
#include <iostream>
#include <string>
#include <cstring>

using namespace kood3plot;
using namespace kood3plot::section_render;

static FieldSelector fieldFromString(const std::string& s)
{
    std::string lo(s.size(), '\0');
    std::transform(s.begin(), s.end(), lo.begin(),
                   [](unsigned char c){ return static_cast<char>(std::tolower(c)); });
    if (lo == "eps" || lo == "eff_plastic_strain") return FieldSelector::EffectivePlasticStrain;
    if (lo == "displacement" || lo == "disp")      return FieldSelector::DisplacementMagnitude;
    if (lo == "pressure")                          return FieldSelector::PressureStress;
    if (lo == "max_shear" || lo == "maxshear")     return FieldSelector::MaxShearStress;
    return FieldSelector::VonMises;
}

static void printUsage(const char* prog)
{
    std::cout <<
        "Usage: " << prog << " --d3plot <path> [options]\n"
        "\n"
        "Options:\n"
        "  --d3plot <path>      d3plot file path (required)\n"
        "  --config <path>      YAML config file (section_views block)\n"
        "  --generate-config    Print example YAML and exit\n"
        "  --axis <x|y|z>       Cut plane axis (default: z)\n"
        "  --field <name>       Field: von_mises|eps|displacement|pressure|max_shear\n"
        "  --output-dir <dir>   Output directory (default: section_views)\n"
        "  --width <px>         Image width  (default: 1920)\n"
        "  --height <px>        Image height (default: 1080)\n"
        "  --no-mp4             PNG frames only, skip MP4 assembly\n"
        "  --fps <n>            MP4 frames per second (default: 24)\n"
        "  --scale <factor>     Viewport scale factor (default: 1.2)\n"
        "  --supersampling <n>  Supersampling (1 or 2, default: 2)\n";
}

int main(int argc, char* argv[])
{
    if (argc < 2) {
        printUsage(argv[0]);
        return 1;
    }

    // ---- Parse CLI ----
    std::string d3plot_path;
    std::string config_path;
    std::string axis_str     = "z";
    std::string field_str    = "von_mises";
    std::string output_dir   = "section_views";
    int   width              = 1920;
    int   height             = 1080;
    bool  make_mp4           = true;
    int   fps                = 24;
    double scale_factor      = 1.2;
    int   supersampling      = 2;
    double slab_thickness    = 0.0;
    double fade_distance     = 0.0;
    bool  generate_config    = false;

    for (int i = 1; i < argc; ++i) {
        auto eq = [&](const char* s){ return std::strcmp(argv[i], s) == 0; };
        auto next = [&]() -> std::string {
            if (i + 1 >= argc) {
                std::cerr << "Missing argument for " << argv[i] << "\n";
                std::exit(1);
            }
            return argv[++i];
        };

        if      (eq("--d3plot"))        d3plot_path   = next();
        else if (eq("--config"))        config_path   = next();
        else if (eq("--axis"))          axis_str      = next();
        else if (eq("--field"))         field_str     = next();
        else if (eq("--output-dir"))    output_dir    = next();
        else if (eq("--width"))         width         = std::stoi(next());
        else if (eq("--height"))        height        = std::stoi(next());
        else if (eq("--fps"))           fps           = std::stoi(next());
        else if (eq("--scale"))         scale_factor  = std::stod(next());
        else if (eq("--supersampling")) supersampling  = std::stoi(next());
        else if (eq("--slab"))          slab_thickness = std::stod(next());
        else if (eq("--fade"))          fade_distance  = std::stod(next());
        else if (eq("--no-mp4"))        make_mp4       = false;
        else if (eq("--generate-config")) generate_config = true;
        else if (eq("--help") || eq("-h")) { printUsage(argv[0]); return 0; }
        else { std::cerr << "Unknown option: " << argv[i] << "\n"; return 1; }
    }

    // ---- --generate-config ----
    if (generate_config) {
        std::cout << SectionViewConfig::exampleYaml();
        return 0;
    }

    if (d3plot_path.empty()) {
        std::cerr << "Error: --d3plot is required\n";
        printUsage(argv[0]);
        return 1;
    }

    // ---- Build SectionViewConfig ----
    SectionViewConfig sv_config;

    if (!config_path.empty()) {
        // Load from file (full YAML with section_render: header)
        if (!sv_config.loadFromFile(config_path)) {
            std::cerr << "Error: cannot parse config file: " << config_path << "\n";
            return 1;
        }
    } else {
        // Build from CLI options
        sv_config.use_axis     = true;
        sv_config.axis         = static_cast<char>(axis_str.empty() ? 'z' : axis_str[0]);
        sv_config.point        = {0, 0, 0};
        sv_config.auto_center    = true;   // always cut through model center by default
        sv_config.slab_thickness = slab_thickness;
        sv_config.fade_distance  = fade_distance;
        sv_config.field          = fieldFromString(field_str);
        sv_config.output_dir   = output_dir;
        sv_config.width        = width;
        sv_config.height       = height;
        sv_config.mp4          = make_mp4;
        sv_config.png_frames   = true;
        sv_config.fps          = fps;
        sv_config.scale_factor = scale_factor;
        sv_config.supersampling = supersampling;
        // target_parts: empty = match all (handled in renderer)
    }

    // ---- Open d3plot ----
    D3plotReader reader(d3plot_path);
    auto ec = reader.open();
    if (ec != ErrorCode::SUCCESS) {
        std::cerr << "Error opening d3plot: " << d3plot_path
                  << " (ErrorCode=" << static_cast<int>(ec) << ")\n";
        return 1;
    }

    std::cout << "d3plot: " << d3plot_path << "\n";
    std::cout << "States: " << reader.get_num_states() << "\n";
    std::cout << "Output: " << sv_config.output_dir << "/\n";
    std::cout << "Rendering...\n";

    // ---- Render ----
    SectionViewRenderer renderer;
    std::string err = renderer.render(reader, sv_config);
    if (!err.empty()) {
        std::cerr << "Render error: " << err << "\n";
        return 1;
    }

    std::cout << "Done.\n";
    return 0;
}
