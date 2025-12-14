/**
 * @file 02_hdf5_benchmark.cpp
 * @brief HDF5 압축 및 양자화 벤치마크
 *
 * 테스트 항목:
 * 1. 압축률 (gzip, 양자화)
 * 2. 데이터 정확도 (유효숫자)
 * 3. 처리 속도
 *
 * Week 1: gzip 압축만 (무손실)
 * Week 2: 양자화 추가 (손실, but 정밀도 보장)
 */

#include <kood3plot/hdf5/HDF5Writer.hpp>
#include <kood3plot/hdf5/HDF5Reader.hpp>
#include <kood3plot/hdf5/HDF5TestUtils.hpp>
#include <kood3plot/quantization/Quantizers.hpp>
#include <kood3plot/D3plotReader.hpp>

#include <iostream>
#include <iomanip>
#include <chrono>
#include <filesystem>

namespace fs = std::filesystem;

void print_header(const std::string& title) {
    std::cout << "\n";
    std::cout << "╔══════════════════════════════════════════════════════════════╗\n";
    std::cout << "║ " << std::left << std::setw(62) << title << "║\n";
    std::cout << "╚══════════════════════════════════════════════════════════════╝\n";
}

void print_section(const std::string& title) {
    std::cout << "\n▶ " << title << "\n";
    std::cout << std::string(60, '-') << "\n";
}

/**
 * @brief Week 1 테스트: gzip 압축만 (무손실)
 */
void run_week1_test() {
    print_header("Week 1: gzip Compression Test (Lossless)");

    using namespace kood3plot::hdf5::test;

    // Test cases
    struct TestCase {
        std::string name;
        int nx, ny, nz;
        double spacing;
    };

    std::vector<TestCase> cases = {
        {"Small (1k nodes)",    32,  32,  1, 1.0},
        {"Medium (10k nodes)", 100, 100,  1, 1.0},
        {"Large (100k nodes)",  50,  50, 40, 1.0},
    };

    std::cout << "\n";
    std::cout << std::setw(20) << "Test Case"
              << std::setw(12) << "Nodes"
              << std::setw(12) << "Elements"
              << std::setw(12) << "Original"
              << std::setw(12) << "Compressed"
              << std::setw(10) << "Ratio"
              << std::setw(10) << "Saved"
              << "\n";
    std::cout << std::string(88, '-') << "\n";

    for (const auto& tc : cases) {
        auto mesh = MeshGenerator::create_grid_mesh(tc.nx, tc.ny, tc.nz, tc.spacing);
        std::string hdf5_path = "test_" + std::to_string(mesh.nodes.size()) + ".h5";

        auto result = run_compression_test(mesh, hdf5_path);

        std::cout << std::setw(20) << tc.name
                  << std::setw(12) << mesh.nodes.size()
                  << std::setw(12) << (mesh.solids.size() + mesh.shells.size())
                  << std::setw(10) << (result.original_size_bytes / 1024) << " KB"
                  << std::setw(10) << (result.compressed_size_bytes / 1024) << " KB"
                  << std::setw(9) << std::fixed << std::setprecision(1) << result.compression_ratio << "%"
                  << std::setw(9) << result.space_saved_percent << "%"
                  << "\n";

        // Validation
        if (!result.node_validation.passed) {
            std::cout << "  ⚠ Node validation FAILED: " << result.node_validation.message << "\n";
        }

        fs::remove(hdf5_path);
    }

    std::cout << "\n✓ Week 1 Target: 40-60% space saved with gzip (lossless)\n";
}

/**
 * @brief Week 2 테스트: 양자화 정확도
 */
