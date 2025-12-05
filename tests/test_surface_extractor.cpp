/**
 * @file test_surface_extractor.cpp
 * @brief Unit tests for SurfaceExtractor module
 * @author KooD3plot Development Team
 * @date 2024-12-04
 *
 * Compile:
 *   (Build with CMake as part of the project)
 *
 * Run:
 *   ./test_surface_extractor [d3plot_path]
 */

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
// Geometry Tests (No d3plot required)
// ============================================================

bool test_quad_normal() {
    std::cout << "  Testing quad normal calculation... ";

    // Simple unit square in XY plane
    Vec3 p0(0, 0, 0);
    Vec3 p1(1, 0, 0);
    Vec3 p2(1, 1, 0);
    Vec3 p3(0, 1, 0);

    Vec3 normal = SurfaceExtractor::calculateQuadNormal(p0, p1, p2, p3);

    TEST_ASSERT(APPROX_EQ(normal.z, 1.0, 1e-6), "Normal should point in +Z");
    TEST_ASSERT(APPROX_EQ(normal.x, 0.0, 1e-6), "Normal X should be 0");
    TEST_ASSERT(APPROX_EQ(normal.y, 0.0, 1e-6), "Normal Y should be 0");

    // Reversed winding (normal should point -Z)
    normal = SurfaceExtractor::calculateQuadNormal(p0, p3, p2, p1);
    TEST_ASSERT(APPROX_EQ(normal.z, -1.0, 1e-6), "Reversed normal should point in -Z");

    std::cout << "PASSED\n";
    return true;
}

bool test_quad_centroid() {
    std::cout << "  Testing quad centroid calculation... ";

    Vec3 p0(0, 0, 0);
    Vec3 p1(2, 0, 0);
    Vec3 p2(2, 2, 0);
    Vec3 p3(0, 2, 0);

    Vec3 centroid = SurfaceExtractor::calculateQuadCentroid(p0, p1, p2, p3);

    TEST_ASSERT(APPROX_EQ(centroid.x, 1.0, 1e-6), "Centroid X should be 1");
    TEST_ASSERT(APPROX_EQ(centroid.y, 1.0, 1e-6), "Centroid Y should be 1");
    TEST_ASSERT(APPROX_EQ(centroid.z, 0.0, 1e-6), "Centroid Z should be 0");

    std::cout << "PASSED\n";
    return true;
}

bool test_quad_area() {
    std::cout << "  Testing quad area calculation... ";

    // 2x2 square -> area = 4
    Vec3 p0(0, 0, 0);
    Vec3 p1(2, 0, 0);
    Vec3 p2(2, 2, 0);
    Vec3 p3(0, 2, 0);

    double area = SurfaceExtractor::calculateQuadArea(p0, p1, p2, p3);
    TEST_ASSERT(APPROX_EQ(area, 4.0, 1e-6), "Area of 2x2 square should be 4");

    // Unit square -> area = 1
    Vec3 q0(0, 0, 0);
    Vec3 q1(1, 0, 0);
    Vec3 q2(1, 1, 0);
    Vec3 q3(0, 1, 0);

    area = SurfaceExtractor::calculateQuadArea(q0, q1, q2, q3);
    TEST_ASSERT(APPROX_EQ(area, 1.0, 1e-6), "Area of unit square should be 1");

    std::cout << "PASSED\n";
    return true;
}

bool test_direction_filter() {
    std::cout << "  Testing direction filtering... ";

    // Create some test faces
    std::vector<Face> faces;

    // Face 1: Normal pointing up (+Z)
    Face f1;
    f1.element_id = 0;
    f1.normal = Vec3(0, 0, 1);
    faces.push_back(f1);

    // Face 2: Normal pointing down (-Z)
    Face f2;
    f2.element_id = 1;
    f2.normal = Vec3(0, 0, -1);
    faces.push_back(f2);

    // Face 3: Normal pointing at 45 degrees
    Face f3;
    f3.element_id = 2;
    f3.normal = Vec3(0, 0.7071, 0.7071);  // 45 deg from +Z
    faces.push_back(f3);

    // Face 4: Normal pointing sideways (+X)
    Face f4;
    f4.element_id = 3;
    f4.normal = Vec3(1, 0, 0);
    faces.push_back(f4);

    // Filter for upward-facing (within 30 degrees of +Z)
    Vec3 up(0, 0, 1);
    auto filtered = SurfaceExtractor::filterByDirection(faces, up, 30.0);
    TEST_ASSERT(filtered.size() == 1, "Should have 1 face within 30 deg of +Z");
    TEST_ASSERT(filtered[0].element_id == 0, "Should be face 0");

    // Filter for upward-facing (within 60 degrees of +Z)
    filtered = SurfaceExtractor::filterByDirection(faces, up, 60.0);
    TEST_ASSERT(filtered.size() == 2, "Should have 2 faces within 60 deg of +Z");

    // Filter for downward-facing (within 30 degrees of -Z)
    Vec3 down(0, 0, -1);
    filtered = SurfaceExtractor::filterByDirection(faces, down, 30.0);
    TEST_ASSERT(filtered.size() == 1, "Should have 1 face within 30 deg of -Z");
    TEST_ASSERT(filtered[0].element_id == 1, "Should be face 1");

    std::cout << "PASSED\n";
    return true;
}

