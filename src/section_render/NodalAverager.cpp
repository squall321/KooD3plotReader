/**
 * @file NodalAverager.cpp
 * @brief Element-to-node scalar field averaging (full implementation)
 *
 * Node ID convention (from BoundingBox.cpp):
 *   Element::node_ids stores 1-based node IDs.
 *   If real_node_ids is empty:  index = nid - 1
 *   If real_node_ids non-empty: index = position in real_node_ids[]
 *
 * Indexing:
 *   solid_data[elem * NV3D + offset]       — offsets 0-5: sxx,syy,szz,sxy,syz,szx; 6: EPS
 *   thick_shell_data[elem * NV3DT + offset]
 *   shell_data[elem * NV2D + offset]       — simplified: first integration point
 */

#include "kood3plot/section_render/NodalAverager.hpp"
#include <algorithm>
#include <cmath>

namespace kood3plot {
namespace section_render {

// ============================================================
// Constructor
// ============================================================

NodalAverager::NodalAverager(const data::Mesh& mesh, const data::ControlData& control)
    : mesh_(mesh), control_(control)
{
    int32_t numnp = control_.NUMNP;
    node_sum_.assign(numnp, 0.0);
    node_count_.assign(numnp, 0);

    // Build O(1) lookup when real_node_ids is present
    if (!mesh_.real_node_ids.empty()) {
        for (int32_t i = 0; i < static_cast<int32_t>(mesh_.real_node_ids.size()); ++i) {
            node_id_to_index_[mesh_.real_node_ids[i]] = i;
        }
    }
}

// ============================================================
// Node-ID → array index
// ============================================================

int32_t NodalAverager::nodeIndex(int32_t node_id) const
{
    if (mesh_.real_node_ids.empty()) {
        return node_id - 1;  // 1-based → 0-based
    }
    auto it = node_id_to_index_.find(node_id);
    return (it != node_id_to_index_.end()) ? it->second : -1;
}

// ============================================================
// compute()
// ============================================================

void NodalAverager::compute(const data::StateData& state,
                             FieldSelector field,
                             const PartMatcher& target)
{
    int32_t numnp = control_.NUMNP;
    std::fill(node_sum_.begin(),   node_sum_.end(),   0.0);
    std::fill(node_count_.begin(), node_count_.end(), 0);

    // Build deletion lookup sets
    std::unordered_set<int32_t> del_solids(
        state.deleted_solids.begin(), state.deleted_solids.end());
    std::unordered_set<int32_t> del_thick(
        state.deleted_thick_shells.begin(), state.deleted_thick_shells.end());
    std::unordered_set<int32_t> del_shells(
        state.deleted_shells.begin(), state.deleted_shells.end());

    // Displacement is nodal — handle separately (no element averaging)
    if (field == FieldSelector::DisplacementMagnitude) {
        if (control_.IU != 1 || state.node_displacements.empty()) {
            global_min_ = 0.0; global_max_ = 1.0;
            return;
        }
        double mn = 1e300, mx = -1e300;
        for (int32_t i = 0; i < numnp; ++i) {
            size_t base = static_cast<size_t>(i) * 3;
            if (base + 2 >= state.node_displacements.size()) break;
            double ux = state.node_displacements[base + 0];
            double uy = state.node_displacements[base + 1];
            double uz = state.node_displacements[base + 2];
            double mag = std::sqrt(ux*ux + uy*uy + uz*uz);
            node_sum_[i]   = mag;
            node_count_[i] = 1;
            if (mag < mn) mn = mag;
            if (mag > mx) mx = mag;
        }
        global_min_ = (mn < 1e299) ? mn : 0.0;
        global_max_ = (mx > -1e299) ? mx : 1.0;
        if (global_max_ <= global_min_ + 1e-12) global_max_ = global_min_ + 1.0;
        return;
    }

    // ---- Solid elements ----
    if (!state.solid_data.empty() && control_.NV3D > 0) {
        for (size_t ei = 0; ei < mesh_.solids.size(); ++ei) {
            const auto& elem = mesh_.solids[ei];
            if (!del_solids.empty() && del_solids.count(elem.id)) continue;
            int32_t pid = (ei < mesh_.solid_parts.size()) ? mesh_.solid_parts[ei] : 0;
            if (!target.empty() && !target.matches(pid, "")) continue;

            double val = extractSolidValue(state, static_cast<int32_t>(ei), field);
            for (int32_t nid : elem.node_ids) {
                int32_t idx = nodeIndex(nid);
                if (idx >= 0 && idx < numnp) {
                    node_sum_[idx]   += val;
                    node_count_[idx] += 1;
                }
            }
        }
    }

    // ---- Thick shell elements ----
    if (!state.thick_shell_data.empty() && control_.NV3DT > 0) {
        for (size_t ei = 0; ei < mesh_.thick_shells.size(); ++ei) {
            const auto& elem = mesh_.thick_shells[ei];
            if (!del_thick.empty() && del_thick.count(elem.id)) continue;
            int32_t pid = (ei < mesh_.thick_shell_parts.size()) ? mesh_.thick_shell_parts[ei] : 0;
            if (!target.empty() && !target.matches(pid, "")) continue;

            double val = extractThickShellValue(state, static_cast<int32_t>(ei), field);
            for (int32_t nid : elem.node_ids) {
                int32_t idx = nodeIndex(nid);
                if (idx >= 0 && idx < numnp) {
                    node_sum_[idx]   += val;
                    node_count_[idx] += 1;
                }
            }
        }
    }

    // ---- Shell elements ----
    if (!state.shell_data.empty() && control_.NV2D > 0) {
        for (size_t ei = 0; ei < mesh_.shells.size(); ++ei) {
            const auto& elem = mesh_.shells[ei];
            if (!del_shells.empty() && del_shells.count(elem.id)) continue;
            int32_t pid = (ei < mesh_.shell_parts.size()) ? mesh_.shell_parts[ei] : 0;
            if (!target.empty() && !target.matches(pid, "")) continue;

            double val = extractShellValue(state, static_cast<int32_t>(ei), field);
            for (int32_t nid : elem.node_ids) {
                int32_t idx = nodeIndex(nid);
                if (idx >= 0 && idx < numnp) {
                    node_sum_[idx]   += val;
                    node_count_[idx] += 1;
                }
            }
        }
    }

    // ---- Divide accumulated sum by count; compute global range ----
    double mn = 1e300, mx = -1e300;
    for (int32_t i = 0; i < numnp; ++i) {
        if (node_count_[i] > 0) {
            double v = node_sum_[i] / static_cast<double>(node_count_[i]);
            node_sum_[i] = v;  // overwrite: node_sum_ now holds the final average
            if (v < mn) mn = v;
            if (v > mx) mx = v;
        }
    }
    global_min_ = (mn < 1e299) ? mn : 0.0;
    global_max_ = (mx > -1e299) ? mx : 1.0;
    if (global_max_ <= global_min_ + 1e-12) global_max_ = global_min_ + 1.0;
}

// ============================================================
// nodeValue()
// ============================================================

double NodalAverager::nodeValue(int32_t node_index) const
{
    if (node_index < 0 || node_index >= static_cast<int32_t>(node_sum_.size()))
        return 0.0;
    return node_sum_[node_index];  // holds averaged value after compute()
}

// ============================================================
// Scalar extraction helpers
// ============================================================

namespace {

double vonMises(double sxx, double syy, double szz,
                double sxy, double syz, double szx)
{
    double s1 = sxx - syy, s2 = syy - szz, s3 = szz - sxx;
    return std::sqrt(0.5*(s1*s1 + s2*s2 + s3*s3) + 3.0*(sxy*sxy + syz*syz + szx*szx));
}

double extractStress(const std::vector<double>& data, size_t base, int stride,
                     FieldSelector field)
{
    if (base + 6 > data.size()) return 0.0;
    double sxx = data[base+0], syy = data[base+1], szz = data[base+2];
    double sxy = data[base+3], syz = data[base+4], szx = data[base+5];

    switch (field) {
        case FieldSelector::VonMises:
            return vonMises(sxx, syy, szz, sxy, syz, szx);
        case FieldSelector::EffectivePlasticStrain:
            return (base + 7 <= data.size()) ? data[base + 6] : 0.0;
        case FieldSelector::PressureStress:
            return -(sxx + syy + szz) / 3.0;
        case FieldSelector::MaxShearStress:
            return vonMises(sxx, syy, szz, sxy, syz, szx) / std::sqrt(3.0);
        default:
            return vonMises(sxx, syy, szz, sxy, syz, szx);
    }
    (void)stride;
}

} // anonymous namespace

double NodalAverager::extractSolidValue(const data::StateData& state,
                                         int32_t ei, FieldSelector field) const
{
    size_t base = static_cast<size_t>(ei) * control_.NV3D;
    return extractStress(state.solid_data, base, control_.NV3D, field);
}

double NodalAverager::extractShellValue(const data::StateData& state,
                                         int32_t ei, FieldSelector field) const
{
    size_t base = static_cast<size_t>(ei) * control_.NV2D;
    return extractStress(state.shell_data, base, control_.NV2D, field);
}

double NodalAverager::extractThickShellValue(const data::StateData& state,
                                              int32_t ei, FieldSelector field) const
{
    size_t base = static_cast<size_t>(ei) * control_.NV3DT;
    return extractStress(state.thick_shell_data, base, control_.NV3DT, field);
}

} // namespace section_render
} // namespace kood3plot