void run_week2_quantization_test() {
    print_header("Week 2: Quantization Precision Test");

    using namespace kood3plot::quantization;

    // Generate test data
    std::mt19937 gen(42);
    const size_t NUM_SAMPLES = 100000;

    // Displacement data
    print_section("Displacement Quantization (16-bit, target: 0.01mm)");
    {
        std::uniform_real_distribution<> dis(-500.0, 500.0);
        std::vector<Vec3> disp_data;
        disp_data.reserve(NUM_SAMPLES);

        for (size_t i = 0; i < NUM_SAMPLES; ++i) {
            disp_data.push_back(Vec3{dis(gen), dis(gen), dis(gen)});
        }

        DisplacementQuantizer quantizer;
        quantizer.calibrate(disp_data);

        auto quantized = quantizer.quantize_array(disp_data);
        auto dequantized = quantizer.dequantize_array(quantized);

        // Statistics
        double max_error = 0.0;
        double sum_error = 0.0;

        for (size_t i = 0; i < disp_data.size(); ++i) {
            double error = (disp_data[i] - dequantized[i]).magnitude();
            max_error = std::max(max_error, error);
            sum_error += error;
        }

        double mean_error = sum_error / disp_data.size();

        std::cout << "  Data range:  -500 to 500 mm\n";
        std::cout << "  Samples:     " << NUM_SAMPLES << "\n";
        std::cout << "  Max error:   " << std::fixed << std::setprecision(6) << max_error << " mm\n";
        std::cout << "  Mean error:  " << mean_error << " mm\n";
        std::cout << "  Target:      0.01 mm\n";
        std::cout << "  Status:      " << (max_error < 0.01 ? "✓ PASS" : "✗ FAIL") << "\n";

        // Compression
        size_t original = NUM_SAMPLES * 3 * sizeof(double);
        size_t compressed = quantized.size() * sizeof(uint16_t);
        std::cout << "  Compression: " << (100.0 - 100.0 * compressed / original) << "% saved\n";
    }

    // Von Mises stress data
    print_section("Von Mises Stress Quantization (16-bit log, target: 1%)");
    {
        // Generate realistic stress data: 0.01 to 10000 MPa range
        std::uniform_real_distribution<> log_dis(-2, 4);  // 0.01 to 10000 MPa
        std::vector<double> stress_data;
        stress_data.reserve(NUM_SAMPLES);

        for (size_t i = 0; i < NUM_SAMPLES; ++i) {
            stress_data.push_back(std::pow(10.0, log_dis(gen)));
        }

        VonMisesQuantizer quantizer;
        // Set threshold: below 0.1 MPa, accuracy doesn't matter
        quantizer.set_threshold(0.1);
        quantizer.calibrate(stress_data);

        auto quantized = quantizer.quantize_array(stress_data);
        auto dequantized = quantizer.dequantize_array(quantized);

        // Statistics - only for values above threshold
        double threshold = quantizer.get_threshold();
        double max_rel_error = 0.0;
        double sum_rel_error = 0.0;
        int count_above = 0;
        int count_below = 0;

        for (size_t i = 0; i < stress_data.size(); ++i) {
            if (stress_data[i] >= threshold) {
                double rel_error = std::abs(stress_data[i] - dequantized[i]) / stress_data[i] * 100.0;
                max_rel_error = std::max(max_rel_error, rel_error);
                sum_rel_error += rel_error;
                count_above++;
            } else {
                count_below++;
            }
        }

        double mean_rel_error = (count_above > 0) ? sum_rel_error / count_above : 0.0;

        std::cout << "  Data range:  0.01 to 10000 MPa (6 decades)\n";
        std::cout << "  Threshold:   " << threshold << " MPa (below = don't care)\n";
        std::cout << "  Samples:     " << NUM_SAMPLES << " (" << count_above << " above threshold)\n";
        std::cout << "  Max rel error:  " << std::fixed << std::setprecision(4) << max_rel_error << "%\n";
        std::cout << "  Mean rel error: " << mean_rel_error << "%\n";
        std::cout << "  Target:         1% (practical engineering tolerance)\n";
        std::cout << "  Status:         " << (max_rel_error < 1.0 ? "PASS" : (max_rel_error < 2.0 ? "OK" : "FAIL")) << "\n";

        // Compression
        size_t original = NUM_SAMPLES * sizeof(double);
        size_t compressed = quantized.size() * sizeof(uint16_t);
        std::cout << "  Compression:    " << (100.0 - 100.0 * compressed / original) << "% saved\n";
    }

    // Strain data
    print_section("Strain Quantization (16-bit, target: 0.01%)");
    {
        std::uniform_real_distribution<> dis(-0.1, 0.5);  // -10% to 50% strain
        std::vector<double> strain_data;
        strain_data.reserve(NUM_SAMPLES);

        for (size_t i = 0; i < NUM_SAMPLES; ++i) {
            strain_data.push_back(dis(gen));
        }

        StrainQuantizer quantizer;
        quantizer.calibrate(strain_data);

        auto quantized = quantizer.quantize_array(strain_data);
        auto dequantized = quantizer.dequantize_array(quantized);

        // Statistics
        double max_error = 0.0;
        double sum_error = 0.0;

        for (size_t i = 0; i < strain_data.size(); ++i) {
            double error = std::abs(strain_data[i] - dequantized[i]);
            max_error = std::max(max_error, error);
            sum_error += error;
        }

        double mean_error = sum_error / strain_data.size();

        std::cout << "  Data range:  -0.1 to 0.5 (strain)\n";
        std::cout << "  Samples:     " << NUM_SAMPLES << "\n";
        std::cout << "  Max error:   " << std::scientific << std::setprecision(4) << max_error << "\n";
        std::cout << "  Mean error:  " << mean_error << "\n";
        std::cout << "  Target:      0.0001 (0.01%)\n";
        std::cout << "  Status:      " << (max_error < 0.0001 ? "✓ PASS" : "✗ FAIL") << "\n";

        // Compression
        size_t original = NUM_SAMPLES * sizeof(double);
        size_t compressed = quantized.size() * sizeof(uint16_t);
        std::cout << "  Compression: " << std::fixed << std::setprecision(1)
                  << (100.0 - 100.0 * compressed / original) << "% saved\n";
    }
}

