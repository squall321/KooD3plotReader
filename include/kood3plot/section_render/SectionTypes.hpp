#pragma once
/**
 * @file SectionTypes.hpp
 * @brief Common types for section render module
 *
 * Defines Vec2, ClipVertex, ClipPolygon shared across all section_render classes.
 * Reuses Vec3 from existing kood3plot::analysis::VectorMath.
 */

#include "kood3plot/analysis/VectorMath.hpp"
#include <vector>
#include <cstdint>

namespace kood3plot {
namespace section_render {

// Reuse existing Vec3 from analysis module
using Vec3 = kood3plot::analysis::Vec3;

// ============================================================
// 2D screen coordinate
// ============================================================
struct Vec2 {
    double x = 0.0;
    double y = 0.0;

    Vec2() = default;
    Vec2(double x_, double y_) : x(x_), y(y_) {}

    Vec2 operator+(const Vec2& o) const { return {x + o.x, y + o.y}; }
    Vec2 operator-(const Vec2& o) const { return {x - o.x, y - o.y}; }
    Vec2 operator*(double s)      const { return {x * s,   y * s};   }
};

// ============================================================
// ClipVertex: a vertex produced by the section plane clipper
// ============================================================
struct ClipVertex {
    Vec3    position;   // 3D world position of the intersection point
    double  value;      // interpolated scalar field value at this point
    int32_t part_id;    // which part this vertex belongs to

    ClipVertex() : value(0.0), part_id(0) {}
    ClipVertex(const Vec3& pos, double val, int32_t pid)
        : position(pos), value(val), part_id(pid) {}
};

// ============================================================
// ClipPolygon: result of one element's intersection with the plane
//
//   size() == 0  -> no intersection (skip)
//   size() == 2  -> Shell element cross-section (line segment)
//                   render with drawEdge()
//   size() >= 3  -> Solid/ThickShell cross-section polygon
//                   render with drawPolygonContour() or drawPolygonFlat()
// ============================================================
using ClipPolygon = std::vector<ClipVertex>;

} // namespace section_render
} // namespace kood3plot
