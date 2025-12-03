/**
 * @file 04_custom_views.cpp
 * @brief Custom view and advanced rendering example
 * @author KooD3plot V4 Development Team
 * @date 2025-11-24
 *
 * This example demonstrates advanced rendering features:
 * - Multiple view orientations
 * - Different fringe types
 * - Various output formats
 * - Script generation for debugging
 */

#include <iostream>
#include <string>
#include <fstream>
#include "kood3plot/render/LSPrePostRenderer.h"

using namespace kood3plot::render;

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cout << "Usage: " << argv[0] << " <d3plot_file> [lsprepost_path]\n";
        std::cout << "\nExample:\n";
        std::cout << "  " << argv[0] << " d3plot\n";
        return 1;
    }

    std::string d3plot_path = argv[1];
    std::string lsprepost_path = (argc >= 3) ? argv[2] : "lsprepost";

    std::cout << "=== KooD3plot V4 Custom Views Example ===\n\n";
    std::cout << "D3plot file: " << d3plot_path << "\n";
    std::cout << "LSPrePost: " << lsprepost_path << "\n\n";

    // Create renderer
    LSPrePostRenderer renderer(lsprepost_path);

    // Example 1: All standard views
    {
        std::cout << "Example 1: Standard View Orientations\n";
        std::cout << "=====================================\n";

        ViewOrientation views[] = {
            ViewOrientation::TOP,
            ViewOrientation::BOTTOM,
            ViewOrientation::LEFT,
            ViewOrientation::RIGHT,
            ViewOrientation::FRONT,
            ViewOrientation::BACK,
            ViewOrientation::ISOMETRIC
        };

        std::string view_names[] = {
            "top", "bottom", "left", "right", "front", "back", "isometric"
        };

        for (int i = 0; i < 7; ++i) {
            RenderOptions options;
            options.view = views[i];
            options.fringe_type = FringeType::VON_MISES;
            options.image_format = ImageFormat::PNG;

            std::string output = "view_" + view_names[i] + ".png";

            std::cout << "  Rendering " << view_names[i] << " view -> " << output << "\n";

            bool success = renderer.renderImage(d3plot_path, output, options);
            if (!success) {
                std::cerr << "    Error: " << renderer.getLastError() << "\n";
            }
        }

        std::cout << "\n";
    }

    // Example 2: Different fringe types
    {
        std::cout << "Example 2: Different Fringe Types\n";
        std::cout << "==================================\n";

        struct FringeExample {
            FringeType type;
            std::string name;
        };

        FringeExample fringes[] = {
            {FringeType::VON_MISES, "vonmises"},
            {FringeType::DISPLACEMENT, "displacement"},
            {FringeType::STRESS_XX, "stress_xx"},
            {FringeType::STRESS_YY, "stress_yy"},
            {FringeType::STRESS_ZZ, "stress_zz"},
            {FringeType::EFFECTIVE_STRAIN, "effective_strain"}
        };

        for (int i = 0; i < 6; ++i) {
            RenderOptions options;
            options.view = ViewOrientation::ISOMETRIC;
            options.fringe_type = fringes[i].type;
            options.image_format = ImageFormat::PNG;

            std::string output = "fringe_" + fringes[i].name + ".png";

            std::cout << "  Rendering " << fringes[i].name << " -> " << output << "\n";

            bool success = renderer.renderImage(d3plot_path, output, options);
            if (!success) {
                std::cerr << "    Error: " << renderer.getLastError() << "\n";
            }
        }

        std::cout << "\n";
    }

    // Example 3: Different image formats
    {
        std::cout << "Example 3: Different Image Formats\n";
        std::cout << "===================================\n";

        ImageFormat formats[] = {
            ImageFormat::PNG,
            ImageFormat::JPG,
            ImageFormat::BMP,
            ImageFormat::TIFF
        };

        std::string extensions[] = {"png", "jpg", "bmp", "tiff"};

        for (int i = 0; i < 4; ++i) {
            RenderOptions options;
            options.view = ViewOrientation::ISOMETRIC;
            options.fringe_type = FringeType::VON_MISES;
            options.image_format = formats[i];

            std::string output = "format_test." + extensions[i];

            std::cout << "  Rendering " << extensions[i] << " format -> " << output << "\n";

            bool success = renderer.renderImage(d3plot_path, output, options);
            if (!success) {
                std::cerr << "    Error: " << renderer.getLastError() << "\n";
            }
        }

        std::cout << "\n";
    }

    // Example 4: Script generation (debugging)
    {
        std::cout << "Example 4: Script Generation\n";
        std::cout << "============================\n";

        RenderOptions options;
        options.view = ViewOrientation::ISOMETRIC;
        options.fringe_type = FringeType::VON_MISES;
        options.image_format = ImageFormat::PNG;

        // Add section plane
        SectionPlane plane;
        plane.point = {0.0, 0.0, 0.0};
        plane.normal = {0.0, 0.0, 1.0};
        plane.visible = true;
        options.section_planes.push_back(plane);

        std::string output = "debug_output.png";

        std::cout << "  Generating LSPrePost script...\n";

        std::string script = renderer.generateScript(d3plot_path, output, options);

        // Save script to file
        std::string script_file = "debug_script.cfile";
        std::ofstream ofs(script_file);
        if (ofs.is_open()) {
            ofs << script;
            ofs.close();
            std::cout << "  Script saved to: " << script_file << "\n\n";
            std::cout << "  Script contents:\n";
            std::cout << "  ----------------------------------------\n";
            std::cout << script;
            std::cout << "  ----------------------------------------\n\n";
        } else {
            std::cerr << "  Error: Could not save script file\n\n";
        }
    }

    std::cout << "Custom views example complete!\n";
    std::cout << "\nTip: You can manually edit the generated .cfile scripts\n";
    std::cout << "     and run them with: lsprepost -nographics c=script.cfile\n";

    return 0;
}
