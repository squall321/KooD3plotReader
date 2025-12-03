/**
 * @file kood3plot_cli.cpp
 * @brief Command-line interface for KooD3plot V3 Query System
 * @author KooD3plot V3 Development Team
 * @date 2025-11-22
 * @version 3.0.0
 *
 * Usage:
 *   kood3plot_cli [options] <d3plot_file>
 */

#include <iostream>
#include <string>
#include <vector>
#include <cstdlib>
#include <fstream>
#include <algorithm>
#include <set>

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/query/D3plotQuery.h"
#include "kood3plot/query/QueryResult.h"
#include "kood3plot/query/PartSelector.h"
#include "kood3plot/query/QuantitySelector.h"
#include "kood3plot/query/TimeSelector.h"
#include "kood3plot/query/ValueFilter.h"
#include "kood3plot/query/OutputSpec.h"
#include "kood3plot/query/ConfigParser.h"
#include "kood3plot/query/QueryTemplate.h"
#include "kood3plot/query/TemplateManager.h"
#include "writers/CSVWriter.h"
#include "writers/JSONWriter.h"
#include "writers/HDF5Writer.h"

// V4 Render System
#include "kood3plot/render/LSPrePostRenderer.h"
#include "kood3plot/render/BatchRenderer.h"
#include "kood3plot/render/RenderConfig.h"
#include "kood3plot/render/GeometryAnalyzer.h"
#include "kood3plot/render/MultiRunProcessor.h"

// Export utilities
#include "kood3plot/export/KeywordExporter.h"

using namespace kood3plot;
using namespace kood3plot::export_utils;
using namespace kood3plot::query;
using namespace kood3plot::render;

// ============================================================
// CLI Options Structure
// ============================================================

struct CLIOptions {
    std::string d3plot_path;
    std::string config_file;
    std::string output_file = "output.csv";
    std::string output_format = "csv";
    std::string template_name;

    std::vector<std::string> parts;
    std::vector<std::string> quantities;

    int first_state = -1;
    int last_state = -1;
    int state_step = 1;

    double time_start = -1.0;
    double time_end = -1.0;

    double min_value = 0.0;
    double max_value = 0.0;
    bool has_min_filter = false;
    bool has_max_filter = false;

    bool verbose = false;
    bool show_info = false;
    bool list_parts = false;
    bool list_templates = false;
    bool help = false;

    // V4 Render options
    std::string mode = "query";  // query, render, batch, multisection, autosection, multirun
    bool render = false;
    bool animate = false;
    std::string lsprepost_path = "lsprepost";
    std::string render_output = "render.png";
    std::string view = "isometric";
    std::string fringe = "von_mises";

    // Section plane: point (px, py, pz) and normal (nx, ny, nz)
    bool has_section_plane = false;
    double section_px = 0.0, section_py = 0.0, section_pz = 0.0;
    double section_nx = 0.0, section_ny = 0.0, section_nz = 1.0;

    // Multi-run options
    int num_threads = 4;
    std::vector<std::string> run_configs;  // Config files for multi-run
    std::string comparison_output = "comparison";

    // Export options (k-file export)
    std::string export_format = "deformed";  // deformed, displacement
    bool export_all_states = false;
    bool export_combined = false;
};

// ============================================================
// Help Message
// ============================================================

