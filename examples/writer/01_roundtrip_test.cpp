/**
 * @file 01_roundtrip_test.cpp
 * @brief Roundtrip test for D3plotWriter
 *
 * This example reads a d3plot file, writes it back, and verifies the data.
 *
 * Usage:
 *   ./01_roundtrip_test <input_d3plot> [output_d3plot]
 */

#include <iostream>
#include <iomanip>
#include <cmath>
#include <string>

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/writer/D3plotWriter.h"

using namespace kood3plot;
using namespace kood3plot::writer;

// Helper function to compare floating point values
bool approx_equal(double a, double b, double epsilon = 1e-5) {
    return std::abs(a - b) < epsilon;
}

// Compare control data
bool compare_control(const data::ControlData& c1, const data::ControlData& c2) {
    bool match = true;

    if (c1.NUMNP != c2.NUMNP) {
        std::cerr << "  NUMNP mismatch: " << c1.NUMNP << " vs " << c2.NUMNP << std::endl;
        match = false;
    }

    if (c1.NEL8 != c2.NEL8) {
        std::cerr << "  NEL8 mismatch: " << c1.NEL8 << " vs " << c2.NEL8 << std::endl;
        match = false;
    }

    if (c1.NEL4 != c2.NEL4) {
        std::cerr << "  NEL4 mismatch: " << c1.NEL4 << " vs " << c2.NEL4 << std::endl;
        match = false;
    }

    if (c1.NEL2 != c2.NEL2) {
        std::cerr << "  NEL2 mismatch: " << c1.NEL2 << " vs " << c2.NEL2 << std::endl;
        match = false;
    }

    if (c1.NELT != c2.NELT) {
        std::cerr << "  NELT mismatch: " << c1.NELT << " vs " << c2.NELT << std::endl;
        match = false;
    }

    return match;
}

// Compare mesh data
bool compare_mesh(const data::Mesh& m1, const data::Mesh& m2) {
    bool match = true;

    // Compare node count
    if (m1.nodes.size() != m2.nodes.size()) {
        std::cerr << "  Node count mismatch: " << m1.nodes.size()
                  << " vs " << m2.nodes.size() << std::endl;
        match = false;
    }

    // Compare first few nodes
    size_t check_count = std::min(m1.nodes.size(), m2.nodes.size());
    check_count = std::min(check_count, size_t(10));

    for (size_t i = 0; i < check_count; ++i) {
        const auto& n1 = m1.nodes[i];
        const auto& n2 = m2.nodes[i];

        if (!approx_equal(n1.x, n2.x) ||
            !approx_equal(n1.y, n2.y) ||
            !approx_equal(n1.z, n2.z)) {
            std::cerr << "  Node " << i << " coord mismatch: ("
                      << n1.x << "," << n1.y << "," << n1.z << ") vs ("
                      << n2.x << "," << n2.y << "," << n2.z << ")" << std::endl;
            match = false;
        }
    }

    // Compare element count
    if (m1.solids.size() != m2.solids.size()) {
        std::cerr << "  Solid count mismatch: " << m1.solids.size()
                  << " vs " << m2.solids.size() << std::endl;
        match = false;
    }

    if (m1.shells.size() != m2.shells.size()) {
        std::cerr << "  Shell count mismatch: " << m1.shells.size()
                  << " vs " << m2.shells.size() << std::endl;
        match = false;
    }

    return match;
}

