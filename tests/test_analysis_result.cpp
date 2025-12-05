/**
 * @file test_analysis_result.cpp
 * @brief Unit tests for AnalysisResult module
 * @author KooD3plot Development Team
 * @date 2024-12-04
 *
 * Compile:
 *   g++ -std=c++17 -I../include -o test_analysis_result test_analysis_result.cpp
 *
 * Run:
 *   ./test_analysis_result
 */

#include "kood3plot/analysis/AnalysisResult.hpp"
#include <iostream>
#include <cmath>
#include <cassert>

using namespace kood3plot::analysis;

#define TEST_ASSERT(cond, msg) \
    if (!(cond)) { \
        std::cerr << "FAILED: " << msg << " at line " << __LINE__ << "\n"; \
        return false; \
    }

// ============================================================
// Tests
// ============================================================

bool test_metadata() {
    std::cout << "  Testing metadata... ";

    AnalysisMetadata meta;
    meta.d3plot_path = "/path/to/d3plot";
    meta.num_states = 100;
    meta.start_time = 0.0;
    meta.end_time = 0.01;
    meta.analyzed_parts = {1, 2, 3};
    meta.setCurrentDate();

    TEST_ASSERT(!meta.analysis_date.empty(), "Date should be set");
    TEST_ASSERT(meta.analysis_date.find("T") != std::string::npos, "Date should be ISO 8601 format");

    std::cout << "PASSED\n";
    return true;
}

bool test_part_time_series() {
    std::cout << "  Testing PartTimeSeriesStats... ";

    PartTimeSeriesStats stats;
    stats.part_id = 1;
    stats.part_name = "Part_001";
    stats.quantity = "von_mises";
    stats.unit = "MPa";

    // Add some time points
    for (int i = 0; i < 10; ++i) {
        TimePointStats tp;
        tp.time = i * 0.001;
        tp.max_value = 100.0 + i * 10;  // 100, 110, 120, ..., 190
        tp.min_value = 10.0 + i;
        tp.avg_value = 50.0 + i * 5;
        tp.max_element_id = 1000 + i;
        stats.data.push_back(tp);
    }

    TEST_ASSERT(stats.size() == 10, "Should have 10 time points");
    TEST_ASSERT(!stats.empty(), "Should not be empty");
    TEST_ASSERT(std::abs(stats.globalMax() - 190.0) < 1e-10, "Global max should be 190");
    TEST_ASSERT(std::abs(stats.globalMin() - 10.0) < 1e-10, "Global min should be 10");
    TEST_ASSERT(std::abs(stats.timeOfGlobalMax() - 0.009) < 1e-10, "Time of max should be 0.009");

    std::cout << "PASSED\n";
    return true;
}

bool test_json_generation() {
    std::cout << "  Testing JSON generation... ";

    AnalysisResult result;
    result.metadata.d3plot_path = "/path/to/d3plot";
    result.metadata.num_states = 100;
    result.metadata.start_time = 0.0;
    result.metadata.end_time = 0.01;
    result.metadata.analyzed_parts = {1, 2, 3};
    result.metadata.setCurrentDate();
    result.metadata.kood3plot_version = "1.0.0";

    // Add stress history
    PartTimeSeriesStats stress;
    stress.part_id = 1;
    stress.part_name = "Part_001";
    stress.quantity = "von_mises";
    stress.unit = "MPa";

    for (int i = 0; i < 5; ++i) {
        TimePointStats tp;
        tp.time = i * 0.001;
        tp.max_value = 100.0 + i * 10;
        tp.min_value = 10.0;
        tp.avg_value = 50.0;
        tp.max_element_id = 1000;
        stress.data.push_back(tp);
    }
    result.stress_history.push_back(stress);

    // Add surface analysis
    SurfaceAnalysisStats surface;
    surface.description = "Bottom facing surfaces";
    surface.reference_direction = Vec3(0, 0, -1);
    surface.angle_threshold_degrees = 30.0;
    surface.part_ids = {1, 2};
    surface.num_faces = 100;

    for (int i = 0; i < 5; ++i) {
        SurfaceTimePointStats tp;
        tp.time = i * 0.001;
        tp.normal_stress_max = 50.0 + i * 5;
        tp.normal_stress_min = -20.0;
        tp.normal_stress_avg = 15.0;
        tp.shear_stress_max = 30.0 + i * 3;
        tp.shear_stress_avg = 10.0;
        surface.data.push_back(tp);
    }
    result.surface_analysis.push_back(surface);

    // Generate JSON
    std::string json = result.toJSON(true);

    // Basic validation
    TEST_ASSERT(!json.empty(), "JSON should not be empty");
    TEST_ASSERT(json.find("\"metadata\"") != std::string::npos, "JSON should contain metadata");
    TEST_ASSERT(json.find("\"stress_history\"") != std::string::npos, "JSON should contain stress_history");
    TEST_ASSERT(json.find("\"surface_analysis\"") != std::string::npos, "JSON should contain surface_analysis");
    TEST_ASSERT(json.find("\"von_mises\"") != std::string::npos, "JSON should contain von_mises");
    TEST_ASSERT(json.find("\"Bottom facing surfaces\"") != std::string::npos, "JSON should contain surface description");
    TEST_ASSERT(json.find("-1.000000]") != std::string::npos, "JSON should contain reference direction");

    std::cout << "PASSED\n";
    return true;
}