void printHelp() {
    std::cout << R"(
KooD3plot CLI - Unified Command Line Interface
===============================================

Usage: kood3plot_cli --mode <mode> [options] <d3plot_file>

Modes:
  --mode query             Data extraction mode (default)
  --mode render            Single image rendering
  --mode batch             Batch rendering with config file
  --mode multisection      Multi-section rendering
  --mode autosection       Automatic section generation
  --mode multirun          Multi-run parallel processing and comparison
  --mode export            Export displacement to LS-DYNA keyword file (.k)

Input Options:
  <d3plot_file>            Path to d3plot file (required unless --config used)
  -c, --config <file>      Load configuration from YAML/JSON file

Output Options:
  -o, --output <file>      Output file path (default: output.csv)
  --format <fmt>           Output format: csv, json, hdf5 (default: csv)

Selection Options (Query Mode):
  -p, --part <name>        Select part by name (can be used multiple times)
  -q, --quantity <name>    Select quantity (can be used multiple times)
                          Options: von_mises, displacement, stress, strain, etc.

Time Selection (Query Mode):
  --first <n>              First state index (0-based)
  --last <n>               Last state index (-1 for last)
  --step <n>               State step interval

Filtering (Query Mode):
  --min <value>            Minimum value filter
  --max <value>            Maximum value filter

Templates (Query Mode):
  -t, --template <name>    Use predefined query template
  --list-templates         List available templates

Rendering Options (Render/Batch/MultiSection/AutoSection Modes):
  --render-output <file>   Render output file (default: render.png)
  --view <orientation>     View orientation: top, bottom, left, right, front,
                          back, isometric (default: isometric)
  --fringe <type>          Fringe type: von_mises, displacement, stress_xx, etc.
                          (default: von_mises)
  --section-plane <px> <py> <pz> <nx> <ny> <nz>
                          Define section plane with point and normal vector
  --animate                Create animation (MP4/AVI) from all timesteps
  --lsprepost-path <path>  Path to LSPrePost executable (default: lsprepost)

Multi-Run Options (MultiRun Mode):
  --threads <n>            Number of parallel threads (default: 4)
  --run-config <file>      Add run configuration (can be used multiple times)
  --comparison-output <dir> Comparison output directory (default: comparison)

Export Options (Export Mode):
  --export-format <fmt>    Export format: deformed, displacement, stress, stress_csv
                          (default: deformed)
  --export-all             Export all states to separate files
  --export-combined        Export all states to a single combined file

Information:
  --info                   Show d3plot file information
  --list-parts             List all parts in file
  -v, --verbose            Verbose output
  -h, --help               Show this help message

Examples:
  # Query mode (data extraction)
  kood3plot_cli --mode query -q von_mises -p Hood input.d3plot -o stress.csv
  kood3plot_cli --config analysis.yaml
  kood3plot_cli --template max_stress_history input.d3plot

  # Render mode (single image)
  kood3plot_cli --mode render --view isometric input.d3plot -o image.png
  kood3plot_cli --mode render --section-plane 0 0 0 0 0 1 input.d3plot

  # Batch mode (config-based rendering)
  kood3plot_cli --mode batch --config render_config.json input.d3plot

  # Multi-section mode (multiple sections at once)
  kood3plot_cli --mode multisection --config sections.json input.d3plot

  # Auto-section mode (automatic section generation)
  kood3plot_cli --mode autosection input.d3plot

  # Multi-run mode (parallel processing and comparison)
  kood3plot_cli --mode multirun --run-config run1.json --run-config run2.json \
                --threads 4 --comparison-output results/

  # Export mode (LS-DYNA keyword file export)
  kood3plot_cli --mode export input.d3plot -o state.k
  kood3plot_cli --mode export --export-all input.d3plot -o states.k
  kood3plot_cli --mode export --export-format displacement input.d3plot -o disp.k
  kood3plot_cli --mode export --first 0 --last 100 --step 10 input.d3plot -o states.k

)";
}

// ============================================================
// Parse Command Line Arguments
// ============================================================

CLIOptions parseArgs(int argc, char* argv[]) {
    CLIOptions opts;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];

        if (arg == "-h" || arg == "--help") {
            opts.help = true;
        } else if (arg == "-v" || arg == "--verbose") {
            opts.verbose = true;
        } else if (arg == "--info") {
            opts.show_info = true;
        } else if (arg == "--list-parts") {
            opts.list_parts = true;
        } else if (arg == "--list-templates") {
            opts.list_templates = true;
        } else if ((arg == "-c" || arg == "--config") && i + 1 < argc) {
            opts.config_file = argv[++i];
        } else if ((arg == "-o" || arg == "--output") && i + 1 < argc) {
            opts.output_file = argv[++i];
        } else if (arg == "--format" && i + 1 < argc) {
            opts.output_format = argv[++i];
        } else if ((arg == "-p" || arg == "--part") && i + 1 < argc) {
            opts.parts.push_back(argv[++i]);
        } else if ((arg == "-q" || arg == "--quantity") && i + 1 < argc) {
            opts.quantities.push_back(argv[++i]);
        } else if ((arg == "-t" || arg == "--template") && i + 1 < argc) {
            opts.template_name = argv[++i];
        } else if (arg == "--first" && i + 1 < argc) {
            opts.first_state = std::stoi(argv[++i]);
        } else if (arg == "--last" && i + 1 < argc) {
            opts.last_state = std::stoi(argv[++i]);
        } else if (arg == "--step" && i + 1 < argc) {
            opts.state_step = std::stoi(argv[++i]);
        } else if (arg == "--min" && i + 1 < argc) {
            opts.min_value = std::stod(argv[++i]);
            opts.has_min_filter = true;
        } else if (arg == "--max" && i + 1 < argc) {
            opts.max_value = std::stod(argv[++i]);
            opts.has_max_filter = true;
        } else if (arg == "--render") {
            opts.render = true;
        } else if (arg == "--animate") {
            opts.animate = true;
        } else if (arg == "--render-output" && i + 1 < argc) {
            opts.render_output = argv[++i];
        } else if (arg == "--view" && i + 1 < argc) {
            opts.view = argv[++i];
        } else if (arg == "--fringe" && i + 1 < argc) {
            opts.fringe = argv[++i];
        } else if (arg == "--lsprepost-path" && i + 1 < argc) {
            opts.lsprepost_path = argv[++i];
        } else if (arg == "--section-plane" && i + 6 < argc) {
            opts.has_section_plane = true;
            opts.section_px = std::stod(argv[++i]);
            opts.section_py = std::stod(argv[++i]);
            opts.section_pz = std::stod(argv[++i]);
            opts.section_nx = std::stod(argv[++i]);
            opts.section_ny = std::stod(argv[++i]);
            opts.section_nz = std::stod(argv[++i]);
        } else if (arg == "--mode" && i + 1 < argc) {
            opts.mode = argv[++i];
        } else if (arg == "--threads" && i + 1 < argc) {
            opts.num_threads = std::stoi(argv[++i]);
        } else if (arg == "--run-config" && i + 1 < argc) {
            opts.run_configs.push_back(argv[++i]);
        } else if (arg == "--comparison-output" && i + 1 < argc) {
            opts.comparison_output = argv[++i];
        } else if (arg == "--export-format" && i + 1 < argc) {
            opts.export_format = argv[++i];
        } else if (arg == "--export-all") {
            opts.export_all_states = true;
        } else if (arg == "--export-combined") {
            opts.export_combined = true;
        } else if (arg[0] != '-' && opts.d3plot_path.empty()) {
            opts.d3plot_path = arg;
        }
    }

    // Backward compatibility: --render flag sets mode to "render"
    if (opts.render) {
        opts.mode = "render";
    }

    return opts;
}