// Compare state data
bool compare_states(const std::vector<data::StateData>& s1,
                    const std::vector<data::StateData>& s2) {
    bool match = true;

    if (s1.size() != s2.size()) {
        std::cerr << "  State count mismatch: " << s1.size()
                  << " vs " << s2.size() << std::endl;
        match = false;
    }

    size_t check_count = std::min(s1.size(), s2.size());
    for (size_t i = 0; i < check_count; ++i) {
        if (!approx_equal(s1[i].time, s2[i].time)) {
            std::cerr << "  State " << i << " time mismatch: "
                      << s1[i].time << " vs " << s2[i].time << std::endl;
            match = false;
        }

        // Compare displacement sizes
        if (s1[i].node_displacements.size() != s2[i].node_displacements.size()) {
            std::cerr << "  State " << i << " displacement size mismatch: "
                      << s1[i].node_displacements.size() << " vs "
                      << s2[i].node_displacements.size() << std::endl;
            match = false;
        }

        // Compare first few displacements
        size_t disp_check = std::min(s1[i].node_displacements.size(),
                                     s2[i].node_displacements.size());
        disp_check = std::min(disp_check, size_t(30));

        for (size_t j = 0; j < disp_check; ++j) {
            if (!approx_equal(s1[i].node_displacements[j],
                              s2[i].node_displacements[j], 1e-4)) {
                std::cerr << "  State " << i << " disp[" << j << "] mismatch: "
                          << s1[i].node_displacements[j] << " vs "
                          << s2[i].node_displacements[j] << std::endl;
                match = false;
                break;
            }
        }
    }

    return match;
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cout << "Usage: " << argv[0] << " <input_d3plot> [output_d3plot]\n";
        std::cout << "\nThis program tests the D3plotWriter by:\n";
        std::cout << "  1. Reading the input d3plot file\n";
        std::cout << "  2. Writing it back to a new file\n";
        std::cout << "  3. Reading the new file and comparing data\n";
        return 1;
    }

    std::string input_path = argv[1];
    std::string output_path = (argc >= 3) ? argv[2] : "roundtrip_output.d3plot";

    std::cout << "========================================\n";
    std::cout << " D3plot Writer Roundtrip Test\n";
    std::cout << "========================================\n\n";

    // ========================================
    // Step 1: Read original d3plot
    // ========================================
    std::cout << "[Step 1] Reading original d3plot: " << input_path << "\n";

    D3plotReader reader1(input_path);
    if (reader1.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error: Cannot open input file: " << input_path << "\n";
        return 1;
    }

    auto control1 = reader1.get_control_data();
    auto mesh1 = reader1.read_mesh();
    auto states1 = reader1.read_all_states();
    reader1.close();

    std::cout << "  Nodes: " << control1.NUMNP << "\n";
    std::cout << "  Solids: " << std::abs(control1.NEL8) << "\n";
    std::cout << "  Shells: " << control1.NEL4 << "\n";
    std::cout << "  Beams: " << control1.NEL2 << "\n";
    std::cout << "  States: " << states1.size() << "\n\n";

    // ========================================
    // Step 2: Write to new d3plot
    // ========================================
    std::cout << "[Step 2] Writing to: " << output_path << "\n";

    D3plotWriter writer(output_path);

    WriterOptions opts;
    opts.precision = Precision::SINGLE;
    opts.endian = Endian::LITTLE;
    opts.verbose = true;
    writer.setOptions(opts);

    writer.setControlData(control1);
    writer.setMesh(mesh1);
    writer.setStates(states1);

    auto write_result = writer.write();
    if (write_result != ErrorCode::SUCCESS) {
        std::cerr << "Error: Write failed: " << writer.getLastError() << "\n";
        return 1;
    }

    std::cout << "  Bytes written: " << writer.getWrittenBytes() << "\n";
    std::cout << "  States written: " << writer.getStatesWritten() << "\n";
    std::cout << "  Output files: ";
    for (const auto& f : writer.getOutputFiles()) {
        std::cout << f << " ";
    }
    std::cout << "\n\n";

    // ========================================
    // Step 3: Read back and compare
    // ========================================
    std::cout << "[Step 3] Reading back and comparing...\n";

    D3plotReader reader2(output_path);
    if (reader2.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error: Cannot open output file: " << output_path << "\n";
        return 1;
    }

    auto control2 = reader2.get_control_data();
    auto mesh2 = reader2.read_mesh();
    auto states2 = reader2.read_all_states();
    reader2.close();

    // Compare
    bool all_match = true;

    std::cout << "\n[Comparison Results]\n";

    std::cout << "\nControl Data:\n";
    if (compare_control(control1, control2)) {
        std::cout << "  [PASS] Control data matches\n";
    } else {
        std::cout << "  [FAIL] Control data mismatch\n";
        all_match = false;
    }

    std::cout << "\nMesh Data:\n";
    if (compare_mesh(mesh1, mesh2)) {
        std::cout << "  [PASS] Mesh data matches\n";
    } else {
        std::cout << "  [FAIL] Mesh data mismatch\n";
        all_match = false;
    }

    std::cout << "\nState Data:\n";
    if (compare_states(states1, states2)) {
        std::cout << "  [PASS] State data matches\n";
    } else {
        std::cout << "  [FAIL] State data mismatch\n";
        all_match = false;
    }

    // ========================================
    // Summary
    // ========================================
    std::cout << "\n========================================\n";
    if (all_match) {
        std::cout << " ROUNDTRIP TEST PASSED!\n";
    } else {
        std::cout << " ROUNDTRIP TEST FAILED!\n";
    }
    std::cout << "========================================\n";

    return all_match ? 0 : 1;
}
