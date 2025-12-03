/**
 * @file 02_section_view.cpp
 * @brief Section view rendering example
 * @author KooD3plot V4 Development Team
 * @date 2025-11-24
 *
 * This example demonstrates section plane rendering using LSPrePostRenderer.
 * It shows how to:
 * - Define section planes
 * - Render section views
 * - Use different view orientations
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

    std::cout << "=== KooD3plot V4 Section View Example ===\n\n";
    std::cout << "D3plot file: " << d3plot_path << "\n";
    std::cout << "LSPrePost: " << lsprepost_path << "\n\n";

    // Create renderer
    LSPrePostRenderer renderer(lsprepost_path);

    // Example 1: XY plane section (cut at Z=0)
    {
        std::cout << "Example 1: XY Plane Section (Z=0)\n";
        std::cout << "================================\n";

        SectionPlane plane;
        plane.point = {0.0, 0.0, 0.0};    // Point on plane
        plane.normal = {0.0, 0.0, 1.0};   // Normal vector (Z direction)
        plane.visible = true;

        RenderOptions options;
        options.view = ViewOrientation::TOP;
        options.fringe_type = FringeType::VON_MISES;
        options.image_format = ImageFormat::PNG;

        std::string output = "section_xy_plane.png";

        std::cout << "  Section plane:\n";
        std::cout << "    Point: (" << plane.point[0] << ", "
                  << plane.point[1] << ", " << plane.point[2] << ")\n";
        std::cout << "    Normal: (" << plane.normal[0] << ", "
                  << plane.normal[1] << ", " << plane.normal[2] << ")\n";
        std::cout << "  View: TOP\n";
        std::cout << "  Output: " << output << "\n\n";

        bool success = renderer.renderSectionView(d3plot_path, output, plane, options);

        if (success) {
            std::cout << "  ✓ Render successful!\n\n";
        } else {
            std::cerr << "  ✗ Render failed: " << renderer.getLastError() << "\n\n";
        }
    }

    // Example 2: YZ plane section (cut at X=0)
    {
        std::cout << "Example 2: YZ Plane Section (X=0)\n";
        std::cout << "================================\n";

        SectionPlane plane;
        plane.point = {0.0, 0.0, 0.0};
        plane.normal = {1.0, 0.0, 0.0};   // Normal in X direction
        plane.visible = true;

        RenderOptions options;
        options.view = ViewOrientation::RIGHT;
        options.fringe_type = FringeType::DISPLACEMENT;
        options.image_format = ImageFormat::PNG;

        std::string output = "section_yz_plane.png";

        std::cout << "  Section plane:\n";
        std::cout << "    Point: (" << plane.point[0] << ", "
                  << plane.point[1] << ", " << plane.point[2] << ")\n";
        std::cout << "    Normal: (" << plane.normal[0] << ", "
                  << plane.normal[1] << ", " << plane.normal[2] << ")\n";
        std::cout << "  View: RIGHT\n";
        std::cout << "  Fringe: DISPLACEMENT\n";
        std::cout << "  Output: " << output << "\n\n";

        bool success = renderer.renderSectionView(d3plot_path, output, plane, options);

        if (success) {
            std::cout << "  ✓ Render successful!\n\n";
        } else {
            std::cerr << "  ✗ Render failed: " << renderer.getLastError() << "\n\n";
        }
    }

    // Example 3: Diagonal plane section
    {
        std::cout << "Example 3: Diagonal Plane Section\n";
        std::cout << "=================================\n";

        SectionPlane plane;
        plane.point = {0.0, 0.0, 0.0};
        plane.normal = {1.0, 1.0, 0.0};   // Diagonal in XY plane
        plane.visible = true;

        RenderOptions options;
        options.view = ViewOrientation::ISOMETRIC;
        options.fringe_type = FringeType::STRESS_XX;
        options.image_format = ImageFormat::PNG;

        std::string output = "section_diagonal.png";

        std::cout << "  Section plane:\n";
        std::cout << "    Point: (" << plane.point[0] << ", "
                  << plane.point[1] << ", " << plane.point[2] << ")\n";
        std::cout << "    Normal: (" << plane.normal[0] << ", "
                  << plane.normal[1] << ", " << plane.normal[2] << ")\n";
        std::cout << "  View: ISOMETRIC\n";
        std::cout << "  Fringe: STRESS_XX\n";
        std::cout << "  Output: " << output << "\n\n";

        bool success = renderer.renderSectionView(d3plot_path, output, plane, options);

        if (success) {
            std::cout << "  ✓ Render successful!\n\n";
        } else {
            std::cerr << "  ✗ Render failed: " << renderer.getLastError() << "\n\n";
        }
    }

    std::cout << "Section view rendering complete!\n";

    return 0;
}
