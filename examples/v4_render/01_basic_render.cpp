/**
 * @file 01_basic_render.cpp
 * @brief Basic LSPrePost rendering example
 * @author KooD3plot V4 Development Team
 * @date 2025-11-24
 *
 * This example demonstrates basic image rendering using LSPrePostRenderer.
 * It shows how to:
 * - Create a renderer instance
 * - Set up render options
 * - Render a single image from d3plot
 */

#include <iostream>
#include <string>
#include "kood3plot/render/LSPrePostRenderer.h"

using namespace kood3plot::render;

int main(int argc, char* argv[]) {
    // Check command line arguments
    if (argc < 2) {
        std::cout << "Usage: " << argv[0] << " <d3plot_file> [lsprepost_path]\n";
        std::cout << "\nExample:\n";
        std::cout << "  " << argv[0] << " d3plot\n";
        std::cout << "  " << argv[0] << " d3plot /usr/local/bin/lsprepost\n";
        return 1;
    }

    std::string d3plot_path = argv[1];
    std::string lsprepost_path = (argc >= 3) ? argv[2] : "lsprepost";

    std::cout << "=== KooD3plot V4 Basic Render Example ===\n\n";
    std::cout << "D3plot file: " << d3plot_path << "\n";
    std::cout << "LSPrePost: " << lsprepost_path << "\n\n";

    // Create renderer
    LSPrePostRenderer renderer(lsprepost_path);

    // Setup render options
    RenderOptions options;
    options.view = ViewOrientation::ISOMETRIC;
    options.fringe_type = FringeType::VON_MISES;
    options.image_format = ImageFormat::PNG;

    // Output file
    std::string output = "output_basic.png";

    std::cout << "Rendering options:\n";
    std::cout << "  View: ISOMETRIC\n";
    std::cout << "  Fringe: Von Mises stress\n";
    std::cout << "  Format: PNG\n";
    std::cout << "  Output: " << output << "\n\n";

    // Render image
    std::cout << "Starting render...\n";
    bool success = renderer.renderImage(d3plot_path, output, options);

    if (success) {
        std::cout << "✓ Render successful!\n";
        std::cout << "  Image saved to: " << output << "\n";
    } else {
        std::cerr << "✗ Render failed!\n";
        std::cerr << "  Error: " << renderer.getLastError() << "\n";
        return 1;
    }

    return 0;
}
