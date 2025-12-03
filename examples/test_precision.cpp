/**
 * @file test_precision.cpp
 * @brief Check precision and word size of d3plot files
 */

#include "kood3plot/core/BinaryReader.hpp"
#include "kood3plot/Types.hpp"
#include <iostream>
#include <iomanip>
#include <memory>
#include <fstream>

int main(int argc, char* argv[]) {
    std::string base_file = "results/d3plot";
    std::string family_file = "results/d3plot01";

    if (argc > 1) base_file = argv[1];
    if (argc > 2) family_file = argv[2];

    std::cout << "=== Precision Test ===\n\n";

    // Check base file
    auto base_reader = std::make_shared<kood3plot::core::BinaryReader>(base_file);
    auto err = base_reader->open();
    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open base file\n";
        return 1;
    }

    std::cout << "Base file: " << base_file << "\n";
    std::cout << "  Precision: " << (base_reader->get_precision() == kood3plot::core::Precision::SINGLE ? "SINGLE (4 bytes)" : "DOUBLE (8 bytes)") << "\n";
    std::cout << "  Endian: " << (base_reader->get_endian() == kood3plot::core::Endian::LITTLE ? "LITTLE" : "BIG") << "\n";
    std::cout << "  Word size: " << base_reader->get_word_size() << " bytes\n";
    std::cout << "  File size: " << base_reader->get_file_size_words() << " words\n";
    std::cout << "  File size: " << (base_reader->get_file_size_words() * base_reader->get_word_size()) << " bytes\n";
    std::cout << "  Version: " << base_reader->get_version() << "\n\n";

    // Check family file
    auto family_reader = std::make_shared<kood3plot::core::BinaryReader>(family_file);
    err = family_reader->open_family_file(base_reader->get_precision(), base_reader->get_endian());
    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open family file\n";
        return 1;
    }

    std::cout << "Family file: " << family_file << "\n";
    std::cout << "  Precision: " << (family_reader->get_precision() == kood3plot::core::Precision::SINGLE ? "SINGLE (4 bytes)" : "DOUBLE (8 bytes)") << "\n";
    std::cout << "  Word size: " << family_reader->get_word_size() << " bytes\n";
    std::cout << "  File size: " << family_reader->get_file_size_words() << " words\n";
    std::cout << "  File size: " << (family_reader->get_file_size_words() * family_reader->get_word_size()) << " bytes\n\n";

    // Also check actual file size on disk
    std::ifstream f1(base_file, std::ios::binary | std::ios::ate);
    std::ifstream f2(family_file, std::ios::binary | std::ios::ate);

    std::cout << "Actual file sizes on disk:\n";
    std::cout << "  " << base_file << ": " << f1.tellg() << " bytes\n";
    std::cout << "  " << family_file << ": " << f2.tellg() << " bytes\n\n";

    // Test reading same word as int and float
    std::cout << "=== Reading first 10 words as different types ===\n";
    for (int i = 0; i < 10; ++i) {
        double d = family_reader->read_double(i);
        float f = family_reader->read_float(i);
        int32_t n = family_reader->read_int(i);

        std::cout << "Word " << i << ": double=" << std::fixed << std::setprecision(6) << d
                  << ", float=" << f
                  << ", int=" << n << "\n";
    }

    base_reader->close();
    family_reader->close();

    std::cout << "\n✓ Test complete\n";
    return 0;
}