// ============================================================
// Show File Info
// ============================================================

void showFileInfo(D3plotReader& reader) {
    std::cout << "\n=== D3plot File Information ===\n\n";

    auto control = reader.get_control_data();

    std::cout << "Title: " << control.TITLE << "\n\n";

    std::cout << "Mesh Statistics:\n";
    std::cout << "  Nodes: " << control.NUMNP << "\n";
    std::cout << "  Solid elements: " << control.NEL8 << "\n";
    std::cout << "  Shell elements: " << control.NEL4 << "\n";
    std::cout << "  Beam elements: " << control.NEL2 << "\n\n";

    std::cout << "States: " << reader.get_num_states() << "\n";
    std::cout << "\n";
}

// ============================================================
// List Parts
// ============================================================

void listParts(D3plotReader& reader) {
    std::cout << "\n=== Parts in D3plot ===\n\n";

    auto mesh = reader.read_mesh();
    auto control = reader.get_control_data();

    // List unique part IDs from mesh
    std::set<int32_t> unique_parts;
    for (auto p : mesh.solid_parts) unique_parts.insert(p);
    for (auto p : mesh.shell_parts) unique_parts.insert(p);
    for (auto p : mesh.beam_parts) unique_parts.insert(p);

    std::cout << "Part IDs found:\n";
    for (auto id : unique_parts) {
        std::cout << "  Part " << id << "\n";
    }
    std::cout << "\nTotal: " << unique_parts.size() << " parts\n\n";
}

// ============================================================
// List Templates
// ============================================================

void listTemplates() {
    std::cout << "\n=== Available Query Templates ===\n\n";

    auto& manager = TemplateManager::instance();
    manager.printTemplateList(std::cout, false);
}

// ============================================================
// Execute Query
// ============================================================

int executeQuery(const CLIOptions& opts) {
    if (opts.verbose) {
        std::cout << "Opening d3plot file: " << opts.d3plot_path << "\n";
    }

    // Open d3plot file
    D3plotReader reader(opts.d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error: Cannot open d3plot file: " << opts.d3plot_path << "\n";
        return 1;
    }

    if (opts.verbose) {
        std::cout << "File opened successfully\n";
        std::cout << "  States: " << reader.get_num_states() << "\n";
    }

    // Build query
    D3plotQuery query(reader);

    // Part selection
    if (!opts.parts.empty()) {
        PartSelector parts;
        for (const auto& p : opts.parts) {
            parts.byName(p);
        }
        query.selectParts(parts);

        if (opts.verbose) {
            std::cout << "Selected parts: " << opts.parts.size() << "\n";
        }
    }

    // Quantity selection
    if (!opts.quantities.empty()) {
        QuantitySelector qty;
        for (const auto& q : opts.quantities) {
            std::string ql = q;
            std::transform(ql.begin(), ql.end(), ql.begin(), ::tolower);

            if (ql == "von_mises" || ql == "vonmises") {
                qty.vonMises();
            } else if (ql == "displacement" || ql == "disp") {
                qty.displacement();
            } else if (ql == "stress") {
                qty.allStress();
            } else if (ql == "strain") {
                qty.allStrain();
            } else if (ql == "effective_strain") {
                qty.effectiveStrain();
            }
        }
        query.selectQuantities(qty);

        if (opts.verbose) {
            std::cout << "Selected quantities: " << opts.quantities.size() << "\n";
        }
    } else {
        // Default to von Mises
        query.selectQuantities(QuantitySelector().vonMises());
    }

    // Time selection
    TimeSelector time;
    if (opts.first_state >= 0 || opts.last_state >= 0) {
        int first = (opts.first_state >= 0) ? opts.first_state : 0;
        int last = (opts.last_state >= 0) ? opts.last_state : -1;
        time.addStateRange(first, last, opts.state_step);
    } else {
        time.all();
    }
    query.selectTime(time);

    // Value filter
    if (opts.has_min_filter || opts.has_max_filter) {
        ValueFilter filter;
        if (opts.has_min_filter) {
            filter.greaterThan(opts.min_value);
        }
        if (opts.has_max_filter) {
            filter.lessThan(opts.max_value);
        }
        query.whereValue(filter);

        if (opts.verbose) {
            std::cout << "Value filter applied\n";
        }
    }

    // Execute query
    if (opts.verbose) {
        std::cout << "Executing query...\n";
    }

    auto result = query.execute();

    if (opts.verbose) {
        std::cout << "Query complete: " << result.size() << " data points\n";
    }

    // Write output
    if (opts.verbose) {
        std::cout << "Writing output to: " << opts.output_file << "\n";
    }

    std::string fmt = opts.output_format;
    std::transform(fmt.begin(), fmt.end(), fmt.begin(), ::tolower);

    if (fmt == "json") {
        writers::JSONWriter writer(opts.output_file);
        writer.write(result);
    } else if (fmt == "hdf5" || fmt == "h5") {
        writers::HDF5Writer writer;
        if (!writer.write(result, opts.output_file)) {
            std::cerr << "Error writing HDF5 output\n";
            return 1;
        }
    } else {
        // Default to CSV
        writers::CSVWriter writer(opts.output_file);
        writer.write(result);
    }

    std::cout << "Output written to: " << opts.output_file << "\n";
    std::cout << "Total data points: " << result.size() << "\n";

    return 0;
}

