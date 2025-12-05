/**
 * @file test_surface_stress.cpp
 * @brief Unit tests for SurfaceStressAnalyzer module
 * @author KooD3plot Development Team
 * @date 2024-12-04
 *
 * Compile:
 *   (Build with CMake as part of the project)
 *
 * Run:
 *   ./test_surface_stress [d3plot_path]
 */

#include "kood3plot/analysis/SurfaceStressAnalyzer.hpp"
#include "kood3plot/analysis/SurfaceExtractor.hpp"
#include "kood3plot/D3plotReader.hpp"
#include <iostream>
#include <cmath>
#include <cassert>

using namespace kood3plot;
using namespace kood3plot::analysis;

#define TEST_ASSERT(cond, msg) \
    if (!(cond)) { \
        std::cerr << "FAILED: " << msg << " at line " << __LINE__ << "\n"; \
        return false; \
    }

#define APPROX_EQ(a, b, eps) (std::abs((a) - (b)) < (eps))

// ============================================================
// Unit Tests (No d3plot required)
// ============================================================

bool test_face_stress_result_struct() {
    std::cout << "  Testing FaceStressResult struct... ";

    FaceStressResult result;
    result.element_id = 100;
    result.part_id = 1;
    result.time = 0.001;
    result.sxx = 100.0;
    result.syy = 50.0;
    result.szz = 25.0;
    result.sxy = 10.0;
    result.syz = 5.0;
    result.szx = 2.0;
    result.von_mises = 75.0;
    result.normal_stress = 80.0;
    result.shear_stress = 30.0;
    result.face_normal = Vec3(0, 0, 1);
    result.face_centroid = Vec3(1, 2, 3);

    TEST_ASSERT(result.element_id == 100, "Element ID should be 100");
    TEST_ASSERT(APPROX_EQ(result.von_mises, 75.0, 1e-6), "Von Mises should be 75");
    TEST_ASSERT(APPROX_EQ(result.face_normal.z, 1.0, 1e-6), "Face normal Z should be 1");

    std::cout << "PASSED\n";
    return true;
}

bool test_surface_stress_stats_struct() {
    std::cout << "  Testing SurfaceStressStats struct... ";

    SurfaceStressStats stats;
    stats.time = 0.002;
    stats.num_faces = 100;
    stats.von_mises_max = 150.0;
    stats.von_mises_min = 10.0;
    stats.von_mises_avg = 80.0;
    stats.von_mises_max_element = 500;
    stats.normal_stress_max = 100.0;
    stats.shear_stress_max = 50.0;

    TEST_ASSERT(APPROX_EQ(stats.time, 0.002, 1e-6), "Time should be 0.002");
    TEST_ASSERT(stats.num_faces == 100, "Num faces should be 100");
    TEST_ASSERT(stats.von_mises_max_element == 500, "Max element should be 500");

    std::cout << "PASSED\n";
    return true;
}

bool test_surface_stress_history_struct() {
    std::cout << "  Testing SurfaceStressHistory struct... ";

    SurfaceStressHistory history;
    history.reference_direction = Vec3(0, 0, -1);
    history.angle_threshold_degrees = 45.0;

    // Add some time points
    for (int i = 0; i < 5; ++i) {
        SurfaceStressStats stats;
        stats.time = i * 0.001;
        stats.von_mises_max = 100 + i * 10;
        history.time_history.push_back(stats);
    }

    history.global_von_mises_max = 140.0;
    history.time_of_max_von_mises = 0.004;

    TEST_ASSERT(history.time_history.size() == 5, "Should have 5 time points");
    TEST_ASSERT(APPROX_EQ(history.angle_threshold_degrees, 45.0, 1e-6), "Angle threshold should be 45");
    TEST_ASSERT(APPROX_EQ(history.global_von_mises_max, 140.0, 1e-6), "Global max should be 140");

    std::cout << "PASSED\n";
    return true;
}

bool test_csv_export_format() {
    std::cout << "  Testing CSV export format... ";

    SurfaceStressHistory history;
    history.reference_direction = Vec3(0, 0, 1);
    history.angle_threshold_degrees = 30.0;

    // Add test data
    SurfaceStressStats stats1;
    stats1.time = 0.001;
    stats1.num_faces = 50;
    stats1.von_mises_max = 100.0;
    stats1.von_mises_min = 10.0;
    stats1.von_mises_avg = 55.0;
    stats1.von_mises_max_element = 123;
    stats1.normal_stress_max = 80.0;
    stats1.normal_stress_min = -20.0;
    stats1.normal_stress_avg = 30.0;
    stats1.normal_stress_max_element = 456;
    stats1.shear_stress_max = 40.0;
    stats1.shear_stress_min = 5.0;
    stats1.shear_stress_avg = 22.5;
    stats1.shear_stress_max_element = 789;
    history.time_history.push_back(stats1);

    // Export to CSV
    std::string filepath = "/tmp/test_surface_stress.csv";
    bool success = SurfaceStressAnalyzer::exportToCSV(history, filepath);
    TEST_ASSERT(success, "CSV export should succeed");

    // Read and verify
    std::ifstream file(filepath);
    TEST_ASSERT(file.is_open(), "Should be able to open CSV file");

    std::string header;
    std::getline(file, header);
    TEST_ASSERT(header.find("VonMises_Max") != std::string::npos, "Header should contain VonMises_Max");
    TEST_ASSERT(header.find("NormalStress_Max") != std::string::npos, "Header should contain NormalStress_Max");
    TEST_ASSERT(header.find("ShearStress_Max") != std::string::npos, "Header should contain ShearStress_Max");

    std::string data_line;
    std::getline(file, data_line);
    TEST_ASSERT(data_line.find("0.001") != std::string::npos, "Data should contain time 0.001");
    TEST_ASSERT(data_line.find("100") != std::string::npos, "Data should contain von mises max 100");

    std::cout << "PASSED\n";
    return true;
}

