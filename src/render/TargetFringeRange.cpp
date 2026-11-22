// LS-PrePost 타깃 렌더에 걸 색 범위를 타깃 파트의 값으로 내는 도우미 — 전 상태, 요소 값은 LS-PrePost 의 「max IP. value」
#include "kood3plot/render/TargetFringeRange.h"

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/VectorMath.hpp"
#include "kood3plot/data/ShellLayerLayout.hpp"
#include "kood3plot/data/SolidIpLayout.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <unordered_map>
#include <unordered_set>

namespace kood3plot {
namespace render {
namespace {

constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();

enum class Kind { Element, Node, None };

Kind kindOf(FringeType t) {
    switch (t) {
        case FringeType::VON_MISES:
        case FringeType::EFFECTIVE_PLASTIC_STRAIN:
        case FringeType::PRESSURE:
        case FringeType::MAX_SHEAR_STRESS:
            return Kind::Element;
        case FringeType::DISPLACEMENT:
        case FringeType::VELOCITY:
        case FringeType::ACCELERATION:
            return Kind::Node;
        default:
            return Kind::None;
    }
}

/// 적분점(층) 하나의 값 — p 부터 응력 6(+ ε_p). 없는 값(ε_p 를 적지 않은 덱)은 NaN
double ipValue(const double* p, size_t words, FringeType t) {
    if (words < 6) return kNaN;
    switch (t) {
        case FringeType::VON_MISES: {
            const double a = p[0] - p[1], b = p[1] - p[2], c = p[2] - p[0];
            return std::sqrt(0.5 * (a * a + b * b + c * c) + 3.0 * (p[3] * p[3] + p[4] * p[4] + p[5] * p[5]));
        }
        case FringeType::EFFECTIVE_PLASTIC_STRAIN:
            return words >= 7 ? p[6] : kNaN;
        case FringeType::PRESSURE:
            return -(p[0] + p[1] + p[2]) / 3.0;
        case FringeType::MAX_SHEAR_STRESS:
            return analysis::StressTensor(p[0], p[1], p[2], p[3], p[4], p[5]).maxShear();
        default:
            return kNaN;
    }
}

/// NaN 을 건너뛰는 최대
double maxOf(double a, double b) {
    if (std::isnan(a)) return b;
    if (std::isnan(b)) return a;
    return std::max(a, b);
}

struct Acc {
    double lo = std::numeric_limits<double>::infinity();
    double hi = -std::numeric_limits<double>::infinity();
    void add(double v) {
        if (!std::isfinite(v)) return;
        lo = std::min(lo, v);
        hi = std::max(hi, v);
    }
};

std::unordered_set<int32_t> asSet(const std::vector<int32_t>& v) { return {v.begin(), v.end()}; }

}  // namespace

std::map<int32_t, FringeRange> partFringeRanges(const data::Mesh& mesh, const data::ControlData& control,
                                                size_t num_states, const StateSource& states,
                                                const std::vector<int32_t>& parts, FringeType type)
{
    std::map<int32_t, FringeRange> out;
    const Kind kind = kindOf(type);
    if (kind == Kind::None || parts.empty()) return out;

    std::unordered_map<int32_t, Acc> acc;
    for (int32_t pid : parts) acc[pid];
    const auto wanted = [&](int32_t pid) { return acc.count(pid) > 0; };

    // 절점 값 — 타깃 요소(빔 포함)의 절점
    std::unordered_map<int32_t, std::vector<int32_t>> part_nodes;   // 파트 → 0부터 절점 순번
    if (kind == Kind::Node) {
        const auto collect = [&](const std::vector<Element>& els, const std::vector<int32_t>& eparts) {
            for (size_t i = 0; i < els.size() && i < eparts.size(); ++i) {
                if (!wanted(eparts[i])) continue;
                std::vector<int32_t>& v = part_nodes[eparts[i]];
                for (int32_t n : els[i].node_ids) {
                    if (n >= 1 && static_cast<size_t>(n) <= mesh.nodes.size()) v.push_back(n - 1);
                }
            }
        };
        collect(mesh.solids, mesh.solid_parts);
        collect(mesh.thick_shells, mesh.thick_shell_parts);
        collect(mesh.shells, mesh.shell_parts);
        collect(mesh.beams, mesh.beam_parts);
        for (auto& kv : part_nodes) {
            std::sort(kv.second.begin(), kv.second.end());
            kv.second.erase(std::unique(kv.second.begin(), kv.second.end()), kv.second.end());
        }
    }
    const bool node_data = (type == FringeType::DISPLACEMENT && control.IU == 1) ||
                           (type == FringeType::VELOCITY && control.IV == 1) ||
                           (type == FringeType::ACCELERATION && control.IA == 1);

    const data::SolidIpLayout solid = data::SolidIpLayout::from(control);
    const size_t solid_words = control.IOSOL[1] ? 7 : 6;
    const data::ShellLayerLayout shell = data::ShellLayerLayout::from(control, true);
    const data::ShellLayerLayout tshell = data::ShellLayerLayout::from(control, false);

    // 층 요소(셸 · 두꺼운 셸) — 층 배치를 믿을 때만
    const auto layered = [&](const std::vector<Element>& els, const std::vector<int32_t>& eparts,
                             const std::vector<double>& data, int nv, const data::ShellLayerLayout& L,
                             const std::vector<int32_t>& deleted) {
        if (L.layers <= 0 || nv <= 0) return;
        const std::unordered_set<int32_t> dead = asSet(deleted);
        for (size_t ei = 0; ei < els.size() && ei < eparts.size(); ++ei) {
            if (!wanted(eparts[ei]) || dead.count(static_cast<int32_t>(ei) + 1)) continue;
            const size_t base = ei * static_cast<size_t>(nv);
            if (base + static_cast<size_t>(nv) > data.size()) continue;
            const double* blk = data.data() + base;
            double v = kNaN;
            for (int l = 0; l < L.layers; ++l) v = maxOf(v, ipValue(blk + static_cast<std::ptrdiff_t>(l) * L.stride, L.words, type));
            acc[eparts[ei]].add(v);
        }
    };

    data::StateData st;
    for (size_t si = 0; si < num_states; ++si) {
        if (!states(si, st)) break;
        if (kind == Kind::Node) {
            if (!node_data) break;
            const std::vector<double>& arr = type == FringeType::DISPLACEMENT ? st.node_displacements
                                           : type == FringeType::VELOCITY     ? st.node_velocities
                                                                              : st.node_accelerations;
            for (const auto& kv : part_nodes) {
                for (int32_t idx : kv.second) {
                    const size_t b = static_cast<size_t>(idx) * 3;
                    if (b + 2 >= arr.size()) continue;
                    double x = arr[b], y = arr[b + 1], z = arr[b + 2];
                    if (type == FringeType::DISPLACEMENT) {   // IU 1 이면 node_displacements 는 현재 좌표다
                        x -= mesh.nodes[idx].x;
                        y -= mesh.nodes[idx].y;
                        z -= mesh.nodes[idx].z;
                    }
                    acc[kv.first].add(std::sqrt(x * x + y * y + z * z));
                }
            }
            continue;
        }
        // 솔리드 — 값이 실린 적분점 자리의 최대(한 자리 덱은 앞 워드)
        if (control.NV3D > 0) {
            const std::unordered_set<int32_t> dead = asSet(st.deleted_solids);
            const size_t nv = static_cast<size_t>(control.NV3D);
            for (size_t ei = 0; ei < mesh.solids.size() && ei < mesh.solid_parts.size(); ++ei) {
                if (!wanted(mesh.solid_parts[ei]) || dead.count(static_cast<int32_t>(ei) + 1)) continue;
                const size_t base = ei * nv;
                if (base + nv > st.solid_data.size()) continue;
                const double* blk = st.solid_data.data() + base;
                double v = kNaN;
                if (solid.nip > 1) {
                    const data::SolidIpSet set = data::solidIps(blk, solid);
                    for (int k = 0; k < set.n; ++k)
                        v = maxOf(v, ipValue(blk + static_cast<std::ptrdiff_t>(set.ip[k]) * solid.stride, solid_words, type));
                } else {
                    v = ipValue(blk, std::min(nv, solid_words), type);
                }
                acc[mesh.solid_parts[ei]].add(v);
            }
        }
        layered(mesh.thick_shells, mesh.thick_shell_parts, st.thick_shell_data, control.NV3DT, tshell, st.deleted_thick_shells);
        layered(mesh.shells, mesh.shell_parts, st.shell_data, control.NV2D, shell, st.deleted_shells);
    }

    for (const auto& kv : acc) {
        FringeRange r;
        if (kv.second.hi > kv.second.lo) {
            r.ok = true;
            r.min = kv.second.lo;
            r.max = kv.second.hi;
        }
        out[kv.first] = r;
    }
    return out;
}

std::map<int32_t, FringeRange> partFringeRanges(D3plotReader& reader, const std::vector<int32_t>& parts, FringeType type)
{
    if (kindOf(type) == Kind::None || parts.empty()) return {};
    const data::Mesh mesh = reader.read_mesh();
    const data::ControlData& control = reader.get_control_data();
    const size_t n = reader.get_num_states();
    return partFringeRanges(mesh, control, n, [&](size_t i, data::StateData& out) {
        out = reader.read_state(i);
        return true;
    }, parts, type);
}

FringeRange mergeRanges(const std::map<int32_t, FringeRange>& ranges, const std::vector<int32_t>& parts)
{
    FringeRange m;
    for (int32_t pid : parts) {
        const auto it = ranges.find(pid);
        if (it == ranges.end() || !it->second.ok) continue;
        m.min = m.ok ? std::min(m.min, it->second.min) : it->second.min;
        m.max = m.ok ? std::max(m.max, it->second.max) : it->second.max;
        m.ok = true;
    }
    return m;
}

}  // namespace render
}  // namespace kood3plot
