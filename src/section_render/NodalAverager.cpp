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
#include <array>

namespace kood3plot {
namespace section_render {

// ============================================================
// Shape function gradients for total strain computation
// ============================================================
namespace {

/// 3×3 matrix type (row-major)
using Mat3 = std::array<double, 9>;

/// Invert 3×3 matrix, returns determinant. Result in inv.
double invert3x3(const Mat3& m, Mat3& inv)
{
    double a = m[0], b = m[1], c = m[2];
    double d = m[3], e = m[4], f = m[5];
    double g = m[6], h = m[7], k = m[8];
    double det = a*(e*k - f*h) - b*(d*k - f*g) + c*(d*h - e*g);
    if (std::abs(det) < 1e-30) return 0.0;
    double invd = 1.0 / det;
    inv[0] = (e*k - f*h) * invd;  inv[1] = (c*h - b*k) * invd;  inv[2] = (b*f - c*e) * invd;
    inv[3] = (f*g - d*k) * invd;  inv[4] = (a*k - c*g) * invd;  inv[5] = (c*d - a*f) * invd;
    inv[6] = (d*h - e*g) * invd;  inv[7] = (b*g - a*h) * invd;  inv[8] = (a*e - b*d) * invd;
    return det;
}

/// Von Mises equivalent strain from 6-component strain tensor
/// ε_eq = sqrt(2/3 * ε_dev : ε_dev)  where ε_dev = ε - 1/3 tr(ε) I
double vonMisesStrain(double exx, double eyy, double ezz,
                      double exy, double eyz, double exz)
{
    double em = (exx + eyy + ezz) / 3.0;
    double dxx = exx - em, dyy = eyy - em, dzz = ezz - em;
    return std::sqrt(2.0/3.0 * (dxx*dxx + dyy*dyy + dzz*dzz +
                                2.0*(exy*exy + eyz*eyz + exz*exz)));
}

/// Compute element-centroid total strain for Hex8 (8-node brick)
/// Uses isoparametric shape functions evaluated at ξ=η=ζ=0
double computeHex8Strain(const double coords[][3], const double disp[][3])
{
    // Hex8 shape function derivatives at center (ξ=η=ζ=0):
    // dN/dξ = ±1/8 * (1±η)(1±ζ), etc.
    // Node ordering: LS-DYNA convention
    static const double signs[8][3] = {
        {-1,-1,-1}, {+1,-1,-1}, {+1,+1,-1}, {-1,+1,-1},
        {-1,-1,+1}, {+1,-1,+1}, {+1,+1,+1}, {-1,+1,+1}
    };

    // dN_i/dξ, dN_i/dη, dN_i/dζ at center (0,0,0)
    double dNdxi[8][3];
    for (int i = 0; i < 8; ++i) {
        double si = signs[i][0], ei = signs[i][1], zi = signs[i][2];
        dNdxi[i][0] = si * 0.125;  // (1±η)(1±ζ)/8 at η=ζ=0 → 1/8
        dNdxi[i][1] = ei * 0.125;
        dNdxi[i][2] = zi * 0.125;
    }

    // Jacobian: J_ij = Σ_k dN_k/dξ_j * x_ki
    Mat3 J = {0,0,0, 0,0,0, 0,0,0};
    for (int k = 0; k < 8; ++k) {
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                J[i*3+j] += dNdxi[k][i] * coords[k][j];
            }
        }
    }

    Mat3 Jinv;
    double det = invert3x3(J, Jinv);
    if (std::abs(det) < 1e-30) return 0.0;

    // dN/dx = Jinv * dN/dξ
    double dNdx[8][3];
    for (int k = 0; k < 8; ++k) {
        for (int i = 0; i < 3; ++i) {
            dNdx[k][i] = Jinv[i*3+0]*dNdxi[k][0] +
                         Jinv[i*3+1]*dNdxi[k][1] +
                         Jinv[i*3+2]*dNdxi[k][2];
        }
    }

    // Strain: ε_ij = 0.5*(∂u_i/∂x_j + ∂u_j/∂x_i)
    double dudx[3][3] = {{0,0,0},{0,0,0},{0,0,0}};
    for (int k = 0; k < 8; ++k) {
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                dudx[i][j] += disp[k][i] * dNdx[k][j];
            }
        }
    }

    double exx = dudx[0][0];
    double eyy = dudx[1][1];
    double ezz = dudx[2][2];
    double exy = 0.5*(dudx[0][1] + dudx[1][0]);
    double eyz = 0.5*(dudx[1][2] + dudx[2][1]);
    double exz = 0.5*(dudx[0][2] + dudx[2][0]);

    return vonMisesStrain(exx, eyy, ezz, exy, eyz, exz);
}

