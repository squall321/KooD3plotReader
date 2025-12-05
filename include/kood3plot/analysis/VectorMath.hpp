/**
 * @file VectorMath.hpp
 * @brief Vector and tensor mathematics utilities for structural analysis
 * @author KooD3plot Development Team
 * @date 2024-12-04
 * @version 1.0.0
 *
 * Provides Vec3 (3D vector) and StressTensor (6-component Voigt notation)
 * classes for stress/strain analysis calculations.
 */

#pragma once

#include <cmath>
#include <array>
#include <stdexcept>

namespace kood3plot {
namespace analysis {

/**
 * @brief 3D Vector class for geometric and mechanical calculations
 *
 * Usage:
 * @code
 * Vec3 a(1.0, 2.0, 3.0);
 * Vec3 b(4.0, 5.0, 6.0);
 * Vec3 c = a.cross(b);
 * double angle = a.angleToInDegrees(b);
 * @endcode
 */
class Vec3 {
public:
    double x, y, z;

    // ============================================================
    // Constructors
    // ============================================================

    /**
     * @brief Default constructor (zero vector)
     */
    Vec3() : x(0.0), y(0.0), z(0.0) {}

    /**
     * @brief Constructor with components
     */
    Vec3(double x_, double y_, double z_) : x(x_), y(y_), z(z_) {}

    /**
     * @brief Constructor from array
     */
    explicit Vec3(const double* arr) : x(arr[0]), y(arr[1]), z(arr[2]) {}

    /**
     * @brief Constructor from std::array
     */
    explicit Vec3(const std::array<double, 3>& arr) : x(arr[0]), y(arr[1]), z(arr[2]) {}

    // ============================================================
    // Basic Arithmetic Operators
    // ============================================================

    Vec3 operator+(const Vec3& o) const {
        return Vec3(x + o.x, y + o.y, z + o.z);
    }

    Vec3 operator-(const Vec3& o) const {
        return Vec3(x - o.x, y - o.y, z - o.z);
    }

    Vec3 operator*(double s) const {
        return Vec3(x * s, y * s, z * s);
    }

    Vec3 operator/(double s) const {
        if (std::abs(s) < 1e-30) {
            throw std::runtime_error("Vec3: Division by zero");
        }
        return Vec3(x / s, y / s, z / s);
    }

    Vec3 operator-() const {
        return Vec3(-x, -y, -z);
    }

    Vec3& operator+=(const Vec3& o) {
        x += o.x; y += o.y; z += o.z;
        return *this;
    }

    Vec3& operator-=(const Vec3& o) {
        x -= o.x; y -= o.y; z -= o.z;
        return *this;
    }

    Vec3& operator*=(double s) {
        x *= s; y *= s; z *= s;
        return *this;
    }

    Vec3& operator/=(double s) {
        if (std::abs(s) < 1e-30) {
            throw std::runtime_error("Vec3: Division by zero");
        }
        x /= s; y /= s; z /= s;
        return *this;
    }

    // ============================================================
    // Comparison Operators
    // ============================================================

    bool operator==(const Vec3& o) const {
        const double eps = 1e-12;
        return std::abs(x - o.x) < eps &&
               std::abs(y - o.y) < eps &&
               std::abs(z - o.z) < eps;
    }

    bool operator!=(const Vec3& o) const {
        return !(*this == o);
    }

    // ============================================================
    // Array Access
    // ============================================================

    double& operator[](int i) {
        switch (i) {
            case 0: return x;
            case 1: return y;
            case 2: return z;
            default: throw std::out_of_range("Vec3 index out of range");
        }
    }

    const double& operator[](int i) const {
        switch (i) {
            case 0: return x;
            case 1: return y;
            case 2: return z;
            default: throw std::out_of_range("Vec3 index out of range");
        }
    }

    // ============================================================
    // Vector Operations
    // ============================================================

    /**
     * @brief Dot product
     */
    double dot(const Vec3& o) const {
        return x * o.x + y * o.y + z * o.z;
    }

    /**
     * @brief Cross product
     */
    Vec3 cross(const Vec3& o) const {
        return Vec3(
            y * o.z - z * o.y,
            z * o.x - x * o.z,
            x * o.y - y * o.x
        );
    }

    /**
     * @brief Vector magnitude (length)
     */
    double magnitude() const {
        return std::sqrt(x * x + y * y + z * z);
    }

    /**
     * @brief Squared magnitude (avoids sqrt)
     */
    double magnitudeSquared() const {
        return x * x + y * y + z * z;
    }

