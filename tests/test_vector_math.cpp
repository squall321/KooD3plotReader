/**
 * @file test_vector_math.cpp
 * @brief Unit tests for VectorMath module
 * @author KooD3plot Development Team
 * @date 2024-12-04
 *
 * Compile:
 *   g++ -std=c++17 -I../include -o test_vector_math test_vector_math.cpp
 *
 * Run:
 *   ./test_vector_math
 */

#include "kood3plot/analysis/VectorMath.hpp"
#include <iostream>
#include <cmath>
#include <cassert>
#include <string>

using namespace kood3plot::analysis;

// Test helper macros
#define TEST_ASSERT(cond, msg) \
    if (!(cond)) { \
        std::cerr << "FAILED: " << msg << " at line " << __LINE__ << "\n"; \
        return false; \
    }

#define APPROX_EQ(a, b, eps) (std::abs((a) - (b)) < (eps))

// ============================================================
// Vec3 Tests
// ============================================================

bool test_vec3_basic_ops() {
    std::cout << "  Testing Vec3 basic operations... ";

    Vec3 a(1.0, 2.0, 3.0);
    Vec3 b(4.0, 5.0, 6.0);

    // Addition
    Vec3 c = a + b;
    TEST_ASSERT(c.x == 5.0 && c.y == 7.0 && c.z == 9.0, "Addition failed");

    // Subtraction
    Vec3 d = b - a;
    TEST_ASSERT(d.x == 3.0 && d.y == 3.0 && d.z == 3.0, "Subtraction failed");

    // Scalar multiplication
    Vec3 e = a * 2.0;
    TEST_ASSERT(e.x == 2.0 && e.y == 4.0 && e.z == 6.0, "Scalar mult failed");

    // Scalar division
    Vec3 f = b / 2.0;
    TEST_ASSERT(APPROX_EQ(f.x, 2.0, 1e-10) && APPROX_EQ(f.y, 2.5, 1e-10) && APPROX_EQ(f.z, 3.0, 1e-10),
                "Scalar div failed");

    // Negation
    Vec3 g = -a;
    TEST_ASSERT(g.x == -1.0 && g.y == -2.0 && g.z == -3.0, "Negation failed");

    std::cout << "PASSED\n";
    return true;
}

bool test_vec3_dot_cross() {
    std::cout << "  Testing Vec3 dot/cross products... ";

    Vec3 a(1.0, 0.0, 0.0);
    Vec3 b(0.0, 1.0, 0.0);
    Vec3 c(0.0, 0.0, 1.0);

    // Dot product: perpendicular vectors
    TEST_ASSERT(APPROX_EQ(a.dot(b), 0.0, 1e-10), "Dot product of perpendicular vectors should be 0");
    TEST_ASSERT(APPROX_EQ(a.dot(a), 1.0, 1e-10), "Dot product of unit vector with itself should be 1");

    // Cross product: right-hand rule
    Vec3 ab = a.cross(b);
    TEST_ASSERT(APPROX_EQ(ab.x, 0.0, 1e-10) && APPROX_EQ(ab.y, 0.0, 1e-10) && APPROX_EQ(ab.z, 1.0, 1e-10),
                "Cross product i x j should be k");

    Vec3 bc = b.cross(c);
    TEST_ASSERT(APPROX_EQ(bc.x, 1.0, 1e-10) && APPROX_EQ(bc.y, 0.0, 1e-10) && APPROX_EQ(bc.z, 0.0, 1e-10),
                "Cross product j x k should be i");

    // Cross product: anti-commutative
    Vec3 ba = b.cross(a);
    TEST_ASSERT(APPROX_EQ(ba.z, -1.0, 1e-10), "Cross product should be anti-commutative");

    std::cout << "PASSED\n";
    return true;
}

