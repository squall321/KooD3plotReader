#include "kood3plot/core/BinaryReader.hpp"
#include "kood3plot/parsers/ControlDataParser.hpp"
#include "kood3plot/parsers/StateDataParser.hpp"
#include "kood3plot/Types.hpp"
#include <iostream>
#include <iomanip>
#include <memory>

int main(int argc, char* argv[]) {
    std::string filepath = "../results/d3plot";

    if (argc > 1) {
        filepath = argv[1];
    }

    std::cout << "Testing StateDataParser with: " << filepath << std::endl;
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

    // Display control data summary
    std::cout << "\n[Control Data Summary]" << std::endl;
    std::cout << "  NUMNP  = " << cd.NUMNP << " nodes" << std::endl;
    std::cout << "  NEL8   = " << cd.NEL8 << " solids" << std::endl;
    std::cout << "  NGLBV  = " << cd.NGLBV << " global vars" << std::endl;
    std::cout << "  NND    = " << cd.NND << " nodal data words per state" << std::endl;
    std::cout << "  ENN    = " << cd.ENN << " element data words per state" << std::endl;
    std::cout << "  IT/IU/IV/IA = " << cd.IT << "/" << cd.IU << "/" << cd.IV << "/" << cd.IA << std::endl;

    // Parse state data
    std::cout << "\nParsing State Data..." << std::endl;
    kood3plot::parsers::StateDataParser state_parser(reader, cd);
    std::vector<kood3plot::data::StateData> states;

    try {
        states = state_parser.parse_all();
        std::cout << "✓ State data parsed successfully" << std::endl;
        std::cout << "  Number of states: " << states.size() << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "✗ Failed to parse state data: " << e.what() << std::endl;
        return 1;
    }

    if (states.empty()) {
        std::cout << "\n⚠ No states found in file" << std::endl;
        return 0;
    }

    // Display state statistics
    std::cout << "\n=== State Data Statistics ===" << std::endl;
    std::cout << std::fixed << std::setprecision(6);

    // Display first state
    std::cout << "\n[First State (State 0)]" << std::endl;
    const auto& state0 = states[0];
    std::cout << "  Time: " << state0.time << std::endl;
    std::cout << "  Global vars: " << state0.global_vars.size() << " values" << std::endl;

    if (!state0.global_vars.empty()) {
        std::cout << "    First 3 global vars: ";
        for (size_t i = 0; i < std::min(size_t(3), state0.global_vars.size()); ++i) {
            if (i > 0) std::cout << ", ";
            std::cout << state0.global_vars[i];
        }
        std::cout << std::endl;
    }

    std::cout << "  Node temperatures: " << state0.node_temperatures.size() << " values" << std::endl;
    std::cout << "  Node displacements: " << state0.node_displacements.size() << " values" << std::endl;
    std::cout << "  Node velocities: " << state0.node_velocities.size() << " values" << std::endl;
    std::cout << "  Node accelerations: " << state0.node_accelerations.size() << " values" << std::endl;

    std::cout << "  Solid data: " << state0.solid_data.size() << " values" << std::endl;
    if (!state0.solid_data.empty()) {
        std::cout << "    First 3 solid values: ";
        for (size_t i = 0; i < std::min(size_t(3), state0.solid_data.size()); ++i) {
            if (i > 0) std::cout << ", ";
            std::cout << state0.solid_data[i];
        }
        std::cout << std::endl;
    }

    std::cout << "  Thick shell data: " << state0.thick_shell_data.size() << " values" << std::endl;
    std::cout << "  Beam data: " << state0.beam_data.size() << " values" << std::endl;
    std::cout << "  Shell data: " << state0.shell_data.size() << " values" << std::endl;

    // Display last state if multiple states
    if (states.size() > 1) {
        std::cout << "\n[Last State (State " << (states.size() - 1) << ")]" << std::endl;
        const auto& last_state = states[states.size() - 1];
        std::cout << "  Time: " << last_state.time << std::endl;
        std::cout << "  Global vars: " << last_state.global_vars.size() << " values" << std::endl;

        if (!last_state.global_vars.empty()) {
            std::cout << "    First 3 global vars: ";
            for (size_t i = 0; i < std::min(size_t(3), last_state.global_vars.size()); ++i) {
                if (i > 0) std::cout << ", ";
                std::cout << last_state.global_vars[i];
            }
            std::cout << std::endl;
        }
    }

    // Time progression
    if (states.size() >= 2) {
        std::cout << "\n[Time Progression]" << std::endl;
        std::cout << "  First 5 time steps:" << std::endl;
        for (size_t i = 0; i < std::min(size_t(5), states.size()); ++i) {
            std::cout << "    State " << std::setw(3) << i << ": t = " << std::setw(12) << states[i].time << std::endl;
        }

        if (states.size() > 5) {
            std::cout << "  ..." << std::endl;
            std::cout << "  Last 3 time steps:" << std::endl;
            for (size_t i = states.size() - 3; i < states.size(); ++i) {
                std::cout << "    State " << std::setw(3) << i << ": t = " << std::setw(12) << states[i].time << std::endl;
            }
        }
    }

    // Verification
    std::cout << "\n=== Verification ===" << std::endl;
    bool data_sizes_ok = true;

    for (size_t i = 0; i < states.size(); ++i) {
        const auto& state = states[i];

        // Check expected sizes
        size_t expected_global = cd.NGLBV;
        if (state.global_vars.size() != expected_global) {
            std::cout << "  ✗ State " << i << ": global_vars size mismatch (expected "
                      << expected_global << ", got " << state.global_vars.size() << ")" << std::endl;
            data_sizes_ok = false;
        }

        // Check solid data size
        size_t expected_solid = std::abs(cd.NEL8) * cd.NV3D;
        if (state.solid_data.size() != expected_solid) {
            std::cout << "  ✗ State " << i << ": solid_data size mismatch (expected "
                      << expected_solid << ", got " << state.solid_data.size() << ")" << std::endl;
            data_sizes_ok = false;
            break;  // Only report first error
        }
    }

    if (data_sizes_ok) {
        std::cout << "  ✓ All state data sizes match expected values" << std::endl;
    }

    reader->close();
    std::cout << "\n✓ Test completed successfully" << std::endl;

    return 0;
}