bool test_to_analysis_stats_conversion() {
    std::cout << "  Testing toAnalysisStats conversion... ";

    SurfaceStressHistory history;
    history.reference_direction = Vec3(0, 0, -1);
    history.angle_threshold_degrees = 45.0;

    SurfaceStressStats stats;
    stats.time = 0.001;
    stats.num_faces = 100;
    stats.normal_stress_max = 150.0;
    stats.normal_stress_min = -50.0;
    stats.normal_stress_avg = 50.0;
    stats.normal_stress_max_element = 999;
    stats.shear_stress_max = 75.0;
    stats.shear_stress_min = 5.0;
    stats.shear_stress_avg = 40.0;
    stats.shear_stress_max_element = 888;
    history.time_history.push_back(stats);

    SurfaceAnalysisStats result = SurfaceStressAnalyzer::toAnalysisStats(history);

    TEST_ASSERT(APPROX_EQ(result.reference_direction.z, -1.0, 1e-6), "Reference direction Z should be -1");
    TEST_ASSERT(APPROX_EQ(result.angle_threshold_degrees, 45.0, 1e-6), "Angle threshold should be 45");
    TEST_ASSERT(result.data.size() == 1, "Should have 1 time point");
    TEST_ASSERT(APPROX_EQ(result.data[0].normal_stress_max, 150.0, 1e-6), "Normal stress max should be 150");
    TEST_ASSERT(result.data[0].normal_stress_max_element_id == 999, "Max element should be 999");

    std::cout << "PASSED\n";
    return true;
}

// ============================================================
// Integration Tests (D3plot required)
// ============================================================

bool test_with_d3plot(const std::string& d3plot_path) {
    std::cout << "  Testing with d3plot file: " << d3plot_path << "... ";

    D3plotReader reader(d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cout << "SKIPPED (cannot open file)\n";
        return true;
    }

    // Extract exterior surfaces
    SurfaceExtractor extractor(reader);
    auto surfaces = extractor.extractExteriorSurfaces();

    if (surfaces.faces.empty()) {
        std::cout << "SKIPPED (no exterior faces found)\n";
        return true;
    }

    std::cout << "\n";
    std::cout << "    Total exterior faces: " << surfaces.faces.size() << "\n";

    // Create analyzer
    SurfaceStressAnalyzer analyzer(reader);
    std::cout << "    NV3D (values per solid): " << analyzer.getNV3D() << "\n";

    // Analyze first state only
    data::StateData state = reader.read_state(0);
    if (state.solid_data.empty() && state.shell_data.empty()) {
        std::cout << "    SKIPPED (empty state data)\n";
        return true;
    }

    auto stats = analyzer.analyzeState(surfaces.faces, state);
    std::cout << "    State 0 (t=" << stats.time << "):\n";
    std::cout << "      Von Mises: max=" << stats.von_mises_max
              << ", min=" << stats.von_mises_min
              << ", avg=" << stats.von_mises_avg << "\n";
    std::cout << "      Normal stress: max=" << stats.normal_stress_max
              << ", min=" << stats.normal_stress_min << "\n";
    std::cout << "      Shear stress: max=" << stats.shear_stress_max
              << ", min=" << stats.shear_stress_min << "\n";

    std::cout << "    PASSED\n";
    return true;
}