// ============================================================
// Execute Render
// ============================================================

int executeRender(const CLIOptions& opts) {
    if (opts.verbose) {
        std::cout << "Render mode enabled\n";
        std::cout << "D3plot file: " << opts.d3plot_path << "\n";
        std::cout << "LSPrePost: " << opts.lsprepost_path << "\n";
    }

    // Create renderer
    LSPrePostRenderer renderer(opts.lsprepost_path);

    // Setup render options
    RenderOptions options;

    // Set view orientation
    std::string view_lower = opts.view;
    std::transform(view_lower.begin(), view_lower.end(), view_lower.begin(), ::tolower);

    if (view_lower == "top") {
        options.view = ViewOrientation::TOP;
    } else if (view_lower == "bottom") {
        options.view = ViewOrientation::BOTTOM;
    } else if (view_lower == "left") {
        options.view = ViewOrientation::LEFT;
    } else if (view_lower == "right") {
        options.view = ViewOrientation::RIGHT;
    } else if (view_lower == "front") {
        options.view = ViewOrientation::FRONT;
    } else if (view_lower == "back") {
        options.view = ViewOrientation::BACK;
    } else if (view_lower == "isometric") {
        options.view = ViewOrientation::ISOMETRIC;
    } else {
        std::cerr << "Warning: Unknown view '" << opts.view << "', using isometric\n";
        options.view = ViewOrientation::ISOMETRIC;
    }

    // Set fringe type
    std::string fringe_lower = opts.fringe;
    std::transform(fringe_lower.begin(), fringe_lower.end(), fringe_lower.begin(), ::tolower);

    if (fringe_lower == "von_mises" || fringe_lower == "vonmises") {
        options.fringe_type = FringeType::VON_MISES;
    } else if (fringe_lower == "displacement" || fringe_lower == "disp") {
        options.fringe_type = FringeType::DISPLACEMENT;
    } else if (fringe_lower == "stress_xx") {
        options.fringe_type = FringeType::STRESS_XX;
    } else if (fringe_lower == "stress_yy") {
        options.fringe_type = FringeType::STRESS_YY;
    } else if (fringe_lower == "stress_zz") {
        options.fringe_type = FringeType::STRESS_ZZ;
    } else if (fringe_lower == "stress_xy") {
        options.fringe_type = FringeType::STRESS_XY;
    } else if (fringe_lower == "stress_yz") {
        options.fringe_type = FringeType::STRESS_YZ;
    } else if (fringe_lower == "stress_xz") {
        options.fringe_type = FringeType::STRESS_XZ;
    } else if (fringe_lower == "effective_strain") {
        options.fringe_type = FringeType::EFFECTIVE_STRAIN;
    } else {
        std::cerr << "Warning: Unknown fringe '" << opts.fringe << "', using von_mises\n";
        options.fringe_type = FringeType::VON_MISES;
    }

    // Set output format
    std::string ext = opts.render_output.substr(opts.render_output.find_last_of('.') + 1);
    std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);

    if (ext == "png") {
        options.image_format = ImageFormat::PNG;
    } else if (ext == "jpg" || ext == "jpeg") {
        options.image_format = ImageFormat::JPG;
    } else if (ext == "bmp") {
        options.image_format = ImageFormat::BMP;
    } else if (ext == "tiff" || ext == "tif") {
        options.image_format = ImageFormat::TIFF;
    }

    // Set animation
    if (opts.animate) {
        options.create_animation = true;
        if (ext == "mp4") {
            options.video_format = VideoFormat::MP4;
        } else if (ext == "avi") {
            options.video_format = VideoFormat::AVI;
        } else if (ext == "wmv") {
            options.video_format = VideoFormat::WMV;
        } else {
            options.video_format = VideoFormat::MP4;  // Default
        }
    }

    // Add section plane if specified
    if (opts.has_section_plane) {
        render::SectionPlane plane;
        plane.point = {opts.section_px, opts.section_py, opts.section_pz};
        plane.normal = {opts.section_nx, opts.section_ny, opts.section_nz};
        plane.visible = true;
        options.section_planes.push_back(plane);

        if (opts.verbose) {
            std::cout << "Section plane defined:\n";
            std::cout << "  Point: (" << plane.point[0] << ", "
                      << plane.point[1] << ", " << plane.point[2] << ")\n";
            std::cout << "  Normal: (" << plane.normal[0] << ", "
                      << plane.normal[1] << ", " << plane.normal[2] << ")\n";
        }
    }

    // Execute render
    bool success = false;

    if (opts.verbose) {
        std::cout << "Starting render...\n";
        std::cout << "  View: " << opts.view << "\n";
        std::cout << "  Fringe: " << opts.fringe << "\n";
        std::cout << "  Output: " << opts.render_output << "\n";
        if (opts.animate) {
            std::cout << "  Animation: enabled\n";
        }
    }

    if (opts.animate) {
        success = renderer.renderAnimation(opts.d3plot_path, opts.render_output, options);
    } else if (opts.has_section_plane) {
        success = renderer.renderSectionView(opts.d3plot_path, opts.render_output,
                                            options.section_planes[0], options);
    } else {
        success = renderer.renderImage(opts.d3plot_path, opts.render_output, options);
    }

    if (success) {
        std::cout << "✓ Render successful!\n";
        std::cout << "  Output: " << opts.render_output << "\n";
        return 0;
    } else {
        std::cerr << "✗ Render failed!\n";
        std::cerr << "  Error: " << renderer.getLastError() << "\n";
        return 1;
    }
}

