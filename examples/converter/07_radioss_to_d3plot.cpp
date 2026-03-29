/**
 * @file 07_radioss_to_d3plot.cpp
 * @brief Direct Radioss → D3plot converter CLI
 *
 * Usage:
 *   converter_radioss_to_d3plot <A00_file> [output_d3plot] [--verbose]
 *
 * Example:
 *   converter_radioss_to_d3plot simA000 output.d3plot --verbose
 */

#include "kood3plot/converter/RadiossToD3plotConverter.h"
#include <iostream>
#include <string>
#include <chrono>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <A00_file> [output_d3plot] [--verbose]\n";
        std::cerr << "  Converts OpenRadioss animation files (A00+A01...) to LS-DYNA d3plot.\n";
        return 1;
    }

    std::string a00_path = argv[1];
    std::string d3plot_path = "d3plot";
    bool verbose = false;

    for (int i = 2; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--verbose" || arg == "-v") {
            verbose = true;
        } else if (arg[0] != '-') {
            d3plot_path = arg;
        }
    }

    std::cout << "=== Radioss → D3plot Converter ===\n";
    std::cout << "Input:  " << a00_path << "\n";
    std::cout << "Output: " << d3plot_path << "\n";

    auto t0 = std::chrono::high_resolution_clock::now();

    kood3plot::converter::RadiossToD3plotConverter converter;
    kood3plot::converter::RadiossConversionOptions opts;
    opts.verbose = verbose;
    opts.title = "Radioss to D3plot";

    auto result = converter.convert(a00_path, d3plot_path, opts,
        [](const std::string& msg) {
            std::cout << "  " << msg << "\n";
        });

    auto t1 = std::chrono::high_resolution_clock::now();
    double elapsed = std::chrono::duration<double>(t1 - t0).count();

    if (result.success) {
        std::cout << "\n=== Conversion Complete ===\n";
        std::cout << "  Nodes:    " << result.num_nodes << "\n";
        std::cout << "  Solids:   " << result.num_solids << "\n";
        std::cout << "  Shells:   " << result.num_shells << "\n";
        std::cout << "  Beams:    " << result.num_beams << "\n";
        std::cout << "  States:   " << result.num_states << "\n";
        std::cout << "  Written:  " << result.bytes_written << " bytes\n";
        std::cout << "  Files:    " << result.output_files.size() << "\n";
        for (const auto& f : result.output_files) {
            std::cout << "    " << f << "\n";
        }
        std::cout << "  Elapsed:  " << elapsed << "s\n";
        return 0;
    } else {
        std::cerr << "ERROR: " << result.error_message << "\n";
        return 1;
    }
}
