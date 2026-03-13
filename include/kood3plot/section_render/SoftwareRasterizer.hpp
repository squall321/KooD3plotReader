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

    /** Fill entire buffer with a background color */
    void clear(RGBA color = {30, 30, 30, 255});

    // ----------------------------------------------------------------
    // Drawing primitives
    // ----------------------------------------------------------------

    /**
     * @brief Filled polygon with Gouraud shading (per-vertex color interpolation)
     *
     * polygon.size() must be >= 3.
     * Each vertex has a scalar value; color is looked up from cmap.
     * Uses scanline fill with barycentric interpolation.
     */
    void drawPolygonContour(const ClipPolygon& polygon,
                             const ColorMap& cmap,
                             const SectionCamera& camera);

    /**
     * @brief Filled polygon with Gouraud shading + alpha blending (target fade)
     */
    void drawPolygonContourAlpha(const ClipPolygon& polygon,
                                  const ColorMap& cmap,
                                  const SectionCamera& camera,
                                  float alpha);

    /**
     * @brief Filled polygon with uniform flat color (for background parts)
     *
     * polygon.size() must be >= 3.
     */
    void drawPolygonFlat(const ClipPolygon& polygon,
                          RGBA color,
                          const SectionCamera& camera,
                          float alpha = 1.0f);

    /**
     * @brief Bresenham line segment (for shell cross-sections, size==2)
     *
     * @param thickness  Line width in pixels (at supersampled resolution)
     */
    void drawEdge(const ClipPolygon& segment,
                   const ColorMap& cmap,
                   const SectionCamera& camera,
                   int32_t thickness = 2);

    /** @brief Bresenham line segment with flat (uniform) color */
    void drawEdgeFlat(const ClipPolygon& segment,
                       RGBA color,
                       const SectionCamera& camera,
                       int32_t thickness = 2);

    // ----------------------------------------------------------------
    // Output
    // ----------------------------------------------------------------

    /**
     * @brief Downsample the supersampled buffer to final resolution
     *
     * Box-filter: each output pixel = average of ss_factor×ss_factor source pixels.
     * Returns the final image buffer (width × height × 4 bytes, RGBA).
     */
    std::vector<uint8_t> downsample() const;

    /**
     * @brief Downsample and write PNG file (libpng)
     * @return empty string on success, error message on failure
     */
    std::string savePng(const std::string& filepath) const;

    int32_t width()  const { return width_;  }
    int32_t height() const { return height_; }

private:
    int32_t width_, height_, ss_factor_;
    int32_t ss_width_, ss_height_;

    std::vector<uint8_t> buffer_;  ///< RGBA at supersampled resolution

    void setPixel(int32_t x, int32_t y, RGBA color);
    RGBA getPixel(int32_t x, int32_t y) const;

    // Scanline polygon fill helpers
    void scanlineFill(const std::vector<Vec2>& screen_verts,
                       const std::vector<RGBA>& vert_colors);
    RGBA interpolateColor(const std::vector<Vec2>& verts,
                           const std::vector<RGBA>& colors,
                           double px, double py) const;
};

} // namespace section_render
} // namespace kood3plot
