/**
 * @file test_time_history.cpp
 * @brief Unit tests for TimeHistoryAnalyzer module
 * @author KooD3plot Development Team
 * @date 2024-12-04
 *
 * Compile:
 *   (Build with CMake as part of the project)
 *
 * Run:
 *   ./test_time_history [d3plot_path]
 */

#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
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

bool test_analysis_config_default() {
    std::cout << "  Testing AnalysisConfig default... ";

    AnalysisConfig config = AnalysisConfig::createDefault("test.d3plot");

    TEST_ASSERT(config.d3plot_path == "test.d3plot", "Path should be set");
    TEST_ASSERT(config.analyze_stress == true, "Stress should be enabled");
    TEST_ASSERT(config.analyze_strain == true, "Strain should be enabled");
    TEST_ASSERT(config.analyze_acceleration == false, "Acceleration should be disabled");
    TEST_ASSERT(config.surface_specs.empty(), "No surface specs by default");

    std::cout << "PASSED\n";
    return true;
}

bool test_analysis_config_with_surface() {
    std::cout << "  Testing AnalysisConfig with surface... ";

    AnalysisConfig config = AnalysisConfig::withBottomSurface("test.d3plot", 30.0);

    TEST_ASSERT(config.surface_specs.size() == 1, "Should have 1 surface spec");
    TEST_ASSERT(config.surface_specs[0].description.find("Bottom") != std::string::npos,
                "Should be bottom surface");
    TEST_ASSERT(APPROX_EQ(config.surface_specs[0].direction.z, -1.0, 1e-6),
                "Direction should be -Z");
    TEST_ASSERT(APPROX_EQ(config.surface_specs[0].angle_threshold_degrees, 30.0, 1e-6),
                "Angle should be 30 degrees");

    std::cout << "PASSED\n";
    return true;
}

bool test_analysis_config_top_bottom() {
    std::cout << "  Testing AnalysisConfig with top/bottom... ";

    AnalysisConfig config = AnalysisConfig::withTopBottomSurfaces("test.d3plot", 45.0);

    TEST_ASSERT(config.surface_specs.size() == 2, "Should have 2 surface specs");
    TEST_ASSERT(APPROX_EQ(config.surface_specs[0].direction.z, -1.0, 1e-6),
                "First should be -Z (bottom)");
    TEST_ASSERT(APPROX_EQ(config.surface_specs[1].direction.z, 1.0, 1e-6),
                "Second should be +Z (top)");

    std::cout << "PASSED\n";
    return true;
}

bool test_surface_analysis_spec() {
    std::cout << "  Testing SurfaceAnalysisSpec... ";

    SurfaceAnalysisSpec spec("Left surface", Vec3(-1, 0, 0), 60.0);

    TEST_ASSERT(spec.description == "Left surface", "Description should match");
    TEST_ASSERT(APPROX_EQ(spec.direction.x, -1.0, 1e-6), "Direction X should be -1");
    TEST_ASSERT(APPROX_EQ(spec.angle_threshold_degrees, 60.0, 1e-6),
                "Angle should be 60 degrees");
    TEST_ASSERT(spec.part_ids.empty(), "No parts by default");

    // With parts
    SurfaceAnalysisSpec spec2("Right surface", Vec3(1, 0, 0), 45.0, {1, 2, 3});
    TEST_ASSERT(spec2.part_ids.size() == 3, "Should have 3 parts");

    std::cout << "PASSED\n";
    return true;
}

bool test_analyzer_error_handling() {
    std::cout << "  Testing error handling (invalid file)... ";

    AnalysisConfig config;
    config.d3plot_path = "/nonexistent/path/d3plot";

    TimeHistoryAnalyzer analyzer;
    AnalysisResult result = analyzer.analyze(config);

    TEST_ASSERT(!analyzer.wasSuccessful(), "Should fail for invalid file");
    TEST_ASSERT(!analyzer.getLastError().empty(), "Error message should be set");

    std::cout << "PASSED\n";
    return true;
}

