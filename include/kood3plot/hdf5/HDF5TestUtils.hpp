#pragma once

#include <kood3plot/hdf5/HDF5Writer.hpp>
#include <kood3plot/hdf5/HDF5Reader.hpp>
#include <kood3plot/data/Mesh.hpp>
#include <kood3plot/data/StateData.hpp>
#include <kood3plot/Types.hpp>

#include <string>
#include <vector>
#include <chrono>
#include <iostream>
#include <iomanip>
#include <cmath>
#include <filesystem>
#include <random>
#include <algorithm>

namespace kood3plot {
namespace hdf5 {
namespace test {

// Use data::Mesh and data::Node types
using data::Mesh;
using data::Node;

/**
 * @brief 압축률 테스트 결과
 */
struct CompressionTestResult {
    // 크기 정보
    size_t original_size_bytes = 0;
    size_t compressed_size_bytes = 0;
    double compression_ratio = 0.0;    // compressed / original (percentage)
    double space_saved_percent = 0.0;  // (1 - ratio) * 100

    // 시간 정보
    double write_time_ms = 0.0;
    double read_time_ms = 0.0;
    double throughput_mb_per_sec = 0.0;

    // 정밀도 정보
    ValidationResult node_validation;
    ValidationResult element_validation;

    void print() const {
        std::cout << "\n========================================\n";
        std::cout << " 압축 테스트 결과\n";
        std::cout << "========================================\n\n";

        std::cout << "[크기 정보]\n";
        std::cout << "  원본 크기 (예상): " << (original_size_bytes / 1024) << " KB\n";
        std::cout << "  압축 후 크기:     " << (compressed_size_bytes / 1024) << " KB\n";
        std::cout << "  압축률:           " << std::fixed << std::setprecision(1)
                  << compression_ratio << "%\n";
        std::cout << "  공간 절약:        " << std::fixed << std::setprecision(1)
                  << space_saved_percent << "%\n";

        std::cout << "\n[성능 정보]\n";
        std::cout << "  쓰기 시간: " << std::fixed << std::setprecision(1)
                  << write_time_ms << " ms\n";
        std::cout << "  읽기 시간: " << std::fixed << std::setprecision(1)
                  << read_time_ms << " ms\n";
        std::cout << "  처리량:    " << std::fixed << std::setprecision(2)
                  << throughput_mb_per_sec << " MB/s\n";

        std::cout << "\n[데이터 정확도]\n";
        std::cout << "  노드 검증: " << (node_validation.passed ? "✓ PASS" : "✗ FAIL")
                  << " - " << node_validation.message << "\n";
        if (node_validation.max_error > 0) {
            std::cout << "    최대 오차: " << std::scientific << std::setprecision(6)
                      << node_validation.max_error << "\n";
            std::cout << "    평균 오차: " << node_validation.mean_error << "\n";
            std::cout << "    RMS 오차:  " << node_validation.rms_error << "\n";
        }

        std::cout << "  요소 검증: " << (element_validation.passed ? "✓ PASS" : "✗ FAIL")
                  << " - " << element_validation.message << "\n";

        std::cout << "\n========================================\n";
    }
};

/**
 * @brief 유효숫자 테스트 결과
 */
struct SignificantDigitsTestResult {
    int min_digits = 0;
    int max_digits = 0;
    double mean_digits = 0.0;
    double ratio_meeting_6_digits = 0.0;  // 6자리 이상 달성 비율
    double ratio_meeting_4_digits = 0.0;  // 4자리 이상 달성 비율