// ============================================================
// Helper: Load Config File (auto-detect JSON/YAML)
// ============================================================

bool loadConfigFile(RenderConfig& config, const std::string& file_path) {
    // Detect file type by extension
    std::string ext;
    size_t dot_pos = file_path.find_last_of('.');
    if (dot_pos != std::string::npos) {
        ext = file_path.substr(dot_pos + 1);
        std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
    }

    if (ext == "yaml" || ext == "yml") {
        return config.loadFromYAML(file_path);
    } else {
        // Default to JSON
        return config.loadFromJSON(file_path);
    }
}

// ============================================================
// Execute Batch Mode
// ============================================================

int executeBatch(const CLIOptions& opts) {
    if (opts.config_file.empty()) {
        std::cerr << "Error: Batch mode requires --config <file>\n";
        return 1;
    }

    if (opts.verbose) {
        std::cout << "Batch rendering mode\n";
        std::cout << "Config file: " << opts.config_file << "\n";
        std::cout << "D3plot file: " << opts.d3plot_path << "\n";
    }

    // Load config (auto-detect JSON/YAML)
    RenderConfig config;
    if (!loadConfigFile(config, opts.config_file)) {
        std::cerr << "Error: Failed to load config from " << opts.config_file << "\n";
        std::cerr << "Error details: " << config.getLastError() << "\n";
        return 1;
    }

    // Create batch renderer
    BatchRenderer renderer(opts.lsprepost_path);

    // Open d3plot
    D3plotReader reader(opts.d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error: Cannot open d3plot file: " << opts.d3plot_path << "\n";
        return 1;
    }

    // Convert RenderConfig sections to BatchJobs
    const auto& data = config.getData();
    for (size_t i = 0; i < data.sections.size(); ++i) {
        auto render_opts = config.toRenderOptions(i);

        std::string output_file = opts.output_file;
        if (data.sections.size() > 1) {
            size_t dot_pos = output_file.find_last_of('.');
            std::string base = output_file.substr(0, dot_pos);
            std::string ext = output_file.substr(dot_pos);
            output_file = base + "_" + std::to_string(i) + ext;
        }

        BatchJob job("job_" + std::to_string(i), opts.d3plot_path, output_file, render_opts);
        renderer.addJob(job);
    }

    if (opts.verbose) {
        std::cout << "Starting batch rendering of " << renderer.getJobCount() << " jobs...\n";
    }

    // Execute batch rendering
    size_t completed = renderer.processAll();

    if (opts.verbose) {
        std::cout << "Batch rendering completed\n";
        std::cout << "Completed: " << completed << " jobs\n";
    }

    auto results = renderer.getSuccessfulJobs();
    for (const auto& result : results) {
        std::cout << "  ✓ " << result.output_path << "\n";
    }

    return (completed == renderer.getJobCount()) ? 0 : 1;
}

// ============================================================
// Execute Multi-Section Mode
// ============================================================

