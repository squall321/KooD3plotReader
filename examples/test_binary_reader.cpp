#include "kood3plot/core/BinaryReader.hpp"
#include "kood3plot/Types.hpp"
#include <iostream>
#include <iomanip>
#include <memory>

int main(int argc, char* argv[]) {
    std::string filepath = "../results/d3plot";

    if (argc > 1) {
        filepath = argv[1];
    }

    std::cout << "Testing BinaryReader with: " << filepath << std::endl;
    std::cout << "========================================" << std::endl;

    // Create reader
    auto reader = std::make_shared<kood3plot::core::BinaryReader>(filepath);

    // Open file
    auto err = reader->open();
    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open file: " << kood3plot::error_to_string(err) << std::endl;
        return 1;
    }

    std::cout << "✓ File opened successfully" << std::endl;

    // Check detected format
    auto precision = reader->get_precision();
    auto endian = reader->get_endian();
    auto word_size = reader->get_word_size();

    std::cout << "\nDetected Format:" << std::endl;
    std::cout << "  Precision:  " << (precision == kood3plot::Precision::SINGLE ? "Single (4 bytes)" : "Double (8 bytes)") << std::endl;
    std::cout << "  Endianness: " << (endian == kood3plot::Endian::LITTLE ? "Little-endian" : "Big-endian") << std::endl;
    std::cout << "  Word size:  " << word_size << " bytes" << std::endl;

    // Read some control words
    std::cout << "\nControl Words (first 20 words as float):" << std::endl;
    std::cout << std::fixed << std::setprecision(6);

    for (size_t i = 0; i < 20; ++i) {
        try {
            float value = reader->read_float(i);
            std::cout << "  Word[" << std::setw(2) << i << "] = "
                      << std::setw(15) << value;

            // Special words
            if (i == 0) std::cout << "  (TITLE start?)";
            if (i == 14) std::cout << "  (VERSION - should be ~900-1200)";
            if (i == 9) std::cout << "  (NDIM/NUMNP)";

            std::cout << std::endl;
        } catch (const std::exception& e) {
            std::cerr << "  Error reading word " << i << ": " << e.what() << std::endl;
        }
    }

    // Read version specifically
    std::cout << "\nVersion check:" << std::endl;
    try {
        double version = reader->read_double(14);
        std::cout << "  Version (word 14) = " << version << std::endl;

        if (version >= 900.0 && version <= 2000.0) {
            std::cout << "  ✓ Version is valid LS-DYNA version" << std::endl;
        } else {
            std::cout << "  ⚠ Version seems unusual" << std::endl;
        }
    } catch (const std::exception& e) {
        std::cerr << "  Error reading version: " << e.what() << std::endl;
    }

    // Read some integers
    std::cout << "\nSome control words as integers:" << std::endl;
    for (size_t i = 9; i < 15; ++i) {
        try {
            int32_t value = reader->read_int(i);
            std::cout << "  Word[" << std::setw(2) << i << "] = "
                      << std::setw(10) << value;

            if (i == 9) std::cout << "  (NDIM?)";
            if (i == 10) std::cout << "  (NUMNP?)";

            std::cout << std::endl;
        } catch (const std::exception& e) {
            std::cerr << "  Error reading word " << i << ": " << e.what() << std::endl;
        }
    }

    // Test array reading
    std::cout << "\nTesting array read (words 0-9):" << std::endl;
    try {
        auto values = reader->read_float_array(0, 10);
        for (size_t i = 0; i < values.size(); ++i) {
            std::cout << "  [" << i << "] = " << values[i] << std::endl;
        }
    } catch (const std::exception& e) {
        std::cerr << "  Error reading array: " << e.what() << std::endl;
    }

    reader->close();
    std::cout << "\n✓ Test completed successfully" << std::endl;

    return 0;
}
