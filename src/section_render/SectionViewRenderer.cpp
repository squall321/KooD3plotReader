/**
 * @file SectionViewRenderer.cpp
 * @brief Top-level section view rendering pipeline (full implementation)
 *
 * Pipeline:
 *   1. read_mesh() + get_control_data()
 *   2. Build plane, NodalAverager, SectionClipper, SoftwareRasterizer
 *   3. Camera setup from state 0 target polygons
 *   4. [Optional] 2-pass global range scan (mp4 mode)
 *   5. Per-state render loop: average → clip → rasterize → savePng
 *   6. [Optional] assembleMp4 via ffmpeg subprocess
 */

#include "kood3plot/section_render/SectionViewRenderer.hpp"
#include "kood3plot/section_render/NodalAverager.hpp"
#include "kood3plot/section_render/SectionClipper.hpp"
#include "kood3plot/section_render/SectionCamera.hpp"
#include "kood3plot/section_render/SoftwareRasterizer.hpp"
#include "kood3plot/section_render/ColorMap.hpp"

#include <algorithm>
#include <cstdio>
#include <filesystem>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace fs = std::filesystem;

namespace kood3plot {
namespace section_render {

// ============================================================
// Helpers
// ============================================================

namespace {

/// Format frame index as zero-padded string (e.g. 0042)
std::string frameName(int idx, int total)
{
    int width = 4;
    if (total > 9999) width = 6;
    std::ostringstream oss;
    oss << "frame_" << std::setw(width) << std::setfill('0') << idx << ".png";
    return oss.str();
}

/// Compute AABB from all ClipPolygon vertices in target_polys
AABB3 computeBbox(const std::vector<ClipPolygon>& polys)
{
    AABB3 box;
    bool first = true;
    for (const auto& poly : polys) {
        for (const auto& v : poly) {
            if (first) {
                box.min_pt = box.max_pt = v.position;
                first = false;
            } else {
                box.expand(v.position);
            }
        }
    }
    if (first) {
        // No polygons — degenerate box
        box.min_pt = {-1,-1,-1};
        box.max_pt = {1,1,1};
    }
    return box;
}

} // anonymous namespace

// ============================================================
// render()
// ============================================================

std::string SectionViewRenderer::render(D3plotReader& reader,
                                         const SectionViewConfig& config)
{
    // ---- 1. Read mesh + control ----
    data::Mesh mesh = reader.read_mesh();
    const data::ControlData& ctrl = reader.get_control_data();

    // ---- 2. Build plane (auto_center: move cut point to mesh centroid axis) ----
    Vec3 plane_point = config.point;
    if (config.auto_center && !mesh.nodes.empty()) {
        // Compute mesh AABB and use its center as the cut point
        double xmin = 1e300, xmax = -1e300;
        double ymin = 1e300, ymax = -1e300;
        double zmin = 1e300, zmax = -1e300;
        for (const auto& nd : mesh.nodes) {
            xmin = std::min(xmin, nd.x); xmax = std::max(xmax, nd.x);
            ymin = std::min(ymin, nd.y); ymax = std::max(ymax, nd.y);
            zmin = std::min(zmin, nd.z); zmax = std::max(zmax, nd.z);
        }
        double cx = (xmin + xmax) * 0.5;
        double cy = (ymin + ymax) * 0.5;
        double cz = (zmin + zmax) * 0.5;
        if (config.use_axis) {
            switch (config.axis) {
                case 'x': plane_point.x = cx; break;
                case 'y': plane_point.y = cy; break;
                default:  plane_point.z = cz; break;
            }
        } else {
            plane_point = {cx, cy, cz};
        }
        std::fprintf(stderr, "[section_view] auto_center: mesh AABB center = (%.3f, %.3f, %.3f)\n",
                     cx, cy, cz);
        std::fprintf(stderr, "[section_view] auto_center: cut point = (%.3f, %.3f, %.3f)\n",
                     plane_point.x, plane_point.y, plane_point.z);
    }
    SectionPlane plane = config.use_axis
        ? SectionPlane::fromAxis(config.axis, plane_point)
        : SectionPlane::fromNormal(config.normal, plane_point);

    size_t num_states = reader.get_num_states();
    if (num_states == 0) return "No states in d3plot file";

    // ---- 3. Create output directory ----
    std::string out_dir = config.output_dir;
    try { fs::create_directories(out_dir); }
    catch (const std::exception& e) {
        return std::string("Cannot create output directory: ") + e.what();
    }

    // ---- 4. Build pipeline objects ----
    NodalAverager     averager(mesh, ctrl);
    SectionClipper    clipper(mesh, ctrl, plane, config.slab_thickness);
    SoftwareRasterizer rasterizer(config.width, config.height, config.supersampling);
    SectionCamera     camera;
    ColorMap          cmap(config.colormap);

    // ---- 5. Camera setup: use state 0 ----
    {
        data::StateData state0 = reader.read_state(0);
        averager.compute(state0, config.field, config.target_parts);

        std::vector<ClipPolygon> tgt0, bg0;
        std::vector<float> bg0_alphas;
        clipper.clip(state0, averager, config.target_parts, config.background_parts,
                     tgt0, bg0, bg0_alphas);

        // Use target bbox; if target is empty fall back to background polys
        AABB3 bbox = tgt0.empty() ? computeBbox(bg0) : computeBbox(tgt0);
        camera.setup(plane, bbox, config.scale_factor, config.width, config.height);
    }

    // ---- 6. Global range scan (2-pass) ----
    if (config.global_range) {
        double gmin = 1e300, gmax = -1e300;
        for (size_t si = 0; si < num_states; ++si) {
            data::StateData st = reader.read_state(si);
            averager.compute(st, config.field, config.target_parts);
            double lo = averager.globalMin(), hi = averager.globalMax();
            if (lo < gmin) gmin = lo;
            if (hi > gmax) gmax = hi;
        }
        cmap.setGlobalRange(gmin, gmax);
    }

    // ---- 7. Per-state render loop ----
    std::string frame_pattern = out_dir + "/frame_%04d.png";  // for ffmpeg

    for (size_t si = 0; si < num_states; ++si) {
        data::StateData state = reader.read_state(si);

        // a) Nodal averaging
        averager.compute(state, config.field, config.target_parts);

        // b) Per-frame auto range (when not using global range)
        if (!config.global_range) {
            cmap.setRange(averager.globalMin(), averager.globalMax());
        }

        // c) Section clipping
        std::vector<ClipPolygon> tgt_polys, bg_polys;
        std::vector<float> bg_alphas;
        clipper.clip(state, averager,
                     config.target_parts, config.background_parts,
                     tgt_polys, bg_polys, bg_alphas,
                     config.fade_distance);

        // d) Rasterize
        rasterizer.clear({255, 255, 255, 255});  // white background

        // Background parts (flat categorical color per part, optional alpha fade)
        for (size_t bi = 0; bi < bg_polys.size(); ++bi) {
            const auto& poly = bg_polys[bi];
            float alpha = (bi < bg_alphas.size()) ? bg_alphas[bi] : 1.0f;
            int32_t pid = poly.empty() ? 0 : poly[0].part_id;
            RGBA pcol = ColorMap::partColor(pid);
            if (poly.size() >= 3) {
                rasterizer.drawPolygonFlat(poly, pcol, camera, alpha);
            } else if (poly.size() == 2) {
                rasterizer.drawEdgeFlat(poly, pcol, camera, 2);
            }
        }

        // Target parts (contour)
        for (const auto& poly : tgt_polys) {
            if (poly.size() >= 3) {
                rasterizer.drawPolygonContour(poly, cmap, camera);
            } else if (poly.size() == 2) {
                rasterizer.drawEdge(poly, cmap, camera, 2);
            }
        }

        // e) Save PNG frame
        std::string frame_path = out_dir + "/" + frameName(static_cast<int>(si),
                                                            static_cast<int>(num_states));
        std::string err = rasterizer.savePng(frame_path);
        if (!err.empty()) return "Frame " + std::to_string(si) + ": " + err;
    }

    // ---- 8. Assemble MP4 ----
    if (config.mp4) {
        std::string mp4_path = out_dir + "/section_view.mp4";
        std::string err = assembleMp4(frame_pattern, mp4_path, config.fps);
        if (!err.empty()) return err;
    }

    return "";  // success
}

// ============================================================
// assembleMp4
// ============================================================

std::string SectionViewRenderer::assembleMp4(const std::string& frame_pattern,
                                              const std::string& output_path,
                                              int32_t fps)
{
    // Determine frame count padding from the pattern
    std::ostringstream cmd;
    // drawtext watermark: bottom-right "Smart Twin Cluster"
    // fontsize ~2% of video height; shadow for visibility on any background
    cmd << "ffmpeg -y -framerate " << fps
        << " -i \"" << frame_pattern << "\""
        << " -vf \"drawtext=text='Smart Twin Cluster'"
        << ":fontsize=h/36"
        << ":fontcolor=white"
        << ":shadowcolor=black@0.6:shadowx=1:shadowy=1"
        << ":x=w-tw-12:y=h-th-10\""
        << " -c:v libx264 -pix_fmt yuv420p"
        << " -crf 18 -preset fast"
        << " \"" << output_path << "\""
        << " 2>&1";

    FILE* pipe = popen(cmd.str().c_str(), "r");
    if (!pipe) return "ffmpeg: popen failed";

    char buf[256];
    std::string ffout;
    while (fgets(buf, sizeof(buf), pipe))
        ffout += buf;

    int rc = pclose(pipe);
    if (rc != 0) return "ffmpeg failed (exit " + std::to_string(rc) + "): " + ffout;
    return "";
}

// ============================================================
// writePng (legacy — now delegated to SoftwareRasterizer::savePng)
// ============================================================

std::string SectionViewRenderer::writePng(const std::vector<uint8_t>& /*rgba*/,
                                           int32_t /*width*/,
                                           int32_t /*height*/,
                                           const std::string& /*filepath*/)
{
    // Kept for API compatibility — actual PNG writing done via
    // SoftwareRasterizer::savePng() directly in render().
    return "";
}

} // namespace section_render
} // namespace kood3plot