int executeMultiSection(const CLIOptions& opts) {
    if (opts.config_file.empty()) {
        std::cerr << "Error: Multi-section mode requires --config <file>\n";
        return 1;
    }

    if (opts.verbose) {
        std::cout << "Multi-section rendering mode\n";
        std::cout << "Config file: " << opts.config_file << "\n";
        std::cout << "D3plot file: " << opts.d3plot_path << "\n";
    }

    // Load config (auto-detect JSON/YAML)
    RenderConfig config;
    if (!loadConfigFile(config, opts.config_file)) {
        std::cerr << "Error: Failed to load config from " << opts.config_file << "\n";
        std::cerr << "Error details: " << config.getLastError() << "\n";
        return 1;
    }

    // Create renderer
    LSPrePostRenderer renderer(opts.lsprepost_path);

    // Process each section
    const auto& data = config.getData();

    if (data.sections.empty()) {
        std::cerr << "Warning: No sections defined in config\n";
        return 1;
    }

    if (opts.verbose) {
        std::cout << "Processing " << data.sections.size() << " sections...\n";
    }

    for (size_t i = 0; i < data.sections.size(); ++i) {
        auto render_opts = config.toRenderOptions(i);

        std::string output_file = opts.output_file;
        if (data.sections.size() > 1) {
            // Generate unique filename for each section
            size_t dot_pos = output_file.find_last_of('.');
            std::string base = output_file.substr(0, dot_pos);
            std::string ext = output_file.substr(dot_pos);
            output_file = base + "_section_" + std::to_string(i) + ext;
        }

        if (opts.verbose) {
            std::cout << "Rendering section " << i << " -> " << output_file << "\n";
        }

        bool success;
        if (data.output.movie) {
            success = renderer.renderAnimation(opts.d3plot_path, output_file, render_opts);
        } else {
            success = renderer.renderImage(opts.d3plot_path, output_file, render_opts);
        }

        if (!success) {
            std::cerr << "Warning: Section " << i << " failed: " << renderer.getLastError() << "\n";
        } else {
            std::cout << "  ✓ Section " << i << " completed\n";
        }
    }

    return 0;
}

// ============================================================
// Execute Auto-Section Mode
// ============================================================

int executeAutoSection(const CLIOptions& opts) {
    if (opts.verbose) {
        std::cout << "Auto-section mode\n";
        std::cout << "D3plot file: " << opts.d3plot_path << "\n";
    }

    // Open d3plot
    D3plotReader reader(opts.d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error: Cannot open d3plot file: " << opts.d3plot_path << "\n";
        return 1;
    }

    // Create default config
    RenderConfigData data;
    data.analysis.data_path = opts.d3plot_path;
    data.fringe.type = opts.fringe;
    data.fringe.auto_range = true;
    data.output.movie = opts.animate;
    data.view.orientation = opts.view;

    // Add auto-section configuration (all 3 axes, center positions)
    const char* axes[] = {"X", "Y", "Z"};
    for (int idx = 0; idx < 3; ++idx) {
        SectionConfig section;
        section.auto_mode = AutoSectionMode::SINGLE;
        section.auto_params.orientation = axes[idx];
        section.auto_params.position = "center";
        data.sections.push_back(section);
    }

    RenderConfig config;
    config.setData(data);

    // Generate auto-sections
    if (opts.verbose) {
        std::cout << "Generating automatic sections...\n";
    }

    config.generateAutoSections(reader, 0);

    if (opts.verbose) {
        std::cout << "Generated " << config.getData().sections.size() << " sections\n";
    }

    // Render each section
    LSPrePostRenderer renderer(opts.lsprepost_path);

    for (size_t i = 0; i < config.getData().sections.size(); ++i) {
        auto render_opts = config.toRenderOptions(i);

        std::string output_file = opts.output_file;
        size_t dot_pos = output_file.find_last_of('.');
        std::string base = output_file.substr(0, dot_pos);
        std::string ext = output_file.substr(dot_pos);
        output_file = base + "_auto_" + std::to_string(i) + ext;

        if (opts.verbose) {
            std::cout << "Rendering auto-section " << i << " -> " << output_file << "\n";
        }

        bool success;
        if (data.output.movie) {
            success = renderer.renderAnimation(opts.d3plot_path, output_file, render_opts);
        } else {
            success = renderer.renderImage(opts.d3plot_path, output_file, render_opts);
        }

        if (!success) {
            std::cerr << "Warning: Auto-section " << i << " failed\n";
        } else {
            std::cout << "  ✓ Auto-section " << i << " completed\n";
        }
    }

    return 0;
}

// ============================================================
// Execute Multi-Run Mode
// ============================================================

