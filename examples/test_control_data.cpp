#include "kood3plot/core/BinaryReader.hpp"
#include "kood3plot/parsers/ControlDataParser.hpp"
#include "kood3plot/Types.hpp"
#include <iostream>
#include <iomanip>
#include <memory>

int main(int argc, char* argv[]) {
    std::string filepath = "../results/d3plot";

    if (argc > 1) {
        filepath = argv[1];
    }

    std::cout << "Testing ControlDataParser with: " << filepath << std::endl;
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

    kood3plot::parsers::ControlDataParser parser(reader);
    kood3plot::data::ControlData cd;

    try {
        cd = parser.parse();
        std::cout << "✓ Control data parsed successfully" << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "✗ Failed to parse control data: " << e.what() << std::endl;
        return 1;
    }

    // Display control data
    std::cout << "\n=== Control Data Summary ===" << std::endl;
    std::cout << std::fixed << std::setprecision(6);

    std::cout << "\n[Dimensions & Nodes]" << std::endl;
    std::cout << "  NDIM    = " << cd.NDIM << " (dimensions)" << std::endl;
    std::cout << "  NUMNP   = " << cd.NUMNP << " (number of nodes)" << std::endl;
    std::cout << "  NGLBV   = " << cd.NGLBV << " (global variables)" << std::endl;

    std::cout << "\n[Node Flags]" << std::endl;
    std::cout << "  IT = " << cd.IT << " (temperature)" << std::endl;
    std::cout << "  IU = " << cd.IU << " (displacement)" << std::endl;
    std::cout << "  IV = " << cd.IV << " (velocity)" << std::endl;
    std::cout << "  IA = " << cd.IA << " (acceleration)" << std::endl;

    std::cout << "\n[Solid Elements (8-node)]" << std::endl;
    std::cout << "  NEL8    = " << cd.NEL8 << " (number of solids)" << std::endl;
    std::cout << "  NUMMAT8 = " << cd.NUMMAT8 << " (materials)" << std::endl;
    std::cout << "  NV3D    = " << cd.NV3D << " (values per element)" << std::endl;

    std::cout << "\n[Beam Elements (2-node)]" << std::endl;
    std::cout << "  NEL2    = " << cd.NEL2 << " (number of beams)" << std::endl;
    std::cout << "  NUMMAT2 = " << cd.NUMMAT2 << " (materials)" << std::endl;
    std::cout << "  NV1D    = " << cd.NV1D << " (values per element)" << std::endl;

    std::cout << "\n[Shell Elements (4-node)]" << std::endl;
    std::cout << "  NEL4    = " << cd.NEL4 << " (number of shells)" << std::endl;
    std::cout << "  NUMMAT4 = " << cd.NUMMAT4 << " (materials)" << std::endl;
    std::cout << "  NV2D    = " << cd.NV2D << " (values per element)" << std::endl;

    std::cout << "\n[Thick Shell Elements (8-node)]" << std::endl;
    std::cout << "  NELT    = " << cd.NELT << " (number of thick shells)" << std::endl;
    std::cout << "  NUMMATT = " << cd.NUMMATT << " (materials)" << std::endl;
    std::cout << "  NV3DT   = " << cd.NV3DT << " (values per element)" << std::endl;

    std::cout << "\n[Integration & Output Flags]" << std::endl;
    std::cout << "  MAXINT  = " << cd.MAXINT << " (integration points)" << std::endl;
    std::cout << "  MDLOPT  = " << cd.MDLOPT << " (material deletion option)" << std::endl;
    std::cout << "  NEIPH   = " << cd.NEIPH << " (extra solid values)" << std::endl;
    std::cout << "  NEIPS   = " << cd.NEIPS << " (extra shell values)" << std::endl;

    std::cout << "\n[Shell Output Flags (converted from 999/1000)]" << std::endl;
    std::cout << "  IOSHL[0] = " << cd.IOSHL[0] << " (6 stress components)" << std::endl;
    std::cout << "  IOSHL[1] = " << cd.IOSHL[1] << " (plastic strain)" << std::endl;
    std::cout << "  IOSHL[2] = " << cd.IOSHL[2] << " (force resultants)" << std::endl;
    std::cout << "  IOSHL[3] = " << cd.IOSHL[3] << " (thickness/energy)" << std::endl;

    std::cout << "\n[Solid Output Flags]" << std::endl;
    std::cout << "  IOSOL[0] = " << cd.IOSOL[0] << " (stress)" << std::endl;
    std::cout << "  IOSOL[1] = " << cd.IOSOL[1] << " (plastic strain)" << std::endl;

    std::cout << "\n[Strain & Other Flags]" << std::endl;
    std::cout << "  ISTRN   = " << cd.ISTRN << " (strain tensor output)" << std::endl;
    std::cout << "  IDTDT   = " << cd.IDTDT << " (various flags)" << std::endl;
    std::cout << "  NARBS   = " << cd.NARBS << " (arbitrary numbering)" << std::endl;
    std::cout << "  EXTRA   = " << cd.EXTRA << " (extended words)" << std::endl;

    std::cout << "\n[Time Step]" << std::endl;
    std::cout << "  DT      = " << cd.DT << " (time step size)" << std::endl;

    std::cout << "\n[Computed Values]" << std::endl;
    std::cout << "  NND     = " << cd.NND << " (total nodal data words per state)" << std::endl;
    std::cout << "  ENN     = " << cd.ENN << " (total element data words per state)" << std::endl;

    // Summary statistics
    int total_elements = std::abs(cd.NEL8) + cd.NEL2 + cd.NEL4 + cd.NELT;
    std::cout << "\n=== Summary ===" << std::endl;
    std::cout << "  Total nodes:    " << cd.NUMNP << std::endl;
    std::cout << "  Total elements: " << total_elements << std::endl;
    std::cout << "    Solids:       " << std::abs(cd.NEL8) << std::endl;
    std::cout << "    Beams:        " << cd.NEL2 << std::endl;
    std::cout << "    Shells:       " << cd.NEL4 << std::endl;
    std::cout << "    Thick Shells: " << cd.NELT << std::endl;

    reader->close();
    std::cout << "\n✓ Test completed successfully" << std::endl;

    return 0;
}
