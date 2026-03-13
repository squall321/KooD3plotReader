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
 *   field: von_mises     # von_mises | eps | displacement | pressure | max_shear
 *   colormap: rainbow    # rainbow | jet | coolwarm | grayscale
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

struct SectionViewConfig {
    // Plane definition
    bool        use_axis    = true;       ///< true=axis-aligned, false=arbitrary normal
    char        axis        = 'z';        ///< 'x','y','z' (when use_axis==true)
    Vec3        normal      = {0,0,1};   ///< Custom normal (when use_axis==false)
    Vec3        point        = {0,0,0};   ///< A point on the plane
    bool        auto_center  = false;    ///< Auto-set cut point to mesh AABB center
    double      slab_thickness  = 0.0;  ///< Half-slab: nodes within ±slab_thickness/2 treated as on-plane (0=exact)
    double      fade_distance   = 0.0;  ///< Background fade: non-target parts within this dist get alpha 0→1 (0=disabled)

    // Part selection
    PartMatcher target_parts;
    PartMatcher background_parts;

    // Rendering settings
    FieldSelector field       = FieldSelector::VonMises;
    ColorMapType  colormap    = ColorMapType::Rainbow;
    bool          global_range = true;   ///< true = consistent color scale (red=global max, blue=global min)
    double        scale_factor = 1.2;
    int32_t       supersampling = 2;

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