int executeMultiRun(const CLIOptions& opts) {
    if (opts.run_configs.empty()) {
        std::cerr << "Error: Multi-run mode requires --run-config <file> (can be used multiple times)\n";
        return 1;
    }

    if (opts.verbose) {
        std::cout << "Multi-run mode\n";
        std::cout << "Number of runs: " << opts.run_configs.size() << "\n";
        std::cout << "Threads: " << opts.num_threads << "\n";
    }

    // Create multi-run processor
    MultiRunProcessor processor(opts.lsprepost_path, opts.num_threads);

    ProcessorOptions proc_opts;
    proc_opts.enable_parallel = true;
    proc_opts.max_threads = opts.num_threads;
    proc_opts.verbose = opts.verbose;
    processor.setOptions(proc_opts);

    // Load and add each run
    for (size_t i = 0; i < opts.run_configs.size(); ++i) {
        const std::string& config_file = opts.run_configs[i];

        if (opts.verbose) {
            std::cout << "Loading run " << i << ": " << config_file << "\n";
        }

        RenderConfig config;
        if (!loadConfigFile(config, config_file)) {
            std::cerr << "Error: Failed to load config from " << config_file << "\n";
            std::cerr << "Error details: " << config.getLastError() << "\n";
            continue;
        }

        RunData run;
        run.run_id = "run_" + std::to_string(i);
        run.d3plot_path = opts.d3plot_path;
        run.output_dir = opts.comparison_output + "/run_" + std::to_string(i);
        run.config = std::move(config);

        processor.addRun(std::move(run));
    }

    // Set up progress callback
    auto progress_callback = [](const MultiRunProgressStatus& status) {
        // Progress updates handled internally by MultiRunProcessor
    };

    processor.setProgressCallback(progress_callback);

    // Process all runs in parallel
    if (opts.verbose) {
        std::cout << "\nProcessing " << processor.getRunCount() << " runs in parallel...\n\n";
    }

    processor.processInParallel(progress_callback);

    // Generate comparison report
    std::string report_file = opts.comparison_output + "/comparison_report.txt";
    std::string csv_file = opts.comparison_output + "/results.csv";

    processor.saveComparisonReport(report_file);
    processor.saveResultsCSV(csv_file);

    if (opts.verbose) {
        std::cout << "\nComparison analysis complete!\n";
        std::cout << "  Report: " << report_file << "\n";
        std::cout << "  CSV: " << csv_file << "\n";
    }

    // Show summary
    auto results = processor.getResults();
    size_t success_count = 0;
    for (const auto& pair : results) {
        if (pair.second.success) ++success_count;
    }

    std::cout << "\nSummary:\n";
    std::cout << "  Total runs: " << results.size() << "\n";
    std::cout << "  Successful: " << success_count << "\n";
    std::cout << "  Failed: " << (results.size() - success_count) << "\n";

    return (success_count == results.size()) ? 0 : 1;
}

// ============================================================
// Execute Export Mode (LS-DYNA Keyword File Export)
// ============================================================

int executeExport(const CLIOptions& opts) {
    if (opts.verbose) {
        std::cout << "Export mode: LS-DYNA keyword file export\n";
        std::cout << "D3plot file: " << opts.d3plot_path << "\n";
        std::cout << "Export format: " << opts.export_format << "\n";
    }

    // Open d3plot file
    D3plotReader reader(opts.d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error: Cannot open d3plot file: " << opts.d3plot_path << "\n";
        return 1;
    }

    // Read mesh
    if (opts.verbose) {
        std::cout << "Reading mesh data...\n";
    }
    auto mesh = reader.read_mesh();

    if (opts.verbose) {
        std::cout << "  Nodes: " << mesh.nodes.size() << "\n";
        std::cout << "  Real node IDs: " << mesh.real_node_ids.size() << "\n";
    }

    // Create exporter
    KeywordExporter exporter(mesh);

    // Setup export options
    KeywordExportOptions export_opts;

    // Parse export format
    std::string fmt = opts.export_format;
    std::transform(fmt.begin(), fmt.end(), fmt.begin(), ::tolower);

    if (fmt == "deformed" || fmt == "node_deformed") {
        export_opts.format = KeywordFormat::NODE_DEFORMED;
    } else if (fmt == "displacement" || fmt == "disp" || fmt == "node_displacement") {
        export_opts.format = KeywordFormat::NODE_DISPLACEMENT;
    } else if (fmt == "velocity" || fmt == "initial_velocity") {
        export_opts.format = KeywordFormat::INITIAL_VELOCITY;
    } else if (fmt == "stress" || fmt == "initial_stress_solid") {
        export_opts.format = KeywordFormat::INITIAL_STRESS_SOLID;
    } else if (fmt == "stress_csv" || fmt == "element_stress_csv") {
        export_opts.format = KeywordFormat::ELEMENT_STRESS_CSV;
    } else {
        std::cerr << "Warning: Unknown export format '" << opts.export_format << "', using 'deformed'\n";
        export_opts.format = KeywordFormat::NODE_DEFORMED;
    }

    // Set export parameters from control data
    auto cd = reader.get_control_data();
    export_opts.IU = cd.IU;            // IU flag for coordinate handling
    export_opts.NV3D = cd.NV3D;        // Number of variables per solid element
    export_opts.num_solids = cd.NEL8;  // Number of solid elements

    // Get total states by reading time values
    auto time_values = reader.get_time_values();
    size_t num_states = time_values.size();
    if (opts.verbose) {
        std::cout << "  Total states: " << num_states << "\n";
    }

    if (num_states == 0) {
        std::cerr << "Error: No states found in d3plot\n";
        return 1;
    }

    // Determine which states to export
    int first_state = (opts.first_state >= 0) ? opts.first_state : 0;
    int last_state = (opts.last_state >= 0) ? opts.last_state : static_cast<int>(num_states) - 1;
    int state_step = opts.state_step;

    // Clamp values
    first_state = std::max(0, std::min(first_state, static_cast<int>(num_states) - 1));
    last_state = std::max(0, std::min(last_state, static_cast<int>(num_states) - 1));

    if (opts.verbose) {
        std::cout << "  Export range: state " << first_state << " to " << last_state;
        std::cout << " (step=" << state_step << ")\n";
    }

    // Build list of state indices to export
    std::vector<int> state_indices;
    for (int i = first_state; i <= last_state; i += state_step) {
        state_indices.push_back(i);
    }

    if (opts.verbose) {
        std::cout << "  States to export: " << state_indices.size() << "\n\n";
    }

    // Export based on mode
    if (opts.export_all_states || state_indices.size() > 1) {
        // Export all states to separate files or combined file
        std::cout << "Reading all states at once (efficient)...\n";

        // Read all states in one pass (much more efficient than read_state in loop)
        auto all_states = reader.read_all_states();
        std::cout << "  Loaded " << all_states.size() << " states from d3plot\n";

        // Filter to requested indices
        std::vector<data::StateData> states;
        states.reserve(state_indices.size());
        for (int idx : state_indices) {
            if (idx >= 0 && static_cast<size_t>(idx) < all_states.size()) {
                states.push_back(std::move(all_states[idx]));
            }
        }
        std::cout << "  Selected " << states.size() << " states for export\n";

        if (opts.export_combined) {
            // Export all to single combined file
            std::cout << "Exporting combined file...\n";
            export_opts.title = "Combined States Export";

            if (exporter.exportCombined(states, opts.output_file, export_opts)) {
                std::cout << "  [OK] " << opts.output_file << "\n";
            } else {
                std::cerr << "  [FAIL] " << exporter.getLastError() << "\n";
                return 1;
            }
        } else {
            // Export to separate files
            std::cout << "Exporting to separate files...\n";
            export_opts.all_states = true;

            int exported = exporter.exportAllStates(states, opts.output_file, export_opts);
            std::cout << "  Exported " << exported << " files\n";

            if (exported != static_cast<int>(states.size())) {
                std::cerr << "  Warning: Some exports failed\n";
            }
        }
    } else {
        // Export single state
        int state_idx = state_indices.empty() ? 0 : state_indices[0];

        if (opts.verbose) {
            std::cout << "Reading state " << state_idx << "...\n";
        }

        auto state = reader.read_state(state_idx);
        double time_val = (state_idx < static_cast<int>(time_values.size())) ? time_values[state_idx] : 0.0;

        export_opts.title = "State " + std::to_string(state_idx) + " (t=" + std::to_string(time_val) + ")";

        std::cout << "Exporting state " << state_idx << " to " << opts.output_file << "...\n";

        if (exporter.exportState(state, opts.output_file, export_opts)) {
            std::cout << "  [OK] " << opts.output_file << "\n";
        } else {
            std::cerr << "  [FAIL] " << exporter.getLastError() << "\n";
            return 1;
        }
    }

    std::cout << "\nExport complete!\n";
    return 0;
}

