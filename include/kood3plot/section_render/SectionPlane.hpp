#pragma once
/**
 * @file SectionPlane.hpp
 * @brief Section plane definition and intersection utilities
 *
 * Supports axis-aligned planes (X/Y/Z) and arbitrary normal planes.
 * Provides signed distance, edge intersection, and 2D basis for radial sort.
 */

#include "kood3plot/section_render/SectionTypes.hpp"

namespace kood3plot {
namespace section_render {

/**
 * @brief Infinite cutting plane defined by a normal and a point on the plane
 *
 * All intersection math lives here.  Consumers (SectionClipper) use:
 *   - signedDistance()     to classify element vertices
 *   - edgeIntersection()   to find the crossing parameter t
 *   - getBasis()           to project 3D intersection points onto 2D for
 *                          radial sort (convex-hull ordering of hex8 cuts)
 */
class SectionPlane {
public:
    // ----------------------------------------------------------------
    // Factories
    // ----------------------------------------------------------------

    /**
     * @brief Axis-aligned plane
     * @param axis  'x', 'y', or 'z' (case-insensitive)
     * @param point Any point on the plane (only the relevant component matters)
     */
    static SectionPlane fromAxis(char axis, const Vec3& point);

    /**
     * @brief Arbitrary-normal plane
     * @param normal Direction perpendicular to the plane (need not be unit-length)
     * @param point  Any point on the plane
     */
    static SectionPlane fromNormal(const Vec3& normal, const Vec3& point);

    // ----------------------------------------------------------------
    // Geometry queries
    // ----------------------------------------------------------------

    /**
     * @brief Signed distance from point p to the plane
     *
     * Positive side is the direction normal_ points toward.
     * Zero means the point lies exactly on the plane.
     */
    double signedDistance(const Vec3& p) const;

    /**
     * @brief Compute edge-plane intersection parameter t
     *
     * If the edge [a, b] crosses the plane, writes t∈(0,1) such that
     *   intersection = a + t*(b - a)
     * and returns true.  Returns false when the edge is parallel to (or
     * entirely on) the plane.
     *
     * @param a  First edge vertex
     * @param b  Second edge vertex
     * @param t  Output: interpolation parameter (0=a, 1=b)
     */
    bool edgeIntersection(const Vec3& a, const Vec3& b, double& t) const;

    /**
     * @brief Compute two orthogonal unit vectors that span the plane
     *
     * Used to project 3D intersection points to 2D for atan2-based
     * radial sort of hex8 cross-sections.
     *
     * Convention for ViewUp selection:
     *   |normal·Z| < 0.9  →  v = (0,0,1) projected onto plane
     *   |normal·Y| < 0.9  →  v = (0,1,0) projected onto plane
     *   else              →  v = (1,0,0) projected onto plane
     *
     * @param u  Output: first  basis vector on the plane
     * @param v  Output: second basis vector on the plane (u×normal)
     */
    void getBasis(Vec3& u, Vec3& v) const;

    // ----------------------------------------------------------------
    // Accessors
    // ----------------------------------------------------------------

    const Vec3& normal() const { return normal_; }
    const Vec3& point()  const { return point_;  }

private:
    Vec3   normal_;   ///< Unit normal (always normalised in factories)
    Vec3   point_;    ///< A point on the plane
    double d_;        ///< Plane constant: d = normal · point

    /// Private constructor — use factories
    SectionPlane(const Vec3& normal, const Vec3& point);
};

} // namespace section_render
} // namespace kood3plot
