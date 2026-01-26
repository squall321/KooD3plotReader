/**
 * @file 02_basic_write.cpp
 * @brief Basic D3plotWriter usage example
 *
 * This example demonstrates creating a simple d3plot file from scratch.
 *
 * Usage:
 *   ./02_basic_write [output_d3plot]
 */

#include <iostream>
#include <iomanip>
#include <cmath>
#include <string>

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/writer/D3plotWriter.h"

using namespace kood3plot;
using namespace kood3plot::writer;

int main(int argc, char* argv[]) {
    std::string output_path = (argc >= 2) ? argv[1] : "test_output.d3plot";

    std::cout << "========================================\n";
    std::cout << " D3plot Writer - Basic Example\n";
    std::cout << "========================================\n\n";

    // ========================================
    // Create simple mesh: a single hexahedron (cube)
    // ========================================

    // Control data
    data::ControlData control;
    control.TITLE = "KooD3plot Writer Test - Single Cube";
    control.NDIM = 5;        // 3D coordinates + extra
    control.NUMNP = 8;       // 8 nodes for a cube
    control.NEL8 = 1;        // 1 solid element
    control.NEL4 = 0;        // No shells
    control.NEL2 = 0;        // No beams
    control.NELT = 0;        // No thick shells
    control.NGLBV = 6;       // Global variables (KE, IE, etc.)
    control.IU = 1;          // Displacements present
    control.IV = 1;          // Velocities present
    control.IA = 0;          // No accelerations
    control.IT = 0;          // No temperatures
    control.NV3D = 7;        // Variables per solid: 6 stress + 1 eff plastic strain
    control.NMMAT = 1;       // 1 material/part
    control.NUMMAT8 = 1;     // 1 solid material
    control.NARBS = 0;       // No arbitrary numbering

    // Compute derived values
    control.NND = control.NUMNP * 3 * (control.IU + control.IV + control.IA);
    control.ENN = std::abs(control.NEL8) * control.NV3D;
    control.compute_derived_values();

    std::cout << "[Step 1] Creating mesh data...\n";

    // Mesh data: 8 nodes of a unit cube
    data::Mesh mesh;
    mesh.nodes.resize(8);

    // Node coordinates (unit cube from 0 to 1)
    // Node struct: { id, x, y, z }
    mesh.nodes[0] = {1, 0.0, 0.0, 0.0};
    mesh.nodes[1] = {2, 1.0, 0.0, 0.0};
    mesh.nodes[2] = {3, 1.0, 1.0, 0.0};
    mesh.nodes[3] = {4, 0.0, 1.0, 0.0};
    mesh.nodes[4] = {5, 0.0, 0.0, 1.0};
    mesh.nodes[5] = {6, 1.0, 0.0, 1.0};
    mesh.nodes[6] = {7, 1.0, 1.0, 1.0};
    mesh.nodes[7] = {8, 0.0, 1.0, 1.0};

    // Single solid element (8-node hexahedron)
    Element hex;
    hex.node_ids = {1, 2, 3, 4, 5, 6, 7, 8};  // 1-based node IDs
    mesh.solids.push_back(hex);
    mesh.solid_parts.push_back(1);  // Part ID = 1
    mesh.num_solids = 1;

    std::cout << "  Created cube with 8 nodes and 1 solid element\n\n";

    // ========================================
    // Create state data (3 time steps)
    // ========================================
    std::cout << "[Step 2] Creating state data (3 timesteps)...\n";

    std::vector<data::StateData> states;

    for (int t = 0; t < 3; ++t) {
        data::StateData state;
        state.time = t * 0.001;  // 0, 1ms, 2ms

        // Global variables (kinetic energy, internal energy, etc.)
        state.global_vars.resize(control.NGLBV, 0.0);
        state.global_vars[0] = t * 100.0;   // KE
        state.global_vars[1] = t * 50.0;    // IE
        state.global_vars[2] = t * 150.0;   // TE
        state.global_vars[3] = 0.0;         // X velocity
        state.global_vars[4] = 0.0;         // Y velocity
        state.global_vars[5] = 0.0;         // Z velocity

        // Node displacements (3 components per node)
        state.node_displacements.resize(control.NUMNP * 3, 0.0);

        // Simulate stretching in Z direction
        double stretch = t * 0.1;
        for (int n = 4; n < 8; ++n) {  // Top nodes (5-8, 0-indexed 4-7)
            state.node_displacements[n * 3 + 2] = stretch;  // Z displacement
        }

        // Node velocities (3 components per node)
        state.node_velocities.resize(control.NUMNP * 3, 0.0);
        for (int n = 4; n < 8; ++n) {
            state.node_velocities[n * 3 + 2] = 0.1;  // Z velocity
        }

        // Solid element data (stress tensor + effective plastic strain)
        state.solid_data.resize(std::abs(control.NEL8) * control.NV3D, 0.0);
        // Sxx, Syy, Szz, Sxy, Syz, Szx, eff_plastic_strain
        state.solid_data[0] = -100.0 * t;  // Sxx (compression)
        state.solid_data[1] = -100.0 * t;  // Syy
        state.solid_data[2] = 200.0 * t;   // Szz (tension in Z)
        state.solid_data[3] = 0.0;         // Sxy
        state.solid_data[4] = 0.0;         // Syz
        state.solid_data[5] = 0.0;         // Szx
        state.solid_data[6] = 0.01 * t;    // Effective plastic strain

        states.push_back(state);

        std::cout << "  State " << t << ": time=" << state.time
                  << "s, Z-disp=" << stretch << "\n";
    }

    std::cout << "\n";

    // ========================================
    // Write d3plot file
    // ========================================
    std::cout << "[Step 3] Writing d3plot: " << output_path << "\n";

    D3plotWriter writer(output_path);

    WriterOptions opts;
    opts.precision = Precision::SINGLE;
    opts.endian = Endian::LITTLE;
    opts.verbose = true;
    writer.setOptions(opts);

    writer.setControlData(control);
    writer.setMesh(mesh);
    writer.setStates(states);

    auto result = writer.write();
    if (result != ErrorCode::SUCCESS) {
        std::cerr << "Error: " << writer.getLastError() << "\n";
        return 1;
    }

    std::cout << "\n[Result]\n";
    std::cout << "  Output file: " << output_path << "\n";
    std::cout << "  Bytes written: " << writer.getWrittenBytes() << "\n";
    std::cout << "  States written: " << writer.getStatesWritten() << "\n";

    // ========================================
    // Verify by reading back
    // ========================================
    std::cout << "\n[Step 4] Verifying by reading back...\n";

    D3plotReader reader(output_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cerr << "Error: Cannot read back output file\n";
        return 1;
    }

    auto read_control = reader.get_control_data();
    auto read_mesh = reader.read_mesh();
    auto read_states = reader.read_all_states();
    reader.close();

    std::cout << "  Title: " << read_control.TITLE << "\n";
    std::cout << "  Nodes: " << read_control.NUMNP << "\n";
    std::cout << "  Solids: " << std::abs(read_control.NEL8) << "\n";
    std::cout << "  States: " << read_states.size() << "\n";

    if (!read_states.empty()) {
        std::cout << "  Time range: " << read_states.front().time
                  << " - " << read_states.back().time << " s\n";
    }

    std::cout << "\n========================================\n";
    std::cout << " D3plot file created successfully!\n";
    std::cout << " Open with LSPrePost: lsprepost " << output_path << "\n";
    std::cout << "========================================\n";

    return 0;
}