    /**
     * @brief Normalized (unit) vector
     * @return Unit vector in same direction
     * @throws std::runtime_error if vector is zero
     */
    Vec3 normalized() const {
        double mag = magnitude();
        if (mag < 1e-30) {
            throw std::runtime_error("Vec3: Cannot normalize zero vector");
        }
        return Vec3(x / mag, y / mag, z / mag);
    }

    /**
     * @brief Safe normalization (returns zero vector if input is zero)
     */
    Vec3 normalizedSafe() const {
        double mag = magnitude();
        if (mag < 1e-30) {
            return Vec3(0.0, 0.0, 0.0);
        }
        return Vec3(x / mag, y / mag, z / mag);
    }

    /**
     * @brief Check if vector is approximately zero
     */
    bool isZero(double eps = 1e-12) const {
        return magnitudeSquared() < eps * eps;
    }

    // ============================================================
    // Angle Calculations
    // ============================================================

    /**
     * @brief Angle to another vector (radians)
     * @param o Other vector
     * @return Angle in radians [0, pi]
     */
    double angleTo(const Vec3& o) const {
        double dot_val = this->dot(o);
        double mag_product = this->magnitude() * o.magnitude();

        if (mag_product < 1e-30) {
            return 0.0;  // Undefined, return 0
        }

        // Clamp to [-1, 1] to handle numerical errors
        double cos_angle = dot_val / mag_product;
        cos_angle = std::max(-1.0, std::min(1.0, cos_angle));

        return std::acos(cos_angle);
    }

    /**
     * @brief Angle to another vector (degrees)
     * @param o Other vector
     * @return Angle in degrees [0, 180]
     */
    double angleToInDegrees(const Vec3& o) const {
        return angleTo(o) * 180.0 / M_PI;
    }

    // ============================================================
    // Utility Functions
    // ============================================================

    /**
     * @brief Component-wise minimum
     */
    static Vec3 min(const Vec3& a, const Vec3& b) {
        return Vec3(
            std::min(a.x, b.x),
            std::min(a.y, b.y),
            std::min(a.z, b.z)
        );
    }

    /**
     * @brief Component-wise maximum
     */
    static Vec3 max(const Vec3& a, const Vec3& b) {
        return Vec3(
            std::max(a.x, b.x),
            std::max(a.y, b.y),
            std::max(a.z, b.z)
        );
    }

    /**
     * @brief Linear interpolation
     */
    static Vec3 lerp(const Vec3& a, const Vec3& b, double t) {
        return a * (1.0 - t) + b * t;
    }

    /**
     * @brief Convert to std::array
     */
    std::array<double, 3> toArray() const {
        return {x, y, z};
    }

    // ============================================================
    // Static Factory Methods
    // ============================================================

    static Vec3 zero() { return Vec3(0.0, 0.0, 0.0); }
    static Vec3 unitX() { return Vec3(1.0, 0.0, 0.0); }
    static Vec3 unitY() { return Vec3(0.0, 1.0, 0.0); }
    static Vec3 unitZ() { return Vec3(0.0, 0.0, 1.0); }
};

// Free function for scalar * vector
inline Vec3 operator*(double s, const Vec3& v) {
    return v * s;
}


/**
 * @brief 6-component stress tensor in Voigt notation
 *
 * Represents the symmetric 3x3 stress tensor:
 * | σxx σxy σxz |
 * | σxy σyy σyz |
 * | σxz σyz σzz |
 *
 * Stored as [σxx, σyy, σzz, σxy, σyz, σzx] (LS-DYNA convention)
 *
 * Usage:
 * @code
 * StressTensor stress(100.0, 50.0, 30.0, 10.0, 5.0, 8.0);
 * double vm = stress.vonMises();
 * Vec3 normal(0, 0, 1);
 * double sigma_n = stress.normalStress(normal);
 * double tau = stress.shearStress(normal);
 * @endcode
 */
class StressTensor {
public:
    double xx, yy, zz;  // Normal stresses
    double xy, yz, zx;  // Shear stresses

    // ============================================================
    // Constructors
    // ============================================================

    /**
     * @brief Default constructor (zero tensor)
     */
    StressTensor() : xx(0), yy(0), zz(0), xy(0), yz(0), zx(0) {}

