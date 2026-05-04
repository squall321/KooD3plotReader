#pragma once
/**
 * @file SoftwareRasterizer.hpp
 * @brief CPU software rasterizer for section view polygons and edges
 *
 * Renders ClipPolygons to an RGBA pixel buffer.
 * Supports:
 *   - drawPolygonContour()  — filled polygon with per-vertex Gouraud shading
 *   - drawPolygonFlat()     — filled polygon with uniform color (background parts)
 *   - drawEdge()            — anti-aliased line segment (shell cross-sections)
 *   - drawTriangle3D()      — Z-buffered triangle with flat shading (3D half-model)
 *
 * Anti-aliasing:
 *   The rasterizer operates at 2× supersampling resolution.
 *   After all drawing, downsample() box-filters 2×2 → 1×1 for the final image.
 *
 * Memory layout:
 *   Pixels stored row-major, top-left origin.
 *   Buffer size = (width * ss_factor) × (height * ss_factor) × 4 bytes.
 */

#include "kood3plot/section_render/SectionTypes.hpp"
#include "kood3plot/section_render/ColorMap.hpp"
#include "kood3plot/section_render/SectionCamera.hpp"
#include <cstdint>
#include <string>
#include <vector>

namespace kood3plot {
namespace section_render {

class SoftwareRasterizer {
public:
    /**
     * @brief Construct rasterizer for given output dimensions
     * @param width      Output image width  in pixels
     * @param height     Output image height in pixels
     * @param ss_factor  Supersampling factor (1 = no SS, 2 = 2× recommended)
     */
    SoftwareRasterizer(int32_t width, int32_t height, int32_t ss_factor = 2);

    /** Fill entire buffer with a background color (also clears Z-buffer) */
    void clear(RGBA color = {30, 30, 30, 255});

    /** Enable/disable Z-buffer depth testing (disabled by default for 2D mode) */
    void enableDepthTest(bool enable);

    // ----------------------------------------------------------------
    // 2D Drawing primitives (existing — no depth test)
    // ----------------------------------------------------------------

    void drawPolygonContour(const ClipPolygon& polygon,
                             const ColorMap& cmap,
                             const SectionCamera& camera);

    void drawPolygonContourAlpha(const ClipPolygon& polygon,
                                  const ColorMap& cmap,
                                  const SectionCamera& camera,
                                  float alpha);

    void drawPolygonFlat(const ClipPolygon& polygon,
                          RGBA color,
                          const SectionCamera& camera,
                          float alpha = 1.0f);

    void drawEdge(const ClipPolygon& segment,
                   const ColorMap& cmap,
                   const SectionCamera& camera,
                   int32_t thickness = 2);

    void drawEdgeFlat(const ClipPolygon& segment,
                       RGBA color,
                       const SectionCamera& camera,
                       int32_t thickness = 2);

    // ----------------------------------------------------------------
    // 3D Drawing primitives (Z-buffered — for half-model rendering)
    // ----------------------------------------------------------------

    /**
     * @brief Draw a Z-buffered triangle with flat shading
     *
     * @param p0,p1,p2   Screen-space vertices (x, y in pixels at SS resolution)
     * @param z0,z1,z2   Depth values (smaller = closer; range arbitrary)
     * @param color       Flat color (pre-shaded with diffuse lighting)
     */
    void drawTriangle3D(double p0x, double p0y, double z0,
                         double p1x, double p1y, double z1,
                         double p2x, double p2y, double z2,
                         RGBA color);

    /**
     * @brief Draw a Z-buffered triangle with per-vertex Gouraud shading
     */
    void drawTriangle3DContour(double p0x, double p0y, double z0, RGBA c0,
                                double p1x, double p1y, double z1, RGBA c1,
                                double p2x, double p2y, double z2, RGBA c2);

    /**
     * @brief Draw a Z-buffered translucent triangle (depth read-only).
     *
     * Reads the depth buffer to skip pixels occluded by previously-drawn
     * opaque geometry (depth < pixel_depth → skip). Does NOT write depth,
     * so subsequent translucent layers still see the same depth values.
     *
     * Color is alpha-blended onto the destination: dst = alpha*src + (1-alpha)*dst.
     *
     * Use this for translucent BG parts in iso-surface rendering after
     * opaque target geometry has been drawn.
     */
    void drawTriangle3DAlpha(double p0x, double p0y, double z0,
                              double p1x, double p1y, double z1,
                              double p2x, double p2y, double z2,
                              RGBA color, float alpha);