bool test_direction_filtered_analysis(const std::string& d3plot_path) {
    std::cout << "  Testing direction-filtered analysis... ";

    D3plotReader reader(d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cout << "SKIPPED\n";
        return true;
    }

    // Extract exterior surfaces
    SurfaceExtractor extractor(reader);
    auto surfaces = extractor.extractExteriorSurfaces();

    if (surfaces.faces.empty()) {
        std::cout << "SKIPPED\n";
        return true;
    }

    // Filter for bottom-facing surfaces (pointing in -Z direction)
    Vec3 down(0, 0, -1);
    auto bottom_faces = SurfaceExtractor::filterByDirection(surfaces.faces, down, 45.0);

    std::cout << "\n";
    std::cout << "    Bottom-facing faces (45 deg): " << bottom_faces.size() << "\n";

    if (bottom_faces.empty()) {
        std::cout << "    SKIPPED (no bottom faces)\n";
        return true;
    }

    // Analyze with progress callback
    SurfaceStressAnalyzer analyzer(reader);
    size_t num_states = reader.get_num_states();

    auto history = analyzer.analyzeAllStates(
        bottom_faces, down, 45.0,
        [](size_t current, size_t total, const std::string& msg) {
            if (current == 0 || current == total - 1 || current % 10 == 0) {
                std::cout << "      Progress: " << current + 1 << "/" << total << " - " << msg << "\n";
            }
        }
    );

    std::cout << "    Analysis complete:\n";
    std::cout << "      Time points: " << history.time_history.size() << "\n";
    std::cout << "      Global max Von Mises: " << history.global_von_mises_max
              << " at t=" << history.time_of_max_von_mises << "\n";
    std::cout << "      Global max normal stress: " << history.global_normal_stress_max
              << " at t=" << history.time_of_max_normal_stress << "\n";
    std::cout << "      Global max shear stress: " << history.global_shear_stress_max
              << " at t=" << history.time_of_max_shear_stress << "\n";

    // Export to CSV
    std::string csv_path = "/tmp/surface_stress_bottom.csv";
    bool exported = SurfaceStressAnalyzer::exportToCSV(history, csv_path);
    std::cout << "    CSV export: " << (exported ? "SUCCESS" : "FAILED") << "\n";

    TEST_ASSERT(history.time_history.size() == num_states, "Should have stats for all states");

    std::cout << "    PASSED\n";
    return true;
}

bool test_single_face_analysis(const std::string& d3plot_path) {
    std::cout << "  Testing single face stress analysis... ";

    D3plotReader reader(d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cout << "SKIPPED\n";
        return true;
    }

    // Extract surfaces
    SurfaceExtractor extractor(reader);
    auto surfaces = extractor.extractExteriorSurfaces();

    if (surfaces.faces.empty()) {
        std::cout << "SKIPPED\n";
        return true;
    }

    // Get first face
    Face& face = surfaces.faces[0];

    // Read first state
    data::StateData state = reader.read_state(0);
    if (state.solid_data.empty()) {
        std::cout << "SKIPPED (empty state)\n";
        return true;
    }

    // Analyze single face
    SurfaceStressAnalyzer analyzer(reader);
    FaceStressResult result = analyzer.analyzeFace(face, state);

    std::cout << "\n";
    std::cout << "    Face element ID: " << result.element_id << "\n";
    std::cout << "    Face normal: (" << result.face_normal.x << ", "
              << result.face_normal.y << ", " << result.face_normal.z << ")\n";
    std::cout << "    Stress tensor: sxx=" << result.sxx << ", syy=" << result.syy
              << ", szz=" << result.szz << "\n";
    std::cout << "    Von Mises: " << result.von_mises << "\n";
    std::cout << "    Normal stress: " << result.normal_stress << "\n";
    std::cout << "    Shear stress: " << result.shear_stress << "\n";
    std::cout << "    Principal stresses: max=" << result.max_principal
              << ", min=" << result.min_principal << "\n";

    // Verify stress tensor calculation
    StressTensor tensor(result.sxx, result.syy, result.szz,
                        result.sxy, result.syz, result.szx);
    double expected_vm = tensor.vonMises();
    TEST_ASSERT(APPROX_EQ(result.von_mises, expected_vm, 1e-3),
                "Von Mises should match StressTensor calculation");

    std::cout << "    PASSED\n";
    return true;
}

// ============================================================
// Main Test Runner
// ============================================================

int main(int argc, char* argv[]) {
    std::cout << "========================================\n";
    std::cout << "SurfaceStressAnalyzer Unit Tests\n";
    std::cout << "========================================\n\n";

    int passed = 0;
    int failed = 0;

    std::cout << "Unit Tests:\n";
    if (test_face_stress_result_struct()) passed++; else failed++;
    if (test_surface_stress_stats_struct()) passed++; else failed++;
    if (test_surface_stress_history_struct()) passed++; else failed++;
    if (test_csv_export_format()) passed++; else failed++;
    if (test_to_analysis_stats_conversion()) passed++; else failed++;

    // D3plot integration tests
    std::string d3plot_path = "results/d3plot";
    if (argc > 1) {
        d3plot_path = argv[1];
    }

    std::cout << "\nD3plot Integration Tests:\n";
    if (test_with_d3plot(d3plot_path)) passed++; else failed++;
    if (test_direction_filtered_analysis(d3plot_path)) passed++; else failed++;
    if (test_single_face_analysis(d3plot_path)) passed++; else failed++;

    std::cout << "\n========================================\n";
    std::cout << "Results: " << passed << " passed, " << failed << " failed\n";
    std::cout << "========================================\n";

    return failed > 0 ? 1 : 0;
}