/// Compute element-centroid total strain for Tet4 (constant strain element)
double computeTet4Strain(const double coords[][3], const double disp[][3])
{
    // For Tet4, strain is constant. Use the inverse of the coordinate matrix.
    // [x2-x1, x3-x1, x4-x1]^-1 gives dN/dx directly
    Mat3 A;
    for (int j = 0; j < 3; ++j) {
        A[0*3+j] = coords[1][j] - coords[0][j];
        A[1*3+j] = coords[2][j] - coords[0][j];
        A[2*3+j] = coords[3][j] - coords[0][j];
    }
    Mat3 Ainv;
    if (std::abs(invert3x3(A, Ainv)) < 1e-30) return 0.0;

    // du/dx = [u2-u1, u3-u1, u4-u1]^T * Ainv^T
    // but more directly: du_i/dx_j = Σ_k (u_{k+1,i} - u_{0,i}) * Ainv_{k,j}
    double dudx[3][3] = {{0,0,0},{0,0,0},{0,0,0}};
    for (int i = 0; i < 3; ++i) {
        double du[3] = { disp[1][i]-disp[0][i], disp[2][i]-disp[0][i], disp[3][i]-disp[0][i] };
        for (int j = 0; j < 3; ++j) {
            dudx[i][j] = du[0]*Ainv[0*3+j] + du[1]*Ainv[1*3+j] + du[2]*Ainv[2*3+j];
        }
    }

    double exx = dudx[0][0], eyy = dudx[1][1], ezz = dudx[2][2];
    double exy = 0.5*(dudx[0][1]+dudx[1][0]);
    double eyz = 0.5*(dudx[1][2]+dudx[2][1]);
    double exz = 0.5*(dudx[0][2]+dudx[2][0]);
    return vonMisesStrain(exx, eyy, ezz, exy, eyz, exz);
}