    void print() const {
        std::cout << "\n========================================\n";
        std::cout << " 유효숫자 분석 결과\n";
        std::cout << "========================================\n\n";

        std::cout << "  최소 유효숫자: " << min_digits << "자리\n";
        std::cout << "  최대 유효숫자: " << max_digits << "자리\n";
        std::cout << "  평균 유효숫자: " << std::fixed << std::setprecision(1)
                  << mean_digits << "자리\n";
        std::cout << "  6자리 이상 달성: " << std::fixed << std::setprecision(1)
                  << ratio_meeting_6_digits << "%\n";
        std::cout << "  4자리 이상 달성: " << std::fixed << std::setprecision(1)
                  << ratio_meeting_4_digits << "%\n";

        std::cout << "\n========================================\n";
    }
};

/**
 * @brief Test mesh generator utility
 */
class MeshGenerator {
public:
    /**
     * @brief Create a regular grid mesh
     * @param nx Number of nodes in x direction
     * @param ny Number of nodes in y direction
     * @param nz Number of nodes in z direction
     * @param spacing Grid spacing (mm)
     */
    static data::Mesh create_grid_mesh(int nx, int ny, int nz = 1, double spacing = 1.0) {
        data::Mesh mesh;

        // Create nodes
        int node_id = 0;
        for (int k = 0; k < nz; ++k) {
            for (int j = 0; j < ny; ++j) {
                for (int i = 0; i < nx; ++i) {
                    data::Node node;
                    node.id = node_id++;
                    node.x = i * spacing;
                    node.y = j * spacing;
                    node.z = k * spacing;
                    mesh.nodes.push_back(node);
                }
            }
        }

        // Create elements (hex for 3D, quad for 2D)
        int elem_id = 0;
        if (nz > 1) {
            // 3D: Hexahedral elements (solids)
            for (int k = 0; k < nz - 1; ++k) {
                for (int j = 0; j < ny - 1; ++j) {
                    for (int i = 0; i < nx - 1; ++i) {
                        Element solid;
                        solid.id = elem_id++;
                        solid.type = ElementType::SOLID;
                        solid.material_id = 1;
                        solid.node_ids.resize(8);

                        int n0 = k * ny * nx + j * nx + i;
                        int n1 = n0 + 1;
                        int n2 = n0 + nx + 1;
                        int n3 = n0 + nx;
                        int n4 = n0 + ny * nx;
                        int n5 = n4 + 1;
                        int n6 = n4 + nx + 1;
                        int n7 = n4 + nx;

                        solid.node_ids[0] = n0;
                        solid.node_ids[1] = n1;
                        solid.node_ids[2] = n2;
                        solid.node_ids[3] = n3;
                        solid.node_ids[4] = n4;
                        solid.node_ids[5] = n5;
                        solid.node_ids[6] = n6;
                        solid.node_ids[7] = n7;

                        mesh.solids.push_back(solid);
                    }
                }
            }
        } else {
            // 2D: Quad elements (shells)
            for (int j = 0; j < ny - 1; ++j) {
                for (int i = 0; i < nx - 1; ++i) {
                    Element shell;
                    shell.id = elem_id++;
                    shell.type = ElementType::SHELL;
                    shell.material_id = 1;
                    shell.node_ids.resize(4);

                    int n0 = j * nx + i;
                    int n1 = n0 + 1;
                    int n2 = n0 + nx + 1;
                    int n3 = n0 + nx;

                    shell.node_ids[0] = n0;
                    shell.node_ids[1] = n1;
                    shell.node_ids[2] = n2;
                    shell.node_ids[3] = n3;

                    mesh.shells.push_back(shell);
                }
            }
        }

        return mesh;
    }