bool test_vec3_magnitude_normalize() {
    std::cout << "  Testing Vec3 magnitude/normalize... ";

    Vec3 v(3.0, 4.0, 0.0);
    TEST_ASSERT(APPROX_EQ(v.magnitude(), 5.0, 1e-10), "Magnitude of (3,4,0) should be 5");

    Vec3 n = v.normalized();
    TEST_ASSERT(APPROX_EQ(n.magnitude(), 1.0, 1e-10), "Normalized vector should have magnitude 1");
    TEST_ASSERT(APPROX_EQ(n.x, 0.6, 1e-10) && APPROX_EQ(n.y, 0.8, 1e-10), "Normalized values incorrect");

    // Test zero vector
    Vec3 zero;
    TEST_ASSERT(zero.isZero(), "Default constructor should create zero vector");

    std::cout << "PASSED\n";
    return true;
}

bool test_vec3_angle() {
    std::cout << "  Testing Vec3 angle calculations... ";

    Vec3 x(1.0, 0.0, 0.0);
    Vec3 y(0.0, 1.0, 0.0);

    // Perpendicular vectors: 90 degrees
    double angle_xy = x.angleToInDegrees(y);
    TEST_ASSERT(APPROX_EQ(angle_xy, 90.0, 1e-6), "Angle between x and y should be 90 degrees");

    // Parallel vectors: 0 degrees
    double angle_xx = x.angleToInDegrees(x);
    TEST_ASSERT(APPROX_EQ(angle_xx, 0.0, 1e-6), "Angle between x and x should be 0 degrees");

    // Anti-parallel vectors: 180 degrees
    Vec3 neg_x(-1.0, 0.0, 0.0);
    double angle_x_negx = x.angleToInDegrees(neg_x);
    TEST_ASSERT(APPROX_EQ(angle_x_negx, 180.0, 1e-6), "Angle between x and -x should be 180 degrees");

    // 45 degree angle
    Vec3 diag(1.0, 1.0, 0.0);
    double angle_45 = x.angleToInDegrees(diag);
    TEST_ASSERT(APPROX_EQ(angle_45, 45.0, 1e-6), "Angle should be 45 degrees");

    std::cout << "PASSED\n";
    return true;
}

// ============================================================
// StressTensor Tests
// ============================================================

bool test_stress_von_mises() {
    std::cout << "  Testing StressTensor Von Mises... ";

    // Uniaxial tension: σxx = 100, others = 0
    // Von Mises = σxx = 100
    StressTensor uniaxial(100.0, 0.0, 0.0, 0.0, 0.0, 0.0);
    TEST_ASSERT(APPROX_EQ(uniaxial.vonMises(), 100.0, 1e-6),
                "Uniaxial tension Von Mises should equal applied stress");

    // Pure shear: σxy = 50, others = 0
    // Von Mises = sqrt(3) * τ = sqrt(3) * 50 ≈ 86.6
    StressTensor shear(0.0, 0.0, 0.0, 50.0, 0.0, 0.0);
    double expected_vm = std::sqrt(3.0) * 50.0;
    TEST_ASSERT(APPROX_EQ(shear.vonMises(), expected_vm, 1e-6),
                "Pure shear Von Mises should be sqrt(3)*tau");

    // Hydrostatic: σxx = σyy = σzz = 100
    // Von Mises = 0 (no deviatoric stress)
    StressTensor hydro(100.0, 100.0, 100.0, 0.0, 0.0, 0.0);
    TEST_ASSERT(APPROX_EQ(hydro.vonMises(), 0.0, 1e-6),
                "Hydrostatic stress Von Mises should be 0");

    std::cout << "PASSED\n";
    return true;
}

