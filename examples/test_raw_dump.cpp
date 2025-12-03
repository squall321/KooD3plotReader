/**
 * @file test_raw_dump.cpp
 * @brief Dump raw bytes from family file to understand structure
 */

#include "kood3plot/core/BinaryReader.hpp"
#include "kood3plot/parsers/ControlDataParser.hpp"
#include <iostream>
#include <iomanip>
#include <cmath>

int main(int argc, char* argv[]) {
    std::string base_file = "results/d3plot";
    std::string family_file = "results/d3plot01";

    if (argc > 1) base_file = argv[1];
    if (argc > 2) family_file = argv[2];

    std::cout << "=== Raw Dump Test ===\n\n";

    // Open base file
    auto base_reader = std::make_shared<kood3plot::core::BinaryReader>(base_file);
    auto err = base_reader->open();
    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open base file\n";
        return 1;
    }

    // Parse control data
    kood3plot::parsers::ControlDataParser ctrl_parser(base_reader);
    auto cd = ctrl_parser.parse();

    std::cout << "Control Data:\n";
    std::cout << "  NUMNP = " << cd.NUMNP << "\n";
    std::cout << "  NDIM = " << cd.NDIM << "\n";
    std::cout << "  NGLBV = " << cd.NGLBV << "\n";
    std::cout << "  NND = " << cd.NND << " (nodal words per state)\n";
    std::cout << "  ENN = " << cd.ENN << " (element words per state)\n";
    std::cout << "  IT/IU/IV/IA = " << cd.IT << "/" << cd.IU << "/" << cd.IV << "/" << cd.IA << "\n";

    size_t state_size = 1 + cd.NGLBV + cd.NND + cd.ENN;
    std::cout << "  State size = " << state_size << " words\n\n";

    // Open family file with base file's format
    auto family_reader = std::make_shared<kood3plot::core::BinaryReader>(family_file);
    err = family_reader->open_family_file(base_reader->get_precision(), base_reader->get_endian());
    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open family file\n";
        return 1;
    }

    size_t file_words = family_reader->get_file_size_words();
    std::cout << "Family file: " << family_file << "\n";
    std::cout << "File size: " << file_words << " words\n";
    std::cout << "Expected states: " << (file_words / state_size) << "\n\n";

    // Dump first 300 words
    std::cout << "=== First 300 words of family file ===\n";
    std::cout << std::fixed << std::setprecision(6);

    for (int i = 0; i < 300 && (size_t)i < file_words; ++i) {
        double val = family_reader->read_double(i);

        std::cout << std::setw(5) << i << ": " << std::setw(18) << val;

        // Annotations
        if (i == 0) std::cout << "  <-- Expected: TIME (should be ~0.001)";
        if (i == 1) std::cout << "  <-- Expected: Global[0]";
        if (i == cd.NGLBV + 1) std::cout << "  <-- Expected: Nodal data start";
        if (i == 168) std::cout << "  <-- Word 168 (1+NGLBV=168)";

        std::cout << "\n";

        if ((i + 1) % 20 == 0) std::cout << "---\n";
    }

    // Check expected state boundaries
    std::cout << "\n=== State Time Values (expected positions) ===\n";
    for (int state = 0; state < 5; ++state) {
        size_t offset = state * state_size;
        if (offset < file_words) {
            double time = family_reader->read_double(offset);
            std::cout << "State " << state << " @ word " << offset << ": time = " << time << "\n";
        }
    }

    // Now let's search for the actual time values
    std::cout << "\n=== Searching for Time Values in File ===\n";
    std::cout << "Looking for values in range [0.0001, 0.1] (typical initial time)\n";

    int count = 0;
    for (size_t i = 0; i < std::min(file_words, (size_t)10000); ++i) {
        double val = family_reader->read_double(i);
        if (val >= 0.0001 && val <= 0.1) {
            std::cout << "  Word " << i << ": " << val << "\n";
            count++;
            if (count > 20) {
                std::cout << "  ... (showing first 20)\n";
                break;
            }
        }
    }

    base_reader->close();
    family_reader->close();

    std::cout << "\n✓ Test complete\n";
    return 0;
}