    /**
     * @brief Constructor with all 6 components
     * @param sxx Normal stress XX
     * @param syy Normal stress YY
     * @param szz Normal stress ZZ
     * @param sxy Shear stress XY
     * @param syz Shear stress YZ
     * @param szx Shear stress ZX
     */
    StressTensor(double sxx, double syy, double szz,
                 double sxy, double syz, double szx)
        : xx(sxx), yy(syy), zz(szz), xy(sxy), yz(syz), zx(szx) {}

    /**
     * @brief Constructor from array (LS-DYNA order)
     * @param arr Array [σxx, σyy, σzz, σxy, σyz, σzx]
     */
    explicit StressTensor(const double* arr)
        : xx(arr[0]), yy(arr[1]), zz(arr[2]),
          xy(arr[3]), yz(arr[4]), zx(arr[5]) {}

    // ============================================================
    // Derived Quantities
    // ============================================================

    /**
     * @brief Von Mises equivalent stress
     *
     * σ_vm = sqrt(0.5 * [(σxx-σyy)² + (σyy-σzz)² + (σzz-σxx)²
     *                    + 6*(σxy² + σyz² + σzx²)])
     */
    double vonMises() const {
        double d1 = xx - yy;
        double d2 = yy - zz;
        double d3 = zz - xx;
        double shear_sum = xy * xy + yz * yz + zx * zx;

        return std::sqrt(0.5 * (d1 * d1 + d2 * d2 + d3 * d3 + 6.0 * shear_sum));
    }

    /**
     * @brief Hydrostatic pressure (negative mean stress)
     *
     * p = -(σxx + σyy + σzz) / 3
     */
    double hydrostaticPressure() const {
        return -(xx + yy + zz) / 3.0;
    }

    /**
     * @brief Mean stress (hydrostatic stress)
     *
     * σ_m = (σxx + σyy + σzz) / 3
     */
    double meanStress() const {
        return (xx + yy + zz) / 3.0;
    }

    /**
     * @brief First stress invariant I1 = σxx + σyy + σzz
     */
    double I1() const {
        return xx + yy + zz;
    }

    /**
     * @brief Second stress invariant
     * I2 = σxx*σyy + σyy*σzz + σzz*σxx - σxy² - σyz² - σzx²
     */
    double I2() const {
        return xx * yy + yy * zz + zz * xx - xy * xy - yz * yz - zx * zx;
    }

    /**
     * @brief Third stress invariant (determinant)
     * I3 = det(σ)
     */
    double I3() const {
        return xx * (yy * zz - yz * yz)
             - xy * (xy * zz - yz * zx)
             + zx * (xy * yz - yy * zx);
    }

    /**
     * @brief Calculate principal stresses
     * @return Array of principal stresses [σ1, σ2, σ3] in descending order
     *
     * Uses a numerically stable algorithm based on the deviatoric stress tensor
     * and the three stress invariants.
     */
    std::array<double, 3> principalStresses() const {
        std::array<double, 3> principals;

        // For special case: zero or near-zero tensor
        if (isZero(1e-20)) {
            return {0.0, 0.0, 0.0};
        }

        // Calculate invariants
        double i1 = I1();
        double i2 = I2();
        double i3 = I3();

        // Mean stress
        double mean = i1 / 3.0;

        // Deviatoric stress components
        double s_xx = xx - mean;
        double s_yy = yy - mean;
        double s_zz = zz - mean;

        // J2 = 0.5 * tr(s^2) = 0.5 * (s_ij * s_ij)
        double J2 = 0.5 * (s_xx * s_xx + s_yy * s_yy + s_zz * s_zz +
                          2.0 * (xy * xy + yz * yz + zx * zx));

        // J3 = det(s) = (1/3) * tr(s^3)
        double J3 = s_xx * (s_yy * s_zz - yz * yz)
                  - xy * (xy * s_zz - yz * zx)
                  + zx * (xy * yz - s_yy * zx);

        // Special case: J2 is zero (hydrostatic state)
        if (J2 < 1e-20) {
            principals[0] = principals[1] = principals[2] = mean;
            return principals;
        }

        // Calculate Lode angle
        double r = std::sqrt(J2 / 3.0);
        double cos3theta = J3 / (2.0 * r * r * r);

        // Clamp to [-1, 1] for numerical stability
        cos3theta = std::max(-1.0, std::min(1.0, cos3theta));

        double theta = std::acos(cos3theta) / 3.0;

        // Principal stresses from Lode angle
        double two_r = 2.0 * r;
        principals[0] = mean + two_r * std::cos(theta);
        principals[1] = mean + two_r * std::cos(theta - 2.0 * M_PI / 3.0);
        principals[2] = mean + two_r * std::cos(theta + 2.0 * M_PI / 3.0);

        // Sort in descending order
        if (principals[0] < principals[1]) std::swap(principals[0], principals[1]);
        if (principals[1] < principals[2]) std::swap(principals[1], principals[2]);
        if (principals[0] < principals[1]) std::swap(principals[0], principals[1]);

        return principals;
    }