bool test_stress_principal() {
    std::cout << "  Testing StressTensor principal stresses... ";

    // Uniaxial: σ1 = 100, σ2 = σ3 = 0
    StressTensor uniaxial(100.0, 0.0, 0.0, 0.0, 0.0, 0.0);
    auto principals = uniaxial.principalStresses();
    TEST_ASSERT(APPROX_EQ(principals[0], 100.0, 1e-6), "Max principal should be 100");
    TEST_ASSERT(APPROX_EQ(principals[1], 0.0, 1e-6), "Mid principal should be 0");
    TEST_ASSERT(APPROX_EQ(principals[2], 0.0, 1e-6), "Min principal should be 0");

    // Biaxial: σxx = 100, σyy = 50
    StressTensor biaxial(100.0, 50.0, 0.0, 0.0, 0.0, 0.0);
    principals = biaxial.principalStresses();
    TEST_ASSERT(APPROX_EQ(principals[0], 100.0, 1e-6), "Max principal should be 100");
    TEST_ASSERT(APPROX_EQ(principals[1], 50.0, 1e-6), "Mid principal should be 50");
    TEST_ASSERT(APPROX_EQ(principals[2], 0.0, 1e-6), "Min principal should be 0");

    // Pure shear: σxy = 50
    // Principal stresses: ±50, 0
    StressTensor pure_shear(0.0, 0.0, 0.0, 50.0, 0.0, 0.0);
    principals = pure_shear.principalStresses();
    TEST_ASSERT(APPROX_EQ(principals[0], 50.0, 1e-6), "Pure shear max principal should be +tau");
    TEST_ASSERT(APPROX_EQ(principals[1], 0.0, 1e-6), "Pure shear mid principal should be 0");
    TEST_ASSERT(APPROX_EQ(principals[2], -50.0, 1e-6), "Pure shear min principal should be -tau");

    std::cout << "PASSED\n";
    return true;
}

bool test_stress_normal_shear() {
    std::cout << "  Testing StressTensor normal/shear stress on plane... ";

    // Uniaxial tension in X direction: σxx = 100
    StressTensor uniaxial(100.0, 0.0, 0.0, 0.0, 0.0, 0.0);

    // Plane perpendicular to X (normal = (1,0,0))
    Vec3 normal_x(1.0, 0.0, 0.0);
    double sigma_n = uniaxial.normalStress(normal_x);
    double tau = uniaxial.shearStress(normal_x);

    TEST_ASSERT(APPROX_EQ(sigma_n, 100.0, 1e-6),
                "Normal stress on X-plane should be 100");
    TEST_ASSERT(APPROX_EQ(tau, 0.0, 1e-6),
                "Shear stress on X-plane should be 0");

    // Plane perpendicular to Y (normal = (0,1,0))
    Vec3 normal_y(0.0, 1.0, 0.0);
    sigma_n = uniaxial.normalStress(normal_y);
    tau = uniaxial.shearStress(normal_y);

    TEST_ASSERT(APPROX_EQ(sigma_n, 0.0, 1e-6),
                "Normal stress on Y-plane should be 0");
    TEST_ASSERT(APPROX_EQ(tau, 0.0, 1e-6),
                "Shear stress on Y-plane should be 0");

    // 45-degree plane: max shear stress
    // Normal = (1/sqrt(2), 1/sqrt(2), 0)
    double s2 = 1.0 / std::sqrt(2.0);
    Vec3 normal_45(s2, s2, 0.0);
    sigma_n = uniaxial.normalStress(normal_45);
    tau = uniaxial.shearStress(normal_45);

    TEST_ASSERT(APPROX_EQ(sigma_n, 50.0, 1e-6),
                "Normal stress on 45-deg plane should be 50");
    TEST_ASSERT(APPROX_EQ(tau, 50.0, 1e-6),
                "Shear stress on 45-deg plane should be 50 (max shear)");

    std::cout << "PASSED\n";
    return true;
}

bool test_stress_pure_shear_analysis() {
    std::cout << "  Testing StressTensor pure shear analysis... ";

    // Pure shear in XY plane: σxy = 100
    StressTensor shear(0.0, 0.0, 0.0, 100.0, 0.0, 0.0);

    // Plane perpendicular to X
    Vec3 normal_x(1.0, 0.0, 0.0);
    double sigma_n = shear.normalStress(normal_x);
    double tau = shear.shearStress(normal_x);

    TEST_ASSERT(APPROX_EQ(sigma_n, 0.0, 1e-6),
                "Normal stress on X-plane in pure shear should be 0");
    TEST_ASSERT(APPROX_EQ(tau, 100.0, 1e-6),
                "Shear stress on X-plane should be 100");

    // Check shear direction
    Vec3 shear_dir = shear.shearDirection(normal_x);
    TEST_ASSERT(APPROX_EQ(shear_dir.y, 1.0, 1e-6),
                "Shear direction on X-plane should be Y");

    std::cout << "PASSED\n";
    return true;
}

