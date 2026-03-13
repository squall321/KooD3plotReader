#pragma once
/**
 * @file ColorMap.hpp
 * @brief Scalar-to-color mapping for contour rendering
 *
 * Provides:
 *   - Named colormaps: Rainbow, Jet, CoolWarm, Grayscale
 *   - Per-frame auto-range (from min/max of visible values)
 *   - Global range (fixed across all frames for animation consistency)
 *   - Per-part categorical color (for background parts)
 */

#include <cstdint>
#include <string>

namespace kood3plot {
namespace section_render {

// ============================================================
// RGBA color (8-bit per channel)
// ============================================================
struct RGBA {
    uint8_t r = 0, g = 0, b = 0, a = 255;

    RGBA() = default;
    RGBA(uint8_t r_, uint8_t g_, uint8_t b_, uint8_t a_ = 255)
        : r(r_), g(g_), b(b_), a(a_) {}
};

// ============================================================
// Colormap type
// ============================================================
enum class ColorMapType {
    Rainbow,    ///< HSV-based rainbow (blue→cyan→green→yellow→red)
    Jet,        ///< Matlab-style jet
    CoolWarm,   ///< Blue→white→red diverging
    Grayscale   ///< Black→white
};

// ============================================================
// ColorMap
// ============================================================
class ColorMap {
public:
    explicit ColorMap(ColorMapType type = ColorMapType::Rainbow);

    // ----------------------------------------------------------------
    // Range control
    // ----------------------------------------------------------------

    /**
     * @brief Fix the mapping range [vmin, vmax] for all subsequent map() calls
     *
     * Use this before rendering frames of an animation to keep color
     * scale consistent across time steps.
     */
    void setRange(double vmin, double vmax);

    /**
     * @brief Automatically set range from a dataset
     *
     * Scans the values array and sets [min, max] as the range.
     * Falls back to [0, 1] if all values are equal.
     */
    void setAutoRange(const double* values, int count);

    /**
     * @brief Set range using a global [vmin, vmax] collected from all frames
     *
     * Identical to setRange() — provided for clarity at call-site.
     */
    void setGlobalRange(double vmin, double vmax);

    // ----------------------------------------------------------------
    // Mapping
    // ----------------------------------------------------------------

    /**
     * @brief Map a scalar value to an RGBA color
     *
     * Values outside [vmin_, vmax_] are clamped to the endpoints.
     */
    RGBA map(double value) const;

    /**
     * @brief Deterministic categorical color for a part_id
     *
     * Used for background parts rendered in flat per-part color.
     * Returns a distinct, visually pleasant color from a fixed palette.
     * Alpha is always 255.
     */
    static RGBA partColor(int32_t part_id);

    // ----------------------------------------------------------------
    // Accessors
    // ----------------------------------------------------------------

    double vmin() const { return vmin_; }
    double vmax() const { return vmax_; }
    ColorMapType type() const { return type_; }

    /** Parse colormap name from string (case-insensitive) */
    static ColorMapType parseType(const std::string& name);

private:
    ColorMapType type_;
    double vmin_ = 0.0;
    double vmax_ = 1.0;

    RGBA mapRainbow  (double t) const;
    RGBA mapJet      (double t) const;
    RGBA mapCoolWarm (double t) const;
    RGBA mapGrayscale(double t) const;

    static uint8_t clamp255(double v);
};

} // namespace section_render
} // namespace kood3plot
