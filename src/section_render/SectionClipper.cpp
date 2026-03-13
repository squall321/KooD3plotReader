/**
 * @file SectionClipper.cpp
 * @brief Element-plane clipping (full implementation)
 *
 * Hex8 (solid / thick-shell): 12 edges → radial-sorted polygon (≥ 3 vertices)
 * Shell quad4: 4 edges → line segment (== 2 vertices)
 *
 * Node IDs in Element::node_ids are 1-based external IDs.
 * Displacement array is indexed by 0-based node array position.
 */

#include "kood3plot/section_render/SectionClipper.hpp"
#include <algorithm>
#include <cmath>

namespace kood3plot {
namespace section_render {

// ============================================================
// Element edge tables (local node index pairs)
// ============================================================

// Tet4: 4 nodes, 6 edges
static const int TET4_EDGES[6][2] = {
    {0,1}, {0,2}, {0,3}, {1,2}, {1,3}, {2,3}
};

// Penta6 (wedge): 6 nodes, 9 edges
static const int PENTA6_EDGES[9][2] = {
    {0,1}, {1,2}, {2,0},          // bottom tri
    {3,4}, {4,5}, {5,3},          // top tri
    {0,3}, {1,4}, {2,5}           // lateral
};

// Pyram5: 5 nodes, 8 edges
static const int PYRAM5_EDGES[8][2] = {
    {0,1}, {1,2}, {2,3}, {3,0},   // base quad
    {0,4}, {1,4}, {2,4}, {3,4}    // lateral to apex
};

// Hex8: 8 nodes, 12 edges
static const int HEX8_EDGES[12][2] = {
    {0,1}, {1,2}, {2,3}, {3,0},   // bottom face
    {4,5}, {5,6}, {6,7}, {7,4},   // top face
    {0,4}, {1,5}, {2,6}, {3,7}    // lateral edges
};

// Quad4 edge table
static const int QUAD4_EDGES[4][2] = {
    {0,1}, {1,2}, {2,3}, {3,0}
};

// ============================================================
// Constructor
// ============================================================

SectionClipper::SectionClipper(const data::Mesh& mesh,
                                const data::ControlData& control,
                                const SectionPlane& plane,
                                double slab_thickness)
    : mesh_(mesh), control_(control), plane_(plane), slab_half_(slab_thickness * 0.5)
{
    if (!mesh_.real_node_ids.empty()) {
        for (int32_t i = 0; i < static_cast<int32_t>(mesh_.real_node_ids.size()); ++i) {
            node_id_to_index_[mesh_.real_node_ids[i]] = i;
        }
    }
}

// ============================================================
// Node helpers
// ============================================================

int32_t SectionClipper::nodeIndex(int32_t node_id) const
{
    if (mesh_.real_node_ids.empty()) return node_id - 1;
    auto it = node_id_to_index_.find(node_id);
    return (it != node_id_to_index_.end()) ? it->second : -1;
}

Vec3 SectionClipper::nodePos(const data::StateData& state, int32_t idx) const
{
    if (idx < 0 || idx >= static_cast<int32_t>(mesh_.nodes.size())) return {};
    const auto& nd = mesh_.nodes[idx];
    Vec3 pos{nd.x, nd.y, nd.z};
    if (control_.IU == 1 && !state.node_displacements.empty()) {
        size_t base = static_cast<size_t>(idx) * 3;
        if (base + 2 < state.node_displacements.size()) {
            pos.x += state.node_displacements[base + 0];
            pos.y += state.node_displacements[base + 1];
            pos.z += state.node_displacements[base + 2];
        }
    }
    return pos;
}

// ============================================================
// clip()
// ============================================================

void SectionClipper::clip(const data::StateData& state,
                           const NodalAverager& averager,
                           const PartMatcher& target,
                           const PartMatcher& background,
                           std::vector<ClipPolygon>& target_result,
                           std::vector<ClipPolygon>& bg_result,
                           std::vector<float>& bg_alphas,
                           double fade_distance)
{
    target_result.clear();
    bg_result.clear();
    bg_alphas.clear();

    std::unordered_set<int32_t> del_solids(
        state.deleted_solids.begin(), state.deleted_solids.end());
    std::unordered_set<int32_t> del_thick(
        state.deleted_thick_shells.begin(), state.deleted_thick_shells.end());
    std::unordered_set<int32_t> del_shells(
        state.deleted_shells.begin(), state.deleted_shells.end());

    auto classify = [&](int32_t pid, bool& is_tgt, bool& is_bg) {
        is_bg = !background.empty() && background.matches(pid, "");
        if (!is_bg) {
            if (target.empty() || target.matches(pid, "")) {
                is_tgt = true;
            } else {
                is_bg  = true;
                is_tgt = false;
            }
        } else {
            is_tgt = false;
        }
    };

    // Helper: push bg polygon with alpha
    auto pushBg = [&](ClipPolygon poly, float alpha) {
        if (poly.empty()) return;
        bg_result.push_back(std::move(poly));
        bg_alphas.push_back(alpha);
    };

    // ---- Solid elements ----
    for (size_t ei = 0; ei < mesh_.solids.size(); ++ei) {
        const auto& elem = mesh_.solids[ei];
        if (!del_solids.empty() && del_solids.count(elem.id)) continue;
        int32_t pid = (ei < mesh_.solid_parts.size()) ? mesh_.solid_parts[ei] : 0;

        bool is_tgt, is_bg;
        classify(pid, is_tgt, is_bg);
        if (!is_tgt && !is_bg) continue;

        if (is_tgt) {
            ClipPolygon poly = clipHex8(elem.node_ids, state, averager, pid);
            if (!poly.empty()) target_result.push_back(std::move(poly));
        } else {
            // Try exact intersection first
            ClipPolygon poly = clipHex8(elem.node_ids, state, averager, pid);
            if (!poly.empty()) {
                pushBg(std::move(poly), 1.0f);
            } else if (fade_distance > 0.0) {
                int nn = static_cast<int>(std::min(elem.node_ids.size(), size_t(8)));
                Vec3 pos[8] = {}; double dist[8] = {}; double val[8] = {};
                for (int i = 0; i < nn; ++i) {
                    int32_t idx = nodeIndex(elem.node_ids[i]);
                    pos[i]  = nodePos(state, idx);
                    dist[i] = plane_.signedDistance(pos[i]);
                    val[i]  = (idx >= 0) ? averager.nodeValue(idx) : 0.0;
                }
                double min_d = std::abs(dist[0]);
                for (int i = 1; i < nn; ++i) min_d = std::min(min_d, std::abs(dist[i]));
                if (min_d <= fade_distance) {
                    float alpha = static_cast<float>(1.0 - min_d / fade_distance);
                    pushBg(projectNNode(pos, dist, val, nn, pid), alpha);
                }
            }
        }
    }

    // ---- Thick shell elements ----
    for (size_t ei = 0; ei < mesh_.thick_shells.size(); ++ei) {
        const auto& elem = mesh_.thick_shells[ei];
        if (!del_thick.empty() && del_thick.count(elem.id)) continue;
        int32_t pid = (ei < mesh_.thick_shell_parts.size()) ? mesh_.thick_shell_parts[ei] : 0;

        bool is_tgt, is_bg;
        classify(pid, is_tgt, is_bg);
        if (!is_tgt && !is_bg) continue;

        if (is_tgt) {
            ClipPolygon poly = clipHex8(elem.node_ids, state, averager, pid);
            if (!poly.empty()) target_result.push_back(std::move(poly));
        } else {
            ClipPolygon poly = clipHex8(elem.node_ids, state, averager, pid);
            if (!poly.empty()) {
                pushBg(std::move(poly), 1.0f);
            } else if (fade_distance > 0.0) {
                int nn = static_cast<int>(std::min(elem.node_ids.size(), size_t(8)));
                Vec3 pos[8] = {}; double dist[8] = {}; double val[8] = {};
                for (int i = 0; i < nn; ++i) {
                    int32_t idx = nodeIndex(elem.node_ids[i]);
                    pos[i]  = nodePos(state, idx);
                    dist[i] = plane_.signedDistance(pos[i]);
                    val[i]  = (idx >= 0) ? averager.nodeValue(idx) : 0.0;
                }
                double min_d = std::abs(dist[0]);
                for (int i = 1; i < nn; ++i) min_d = std::min(min_d, std::abs(dist[i]));
                if (min_d <= fade_distance) {
                    float alpha = static_cast<float>(1.0 - min_d / fade_distance);
                    pushBg(projectNNode(pos, dist, val, nn, pid), alpha);
                }
            }
        }
    }

    // ---- Shell elements ----
    for (size_t ei = 0; ei < mesh_.shells.size(); ++ei) {
        const auto& elem = mesh_.shells[ei];
        if (!del_shells.empty() && del_shells.count(elem.id)) continue;
        int32_t pid = (ei < mesh_.shell_parts.size()) ? mesh_.shell_parts[ei] : 0;

        bool is_tgt, is_bg;
        classify(pid, is_tgt, is_bg);
        if (!is_tgt && !is_bg) continue;

        if (is_tgt) {
            ClipPolygon poly = clipShell(state, averager, static_cast<int32_t>(ei), pid);
            if (!poly.empty()) target_result.push_back(std::move(poly));
        } else {
            ClipPolygon poly = clipShell(state, averager, static_cast<int32_t>(ei), pid);
            if (!poly.empty()) {
                pushBg(std::move(poly), 1.0f);
            } else if (fade_distance > 0.0) {
                const auto& nids = elem.node_ids;
                int nc = std::min(static_cast<int>(nids.size()), 4);
                if (nc < 3) continue;
                Vec3 pos[4]; double dist[4]; double val[4];
                for (int i = 0; i < nc; ++i) {
                    int32_t idx = nodeIndex(nids[i]);
                    pos[i]  = nodePos(state, idx);
                    dist[i] = plane_.signedDistance(pos[i]);
                    val[i]  = (idx >= 0) ? averager.nodeValue(idx) : 0.0;
                }
                double min_d = std::abs(dist[0]);
                for (int i = 1; i < nc; ++i) min_d = std::min(min_d, std::abs(dist[i]));
                if (min_d <= fade_distance) {
                    float alpha = static_cast<float>(1.0 - min_d / fade_distance);
                    pushBg(projectShell(pos, dist, val, nc, pid), alpha);
                }
            }
        }
    }
}

// ============================================================
// clipSolidElement — handles Tet4, Penta6, Pyram5, Hex8
// ============================================================

ClipPolygon SectionClipper::clipHex8(const std::vector<int32_t>& nids,
                                      const data::StateData& state,
                                      const NodalAverager& averager,
                                      int32_t part_id) const
{
    int nn = static_cast<int>(nids.size());
    if (nn < 4) return {};

    // Select edge table by node count
    const int (*edges)[2] = nullptr;
    int ne = 0;
    if      (nn >= 8) { edges = HEX8_EDGES;   ne = 12; nn = 8; }
    else if (nn == 6) { edges = PENTA6_EDGES;  ne =  9; }
    else if (nn == 5) { edges = PYRAM5_EDGES;  ne =  8; }
    else              { edges = TET4_EDGES;    ne =  6; nn = 4; }

    Vec3   pos[8] = {};
    double dist[8] = {};
    double val[8]  = {};
    for (int i = 0; i < nn; ++i) {
        int32_t idx = nodeIndex(nids[i]);
        pos[i]  = nodePos(state, idx);
        dist[i] = plane_.signedDistance(pos[i]);
        val[i]  = (idx >= 0) ? averager.nodeValue(idx) : 0.0;
    }

    // Quick reject: all nodes on same side of the plane
    bool anyPos = false, anyNeg = false;
    for (int i = 0; i < nn; ++i) {
        double d = (slab_half_ > 0.0 && std::abs(dist[i]) <= slab_half_) ? 0.0 : dist[i];
        if (d > 0.0) anyPos = true;
        if (d < 0.0) anyNeg = true;
    }
    if (!anyPos || !anyNeg) return {};

    std::vector<ClipVertex> verts;
    verts.reserve(ne);

    constexpr double CLAMP_EPS = 1e-9;
    for (int e = 0; e < ne; ++e) {
        int a = edges[e][0], b = edges[e][1];
        double da = (slab_half_ > 0.0 && std::abs(dist[a]) <= slab_half_) ? 0.0 : dist[a];
        double db = (slab_half_ > 0.0 && std::abs(dist[b]) <= slab_half_) ? 0.0 : dist[b];
        // Only crossed edges produce an intersection
        if ((da >= 0.0) == (db >= 0.0)) continue;
        double denom = da - db;
        if (std::abs(denom) < 1e-12) continue;
        double t = da / denom;
        t = std::max(0.0, std::min(1.0, t));

        Vec3 ipos{
            pos[a].x + t*(pos[b].x - pos[a].x),
            pos[a].y + t*(pos[b].y - pos[a].y),
            pos[a].z + t*(pos[b].z - pos[a].z)
        };
        verts.emplace_back(ipos, val[a] + t*(val[b] - val[a]), part_id);
    }

    if (verts.size() < 3) return {};
    radialSort(verts);
    return verts;
}

// ============================================================
// projectHex8 — project all 8 nodes onto the plane (fade mode)
// ============================================================

ClipPolygon SectionClipper::projectHex8(const Vec3 pos[8], const double dist[8],
                                         const double val[8], int32_t part_id) const
{
    return projectNNode(pos, dist, val, 8, part_id);
}

ClipPolygon SectionClipper::projectNNode(const Vec3* pos, const double* dist,
                                          const double* val, int nn, int32_t part_id) const
{
    const Vec3& n = plane_.normal();
    std::vector<ClipVertex> verts;
    verts.reserve(nn);
    for (int i = 0; i < nn; ++i) {
        Vec3 proj{
            pos[i].x - dist[i]*n.x,
            pos[i].y - dist[i]*n.y,
            pos[i].z - dist[i]*n.z
        };
        verts.emplace_back(proj, val[i], part_id);
    }
    if (verts.size() < 3) return {};
    radialSort(verts);
    return verts;
}

ClipPolygon SectionClipper::projectShell(const Vec3* pos, const double* dist,
                                          const double* val, int nc, int32_t part_id) const
{
    const Vec3& n = plane_.normal();
    std::vector<ClipVertex> verts;
    verts.reserve(nc);
    for (int i = 0; i < nc; ++i) {
        Vec3 proj{
            pos[i].x - dist[i]*n.x,
            pos[i].y - dist[i]*n.y,
            pos[i].z - dist[i]*n.z
        };
        verts.emplace_back(proj, val[i], part_id);
    }
    if (verts.size() < 3) return {};
    radialSort(verts);
    return verts;
}

// ============================================================
// clipSolid / clipThickShell — delegate to clipHex8
// ============================================================

ClipPolygon SectionClipper::clipSolid(const data::StateData& state,
                                       const NodalAverager& averager,
                                       int32_t ei, int32_t part_id) const
{
    if (ei < 0 || static_cast<size_t>(ei) >= mesh_.solids.size()) return {};
    return clipHex8(mesh_.solids[ei].node_ids, state, averager, part_id);
}

ClipPolygon SectionClipper::clipThickShell(const data::StateData& state,
                                            const NodalAverager& averager,
                                            int32_t ei, int32_t part_id) const
{
    if (ei < 0 || static_cast<size_t>(ei) >= mesh_.thick_shells.size()) return {};
    return clipHex8(mesh_.thick_shells[ei].node_ids, state, averager, part_id);
}

// ============================================================
// clipShell — quad4 → line segment (size == 2)
// ============================================================

ClipPolygon SectionClipper::clipShell(const data::StateData& state,
                                       const NodalAverager& averager,
                                       int32_t ei, int32_t part_id) const
{
    if (ei < 0 || static_cast<size_t>(ei) >= mesh_.shells.size()) return {};
    const auto& nids = mesh_.shells[ei].node_ids;
    int n = static_cast<int>(nids.size());
    if (n < 3) return {};

    Vec3   pos[4] = {};
    double dist[4] = {};
    double val[4]  = {};
    int nc = std::min(n, 4);
    for (int i = 0; i < nc; ++i) {
        int32_t idx = nodeIndex(nids[i]);
        pos[i]  = nodePos(state, idx);
        dist[i] = plane_.signedDistance(pos[i]);
        val[i]  = (idx >= 0) ? averager.nodeValue(idx) : 0.0;
    }

    constexpr double CLAMP_EPS = 1e-9;
    std::vector<ClipVertex> verts;
    verts.reserve(2);
    for (int e = 0; e < nc; ++e) {
        int a = QUAD4_EDGES[e][0], b = QUAD4_EDGES[e][1];
        if (a >= nc || b >= nc) continue;
        double da = (slab_half_ > 0.0 && std::abs(dist[a]) <= slab_half_) ? 0.0 : dist[a];
        double db = (slab_half_ > 0.0 && std::abs(dist[b]) <= slab_half_) ? 0.0 : dist[b];
        double denom = da - db;
        if (std::abs(denom) < 1e-12) continue;
        double t = da / denom;
        if (t < -CLAMP_EPS || t > 1.0 + CLAMP_EPS) continue;
        t = std::max(0.0, std::min(1.0, t));
        Vec3 ipos{
            pos[a].x + t*(pos[b].x - pos[a].x),
            pos[a].y + t*(pos[b].y - pos[a].y),
            pos[a].z + t*(pos[b].z - pos[a].z)
        };
        verts.emplace_back(ipos, val[a] + t*(val[b] - val[a]), part_id);
    }

    if (verts.size() != 2) return {};
    return verts;
}

// ============================================================
// radialSort
// ============================================================

void SectionClipper::radialSort(std::vector<ClipVertex>& verts) const
{
    if (verts.size() < 3) return;

    Vec3 c{0,0,0};
    for (const auto& v : verts) {
        c.x += v.position.x; c.y += v.position.y; c.z += v.position.z;
    }
    double ni = 1.0 / static_cast<double>(verts.size());
    c.x *= ni; c.y *= ni; c.z *= ni;

    Vec3 u, bv;
    plane_.getBasis(u, bv);

    std::sort(verts.begin(), verts.end(),
        [&](const ClipVertex& a, const ClipVertex& b_v) {
            double ax = a.position.x-c.x, ay = a.position.y-c.y, az = a.position.z-c.z;
            double bx = b_v.position.x-c.x, by_ = b_v.position.y-c.y, bz = b_v.position.z-c.z;
            double au = ax*u.x+ay*u.y+az*u.z, av = ax*bv.x+ay*bv.y+az*bv.z;
            double bu = bx*u.x+by_*u.y+bz*u.z, bvv = bx*bv.x+by_*bv.y+bz*bv.z;
            return std::atan2(av, au) < std::atan2(bvv, bu);
        });
}

} // namespace section_render
} // namespace kood3plot