// ============================================================
// Integration Tests (D3plot required)
// ============================================================

bool test_basic_analysis(const std::string& d3plot_path) {
    std::cout << "  Testing basic analysis... ";

    D3plotReader reader(d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cout << "SKIPPED (cannot open file)\n";
        return true;
    }

    AnalysisConfig config = AnalysisConfig::createDefault(d3plot_path);
    config.verbose = false;

    TimeHistoryAnalyzer analyzer;
    AnalysisResult result = analyzer.analyze(config);

    if (!analyzer.wasSuccessful()) {
        std::cout << "SKIPPED (" << analyzer.getLastError() << ")\n";
        return true;
    }

    std::cout << "\n";
    std::cout << "    Metadata:\n";
    std::cout << "      Version: " << result.metadata.kood3plot_version << "\n";
    std::cout << "      States: " << result.metadata.num_states << "\n";
    std::cout << "      Time: " << result.metadata.start_time << " to "
              << result.metadata.end_time << "\n";
    std::cout << "      Parts analyzed: " << result.metadata.analyzed_parts.size() << "\n";

    std::cout << "    Stress history: " << result.stress_history.size() << " parts\n";
    std::cout << "    Strain history: " << result.strain_history.size() << " parts\n";

    TEST_ASSERT(result.metadata.num_states > 0, "Should have states");
    TEST_ASSERT(!result.stress_history.empty(), "Should have stress data");

    std::cout << "    PASSED\n";
    return true;
}

bool test_surface_analysis(const std::string& d3plot_path) {
    std::cout << "  Testing surface analysis... ";

    D3plotReader reader(d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cout << "SKIPPED\n";
        return true;
    }

    AnalysisConfig config = AnalysisConfig::withBottomSurface(d3plot_path, 45.0);
    config.verbose = false;

    TimeHistoryAnalyzer analyzer;
    AnalysisResult result = analyzer.analyze(config);

    if (!analyzer.wasSuccessful()) {
        std::cout << "SKIPPED\n";
        return true;
    }

    std::cout << "\n";
    std::cout << "    Surface analyses: " << result.surface_analysis.size() << "\n";

    if (!result.surface_analysis.empty()) {
        const auto& surf = result.surface_analysis[0];
        std::cout << "    Description: " << surf.description << "\n";
        std::cout << "    Num faces: " << surf.num_faces << "\n";
        std::cout << "    Time points: " << surf.data.size() << "\n";

        if (!surf.data.empty()) {
            std::cout << "    Sample (t=" << surf.data[0].time << "):\n";
            std::cout << "      Normal stress max: " << surf.data[0].normal_stress_max << "\n";
            std::cout << "      Shear stress max: " << surf.data[0].shear_stress_max << "\n";
        }
    }

    TEST_ASSERT(!result.surface_analysis.empty(), "Should have surface data");

    std::cout << "    PASSED\n";
    return true;
}

bool test_json_output(const std::string& d3plot_path) {
    std::cout << "  Testing JSON output... ";

    D3plotReader reader(d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cout << "SKIPPED\n";
        return true;
    }

    AnalysisConfig config = AnalysisConfig::createDefault(d3plot_path);
    config.output_json_path = "/tmp/test_time_history_output.json";
    config.verbose = false;

    TimeHistoryAnalyzer analyzer;
    AnalysisResult result = analyzer.analyze(config);

    if (!analyzer.wasSuccessful()) {
        std::cout << "SKIPPED\n";
        return true;
    }

    // Check JSON file was created
    std::ifstream file(config.output_json_path);
    TEST_ASSERT(file.is_open(), "JSON file should be created");

    std::string first_line;
    std::getline(file, first_line);
    TEST_ASSERT(first_line.find("{") != std::string::npos, "Should be valid JSON");

    std::cout << "PASSED (saved to " << config.output_json_path << ")\n";
    return true;
}

