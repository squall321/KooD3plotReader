#include "kood3plot/core/BinaryReader.hpp"
#include "kood3plot/parsers/ControlDataParser.hpp"
#include "kood3plot/parsers/GeometryParser.hpp"
#include "kood3plot/Types.hpp"
#include <iostream>
#include <iomanip>
#include <memory>

int main(int argc, char* argv[]) {
    std::string filepath = "../results/d3plot";

    if (argc > 1) {
        filepath = argv[1];
    }

    std::cout << "Testing GeometryParser with: " << filepath << std::endl;
    std::cout << "========================================" << std::endl;

    // Create reader and open file
    auto reader = std::make_shared<kood3plot::core::BinaryReader>(filepath);

    auto err = reader->open();
    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open file: " << kood3plot::error_to_string(err) << std::endl;
        return 1;
    }

    std::cout << "✓ File opened successfully" << std::endl;
    std::cout << "  Format: " << (reader->get_precision() == kood3plot::Precision::SINGLE ? "Single" : "Double")
              << " precision, " << (reader->get_endian() == kood3plot::Endian::LITTLE ? "Little" : "Big")
              << "-endian" << std::endl;

    // Parse control data
    std::cout << "\nParsing Control Data..." << std::endl;
    kood3plot::parsers::ControlDataParser control_parser(reader);
    kood3plot::data::ControlData cd;

    try {
        cd = control_parser.parse();
        std::cout << "✓ Control data parsed successfully" << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "✗ Failed to parse control data: " << e.what() << std::endl;
        return 1;
    }

    // Parse geometry
    std::cout << "\nParsing Geometry Data..." << std::endl;
    kood3plot::parsers::GeometryParser geom_parser(reader, cd);
    kood3plot::data::Mesh mesh;

    try {
        mesh = geom_parser.parse();
        std::cout << "✓ Geometry parsed successfully" << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "✗ Failed to parse geometry: " << e.what() << std::endl;
        return 1;
    }

    // Display mesh statistics
    std::cout << "\n=== Mesh Statistics ===" << std::endl;
    std::cout << std::fixed << std::setprecision(6);

    std::cout << "\n[Nodes]" << std::endl;
    std::cout << "  Total nodes: " << mesh.get_num_nodes() << std::endl;

    if (mesh.get_num_nodes() > 0) {
        std::cout << "\n  First 5 nodes:" << std::endl;
        for (size_t i = 0; i < std::min(size_t(5), mesh.nodes.size()); ++i) {
            const auto& node = mesh.nodes[i];
            std::cout << "    Node " << std::setw(6) << node.id << ": ("
                      << std::setw(12) << node.x << ", "
                      << std::setw(12) << node.y << ", "
                      << std::setw(12) << node.z << ")" << std::endl;
        }

        std::cout << "\n  Last 5 nodes:" << std::endl;
        size_t start = mesh.nodes.size() >= 5 ? mesh.nodes.size() - 5 : 0;
        for (size_t i = start; i < mesh.nodes.size(); ++i) {
            const auto& node = mesh.nodes[i];
            std::cout << "    Node " << std::setw(6) << node.id << ": ("
                      << std::setw(12) << node.x << ", "
                      << std::setw(12) << node.y << ", "
                      << std::setw(12) << node.z << ")" << std::endl;
        }
    }

    std::cout << "\n[Elements]" << std::endl;
    std::cout << "  Total elements: " << mesh.get_num_elements() << std::endl;
    std::cout << "    Solids:       " << mesh.num_solids << std::endl;
    std::cout << "    Thick shells: " << mesh.num_thick_shells << std::endl;
    std::cout << "    Beams:        " << mesh.num_beams << std::endl;
    std::cout << "    Shells:       " << mesh.num_shells << std::endl;

    // Display solid elements
    if (mesh.num_solids > 0) {
        std::cout << "\n  First 3 solid elements:" << std::endl;
        for (size_t i = 0; i < std::min(size_t(3), mesh.solids.size()); ++i) {
            const auto& elem = mesh.solids[i];
            std::cout << "    Solid " << std::setw(6) << elem.id
                      << " (mat=" << std::setw(3) << mesh.solid_materials[i] << "): nodes = [";
            for (size_t n = 0; n < elem.node_ids.size(); ++n) {
                if (n > 0) std::cout << ", ";
                std::cout << elem.node_ids[n];
            }
            std::cout << "]" << std::endl;
        }
    }

    // Display thick shell elements
    if (mesh.num_thick_shells > 0) {
        std::cout << "\n  First 3 thick shell elements:" << std::endl;
        for (size_t i = 0; i < std::min(size_t(3), mesh.thick_shells.size()); ++i) {
            const auto& elem = mesh.thick_shells[i];
            std::cout << "    Thick Shell " << std::setw(6) << elem.id
                      << " (mat=" << std::setw(3) << mesh.thick_shell_materials[i] << "): nodes = [";
            for (size_t n = 0; n < elem.node_ids.size(); ++n) {
                if (n > 0) std::cout << ", ";
                std::cout << elem.node_ids[n];
            }
            std::cout << "]" << std::endl;
        }
    }

    // Display beam elements
    if (mesh.num_beams > 0) {
        std::cout << "\n  First 3 beam elements:" << std::endl;
        for (size_t i = 0; i < std::min(size_t(3), mesh.beams.size()); ++i) {
            const auto& elem = mesh.beams[i];
            std::cout << "    Beam " << std::setw(6) << elem.id
                      << " (mat=" << std::setw(3) << mesh.beam_materials[i] << "): nodes = [";
            for (size_t n = 0; n < elem.node_ids.size(); ++n) {
                if (n > 0) std::cout << ", ";
                std::cout << elem.node_ids[n];
            }
            std::cout << "]" << std::endl;
        }
    }

    // Display shell elements
    if (mesh.num_shells > 0) {
        std::cout << "\n  First 3 shell elements:" << std::endl;
        for (size_t i = 0; i < std::min(size_t(3), mesh.shells.size()); ++i) {
            const auto& elem = mesh.shells[i];
            std::cout << "    Shell " << std::setw(6) << elem.id
                      << " (mat=" << std::setw(3) << mesh.shell_materials[i] << "): nodes = [";
            for (size_t n = 0; n < elem.node_ids.size(); ++n) {
                if (n > 0) std::cout << ", ";
                std::cout << elem.node_ids[n];
            }
            std::cout << "]" << std::endl;
        }
    }

    // Verify element counts match control data
    std::cout << "\n=== Verification ===" << std::endl;
    bool counts_match = true;

    if (mesh.num_solids != static_cast<size_t>(std::abs(cd.NEL8))) {
        std::cout << "  ✗ Solid count mismatch: expected " << std::abs(cd.NEL8)
                  << ", got " << mesh.num_solids << std::endl;
        counts_match = false;
    }

    if (mesh.num_thick_shells != static_cast<size_t>(cd.NELT)) {
        std::cout << "  ✗ Thick shell count mismatch: expected " << cd.NELT
                  << ", got " << mesh.num_thick_shells << std::endl;
        counts_match = false;
    }

    if (mesh.num_beams != static_cast<size_t>(cd.NEL2)) {
        std::cout << "  ✗ Beam count mismatch: expected " << cd.NEL2
                  << ", got " << mesh.num_beams << std::endl;
        counts_match = false;
    }

    if (mesh.num_shells != static_cast<size_t>(cd.NEL4)) {
        std::cout << "  ✗ Shell count mismatch: expected " << cd.NEL4
                  << ", got " << mesh.num_shells << std::endl;
        counts_match = false;
    }

    if (mesh.get_num_nodes() != static_cast<size_t>(cd.NUMNP)) {
        std::cout << "  ✗ Node count mismatch: expected " << cd.NUMNP
                  << ", got " << mesh.get_num_nodes() << std::endl;
        counts_match = false;
    }

    if (counts_match) {
        std::cout << "  ✓ All element and node counts match control data" << std::endl;
    }

    reader->close();
    std::cout << "\n✓ Test completed successfully" << std::endl;

    return 0;
}
