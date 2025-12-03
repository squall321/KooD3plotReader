#pragma once

/**
 * @file SpatialSelector.h
 * @brief Spatial region selection for the KooD3plot Query System
 * @author KooD3plot V3 Development Team
 * @date 2025-11-22
 * @version 3.0.0
 *
 * SpatialSelector provides geometric region-based selection of elements
 * and nodes. Supports bounding boxes, spheres, cylinders, and section planes.
 *
 * Example usage:
 * @code
 * // Select elements in a bounding box
 * SpatialSelector::boundingBox({0, 0, 0}, {100, 50, 50});
 *
 * // Select elements in a sphere
 * SpatialSelector::sphere({50, 25, 25}, 30.0);
 *
 * // Select elements cut by a plane
 * SpatialSelector::sectionPlane({0, 0, 0}, {1, 0, 0});  // YZ plane at x=0
 * @endcode
 */

#include <vector>
#include <array>
#include <memory>
#include <string>
#include <cmath>

namespace kood3plot {
namespace query {

/**
 * @brief 3D point type
 */
using Point3D = std::array<double, 3>;

/**
 * @brief 3D vector type
 */
using Vector3D = std::array<double, 3>;

/**
 * @brief Bounding box structure for spatial selection
 */
struct SpatialBoundingBox {
    Point3D min_point;  ///< Minimum corner
    Point3D max_point;  ///< Maximum corner

    /**
     * @brief Check if point is inside box
     */
    bool contains(const Point3D& point) const {
        return point[0] >= min_point[0] && point[0] <= max_point[0] &&
               point[1] >= min_point[1] && point[1] <= max_point[1] &&
               point[2] >= min_point[2] && point[2] <= max_point[2];
    }

    /**
     * @brief Get center of bounding box
     */
    Point3D center() const {
        return {
            (min_point[0] + max_point[0]) / 2.0,
            (min_point[1] + max_point[1]) / 2.0,
            (min_point[2] + max_point[2]) / 2.0
        };
    }

    /**
     * @brief Get dimensions (width, height, depth)
     */
    Vector3D dimensions() const {
        return {
            max_point[0] - min_point[0],
            max_point[1] - min_point[1],
            max_point[2] - min_point[2]
        };
    }
};

/**
 * @brief Sphere structure for spatial selection
 */
struct SpatialSphere {
    Point3D center;  ///< Center point
    double radius;   ///< Radius

    /**
     * @brief Check if point is inside sphere
     */
    bool contains(const Point3D& point) const {
        double dx = point[0] - center[0];
        double dy = point[1] - center[1];
        double dz = point[2] - center[2];
        return (dx*dx + dy*dy + dz*dz) <= (radius * radius);
    }
};

/**
 * @brief Cylinder structure for spatial selection
 */
struct SpatialCylinder {
    Point3D center;     ///< Center of base
    Vector3D axis;      ///< Axis direction (normalized)
    double radius;      ///< Radius
    double height;      ///< Height along axis

    /**
     * @brief Check if point is inside cylinder
     */
    bool contains(const Point3D& point) const {
        // Vector from center to point
        double vx = point[0] - center[0];
        double vy = point[1] - center[1];
        double vz = point[2] - center[2];

        // Project onto axis
        double proj = vx * axis[0] + vy * axis[1] + vz * axis[2];

        // Check height bounds
        if (proj < 0 || proj > height) return false;

        // Perpendicular distance from axis
        double px = vx - proj * axis[0];
        double py = vy - proj * axis[1];
        double pz = vz - proj * axis[2];
        double perp_dist_sq = px*px + py*py + pz*pz;

        return perp_dist_sq <= (radius * radius);
    }
};

/**
 * @brief Section plane structure for spatial selection
 */
struct SpatialSectionPlane {
    Point3D point;     ///< Point on plane
    Vector3D normal;   ///< Normal vector (normalized)
    double tolerance;  ///< Tolerance for plane intersection

    /**
     * @brief Get signed distance from point to plane
     */
    double signedDistance(const Point3D& p) const {
        return (p[0] - point[0]) * normal[0] +
               (p[1] - point[1]) * normal[1] +
               (p[2] - point[2]) * normal[2];
    }

    /**
     * @brief Check if point is on the positive side of plane
     */
    bool isPositiveSide(const Point3D& p) const {
        return signedDistance(p) >= 0;
    }

    /**
     * @brief Check if point is near the plane (within tolerance)
     */
    bool isOnPlane(const Point3D& p) const {
        return std::abs(signedDistance(p)) <= tolerance;
    }
};

/**
 * @brief Spatial region type
 */
enum class SpatialRegionType {
    NONE,           ///< No region (all)
    BOUNDING_BOX,   ///< Axis-aligned bounding box
    SPHERE,         ///< Spherical region
    CYLINDER,       ///< Cylindrical region
    SECTION_PLANE,  ///< Cut plane
    HALF_SPACE,     ///< Half space (one side of plane)
    CUSTOM          ///< Custom predicate
};

/**
 * @class SpatialSelector
 * @brief Selects elements/nodes by spatial region
 *
 * Provides geometric region-based selection using bounding boxes,
 * spheres, cylinders, and section planes.
 */
class SpatialSelector {
public:
    // ============================================================
    // Constructors
    // ============================================================