/**
 * @brief 유효숫자 분석 테스트
 */
void run_significant_digits_test() {
    print_header("Significant Digits Analysis");

    using namespace kood3plot::hdf5::test;

    // Create random mesh
    auto mesh = MeshGenerator::create_random_mesh(10000, 8000);

    // Write and read back
    {
        kood3plot::hdf5::HDF5Writer writer("test_sigdig.h5");
        writer.write_mesh(mesh);
        writer.close();
    }

    {
        kood3plot::hdf5::HDF5Reader reader("test_sigdig.h5");
        auto loaded_nodes = reader.read_nodes();

        // Extract coordinates
        auto original_coords = extract_coordinates(mesh);
        std::vector<double> loaded_coords;
        for (const auto& node : loaded_nodes) {
            loaded_coords.push_back(node.x);
            loaded_coords.push_back(node.y);
            loaded_coords.push_back(node.z);
        }

        auto result = run_significant_digits_test(original_coords, loaded_coords);

        print_section("Node Coordinates (gzip, lossless)");
        std::cout << "  Minimum significant digits: " << result.min_digits << "\n";
        std::cout << "  Maximum significant digits: " << result.max_digits << "\n";
        std::cout << "  Mean significant digits:    " << std::fixed << std::setprecision(1)
                  << result.mean_digits << "\n";
        std::cout << "  6+ digits achieved:         " << result.ratio_meeting_6_digits << "%\n";

        std::cout << "\n  Expected: 15 digits (double precision, lossless)\n";
        std::cout << "  Status:   " << (result.min_digits >= 14 ? "✓ PASS" : "✗ CHECK") << "\n";
    }

    fs::remove("test_sigdig.h5");
}

/**
 * @brief Week 3 테스트: Temporal Delta Compression
 */