bool test_json_save() {
    std::cout << "  Testing JSON save to file... ";

    AnalysisResult result;
    result.metadata.d3plot_path = "test/d3plot";
    result.metadata.num_states = 10;
    result.metadata.setCurrentDate();

    PartTimeSeriesStats stress;
    stress.part_id = 1;
    stress.quantity = "von_mises";

    TimePointStats tp;
    tp.time = 0.0;
    tp.max_value = 100.0;
    stress.data.push_back(tp);
    result.stress_history.push_back(stress);

    // Save to file
    std::string filepath = "/tmp/test_analysis_result.json";
    TEST_ASSERT(result.saveToFile(filepath), "Should save file successfully");

    // Verify file exists and has content
    std::ifstream file(filepath);
    TEST_ASSERT(file.good(), "File should exist");

    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string content = buffer.str();

    TEST_ASSERT(content.find("\"metadata\"") != std::string::npos, "Saved file should contain metadata");

    std::cout << "PASSED\n";
    return true;
}

bool test_csv_export() {
    std::cout << "  Testing CSV export... ";

    AnalysisResult result;

    // Add two parts with stress history
    for (int p = 1; p <= 2; ++p) {
        PartTimeSeriesStats stress;
        stress.part_id = p;
        stress.quantity = "von_mises";

        for (int i = 0; i < 5; ++i) {
            TimePointStats tp;
            tp.time = i * 0.001;
            tp.max_value = 100.0 * p + i * 10;
            tp.min_value = 10.0 * p;
            tp.avg_value = 50.0 * p;
            stress.data.push_back(tp);
        }
        result.stress_history.push_back(stress);
    }

    // Export to CSV
    std::string filepath = "/tmp/test_stress_export.csv";
    TEST_ASSERT(result.exportStressToCSV(filepath), "Should export CSV successfully");

    // Verify file content
    std::ifstream file(filepath);
    TEST_ASSERT(file.good(), "CSV file should exist");

    std::string header;
    std::getline(file, header);
    TEST_ASSERT(header.find("Time") != std::string::npos, "Header should contain Time");
    TEST_ASSERT(header.find("Part1_Max") != std::string::npos, "Header should contain Part1_Max");
    TEST_ASSERT(header.find("Part2_Max") != std::string::npos, "Header should contain Part2_Max");

    std::cout << "PASSED\n";
    return true;
}

bool test_special_characters() {
    std::cout << "  Testing JSON escape of special characters... ";

    AnalysisResult result;
    result.metadata.d3plot_path = "path/with\"quotes\"and\\backslash";
    result.metadata.setCurrentDate();

    std::string json = result.toJSON(true);

    // Should have escaped quotes and backslashes
    TEST_ASSERT(json.find("\\\"") != std::string::npos, "Should escape quotes");
    TEST_ASSERT(json.find("\\\\") != std::string::npos, "Should escape backslashes");

    std::cout << "PASSED\n";
    return true;
}

bool test_large_dataset_json() {
    std::cout << "  Testing large dataset JSON (truncation)... ";

    AnalysisResult result;
    result.metadata.d3plot_path = "test";
    result.metadata.setCurrentDate();

    PartTimeSeriesStats stress;
    stress.part_id = 1;
    stress.quantity = "von_mises";

    // Add 100 time points
    for (int i = 0; i < 100; ++i) {
        TimePointStats tp;
        tp.time = i * 0.001;
        tp.max_value = 100.0 + i;
        stress.data.push_back(tp);
    }
    result.stress_history.push_back(stress);

    std::string json = result.toJSON(true);

    // Should contain truncation message for large datasets
    TEST_ASSERT(json.find("omitted") != std::string::npos, "Should show omitted message for large datasets");

    std::cout << "PASSED\n";
    return true;
}

// ============================================================
// Main Test Runner
// ============================================================

int main() {
    std::cout << "========================================\n";
    std::cout << "AnalysisResult Unit Tests\n";
    std::cout << "========================================\n\n";

    int passed = 0;
    int failed = 0;

    std::cout << "Basic Tests:\n";
    if (test_metadata()) passed++; else failed++;
    if (test_part_time_series()) passed++; else failed++;

    std::cout << "\nJSON Tests:\n";
    if (test_json_generation()) passed++; else failed++;
    if (test_json_save()) passed++; else failed++;
    if (test_special_characters()) passed++; else failed++;
    if (test_large_dataset_json()) passed++; else failed++;

    std::cout << "\nCSV Tests:\n";
    if (test_csv_export()) passed++; else failed++;

    std::cout << "\n========================================\n";
    std::cout << "Results: " << passed << " passed, " << failed << " failed\n";
    std::cout << "========================================\n";

    return failed > 0 ? 1 : 0;
}