    /**
     * @brief Default constructor (selects all)
     */
    SpatialSelector();

    /**
     * @brief Copy constructor
     */
    SpatialSelector(const SpatialSelector& other);

    /**
     * @brief Move constructor
     */
    SpatialSelector(SpatialSelector&& other) noexcept;

    /**
     * @brief Assignment operator
     */
    SpatialSelector& operator=(const SpatialSelector& other);

    /**
     * @brief Move assignment operator
     */
    SpatialSelector& operator=(SpatialSelector&& other) noexcept;

    /**
     * @brief Destructor
     */
    ~SpatialSelector();

    // ============================================================
    // Region Specification
    // ============================================================

    /**
     * @brief Set bounding box region
     * @param min_point Minimum corner (x, y, z)
     * @param max_point Maximum corner (x, y, z)
     * @return Reference for chaining
     */
    SpatialSelector& box(const Point3D& min_point, const Point3D& max_point);

    /**
     * @brief Set bounding box region (convenience)
     */
    SpatialSelector& box(double x_min, double y_min, double z_min,
                         double x_max, double y_max, double z_max);

    /**
     * @brief Set spherical region
     * @param center Sphere center
     * @param radius Sphere radius
     * @return Reference for chaining
     */
    SpatialSelector& sphere(const Point3D& center, double radius);

    /**
     * @brief Set cylindrical region
     * @param base_center Center of cylinder base
     * @param axis Axis direction
     * @param radius Cylinder radius
     * @param height Cylinder height
     * @return Reference for chaining
     */
    SpatialSelector& cylinder(const Point3D& base_center,
                              const Vector3D& axis,
                              double radius,
                              double height);

    /**
     * @brief Set section plane
     * @param point Point on plane
     * @param normal Plane normal
     * @param tolerance Thickness tolerance
     * @return Reference for chaining
     */
    SpatialSelector& plane(const Point3D& point,
                           const Vector3D& normal,
                           double tolerance = 1.0);

    /**
     * @brief Set half-space (one side of plane)
     * @param point Point on dividing plane
     * @param normal Normal pointing to included side
     * @return Reference for chaining
     */
    SpatialSelector& halfSpace(const Point3D& point,
                               const Vector3D& normal);

    // ============================================================
    // Convenience Planes
    // ============================================================

    /**
     * @brief XY plane at z = value
     */
    SpatialSelector& xyPlane(double z, double tolerance = 1.0);

    /**
     * @brief YZ plane at x = value
     */
    SpatialSelector& yzPlane(double x, double tolerance = 1.0);

    /**
     * @brief XZ plane at y = value
     */
    SpatialSelector& xzPlane(double y, double tolerance = 1.0);

    // ============================================================
    // Point Testing
    // ============================================================

    /**
     * @brief Test if a point is within the selected region
     * @param point Point to test
     * @return true if point is in region
     */
    bool contains(const Point3D& point) const;

    /**
     * @brief Test if a point is within the selected region
     */
    bool contains(double x, double y, double z) const;

    /**
     * @brief Filter points, return indices of points in region
     * @param points Vector of points
     * @return Indices of points in region
     */
    std::vector<size_t> filter(const std::vector<Point3D>& points) const;

    // ============================================================
    // Logical Operators
    // ============================================================

    /**
     * @brief AND combination (intersection)
     */
    SpatialSelector operator&&(const SpatialSelector& other) const;

    /**
     * @brief OR combination (union)
     */
    SpatialSelector operator||(const SpatialSelector& other) const;

    /**
     * @brief NOT (invert/complement)
     */
    SpatialSelector operator!() const;

    // ============================================================
    // Query Methods
    // ============================================================

    /**
     * @brief Get region type
     */
    SpatialRegionType getType() const;

    /**
     * @brief Get human-readable description
     */
    std::string getDescription() const;

    /**
     * @brief Check if selector is empty (selects nothing)
     */
    bool isEmpty() const;

    /**
     * @brief Check if selector selects all
     */
    bool isAll() const;

    // ============================================================
    // Static Factory Methods
    // ============================================================

    /**
     * @brief Create bounding box selector
     */
    static SpatialSelector boundingBox(const Point3D& min_pt, const Point3D& max_pt);

    /**
     * @brief Create sphere selector
     */
    static SpatialSelector sphereRegion(const Point3D& center, double radius);

    /**
     * @brief Create section plane selector
     */
    static SpatialSelector sectionPlane(const Point3D& point, const Vector3D& normal,
                                        double tolerance = 1.0);

    /**
     * @brief Select all (no spatial filter)
     */
    static SpatialSelector all();

    /**
     * @brief Select none
     */
    static SpatialSelector none();

private:
    struct Impl;
    std::unique_ptr<Impl> pImpl;
};

} // namespace query
} // namespace kood3plot
