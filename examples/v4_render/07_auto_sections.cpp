/**
 * @file 07_auto_sections.cpp
 * @brief Demonstrate automatic section generation using GeometryAnalyzer
 *
 * This example shows:
 * - Automatic section calculation based on model geometry
 * - Different section positioning (center, quarters, edges)
 * - Multiple section generation modes (even spaced, uniform spacing, etc.)
 * - YAML configuration for auto-sections
 */

#include <kood3plot/D3plotReader.hpp>
#include <kood3plot/render/LSPrePostRenderer.h>
#include <kood3plot/render/RenderConfig.h>
#include <kood3plot/render/BatchRenderer.h>
#include <iostream>
#include <filesystem>

using namespace kood3plot;
using namespace kood3plot::render;

void printSectionInfo(const std::string& title, const std::vector<SectionPlane>& planes) {
    std::cout << "\n" << title << ":\n";
    std::cout << "  Generated " << planes.size() << " section plane(s):\n";
    for (size_t i = 0; i < planes.size(); ++i) {
        std::cout << "  [" << i+1 << "] Point: ("
                  << planes[i].point[0] << ", "
                  << planes[i].point[1] << ", "
                  << planes[i].point[2] << "), Normal: ("
                  << planes[i].normal[0] << ", "
                  << planes[i].normal[1] << ", "
                  << planes[i].normal[2] << ")\n";
    }
}