    /**
     * @brief Create a mesh with random coordinates (for precision testing)
     */
    static data::Mesh create_random_mesh(int num_nodes, int num_elements,
                                   double coord_range = 1000.0) {
        data::Mesh mesh;
        std::mt19937 rng(42);  // Fixed seed for reproducibility
        std::uniform_real_distribution<double> dist(-0.5, 0.5);

        // Random nodes (various coordinate scales)
        for (int i = 0; i < num_nodes; ++i) {
            double scale = std::pow(10.0, (i % 10) - 5);  // 1e-5 ~ 1e4 range
            data::Node node;
            node.id = i;
            node.x = dist(rng) * coord_range * scale;
            node.y = dist(rng) * coord_range * scale;
            node.z = dist(rng) * coord_range * scale;
            mesh.nodes.push_back(node);
        }

        // Elements (random connectivity)
        std::uniform_int_distribution<int> node_dist(0, num_nodes - 1);
        for (int i = 0; i < num_elements; ++i) {
            Element solid;
            solid.id = i;
            solid.type = ElementType::SOLID;
            solid.material_id = (i % 10) + 1;
            solid.node_ids.resize(8);
            for (int j = 0; j < 8; ++j) {
                solid.node_ids[j] = node_dist(rng);
            }
            mesh.solids.push_back(solid);
        }

        return mesh;
    }
};

/**
 * @brief Run compression test
 * @param mesh Mesh to test
 * @param hdf5_path Temporary HDF5 file path
 */
inline CompressionTestResult run_compression_test(
    const data::Mesh& mesh,
    const std::string& hdf5_path = "test_compression.h5"
) {
    CompressionTestResult result;

    // Calculate original size
    result.original_size_bytes =
        mesh.nodes.size() * 3 * sizeof(double) +
        mesh.solids.size() * 8 * sizeof(int) +
        mesh.solids.size() * sizeof(int) +
        mesh.shells.size() * 4 * sizeof(int) +
        mesh.shells.size() * sizeof(int) +
        mesh.beams.size() * 2 * sizeof(int) +
        mesh.beams.size() * sizeof(int);

    // Measure write time
    auto write_start = std::chrono::high_resolution_clock::now();
    {
        HDF5Writer writer(hdf5_path);
        writer.write_mesh(mesh);
        writer.close();
    }
    auto write_end = std::chrono::high_resolution_clock::now();
    result.write_time_ms = std::chrono::duration<double, std::milli>(
        write_end - write_start
    ).count();

    // Get compressed size
    result.compressed_size_bytes = std::filesystem::file_size(hdf5_path);

    // Calculate compression ratio
    result.compression_ratio = 100.0 *
        static_cast<double>(result.compressed_size_bytes) /
        static_cast<double>(result.original_size_bytes);
    result.space_saved_percent = 100.0 - result.compression_ratio;

    // Measure read time and validate
    auto read_start = std::chrono::high_resolution_clock::now();
    {
        HDF5Reader reader(hdf5_path);

        // Convert to std::vector<data::Node> for validation
        std::vector<data::Node> nodes_for_validation;
        nodes_for_validation.reserve(mesh.nodes.size());
        for (const auto& n : mesh.nodes) {
            data::Node node;
            node.id = n.id;
            node.x = n.x;
            node.y = n.y;
            node.z = n.z;
            nodes_for_validation.push_back(node);
        }

        // Node validation
        result.node_validation = reader.validate_nodes(nodes_for_validation);

        // Element validation
        if (!mesh.solids.empty()) {
            result.element_validation = reader.validate_solids(mesh.solids);
        } else if (!mesh.shells.empty()) {
            result.element_validation = reader.validate_shells(mesh.shells);
        } else {
            result.element_validation.passed = true;
            result.element_validation.message = "No elements to validate";
        }
    }
    auto read_end = std::chrono::high_resolution_clock::now();
    result.read_time_ms = std::chrono::duration<double, std::milli>(
        read_end - read_start
    ).count();

    // Calculate throughput
    double total_size_mb = static_cast<double>(result.original_size_bytes) / (1024.0 * 1024.0);
    double total_time_sec = (result.write_time_ms + result.read_time_ms) / 1000.0;
    result.throughput_mb_per_sec = total_size_mb / total_time_sec;

    return result;
}

/**
 * @brief 유효숫자 테스트 실행
 * @param original 원본 값들
 * @param loaded 로드된 값들
 */
inline SignificantDigitsTestResult run_significant_digits_test(
    const std::vector<double>& original,
    const std::vector<double>& loaded
) {
    SignificantDigitsTestResult result;

    if (original.size() != loaded.size()) {
        return result;
    }

    std::vector<int> digits_list;
    digits_list.reserve(original.size());

    for (size_t i = 0; i < original.size(); ++i) {
        double orig = original[i];
        double load = loaded[i];

        if (std::abs(orig) < 1e-15) {
            if (std::abs(load) < 1e-15) {
                digits_list.push_back(15);  // Both zero
            }
            continue;
        }

        double rel_err = std::abs(orig - load) / std::abs(orig);
        int digits;
        if (rel_err < 1e-15) {
            digits = 15;
        } else {
            digits = static_cast<int>(-std::log10(rel_err));
        }
        digits_list.push_back(std::max(0, digits));
    }

    if (digits_list.empty()) {
        return result;
    }

    // 통계 계산
    result.min_digits = *std::min_element(digits_list.begin(), digits_list.end());
    result.max_digits = *std::max_element(digits_list.begin(), digits_list.end());

    double sum = 0.0;
    int count_6 = 0;
    int count_4 = 0;

    for (int d : digits_list) {
        sum += d;
        if (d >= 6) count_6++;
        if (d >= 4) count_4++;
    }

    result.mean_digits = sum / digits_list.size();
    result.ratio_meeting_6_digits = 100.0 * count_6 / digits_list.size();
    result.ratio_meeting_4_digits = 100.0 * count_4 / digits_list.size();

    return result;
}

/**
 * @brief Extract coordinate array from mesh
 */
inline std::vector<double> extract_coordinates(const data::Mesh& mesh) {
    std::vector<double> coords;
    coords.reserve(mesh.nodes.size() * 3);

    for (const auto& node : mesh.nodes) {
        coords.push_back(node.x);
        coords.push_back(node.y);
        coords.push_back(node.z);
    }

    return coords;
}

/**
 * @brief 벤치마크 스위트 실행
 */
inline void run_benchmark_suite() {
    std::cout << "\n";
    std::cout << "╔══════════════════════════════════════════════════════════════╗\n";
    std::cout << "║              HDF5 Compression Benchmark Suite                ║\n";
    std::cout << "╚══════════════════════════════════════════════════════════════╝\n";

    // Test 1: Small mesh (1k nodes)
    std::cout << "\n▶ Test 1: Small Mesh (1k nodes, 2D grid)\n";
    {
        auto mesh = MeshGenerator::create_grid_mesh(32, 32, 1, 1.0);
        auto result = run_compression_test(mesh, "bench_small.h5");
        result.print();
        std::filesystem::remove("bench_small.h5");
    }

    // Test 2: Medium mesh (10k nodes)
    std::cout << "\n▶ Test 2: Medium Mesh (10k nodes, 2D grid)\n";
    {
        auto mesh = MeshGenerator::create_grid_mesh(100, 100, 1, 1.0);
        auto result = run_compression_test(mesh, "bench_medium.h5");
        result.print();
        std::filesystem::remove("bench_medium.h5");
    }

    // Test 3: Large mesh (100k nodes)
    std::cout << "\n▶ Test 3: Large Mesh (100k nodes, 3D grid)\n";
    {
        auto mesh = MeshGenerator::create_grid_mesh(50, 50, 40, 1.0);
        auto result = run_compression_test(mesh, "bench_large.h5");
        result.print();
        std::filesystem::remove("bench_large.h5");
    }

    // Test 4: Random coordinates (precision test)
    std::cout << "\n▶ Test 4: Random Coordinates (precision test)\n";
    {
        auto mesh = MeshGenerator::create_random_mesh(10000, 8000);
        auto result = run_compression_test(mesh, "bench_random.h5");

        // Additional precision analysis
        HDF5Reader reader("bench_random.h5");
        auto loaded_nodes = reader.read_nodes();

        auto original_coords = extract_coordinates(mesh);
        std::vector<double> loaded_coords;
        for (const auto& node : loaded_nodes) {
            loaded_coords.push_back(node.x);
            loaded_coords.push_back(node.y);
            loaded_coords.push_back(node.z);
        }

        auto sig_result = run_significant_digits_test(original_coords, loaded_coords);

        result.print();
        sig_result.print();

        std::filesystem::remove("bench_random.h5");
    }

    std::cout << "\n╔══════════════════════════════════════════════════════════════╗\n";
    std::cout << "║                    Benchmark Complete                        ║\n";
    std::cout << "╚══════════════════════════════════════════════════════════════╝\n\n";
}

} // namespace test
} // namespace hdf5
} // namespace kood3plot