bool test_stress_transform() {
    std::cout << "  Testing StressTensor coordinate transformation... ";

    // Uniaxial tension in X
    StressTensor original(100.0, 0.0, 0.0, 0.0, 0.0, 0.0);

    // Rotate 90 degrees about Z: X->Y, Y->-X
    Vec3 new_x(0.0, 1.0, 0.0);   // Old Y becomes new X
    Vec3 new_y(-1.0, 0.0, 0.0);  // Old -X becomes new Y
    Vec3 new_z(0.0, 0.0, 1.0);   // Z unchanged

    StressTensor transformed = original.transform(new_x, new_y, new_z);

    // After rotation, stress should be in Y' direction (which was X)
    TEST_ASSERT(APPROX_EQ(transformed.yy, 100.0, 1e-6),
                "Transformed stress should be in new Y direction");
    TEST_ASSERT(APPROX_EQ(transformed.xx, 0.0, 1e-6),
                "Transformed XX should be 0");

    // Von Mises should be invariant
    TEST_ASSERT(APPROX_EQ(original.vonMises(), transformed.vonMises(), 1e-6),
                "Von Mises should be invariant under rotation");

    std::cout << "PASSED\n";
    return true;
}

bool test_stress_invariants() {
    std::cout << "  Testing StressTensor invariants... ";

    StressTensor stress(100.0, 50.0, 30.0, 20.0, 10.0, 15.0);

    double i1 = stress.I1();
    double i2 = stress.I2();
    double i3 = stress.I3();

    // I1 = trace
    TEST_ASSERT(APPROX_EQ(i1, 180.0, 1e-6), "I1 should be sum of diagonal");

    // Verify principal stresses satisfy characteristic equation
    auto principals = stress.principalStresses();
    for (double p : principals) {
        double val = p * p * p - i1 * p * p + i2 * p - i3;
        TEST_ASSERT(APPROX_EQ(val, 0.0, 1e-3),
                    "Principal stress should satisfy characteristic equation");
    }

    // Test rotation invariance
    Vec3 new_x(0.6, 0.8, 0.0);
    Vec3 new_y(-0.8, 0.6, 0.0);
    Vec3 new_z(0.0, 0.0, 1.0);

    StressTensor rotated = stress.transform(new_x, new_y, new_z);

    TEST_ASSERT(APPROX_EQ(stress.I1(), rotated.I1(), 1e-6), "I1 should be rotation invariant");
    TEST_ASSERT(APPROX_EQ(stress.I2(), rotated.I2(), 1e-6), "I2 should be rotation invariant");
    TEST_ASSERT(APPROX_EQ(stress.I3(), rotated.I3(), 1e-6), "I3 should be rotation invariant");

    std::cout << "PASSED\n";
    return true;
}

// ============================================================
// Main Test Runner
// ============================================================

int main() {
    std::cout << "========================================\n";
    std::cout << "VectorMath Unit Tests\n";
    std::cout << "========================================\n\n";

    int passed = 0;
    int failed = 0;

    std::cout << "Vec3 Tests:\n";
    if (test_vec3_basic_ops()) passed++; else failed++;
    if (test_vec3_dot_cross()) passed++; else failed++;
    if (test_vec3_magnitude_normalize()) passed++; else failed++;
    if (test_vec3_angle()) passed++; else failed++;

    std::cout << "\nStressTensor Tests:\n";
    if (test_stress_von_mises()) passed++; else failed++;
    if (test_stress_principal()) passed++; else failed++;
    if (test_stress_normal_shear()) passed++; else failed++;
    if (test_stress_pure_shear_analysis()) passed++; else failed++;
    if (test_stress_transform()) passed++; else failed++;
    if (test_stress_invariants()) passed++; else failed++;

    std::cout << "\n========================================\n";
    std::cout << "Results: " << passed << " passed, " << failed << " failed\n";
    std::cout << "========================================\n";

    return failed > 0 ? 1 : 0;
}
