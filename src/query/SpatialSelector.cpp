/**
 * @file SpatialSelector.cpp
 * @brief Implementation of SpatialSelector class
 * @author KooD3plot V3 Development Team
 * @date 2025-11-22
 * @version 3.0.0
 */

#include "kood3plot/query/SpatialSelector.h"
#include <sstream>
#include <cmath>
#include <algorithm>
#include <functional>

namespace kood3plot {
namespace query {

// ============================================================
// Helper Functions
// ============================================================

namespace {

Vector3D normalize(const Vector3D& v) {
    double len = std::sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]);
    if (len < 1e-10) return {0, 0, 1};  // Default to Z axis
    return {v[0]/len, v[1]/len, v[2]/len};
}

} // anonymous namespace

// ============================================================
// PIMPL Implementation
// ============================================================

struct SpatialSelector::Impl {
    SpatialRegionType type = SpatialRegionType::NONE;

    // Region data (use appropriate one based on type)
    SpatialBoundingBox bbox;
    SpatialSphere sphere;
    SpatialCylinder cylinder;
    SpatialSectionPlane section_plane;

    // For half-space
    bool half_space_positive = true;

    // For combined selectors
    std::shared_ptr<SpatialSelector> child1;
    std::shared_ptr<SpatialSelector> child2;
    enum class CombineOp { NONE, AND, OR, NOT } combine_op = CombineOp::NONE;

    // Custom predicate
    std::function<bool(const Point3D&)> custom_predicate;

    bool testPoint(const Point3D& p) const {
        switch (type) {
            case SpatialRegionType::NONE:
                return true;  // Select all

            case SpatialRegionType::BOUNDING_BOX:
                return bbox.contains(p);

            case SpatialRegionType::SPHERE:
                return sphere.contains(p);

            case SpatialRegionType::CYLINDER:
                return cylinder.contains(p);

            case SpatialRegionType::SECTION_PLANE:
                return section_plane.isOnPlane(p);

            case SpatialRegionType::HALF_SPACE:
                return half_space_positive ?
                    section_plane.isPositiveSide(p) :
                    !section_plane.isPositiveSide(p);

            case SpatialRegionType::CUSTOM:
                return custom_predicate ? custom_predicate(p) : true;

            default:
                return true;
        }
    }
};

// ============================================================
// Constructors and Destructor
// ============================================================

SpatialSelector::SpatialSelector()
    : pImpl(std::make_unique<Impl>())
{
}

SpatialSelector::SpatialSelector(const SpatialSelector& other)
    : pImpl(std::make_unique<Impl>(*other.pImpl))
{
}

SpatialSelector::SpatialSelector(SpatialSelector&& other) noexcept = default;

SpatialSelector& SpatialSelector::operator=(const SpatialSelector& other) {
    if (this != &other) {
        pImpl = std::make_unique<Impl>(*other.pImpl);
    }
    return *this;
}

SpatialSelector& SpatialSelector::operator=(SpatialSelector&& other) noexcept = default;

SpatialSelector::~SpatialSelector() = default;

// ============================================================
// Region Specification
// ============================================================

SpatialSelector& SpatialSelector::box(const Point3D& min_point, const Point3D& max_point) {
    pImpl->type = SpatialRegionType::BOUNDING_BOX;
    pImpl->bbox.min_point = min_point;
    pImpl->bbox.max_point = max_point;
    return *this;
}

SpatialSelector& SpatialSelector::box(double x_min, double y_min, double z_min,
                                       double x_max, double y_max, double z_max) {
    return box({x_min, y_min, z_min}, {x_max, y_max, z_max});
}

SpatialSelector& SpatialSelector::sphere(const Point3D& center, double radius) {
    pImpl->type = SpatialRegionType::SPHERE;
    pImpl->sphere.center = center;
    pImpl->sphere.radius = radius;
    return *this;
}

SpatialSelector& SpatialSelector::cylinder(const Point3D& base_center,
                                            const Vector3D& axis,
                                            double radius,
                                            double height) {
    pImpl->type = SpatialRegionType::CYLINDER;
    pImpl->cylinder.center = base_center;
    pImpl->cylinder.axis = normalize(axis);
    pImpl->cylinder.radius = radius;
    pImpl->cylinder.height = height;
    return *this;
}

SpatialSelector& SpatialSelector::plane(const Point3D& point,
                                         const Vector3D& normal,
                                         double tolerance) {
    pImpl->type = SpatialRegionType::SECTION_PLANE;
    pImpl->section_plane.point = point;
    pImpl->section_plane.normal = normalize(normal);
    pImpl->section_plane.tolerance = tolerance;
    return *this;
}

SpatialSelector& SpatialSelector::halfSpace(const Point3D& point,
                                             const Vector3D& normal) {
    pImpl->type = SpatialRegionType::HALF_SPACE;
    pImpl->section_plane.point = point;
    pImpl->section_plane.normal = normalize(normal);
    pImpl->half_space_positive = true;
    return *this;
}

// ============================================================
// Convenience Planes
// ============================================================

SpatialSelector& SpatialSelector::xyPlane(double z, double tolerance) {
    return plane({0, 0, z}, {0, 0, 1}, tolerance);
}

SpatialSelector& SpatialSelector::yzPlane(double x, double tolerance) {
    return plane({x, 0, 0}, {1, 0, 0}, tolerance);
}

SpatialSelector& SpatialSelector::xzPlane(double y, double tolerance) {
    return plane({0, y, 0}, {0, 1, 0}, tolerance);
}

// ============================================================
// Point Testing
// ============================================================