int main(int argc, char* argv[]) {
    std::cout << "==============================================\n";
    std::cout << "  KooD3plot V4: Auto-Section Generation Demo\n";
    std::cout << "==============================================\n\n";

    // Check arguments
    std::string d3plot_path = (argc > 1) ? argv[1] : "results/d3plot";
    std::string lsprepost_path = (argc > 2) ? argv[2] : "installed/lsprepost/lspp412_mesa";

    if (!std::filesystem::exists(d3plot_path)) {
        std::cerr << "ERROR: D3plot file not found: " << d3plot_path << "\n";
        std::cerr << "Usage: " << argv[0] << " [d3plot_path] [lsprepost_path]\n";
        return 1;
    }

    try {
        // Open D3plot reader
        D3plotReader reader(d3plot_path);
        auto err = reader.open();
        if (err != kood3plot::ErrorCode::SUCCESS) {
            std::cerr << "ERROR: Failed to open d3plot file\n";
            return 1;
        }
        std::cout << "Opened D3plot: " << d3plot_path << "\n";

        // ================================================================
        // Example 1: Single section at different positions
        // ================================================================
        std::cout << "\n--- Example 1: Single Section at Different Positions ---\n";

        RenderConfig config1;
        RenderConfigData data1;

        data1.analysis.data_path = d3plot_path;
        data1.analysis.output_path = "auto_section_outputs";
        data1.fringe.type = "von_mises";
        data1.fringe.auto_range = true;
        data1.output.movie = true;
        data1.output.width = 1280;
        data1.output.height = 720;
        data1.view.orientation = "iso";

        // Create sections at different positions
        std::vector<std::string> positions = {"center", "quarter_1", "quarter_3", "edge_min", "edge_max"};
        for (const auto& pos : positions) {
            SectionConfig section;
            section.auto_mode = AutoSectionMode::SINGLE;
            section.auto_params.orientation = "Z";
            section.auto_params.position = pos;
            data1.sections.push_back(section);
        }

        config1.setData(data1);

        // Generate auto-sections
        config1.generateAutoSections(reader, 0);

        // Print generated sections
        auto& sections1 = config1.getData().sections;
        for (size_t i = 0; i < sections1.size(); ++i) {
            printSectionInfo("Position: " + positions[i], sections1[i].planes);
        }

        // Save configuration
        config1.saveToYAML("auto_sections_positions.yaml");
        std::cout << "\nSaved configuration to: auto_sections_positions.yaml\n";

        // ================================================================
        // Example 2: Standard 3-section layout (25%, 50%, 75%)
        // ================================================================
        std::cout << "\n--- Example 2: Standard 3-Section Layout ---\n";

        RenderConfig config2;
        RenderConfigData data2;

        data2.analysis.data_path = d3plot_path;
        data2.fringe.type = "effective_strain";
        data2.output.movie = true;
        data2.view.orientation = "front";

        SectionConfig section2;
        section2.auto_mode = AutoSectionMode::STANDARD_3;
        section2.auto_params.orientation = "X";
        data2.sections.push_back(section2);

        config2.setData(data2);
        config2.generateAutoSections(reader, 0);

        printSectionInfo("Standard 3-Section (X-axis)", config2.getData().sections[0].planes);
        config2.saveToYAML("auto_sections_standard3.yaml");

        // ================================================================
        // Example 3: Even-spaced sections
        // ================================================================
        std::cout << "\n--- Example 3: Even-Spaced Sections ---\n";

        RenderConfig config3;
        RenderConfigData data3;

        data3.analysis.data_path = d3plot_path;
        data3.fringe.type = "displacement";
        data3.output.movie = true;
        data3.view.orientation = "left";

        SectionConfig section3;
        section3.auto_mode = AutoSectionMode::EVEN_SPACED;
        section3.auto_params.orientation = "Y";
        section3.auto_params.count = 5;  // 5 evenly-spaced sections
        data3.sections.push_back(section3);

        config3.setData(data3);
        config3.generateAutoSections(reader, 0);

        printSectionInfo("5 Even-Spaced Sections (Y-axis)", config3.getData().sections[0].planes);
        config3.saveToYAML("auto_sections_even5.yaml");

        // ================================================================
        // Example 4: Offset from edges
        // ================================================================
        std::cout << "\n--- Example 4: Offset from Edges ---\n";

        RenderConfig config4;
        RenderConfigData data4;

        data4.analysis.data_path = d3plot_path;
        data4.fringe.type = "stress_xx";
        data4.output.movie = true;
        data4.view.orientation = "top";

        SectionConfig section4;
        section4.auto_mode = AutoSectionMode::OFFSET_EDGES;
        section4.auto_params.orientation = "Z";
        section4.auto_params.offset_percent = 10.0;  // 10% from each edge
        data4.sections.push_back(section4);

        config4.setData(data4);
        config4.generateAutoSections(reader, 0);

        printSectionInfo("Offset 10% from Edges (Z-axis)", config4.getData().sections[0].planes);
        config4.saveToYAML("auto_sections_offset.yaml");

        // ================================================================
        // Example 5: Render one auto-generated section
        // ================================================================
        std::cout << "\n--- Example 5: Rendering Auto-Generated Section ---\n";

        // Use the standard 3-section configuration
        auto render_opts = config2.toRenderOptions(1);  // Use middle section (50%)

        LSPrePostRenderer renderer(lsprepost_path);

        std::cout << "Rendering center section (50%)...\n";
        bool success = renderer.renderAnimation(
            d3plot_path,
            "auto_section_center.mp4",
            render_opts
        );

        if (success) {
            std::cout << "SUCCESS: Rendered to auto_section_center.mp4\n";
        } else {
            std::cout << "ERROR: Rendering failed\n";
        }

        // ================================================================
        // Example 6: Batch rendering all positions
        // ================================================================
        std::cout << "\n--- Example 6: Batch Rendering All Positions ---\n";

        BatchRenderer batch(lsprepost_path);

        std::vector<std::string> output_names = {
            "auto_center.mp4",
            "auto_quarter1.mp4",
            "auto_quarter3.mp4",
            "auto_edge_min.mp4",
            "auto_edge_max.mp4"
        };

        for (size_t i = 0; i < output_names.size(); ++i) {
            auto opts = config1.toRenderOptions(i);
            batch.addJob({
                positions[i],
                d3plot_path,
                output_names[i],
                opts
            });
        }

        std::cout << "Processing " << batch.getJobCount() << " render jobs...\n";

        // Progress callback
        auto progress_callback = [](size_t completed, size_t total,
                                     const std::string& job_id, double pct) {
            std::cout << "[" << completed << "/" << total << "] "
                      << job_id << ": " << static_cast<int>(pct) << "%\n";
        };

        batch.processAll(progress_callback);

        std::cout << "\nBatch rendering complete!\n";
        batch.saveReport("auto_sections_report.txt");

        // ================================================================
        // Example 7: Loading and modifying YAML config
        // ================================================================
        std::cout << "\n--- Example 7: Loading and Modifying YAML Config ---\n";

        RenderConfig config_loaded;
        if (config_loaded.loadFromYAML("auto_sections_standard3.yaml")) {
            std::cout << "Loaded configuration from YAML\n";

            // Modify the configuration
            auto data_loaded = config_loaded.getData();
            data_loaded.output.width = 1920;
            data_loaded.output.height = 1080;
            config_loaded.setData(data_loaded);

            // Regenerate sections with updated config
            config_loaded.generateAutoSections(reader, 0);

            // Save modified config
            config_loaded.saveToYAML("auto_sections_modified.yaml");
            std::cout << "Saved modified configuration\n";
        }

        // ================================================================
        // Summary
        // ================================================================
        std::cout << "\n==============================================\n";
        std::cout << "  Summary of Auto-Section Generation\n";
        std::cout << "==============================================\n\n";

        std::cout << "Position Types Available:\n";
        std::cout << "  - center      : 50% (middle)\n";
        std::cout << "  - quarter_1   : 25%\n";
        std::cout << "  - quarter_3   : 75%\n";
        std::cout << "  - edge_min    : 0% (minimum boundary)\n";
        std::cout << "  - edge_max    : 100% (maximum boundary)\n";
        std::cout << "  - custom      : User-defined ratio (0.0-1.0)\n\n";

        std::cout << "Auto-Section Modes Available:\n";
        std::cout << "  - manual          : Manual plane specification\n";
        std::cout << "  - single          : Single plane at specified position\n";
        std::cout << "  - even_spaced     : Multiple evenly-spaced sections\n";
        std::cout << "  - uniform_spacing : Sections with uniform spacing\n";
        std::cout << "  - standard_3      : Standard 3-section (25%, 50%, 75%)\n";
        std::cout << "  - offset_edges    : Offset from edges\n\n";

        std::cout << "Generated Files:\n";
        std::cout << "  - auto_sections_positions.yaml  : Single sections at different positions\n";
        std::cout << "  - auto_sections_standard3.yaml  : Standard 3-section layout\n";
        std::cout << "  - auto_sections_even5.yaml      : 5 evenly-spaced sections\n";
        std::cout << "  - auto_sections_offset.yaml     : Offset from edges\n";
        std::cout << "  - auto_sections_modified.yaml   : Modified configuration\n";
        std::cout << "  - auto_sections_report.txt      : Batch rendering report\n";
        std::cout << "  - auto_*.mp4                    : Rendered animations\n\n";

    } catch (const std::exception& e) {
        std::cerr << "ERROR: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
