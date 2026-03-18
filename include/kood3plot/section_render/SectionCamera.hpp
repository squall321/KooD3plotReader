#pragma once
/**
 * @file SectionCamera.hpp
 * @brief Orthographic camera for section view rendering
 *
 * Camera is fixed once per animation (computed from state 0 target-part bounding box).
 * Projects 3D world coordinates to 2D pixel coordinates for the rasterizer.
 *
 * Coordinate system:
 *   - View direction: plane normal (camera looks along -normal into the plane)
 *   - Up vector:      SectionPlane::getBasis() second vector (v)
 *   - Right vector:   SectionPlane::getBasis() first vector (u)
 *
 * Viewport:
 *   - Fitted to target part bounding box × scale_factor
 *   - Aspect ratio derived from output image width/height
 */

#include "kood3plot/section_render/SectionTypes.hpp"
#include "kood3plot/section_render/SectionPlane.hpp"
#include <cstdint>

namespace kood3plot {
namespace section_render {

/** 3D axis-aligned bounding box */
struct AABB3 {
    Vec3 min_pt{0, 0, 0};
    Vec3 max_pt{0, 0, 0};

    Vec3 center() const {
        return { (min_pt.x + max_pt.x) * 0.5,
                 (min_pt.y + max_pt.y) * 0.5,
                 (min_pt.z + max_pt.z) * 0.5 };
    }

    void expand(const Vec3& p) {
        if (p.x < min_pt.x) min_pt.x = p.x;
        if (p.y < min_pt.y) min_pt.y = p.y;
        if (p.z < min_pt.z) min_pt.z = p.z;
        if (p.x > max_pt.x) max_pt.x = p.x;
        if (p.y > max_pt.y) max_pt.y = p.y;
        if (p.z > max_pt.z) max_pt.z = p.z;
    }
};

class SectionCamera {
public:
    /**
     * @brief Set up the camera from the plane and the target-part bounding box
     *
     * @param plane         The section plane (provides basis vectors)
     * @param bbox          Bounding box of the target parts (in world space)
     * @param scale_factor  Viewport = bbox extent × scale_factor (default 1.2)
     * @param img_width     Output image width  in pixels
     * @param img_height    Output image height in pixels
     */
    void setup(const SectionPlane& plane,
               const AABB3& bbox,
               double scale_factor,
               int32_t img_width,
               int32_t img_height);

    /**
     * @brief Project a 3D world point to 2D pixel coordinates
     *
     * Returns pixel (px, py) where (0,0) is top-left.
     * Points outside the viewport are not clipped here.
     */
    Vec2 project(const Vec3& world_point) const;

    /**
     * @brief Set up an isometric 3D camera for half-model rendering
     *
     * The camera views the model from an oblique angle that shows 3D depth.
     * For axis-aligned cuts, it rotates ~45° azimuth and ~35° elevation
     * from the cut plane normal, giving good visibility of both the
     * cut face and the 3D exterior surface.
     *
     * @param plane         The section plane (provides normal and basis vectors)
     * @param bbox          Bounding box of the visible half-model (in world space)
     * @param scale_factor  Viewport = bbox extent × scale_factor (default 1.2)
     * @param img_width     Output image width  in pixels
     * @param img_height    Output image height in pixels
     */
    void setupIsometric(const SectionPlane& plane,
                        const AABB3& bbox,
                        double scale_factor,
                        int32_t img_width,
                        int32_t img_height);

    /**
     * @brief Project a 3D world point to 2D pixel coordinates + depth
     *
     * Like project(), but also returns a depth value for Z-buffer testing.
     * Depth is the signed distance along the view direction from the camera.
     * Smaller depth = closer to camera.
     *
     * @param world_point  3D world coordinates
     * @param depth        Output: depth value (smaller = closer)
     * @return             Pixel coordinates (px, py), (0,0) is top-left
     */
    Vec2 project3D(const Vec3& world_point, double& depth) const;

    /** @brief Get the view direction (camera looks along -view_dir) */
    const Vec3& viewDirection() const { return view_dir_; }

    /** @brief Camera right axis (u) and up axis (v) */
    const Vec3& axisU() const { return axis_u_; }
    const Vec3& axisV() const { return axis_v_; }

    int32_t imageWidth()  const { return img_width_;  }
    int32_t imageHeight() const { return img_height_; }

private:
    Vec3    origin_;      ///< Centre of the viewport in world space
    Vec3    axis_u_;      ///< Right direction (plane basis u)
    Vec3    axis_v_;      ///< Up direction    (plane basis v, points toward pixel row 0)
    Vec3    view_dir_;    ///< View direction (camera looks along -view_dir_)

    double  half_w_;      ///< Half world-space width  of viewport
    double  half_h_;      ///< Half world-space height of viewport

    int32_t img_width_  = 1920;
    int32_t img_height_ = 1080;
};

} // namespace section_render
} // namespace kood3plot