    /**
     * @brief Maximum principal stress (σ1)
     */
    double maxPrincipal() const {
        return principalStresses()[0];
    }

    /**
     * @brief Minimum principal stress (σ3)
     */
    double minPrincipal() const {
        return principalStresses()[2];
    }

    /**
     * @brief Middle principal stress (σ2)
     */
    double midPrincipal() const {
        return principalStresses()[1];
    }

    /**
     * @brief Maximum shear stress
     * τ_max = (σ1 - σ3) / 2
     */
    double maxShear() const {
        auto principals = principalStresses();
        return (principals[0] - principals[2]) / 2.0;
    }

    // ============================================================
    // Stress on Arbitrary Plane
    // ============================================================

    /**
     * @brief Traction vector on a plane with given normal
     *
     * t = σ · n
     *
     * @param normal Unit normal vector of the plane (must be normalized)
     * @return Traction vector
     */
    Vec3 tractionVector(const Vec3& normal) const {
        return Vec3(
            xx * normal.x + xy * normal.y + zx * normal.z,
            xy * normal.x + yy * normal.y + yz * normal.z,
            zx * normal.x + yz * normal.y + zz * normal.z
        );
    }

    /**
     * @brief Normal stress on a plane with given normal
     *
     * σ_n = n · σ · n = n · t
     *
     * @param normal Unit normal vector of the plane (must be normalized)
     * @return Normal stress (positive = tension, negative = compression)
     */
    double normalStress(const Vec3& normal) const {
        Vec3 traction = tractionVector(normal);
        return traction.dot(normal);
    }

    /**
     * @brief Shear stress magnitude on a plane with given normal
     *
     * τ = sqrt(|t|² - σ_n²)
     *
     * @param normal Unit normal vector of the plane (must be normalized)
     * @return Shear stress magnitude (always positive)
     */
    double shearStress(const Vec3& normal) const {
        Vec3 traction = tractionVector(normal);
        double sigma_n = traction.dot(normal);
        double traction_mag_sq = traction.magnitudeSquared();

        // Handle numerical errors
        double diff = traction_mag_sq - sigma_n * sigma_n;
        if (diff < 0.0) diff = 0.0;

        return std::sqrt(diff);
    }

    /**
     * @brief Shear stress vector on a plane with given normal
     *
     * τ_vec = t - σ_n * n
     *
     * @param normal Unit normal vector of the plane (must be normalized)
     * @return Shear stress vector (tangent to the plane)
     */
    Vec3 shearStressVector(const Vec3& normal) const {
        Vec3 traction = tractionVector(normal);
        double sigma_n = traction.dot(normal);
        return traction - normal * sigma_n;
    }

    /**
     * @brief Shear stress direction on a plane
     * @param normal Unit normal vector of the plane
     * @return Unit vector in shear stress direction (tangent to plane)
     */
    Vec3 shearDirection(const Vec3& normal) const {
        return shearStressVector(normal).normalizedSafe();
    }

    // ============================================================
    // Tensor Transformation
    // ============================================================

    /**
     * @brief Transform stress tensor to new coordinate system
     *
     * σ' = Q · σ · Q^T
     *
     * @param new_x New X-axis direction (unit vector)
     * @param new_y New Y-axis direction (unit vector)
     * @param new_z New Z-axis direction (unit vector)
     * @return Transformed stress tensor
     */
    StressTensor transform(const Vec3& new_x, const Vec3& new_y, const Vec3& new_z) const {
        // Build rotation matrix Q (each row is a new basis vector)
        // Q[i][j] = new_basis[i] . old_basis[j]
        double Q[3][3] = {
            {new_x.x, new_x.y, new_x.z},
            {new_y.x, new_y.y, new_y.z},
            {new_z.x, new_z.y, new_z.z}
        };

        // Build symmetric stress matrix S
        double S[3][3] = {
            {xx, xy, zx},
            {xy, yy, yz},
            {zx, yz, zz}
        };

        // Compute S' = Q * S * Q^T
        double temp[3][3] = {{0}};
        double S_prime[3][3] = {{0}};

        // temp = Q * S
        for (int i = 0; i < 3; i++) {
            for (int j = 0; j < 3; j++) {
                for (int k = 0; k < 3; k++) {
                    temp[i][j] += Q[i][k] * S[k][j];
                }
            }
        }

        // S' = temp * Q^T = temp * Q (since Q^T[i][j] = Q[j][i])
        for (int i = 0; i < 3; i++) {
            for (int j = 0; j < 3; j++) {
                for (int k = 0; k < 3; k++) {
                    S_prime[i][j] += temp[i][k] * Q[j][k];
                }
            }
        }

        return StressTensor(
            S_prime[0][0], S_prime[1][1], S_prime[2][2],
            S_prime[0][1], S_prime[1][2], S_prime[0][2]
        );
    }

