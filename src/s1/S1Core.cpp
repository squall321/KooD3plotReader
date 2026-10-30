// S1 경량 추출본의 기하 핵심 구현 — StepForge 겉면 규칙 이식 · von Mises · 바닥 평면 맞춤
#include "kood3plot/s1/S1Core.hpp"

#include <algorithm>
#include <cmath>
#include <map>
#include <stdexcept>
#include <unordered_map>

namespace kood3plot {
namespace s1 {

namespace {

// 8슬롯 육면체의 면(0부터) — 양의 야코비안에서 바깥 법선 차례 (StepForge HEX_FACES)
constexpr int HEX_FACES[6][4] = {{0, 3, 2, 1}, {4, 5, 6, 7}, {0, 1, 5, 4},
                                 {1, 2, 6, 5}, {2, 3, 7, 6}, {3, 0, 4, 7}};
// 사면체 (a,b,c,d) 의 면 (StepForge TET_FACES)
constexpr int TET_FACES[4][3] = {{0, 3, 2}, {0, 2, 1}, {0, 1, 3}, {1, 2, 3}};

// 면 고리에서 이어진 같은 절점을 하나로(고리이므로 끝과 처음도) — StepForge _ring
std::vector<int32_t> ring(const std::vector<int32_t>& face) {
    std::vector<int32_t> out;
    for (int32_t n : face) {
        if (out.empty() || out.back() != n) out.push_back(n);
    }
    while (out.size() > 1 && out.front() == out.back()) out.pop_back();
    return out;
}

std::vector<std::vector<int32_t>> hexRings(const std::array<int32_t, 8>& c) {
    std::vector<std::vector<int32_t>> rings;
    for (const auto& f : HEX_FACES) {
        auto r = ring({c[f[0]], c[f[1]], c[f[2]], c[f[3]]});
        if (r.size() >= 3) rings.push_back(std::move(r));
    }
    return rings;
}

size_t distinctCount(const std::array<int32_t, 8>& c) {
    std::set<int32_t> s(c.begin(), c.end());
    return s.size();
}

// 알려진 축퇴 차례 밖의 요소 — 접은 면이 닫힌 다면체이고 꼴이 사면체·피라미드·쐐기면 그 꼴 (StepForge _general_form)
bool generalForm(const std::array<int32_t, 8>& c, SolidForm& out) {
    const size_t distinct = distinctCount(c);
    if (distinct == 4) {
        out = SolidForm::Tet;
        return true;
    }
    const auto rings = hexRings(c);
    for (const auto& r : rings) {
        std::set<int32_t> u(r.begin(), r.end());
        if (u.size() != r.size()) return false;  // 고리 안에 떨어진 같은 절점 — 면이 꼬였다
    }
    std::map<std::pair<int32_t, int32_t>, int> edges;
    for (const auto& r : rings) {
        for (size_t k = 0; k < r.size(); ++k) {
            int32_t a = r[k], b = r[(k + 1) % r.size()];
            if (a > b) std::swap(a, b);
            ++edges[{a, b}];
        }
    }
    for (const auto& e : edges) {
        if (e.second != 2) return false;  // 닫힌 다면체가 아니다
    }
    std::vector<size_t> sides;
    for (const auto& r : rings) sides.push_back(r.size());
    std::sort(sides.begin(), sides.end());
    if (distinct == 6 && sides == std::vector<size_t>{3, 3, 4, 4, 4}) {
        out = SolidForm::Wedge;
        return true;
    }
    if (distinct == 5 && sides == std::vector<size_t>{3, 3, 3, 3, 4}) {
        out = SolidForm::Pyramid;
        return true;
    }
    return false;
}

double tripleProduct(const data::Node& a, const data::Node& b, const data::Node& c) {
    // a · (b × c)
    const double cx = b.y * c.z - b.z * c.y;
    const double cy = b.z * c.x - b.x * c.z;
    const double cz = b.x * c.y - b.y * c.x;
    return a.x * cx + a.y * cy + a.z * cz;
}

// 면 고리들로 둘러싼 부피 ×6 (발산 정리, 부채꼴 삼각 분할). 바깥 차례면 양수.
double signedVolume6(const std::vector<std::vector<int32_t>>& faces,
                     const std::vector<data::Node>& nodes) {
    double v = 0.0;
    for (const auto& f : faces) {
        for (size_t k = 1; k + 1 < f.size(); ++k) {
            v += tripleProduct(nodes[f[0]], nodes[f[k]], nodes[f[k + 1]]);
        }
    }
    return v;
}

struct KeyHash {
    size_t operator()(const std::array<int32_t, 4>& k) const {
        uint64_t h = 1469598103934665603ULL;
        for (int32_t v : k) {
            h ^= static_cast<uint64_t>(static_cast<uint32_t>(v));
            h *= 1099511628211ULL;
        }
        return static_cast<size_t>(h);
    }
};

}  // namespace

SolidForm solidForm(const std::array<int32_t, 8>& c) {
    const size_t distinct = distinctCount(c);
    if (distinct == 8) return SolidForm::Hex;
    if (c[3] == c[4] && c[4] == c[5] && c[5] == c[6] && c[6] == c[7]) {
        std::set<int32_t> first4(c.begin(), c.begin() + 4);
        if (first4.size() == 4) return SolidForm::Tet;
    }
    if (distinct == 6 && c[2] == c[3] && c[6] == c[7]) return SolidForm::Wedge;
    if (distinct == 5 && c[4] == c[5] && c[5] == c[6] && c[6] == c[7]) return SolidForm::Pyramid;
    SolidForm g;
    if (generalForm(c, g)) return g;
    std::string list;
    for (int32_t v : c) list += (list.empty() ? "" : ",") + std::to_string(v);
    throw std::runtime_error("모르는 솔리드 요소 꼴(서로 다른 절점 " + std::to_string(distinct) +
                             "개: " + list + ") — 육면체·사면체·쐐기·피라미드만 읽는다");
}

std::vector<std::vector<int32_t>> solidFaces(const std::array<int32_t, 8>& c, SolidForm* form_out) {
    const SolidForm form = solidForm(c);
    if (form_out) *form_out = form;
    std::vector<std::vector<int32_t>> faces;
    if (form == SolidForm::Tet) {
        // n4=n5~n8 꼴이면 앞 넷, 그 밖(고유 절점 넷)은 처음 나온 차례의 고유 절점 넷
        std::vector<int32_t> t;
        std::set<int32_t> first4(c.begin(), c.begin() + 4);
        if (first4.size() == 4) {
            t.assign(c.begin(), c.begin() + 4);
        } else {
            for (int32_t v : c) {
                if (std::find(t.begin(), t.end(), v) == t.end()) t.push_back(v);
            }
            t.resize(4);
        }
        for (const auto& f : TET_FACES) faces.push_back({t[f[0]], t[f[1]], t[f[2]]});
        return faces;
    }
    return hexRings(c);
}

Surface extractSurface(const data::Mesh& mesh, const std::set<int32_t>& excluded_parts) {
    Surface out;

    struct Entry {
        std::vector<int32_t> ring;
        size_t solid_index;
        int32_t part;
        int count = 0;
        bool shared_across_parts = false;
    };
    std::vector<Entry> entries;
    std::unordered_map<std::array<int32_t, 4>, size_t, KeyHash> index;

    for (size_t s = 0; s < mesh.solids.size(); ++s) {
        const int32_t part = s < mesh.solid_parts.size() ? mesh.solid_parts[s] : 0;
        if (excluded_parts.count(part)) continue;
        const auto& ids = mesh.solids[s].node_ids;
        if (ids.size() < 8) {
            throw std::runtime_error("솔리드 요소 " + std::to_string(s) + " 의 절점이 8칸이 아니다");
        }
        std::array<int32_t, 8> c{};
        for (int k = 0; k < 8; ++k) {
            c[k] = ids[k] - 1;  // 연결성은 1-based 내부 순번
            if (c[k] < 0 || static_cast<size_t>(c[k]) >= mesh.nodes.size()) {
                throw std::runtime_error("솔리드 요소 " + std::to_string(s) + " 의 절점 순번이 범위를 벗어난다");
            }
            out.device_nodes.insert(c[k]);
        }
        ++out.n_device_elems;

        auto faces = solidFaces(c);
        if (signedVolume6(faces, mesh.nodes) < 0.0) {
            for (auto& f : faces) std::reverse(f.begin(), f.end());
            ++out.n_flipped_elems;
        }
        for (auto& f : faces) {
            std::array<int32_t, 4> key{-1, -1, -1, -1};
            std::vector<int32_t> sorted(f.begin(), f.end());
            std::sort(sorted.begin(), sorted.end());
            sorted.erase(std::unique(sorted.begin(), sorted.end()), sorted.end());
            for (size_t k = 0; k < sorted.size() && k < 4; ++k) key[k] = sorted[k];
            auto it = index.find(key);
            if (it == index.end()) {
                index.emplace(key, entries.size());
                entries.push_back({std::move(f), s, part, 1, false});
            } else {
                Entry& e = entries[it->second];
                ++e.count;
                if (e.count > 2) {
                    throw std::runtime_error("면 하나를 요소 셋 이상이 공유한다(비다양체) — 요소 순번 " +
                                             std::to_string(e.solid_index) + "·" + std::to_string(s));
                }
                if (e.part != part) e.shared_across_parts = true;
            }
        }
    }

    for (const auto& e : entries) {
        if (e.count == 2 && e.shared_across_parts) ++out.n_inter_part_shared_faces;
        if (e.count != 1) continue;
        SurfaceFace sf;
        for (size_t k = 0; k < e.ring.size() && k < 4; ++k) sf.nodes[k] = e.ring[k];
        sf.solid_index = e.solid_index;
        out.faces.push_back(sf);
    }

    for (size_t i = 0; i < mesh.shells.size(); ++i) {
        const int32_t part = i < mesh.shell_parts.size() ? mesh.shell_parts[i] : 0;
        if (!excluded_parts.count(part)) ++out.n_shell_elems_skipped;
    }
    for (size_t i = 0; i < mesh.thick_shells.size(); ++i) {
        const int32_t part = i < mesh.thick_shell_parts.size() ? mesh.thick_shell_parts[i] : 0;
        if (!excluded_parts.count(part)) ++out.n_shell_elems_skipped;
    }
    return out;
}

double solidVonMises(const data::StateData& state, size_t elem_index, int nv3d) {
    const size_t base = elem_index * static_cast<size_t>(nv3d);
    if (nv3d < 6 || base + 5 >= state.solid_data.size()) return 0.0;
    const double sxx = state.solid_data[base + 0];
    const double syy = state.solid_data[base + 1];
    const double szz = state.solid_data[base + 2];
    const double sxy = state.solid_data[base + 3];
    const double syz = state.solid_data[base + 4];
    const double szx = state.solid_data[base + 5];
    const double d = (sxx - syy) * (sxx - syy) + (syy - szz) * (syy - szz) + (szz - sxx) * (szz - sxx);
    return std::sqrt(0.5 * d + 3.0 * (sxy * sxy + syz * syz + szx * szx));
}

V3 smallestEigenvector(const double m_in[3][3]) {
    double a[3][3], v[3][3] = {{1, 0, 0}, {0, 1, 0}, {0, 0, 1}};
    for (int i = 0; i < 3; ++i)
        for (int j = 0; j < 3; ++j) a[i][j] = m_in[i][j];
    for (int sweep = 0; sweep < 64; ++sweep) {
        const double off = a[0][1] * a[0][1] + a[0][2] * a[0][2] + a[1][2] * a[1][2];
        if (off < 1e-30) break;
        for (int p = 0; p < 2; ++p) {
            for (int q = p + 1; q < 3; ++q) {
                if (std::abs(a[p][q]) < 1e-300) continue;
                const double theta = (a[q][q] - a[p][p]) / (2.0 * a[p][q]);
                const double t = (theta >= 0 ? 1.0 : -1.0) / (std::abs(theta) + std::sqrt(theta * theta + 1.0));
                const double c = 1.0 / std::sqrt(t * t + 1.0), s = t * c;
                for (int k = 0; k < 3; ++k) {
                    const double akp = a[k][p], akq = a[k][q];
                    a[k][p] = c * akp - s * akq;
                    a[k][q] = s * akp + c * akq;
                }
                for (int k = 0; k < 3; ++k) {
                    const double apk = a[p][k], aqk = a[q][k];
                    a[p][k] = c * apk - s * aqk;
                    a[q][k] = s * apk + c * aqk;
                }
                for (int k = 0; k < 3; ++k) {
                    const double vkp = v[k][p], vkq = v[k][q];
                    v[k][p] = c * vkp - s * vkq;
                    v[k][q] = s * vkp + c * vkq;
                }
            }
        }
    }
    int imin = 0;
    for (int i = 1; i < 3; ++i)
        if (a[i][i] < a[imin][imin]) imin = i;
    V3 e{v[0][imin], v[1][imin], v[2][imin]};
    const double n = std::sqrt(e.x * e.x + e.y * e.y + e.z * e.z);
    return {e.x / n, e.y / n, e.z / n};
}

namespace {

void fitPlane(const std::vector<V3>& pts, const V3& toward, V3& point, V3& normal) {
    V3 c;
    for (const auto& p : pts) {
        c.x += p.x;
        c.y += p.y;
        c.z += p.z;
    }
    c.x /= pts.size();
    c.y /= pts.size();
    c.z /= pts.size();
    double m[3][3] = {{0, 0, 0}, {0, 0, 0}, {0, 0, 0}};
    for (const auto& p : pts) {
        const double d[3] = {p.x - c.x, p.y - c.y, p.z - c.z};
        for (int i = 0; i < 3; ++i)
            for (int j = 0; j < 3; ++j) m[i][j] += d[i] * d[j];
    }
    V3 n = smallestEigenvector(m);
    if ((toward.x - c.x) * n.x + (toward.y - c.y) * n.y + (toward.z - c.z) * n.z < 0) {
        n = {-n.x, -n.y, -n.z};
    }
    point = c;
    normal = n;
}

double dot(const V3& a, const V3& b) { return a.x * b.x + a.y * b.y + a.z * b.z; }

}  // namespace

FloorPlane fitFloorPlane(const std::vector<V3>& floor_nodes, const V3& device_centroid) {
    if (floor_nodes.size() < 3) throw std::runtime_error("바닥 절점이 3개 미만이다");
    V3 c, n;
    fitPlane(floor_nodes, device_centroid, c, n);

    // 법선 방향 투영으로 층을 나눠 기기에 가장 가까운(투영이 가장 큰) 층만 쓴다
    double smin = 1e300, smax = -1e300;
    std::vector<double> s(floor_nodes.size());
    for (size_t i = 0; i < floor_nodes.size(); ++i) {
        const V3 d{floor_nodes[i].x - c.x, floor_nodes[i].y - c.y, floor_nodes[i].z - c.z};
        s[i] = dot(d, n);
        smin = std::min(smin, s[i]);
        smax = std::max(smax, s[i]);
    }
    const double tol = std::max(1e-9, 0.05 * (smax - smin));
    std::vector<V3> layer;
    for (size_t i = 0; i < floor_nodes.size(); ++i) {
        if (s[i] >= smax - tol) layer.push_back(floor_nodes[i]);
    }
    if (layer.size() < 3) throw std::runtime_error("바닥의 기기 쪽 층 절점이 3개 미만이다");

    FloorPlane fp;
    fitPlane(layer, device_centroid, fp.point, fp.normal);
    fp.n_layer_nodes = layer.size();
    for (const auto& p : layer) {
        const V3 d{p.x - fp.point.x, p.y - fp.point.y, p.z - fp.point.z};
        fp.flatness = std::max(fp.flatness, std::abs(dot(d, fp.normal)));
    }
    return fp;
}

}  // namespace s1
}  // namespace kood3plot