void run_week3_temporal_test() {
    print_header("Week 3: Temporal Delta Compression Test");

    using namespace kood3plot::hdf5;

    const size_t NUM_NODES = 10000;
    const int NUM_TIMESTEPS = 10;
    const double DT = 0.001;  // 1ms timestep

    // Generate synthetic time-series data
    std::mt19937 gen(42);
    std::uniform_real_distribution<> pos_dis(-100.0, 100.0);
    std::uniform_real_distribution<> delta_dis(-0.5, 0.5);  // Small changes between frames

    // Create test mesh
    kood3plot::data::Mesh mesh;
    mesh.nodes.resize(NUM_NODES);
    for (size_t i = 0; i < NUM_NODES; ++i) {
        mesh.nodes[i].x = pos_dis(gen);
        mesh.nodes[i].y = pos_dis(gen);
        mesh.nodes[i].z = pos_dis(gen);
    }

    // Generate timestep data with realistic temporal correlation
    std::vector<kood3plot::data::StateData> states(NUM_TIMESTEPS);
    std::vector<double> prev_disp(NUM_NODES * 3, 0.0);

    for (int t = 0; t < NUM_TIMESTEPS; ++t) {
        states[t].time = t * DT;
        states[t].node_displacements.resize(NUM_NODES * 3);

        for (size_t i = 0; i < NUM_NODES * 3; ++i) {
            // Add small delta from previous frame
            states[t].node_displacements[i] = prev_disp[i] + delta_dis(gen);
            prev_disp[i] = states[t].node_displacements[i];
        }
    }

    print_section("Compression Mode Comparison");

    struct TestResult {
        std::string mode;
        size_t file_size;
        double compression_ratio;
        double max_error;
        double mean_error;
    };
    std::vector<TestResult> results;

    // Test 1: No compression (raw)
    {
        std::string path = "test_temporal_none.h5";
        {
            HDF5Writer writer(path, CompressionOptions::none());
            writer.write_mesh(mesh);
            for (int t = 0; t < NUM_TIMESTEPS; ++t) {
                writer.write_timestep(t, states[t]);
            }
            writer.close();
        }

        TestResult result;
        result.mode = "None (raw double)";
        result.file_size = fs::file_size(path);

        // Read back and validate
        {
            HDF5Reader reader(path);
            double max_err = 0.0, sum_err = 0.0;
            int count = 0;
            for (int t = 0; t < NUM_TIMESTEPS; ++t) {
                auto loaded = reader.read_state(t);
                if (loaded && !loaded->node_displacements.empty()) {
                    for (size_t i = 0; i < states[t].node_displacements.size(); ++i) {
                        double err = std::abs(states[t].node_displacements[i] - loaded->node_displacements[i]);
                        max_err = std::max(max_err, err);
                        sum_err += err;
                        count++;
                    }
                }
            }
            result.max_error = max_err;
            result.mean_error = (count > 0) ? sum_err / count : 0.0;
        }

        results.push_back(result);
        fs::remove(path);
    }

    // Test 2: Lossless gzip only
    {
        std::string path = "test_temporal_lossless.h5";
        {
            HDF5Writer writer(path, CompressionOptions::lossless());
            writer.write_mesh(mesh);
            for (int t = 0; t < NUM_TIMESTEPS; ++t) {
                writer.write_timestep(t, states[t]);
            }
            writer.close();
        }

        TestResult result;
        result.mode = "Lossless (gzip)";
        result.file_size = fs::file_size(path);

        {
            HDF5Reader reader(path);
            double max_err = 0.0, sum_err = 0.0;
            int count = 0;
            for (int t = 0; t < NUM_TIMESTEPS; ++t) {
                auto loaded = reader.read_state(t);
                if (loaded && !loaded->node_displacements.empty()) {
                    for (size_t i = 0; i < states[t].node_displacements.size(); ++i) {
                        double err = std::abs(states[t].node_displacements[i] - loaded->node_displacements[i]);
                        max_err = std::max(max_err, err);
                        sum_err += err;
                        count++;
                    }
                }
            }
            result.max_error = max_err;
            result.mean_error = (count > 0) ? sum_err / count : 0.0;
        }

        results.push_back(result);
        fs::remove(path);
    }

    // Test 3: Quantization + Delta compression (balanced)
    {
        std::string path = "test_temporal_balanced.h5";
        {
            HDF5Writer writer(path, CompressionOptions::balanced());
            writer.write_mesh(mesh);
            for (int t = 0; t < NUM_TIMESTEPS; ++t) {
                writer.write_timestep(t, states[t]);
            }
            writer.close();
        }

        TestResult result;
        result.mode = "Balanced (quant+delta)";
        result.file_size = fs::file_size(path);

        {
            HDF5Reader reader(path);
            double max_err = 0.0, sum_err = 0.0;
            int count = 0;
            for (int t = 0; t < NUM_TIMESTEPS; ++t) {
                auto loaded = reader.read_state(t);
                if (loaded && !loaded->node_displacements.empty()) {
                    for (size_t i = 0; i < states[t].node_displacements.size(); ++i) {
                        double err = std::abs(states[t].node_displacements[i] - loaded->node_displacements[i]);
                        max_err = std::max(max_err, err);
                        sum_err += err;
                        count++;
                    }
                }
            }
            result.max_error = max_err;
            result.mean_error = (count > 0) ? sum_err / count : 0.0;
        }

        results.push_back(result);
        fs::remove(path);
    }

    // Test 4: Maximum compression
    {
        std::string path = "test_temporal_max.h5";
        {
            HDF5Writer writer(path, CompressionOptions::maximum());
            writer.write_mesh(mesh);
            for (int t = 0; t < NUM_TIMESTEPS; ++t) {
                writer.write_timestep(t, states[t]);
            }
            writer.close();
        }

        TestResult result;
        result.mode = "Maximum (quant+delta+gzip9)";
        result.file_size = fs::file_size(path);

        {
            HDF5Reader reader(path);
            double max_err = 0.0, sum_err = 0.0;
            int count = 0;
            for (int t = 0; t < NUM_TIMESTEPS; ++t) {
                auto loaded = reader.read_state(t);
                if (loaded && !loaded->node_displacements.empty()) {
                    for (size_t i = 0; i < states[t].node_displacements.size(); ++i) {
                        double err = std::abs(states[t].node_displacements[i] - loaded->node_displacements[i]);
                        max_err = std::max(max_err, err);
                        sum_err += err;
                        count++;
                    }
                }
            }
            result.max_error = max_err;
            result.mean_error = (count > 0) ? sum_err / count : 0.0;
        }

        results.push_back(result);
        fs::remove(path);
    }

    // Calculate baseline (raw size)
    size_t baseline_size = results[0].file_size;

    // Print results
    std::cout << "\n";
    std::cout << std::setw(28) << "Mode"
              << std::setw(12) << "Size"
              << std::setw(10) << "Ratio"
              << std::setw(14) << "Max Error"
              << std::setw(14) << "Mean Error"
              << "\n";
    std::cout << std::string(78, '-') << "\n";

    for (const auto& r : results) {
        double ratio = 100.0 * r.file_size / baseline_size;
        std::cout << std::setw(28) << r.mode
                  << std::setw(10) << (r.file_size / 1024) << " KB"
                  << std::setw(9) << std::fixed << std::setprecision(1) << ratio << "%"
                  << std::setw(14) << std::scientific << std::setprecision(2) << r.max_error
                  << std::setw(14) << r.mean_error
                  << "\n";
    }

    std::cout << "\n";
    std::cout << "Test Data:\n";
    std::cout << "  Nodes:      " << NUM_NODES << "\n";
    std::cout << "  Timesteps:  " << NUM_TIMESTEPS << "\n";
    std::cout << "  Data range: ±100mm displacement, ±0.5mm/frame delta\n";
    std::cout << "\n✓ Week 3 Target: >50% additional compression with delta (small deltas)\n";
}

