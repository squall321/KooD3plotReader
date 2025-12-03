#pragma once

#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"
#include <limits>
#include <cmath>
#include <vector>
#include <array>
#include <iostream>

namespace kood3plot {
namespace analysis {

/**
 * @brief 3D point structure
 */
struct Point3D {
    double x, y, z;

    Point3D() : x(0), y(0), z(0) {}
    Point3D(double x_, double y_, double z_) : x(x_), y(y_), z(z_) {}

    Point3D operator+(const Point3D& other) const {
        return Point3D(x + other.x, y + other.y, z + other.z);
    }

    Point3D operator-(const Point3D& other) const {
        return Point3D(x - other.x, y - other.y, z - other.z);
    }

    Point3D operator*(double scalar) const {
        return Point3D(x * scalar, y * scalar, z * scalar);
    }

    double length() const {
        return std::sqrt(x * x + y * y + z * z);
    }
};

/**
 * @brief Axis-Aligned Bounding Box (AABB)
 *
 * Represents a 3D bounding box aligned with the coordinate axes.
 * Provides utilities for calculating model extent, center, and view setup.
 *
 * Usage:
 * @code
 * D3plotReader reader("d3plot");
 * reader.open();
 * auto mesh = reader.read_mesh();
 *
 * BoundingBox bbox(mesh);
 * std::cout << "Center: " << bbox.center() << "\n";
 * std::cout << "Extent: " << bbox.extent() << "\n";
 * @endcode
 */
class BoundingBox {
public:
    /**
     * @brief Default constructor - creates an invalid (empty) box
     */
    BoundingBox();

    /**
     * @brief Construct from mesh nodes
     * @param mesh Mesh containing node coordinates
     */
    explicit BoundingBox(const data::Mesh& mesh);

    /**
     * @brief Construct from mesh with deformation state
     * @param mesh Base mesh
     * @param state State data containing displacements
     */
    BoundingBox(const data::Mesh& mesh, const data::StateData& state);

    /**
     * @brief Construct from explicit min/max points
     */
    BoundingBox(const Point3D& min_pt, const Point3D& max_pt);

    /**
     * @brief Get minimum point (corner with smallest coordinates)
     */
    const Point3D& min() const { return min_; }

    /**
     * @brief Get maximum point (corner with largest coordinates)
     */
    const Point3D& max() const { return max_; }

    /**
     * @brief Get center point of the box
     */
    Point3D center() const;

    /**
     * @brief Get size (width, height, depth)
     */
    Point3D size() const;

    /**
     * @brief Get diagonal length
     */
    double diagonal() const;

    /**
     * @brief Get extent (max of width, height, depth)
     * Useful for setting view scale
     */
    double extent() const;

    /**
     * @brief Check if box is valid (non-empty)
     */
    bool is_valid() const;

    /**
     * @brief Expand box to include a point
     */
    void expand(const Point3D& point);

    /**
     * @brief Expand box to include another bounding box
     */
    void expand(const BoundingBox& other);

    /**
     * @brief Reset to invalid state
     */
    void reset();

    /**
     * @brief Calculate X-direction size
     */
    double width() const { return max_.x - min_.x; }

    /**
     * @brief Calculate Y-direction size
     */
    double height() const { return max_.y - min_.y; }

    /**
     * @brief Calculate Z-direction size
     */
    double depth() const { return max_.z - min_.z; }

    /**
     * @brief Get all 8 corners of the box
     */
    std::array<Point3D, 8> corners() const;

    /**
     * @brief Calculate bounding box for specific parts
     * @param mesh Mesh data
     * @param part_ids Part IDs to include (empty = all parts)
     * @param state Optional deformation state
     * @return BoundingBox for specified parts
     */
    static BoundingBox from_parts(
        const data::Mesh& mesh,
        const std::vector<int32_t>& part_ids,
        const data::StateData* state = nullptr);

    /**
     * @brief Calculate bounding box for node subset
     * @param mesh Mesh data
     * @param node_indices Internal node indices to include
     * @param state Optional deformation state
     * @return BoundingBox for specified nodes
     */
    static BoundingBox from_nodes(
        const data::Mesh& mesh,
        const std::vector<size_t>& node_indices,
        const data::StateData* state = nullptr);

private:
    Point3D min_;
    Point3D max_;

    void compute_from_mesh(const data::Mesh& mesh, const data::StateData* state = nullptr);
};

/**
 * @brief Output operator for Point3D
 */
inline std::ostream& operator<<(std::ostream& os, const Point3D& pt) {
    os << "(" << pt.x << ", " << pt.y << ", " << pt.z << ")";
    return os;
}

/**
 * @brief Output operator for BoundingBox
 */
inline std::ostream& operator<<(std::ostream& os, const BoundingBox& bbox) {
    os << "BoundingBox[min=" << bbox.min() << ", max=" << bbox.max()
       << ", center=" << bbox.center() << ", extent=" << bbox.extent() << "]";
    return os;
}

} // namespace analysis
} // namespace kood3plot