    /**
     * @brief Rasterize triangle coverage into a per-part silhouette mask
     *        with per-pixel lighting intensity.
     *
     * For each pixel covered by the triangle:
     *   - if pixel_depth >= zbuffer + 1e-4 (strictly behind opaque): skip
     *   - else: set mask[idx]=1; update part_depth[idx]=min(...);
     *           and store the BRIGHTEST shade across all contributing
     *           triangles (so top face's strong ndotl wins over a side
     *           face's dim ndotl at the same pixel).
     *
     * The zbuffer is NOT modified by this call. Used to build a
     * silhouette of an entire BG part — every triangle contributes
     * coverage, the shading captures 3D depth perception, and
     * compositePartSilhouette applies a single alpha-blended color
     * modulated by the per-pixel shade.
     *
     * mask, part_depth, shade must each have ssWidth()*ssHeight() entries.
     * shade values typically in [0,1] (will be clamped on composite).
     */
    void rasterizeToPartMask(double p0x, double p0y, double z0,
                              double p1x, double p1y, double z1,
                              double p2x, double p2y, double z2,
                              float tri_shade,
                              std::vector<uint8_t>& mask,
                              std::vector<float>& part_depth,
                              std::vector<float>& shade);

    /**
     * @brief Composite a part silhouette mask onto the framebuffer.
     *
     * For every masked pixel:
     *   shaded = color × shade[idx]
     *   framebuffer = α*shaded + (1-α)*framebuffer
     * and zbuffer is updated to part_depth so subsequent BG parts can be
     * occlusion-tested correctly.
     *
     * Produces a translucent silhouette per BG part with subtle 3D depth
     * perception (top face bright, side faces darker) — no internal
     * element diagonals, no multi-layer alpha stacking.
     */
    void compositePartSilhouette(const std::vector<uint8_t>& mask,
                                  const std::vector<float>& part_depth,
                                  const std::vector<float>& shade,
                                  RGBA color, float alpha);

    /// Supersampled buffer dimensions (for sizing mask buffers)
    int32_t ssWidth()  const { return ss_width_; }
    int32_t ssHeight() const { return ss_height_; }

    /**
     * @brief Draw a Z-buffered line (for mesh edge wireframe)
     */
    void drawLine3D(double ax, double ay, double az,
                     double bx, double by, double bz,
                     RGBA color, int32_t thickness = 1);

    // ----------------------------------------------------------------
    // Output
    // ----------------------------------------------------------------

    std::vector<uint8_t> downsample() const;
    std::string savePng(const std::string& filepath) const;

    /**
     * @brief Screen-space edge detection via Z-buffer discontinuities
     *
     * Scans the depth buffer for large depth jumps between adjacent pixels.
     * Darkens those pixels to create visible crease/silhouette edges.
     * Also darkens foreground-background boundaries.
     *
     * @param depth_threshold  Relative depth difference to trigger edge darkening
     * @param darken_factor    How much to darken (0.0 = black, 1.0 = no change)
     */
    void applyDepthEdgeDetection(double depth_threshold = 0.02,
                                  double darken_factor = 0.25);

    int32_t width()  const { return width_;  }
    int32_t height() const { return height_; }

private:
    int32_t width_, height_, ss_factor_;
    int32_t ss_width_, ss_height_;

    std::vector<uint8_t> buffer_;   ///< RGBA at supersampled resolution
    std::vector<float>   zbuffer_;  ///< Depth buffer at supersampled resolution
    bool depth_test_ = false;       ///< Z-buffer enabled?

    void setPixel(int32_t x, int32_t y, RGBA color);
    RGBA getPixel(int32_t x, int32_t y) const;

    bool testAndSetDepth(int32_t x, int32_t y, float depth);

    // Scanline polygon fill helpers
    void scanlineFill(const std::vector<Vec2>& screen_verts,
                       const std::vector<RGBA>& vert_colors);
    RGBA interpolateColor(const std::vector<Vec2>& verts,
                           const std::vector<RGBA>& colors,
                           double px, double py) const;
};

} // namespace section_render
} // namespace kood3plot