    // ============================================================
    // Arithmetic Operations
    // ============================================================

    StressTensor operator+(const StressTensor& o) const {
        return StressTensor(
            xx + o.xx, yy + o.yy, zz + o.zz,
            xy + o.xy, yz + o.yz, zx + o.zx
        );
    }

    StressTensor operator-(const StressTensor& o) const {
        return StressTensor(
            xx - o.xx, yy - o.yy, zz - o.zz,
            xy - o.xy, yz - o.yz, zx - o.zx
        );
    }

    StressTensor operator*(double s) const {
        return StressTensor(
            xx * s, yy * s, zz * s,
            xy * s, yz * s, zx * s
        );
    }

    StressTensor operator/(double s) const {
        return StressTensor(
            xx / s, yy / s, zz / s,
            xy / s, yz / s, zx / s
        );
    }

    // ============================================================
    // Utility Functions
    // ============================================================

    /**
     * @brief Get component by index (LS-DYNA order)
     * @param i Index (0=xx, 1=yy, 2=zz, 3=xy, 4=yz, 5=zx)
     */
    double operator[](int i) const {
        switch (i) {
            case 0: return xx;
            case 1: return yy;
            case 2: return zz;
            case 3: return xy;
            case 4: return yz;
            case 5: return zx;
            default: throw std::out_of_range("StressTensor index out of range");
        }
    }

    /**
     * @brief Convert to array (LS-DYNA order)
     */
    std::array<double, 6> toArray() const {
        return {xx, yy, zz, xy, yz, zx};
    }

    /**
     * @brief Check if tensor is approximately zero
     */
    bool isZero(double eps = 1e-12) const {
        return std::abs(xx) < eps && std::abs(yy) < eps && std::abs(zz) < eps &&
               std::abs(xy) < eps && std::abs(yz) < eps && std::abs(zx) < eps;
    }

    // ============================================================
    // Static Factory Methods
    // ============================================================

    /**
     * @brief Create zero tensor
     */
    static StressTensor zero() {
        return StressTensor();
    }

    /**
     * @brief Create hydrostatic stress tensor
     * @param p Hydrostatic stress (positive = compression)
     */
    static StressTensor hydrostatic(double p) {
        return StressTensor(-p, -p, -p, 0, 0, 0);
    }

    /**
     * @brief Create uniaxial stress tensor
     * @param sigma Uniaxial stress
     * @param axis 0=X, 1=Y, 2=Z
     */
    static StressTensor uniaxial(double sigma, int axis) {
        switch (axis) {
            case 0: return StressTensor(sigma, 0, 0, 0, 0, 0);
            case 1: return StressTensor(0, sigma, 0, 0, 0, 0);
            case 2: return StressTensor(0, 0, sigma, 0, 0, 0);
            default: throw std::out_of_range("Axis must be 0, 1, or 2");
        }
    }

    /**
     * @brief Create pure shear stress tensor
     * @param tau Shear stress magnitude
     * @param plane 0=XY, 1=YZ, 2=ZX
     */
    static StressTensor pureShear(double tau, int plane) {
        switch (plane) {
            case 0: return StressTensor(0, 0, 0, tau, 0, 0);
            case 1: return StressTensor(0, 0, 0, 0, tau, 0);
            case 2: return StressTensor(0, 0, 0, 0, 0, tau);
            default: throw std::out_of_range("Plane must be 0, 1, or 2");
        }
    }
};

// Free function for scalar * tensor
inline StressTensor operator*(double s, const StressTensor& t) {
    return t * s;
}

} // namespace analysis
} // namespace kood3plot