/// Compute element-centroid total strain for Quad4 shell (in-plane + bending approximation)
/// Uses 2D isoparametric shape functions at ξ=η=0 in local tangent plane
double computeQuad4Strain(const double coords[][3], const double disp[][3])
{
    // Build local coordinate system from element edges
    double e1[3], e2[3], en[3];
    for (int i = 0; i < 3; ++i) {
        e1[i] = (coords[1][i] - coords[0][i]) + (coords[2][i] - coords[3][i]);  // avg ξ-direction
        e2[i] = (coords[3][i] - coords[0][i]) + (coords[2][i] - coords[1][i]);  // avg η-direction
    }
    // Normal = e1 × e2
    en[0] = e1[1]*e2[2] - e1[2]*e2[1];
    en[1] = e1[2]*e2[0] - e1[0]*e2[2];
    en[2] = e1[0]*e2[1] - e1[1]*e2[0];
    double nlen = std::sqrt(en[0]*en[0]+en[1]*en[1]+en[2]*en[2]);
    if (nlen < 1e-30) return 0.0;
    for (int i = 0; i < 3; ++i) en[i] /= nlen;

    // Re-orthogonalize e1, e2
    double e1len = std::sqrt(e1[0]*e1[0]+e1[1]*e1[1]+e1[2]*e1[2]);
    if (e1len < 1e-30) return 0.0;
    for (int i = 0; i < 3; ++i) e1[i] /= e1len;
    // e2 = en × e1
    e2[0] = en[1]*e1[2] - en[2]*e1[1];
    e2[1] = en[2]*e1[0] - en[0]*e1[2];
    e2[2] = en[0]*e1[1] - en[1]*e1[0];

    // Project to 2D local coordinates
    double lc[4][2], ld[4][2]; // local coords, local displacements (in-plane)
    double cx = 0, cy = 0, cz = 0;
    for (int i = 0; i < 4; ++i) { cx += coords[i][0]; cy += coords[i][1]; cz += coords[i][2]; }
    cx *= 0.25; cy *= 0.25; cz *= 0.25;

    for (int i = 0; i < 4; ++i) {
        double dx = coords[i][0]-cx, dy = coords[i][1]-cy, dz = coords[i][2]-cz;
        lc[i][0] = dx*e1[0] + dy*e1[1] + dz*e1[2];
        lc[i][1] = dx*e2[0] + dy*e2[1] + dz*e2[2];
        ld[i][0] = disp[i][0]*e1[0] + disp[i][1]*e1[1] + disp[i][2]*e1[2];
        ld[i][1] = disp[i][0]*e2[0] + disp[i][1]*e2[1] + disp[i][2]*e2[2];
    }

    // Quad4 shape function derivatives at ξ=η=0
    static const double sgn[4][2] = {{-1,-1},{+1,-1},{+1,+1},{-1,+1}};
    double dNdxi[4][2];
    for (int i = 0; i < 4; ++i) {
        dNdxi[i][0] = sgn[i][0] * 0.25;  // at η=0: (1±η)/4 = 1/4
        dNdxi[i][1] = sgn[i][1] * 0.25;
    }

    // 2D Jacobian
    double J[2][2] = {{0,0},{0,0}};
    for (int k = 0; k < 4; ++k) {
        J[0][0] += dNdxi[k][0]*lc[k][0]; J[0][1] += dNdxi[k][0]*lc[k][1];
        J[1][0] += dNdxi[k][1]*lc[k][0]; J[1][1] += dNdxi[k][1]*lc[k][1];
    }
    double det2 = J[0][0]*J[1][1] - J[0][1]*J[1][0];
    if (std::abs(det2) < 1e-30) return 0.0;
    double id = 1.0/det2;
    double Ji[2][2] = {{J[1][1]*id, -J[0][1]*id}, {-J[1][0]*id, J[0][0]*id}};

    // dN/dx_local
    double dNdx[4][2];
    for (int k = 0; k < 4; ++k) {
        dNdx[k][0] = Ji[0][0]*dNdxi[k][0] + Ji[0][1]*dNdxi[k][1];
        dNdx[k][1] = Ji[1][0]*dNdxi[k][0] + Ji[1][1]*dNdxi[k][1];
    }

    // In-plane strain
    double dudx_l[2][2] = {{0,0},{0,0}};
    for (int k = 0; k < 4; ++k) {
        dudx_l[0][0] += ld[k][0]*dNdx[k][0];
        dudx_l[0][1] += ld[k][0]*dNdx[k][1];
        dudx_l[1][0] += ld[k][1]*dNdx[k][0];
        dudx_l[1][1] += ld[k][1]*dNdx[k][1];
    }

    double exx = dudx_l[0][0];
    double eyy = dudx_l[1][1];
    double exy = 0.5*(dudx_l[0][1] + dudx_l[1][0]);
    // Plane stress: ezz ≈ 0 for thin shells
    return vonMisesStrain(exx, eyy, 0.0, exy, 0.0, 0.0);
}

