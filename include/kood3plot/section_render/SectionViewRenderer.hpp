#pragma once
/**
 * @file SectionViewRenderer.hpp
 * @brief Top-level orchestrator for software section view rendering
 *
 * Drives the full pipeline:
 *   1. Build SectionPlane from config
 *   2. Compute camera from target-part bounding box (state 0)
 *   3. [Optional] 2-pass global-range scan (if config.global_range == true)
 *   4. Per-frame loop:
 *        a. NodalAverager::compute()
 *        b. SectionClipper::clip()
 *        c. SoftwareRasterizer::clear()
 *           drawPolygonFlat()  for background polygons
 *           drawPolygonContour() / drawEdge() for target polygons
 *        d. downsample() → PNG frame
 *   5. [Optional] Assemble MP4 via ffmpeg subprocess
 *
 * Single public entry point: render(reader, config)
 */

#include "kood3plot/section_render/SectionViewConfig.hpp"
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/data/StateData.hpp"
#include "kood3plot/data/ControlData.hpp"
#include <string>
#include <vector>

namespace kood3plot {
namespace section_render {

class SectionViewRenderer {
public:
    SectionViewRenderer() = default;

    /**
     * @brief Run the full rendering pipeline
     *
     * @param reader  An already-opened D3plotReader (open() must have returned OK)
     * @param config  Rendering configuration
     * @return        Error message, or empty string on success
     */
    std::string render(D3plotReader& reader, const SectionViewConfig& config);

    /**
     * @brief Run the full rendering pipeline with pre-loaded state data
     *
     * Avoids re-reading d3plot states — uses the already-loaded data directly.
     * No copies: all states are accessed by const reference.
     *
     * @param mesh        Pre-loaded mesh
     * @param ctrl        Pre-loaded control data
     * @param all_states  Pre-loaded state data (shared, not copied)
     * @param config      Rendering configuration
     * @return            Error message, or empty string on success
     */
    std::string render(const data::Mesh& mesh,
                       const data::ControlData& ctrl,
                       const std::vector<data::StateData>& all_states,
                       const SectionViewConfig& config);

private:
    // Sub-steps (all return error string or "")
    std::string writePng(const std::vector<uint8_t>& rgba,
                          int32_t width, int32_t height,
                          const std::string& filepath);

    std::string assembleMp4(const std::string& frame_pattern,
                             const std::string& output_path,
                             int32_t fps);
};

} // namespace section_render
} // namespace kood3plot