// ============================================================
// Main
// ============================================================

int main(int argc, char* argv[]) {
    if (argc < 2) {
        printHelp();
        return 0;
    }

    CLIOptions opts = parseArgs(argc, argv);

    if (opts.help) {
        printHelp();
        return 0;
    }

    if (opts.list_templates) {
        listTemplates();
        return 0;
    }

    // Check if config file is specified
    if (!opts.config_file.empty()) {
        ConfigParser parser;
        auto config = parser.parse(opts.config_file);

        if (!parser.isValid()) {
            std::cerr << "Error parsing config: " << parser.getLastError() << "\n";
            return 1;
        }

        // Override with config values
        if (!config.d3plot_path.empty()) {
            opts.d3plot_path = config.d3plot_path;
        }
        if (!config.output_path.empty()) {
            opts.output_file = config.output_path;
        }
        opts.output_format = config.output_format;
        if (!config.parts.empty()) {
            opts.parts = config.parts;
        }
        if (!config.quantities.empty()) {
            opts.quantities = config.quantities;
        }
    }

    // Validate d3plot path
    if (opts.d3plot_path.empty()) {
        std::cerr << "Error: No d3plot file specified\n";
        std::cerr << "Use -h for help\n";
        return 1;
    }

    // Handle info/list commands
    if (opts.show_info || opts.list_parts) {
        D3plotReader reader(opts.d3plot_path);
        if (reader.open() != ErrorCode::SUCCESS) {
            std::cerr << "Error: Cannot open d3plot file: " << opts.d3plot_path << "\n";
            return 1;
        }

        if (opts.show_info) {
            showFileInfo(reader);
        }
        if (opts.list_parts) {
            listParts(reader);
        }

        return 0;
    }

    // Dispatch based on mode
    std::string mode = opts.mode;
    std::transform(mode.begin(), mode.end(), mode.begin(), ::tolower);

    if (mode == "render") {
        return executeRender(opts);
    } else if (mode == "batch") {
        return executeBatch(opts);
    } else if (mode == "multisection") {
        return executeMultiSection(opts);
    } else if (mode == "autosection") {
        return executeAutoSection(opts);
    } else if (mode == "multirun") {
        return executeMultiRun(opts);
    } else if (mode == "export") {
        return executeExport(opts);
    } else if (mode == "query") {
        return executeQuery(opts);
    } else {
        std::cerr << "Error: Unknown mode '" << opts.mode << "'\n";
        std::cerr << "Valid modes: query, render, batch, multisection, autosection, multirun, export\n";
        return 1;
    }
}