/**
 * @brief 전체 벤치마크
 */
void run_full_benchmark() {
    print_header("Full Benchmark Suite");

    using namespace kood3plot::hdf5::test;
    run_benchmark_suite();
}

/**
 * @brief D3plot 파일 테스트 (실제 데이터)
 */
void run_d3plot_test(const std::string& d3plot_path) {
    print_header("D3plot File Test");

    std::cout << "File: " << d3plot_path << "\n\n";

    // Read D3plot
    kood3plot::D3plotReader reader(d3plot_path);
    if (reader.open() != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "Failed to open D3plot file\n";
        return;
    }

    auto mesh = reader.read_mesh();
    std::cout << "Loaded mesh:\n";
    std::cout << "  Nodes:  " << mesh.nodes.size() << "\n";
    std::cout << "  Solids: " << mesh.solids.size() << "\n";
    std::cout << "  Shells: " << mesh.shells.size() << "\n";
    std::cout << "  Beams:  " << mesh.beams.size() << "\n";

    // Run compression test
    using namespace kood3plot::hdf5::test;
    std::string hdf5_path = d3plot_path + ".h5";

    auto result = run_compression_test(mesh, hdf5_path);
    result.print();

    // Significant digits test
    {
        kood3plot::hdf5::HDF5Reader hdf_reader(hdf5_path);
        auto loaded_nodes = hdf_reader.read_nodes();

        auto original_coords = extract_coordinates(mesh);
        std::vector<double> loaded_coords;
        for (const auto& node : loaded_nodes) {
            loaded_coords.push_back(node.x);
            loaded_coords.push_back(node.y);
            loaded_coords.push_back(node.z);
        }

        auto sig_result = run_significant_digits_test(original_coords, loaded_coords);
        sig_result.print();
    }

    // Cleanup
    fs::remove(hdf5_path);
}

int main(int argc, char* argv[]) {
    std::cout << "\n";
    std::cout << "╔══════════════════════════════════════════════════════════════╗\n";
    std::cout << "║         KooD3plotReader HDF5 Benchmark Suite                 ║\n";
    std::cout << "║                 Phase 1 Week 1-3                             ║\n";
    std::cout << "╚══════════════════════════════════════════════════════════════╝\n";

    if (argc >= 2) {
        // Test with actual D3plot file
        run_d3plot_test(argv[1]);
    } else {
        // Run synthetic benchmarks
        run_week1_test();
        run_week2_quantization_test();
        run_week3_temporal_test();
        run_significant_digits_test();
        run_full_benchmark();
    }

    std::cout << "\n";
    std::cout << "╔══════════════════════════════════════════════════════════════╗\n";
    std::cout << "║                  Benchmark Complete                          ║\n";
    std::cout << "╚══════════════════════════════════════════════════════════════╝\n\n";

    return 0;
}
