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
#include <array>
#include <cstdio>
#include <filesystem>
#include <limits>
#include <map>
#include <set>
#include <unordered_map>
#include <iomanip>
#include <sstream>
#include <stdexcept>

// MSVC uses _popen/_pclose instead of popen/pclose
#ifdef _WIN32
#define popen  _popen
#define pclose _pclose
#endif

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
    // Dispatch to 3D pipeline if requested
    if (config.view_mode == SectionViewMode::Section3D) {
        return render3D(mesh, ctrl, all_states, config);
    }
    if (config.view_mode == SectionViewMode::IsoSurface) {
        return renderIsoSurface(mesh, ctrl, all_states, config);
    }

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
    AABB3 cached_view_bbox;  // also reused by sliding mode to keep view stable
    {
        const auto& state0 = all_states[0];
        averager.compute(state0, config.field, config.target_parts);

        std::vector<ClipPolygon> tgt0, bg0;
        std::vector<float> bg0_alphas;
        clipper.clip(state0, averager, config.target_parts, config.background_parts,
                     tgt0, bg0, bg0_alphas);

        AABB3 tgt_bbox = tgt0.empty() ? computeBbox(bg0) : computeBbox(tgt0);
        // For sliding we want the view to encompass the full target part along
        // the slide axis (tgt0 only contains polygons clipped at the initial
        // plane, which is too thin), so widen the bbox using the mesh nodes
        // of the target part along all axes.
        if (config.sliding_view) {
            // Re-derive target part AABB from mesh + state0 displacement
            std::unordered_map<int32_t, int32_t> nid_map;
            if (!mesh.real_node_ids.empty()) {
                for (int32_t i = 0; i < (int32_t)mesh.real_node_ids.size(); ++i)
                    nid_map[mesh.real_node_ids[i]] = i;
            }
            auto resolveNode = [&](int32_t nid) -> int32_t {
                if (!nid_map.empty()) {
                    auto it = nid_map.find(nid);
                    return (it != nid_map.end()) ? it->second : -1;
                }
                return nid - 1;
            };
            AABB3 tp{{1e300,1e300,1e300},{-1e300,-1e300,-1e300}};
            bool any = false;
            auto expand = [&](int32_t nid) {
                int32_t idx = resolveNode(nid);
                if (idx < 0 || idx >= (int32_t)mesh.nodes.size()) return;
                const auto& nd = mesh.nodes[idx];
                tp.expand({nd.x, nd.y, nd.z}); any = true;
            };
            for (size_t ei = 0; ei < mesh.solids.size(); ++ei) {
                int32_t pid = (ei < mesh.solid_parts.size()) ? mesh.solid_parts[ei] : 0;
                if (!config.target_parts.empty() && !config.target_parts.matches(pid))
                    continue;
                for (int32_t nid : mesh.solids[ei].node_ids) expand(nid);
            }
            for (size_t ei = 0; ei < mesh.shells.size(); ++ei) {
                int32_t pid = (ei < mesh.shell_parts.size()) ? mesh.shell_parts[ei] : 0;
                if (!config.target_parts.empty() && !config.target_parts.matches(pid))
                    continue;
                for (int32_t nid : mesh.shells[ei].node_ids) expand(nid);
            }
            if (any) tgt_bbox = tp;
        }
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
        cached_view_bbox = view_bbox;
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

    // ---- 7. Per-state OR per-plane-position render loop ----
    std::string frame_pattern = out_dir + "/frame_%04d.png";

    // Sliding mode setup: hold time at one state, sweep plane along axis.
    bool sliding = config.sliding_view && config.use_axis;
    int sliding_axis_idx = 0;
    double a_min = 0.0, a_max = 0.0;
    size_t sliding_state_idx = num_states - 1;
    int N_steps = static_cast<int>(num_states);

    if (sliding) {
        // Axis index
        sliding_axis_idx = (config.axis == 'x') ? 0 : (config.axis == 'y') ? 1 : 2;

        // Target part axis-range (re-compute, iterating only target-part nodes
        // when target_parts has explicit ids; otherwise full mesh).
        double mn = 1e300, mx = -1e300;
        bool use_tgt_bbox = config.target_parts.hasSpecificIds();
        std::unordered_map<int32_t, int32_t> nid_map;
        if (!mesh.real_node_ids.empty()) {
            for (int32_t i = 0; i < static_cast<int32_t>(mesh.real_node_ids.size()); ++i)
                nid_map[mesh.real_node_ids[i]] = i;
        }
        auto resolveNode = [&](int32_t nid) -> int32_t {
            if (!nid_map.empty()) {
                auto it = nid_map.find(nid);
                return (it != nid_map.end()) ? it->second : -1;
            }
            return nid - 1;
        };
        auto coord = [&](const auto& nd) -> double {
            return (sliding_axis_idx == 0) ? nd.x
                 : (sliding_axis_idx == 1) ? nd.y : nd.z;
        };
        auto expand = [&](int32_t nid) {
            int32_t idx = resolveNode(nid);
            if (idx >= 0 && idx < static_cast<int32_t>(mesh.nodes.size())) {
                double v = coord(mesh.nodes[idx]);
                if (v < mn) mn = v;
                if (v > mx) mx = v;
            }
        };
        if (use_tgt_bbox) {
            for (size_t ei = 0; ei < mesh.solids.size(); ++ei) {
                int32_t pid = (ei < mesh.solid_parts.size()) ? mesh.solid_parts[ei] : 0;
                if (!config.target_parts.matches(pid)) continue;
                for (int32_t nid : mesh.solids[ei].node_ids) expand(nid);
            }
            for (size_t ei = 0; ei < mesh.thick_shells.size(); ++ei) {
                int32_t pid = (ei < mesh.thick_shell_parts.size()) ? mesh.thick_shell_parts[ei] : 0;
                if (!config.target_parts.matches(pid)) continue;
                for (int32_t nid : mesh.thick_shells[ei].node_ids) expand(nid);
            }
            for (size_t ei = 0; ei < mesh.shells.size(); ++ei) {
                int32_t pid = (ei < mesh.shell_parts.size()) ? mesh.shell_parts[ei] : 0;
                if (!config.target_parts.matches(pid)) continue;
                for (int32_t nid : mesh.shells[ei].node_ids) expand(nid);
            }
        }
        if (mn > mx) {
            // Fallback: full mesh
            for (const auto& nd : mesh.nodes) {
                double v = coord(nd);
                if (v < mn) mn = v;
                if (v > mx) mx = v;
            }
        }
        double extent = mx - mn;
        double pad = config.sliding_pad * extent;
        a_min = mn - pad;
        a_max = mx + pad;

        // Peak state from sliding_peak_time
        if (config.sliding_peak_time < 0) {
            sliding_state_idx = (num_states > 1) ? (num_states - 1) : 0;
        } else {
            // Linear approximation: peak_time / total_sim_time × num_states
            double total = (num_states > 0)
                ? all_states[num_states - 1].time : 0.0;
            if (total > 0) {
                double frac = config.sliding_peak_time / total;
                if (frac < 0) frac = 0;
                if (frac > 1) frac = 1;
                sliding_state_idx = static_cast<size_t>(frac * (num_states - 1) + 0.5);
            }
        }
        N_steps = std::max(2, static_cast<int>(config.sliding_steps));

        std::fprintf(stderr,
            "[section_view] sliding: axis=%c sign=%d steps=%d range=[%.3f, %.3f] state=%zu/%zu\n",
            config.axis, config.sliding_axis_sign, N_steps,
            a_min, a_max, sliding_state_idx, num_states);
    }

    size_t loop_count = sliding ? static_cast<size_t>(N_steps) : num_states;

    for (size_t si = 0; si < loop_count; ++si) {
        const auto& state = sliding ? all_states[sliding_state_idx] : all_states[si];

        // For sliding: build a fresh clipper at the next plane position.
        std::unique_ptr<SectionClipper> sliding_clipper;
        SectionClipper* eff_clipper = &clipper;
        if (sliding) {
            double frac = (N_steps > 1) ? (double)si / (N_steps - 1) : 0.0;
            double pos = (config.sliding_axis_sign > 0)
                ? (a_max - frac * (a_max - a_min))
                : (a_min + frac * (a_max - a_min));
            Vec3 new_point = plane_point;
            if (sliding_axis_idx == 0)      new_point.x = pos;
            else if (sliding_axis_idx == 1) new_point.y = pos;
            else                             new_point.z = pos;
            SectionPlane sp_iter = SectionPlane::fromAxis(config.axis, new_point);
            sliding_clipper = std::make_unique<SectionClipper>(
                mesh, ctrl, sp_iter, effective_slab);
            eff_clipper = sliding_clipper.get();
            // Re-aim camera at the new plane so frame-to-frame view stays
            // consistent (no flicker from camera orientation drift).
            camera.setup(sp_iter, cached_view_bbox, 1.0,
                         config.width, config.height);
        }

        averager.compute(state, config.field, config.target_parts);

        if (!config.global_range) {
            cmap.setRange(averager.globalMin(), averager.globalMax());
        }

        std::vector<ClipPolygon> tgt_polys, bg_polys;
        std::vector<float> bg_alphas, tgt_alphas;
        eff_clipper->clip(state, averager,
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
                                                            static_cast<int>(loop_count));
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
// render3D — 3D half-model rendering pipeline
// ============================================================

namespace {

/// A pre-computed exterior face (triangle) for 3D rendering
struct ExtFace {
    int32_t node_idx[3];   ///< Internal 0-based node indices (triangle)
    int32_t part_id;       ///< Part ID
    bool    is_target;     ///< true=target part (contour), false=background (flat color)
    float   max_edge2_init = 0.f; ///< Largest edge length² in the INITIAL configuration
};

/// Build a canonical face key from 3 or 4 node indices (sorted) for deduplication
uint64_t faceKey3(int32_t a, int32_t b, int32_t c) {
    int32_t arr[3] = {a, b, c};
    if (arr[0] > arr[1]) std::swap(arr[0], arr[1]);
    if (arr[1] > arr[2]) std::swap(arr[1], arr[2]);
    if (arr[0] > arr[1]) std::swap(arr[0], arr[1]);
    return (uint64_t(arr[0]) << 40) | (uint64_t(arr[1]) << 20) | uint64_t(arr[2]);
}

/// Resolve element node reference to 0-based mesh.nodes index.
///
/// IMPORTANT: in d3plot binary, element node references (`elem.node_ids[n]`)
/// are 1-based INTERNAL INDICES into the mesh.nodes array — NOT real-IDs.
/// The NARBS section provides a separate map (real_id → internal_index)
/// used only when the caller starts from a user-supplied real ID. Element
/// arrays are already in internal-index form and only need the 1→0
/// adjustment.
///
/// Misusing real_node_ids here would silently re-route an element's nodes
/// onto whatever real-ID happened to equal the internal index — which is
/// exactly what produced the impactor-collapsed-onto-rubber bbox bug.
int32_t resolveNodeIdx(int32_t nid,
                       const std::unordered_map<int32_t, int32_t>& /*nid_to_idx*/)
{
    return nid - 1;
}

/// Get deformed node position.
/// `state.node_displacements` stores DELTAS from initial.
Vec3 deformedPos(int32_t idx,
                 const data::Mesh& mesh,
                 const data::StateData& state)
{
    const auto& nd = mesh.nodes[idx];
    double dx = 0, dy = 0, dz = 0;
    if (idx < static_cast<int32_t>(state.node_displacements.size()/3)) {
        dx = state.node_displacements[idx*3+0];
        dy = state.node_displacements[idx*3+1];
        dz = state.node_displacements[idx*3+2];
    }
    return {nd.x + dx, nd.y + dy, nd.z + dz};
}

// ---- Triangle-plane clipping ----
// Clips a triangle against the half-model cut plane.
// Keeps the portion where signedDistance <= threshold.
// Returns 0..2 output triangles (each with 3 vertices).
struct ClipVert {
    Vec3   pos;
    double scalar;   // interpolated nodal value (for target contour)
    int32_t node_idx; // original node index (-1 for interpolated)
};

/// Linearly interpolate between two clip vertices at parameter t
ClipVert lerpClipVert(const ClipVert& a, const ClipVert& b, double t) {
    return {
        {a.pos.x + t * (b.pos.x - a.pos.x),
         a.pos.y + t * (b.pos.y - a.pos.y),
         a.pos.z + t * (b.pos.z - a.pos.z)},
        a.scalar + t * (b.scalar - a.scalar),
        -1  // interpolated vertex
    };
}

/// Clip triangle by plane. Returns number of output triangles (0, 1, or 2).
/// out[] must have room for 6 ClipVert (2 triangles × 3 verts).
/// d0,d1,d2 = signedDistance(vertex) - threshold; negative = keep, positive = discard.
int clipTriByPlane(const ClipVert& v0, const ClipVert& v1, const ClipVert& v2,
                   double d0, double d1, double d2,
                   ClipVert out[6])
{
    // Count vertices inside (d <= 0)
    bool in0 = (d0 <= 0), in1 = (d1 <= 0), in2 = (d2 <= 0);
    int n_in = int(in0) + int(in1) + int(in2);

    if (n_in == 3) {
        // All inside — keep entire triangle
        out[0] = v0; out[1] = v1; out[2] = v2;
        return 1;
    }
    if (n_in == 0) {
        // All outside — discard
        return 0;
    }

    // Reorder so that the "lone" vertex comes first
    // Case: 1 inside, 2 outside → result is 1 triangle
    // Case: 2 inside, 1 outside → result is 2 triangles (quad)
    const ClipVert* verts[3] = {&v0, &v1, &v2};
    double dists[3] = {d0, d1, d2};
    bool ins[3] = {in0, in1, in2};

    if (n_in == 1) {
        // Rotate so that the inside vertex is at index 0
        int lone = in0 ? 0 : (in1 ? 1 : 2);
        const ClipVert& A = *verts[lone];
        const ClipVert& B = *verts[(lone+1)%3];
        const ClipVert& C = *verts[(lone+2)%3];
        double dA = dists[lone], dB = dists[(lone+1)%3], dC = dists[(lone+2)%3];

        // A is inside, B and C are outside
        double tAB = dA / (dA - dB);  // intersection A→B
        double tAC = dA / (dA - dC);  // intersection A→C
        ClipVert iAB = lerpClipVert(A, B, tAB);
        ClipVert iAC = lerpClipVert(A, C, tAC);

        out[0] = A; out[1] = iAB; out[2] = iAC;
        return 1;
    }

    // n_in == 2: one vertex outside
    {
        int lone = !ins[0] ? 0 : (!ins[1] ? 1 : 2);  // the outside vertex
        const ClipVert& A = *verts[lone];           // outside
        const ClipVert& B = *verts[(lone+1)%3];     // inside
        const ClipVert& C = *verts[(lone+2)%3];     // inside
        double dA = dists[lone], dB = dists[(lone+1)%3], dC = dists[(lone+2)%3];

        double tAB = dA / (dA - dB);
        double tAC = dA / (dA - dC);
        ClipVert iAB = lerpClipVert(A, B, tAB);
        ClipVert iAC = lerpClipVert(A, C, tAC);

        // Quad: B, C, iAC, iAB → 2 triangles
        out[0] = B;   out[1] = C;   out[2] = iAC;
        out[3] = B;   out[4] = iAC; out[5] = iAB;
        return 2;
    }
}

/// 20-color high-contrast palette for sequential part coloring
/// Reordered so adjacent indices are maximally distinct
static const RGBA g_part_palette[] = {
    { 31, 119, 180, 255},  //  0: blue
    {214,  39,  40, 255},  //  1: red
    { 44, 160,  44, 255},  //  2: green
    {255, 127,  14, 255},  //  3: orange
    {148, 103, 189, 255},  //  4: purple
    { 23, 190, 207, 255},  //  5: cyan
    {188, 189,  34, 255},  //  6: olive
    {227, 119, 194, 255},  //  7: pink
    {140,  86,  75, 255},  //  8: brown
    {127, 127, 127, 255},  //  9: gray
    {174, 199, 232, 255},  // 10: light blue
    {255, 152, 150, 255},  // 11: light red
    {152, 223, 138, 255},  // 12: light green
    {255, 187, 120, 255},  // 13: light orange
    {197, 176, 213, 255},  // 14: light purple
    {158, 218, 229, 255},  // 15: light cyan
    {219, 219, 141, 255},  // 16: light olive
    {247, 182, 210, 255},  // 17: light pink
    {196, 156, 148, 255},  // 18: light brown
    {199, 199, 199, 255},  // 19: light gray
};
constexpr int G_PART_PALETTE_SIZE = 20;

} // anonymous

std::string SectionViewRenderer::render3D(const data::Mesh& mesh,
                                           const data::ControlData& ctrl,
                                           const std::vector<data::StateData>& all_states,
                                           const SectionViewConfig& config)
{
    size_t num_states = all_states.size();
    if (num_states == 0) return "No states in d3plot file";

    // ---- 1. Build plane (same auto_center logic as 2D) ----
    Vec3 plane_point = config.point;
    if (config.auto_center && !mesh.nodes.empty()) {
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
        std::fprintf(stderr, "[section_3d] auto_center: cut point = (%.3f, %.3f, %.3f)\n",
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

    // ---- 3. Build node-ID-to-index mapping ----
    std::unordered_map<int32_t, int32_t> nid_to_idx;
    if (!mesh.real_node_ids.empty()) {
        for (int32_t i = 0; i < static_cast<int32_t>(mesh.real_node_ids.size()); ++i)
            nid_to_idx[mesh.real_node_ids[i]] = i;
    }

    // ---- 4. Extract exterior faces (solid hex → 6 quad faces → 12 triangles) ----
    // Face deduplication: exterior = face that appears exactly once
    std::unordered_map<uint64_t, int> face_count;  // key → count

    // Helper: register a quad face as 2 triangles
    struct QuadFace {
        int32_t ni[4];  // 0-based node indices
        int32_t part_id;
    };
    std::vector<QuadFace> all_quads;

    // Hex face definitions (same as SurfaceExtractor)
    static const int HEXA_FACES[6][4] = {
        {0,3,2,1}, {4,5,6,7}, {0,1,5,4}, {2,3,7,6}, {0,4,7,3}, {1,2,6,5}
    };

    // Process solid elements
    for (size_t ei = 0; ei < mesh.solids.size(); ++ei) {
        int32_t pid = (ei < mesh.solid_parts.size()) ? mesh.solid_parts[ei] : 0;
        const auto& nids = mesh.solids[ei].node_ids;
        int nn = static_cast<int>(nids.size());
        if (nn < 4) continue;

        // Resolve node indices
        int32_t ni[8] = {-1,-1,-1,-1,-1,-1,-1,-1};
        for (int i = 0; i < std::min(nn, 8); ++i)
            ni[i] = resolveNodeIdx(nids[i], nid_to_idx);

        if (nn >= 8) {
            // Hex8: 6 faces
            for (int f = 0; f < 6; ++f) {
                int32_t fn[4];
                for (int k = 0; k < 4; ++k) fn[k] = ni[HEXA_FACES[f][k]];
                if (fn[0] < 0 || fn[1] < 0 || fn[2] < 0 || fn[3] < 0) continue;

                // Two triangles: (0,1,2) and (0,2,3)
                uint64_t k1 = faceKey3(fn[0], fn[1], fn[2]);
                uint64_t k2 = faceKey3(fn[0], fn[2], fn[3]);
                face_count[k1]++;
                face_count[k2]++;

                all_quads.push_back({fn[0], fn[1], fn[2], fn[3], pid});
            }
        } else if (nn >= 4) {
            // Tet4/5/6: treat as 4 tri faces for tet, or degenerate hex
            // Tet: faces (0,2,1), (0,1,3), (1,2,3), (0,3,2)
            if (ni[4] < 0 || ni[4] == ni[3]) {
                // Tet4
                int32_t tet_faces[4][3] = {
                    {ni[0], ni[2], ni[1]},
                    {ni[0], ni[1], ni[3]},
                    {ni[1], ni[2], ni[3]},
                    {ni[0], ni[3], ni[2]}
                };
                for (int f = 0; f < 4; ++f) {
                    if (tet_faces[f][0] < 0) continue;
                    uint64_t k = faceKey3(tet_faces[f][0], tet_faces[f][1], tet_faces[f][2]);
                    face_count[k]++;
                    all_quads.push_back({tet_faces[f][0], tet_faces[f][1], tet_faces[f][2], -1, pid});
                }
            }
        }
    }

    // Process shell elements (always exterior)
    for (size_t ei = 0; ei < mesh.shells.size(); ++ei) {
        int32_t pid = (ei < mesh.shell_parts.size()) ? mesh.shell_parts[ei] : 0;
        const auto& nids = mesh.shells[ei].node_ids;
        int nn = static_cast<int>(nids.size());
        if (nn < 3) continue;

        int32_t ni[4] = {-1,-1,-1,-1};
        for (int i = 0; i < std::min(nn, 4); ++i)
            ni[i] = resolveNodeIdx(nids[i], nid_to_idx);

        // Shells are always exterior — mark count = 1 to keep them
        if (ni[3] >= 0 && ni[3] != ni[2]) {
            // Quad shell → 2 triangles
            all_quads.push_back({ni[0], ni[1], ni[2], ni[3], pid});
        } else {
            // Tri shell
            all_quads.push_back({ni[0], ni[1], ni[2], -1, pid});
        }
    }

    // Process thick shell elements (always exterior)
    for (size_t ei = 0; ei < mesh.thick_shells.size(); ++ei) {
        int32_t pid = (ei < mesh.thick_shell_parts.size()) ? mesh.thick_shell_parts[ei] : 0;
        const auto& nids = mesh.thick_shells[ei].node_ids;
        int nn = static_cast<int>(nids.size());
        if (nn < 8) continue;  // thick shells have 8 nodes (like hex)

        int32_t ni[8];
        for (int i = 0; i < 8; ++i)
            ni[i] = resolveNodeIdx(nids[i], nid_to_idx);

        for (int f = 0; f < 6; ++f) {
            int32_t fn[4];
            for (int k = 0; k < 4; ++k) fn[k] = ni[HEXA_FACES[f][k]];
            if (fn[0] < 0 || fn[1] < 0 || fn[2] < 0 || fn[3] < 0) continue;
            uint64_t k1 = faceKey3(fn[0], fn[1], fn[2]);
            uint64_t k2 = faceKey3(fn[0], fn[2], fn[3]);
            face_count[k1]++;
            face_count[k2]++;
            all_quads.push_back({fn[0], fn[1], fn[2], fn[3], pid});
        }
    }

    // Build exterior triangle list (faces appearing exactly once, or shells)
    std::vector<ExtFace> ext_faces;
    ext_faces.reserve(all_quads.size() * 2);

    // If target_parts is empty, ALL parts are targets (same convention as 2D mode)
    bool all_are_target = config.target_parts.empty();

    for (const auto& q : all_quads) {
        bool is_target = all_are_target || config.target_parts.matches(q.part_id);

        if (q.ni[3] >= 0) {
            // Quad → 2 triangles
            uint64_t k1 = faceKey3(q.ni[0], q.ni[1], q.ni[2]);
            uint64_t k2 = faceKey3(q.ni[0], q.ni[2], q.ni[3]);
            bool ext1 = (face_count.find(k1) != face_count.end()) ? (face_count[k1] <= 1) : true;
            bool ext2 = (face_count.find(k2) != face_count.end()) ? (face_count[k2] <= 1) : true;
            if (ext1) ext_faces.push_back({{q.ni[0], q.ni[1], q.ni[2]}, q.part_id, is_target});
            if (ext2) ext_faces.push_back({{q.ni[0], q.ni[2], q.ni[3]}, q.part_id, is_target});
        } else {
            // Triangle
            uint64_t k = faceKey3(q.ni[0], q.ni[1], q.ni[2]);
            bool ext = (face_count.find(k) != face_count.end()) ? (face_count[k] <= 1) : true;
            if (ext) ext_faces.push_back({{q.ni[0], q.ni[1], q.ni[2]}, q.part_id, is_target});
        }
    }

    std::fprintf(stderr, "[section_3d] Exterior faces: %zu triangles (from %zu quads)\n",
                 ext_faces.size(), all_quads.size());

    // ---- 4b. Build sequential part color mapping ----
    // Collect unique part IDs, sort, assign sequential palette index
    std::set<int32_t> unique_pids;
    for (const auto& f : ext_faces) unique_pids.insert(f.part_id);
    std::unordered_map<int32_t, int> part_color_map;
    {
        int cidx = 0;
        for (int32_t pid : unique_pids)
            part_color_map[pid] = cidx++;
    }
    std::fprintf(stderr, "[section_3d] Part color mapping: %zu unique parts\n",
                 unique_pids.size());

    // ---- 5. Auto-slab ----
    double effective_slab = config.slab_thickness;
    if (config.auto_slab && config.slab_thickness == 0.0) {
        const auto& state0 = all_states[0];
        double sum_edge = 0.0;
        int count = 0;
        for (size_t ei = 0; ei < mesh.solids.size() && count < 200; ++ei) {
            const auto& nids = mesh.solids[ei].node_ids;
            int nn = std::min(static_cast<int>(nids.size()), 4);
            Vec3 positions[4];
            for (int i = 0; i < nn; ++i) {
                int32_t idx = resolveNodeIdx(nids[i], nid_to_idx);
                if (idx >= 0 && idx < static_cast<int32_t>(mesh.nodes.size()))
                    positions[i] = deformedPos(idx, mesh, state0);
            }
            for (int i = 0; i < nn; ++i) {
                for (int j = i+1; j < nn; ++j) {
                    double elen = (positions[i] - positions[j]).magnitude();
                    if (elen > 1e-12) { sum_edge += elen; ++count; }
                }
            }
        }
        if (count > 0) {
            effective_slab = 0.5 * (sum_edge / count);
            std::fprintf(stderr, "[section_3d] auto_slab: slab=%.4f\n", effective_slab);
        }
    }

    // ---- 6. Build pipeline objects ----
    NodalAverager     averager(mesh, ctrl);
    SectionClipper    clipper(mesh, ctrl, plane, effective_slab);
    SoftwareRasterizer rasterizer(config.width, config.height, config.supersampling);
    SectionCamera     camera;
    ColorMap          cmap(config.colormap);

    // ---- 7. Camera setup: compute model AABB from state 0 (kept-side faces only) ----
    {
        const auto& state0 = all_states[0];
        AABB3 bbox;
        bool first = true;
        for (const auto& face : ext_faces) {
            for (int k = 0; k < 3; ++k) {
                Vec3 p = deformedPos(face.node_idx[k], mesh, state0);
                // Keep only faces on the NEGATIVE side (below cut plane)
                if (k == 0) {
                    Vec3 c = deformedPos(face.node_idx[0], mesh, state0);
                    Vec3 c1 = deformedPos(face.node_idx[1], mesh, state0);
                    Vec3 c2 = deformedPos(face.node_idx[2], mesh, state0);
                    Vec3 centroid = {(c.x + c1.x + c2.x) / 3.0,
                                     (c.y + c1.y + c2.y) / 3.0,
                                     (c.z + c1.z + c2.z) / 3.0};
                    if (plane.signedDistance(centroid) > 0) break;
                }
                if (first) { bbox.min_pt = bbox.max_pt = p; first = false; }
                else bbox.expand(p);
            }
        }
        if (first) {
            // Fallback to full mesh bbox
            for (const auto& nd : mesh.nodes) {
                Vec3 p = {nd.x, nd.y, nd.z};
                if (first) { bbox.min_pt = bbox.max_pt = p; first = false; }
                else bbox.expand(p);
            }
        }

        camera.setupIsometric(plane, bbox, config.scale_factor, config.width, config.height);
    }

    // ---- 8. Global range scan ----
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

    // Lighting constants — offset light gives good contrast
    const double ambient      = 0.2;   // For background parts (flat shaded)
    const double diffuse_k    = 0.8;
    const double ambient_tgt  = 0.3;   // Target contour: more diffuse range for visible shading
    const double diffuse_tgt  = 0.7;

    // ---- 9. Per-state render loop ----
    std::string frame_pattern = out_dir + "/frame_%04d.png";

    for (size_t si = 0; si < num_states; ++si) {
        const auto& state = all_states[si];

        // Compute nodal stress values for this state
        averager.compute(state, config.field, config.target_parts);
        if (!config.global_range)
            cmap.setRange(averager.globalMin(), averager.globalMax());

        // Clip to get cut face polygons
        std::vector<ClipPolygon> tgt_polys, bg_polys;
        std::vector<float> bg_alphas, tgt_alphas;
        clipper.clip(state, averager,
                     config.target_parts, config.background_parts,
                     tgt_polys, bg_polys, bg_alphas);

        rasterizer.clear({255, 255, 255, 255});
        rasterizer.enableDepthTest(true);

        // Lighting: offset from camera direction toward upper-right
        // This creates shadows on left/bottom-facing surfaces for depth perception
        Vec3 vd = camera.viewDirection();
        Vec3 ru = camera.axisU();   // right
        Vec3 up = camera.axisV();   // up
        Vec3 light_dir = (vd + ru * 0.4 + up * 0.6).normalized();

        // ---- 9a. Draw exterior faces with triangle-plane clipping ----
        // Also collect edge-adjacency data for crease/silhouette detection.
        struct EdgeRec { Vec3 normal; Vec3 wa, wb; };
        std::unordered_map<uint64_t, std::vector<EdgeRec>> crease_map;
        auto edgeKey64 = [](int32_t a, int32_t b) -> uint64_t {
            if (a > b) std::swap(a, b);
            return (uint64_t(uint32_t(a)) << 32) | uint64_t(uint32_t(b));
        };

        for (const auto& face : ext_faces) {
            Vec3 p0 = deformedPos(face.node_idx[0], mesh, state);
            Vec3 p1 = deformedPos(face.node_idx[1], mesh, state);
            Vec3 p2 = deformedPos(face.node_idx[2], mesh, state);

            double d0 = plane.signedDistance(p0) - effective_slab;
            double d1 = plane.signedDistance(p1) - effective_slab;
            double d2 = plane.signedDistance(p2) - effective_slab;
            if (d0 > 0 && d1 > 0 && d2 > 0) continue;

            double val0 = face.is_target ? averager.nodeValue(face.node_idx[0]) : 0.0;
            double val1 = face.is_target ? averager.nodeValue(face.node_idx[1]) : 0.0;
            double val2 = face.is_target ? averager.nodeValue(face.node_idx[2]) : 0.0;

            ClipVert cv0 = {p0, val0, face.node_idx[0]};
            ClipVert cv1 = {p1, val1, face.node_idx[1]};
            ClipVert cv2 = {p2, val2, face.node_idx[2]};

            ClipVert clipped[6];
            int n_tris = clipTriByPlane(cv0, cv1, cv2, d0, d1, d2, clipped);

            for (int ti = 0; ti < n_tris; ++ti) {
                const ClipVert& a = clipped[ti*3 + 0];
                const ClipVert& b = clipped[ti*3 + 1];
                const ClipVert& c = clipped[ti*3 + 2];

                Vec3 e1 = b.pos - a.pos;
                Vec3 e2 = c.pos - a.pos;
                Vec3 fn = e1.cross(e2).normalizedSafe();
                if (fn.dot(light_dir) < 0) fn = fn * -1.0;
                double ndotl = std::max(0.0, fn.dot(light_dir));

                double za, zb, zc;
                Vec2 sa = camera.project3D(a.pos, za);
                Vec2 sb = camera.project3D(b.pos, zb);
                Vec2 sc = camera.project3D(c.pos, zc);
                double ss = static_cast<double>(config.supersampling);
                sa.x *= ss; sa.y *= ss;
                sb.x *= ss; sb.y *= ss;
                sc.x *= ss; sc.y *= ss;

                if (face.is_target) {
                    double tgt_i = std::min(1.0, ambient_tgt + diffuse_tgt * ndotl);
                    RGBA ca = cmap.map(a.scalar);
                    RGBA cb = cmap.map(b.scalar);
                    RGBA cc = cmap.map(c.scalar);
                    ca.r = uint8_t(ca.r * tgt_i); ca.g = uint8_t(ca.g * tgt_i); ca.b = uint8_t(ca.b * tgt_i);
                    cb.r = uint8_t(cb.r * tgt_i); cb.g = uint8_t(cb.g * tgt_i); cb.b = uint8_t(cb.b * tgt_i);
                    cc.r = uint8_t(cc.r * tgt_i); cc.g = uint8_t(cc.g * tgt_i); cc.b = uint8_t(cc.b * tgt_i);
                    rasterizer.drawTriangle3DContour(sa.x, sa.y, za, ca,
                                                     sb.x, sb.y, zb, cb,
                                                     sc.x, sc.y, zc, cc);
                } else {
                    double bg_i = std::min(1.0, ambient + diffuse_k * ndotl);
                    int cidx = 0;
                    auto cit = part_color_map.find(face.part_id);
                    if (cit != part_color_map.end()) cidx = cit->second;
                    RGBA pcol = g_part_palette[cidx % G_PART_PALETTE_SIZE];
                    pcol.r = uint8_t(pcol.r * bg_i);
                    pcol.g = uint8_t(pcol.g * bg_i);
                    pcol.b = uint8_t(pcol.b * bg_i);
                    rasterizer.drawTriangle3D(sa.x, sa.y, za,
                                               sb.x, sb.y, zb,
                                               sc.x, sc.y, zc, pcol);
                }

                // Collect edges for crease detection (only original vertices, skip interpolated)
                const ClipVert* verts[3] = {&a, &b, &c};
                for (int ei = 0; ei < 3; ++ei) {
                    int32_t na = verts[ei]->node_idx;
                    int32_t nb = verts[(ei+1)%3]->node_idx;
                    if (na >= 0 && nb >= 0) {
                        uint64_t ek = edgeKey64(na, nb);
                        crease_map[ek].push_back({fn, verts[ei]->pos, verts[(ei+1)%3]->pos});
                    }
                }
            }
        }

        // ---- 9a'. Draw crease and silhouette edges ----
        {
            const double crease_cos = 0.707;  // ~45° dihedral angle threshold
            RGBA edge_color = {30, 30, 30, 255};
            double ss = static_cast<double>(config.supersampling);
            for (auto& [ek, recs] : crease_map) {
                if (recs.size() < 2) continue;  // skip boundary (clip artifacts)
                // Crease: large dihedral angle between adjacent faces
                double cos_a = recs[0].normal.dot(recs[1].normal);
                bool is_crease = (cos_a < crease_cos);
                // Silhouette: one face toward camera, one face away
                double d0 = recs[0].normal.dot(light_dir);
                double d1 = recs[1].normal.dot(light_dir);
                bool is_silhouette = (d0 * d1 < 0);
                if (!is_crease && !is_silhouette) continue;

                double za, zb;
                Vec2 sa = camera.project3D(recs[0].wa, za);
                Vec2 sb = camera.project3D(recs[0].wb, zb);
                sa.x *= ss; sa.y *= ss;
                sb.x *= ss; sb.y *= ss;
                rasterizer.drawLine3D(sa.x, sa.y, za, sb.x, sb.y, zb, edge_color, 1);
            }
        }

        // ---- 9b. Draw cut face polygons (from SectionClipper) ----
        // Target cut face: contour
        for (const auto& poly : tgt_polys) {
            if (poly.size() < 3) continue;
            // Fan triangulate from vertex 0
            for (size_t i = 1; i + 1 < poly.size(); ++i) {
                Vec3 pp0 = poly[0].position;
                Vec3 pp1 = poly[i].position;
                Vec3 pp2 = poly[i+1].position;

                double zz0, zz1, zz2;
                Vec2 ss0 = camera.project3D(pp0, zz0);
                Vec2 ss1 = camera.project3D(pp1, zz1);
                Vec2 ss2 = camera.project3D(pp2, zz2);

                double ss = static_cast<double>(config.supersampling);
                ss0.x *= ss; ss0.y *= ss;
                ss1.x *= ss; ss1.y *= ss;
                ss2.x *= ss; ss2.y *= ss;

                RGBA cc0 = cmap.map(poly[0].value);
                RGBA cc1 = cmap.map(poly[i].value);
                RGBA cc2 = cmap.map(poly[i+1].value);

                rasterizer.drawTriangle3DContour(
                    ss0.x, ss0.y, zz0, cc0,
                    ss1.x, ss1.y, zz1, cc1,
                    ss2.x, ss2.y, zz2, cc2);
            }
        }
        // Background cut face: flat part color (sequential palette)
        for (const auto& poly : bg_polys) {
            if (poly.size() < 3) continue;
            int32_t pid = poly[0].part_id;
            int cidx = 0;
            {
                auto cit = part_color_map.find(pid);
                if (cit != part_color_map.end()) cidx = cit->second;
            }
            RGBA pcol = g_part_palette[cidx % G_PART_PALETTE_SIZE];
            for (size_t i = 1; i + 1 < poly.size(); ++i) {
                Vec3 pp0 = poly[0].position;
                Vec3 pp1 = poly[i].position;
                Vec3 pp2 = poly[i+1].position;

                double zz0, zz1, zz2;
                Vec2 ss0 = camera.project3D(pp0, zz0);
                Vec2 ss1 = camera.project3D(pp1, zz1);
                Vec2 ss2 = camera.project3D(pp2, zz2);

                double ss = static_cast<double>(config.supersampling);
                ss0.x *= ss; ss0.y *= ss;
                ss1.x *= ss; ss1.y *= ss;
                ss2.x *= ss; ss2.y *= ss;

                rasterizer.drawTriangle3D(
                    ss0.x, ss0.y, zz0,
                    ss1.x, ss1.y, zz1,
                    ss2.x, ss2.y, zz2,
                    pcol);
            }
        }

        // Save frame
        std::string frame_path = out_dir + "/" + frameName(static_cast<int>(si),
                                                            static_cast<int>(num_states));
        std::string err = rasterizer.savePng(frame_path);
        if (!err.empty()) return "Frame " + std::to_string(si) + ": " + err;

        if (si % 20 == 0 || si == num_states - 1) {
            std::fprintf(stderr, "[section_3d] Rendered frame %zu / %zu\n", si + 1, num_states);
        }
    }

    // ---- 10. Assemble MP4 ----
    if (config.mp4) {
        std::string mp4_path = out_dir + "/section_view.mp4";
        std::string err = assembleMp4(frame_pattern, mp4_path, config.fps);
        if (!err.empty()) return err;
    }

    // ---- 11. Clean up frame PNGs ----
    if (!config.png_frames) {
        for (const auto& entry : fs::directory_iterator(out_dir)) {
            if (entry.path().extension() == ".png") {
                const std::string fname = entry.path().filename().string();
                if (fname.substr(0, 6) == "frame_") {
                    fs::remove(entry.path());
                }
            }
        }
    }

    return "";
}

// ============================================================
// renderIsoSurface — iso view, no cut, target = fringe / bg = alpha
// ============================================================

std::string SectionViewRenderer::renderIsoSurface(const data::Mesh& mesh,
                                                  const data::ControlData& ctrl,
                                                  const std::vector<data::StateData>& all_states,
                                                  const SectionViewConfig& config)
{
    size_t num_states = all_states.size();
    if (num_states == 0) return "No states in d3plot file";

    // Output directory
    std::string out_dir = config.output_dir;
    try { fs::create_directories(out_dir); }
    catch (const std::exception& e) {
        return std::string("Cannot create output directory: ") + e.what();
    }

    // Node real-ID → 0-based index. Same approach as render3D: when the d3plot
    // ships a real-id table (NARBS), node_ids in solids/shells are real IDs and
    // need a map lookup. Without this, the (nid - 1) fallback produces garbled
    // indices and a shattered mesh whenever real IDs aren't sequential 1..N.
    std::unordered_map<int32_t, int32_t> nid_to_idx;
    if (!mesh.real_node_ids.empty()) {
        for (int32_t i = 0; i < (int32_t)mesh.real_node_ids.size(); ++i)
            nid_to_idx[mesh.real_node_ids[i]] = i;
    }

    // ---- Robust 3D exterior face extraction ----
    //
    // Algorithm (per-element type):
    //   1. Detect actual element type from collapsed-node patterns:
    //        - tet4    : 4 unique nodes (last 4 hex slots collapsed to n3)
    //        - penta6  : 6 unique nodes (wedge, ni[4]==ni[5] OR ni[7]==ni[6])
    //        - pyr5    : 5 unique nodes (rare)
    //        - hex8    : 8 unique nodes
    //   2. Generate face list with WINDING preserved:
    //        - tet4   → 4 tri faces
    //        - penta6 → 2 tri caps + 3 quad sides
    //        - hex8   → 6 quad faces
    //   3. Dedup by SORTED-NODE-TUPLE key (3 nodes for tri, 4 for quad).
    //      Adjacent elements traverse a shared face in opposite cyclic order,
    //      so the SORTED tuple is the only stable, element-agnostic key.
    //      *Critical*: hex faces MUST be deduped at the QUAD level, not the
    //      triangle level — two hex cells sharing a quad face may pick
    //      different diagonals when triangulating, so triangle hashes won't
    //      match and phantom interior triangles leak through. This was the
    //      root cause of the prior "spike" artifacts in iso surface mode.
    //   4. Triangulate exterior quads with the 0→2 diagonal (canonical).

    // Pending face record: stored in vectors during element traversal so we
    // know which faces to triangulate after dedup.
    struct PendingTri  { int32_t a, b, c;          int32_t part_id; };
    struct PendingQuad { int32_t a, b, c, d;       int32_t part_id; };
    std::vector<PendingTri>  pending_tris;
    std::vector<PendingQuad> pending_quads;

    auto sortedTri = [](int32_t a, int32_t b, int32_t c) {
        std::array<int32_t, 3> k{a, b, c};
        std::sort(k.begin(), k.end());
        return k;
    };
    auto sortedQuad = [](int32_t a, int32_t b, int32_t c, int32_t d) {
        std::array<int32_t, 4> k{a, b, c, d};
        std::sort(k.begin(), k.end());
        return k;
    };
    struct ArrHash3 {
        size_t operator()(const std::array<int32_t, 3>& k) const noexcept {
            uint64_t h = uint64_t(uint32_t(k[0])) * 0x9E3779B185EBCA87ULL;
            h ^= uint64_t(uint32_t(k[1])) + 0xC2B2AE3D27D4EB4FULL + (h << 6) + (h >> 2);
            h ^= uint64_t(uint32_t(k[2])) + 0x165667B19E3779F9ULL + (h << 6) + (h >> 2);
            return size_t(h);
        }
    };
    struct ArrHash4 {
        size_t operator()(const std::array<int32_t, 4>& k) const noexcept {
            uint64_t h = uint64_t(uint32_t(k[0])) * 0x9E3779B185EBCA87ULL;
            h ^= uint64_t(uint32_t(k[1])) + 0xC2B2AE3D27D4EB4FULL + (h << 6) + (h >> 2);
            h ^= uint64_t(uint32_t(k[2])) + 0x165667B19E3779F9ULL + (h << 6) + (h >> 2);
            h ^= uint64_t(uint32_t(k[3])) + 0x85EBCA77C2B2AE3DULL + (h << 6) + (h >> 2);
            return size_t(h);
        }
    };
    std::unordered_map<std::array<int32_t, 3>, int, ArrHash3> tri_count;
    std::unordered_map<std::array<int32_t, 4>, int, ArrHash4> quad_count;

    auto distinct3 = [](int32_t a, int32_t b, int32_t c) {
        return a >= 0 && b >= 0 && c >= 0 && a != b && b != c && a != c;
    };
    auto distinct4 = [](int32_t a, int32_t b, int32_t c, int32_t d) {
        return a >= 0 && b >= 0 && c >= 0 && d >= 0
            && a != b && a != c && a != d
            && b != c && b != d && c != d;
    };

    auto pushTri = [&](int32_t a, int32_t b, int32_t c, int32_t pid) {
        if (!distinct3(a, b, c)) return;
        tri_count[sortedTri(a, b, c)]++;
        pending_tris.push_back({a, b, c, pid});
    };
    auto pushQuad = [&](int32_t a, int32_t b, int32_t c, int32_t d, int32_t pid) {
        if (!distinct4(a, b, c, d)) {
            // Quad collapsed to triangle — push as triangle instead.
            // Find the duplicated vertex and emit the surviving triangle.
            int32_t v[4] = {a, b, c, d};
            for (int i = 0; i < 4; ++i) {
                int32_t out[3], k = 0;
                for (int j = 0; j < 4; ++j) if (j != i) out[k++] = v[j];
                if (distinct3(out[0], out[1], out[2])) {
                    pushTri(out[0], out[1], out[2], pid);
                    return;
                }
            }
            return;
        }
        quad_count[sortedQuad(a, b, c, d)]++;
        pending_quads.push_back({a, b, c, d, pid});
    };

    // Standard LS-DYNA hex8 face winding (outward normals):
    // node ordering (LS-DYNA right-hand convention):
    //
    //       7-------6
    //      /|      /|
    //     / |     / |
    //    4-------5  |
    //    |  3----|--2
    //    | /     | /
    //    |/      |/
    //    0-------1
    static const int HEXA_FACES[6][4] = {
        {0, 3, 2, 1},  // bottom (z-)
        {4, 5, 6, 7},  // top    (z+)
        {0, 1, 5, 4},  // front  (y-)
        {2, 3, 7, 6},  // back   (y+)
        {0, 4, 7, 3},  // left   (x-)
        {1, 2, 6, 5}   // right  (x+)
    };

    int n_tet = 0, n_penta = 0, n_pyr = 0, n_hex = 0, n_other = 0;

    for (size_t ei = 0; ei < mesh.solids.size(); ++ei) {
        int32_t pid = (ei < mesh.solid_parts.size()) ? mesh.solid_parts[ei] : 0;
        const auto& nids = mesh.solids[ei].node_ids;
        int nn = (int)nids.size();
        if (nn < 4) continue;
        int32_t ni[8] = {-1, -1, -1, -1, -1, -1, -1, -1};
        for (int i = 0; i < std::min(nn, 8); ++i)
            ni[i] = resolveNodeIdx(nids[i], nid_to_idx);

        // Count unique node indices to classify the actual element type.
        // D3plot stores all solids in 8-node slots and pads degenerate
        // elements by repeating nodes (tet4 / penta6 / pyr5).
        if (nn < 8) {
            // Standalone tet4 storage (rare; some readers truncate).
            if (nn == 4 && distinct4(ni[0], ni[1], ni[2], ni[3])) {
                n_tet++;
                pushTri(ni[0], ni[2], ni[1], pid);  // base (opposite n3)
                pushTri(ni[0], ni[1], ni[3], pid);
                pushTri(ni[1], ni[2], ni[3], pid);
                pushTri(ni[0], ni[3], ni[2], pid);
            } else {
                n_other++;
            }
            continue;
        }

        // 8-slot storage. Classify by counting UNIQUE node indices.
        // LS-DYNA pads degenerate solids with repeated corner nodes; the
        // particular slot pattern varies between solvers and meshers, so
        // counting unique values is more robust than pattern matching.
        int n_unique = 0;
        {
            int32_t tmp[8] = {ni[0], ni[1], ni[2], ni[3], ni[4], ni[5], ni[6], ni[7]};
            std::sort(tmp, tmp + 8);
            for (int i = 0; i < 8; ++i) {
                if (i == 0 || tmp[i] != tmp[i-1]) ++n_unique;
            }
        }

        if (n_unique == 4) {
            // tet4 — extract the 4 unique nodes preserving their first
            // appearance in the original element node list (so the standard
            // outward winding still applies to ni[0..3] when the padding
            // collapsed slots 4..7).
            int32_t v[4] = {-1,-1,-1,-1}; int k = 0;
            for (int i = 0; i < 8 && k < 4; ++i) {
                bool seen = false;
                for (int j = 0; j < k; ++j) if (v[j] == ni[i]) { seen = true; break; }
                if (!seen) v[k++] = ni[i];
            }
            if (k < 4 || !distinct4(v[0], v[1], v[2], v[3])) { n_other++; continue; }
            n_tet++;
            // LS-DYNA tet4 winding (face opposite v3 = base, v0->v2->v1 is CCW
            // viewed from outside). All 4 faces use right-hand rule outward.
            pushTri(v[0], v[2], v[1], pid);
            pushTri(v[0], v[1], v[3], pid);
            pushTri(v[1], v[2], v[3], pid);
            pushTri(v[0], v[3], v[2], pid);
        } else if (n_unique == 5) {
            // pyr5 — apex is the node that appears in slots 4..7 and not in 0..3.
            int32_t base[4] = {ni[0], ni[1], ni[2], ni[3]};
            int32_t apex = -1;
            for (int i = 4; i < 8; ++i) {
                bool in_base = false;
                for (int j = 0; j < 4; ++j) if (base[j] == ni[i]) { in_base = true; break; }
                if (!in_base) { apex = ni[i]; break; }
            }
            if (apex < 0 || !distinct4(base[0], base[1], base[2], base[3])) {
                n_other++; continue;
            }
            n_pyr++;
            // Base quad (winding = outward, away from apex).
            pushQuad(base[0], base[3], base[2], base[1], pid);
            // 4 triangular sides connecting base edges to apex.
            pushTri(base[0], base[1], apex, pid);
            pushTri(base[1], base[2], apex, pid);
            pushTri(base[2], base[3], apex, pid);
            pushTri(base[3], base[0], apex, pid);
        } else if (n_unique == 6) {
            // penta6 wedge — 2 tri caps + 3 quad sides.
            // Multiple LS-DYNA padding conventions exist:
            //   (a) [n0,n1,n2,n3, n4,n4,n5,n5] — bottom={0,1,2}, top={3,4,5} via slots(3,4,6)
            //   (b) [n0,n1,n2,n3, n3,n4,n5,n5] — bottom={0,1,2}, top via slots(3,5,6)
            //   (c) [n0,n1,n2,n2, n3,n4,n5,n5] — bottom via slots(0,1,2),
            //       top via slots(4,5,6)
            // Identify two triangle caps by finding two disjoint sets of 3
            // unique nodes from the slot list. The simplest & robust approach:
            // collect unique node IDs in original-slot order, classify by
            // membership in slots 0..3 vs 4..7.
            int32_t low[8], hi[8]; int nl = 0, nh = 0;
            auto haveLow = [&](int32_t v) {
                for (int j = 0; j < nl; ++j) if (low[j] == v) return true; return false;
            };
            auto haveHi = [&](int32_t v) {
                for (int j = 0; j < nh; ++j) if (hi[j] == v) return true; return false;
            };
            for (int i = 0; i < 4; ++i) if (!haveLow(ni[i])) low[nl++] = ni[i];
            for (int i = 4; i < 8; ++i) if (!haveLow(ni[i]) && !haveHi(ni[i])) hi[nh++] = ni[i];
            // After this: low ∪ hi covers all 6 unique nodes, low ∩ hi = ∅.
            // Both caps must have 3 nodes each — but if not, fall back.
            if (nl == 3 && nh == 3) {
                n_penta++;
                int32_t b0 = low[0], b1 = low[1], b2 = low[2];
                int32_t t0 = hi[0],  t1 = hi[1],  t2 = hi[2];
                // Bottom cap (outward = away from top side)
                pushTri(b0, b2, b1, pid);
                pushTri(t0, t1, t2, pid);
                // 3 side quads — connect each bottom edge to the closest
                // pair of top nodes. Without knowing the exact pairing from
                // padding alone, build sides connecting edges (b0,b1)→(t0,t1),
                // (b1,b2)→(t1,t2), (b2,b0)→(t2,t0). May produce twisted
                // quads on rare meshes; the dedup catches such anomalies.
                pushQuad(b0, t0, t1, b1, pid);
                pushQuad(b1, t1, t2, b2, pid);
                pushQuad(b2, t2, t0, b0, pid);
            } else {
                n_other++;
                continue;
            }
        } else if (n_unique == 7) {
            // 7-unique-node degenerate hex — uncommon; treat as hex with one
            // collapsed face. The dedup naturally drops the collapsed quad.
            n_hex++;
            for (int f = 0; f < 6; ++f) {
                pushQuad(ni[HEXA_FACES[f][0]], ni[HEXA_FACES[f][1]],
                         ni[HEXA_FACES[f][2]], ni[HEXA_FACES[f][3]], pid);
            }
        } else if (n_unique == 8) {
            // True hex8.
            n_hex++;
            for (int f = 0; f < 6; ++f) {
                pushQuad(ni[HEXA_FACES[f][0]], ni[HEXA_FACES[f][1]],
                         ni[HEXA_FACES[f][2]], ni[HEXA_FACES[f][3]], pid);
            }
        } else {
            n_other++;
        }
    }
    std::fprintf(stderr, "[iso_surface] solids: %zu (tet4=%d penta6=%d pyr5=%d hex8=%d other=%d)\n",
                 mesh.solids.size(), n_tet, n_penta, n_pyr, n_hex, n_other);

    // Shells & thick shells: always exterior (no dedup needed).
    int n_shells = 0, n_tshells = 0;
    for (size_t ei = 0; ei < mesh.shells.size(); ++ei) {
        int32_t pid = (ei < mesh.shell_parts.size()) ? mesh.shell_parts[ei] : 0;
        const auto& nids = mesh.shells[ei].node_ids;
        int nn = (int)nids.size();
        if (nn < 3) continue;
        int32_t ni[4] = {-1, -1, -1, -1};
        for (int i = 0; i < std::min(nn, 4); ++i)
            ni[i] = resolveNodeIdx(nids[i], nid_to_idx);
        if (ni[3] >= 0 && ni[3] != ni[2] && distinct4(ni[0], ni[1], ni[2], ni[3])) {
            // Quad shell — emit DIRECTLY as 2 triangles (skip dedup).
            pending_quads.push_back({ni[0], ni[1], ni[2], ni[3], pid});
            quad_count[sortedQuad(ni[0], ni[1], ni[2], ni[3])] = 1;  // mark exterior
        } else if (distinct3(ni[0], ni[1], ni[2])) {
            pending_tris.push_back({ni[0], ni[1], ni[2], pid});
            tri_count[sortedTri(ni[0], ni[1], ni[2])] = 1;
        }
        n_shells++;
    }
    for (size_t ei = 0; ei < mesh.thick_shells.size(); ++ei) {
        int32_t pid = (ei < mesh.thick_shell_parts.size()) ? mesh.thick_shell_parts[ei] : 0;
        const auto& nids = mesh.thick_shells[ei].node_ids;
        if (nids.size() < 8) continue;
        int32_t ni[8];
        for (int i = 0; i < 8; ++i) ni[i] = resolveNodeIdx(nids[i], nid_to_idx);
        // Treat as hex8 — its 6 faces participate in dedup like solids.
        for (int f = 0; f < 6; ++f) {
            pushQuad(ni[HEXA_FACES[f][0]], ni[HEXA_FACES[f][1]],
                     ni[HEXA_FACES[f][2]], ni[HEXA_FACES[f][3]], pid);
        }
        n_tshells++;
    }

    // ---- Filter: only keep faces with count == 1 (exterior) ----
    // Also record each face's INITIAL max edge length² so the per-frame
    // erosion filter can compare runtime size against initial size.
    bool all_are_target = config.target_parts.empty();
    std::vector<ExtFace> ext_faces;
    ext_faces.reserve(pending_tris.size() + pending_quads.size() * 2);

    auto initialEdge2 = [&](int32_t a, int32_t b, int32_t c) -> float {
        if (a < 0 || b < 0 || c < 0) return 0.f;
        if (a >= (int32_t)mesh.nodes.size() || b >= (int32_t)mesh.nodes.size() ||
            c >= (int32_t)mesh.nodes.size()) return 0.f;
        const auto& na = mesh.nodes[a];
        const auto& nb = mesh.nodes[b];
        const auto& nc = mesh.nodes[c];
        auto sq = [](double x, double y, double z) { return x*x + y*y + z*z; };
        float e1 = (float)sq(nb.x-na.x, nb.y-na.y, nb.z-na.z);
        float e2 = (float)sq(nc.x-na.x, nc.y-na.y, nc.z-na.z);
        float e3 = (float)sq(nc.x-nb.x, nc.y-nb.y, nc.z-nb.z);
        return std::max({e1, e2, e3});
    };

    for (const auto& t : pending_tris) {
        auto it = tri_count.find(sortedTri(t.a, t.b, t.c));
        if (it != tri_count.end() && it->second == 1) {
            bool is_tgt = all_are_target || config.target_parts.matches(t.part_id);
            ExtFace f{{t.a, t.b, t.c}, t.part_id, is_tgt, initialEdge2(t.a, t.b, t.c)};
            ext_faces.push_back(f);
        }
    }
    for (const auto& q : pending_quads) {
        auto it = quad_count.find(sortedQuad(q.a, q.b, q.c, q.d));
        if (it == quad_count.end() || it->second != 1) continue;
        bool is_tgt = all_are_target || config.target_parts.matches(q.part_id);
        ExtFace f1{{q.a, q.b, q.c}, q.part_id, is_tgt, initialEdge2(q.a, q.b, q.c)};
        ExtFace f2{{q.a, q.c, q.d}, q.part_id, is_tgt, initialEdge2(q.a, q.c, q.d)};
        ext_faces.push_back(f1);
        ext_faces.push_back(f2);
    }
    std::fprintf(stderr, "[iso_surface] Exterior faces: %zu triangles "
                         "(%zu tris + %zu quads pending; shells=%d, tshells=%d)\n",
                 ext_faces.size(), pending_tris.size(), pending_quads.size(),
                 n_shells, n_tshells);


    // Part color map
    std::set<int32_t> unique_pids;
    for (const auto& f : ext_faces) unique_pids.insert(f.part_id);
    std::unordered_map<int32_t, int> part_color_map;
    {
        int cidx = 0;
        for (int32_t pid : unique_pids) part_color_map[pid] = cidx++;
    }

    // ---- Pipeline objects ----
    NodalAverager     averager(mesh, ctrl);
    SoftwareRasterizer rasterizer(config.width, config.height, config.supersampling);
    SectionCamera     camera;
    ColorMap          cmap(config.colormap);

    // Camera: isometric covering the INITIAL exterior surface AABB (state 0).
    // Use only nodes that participate in exterior faces — including all
    // mesh.nodes inflates the bbox with floating/eroded-element nodes and
    // shrinks the visible model. Mirrors render3D's framing behaviour.
    Vec3 mesh_center{0,0,0};
    {
        AABB3 bbox;
        bool first = true;
        const auto& st0 = all_states[0];
        for (const auto& face : ext_faces) {
            for (int k = 0; k < 3; ++k) {
                int32_t idx = face.node_idx[k];
                if (idx < 0 || idx >= (int32_t)mesh.nodes.size()) continue;
                Vec3 p = deformedPos(idx, mesh, st0);
                if (first) { bbox.min_pt = bbox.max_pt = p; first = false; }
                else bbox.expand(p);
            }
        }
        if (first) {
            for (size_t i = 0; i < mesh.nodes.size(); ++i) {
                Vec3 p = deformedPos((int32_t)i, mesh, st0);
                if (first) { bbox.min_pt = bbox.max_pt = p; first = false; }
                else bbox.expand(p);
            }
        }
        mesh_center = bbox.center();

        SectionPlane dummy = SectionPlane::fromAxis('z', mesh_center);
        camera.setupIsometric(dummy, bbox, config.scale_factor,
                              config.width, config.height);
    }

    // Global range scan
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

    // Target lighting (BG uses flat per-part color via silhouette compositor).
    const double ambient_tgt = 0.3;
    const double diffuse_tgt = 0.7;

    // Background alpha (clamped to [0, 1])
    double bg_alpha = config.background_alpha;
    if (bg_alpha < 0.0) bg_alpha = 0.0;
    if (bg_alpha > 1.0) bg_alpha = 1.0;

    // Defensive sanity check — if a triangle ever exceeds 6× its initial
    // edge length, something has gone catastrophically wrong (broken
    // displacement read, eroded element with stale data, etc). Skip it
    // rather than render a giant shard. Healthy deformation rarely
    // exceeds ~3×.
    const float erosion_growth2 = 36.0f;  // (6.0)²

    std::string frame_pattern = out_dir + "/frame_%04d.png";

    for (size_t si = 0; si < num_states; ++si) {
        const auto& state = all_states[si];

        averager.compute(state, config.field, config.target_parts);
        if (!config.global_range)
            cmap.setRange(averager.globalMin(), averager.globalMax());

        rasterizer.clear({255, 255, 255, 255});
        rasterizer.enableDepthTest(true);

        Vec3 vd = camera.viewDirection();
        Vec3 ru = camera.axisU();
        Vec3 up = camera.axisV();
        Vec3 light_dir = (vd + ru * 0.4 + up * 0.6).normalized();

        // Pass 0 — TARGET opaque (depth read+write, contour shading).
        for (const auto& face : ext_faces) {
            if (!face.is_target) continue;

            Vec3 p0 = deformedPos(face.node_idx[0], mesh, state);
            Vec3 p1 = deformedPos(face.node_idx[1], mesh, state);
            Vec3 p2 = deformedPos(face.node_idx[2], mesh, state);

            Vec3 e1 = p1 - p0;
            Vec3 e2 = p2 - p0;
            Vec3 e3 = p2 - p1;
            // Erosion filter — current max edge² compared to initial.
            double e1l2 = e1.dot(e1), e2l2 = e2.dot(e2), e3l2 = e3.dot(e3);
            double cur_max_edge2 = std::max({e1l2, e2l2, e3l2});
            if (face.max_edge2_init > 0.f &&
                cur_max_edge2 > face.max_edge2_init * erosion_growth2) continue;
            Vec3 cross = e1.cross(e2);
            double face_area2 = cross.dot(cross);
            if (face_area2 < 1e-10) continue;
            Vec3 fn = cross.normalizedSafe();
            if (fn.dot(vd) > 1e-3) continue;
            if (fn.dot(light_dir) < 0) fn = fn * -1.0;
            double ndotl = std::max(0.0, fn.dot(light_dir));

            double za, zb, zc;
            Vec2 sa = camera.project3D(p0, za);
            Vec2 sb = camera.project3D(p1, zb);
            Vec2 sc = camera.project3D(p2, zc);
            double ss = (double)config.supersampling;
            sa.x *= ss; sa.y *= ss;
            sb.x *= ss; sb.y *= ss;
            sc.x *= ss; sc.y *= ss;

            double tgt_i = std::min(1.0, ambient_tgt + diffuse_tgt * ndotl);
            RGBA ca = cmap.map(averager.nodeValue(face.node_idx[0]));
            RGBA cb = cmap.map(averager.nodeValue(face.node_idx[1]));
            RGBA cc = cmap.map(averager.nodeValue(face.node_idx[2]));
            ca.r = uint8_t(ca.r * tgt_i); ca.g = uint8_t(ca.g * tgt_i); ca.b = uint8_t(ca.b * tgt_i);
            cb.r = uint8_t(cb.r * tgt_i); cb.g = uint8_t(cb.g * tgt_i); cb.b = uint8_t(cb.b * tgt_i);
            cc.r = uint8_t(cc.r * tgt_i); cc.g = uint8_t(cc.g * tgt_i); cc.b = uint8_t(cc.b * tgt_i);
            rasterizer.drawTriangle3DContour(sa.x, sa.y, za, ca,
                                             sb.x, sb.y, zb, cb,
                                             sc.x, sc.y, zc, cc);
        }

        // Pass 1 — BG per-part SILHOUETTE compositing.
        // For each BG part we (a) build a coverage mask of every front-facing
        // triangle that's in front of the opaque target, then (b) blend the
        // part's solid color over the framebuffer once for the masked region.
        // This replaces the element-by-element alpha blend that produced
        // visible diagonals, multi-layer side strips, and stacked alpha.
        // Result: each BG part appears as a single uniform translucent
        // silhouette — the look the user asked for.
        const size_t mask_size =
            static_cast<size_t>(rasterizer.ssWidth()) * rasterizer.ssHeight();
        std::vector<uint8_t> mask(mask_size);
        std::vector<float>   pdepth(mask_size);
        std::vector<float>   shade(mask_size);

        // Group BG faces by part id (back-to-front order is preferred for
        // correct alpha compositing; we sort by minimum depth at state 0,
        // recomputed each frame would be slow — use part centroid below).
        std::map<int32_t, std::vector<const ExtFace*>> bg_by_part;
        for (const auto& face : ext_faces) {
            if (face.is_target) continue;
            bg_by_part[face.part_id].push_back(&face);
        }

        // Sort parts back-to-front by their average centroid depth so
        // overlapping translucent parts blend in correct order.
        struct PartOrder { int32_t pid; double avg_z; };
        std::vector<PartOrder> ordered_parts;
        ordered_parts.reserve(bg_by_part.size());
        for (auto& [pid, faces] : bg_by_part) {
            double sum_z = 0.0;
            int n = 0;
            for (const auto* f : faces) {
                Vec3 c = deformedPos(f->node_idx[0], mesh, state);
                Vec3 c1 = deformedPos(f->node_idx[1], mesh, state);
                Vec3 c2 = deformedPos(f->node_idx[2], mesh, state);
                Vec3 cen = {(c.x+c1.x+c2.x)/3.0, (c.y+c1.y+c2.y)/3.0, (c.z+c1.z+c2.z)/3.0};
                double zz;
                camera.project3D(cen, zz);
                sum_z += zz; ++n;
            }
            ordered_parts.push_back({pid, n ? sum_z / n : 0.0});
        }
        // Larger depth = further away = draw first (back-to-front).
        std::sort(ordered_parts.begin(), ordered_parts.end(),
                  [](const PartOrder& a, const PartOrder& b){ return a.avg_z > b.avg_z; });

        // Compute depth-based alpha modulation: parts CLOSER to camera get
        // MORE transparency (lower alpha) so they don't occlude what's
        // behind them. Farther parts stay near `bg_alpha` for visibility.
        double z_min_part = +std::numeric_limits<double>::infinity();
        double z_max_part = -std::numeric_limits<double>::infinity();
        for (const auto& po : ordered_parts) {
            if (po.avg_z < z_min_part) z_min_part = po.avg_z;
            if (po.avg_z > z_max_part) z_max_part = po.avg_z;
        }
        double z_span = z_max_part - z_min_part;

        for (const auto& po : ordered_parts) {
            std::fill(mask.begin(), mask.end(), uint8_t(0));
            std::fill(pdepth.begin(), pdepth.end(),
                      std::numeric_limits<float>::max());
            std::fill(shade.begin(), shade.end(), 0.0f);

            for (const auto* face : bg_by_part[po.pid]) {
                Vec3 p0 = deformedPos(face->node_idx[0], mesh, state);
                Vec3 p1 = deformedPos(face->node_idx[1], mesh, state);
                Vec3 p2 = deformedPos(face->node_idx[2], mesh, state);

                Vec3 e1 = p1 - p0;
                Vec3 e2 = p2 - p0;
                Vec3 e3 = p2 - p1;
                double e1l2 = e1.dot(e1), e2l2 = e2.dot(e2), e3l2 = e3.dot(e3);
                double cur_max_edge2 = std::max({e1l2, e2l2, e3l2});
                if (face->max_edge2_init > 0.f &&
                    cur_max_edge2 > face->max_edge2_init * erosion_growth2) continue;
                Vec3 cross = e1.cross(e2);
                double face_area2 = cross.dot(cross);
                if (face_area2 < 1e-10) continue;
                Vec3 fn = cross.normalizedSafe();

                // Per-triangle lighting intensity. The frontmost triangle
                // at each pixel sets the shade, so visible top, side, and
                // back faces each have distinct brightness — gives clear
                // 3D depth perception through the translucent silhouette.
                // Auto-flip normal to face the light so back-facing
                // triangles (which only win at silhouette grazing edges)
                // still get reasonable shading.
                if (fn.dot(light_dir) < 0) fn = fn * -1.0;
                double ndotl = std::max(0.0, fn.dot(light_dir));
                // Wider ambient/diffuse range (0.4..1.0) to make front-
                // vs-side face contrast visible through alpha blending.
                float tri_shade = static_cast<float>(0.4 + 0.6 * ndotl);

                double za, zb, zc;
                Vec2 sa = camera.project3D(p0, za);
                Vec2 sb = camera.project3D(p1, zb);
                Vec2 sc = camera.project3D(p2, zc);
                double ss = (double)config.supersampling;
                sa.x *= ss; sa.y *= ss;
                sb.x *= ss; sb.y *= ss;
                sc.x *= ss; sc.y *= ss;

                rasterizer.rasterizeToPartMask(sa.x, sa.y, za,
                                               sb.x, sb.y, zb,
                                               sc.x, sc.y, zc,
                                               tri_shade,
                                               mask, pdepth, shade);
            }

            // Per-part base color; per-pixel shade is applied inside
            // compositePartSilhouette to give 3D depth perception while
            // keeping each part as a single hue.
            int cidx = 0;
            auto cit = part_color_map.find(po.pid);
            if (cit != part_color_map.end()) cidx = cit->second;
            RGBA pcol = g_part_palette[cidx % G_PART_PALETTE_SIZE];
            pcol.a = 255;

            // Depth-modulated alpha: closer parts (smaller depth) get
            // 0.4× of bg_alpha (more transparent), farther parts get
            // 1.0× (less transparent, visible as backdrop). When there is
            // only one BG part or all are at the same depth, use bg_alpha
            // directly.
            double part_alpha = bg_alpha;
            if (z_span > 1e-6) {
                double t = (po.avg_z - z_min_part) / z_span;  // 0=closest, 1=farthest
                double scale = 0.4 + 0.6 * t;                 // 0.4..1.0
                part_alpha = bg_alpha * scale;
            }
            if (part_alpha < 0.0) part_alpha = 0.0;
            if (part_alpha > 1.0) part_alpha = 1.0;

            rasterizer.compositePartSilhouette(mask, pdepth, shade,
                                               pcol, (float)part_alpha);
        }

        std::string frame_path = out_dir + "/" + frameName((int)si, (int)num_states);
        std::string err = rasterizer.savePng(frame_path);
        if (!err.empty()) return "Frame " + std::to_string(si) + ": " + err;

        if (si % 20 == 0 || si == num_states - 1)
            std::fprintf(stderr, "[iso_surface] Rendered frame %zu / %zu\n", si + 1, num_states);
    }

    if (config.mp4) {
        std::string mp4_path = out_dir + "/section_view.mp4";
        std::string err = assembleMp4(frame_pattern, mp4_path, config.fps);
        if (!err.empty()) return err;
    }
    if (!config.png_frames) {
        for (const auto& entry : fs::directory_iterator(out_dir)) {
            if (entry.path().extension() == ".png") {
                const std::string fname = entry.path().filename().string();
                if (fname.substr(0, 6) == "frame_") fs::remove(entry.path());
            }
        }
    }
    return "";
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