/// Generic strain for degenerate hex (penta6, pyram5): use first 4 nodes as tet4 fallback
double computeDegenerateStrain(const double coords[][3], const double disp[][3], int nn)
{
    if (nn >= 4) return computeTet4Strain(coords, disp);
    return 0.0;
}

} // anonymous namespace (strain helpers)

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

    // Total strain from displacement gradient — element-based
    if (field == FieldSelector::TotalStrain) {
        if (control_.IU != 1 || state.node_displacements.empty()) {
            global_min_ = 0.0; global_max_ = 1.0;
            return;
        }

        // Helper: get deformed coords and displacements for an element
        auto getNodeData = [&](int32_t nid, double pos[3], double disp[3]) -> bool {
            int32_t idx = nodeIndex(nid);
            if (idx < 0 || idx >= numnp) return false;
            size_t bi = static_cast<size_t>(idx) * 3;
            if (bi + 2 >= state.node_displacements.size()) return false;
            // Reference coords (undeformed)
            if (static_cast<size_t>(idx) >= mesh_.nodes.size()) return false;
            pos[0] = mesh_.nodes[idx].x;
            pos[1] = mesh_.nodes[idx].y;
            pos[2] = mesh_.nodes[idx].z;
            disp[0] = state.node_displacements[bi+0];
            disp[1] = state.node_displacements[bi+1];
            disp[2] = state.node_displacements[bi+2];
            return true;
        };

        // Solid elements
        for (size_t ei = 0; ei < mesh_.solids.size(); ++ei) {
            const auto& elem = mesh_.solids[ei];
            if (!del_solids.empty() && del_solids.count(elem.id)) continue;
            int32_t pid = (ei < mesh_.solid_parts.size()) ? mesh_.solid_parts[ei] : 0;
            if (!target.empty() && !target.matches(pid, "")) continue;

            int nn = static_cast<int>(elem.node_ids.size());
            double coords[8][3], disp[8][3];
            bool ok = true;
            int actual_nn = std::min(nn, 8);
            for (int i = 0; i < actual_nn && ok; ++i)
                ok = getNodeData(elem.node_ids[i], coords[i], disp[i]);
            if (!ok) continue;

            double val = 0.0;
            if (actual_nn == 8) {
                // Check for degenerate hex (repeated nodes → tet/penta/pyram)
                bool degen = false;
                for (int i = 0; i < 8 && !degen; ++i)
                    for (int j = i+1; j < 8 && !degen; ++j)
                        if (elem.node_ids[i] == elem.node_ids[j]) degen = true;
                val = degen ? computeDegenerateStrain(coords, disp, actual_nn)
                            : computeHex8Strain(coords, disp);
            } else if (actual_nn == 4) {
                val = computeTet4Strain(coords, disp);
            } else {
                val = computeDegenerateStrain(coords, disp, actual_nn);
            }

            for (int i = 0; i < actual_nn; ++i) {
                int32_t idx = nodeIndex(elem.node_ids[i]);
                if (idx >= 0 && idx < numnp) {
                    node_sum_[idx]   += val;
                    node_count_[idx] += 1;
                }
            }
        }

        // Thick shell elements (8-node: treat as hex8)
        for (size_t ei = 0; ei < mesh_.thick_shells.size(); ++ei) {
            const auto& elem = mesh_.thick_shells[ei];
            if (!del_thick.empty() && del_thick.count(elem.id)) continue;
            int32_t pid = (ei < mesh_.thick_shell_parts.size()) ? mesh_.thick_shell_parts[ei] : 0;
            if (!target.empty() && !target.matches(pid, "")) continue;

            int nn = std::min(static_cast<int>(elem.node_ids.size()), 8);
            double coords[8][3], disp[8][3];
            bool ok = true;
            for (int i = 0; i < nn && ok; ++i)
                ok = getNodeData(elem.node_ids[i], coords[i], disp[i]);
            if (!ok) continue;

            double val = (nn == 8) ? computeHex8Strain(coords, disp)
                                   : computeDegenerateStrain(coords, disp, nn);

            for (int i = 0; i < nn; ++i) {
                int32_t idx = nodeIndex(elem.node_ids[i]);
                if (idx >= 0 && idx < numnp) {
                    node_sum_[idx]   += val;
                    node_count_[idx] += 1;
                }
            }
        }

        // Shell elements (4-node quad)
        for (size_t ei = 0; ei < mesh_.shells.size(); ++ei) {
            const auto& elem = mesh_.shells[ei];
            if (!del_shells.empty() && del_shells.count(elem.id)) continue;
            int32_t pid = (ei < mesh_.shell_parts.size()) ? mesh_.shell_parts[ei] : 0;
            if (!target.empty() && !target.matches(pid, "")) continue;

            int nn = std::min(static_cast<int>(elem.node_ids.size()), 4);
            double coords[4][3], disp[4][3];
            bool ok = true;
            for (int i = 0; i < nn && ok; ++i)
                ok = getNodeData(elem.node_ids[i], coords[i], disp[i]);
            if (!ok) continue;

            double val = (nn == 4) ? computeQuad4Strain(coords, disp)
                                   : 0.0;  // Tri3: would need separate handling

            for (int i = 0; i < nn; ++i) {
                int32_t idx = nodeIndex(elem.node_ids[i]);
                if (idx >= 0 && idx < numnp) {
                    node_sum_[idx]   += val;
                    node_count_[idx] += 1;
                }
            }
        }

        // Divide + global range
        double mn = 1e300, mx = -1e300;
        for (int32_t i = 0; i < numnp; ++i) {
            if (node_count_[i] > 0) {
                double v = node_sum_[i] / static_cast<double>(node_count_[i]);
                node_sum_[i] = v;
                if (v < mn) mn = v;
                if (v > mx) mx = v;
            }
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
        case FieldSelector::TotalStrain:
        case FieldSelector::DisplacementMagnitude:
            return 0.0;  // handled separately in compute()
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
