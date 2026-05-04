#pragma once
/**
 * @file SectionViewConfig.hpp
 * @brief YAML-driven configuration for section view rendering
 *
 * Maps to the YAML block:
 * ```yaml
 * section_render:
 *   enabled: true
 *   plane:
 *     axis: z           # x | y | z  (mutually exclusive with normal:)
 *     # normal: [0.0, 0.0, 1.0]
 *     point: [0.0, 0.0, 0.0]
 *   target_parts:
 *     ids: [1, 2, 3]
 *     patterns: ["*battery*"]
 *     keywords: ["cell"]
 *   background_parts:
 *     ids: []
 *     patterns: ["*"]    # empty = show all non-target parts
 *   field: von_mises     # von_mises | eps | strain | displacement | pressure | max_shear
 *   colormap: fringe     # fringe | rainbow | jet | coolwarm | grayscale
 *   global_range: false  # true = 2-pass (collect global min/max first)
 *   scale_factor: 1.2    # viewport extent relative to target bbox
 *   supersampling: 2     # 1 or 2
 *   output:
 *     width: 1920
 *     height: 1080
 *     png_frames: true
 *     mp4: true
 *     fps: 24
 *     output_dir: "section_views"
 * ```
 */

#include "kood3plot/section_render/SectionPlane.hpp"
#include "kood3plot/section_render/PartMatcher.hpp"
#include "kood3plot/section_render/ColorMap.hpp"
#include "kood3plot/section_render/NodalAverager.hpp"  // FieldSelector
#include <string>

namespace kood3plot {
namespace section_render {

/** Section view rendering mode */
enum class SectionViewMode {
    Section2D,    ///< Default: 2D cross-section view (camera perpendicular to cut plane)
    Section3D,    ///< 3D half-model: isometric view with cut face + 3D exterior
    IsoSurface    ///< Iso view, no cut: target part = fringe contour, background = part color + alpha
};

struct SectionViewConfig {
    // View mode
    SectionViewMode view_mode = SectionViewMode::Section2D;   ///< "section" (default) or "section_3d"

    // Plane definition
    bool        use_axis    = true;       ///< true=axis-aligned, false=arbitrary normal
    char        axis        = 'z';        ///< 'x','y','z' (when use_axis==true)
    Vec3        normal      = {0,0,1};   ///< Custom normal (when use_axis==false)
    Vec3        point        = {0,0,0};   ///< A point on the plane
    bool        auto_center  = false;    ///< Auto-set cut point to mesh AABB center
    bool        auto_slab        = true; ///< Auto-compute slab_thickness from element edge lengths at state 0
    double      slab_thickness  = 0.0;  ///< Half-slab: nodes within ±slab_thickness/2 treated as on-plane (0=exact)
    double      fade_distance   = 0.0;  ///< Fade: near-plane elements get alpha 0→1 (0=disabled, applies to both target & background)

    // Part selection
    PartMatcher target_parts;
    PartMatcher background_parts;

    // Rendering settings
    FieldSelector field       = FieldSelector::VonMises;
    ColorMapType  colormap    = ColorMapType::Fringe;
    bool          global_range = true;   ///< true = consistent color scale (red=global max, blue=global min)
    double        scale_factor = 3.0;    ///< viewport extent relative to target bbox (clamped to full model)
    int32_t       supersampling = 2;

    // ── Sliding section (SW backend) ──
    // When sliding_view=true the renderer holds simulation time at
    // sliding_peak_time and instead steps the cut plane through the part along
    // the chosen axis, producing one frame per plane position. The result is a
    // "frozen-time, plane sweeps the part" animation that mirrors the
    // LSPrePost iso sliding pipeline.
    bool        sliding_view        = false;  ///< master toggle for sliding mode
    int32_t     sliding_steps       = 20;     ///< number of plane positions
    double      sliding_peak_time   = -1.0;   ///< -1 = auto (last state)
    double      sliding_pad         = 0.05;   ///< padding fraction outside bbox
    int32_t     sliding_axis_sign   = 1;      ///< +1 or -1 (slide direction)

    // ── IsoSurface mode ──
    /// Background-part alpha when view_mode == IsoSurface. 1.0 = opaque,
    /// 0.0 = invisible. Default 0.3 (≈ 70% transparent).
    double      background_alpha    = 0.3;

    // Output settings
    int32_t     width       = 1920;
    int32_t     height      = 1080;
    bool        png_frames  = true;
    bool        mp4         = true;
    int32_t     fps         = 24;
    std::string output_dir  = "section_views";

    /**
     * @brief Build a SectionPlane from the plane definition fields
     */
    SectionPlane buildPlane() const;

    /**
     * @brief Load from a YAML string (hand-rolled parser, no yaml-cpp dependency)
     *
     * Parses the indented block that starts after "section_render:" in the config file.
     * Returns true on success.
     */
    bool loadFromString(const std::string& yaml_block);

    /**
     * @brief Load from a file (reads entire file, delegates to loadFromString)
     */
    bool loadFromFile(const std::string& filepath);

    /**
     * @brief Write example YAML to a stream (for --generate-config)
     */
    static std::string exampleYaml();

    /** @deprecated Use loadFromString with the void* = &std::string */
    bool loadFromYaml(const void* yaml_node);   // kept for API compat
};

} // namespace section_render
} // namespace kood3plot
