/**
 * @file SectionViewRenderer.cpp
 * @brief Top-level section view rendering pipeline (full implementation)
 *
 * Pipeline:
 *   1. Build plane, NodalAverager, SectionClipper, SoftwareRasterizer
 *   2. Camera setup from state 0 target polygons
 *   3. [Optional] 2-pass global range scan (mp4 mode)
 *   4. Per-state render loop: average → clip → rasterize → savePng
 *   5. [Optional] assembleMp4 via ffmpeg subprocess
 *
 * Two entry points:
 *   render(reader, config)              — reads mesh/states from reader (standalone)
 *   render(mesh, ctrl, all_states, config) — uses pre-loaded data (zero-copy shared)
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
#include <unordered_map>
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
        box.min_pt = {-1,-1,-1};
        box.max_pt = {1,1,1};
    }
    return box;
}

} // anonymous namespace

// ============================================================
// render() — reader-based (standalone, reads states internally)
// ============================================================

std::string SectionViewRenderer::render(D3plotReader& reader,
                                         const SectionViewConfig& config)
{
    // Read mesh + control once
    data::Mesh mesh = reader.read_mesh();
    const data::ControlData& ctrl = reader.get_control_data();

    size_t num_states = reader.get_num_states();
    if (num_states == 0) return "No states in d3plot file";

    // Read all states (uses internal cache — no double disk I/O)
    std::vector<data::StateData> all_states;
    all_states.reserve(num_states);
    for (size_t si = 0; si < num_states; ++si)
        all_states.push_back(reader.read_state(si));

    return render(mesh, ctrl, all_states, config);
}

// ============================================================
// render() — pre-loaded state data (zero-copy, shared across jobs)
// ============================================================

std::string SectionViewRenderer::render(const data::Mesh& mesh,
                                         const data::ControlData& ctrl,
                                         const std::vector<data::StateData>& all_states,
                                         const SectionViewConfig& config)
{
    size_t num_states = all_states.size();
    if (num_states == 0) return "No states in d3plot file";

    // ---- 1. Build plane (auto_center: move cut point to target/mesh centroid axis) ----
    Vec3 plane_point = config.point;
    if (config.auto_center && !mesh.nodes.empty()) {
        double xmin = 1e300, xmax = -1e300;
        double ymin = 1e300, ymax = -1e300;
        double zmin = 1e300, zmax = -1e300;

        // If target_parts has specific IDs, compute AABB from target part nodes only
        bool use_target_bbox = config.target_parts.hasSpecificIds();
        if (use_target_bbox) {
            // Build node-id → index map (same as SectionClipper)
            std::unordered_map<int32_t, int32_t> nid_to_idx;
            if (!mesh.real_node_ids.empty()) {
                for (int32_t i = 0; i < static_cast<int32_t>(mesh.real_node_ids.size()); ++i)
                    nid_to_idx[mesh.real_node_ids[i]] = i;
            }
            auto resolveIdx = [&](int32_t nid) -> int32_t {
                if (!nid_to_idx.empty()) {
                    auto it = nid_to_idx.find(nid);
                    return (it != nid_to_idx.end()) ? it->second : -1;
                }
                return nid - 1;  // 1-based fallback
            };

            // Collect node positions from target part elements
            auto expandNode = [&](int32_t nid) {
                int32_t idx = resolveIdx(nid);
                if (idx >= 0 && idx < static_cast<int32_t>(mesh.nodes.size())) {
                    const auto& nd = mesh.nodes[idx];
                    xmin = std::min(xmin, nd.x); xmax = std::max(xmax, nd.x);
                    ymin = std::min(ymin, nd.y); ymax = std::max(ymax, nd.y);
                    zmin = std::min(zmin, nd.z); zmax = std::max(zmax, nd.z);
                }
            };

            bool found_any = false;
            // Solids
            for (size_t ei = 0; ei < mesh.solids.size(); ++ei) {
                int32_t pid = (ei < mesh.solid_parts.size()) ? mesh.solid_parts[ei] : 0;
                if (!config.target_parts.matches(pid)) continue;
                found_any = true;
                for (int32_t nid : mesh.solids[ei].node_ids) expandNode(nid);
            }
            // Thick shells
            for (size_t ei = 0; ei < mesh.thick_shells.size(); ++ei) {
                int32_t pid = (ei < mesh.thick_shell_parts.size()) ? mesh.thick_shell_parts[ei] : 0;
                if (!config.target_parts.matches(pid)) continue;
                found_any = true;
                for (int32_t nid : mesh.thick_shells[ei].node_ids) expandNode(nid);
            }
            // Shells
            for (size_t ei = 0; ei < mesh.shells.size(); ++ei) {
                int32_t pid = (ei < mesh.shell_parts.size()) ? mesh.shell_parts[ei] : 0;
                if (!config.target_parts.matches(pid)) continue;
                found_any = true;
                for (int32_t nid : mesh.shells[ei].node_ids) expandNode(nid);
            }

            if (found_any) {
                std::fprintf(stderr, "[section_view] auto_center: target part AABB = (%.3f..%.3f, %.3f..%.3f, %.3f..%.3f)\n",
                             xmin, xmax, ymin, ymax, zmin, zmax);
            } else {
                use_target_bbox = false;  // fallback to full mesh
            }
        }

        if (!use_target_bbox) {
            for (const auto& nd : mesh.nodes) {
                xmin = std::min(xmin, nd.x); xmax = std::max(xmax, nd.x);
                ymin = std::min(ymin, nd.y); ymax = std::max(ymax, nd.y);
                zmin = std::min(zmin, nd.z); zmax = std::max(zmax, nd.z);
            }
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
        std::fprintf(stderr, "[section_view] auto_center: %s center = (%.3f, %.3f, %.3f)\n",
                     use_target_bbox ? "target" : "mesh AABB",  cx, cy, cz);
        std::fprintf(stderr, "[section_view] auto_center: cut point = (%.3f, %.3f, %.3f)\n",
                     plane_point.x, plane_point.y, plane_point.z);
    }
    SectionPlane plane = config.use_axis
        ? SectionPlane::fromAxis(config.axis, plane_point)
        : SectionPlane::fromNormal(config.normal, plane_point);

    // ---- 2. Create output directory ----
    std::string out_dir = config.output_dir;
    try { fs::create_directories(out_dir); }
    catch (const std::exception& e) {
        return std::string("Cannot create output directory: ") + e.what();
    }

    // ---- 3. Auto-slab: compute average edge length near cutting plane ----
    double effective_slab = config.slab_thickness;
    double effective_fade = config.fade_distance;
    if (config.auto_slab && config.slab_thickness == 0.0) {
        const auto& state0 = all_states[0];
        double sum_edge = 0.0;
        int    count = 0;
        for (size_t ei = 0; ei < mesh.solids.size(); ++ei) {
            int32_t pid = (ei < mesh.solid_parts.size()) ? mesh.solid_parts[ei] : 0;
            if (!config.target_parts.empty() && !config.target_parts.matches(pid, ""))
                continue;
            const auto& nids = mesh.solids[ei].node_ids;
            int32_t uniq[8]; int nn = 0;
            for (int i = 0; i < static_cast<int>(std::min(nids.size(), size_t(8))); ++i) {
                bool dup = false;
                for (int j = 0; j < nn; ++j) { if (nids[i] == uniq[j]) { dup = true; break; } }
                if (!dup && nn < 8) uniq[nn++] = nids[i];
            }
            if (nn < 4) continue;

            Vec3 positions[8];
            for (int i = 0; i < nn; ++i) {
                int32_t ni = -1;
                if (!mesh.real_node_ids.empty()) {
                    for (size_t k = 0; k < mesh.real_node_ids.size(); ++k) {
                        if (mesh.real_node_ids[k] == uniq[i]) { ni = static_cast<int32_t>(k); break; }
                    }
                } else {
                    ni = uniq[i] - 1;
                }
                if (ni < 0 || ni >= static_cast<int32_t>(mesh.nodes.size())) continue;
                const auto& nd = mesh.nodes[ni];
                double dx = (ni < static_cast<int32_t>(state0.node_displacements.size()/3))
                    ? state0.node_displacements[ni*3+0] : 0.0;
                double dy = (ni < static_cast<int32_t>(state0.node_displacements.size()/3))
                    ? state0.node_displacements[ni*3+1] : 0.0;
                double dz = (ni < static_cast<int32_t>(state0.node_displacements.size()/3))
                    ? state0.node_displacements[ni*3+2] : 0.0;
                positions[i] = {nd.x + dx, nd.y + dy, nd.z + dz};
            }
            for (int i = 0; i < nn && i < 4; ++i) {
                for (int j = i+1; j < nn && j < 4; ++j) {
                    double ex = positions[i].x - positions[j].x;
                    double ey = positions[i].y - positions[j].y;
                    double ez = positions[i].z - positions[j].z;
                    double elen = std::sqrt(ex*ex + ey*ey + ez*ez);
                    if (elen > 1e-12) { sum_edge += elen; ++count; }
                }
            }
            if (count > 200) break;
        }
        if (count > 0) {
            double avg_edge = sum_edge / count;
            effective_slab = 0.5 * avg_edge;
            if (effective_fade == 0.0) {
                effective_fade = avg_edge;
            }
            std::fprintf(stderr, "[section_view] auto_slab: avg_edge=%.4f  slab=%.4f  fade=%.4f\n",
                         avg_edge, effective_slab, effective_fade);
        }
    }

    // ---- 4. Build pipeline objects ----
    NodalAverager     averager(mesh, ctrl);
    SectionClipper    clipper(mesh, ctrl, plane, effective_slab);
    SoftwareRasterizer rasterizer(config.width, config.height, config.supersampling);
    SectionCamera     camera;
    ColorMap          cmap(config.colormap);

    // ---- 5. Camera setup: use state 0 ----
    {
        const auto& state0 = all_states[0];
        averager.compute(state0, config.field, config.target_parts);

        std::vector<ClipPolygon> tgt0, bg0;
        std::vector<float> bg0_alphas;
        clipper.clip(state0, averager, config.target_parts, config.background_parts,
                     tgt0, bg0, bg0_alphas);

        AABB3 tgt_bbox = tgt0.empty() ? computeBbox(bg0) : computeBbox(tgt0);
        Vec3 tgt_center = tgt_bbox.center();

        // Compute full model bbox (target + background) for clamping
        AABB3 full_bbox = tgt_bbox;
        if (!bg0.empty()) {
            AABB3 bg_bbox = computeBbox(bg0);
            full_bbox.expand(bg_bbox.min_pt);
            full_bbox.expand(bg_bbox.max_pt);
        }

        // Target bbox half-extents × scale_factor
        Vec3 tgt_half = {
            (tgt_bbox.max_pt.x - tgt_bbox.min_pt.x) * 0.5 * config.scale_factor,
            (tgt_bbox.max_pt.y - tgt_bbox.min_pt.y) * 0.5 * config.scale_factor,
            (tgt_bbox.max_pt.z - tgt_bbox.min_pt.z) * 0.5 * config.scale_factor
        };

        // Full model half-extents × 1.2 margin
        Vec3 full_half = {
            (full_bbox.max_pt.x - full_bbox.min_pt.x) * 0.5 * 1.2,
            (full_bbox.max_pt.y - full_bbox.min_pt.y) * 0.5 * 1.2,
            (full_bbox.max_pt.z - full_bbox.min_pt.z) * 0.5 * 1.2
        };

        // Clamp each axis: use min(target×scale, full×1.2)
        // Always centered on target, never on full model
        Vec3 view_half = {
            std::min(tgt_half.x, full_half.x),
            std::min(tgt_half.y, full_half.y),
            std::min(tgt_half.z, full_half.z)
        };

        AABB3 view_bbox;
        view_bbox.min_pt = {tgt_center.x - view_half.x, tgt_center.y - view_half.y, tgt_center.z - view_half.z};
        view_bbox.max_pt = {tgt_center.x + view_half.x, tgt_center.y + view_half.y, tgt_center.z + view_half.z};

        camera.setup(plane, view_bbox, 1.0, config.width, config.height);
    }

    // ---- 6. Global range scan ----
    if (config.global_range) {
        double gmin = 1e300, gmax = -1e300;
        for (size_t si = 0; si < num_states; ++si) {
            averager.compute(all_states[si], config.field, config.target_parts);
            double lo = averager.globalMin(), hi = averager.globalMax();
            if (lo < gmin) gmin = lo;
            if (hi > gmax) gmax = hi;
        }
        cmap.setGlobalRange(gmin, gmax);
    }

    // ---- 7. Per-state render loop ----
    std::string frame_pattern = out_dir + "/frame_%04d.png";

    for (size_t si = 0; si < num_states; ++si) {
        const auto& state = all_states[si];

        averager.compute(state, config.field, config.target_parts);

        if (!config.global_range) {
            cmap.setRange(averager.globalMin(), averager.globalMax());
        }

        std::vector<ClipPolygon> tgt_polys, bg_polys;
        std::vector<float> bg_alphas, tgt_alphas;
        clipper.clip(state, averager,
                     config.target_parts, config.background_parts,
                     tgt_polys, bg_polys, bg_alphas,
                     effective_fade,
                     &tgt_alphas);

        rasterizer.clear({255, 255, 255, 255});

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

        for (size_t ti = 0; ti < tgt_polys.size(); ++ti) {
            const auto& poly = tgt_polys[ti];
            float alpha = (ti < tgt_alphas.size()) ? tgt_alphas[ti] : 1.0f;
            if (poly.size() >= 3) {
                if (alpha >= 1.0f) {
                    rasterizer.drawPolygonContour(poly, cmap, camera);
                } else {
                    rasterizer.drawPolygonContourAlpha(poly, cmap, camera, alpha);
                }
            } else if (poly.size() == 2) {
                rasterizer.drawEdge(poly, cmap, camera, 2);
            }
        }

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

    // ---- 9. Clean up frame PNGs unless png_frames is requested ----
    if (!config.png_frames) {
        namespace fs = std::filesystem;
        for (const auto& entry : fs::directory_iterator(out_dir)) {
            if (entry.path().extension() == ".png") {
                const std::string fname = entry.path().filename().string();
                if (fname.substr(0, 6) == "frame_") {
                    fs::remove(entry.path());
                }
            }
        }
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
    std::ostringstream cmd;
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
    return "";
}

} // namespace section_render
} // namespace kood3plot