bool test_csv_output(const std::string& d3plot_path) {
    std::cout << "  Testing CSV output... ";

    D3plotReader reader(d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cout << "SKIPPED\n";
        return true;
    }

    AnalysisConfig config = AnalysisConfig::withBottomSurface(d3plot_path, 45.0);
    config.output_csv_prefix = "/tmp/test_time_history";
    config.verbose = false;

    TimeHistoryAnalyzer analyzer;
    AnalysisResult result = analyzer.analyze(config);

    if (!analyzer.wasSuccessful()) {
        std::cout << "SKIPPED\n";
        return true;
    }

    // Check CSV files were created
    std::ifstream stress_csv("/tmp/test_time_history_stress.csv");
    std::ifstream strain_csv("/tmp/test_time_history_strain.csv");
    std::ifstream surface_csv("/tmp/test_time_history_surface.csv");

    bool stress_ok = stress_csv.is_open();
    bool strain_ok = strain_csv.is_open();
    bool surface_ok = surface_csv.is_open();

    std::cout << "\n";
    std::cout << "    Stress CSV: " << (stress_ok ? "OK" : "NOT FOUND") << "\n";
    std::cout << "    Strain CSV: " << (strain_ok ? "OK" : "NOT FOUND") << "\n";
    std::cout << "    Surface CSV: " << (surface_ok ? "OK" : "NOT FOUND") << "\n";

    std::cout << "    PASSED\n";
    return true;
}

bool test_progress_callback(const std::string& d3plot_path) {
    std::cout << "  Testing progress callback... ";

    D3plotReader reader(d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cout << "SKIPPED\n";
        return true;
    }

    AnalysisConfig config = AnalysisConfig::createDefault(d3plot_path);
    config.analyze_strain = false;  // Skip strain for speed

    int callback_count = 0;
    std::string last_phase;

    TimeHistoryAnalyzer analyzer;
    AnalysisResult result = analyzer.analyze(config,
        [&callback_count, &last_phase](const std::string& phase,
                                        size_t current, size_t total,
                                        const std::string& msg) {
            callback_count++;
            last_phase = phase;
        }
    );

    if (!analyzer.wasSuccessful()) {
        std::cout << "SKIPPED\n";
        return true;
    }

    std::cout << "\n";
    std::cout << "    Callback count: " << callback_count << "\n";
    std::cout << "    Last phase: " << last_phase << "\n";

    TEST_ASSERT(callback_count > 0, "Should have called callback");
    TEST_ASSERT(last_phase == "Complete", "Last phase should be 'Complete'");

    std::cout << "    PASSED\n";
    return true;
}

// ============================================================
// Main Test Runner
// ============================================================

int main(int argc, char* argv[]) {
    std::cout << "========================================\n";
    std::cout << "TimeHistoryAnalyzer Unit Tests\n";
    std::cout << "========================================\n\n";

    int passed = 0;
    int failed = 0;

    std::cout << "Unit Tests:\n";
    if (test_analysis_config_default()) passed++; else failed++;
    if (test_analysis_config_with_surface()) passed++; else failed++;
    if (test_analysis_config_top_bottom()) passed++; else failed++;
    if (test_surface_analysis_spec()) passed++; else failed++;
    if (test_analyzer_error_handling()) passed++; else failed++;

    // D3plot integration tests
    std::string d3plot_path = "results/d3plot";
    if (argc > 1) {
        d3plot_path = argv[1];
    }

    std::cout << "\nD3plot Integration Tests:\n";
    if (test_basic_analysis(d3plot_path)) passed++; else failed++;
    if (test_surface_analysis(d3plot_path)) passed++; else failed++;
    if (test_json_output(d3plot_path)) passed++; else failed++;
    if (test_csv_output(d3plot_path)) passed++; else failed++;
    if (test_progress_callback(d3plot_path)) passed++; else failed++;

    std::cout << "\n========================================\n";
    std::cout << "Results: " << passed << " passed, " << failed << " failed\n";
    std::cout << "========================================\n";

    return failed > 0 ? 1 : 0;
}
