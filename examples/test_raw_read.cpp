/**
 * @file test_raw_read.cpp
 * @brief Read raw bytes from family file to understand structure
 */

#include "kood3plot/core/BinaryReader.hpp"
#include "kood3plot/parsers/ControlDataParser.hpp"
#include <iostream>
#include <iomanip>
#include <cmath>

int main(int argc, char* argv[]) {
    std::string base_file = "results/d3plot";
    std::string family_file = "results/d3plot01";

    if (argc > 1) {
        base_file = argv[1];
    }
    if (argc > 2) {
        family_file = argv[2];
    }

    std::cout << "=== Raw Read Test ===\n\n";

    // Open base file to get format
    auto base_reader = std::make_shared<kood3plot::core::BinaryReader>(base_file);
    auto err = base_reader->open();
    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open base file\n";
        return 1;
    }

    // Get control data for reference
    kood3plot::parsers::ControlDataParser ctrl_parser(base_reader);
    auto cd = ctrl_parser.parse();

    std::cout << "Control Data:\n";
    std::cout << "  NUMNP = " << cd.NUMNP << "\n";
    std::cout << "  NDIM = " << cd.NDIM << "\n";
    std::cout << "  NGLBV = " << cd.NGLBV << "\n";
    std::cout << "  NND = " << cd.NND << "\n";
    std::cout << "  ENN = " << cd.ENN << "\n";
    std::cout << "  State size = " << (1 + cd.NGLBV + cd.NND + cd.ENN) << " words\n\n";

    // Open family file
    auto family_reader = std::make_shared<kood3plot::core::BinaryReader>(family_file);
    err = family_reader->open_family_file(base_reader->get_precision(), base_reader->get_endian());
    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open family file\n";
        return 1;
    }

    std::cout << "Family file: " << family_file << "\n";
    std::cout << "File size: " << family_reader->get_file_size_words() << " words\n\n";

    // Read first 200 words and display
    std::cout << "=== First 200 words of family file ===\n";
    std::cout << std::fixed << std::setprecision(6);

    for (int i = 0; i < 200; ++i) {
        double val = family_reader->read_double(i);

        // Print index and value
        std::cout << std::setw(4) << i << ": " << std::setw(15) << val;

        // Add annotations for expected positions
        if (i == 0) std::cout << "  <-- TIME (state 0)?";
        if (i == 1) std::cout << "  <-- global[0]?";
        if (i == 168) std::cout << "  <-- nodal start? (1+NGLBV)";

        // Check if this looks like a valid time value
        if (i < 10 && val >= 0.0 && val < 1.0) {
            std::cout << " (valid time?)";
        }

        std::cout << "\n";

        // Group every 10 lines
        if ((i + 1) % 20 == 0) std::cout << "\n";
    }

    // Try reading what should be the second state's time
    size_t state_size = 1 + cd.NGLBV + cd.NND + cd.ENN;
    std::cout << "\n=== Check state boundaries ===\n";
    std::cout << "State size: " << state_size << " words\n";

    for (int state = 0; state < 3; ++state) {
        size_t offset = state * state_size;
        if (offset < family_reader->get_file_size_words()) {
            double time = family_reader->read_double(offset);
            std::cout << "State " << state << " (offset " << offset << "): time = " << time << "\n";
        }
    }

    // Check if maybe there's a header
    std::cout << "\n=== Looking for potential header ===\n";

    // Check first few values for common header patterns
    double w0 = family_reader->read_double(0);
    double w1 = family_reader->read_double(1);
    double w2 = family_reader->read_double(2);

    std::cout << "word[0] = " << w0 << "\n";
    std::cout << "word[1] = " << w1 << "\n";
    std::cout << "word[2] = " << w2 << "\n";

    // Check if word 0 could be an integer marker
    int32_t iw0 = base_reader->read_int(0);  // Try reading as int from base
    std::cout << "\nBase file word[0] as int: " << iw0 << "\n";

    base_reader->close();
    family_reader->close();

    std::cout << "\n✓ Test complete\n";
    return 0;
}