bool SpatialSelector::contains(const Point3D& point) const {
    // Handle combined selectors
    if (pImpl->combine_op != Impl::CombineOp::NONE) {
        switch (pImpl->combine_op) {
            case Impl::CombineOp::AND:
                return pImpl->child1->contains(point) && pImpl->child2->contains(point);
            case Impl::CombineOp::OR:
                return pImpl->child1->contains(point) || pImpl->child2->contains(point);
            case Impl::CombineOp::NOT:
                return !pImpl->child1->contains(point);
            default:
                break;
        }
    }

    return pImpl->testPoint(point);
}

bool SpatialSelector::contains(double x, double y, double z) const {
    return contains(Point3D{x, y, z});
}

std::vector<size_t> SpatialSelector::filter(const std::vector<Point3D>& points) const {
    std::vector<size_t> indices;
    indices.reserve(points.size() / 4);  // Estimate

    for (size_t i = 0; i < points.size(); ++i) {
        if (contains(points[i])) {
            indices.push_back(i);
        }
    }

    return indices;
}

// ============================================================
// Logical Operators
// ============================================================

SpatialSelector SpatialSelector::operator&&(const SpatialSelector& other) const {
    SpatialSelector result;
    result.pImpl->combine_op = Impl::CombineOp::AND;
    result.pImpl->child1 = std::make_shared<SpatialSelector>(*this);
    result.pImpl->child2 = std::make_shared<SpatialSelector>(other);
    return result;
}

SpatialSelector SpatialSelector::operator||(const SpatialSelector& other) const {
    SpatialSelector result;
    result.pImpl->combine_op = Impl::CombineOp::OR;
    result.pImpl->child1 = std::make_shared<SpatialSelector>(*this);
    result.pImpl->child2 = std::make_shared<SpatialSelector>(other);
    return result;
}

SpatialSelector SpatialSelector::operator!() const {
    SpatialSelector result;
    result.pImpl->combine_op = Impl::CombineOp::NOT;
    result.pImpl->child1 = std::make_shared<SpatialSelector>(*this);
    return result;
}

// ============================================================
// Query Methods
// ============================================================

SpatialRegionType SpatialSelector::getType() const {
    return pImpl->type;
}

std::string SpatialSelector::getDescription() const {
    std::ostringstream oss;

    if (pImpl->combine_op != Impl::CombineOp::NONE) {
        switch (pImpl->combine_op) {
            case Impl::CombineOp::AND:
                oss << "(" << pImpl->child1->getDescription()
                    << " AND " << pImpl->child2->getDescription() << ")";
                break;
            case Impl::CombineOp::OR:
                oss << "(" << pImpl->child1->getDescription()
                    << " OR " << pImpl->child2->getDescription() << ")";
                break;
            case Impl::CombineOp::NOT:
                oss << "NOT(" << pImpl->child1->getDescription() << ")";
                break;
            default:
                break;
        }
        return oss.str();
    }

    switch (pImpl->type) {
        case SpatialRegionType::NONE:
            oss << "All (no spatial filter)";
            break;

        case SpatialRegionType::BOUNDING_BOX:
            oss << "Box[("
                << pImpl->bbox.min_point[0] << "," << pImpl->bbox.min_point[1] << "," << pImpl->bbox.min_point[2]
                << ") to ("
                << pImpl->bbox.max_point[0] << "," << pImpl->bbox.max_point[1] << "," << pImpl->bbox.max_point[2]
                << ")]";
            break;

        case SpatialRegionType::SPHERE:
            oss << "Sphere[center=("
                << pImpl->sphere.center[0] << "," << pImpl->sphere.center[1] << "," << pImpl->sphere.center[2]
                << "), r=" << pImpl->sphere.radius << "]";
            break;

        case SpatialRegionType::CYLINDER:
            oss << "Cylinder[r=" << pImpl->cylinder.radius
                << ", h=" << pImpl->cylinder.height << "]";
            break;

        case SpatialRegionType::SECTION_PLANE:
            oss << "Plane[at ("
                << pImpl->section_plane.point[0] << "," << pImpl->section_plane.point[1] << "," << pImpl->section_plane.point[2]
                << "), tol=" << pImpl->section_plane.tolerance << "]";
            break;

        case SpatialRegionType::HALF_SPACE:
            oss << "HalfSpace[" << (pImpl->half_space_positive ? "+" : "-") << " side]";
            break;

        case SpatialRegionType::CUSTOM:
            oss << "Custom predicate";
            break;
    }

    return oss.str();
}

bool SpatialSelector::isEmpty() const {
    // A selector is "empty" if it's explicitly set to select nothing
    // For now, we don't have a "none" state, so this returns false
    return false;
}

bool SpatialSelector::isAll() const {
    return pImpl->type == SpatialRegionType::NONE &&
           pImpl->combine_op == Impl::CombineOp::NONE;
}

// ============================================================
// Static Factory Methods
// ============================================================

SpatialSelector SpatialSelector::boundingBox(const Point3D& min_pt, const Point3D& max_pt) {
    SpatialSelector sel;
    sel.box(min_pt, max_pt);
    return sel;
}

SpatialSelector SpatialSelector::sphereRegion(const Point3D& center, double radius) {
    SpatialSelector sel;
    sel.sphere(center, radius);
    return sel;
}

SpatialSelector SpatialSelector::sectionPlane(const Point3D& point, const Vector3D& normal,
                                               double tolerance) {
    SpatialSelector sel;
    sel.plane(point, normal, tolerance);
    return sel;
}

SpatialSelector SpatialSelector::all() {
    return SpatialSelector();  // Default is "select all"
}

SpatialSelector SpatialSelector::none() {
    SpatialSelector sel;
    // Create a box that contains nothing
    sel.box({0, 0, 0}, {-1, -1, -1});  // Invalid box
    return sel;
}

} // namespace query
} // namespace kood3plot
