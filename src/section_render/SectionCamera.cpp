/**
 * @file SectionCamera.cpp
 * @brief Orthographic camera (full implementation)
 *
 * Camera is fixed once per animation from state-0 target bounding box.
 * All rendering frames reuse the same camera parameters.
 *
 * Coordinate frame on the cutting plane:
 *   axis_u_ = right  (plane basis u, from SectionPlane::getBasis)
 *   axis_v_ = up     (plane basis v, from SectionPlane::getBasis)
 *
 * Image convention: pixel (0,0) is TOP-LEFT
 *   px = (u_coord/half_w + 1) * 0.5 * W
 *   py = (1 - v_coord/half_h) * 0.5 * H    ← V flipped
 */

#include "kood3plot/section_render/SectionCamera.hpp"
#include <cmath>
#include <algorithm>

namespace kood3plot {
namespace section_render {

void SectionCamera::setup(const SectionPlane& plane,
                           const AABB3& bbox,
                           double scale_factor,
                           int32_t img_width,
                           int32_t img_height)
{
    img_width_  = img_width;
    img_height_ = img_height;
    origin_     = bbox.center();

    plane.getBasis(axis_u_, axis_v_);

    // Project all 8 bbox corners onto the plane basis to find the view extent
    Vec3 corners[8] = {
        {bbox.min_pt.x, bbox.min_pt.y, bbox.min_pt.z},
        {bbox.max_pt.x, bbox.min_pt.y, bbox.min_pt.z},
        {bbox.min_pt.x, bbox.max_pt.y, bbox.min_pt.z},
        {bbox.max_pt.x, bbox.max_pt.y, bbox.min_pt.z},
        {bbox.min_pt.x, bbox.min_pt.y, bbox.max_pt.z},
        {bbox.max_pt.x, bbox.min_pt.y, bbox.max_pt.z},
        {bbox.min_pt.x, bbox.max_pt.y, bbox.max_pt.z},
        {bbox.max_pt.x, bbox.max_pt.y, bbox.max_pt.z},
    };

    double u_min = 1e300, u_max = -1e300;
    double v_min = 1e300, v_max = -1e300;
    for (const auto& c : corners) {
        double dx = c.x - origin_.x;
        double dy = c.y - origin_.y;
        double dz = c.z - origin_.z;
        double u_coord = dx*axis_u_.x + dy*axis_u_.y + dz*axis_u_.z;
        double v_coord = dx*axis_v_.x + dy*axis_v_.y + dz*axis_v_.z;
        u_min = std::min(u_min, u_coord);
        u_max = std::max(u_max, u_coord);
        v_min = std::min(v_min, v_coord);
        v_max = std::max(v_max, v_coord);
    }

    double extent_u = (u_max - u_min) * 0.5 * scale_factor;
    double extent_v = (v_max - v_min) * 0.5 * scale_factor;

    // Preserve aspect ratio: expand the smaller extent to match image AR
    double img_ar = static_cast<double>(img_width_) / static_cast<double>(img_height_);
    double view_ar = (extent_v > 1e-12) ? (extent_u / extent_v) : img_ar;

    if (view_ar > img_ar) {
        // View is wider than image → expand V to fit
        half_w_ = extent_u;
        half_h_ = extent_u / img_ar;
    } else {
        // View is taller than image → expand U to fit
        half_h_ = extent_v;
        half_w_ = extent_v * img_ar;
    }

    // Guarantee a non-degenerate viewport
    if (half_w_ < 1e-6) { half_w_ = 1.0; half_h_ = 1.0 / img_ar; }
}

Vec2 SectionCamera::project(const Vec3& p) const
{
    double dx = p.x - origin_.x;
    double dy = p.y - origin_.y;
    double dz = p.z - origin_.z;

    double u_coord = dx*axis_u_.x + dy*axis_u_.y + dz*axis_u_.z;
    double v_coord = dx*axis_v_.x + dy*axis_v_.y + dz*axis_v_.z;

    // Map [−half_w, +half_w] → [0, img_width]
    // Map [−half_h, +half_h] → [img_height, 0]  (V flipped: top = positive V)
    double px = ( u_coord / half_w_ + 1.0) * 0.5 * img_width_;
    double py = (1.0 - v_coord / half_h_) * 0.5 * img_height_;

    return {px, py};
}

} // namespace section_render
} // namespace kood3plot
