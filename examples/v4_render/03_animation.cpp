/**
 * @file 03_animation.cpp
 * @brief Animation rendering example
 * @author KooD3plot V4 Development Team
 * @date 2025-11-24
 *
 * This example demonstrates animation rendering using LSPrePostRenderer.
 * It shows how to:
 * - Create animations from all timesteps
 * - Choose video format
 * - Combine animation with section views
 */

#include <iostream>
#include <string>
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

    std::cout << "=== KooD3plot V4 Animation Example ===\n\n";
    std::cout << "D3plot file: " << d3plot_path << "\n";
    std::cout << "LSPrePost: " << lsprepost_path << "\n\n";

    // Create renderer
    LSPrePostRenderer renderer(lsprepost_path);

    // Example 1: Basic animation (Von Mises stress)
    {
        std::cout << "Example 1: Basic Animation\n";
        std::cout << "==========================\n";

        RenderOptions options;
        options.view = ViewOrientation::ISOMETRIC;
        options.fringe_type = FringeType::VON_MISES;
        options.create_animation = true;
        options.video_format = VideoFormat::MP4;

        std::string output = "animation_vonmises.mp4";

        std::cout << "  Animation settings:\n";
        std::cout << "    View: ISOMETRIC\n";
        std::cout << "    Fringe: Von Mises stress\n";
        std::cout << "    Format: MP4\n";
        std::cout << "    Output: " << output << "\n";
        std::cout << "  Note: This will render all timesteps\n\n";

        std::cout << "  Starting animation render (this may take a while)...\n";
        bool success = renderer.renderAnimation(d3plot_path, output, options);

        if (success) {
            std::cout << "  ✓ Animation render successful!\n\n";
        } else {
            std::cerr << "  ✗ Animation render failed: " << renderer.getLastError() << "\n\n";
        }
    }

    // Example 2: Animation with displacement fringe
    {
        std::cout << "Example 2: Displacement Animation\n";
        std::cout << "=================================\n";

        RenderOptions options;
        options.view = ViewOrientation::FRONT;
        options.fringe_type = FringeType::DISPLACEMENT;
        options.create_animation = true;
        options.video_format = VideoFormat::AVI;

        std::string output = "animation_displacement.avi";

        std::cout << "  Animation settings:\n";
        std::cout << "    View: FRONT\n";
        std::cout << "    Fringe: Displacement\n";
        std::cout << "    Format: AVI\n";
        std::cout << "    Output: " << output << "\n\n";

        std::cout << "  Starting animation render...\n";
        bool success = renderer.renderAnimation(d3plot_path, output, options);

        if (success) {
            std::cout << "  ✓ Animation render successful!\n\n";
        } else {
            std::cerr << "  ✗ Animation render failed: " << renderer.getLastError() << "\n\n";
        }
    }

    // Example 3: Animation with section plane
    {
        std::cout << "Example 3: Section Plane Animation\n";
        std::cout << "==================================\n";

        // Define section plane
        SectionPlane plane;
        plane.point = {0.0, 0.0, 0.0};
        plane.normal = {0.0, 0.0, 1.0};
        plane.visible = true;

        RenderOptions options;
        options.view = ViewOrientation::ISOMETRIC;
        options.fringe_type = FringeType::STRESS_XX;
        options.section_planes.push_back(plane);
        options.create_animation = true;
        options.video_format = VideoFormat::MP4;

        std::string output = "animation_section.mp4";

        std::cout << "  Animation settings:\n";
        std::cout << "    View: ISOMETRIC\n";
        std::cout << "    Fringe: Stress XX\n";
        std::cout << "    Section plane: Z=0 (normal = [0,0,1])\n";
        std::cout << "    Format: MP4\n";
        std::cout << "    Output: " << output << "\n\n";

        std::cout << "  Starting animation render...\n";
        bool success = renderer.renderAnimation(d3plot_path, output, options);

        if (success) {
            std::cout << "  ✓ Animation render successful!\n\n";
        } else {
            std::cerr << "  ✗ Animation render failed: " << renderer.getLastError() << "\n\n";
        }
    }

    std::cout << "Animation rendering complete!\n";
    std::cout << "\nNote: Animation rendering processes all timesteps in the d3plot file.\n";
    std::cout << "For large files, this may take several minutes.\n";

    return 0;
}