bool test_part_filter() {
    std::cout << "  Testing part filtering... ";

    std::vector<Face> faces;

    Face f1; f1.element_id = 0; f1.part_id = 1; faces.push_back(f1);
    Face f2; f2.element_id = 1; f2.part_id = 2; faces.push_back(f2);
    Face f3; f3.element_id = 2; f3.part_id = 1; faces.push_back(f3);
    Face f4; f4.element_id = 3; f4.part_id = 3; faces.push_back(f4);

    // Filter for part 1
    auto filtered = SurfaceExtractor::filterByPart(faces, {1});
    TEST_ASSERT(filtered.size() == 2, "Should have 2 faces from part 1");

    // Filter for parts 1 and 2
    filtered = SurfaceExtractor::filterByPart(faces, {1, 2});
    TEST_ASSERT(filtered.size() == 3, "Should have 3 faces from parts 1 and 2");

    // Filter for non-existent part
    filtered = SurfaceExtractor::filterByPart(faces, {99});
    TEST_ASSERT(filtered.size() == 0, "Should have 0 faces from part 99");

    std::cout << "PASSED\n";
    return true;
}

// ============================================================
// D3plot Integration Tests
// ============================================================

bool test_with_d3plot(const std::string& d3plot_path) {
    std::cout << "  Testing with d3plot file: " << d3plot_path << "... ";

    D3plotReader reader(d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cout << "SKIPPED (cannot open file)\n";
        return true;  // Not a failure if file doesn't exist
    }

    SurfaceExtractor extractor(reader);

    // Extract exterior surfaces
    auto result = extractor.extractExteriorSurfaces();

    std::cout << "\n";
    std::cout << "    Solid elements: " << result.total_solid_elements << "\n";
    std::cout << "    Shell elements: " << result.total_shell_elements << "\n";
    std::cout << "    Exterior faces: " << result.total_exterior_faces << "\n";
    std::cout << "    Parts included: ";
    for (auto p : result.parts_included) std::cout << p << " ";
    std::cout << "\n";

    TEST_ASSERT(result.faces.size() > 0, "Should extract some exterior faces");

    // Test direction filtering
    Vec3 down(0, 0, -1);
    auto bottom_faces = SurfaceExtractor::filterByDirection(result.faces, down, 45.0);
    std::cout << "    Bottom-facing faces (45 deg): " << bottom_faces.size() << "\n";

    Vec3 up(0, 0, 1);
    auto top_faces = SurfaceExtractor::filterByDirection(result.faces, up, 45.0);
    std::cout << "    Top-facing faces (45 deg): " << top_faces.size() << "\n";

    // Verify normals are unit vectors
    for (const auto& face : result.faces) {
        double mag = face.normal.magnitude();
        if (!face.normal.isZero() && std::abs(mag - 1.0) > 1e-3) {
            std::cerr << "FAILED: Normal not unit vector (mag=" << mag << ")\n";
            return false;
        }
    }

    std::cout << "    PASSED\n";
    return true;
}

bool test_solid_only_extraction(const std::string& d3plot_path) {
    std::cout << "  Testing solid-only extraction... ";

    D3plotReader reader(d3plot_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::cout << "SKIPPED\n";
        return true;
    }

    SurfaceExtractor extractor(reader);
    auto result = extractor.extractSolidExteriorSurfaces();

    // All faces should be from solid elements
    for (const auto& face : result.faces) {
        if (face.element_type != SurfaceElementType::SOLID) {
            std::cerr << "FAILED: Found non-solid face in solid-only extraction\n";
            return false;
        }
    }

    std::cout << "PASSED (" << result.faces.size() << " solid faces)\n";
    return true;
}

// ============================================================
// Main Test Runner
// ============================================================

int main(int argc, char* argv[]) {
    std::cout << "========================================\n";
    std::cout << "SurfaceExtractor Unit Tests\n";
    std::cout << "========================================\n\n";

    int passed = 0;
    int failed = 0;

    std::cout << "Geometry Tests:\n";
    if (test_quad_normal()) passed++; else failed++;
    if (test_quad_centroid()) passed++; else failed++;
    if (test_quad_area()) passed++; else failed++;

    std::cout << "\nFiltering Tests:\n";
    if (test_direction_filter()) passed++; else failed++;
    if (test_part_filter()) passed++; else failed++;

    // D3plot integration tests
    std::string d3plot_path = "results/d3plot";
    if (argc > 1) {
        d3plot_path = argv[1];
    }

    std::cout << "\nD3plot Integration Tests:\n";
    if (test_with_d3plot(d3plot_path)) passed++; else failed++;
    if (test_solid_only_extraction(d3plot_path)) passed++; else failed++;

    std::cout << "\n========================================\n";
    std::cout << "Results: " << passed << " passed, " << failed << " failed\n";
    std::cout << "========================================\n";

    return failed > 0 ? 1 : 0;
}
