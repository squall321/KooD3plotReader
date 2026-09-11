// 파트 내 상위 백분위 요소의 공간 군집화 — 기하 계산과 군집 알고리즘 구현
#include "kood3plot/analysis/HotspotClusterAnalyzer.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <map>
#include <functional>
#include <limits>
#include <cstdint>
#include <unordered_map>
#include <utility>
#include <vector>

namespace kood3plot {
namespace analysis {

// ── 기준량 이름 왕복 ─────────────────────────────────────────
bool parseHotspotCriterion(const std::string& name, HotspotCriterion& out) {
    std::string k;
    k.reserve(name.size());
    for (char ch : name) {
        if (ch == '-' || ch == ' ') ch = '_';
        k.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(ch))));
    }
    if (k == "von_mises" || k == "vonmises" || k == "vm")            { out = HotspotCriterion::VonMises;     return true; }
    if (k == "max_principal" || k == "maxprincipal" || k == "sigma1" || k == "s1" || k == "p1")
                                                                       { out = HotspotCriterion::MaxPrincipal; return true; }
    if (k == "min_principal" || k == "minprincipal" || k == "sigma3" || k == "s3" || k == "p3")
                                                                       { out = HotspotCriterion::MinPrincipal; return true; }
    return false;
}

const char* hotspotCriterionName(HotspotCriterion c) {
    switch (c) {
        case HotspotCriterion::VonMises:     return "von_mises";
        case HotspotCriterion::MaxPrincipal: return "max_principal";
        case HotspotCriterion::MinPrincipal: return "min_principal";
    }
    return "von_mises";
}

std::vector<HotspotCriterion> parseHotspotCriteria(const std::vector<std::string>& names,
                                                   std::vector<std::string>* unknown) {
    std::vector<HotspotCriterion> out;
    for (const std::string& n : names) {
        HotspotCriterion c;
        if (!parseHotspotCriterion(n, c)) {
            if (unknown) unknown->push_back(n);
            continue;
        }
        if (std::find(out.begin(), out.end(), c) == out.end()) out.push_back(c);
    }
    return out;
}

const char* hotspotElementKindName(HotspotElementKind k) {
    switch (k) {
        case HotspotElementKind::Solid:      return "solid";
        case HotspotElementKind::ThickShell: return "thick_shell";
        case HotspotElementKind::Shell:      return "shell";
    }
    return "solid";
}

const char* hotspotStrainMeasureName(HotspotCriterion c) {
    switch (c) {
        case HotspotCriterion::VonMises:     return "equivalent";
        case HotspotCriterion::MaxPrincipal: return "max_principal";
        case HotspotCriterion::MinPrincipal: return "min_principal";
    }
    return "equivalent";
}

namespace {

// ── 3선형 육면체 등매개 사상 ──────────────────────────────────
//
// LS-DYNA hex8 절점 순서에 대응하는 기준 좌표.
//   1-4 : 하면 (ζ = -1), 반시계
//   5-8 : 상면 (ζ = +1), 반시계
constexpr double kXi[8]   = {-1, +1, +1, -1, -1, +1, +1, -1};
constexpr double kEta[8]  = {-1, -1, +1, +1, -1, -1, +1, +1};
constexpr double kZeta[8] = {-1, -1, -1, -1, +1, +1, +1, +1};

// 2점 가우스 구적점과 가중치. 각 변수 2차까지 정확한 적분에 필요한
// 최소 차수이며, det(J)(각 변수 2차)와 x·det(J)(3차) 모두 정확하다.
const double kG = 1.0 / 1.7320508075688772935;  // 1/sqrt(3)

}  // namespace

bool computeSolidVolumeAndCentroid(const Node* p,
                                   double& volume,
                                   double& cx, double& cy, double& cz) {
    volume = 0.0;
    cx = cy = cz = 0.0;

    // ── 고유 절점 수 판정 ──
    // 🔴 4고유(tet)는 등매개 구적으로 풀면 안 된다. LS-DYNA 실덱이 쓰는
    //    (A,B,C,D,D,D,D,D) 패턴은 밑면 사각형이 비평면인데 꼭짓점이 밑면
    //    모서리와 겹쳐 기하가 모호하고, det(J) 적분이 **정확히 참값의 절반**을
    //    낸다(실측). MinimumModel.k 는 43,657 요소 중 76.1% 가 이 패턴이므로
    //    분기가 없으면 부피 가중 통계 전체가 조용히 무너진다.
    //    4고유일 때는 사면체 닫힌 해석식을 쓴다 — 부피·도심 모두 정확하다.
    int uniq_idx[8];
    int nu = 0;
    for (int i = 0; i < 8; ++i) {
        bool dup = false;
        for (int j = 0; j < nu; ++j) {
            if (p[uniq_idx[j]].id == p[i].id) { dup = true; break; }
        }
        if (!dup) uniq_idx[nu++] = i;
    }

    if (nu < 4) {
        // 면적/부피가 없는 완전 축퇴 — 유효하지 않다
        return false;
    }

    if (nu == 4) {
        const Node& a = p[uniq_idx[0]];
        const Node& b = p[uniq_idx[1]];
        const Node& c = p[uniq_idx[2]];
        const Node& d = p[uniq_idx[3]];

        const double ux = b.x - a.x, uy = b.y - a.y, uz = b.z - a.z;
        const double vx = c.x - a.x, vy = c.y - a.y, vz = c.z - a.z;
        const double wx = d.x - a.x, wy = d.y - a.y, wz = d.z - a.z;

        // V = (1/6)·(b−a)·[(c−a)×(d−a)]   — 사면체 부피, 정확
        volume = (ux * (vy * wz - vz * wy)
                - uy * (vx * wz - vz * wx)
                + uz * (vx * wy - vy * wx)) / 6.0;

        if (std::abs(volume) < 1e-20) return false;

        // 사면체 도심 = 네 꼭짓점의 산술평균 — 정확
        cx = 0.25 * (a.x + b.x + c.x + d.x);
        cy = 0.25 * (a.y + b.y + c.y + d.y);
        cz = 0.25 * (a.z + b.z + c.z + d.z);
        return true;
    }

    // 5(pyramid) / 6(wedge) / 7 / 8(hex) 고유 — 등매개 2×2×2 가우스.
    // 사각뿔·쐐기·정상 육면체 모두 해석해와 일치함을 검증했다.
    double vol_acc = 0.0;
    double mx = 0.0, my = 0.0, mz = 0.0;  // ∫ x·det(J)

    for (int gi = 0; gi < 2; ++gi) {
        const double xi = (gi == 0) ? -kG : kG;
        for (int gj = 0; gj < 2; ++gj) {
            const double eta = (gj == 0) ? -kG : kG;
            for (int gk = 0; gk < 2; ++gk) {
                const double zeta = (gk == 0) ? -kG : kG;

                // 자코비안 J[row=좌표축][col=기준변수] 과 사상점 x(ξ)
                double J[3][3] = {{0, 0, 0}, {0, 0, 0}, {0, 0, 0}};
                double px = 0.0, py = 0.0, pz = 0.0;

                for (int i = 0; i < 8; ++i) {
                    const double a = 1.0 + kXi[i] * xi;
                    const double b = 1.0 + kEta[i] * eta;
                    const double c = 1.0 + kZeta[i] * zeta;

                    const double N     = 0.125 * a * b * c;
                    const double dNdxi = 0.125 * kXi[i]   * b * c;
                    const double dNdet = 0.125 * kEta[i]  * a * c;
                    const double dNdze = 0.125 * kZeta[i] * a * b;

                    const double X = p[i].x, Y = p[i].y, Z = p[i].z;

                    px += N * X;  py += N * Y;  pz += N * Z;

                    J[0][0] += dNdxi * X;  J[0][1] += dNdet * X;  J[0][2] += dNdze * X;
                    J[1][0] += dNdxi * Y;  J[1][1] += dNdet * Y;  J[1][2] += dNdze * Y;
                    J[2][0] += dNdxi * Z;  J[2][1] += dNdet * Z;  J[2][2] += dNdze * Z;
                }

                const double detJ =
                    J[0][0] * (J[1][1] * J[2][2] - J[1][2] * J[2][1]) -
                    J[0][1] * (J[1][0] * J[2][2] - J[1][2] * J[2][0]) +
                    J[0][2] * (J[1][0] * J[2][1] - J[1][1] * J[2][0]);

                // 2점 가우스의 가중치는 각 방향 1.0 이므로 곱도 1.0
                vol_acc += detJ;
                mx += px * detJ;
                my += py * detJ;
                mz += pz * detJ;
            }
        }
    }

    volume = vol_acc;

    // 부피가 0 에 가까우면 도심이 정의되지 않는다 (완전 축퇴 요소).
    // 0 으로 나누어 NaN 을 내보내는 대신 실패로 알린다.
    if (std::abs(vol_acc) < 1e-20) {
        return false;
    }

    cx = mx / vol_acc;
    cy = my / vol_acc;
    cz = mz / vol_acc;
    return true;
}

double isoparametricHexVolume(const double xyz[8][3]) {
    // computeSolidVolumeAndCentroid 의 부피 항과 동일한 구적.
    // det(J) 는 ξ,η,ζ 각각에 대해 2차이므로 2점 가우스로 정확하다.
    double vol_acc = 0.0;
    for (int gi = 0; gi < 2; ++gi) {
        const double xi = (gi == 0) ? -kG : kG;
        for (int gj = 0; gj < 2; ++gj) {
            const double eta = (gj == 0) ? -kG : kG;
            for (int gk = 0; gk < 2; ++gk) {
                const double zeta = (gk == 0) ? -kG : kG;
                double J[3][3] = {{0, 0, 0}, {0, 0, 0}, {0, 0, 0}};
                for (int i = 0; i < 8; ++i) {
                    const double a = 1.0 + kXi[i] * xi;
                    const double b = 1.0 + kEta[i] * eta;
                    const double c = 1.0 + kZeta[i] * zeta;
                    const double dNdxi = 0.125 * kXi[i]   * b * c;
                    const double dNdet = 0.125 * kEta[i]  * a * c;
                    const double dNdze = 0.125 * kZeta[i] * a * b;
                    for (int r = 0; r < 3; ++r) {
                        J[r][0] += dNdxi * xyz[i][r];
                        J[r][1] += dNdet * xyz[i][r];
                        J[r][2] += dNdze * xyz[i][r];
                    }
                }
                vol_acc +=
                    J[0][0] * (J[1][1] * J[2][2] - J[1][2] * J[2][1]) -
                    J[0][1] * (J[1][0] * J[2][2] - J[1][2] * J[2][0]) +
                    J[0][2] * (J[1][0] * J[2][1] - J[1][1] * J[2][0]);
            }
        }
    }
    return vol_acc;
}

namespace {
// 4점 가우스-르장드르 (±0.3399810436, ±0.8611363116)
constexpr double kG4x[4] = {-0.8611363115940526, -0.3399810435848563,
                             0.3399810435848563,  0.8611363115940526};
constexpr double kG4w[4] = { 0.3478548451374538,  0.6521451548625461,
                             0.6521451548625461,  0.3478548451374538};
// 쌍선형 사각형 기준 좌표 (LS-DYNA shell 1-2-3-4 반시계)
constexpr double kQXi[4]  = {-1, +1, +1, -1};
constexpr double kQEta[4] = {-1, -1, +1, +1};
}  // namespace

bool computeShellAreaAndCentroid(const Node* p,
                                 double& area,
                                 double& cx, double& cy, double& cz) {
    area = 0.0;
    cx = cy = cz = 0.0;

    int uniq[4];
    int nu = 0;
    for (int i = 0; i < 4; ++i) {
        bool dup = false;
        for (int j = 0; j < nu; ++j) {
            if (p[uniq[j]].id == p[i].id) { dup = true; break; }
        }
        if (!dup) uniq[nu++] = i;
    }
    if (nu < 3) return false;

    if (nu == 3) {
        // 삼각형 — A = |(b−a)×(c−a)|/2, 도심 = 세 꼭짓점 평균. 정확.
        const Node& a = p[uniq[0]];
        const Node& b = p[uniq[1]];
        const Node& c = p[uniq[2]];
        const double ux = b.x - a.x, uy = b.y - a.y, uz = b.z - a.z;
        const double vx = c.x - a.x, vy = c.y - a.y, vz = c.z - a.z;
        const double nx = uy * vz - uz * vy;
        const double ny = uz * vx - ux * vz;
        const double nz = ux * vy - uy * vx;
        area = 0.5 * std::sqrt(nx * nx + ny * ny + nz * nz);
        if (!(area > 1e-30)) return false;
        cx = (a.x + b.x + c.x) / 3.0;
        cy = (a.y + b.y + c.y) / 3.0;
        cz = (a.z + b.z + c.z) / 3.0;
        return true;
    }

    // 사각형 — 4×4 가우스. 평면이면 2점으로도 정확하므로 4점은 여유이고,
    // 뒤틀린 경우의 오차를 떨어뜨린다.
    double a_acc = 0.0, mx = 0.0, my = 0.0, mz = 0.0;
    for (int gi = 0; gi < 4; ++gi) {
        const double xi = kG4x[gi];
        for (int gj = 0; gj < 4; ++gj) {
            const double eta = kG4x[gj];
            const double w = kG4w[gi] * kG4w[gj];
            double px = 0, py = 0, pz = 0;
            double tx = 0, ty = 0, tz = 0;   // x_ξ
            double sx = 0, sy = 0, sz = 0;   // x_η
            for (int i = 0; i < 4; ++i) {
                const double a = 1.0 + kQXi[i] * xi;
                const double b = 1.0 + kQEta[i] * eta;
                const double N = 0.25 * a * b;
                const double dNdxi = 0.25 * kQXi[i] * b;
                const double dNdet = 0.25 * kQEta[i] * a;
                px += N * p[i].x;      py += N * p[i].y;      pz += N * p[i].z;
                tx += dNdxi * p[i].x;  ty += dNdxi * p[i].y;  tz += dNdxi * p[i].z;
                sx += dNdet * p[i].x;  sy += dNdet * p[i].y;  sz += dNdet * p[i].z;
            }
            const double nx = ty * sz - tz * sy;
            const double ny = tz * sx - tx * sz;
            const double nz = tx * sy - ty * sx;
            const double dA = std::sqrt(nx * nx + ny * ny + nz * nz) * w;
            a_acc += dA;
            mx += px * dA; my += py * dA; mz += pz * dA;
        }
    }
    area = a_acc;
    if (!(area > 1e-30)) return false;
    cx = mx / area; cy = my / area; cz = mz / area;
    return true;
}

double hexMinFaceSeparation(const Node* p) {
    // 대면 세 쌍: (하 1234, 상 5678), (전 1265, 후 4378), (좌 1485, 우 2376)
    static const int F[6][4] = {{0, 1, 2, 3}, {4, 5, 6, 7},
                                {0, 1, 5, 4}, {3, 2, 6, 7},
                                {0, 3, 7, 4}, {1, 2, 6, 5}};
    double c[6][3];
    for (int f = 0; f < 6; ++f) {
        c[f][0] = c[f][1] = c[f][2] = 0.0;
        for (int k = 0; k < 4; ++k) {
            c[f][0] += 0.25 * p[F[f][k]].x;
            c[f][1] += 0.25 * p[F[f][k]].y;
            c[f][2] += 0.25 * p[F[f][k]].z;
        }
    }
    double h = std::numeric_limits<double>::max();
    for (int pr = 0; pr < 3; ++pr) {
        const double dx = c[2 * pr][0] - c[2 * pr + 1][0];
        const double dy = c[2 * pr][1] - c[2 * pr + 1][1];
        const double dz = c[2 * pr][2] - c[2 * pr + 1][2];
        h = std::min(h, std::sqrt(dx * dx + dy * dy + dz * dz));
    }
    return h;
}

double equivalentStress(double xx, double yy, double zz,
                        double xy, double yz, double zx) {
    const double d1 = xx - yy;
    const double d2 = yy - zz;
    const double d3 = zz - xx;
    return std::sqrt(0.5 * (d1 * d1 + d2 * d2 + d3 * d3) +
                     3.0 * (xy * xy + yz * yz + zx * zx));
}

double equivalentStrain(double xx, double yy, double zz,
                        double xy, double yz, double zx) {
    // d3plot 의 변형률은 **텐서 성분**(공학전단 γ 가 아니라 ε_ij)이다.
    // 등가변형률 정의:  ε_eq = sqrt( (2/3) · e'_ij e'_ij )
    //   e'_ij e'_ij = e'xx² + e'yy² + e'zz² + 2(exy² + eyz² + ezx²)
    // 단축 인장(비압축)에서 ε_eq = ε_axial 이 되도록 하는 표준 정의.
    const double mean = (xx + yy + zz) / 3.0;
    const double ex = xx - mean;
    const double ey = yy - mean;
    const double ez = zz - mean;
    const double sum = ex * ex + ey * ey + ez * ez +
                       2.0 * (xy * xy + yz * yz + zx * zx);
    return std::sqrt((2.0 / 3.0) * sum);
}

namespace {
/// 양수만 남긴 중앙값 (없으면 0). representativeElementSize 와 같은 규약.
double medianPositive(std::vector<double> v) {
    v.erase(std::remove_if(v.begin(), v.end(), [](double x) { return !(x > 0.0); }), v.end());
    if (v.empty()) return 0.0;
    const size_t mid = v.size() / 2;
    std::nth_element(v.begin(), v.begin() + mid, v.end());
    double median = v[mid];
    if (v.size() % 2 == 0) {
        const double lower = *std::max_element(v.begin(), v.begin() + mid);
        median = 0.5 * (median + lower);
    }
    return median;
}
}  // namespace

double representativeElementSize(std::vector<double> volumes) {
    // 유효한 양의 부피만 남긴다 (축퇴/뒤집힘 요소 제외)
    volumes.erase(std::remove_if(volumes.begin(), volumes.end(),
                                 [](double v) { return !(v > 0.0); }),
                  volumes.end());
    if (volumes.empty()) return 0.0;

    // 평균이 아니라 **중앙값**을 쓴다. 평균은 소수의 큰 요소에 끌려가
    // 임계 거리를 부풀리고, 서로 다른 덩어리가 하나로 붙는다.
    const size_t mid = volumes.size() / 2;
    std::nth_element(volumes.begin(), volumes.begin() + mid, volumes.end());
    double median = volumes[mid];

    if (volumes.size() % 2 == 0) {
        // 짝수 개면 아래쪽 중앙값과 평균해 정확한 중앙값을 낸다
        double lower = *std::max_element(volumes.begin(), volumes.begin() + mid);
        median = 0.5 * (median + lower);
    }

    return std::cbrt(median);
}

namespace {

/// 경로 압축 + 랭크 결합 Union-Find
class UnionFind {
public:
    explicit UnionFind(size_t n) : parent_(n), rank_(n, 0) {
        for (size_t i = 0; i < n; ++i) parent_[i] = i;
    }

    size_t find(size_t x) {
        while (parent_[x] != x) {
            parent_[x] = parent_[parent_[x]];  // 경로 절반 압축
            x = parent_[x];
        }
        return x;
    }

    void unite(size_t a, size_t b) {
        size_t ra = find(a), rb = find(b);
        if (ra == rb) return;
        if (rank_[ra] < rank_[rb]) std::swap(ra, rb);
        parent_[rb] = ra;
        if (rank_[ra] == rank_[rb]) ++rank_[ra];
    }

private:
    std::vector<size_t> parent_;
    std::vector<int> rank_;
};

/// 공간 격자 셀 좌표 → 해시
struct CellKey {
    int64_t i, j, k;
    bool operator==(const CellKey& o) const { return i == o.i && j == o.j && k == o.k; }
};

struct CellHash {
    size_t operator()(const CellKey& c) const {
        // 서로 다른 큰 소수를 곱해 축별 상관을 끊는다
        uint64_t h = static_cast<uint64_t>(c.i) * 73856093ULL;
        h ^= static_cast<uint64_t>(c.j) * 19349663ULL;
        h ^= static_cast<uint64_t>(c.k) * 83492791ULL;
        return static_cast<size_t>(h);
    }
};

}  // namespace

std::vector<int> clusterByDistance(const std::vector<ClusterElement>& elems,
                                   double threshold) {
    const size_t n = elems.size();
    std::vector<int> labels(n, -1);
    if (n == 0) return labels;

    if (!(threshold > 0.0)) {
        // 임계값이 무효하면 군집화가 정의되지 않는다.
        // 전부 개별 덩어리로 두어 호출부가 알아채게 한다.
        for (size_t i = 0; i < n; ++i) labels[i] = static_cast<int>(i);
        return labels;
    }

    // 격자 한 변을 임계값과 같게 잡으면, 임계 거리 안의 이웃은 반드시
    // 자기 셀 또는 인접 26 셀 안에 있다 → 27 셀만 보면 충분하다.
    const double cell = threshold;
    std::unordered_map<CellKey, std::vector<size_t>, CellHash> grid;
    grid.reserve(n * 2);

    auto cellOf = [cell](const ClusterElement& e) -> CellKey {
        return CellKey{
            static_cast<int64_t>(std::floor(e.x / cell)),
            static_cast<int64_t>(std::floor(e.y / cell)),
            static_cast<int64_t>(std::floor(e.z / cell))};
    };

    for (size_t i = 0; i < n; ++i) grid[cellOf(elems[i])].push_back(i);

    UnionFind uf(n);
    const double thr2 = threshold * threshold;

    for (size_t i = 0; i < n; ++i) {
        const CellKey c = cellOf(elems[i]);
        for (int di = -1; di <= 1; ++di) {
            for (int dj = -1; dj <= 1; ++dj) {
                for (int dk = -1; dk <= 1; ++dk) {
                    auto it = grid.find(CellKey{c.i + di, c.j + dj, c.k + dk});
                    if (it == grid.end()) continue;
                    for (size_t j : it->second) {
                        if (j <= i) continue;  // 각 쌍을 한 번만
                        const double dx = elems[i].x - elems[j].x;
                        const double dy = elems[i].y - elems[j].y;
                        const double dz = elems[i].z - elems[j].z;
                        if (dx * dx + dy * dy + dz * dz <= thr2) {
                            uf.unite(i, j);
                        }
                    }
                }
            }
        }
    }

    // 루트를 0부터의 연속 라벨로 재번호
    std::unordered_map<size_t, int> root_to_label;
    root_to_label.reserve(n);
    int next = 0;
    for (size_t i = 0; i < n; ++i) {
        const size_t r = uf.find(i);
        auto it = root_to_label.find(r);
        if (it == root_to_label.end()) {
            root_to_label.emplace(r, next);
            labels[i] = next;
            ++next;
        } else {
            labels[i] = it->second;
        }
    }

    return labels;
}

}  // namespace analysis
}  // namespace kood3plot

// ════════════════════════════════════════════════════════════════
// 최상위 — 파트별 핫스팟 군집
// ════════════════════════════════════════════════════════════════

namespace kood3plot {
namespace analysis {

std::vector<PartHotspotResult> computeHotspotClusters(
    const data::Mesh& mesh,
    const std::vector<double>& elem_max_vm,
    const std::vector<double>& elem_max_time,
    const std::vector<double>& elem_strain,
    const std::map<int32_t, std::string>& part_names,
    const HotspotClusterConfig& cfg) {
    // 솔리드 전용 기존 진입점 — 종류 일반판으로 위임한다(결과 동일).
    ElementExtremes ex;
    ex.value = elem_max_vm;
    ex.time = elem_max_time;
    ex.strain = elem_strain;
    return computeHotspotClusters(mesh, HotspotElementKind::Solid, ex, {}, "", part_names, cfg);
}

std::vector<PartHotspotResult> computeHotspotClusters(
    const data::Mesh& mesh,
    HotspotElementKind kind,
    const ElementExtremes& ex,
    const std::vector<double>& shell_thickness,
    const std::string& layer_scheme,
    const std::map<int32_t, std::string>& part_names,
    const HotspotClusterConfig& cfg) {

    const std::vector<double>& elem_max_vm = ex.value;
    const std::vector<double>& elem_max_time = ex.time;
    const std::vector<double>& elem_strain = ex.strain;
    const bool have_layer = !ex.layer.empty();

    // 종류별 요소·파트·사용자 ID 배열
    const std::vector<Element>& elems =
        (kind == HotspotElementKind::Solid)      ? mesh.solids :
        (kind == HotspotElementKind::ThickShell) ? mesh.thick_shells : mesh.shells;
    const std::vector<int32_t>& elem_parts =
        (kind == HotspotElementKind::Solid)      ? mesh.solid_parts :
        (kind == HotspotElementKind::ThickShell) ? mesh.thick_shell_parts : mesh.shell_parts;
    const std::vector<int32_t>& elem_uids =
        (kind == HotspotElementKind::Solid)      ? mesh.real_solid_ids :
        (kind == HotspotElementKind::ThickShell) ? mesh.real_thick_shell_ids : mesh.real_shell_ids;
    const bool is_shell = (kind == HotspotElementKind::Shell);
    const int need_nodes = is_shell ? 4 : 8;

    std::vector<PartHotspotResult> out;
    if (!cfg.enabled || elem_max_vm.empty() || elems.empty()) return out;

    const bool have_strain = !elem_strain.empty();
    const size_t n_nodes = mesh.nodes.size();

    // ── 파트별 요소 인덱스 수집 ──
    std::map<int32_t, std::vector<size_t>> part_elems;
    for (size_t i = 0; i < elems.size() && i < elem_max_vm.size(); ++i) {
        const int32_t pid = (i < elem_parts.size()) ? elem_parts[i] : 0;
        part_elems[pid].push_back(i);
    }

    for (const auto& kv : part_elems) {
        const int32_t pid = kv.first;
        const std::vector<size_t>& idxs = kv.second;

        PartHotspotResult res;
        res.part_id = pid;
        auto nit = part_names.find(pid);
        if (nit != part_names.end()) res.part_name = nit->second;
        res.criterion = hotspotCriterionName(cfg.criterion);
        res.direction = hotspotCriterionIsMin(cfg.criterion) ? "min" : "max";
        res.strain_measure = hotspotStrainMeasureName(cfg.criterion);
        res.top_percent = cfg.top_percent;
        res.element_count_total = static_cast<int>(idxs.size());
        res.strain_available = have_strain;
        res.element_type = hotspotElementKindName(kind);
        res.layer_scheme = (kind == HotspotElementKind::Solid) ? "" : layer_scheme;

        // ── 1) 요소 기하: 부피·도심 ──
        // 🔴 node_ids 는 내부 1-based 인덱스다. mesh.nodes[id-1] 로만 변환한다.
        // 🔴 Node 를 통째로 복사해야 한다 — 축퇴 판정이 p[i].id 비교이므로
        //    좌표만 채우면 8개 id 가 같아져 요소가 통째로 버려진다.
        // v = 가중 측도(부피 / 면적×두께 / 면적), a = 셸 면적, s = 대표 크기용 측도
        struct Geo { double x, y, z, v, a; bool ok; };
        std::vector<Geo> geo(idxs.size(), Geo{0, 0, 0, 0, 0, false});
        std::vector<double> size_metric;     // Solid: 부피 · Shell: 면적 · ThickShell: 면내 크기
        size_metric.reserve(idxs.size());
        int bad_conn = 0, bad_vol = 0;

        // 셸 두께 가중은 파트 안 모든 유효 요소에 양의 두께가 있을 때만 쓴다.
        // 섞이면(일부만 두께) 단위가 다른 가중이 한 평균에 섞인다.
        bool part_thick_ok = is_shell && !shell_thickness.empty();

        for (size_t k = 0; k < idxs.size(); ++k) {
            const auto& elem = elems[idxs[k]];
            if (static_cast<int>(elem.node_ids.size()) < need_nodes) { ++bad_conn; continue; }

            Node p[8];
            bool ok = true;
            for (int n = 0; n < need_nodes; ++n) {
                const int64_t ni = static_cast<int64_t>(elem.node_ids[n]) - 1;
                if (ni < 0 || static_cast<size_t>(ni) >= n_nodes) { ok = false; break; }
                p[n] = mesh.nodes[static_cast<size_t>(ni)];   // id 포함 통째 복사
            }
            if (!ok) { ++bad_conn; continue; }

            // 경계상자 — 초기 형상, 연결성이 유효한 요소의 절점 전부
            for (int n = 0; n < need_nodes; ++n) {
                const double c3[3] = {p[n].x, p[n].y, p[n].z};
                for (int r = 0; r < 3; ++r) {
                    if (!res.bbox_valid) { res.bbox_min[r] = res.bbox_max[r] = c3[r]; }
                    else {
                        res.bbox_min[r] = std::min(res.bbox_min[r], c3[r]);
                        res.bbox_max[r] = std::max(res.bbox_max[r], c3[r]);
                    }
                }
                res.bbox_valid = true;
            }

            double cx, cy, cz;
            if (is_shell) {
                double A;
                if (!computeShellAreaAndCentroid(p, A, cx, cy, cz)) { ++bad_vol; continue; }
                const size_t ei = idxs[k];
                if (part_thick_ok && !(ei < shell_thickness.size() && shell_thickness[ei] > 0.0)) {
                    part_thick_ok = false;
                }
                geo[k] = Geo{cx, cy, cz, A, A, true};   // 가중은 아래에서 두께를 곱해 확정
                size_metric.push_back(A);
            } else {
                double V;
                if (!computeSolidVolumeAndCentroid(p, V, cx, cy, cz)) { ++bad_vol; continue; }
                const double av = std::abs(V);
                geo[k] = Geo{cx, cy, cz, av, 0.0, true};
                if (kind == HotspotElementKind::ThickShell) {
                    const double h = hexMinFaceSeparation(p);
                    if (h > 0.0) size_metric.push_back(std::sqrt(av / h));
                } else {
                    // 솔리드 특성 길이 L 의 세제곱을 모은다 (대표 크기 = ∛median(L³)).
                    //  · 육면체·쐐기(고유 절점 ≥ 6): L = √(V / h_min) — 면내 크기.
                    //    🔴 ∛V 만 쓰면 한 층 벽돌로 메시한 얇은 판(PCB·인터포저)에서
                    //       임계가 면내 간격보다 작아져 맞닿은 요소도 안 묶인다.
                    //       실측: 0.4 mm 판 파트에서 인접 요소 11개가 덩어리 0 으로 사라짐.
                    //  · 사면체·사각뿔: L = ∛V (등방 메시 가정, 기존과 동일).
                    //  정육면체는 √(a³/a)³ = a³ = V 라 기존 값과 같다.
                    int nu = 0;
                    for (int a = 0; a < 8; ++a) {
                        bool dup = false;
                        for (int b = 0; b < a; ++b) if (p[b].id == p[a].id) { dup = true; break; }
                        if (!dup) ++nu;
                    }
                    const double h = (nu >= 6) ? hexMinFaceSeparation(p) : 0.0;
                    if (nu >= 6 && h > 0.0) {
                        const double L = std::sqrt(av / h);
                        size_metric.push_back(L * L * L);
                    } else {
                        size_metric.push_back(av);
                    }
                }
            }
        }

        if (is_shell) {
            if (part_thick_ok) {
                for (size_t k = 0; k < idxs.size(); ++k) {
                    if (geo[k].ok) geo[k].v = geo[k].a * shell_thickness[idxs[k]];
                }
                res.weight_measure = "area_x_thickness";
            } else {
                res.weight_measure = "area";
            }
        } else {
            res.weight_measure = "volume";
        }

        // 대표 요소 크기 — 종류별 정의 (헤더 표 참조). 솔리드는 기존과 동일.
        if (kind == HotspotElementKind::Solid) {
            res.element_size_ref = representativeElementSize(size_metric);
        } else if (is_shell) {
            res.element_size_ref = std::sqrt(medianPositive(size_metric));
        } else {
            res.element_size_ref = medianPositive(size_metric);
        }
        res.distance_threshold = cfg.distance_factor * res.element_size_ref;

        // ── 3) 상위 p% 선별 ──
        //
        // 🔴 "값이 컷 이상인 것 전부" 로 뽑으면 안 된다. 배경 응력이 균일한
        //    모델에서는 N번째 큰 값이 배경값과 같아져 **전 요소가 통과**한다
        //    (실측: 180 요소 중 상위 5% 를 뽑았더니 180개 전부 선별).
        //    상위 5% 는 요소 수의 5% 를 뜻하므로 **정확히 N개**를 고른다.
        //
        // 동점 처리: 값이 같으면 요소 인덱스가 작은 쪽을 먼저 — 결정적이어야
        // 같은 입력이 항상 같은 결과를 낸다.
        const double frac = std::min(100.0, std::max(0.0, cfg.top_percent)) / 100.0;

        // (값, 파트내 순번 k) 쌍으로 정렬 대상 구성
        std::vector<std::pair<double, size_t>> rank;
        rank.reserve(idxs.size());
        for (size_t k = 0; k < idxs.size(); ++k) {
            if (!geo[k].ok) continue;
            const double v = elem_max_vm[idxs[k]];
            // 🔴 `v < 0` 로 거르면 안 된다 — σ1·σ3 은 음수가 정상값이다.
            if (hotspotIsUnrecorded(v)) continue;
            rank.emplace_back(v, k);
        }

        if (rank.size() < static_cast<size_t>(std::max(1, cfg.min_cluster_elements))) {
            out.push_back(res);               // 유효 요소가 최소 덩어리 크기에도 못 미침
            continue;
        }

        size_t want = static_cast<size_t>(std::floor(rank.size() * frac));
        if (want < 1) want = 1;
        if (want > rank.size()) want = rank.size();

        // "뜨거운 순" — von Mises·σ1 은 내림차순, σ3 은 오름차순(가장 압축인 것부터).
        const HotspotCriterion crit = cfg.criterion;
        auto hotter_first = [crit](const std::pair<double, size_t>& a,
                                   const std::pair<double, size_t>& b) {
            if (a.first != b.first) return hotspotHotter(crit, a.first, b.first);
            return a.second < b.second;          // 동점이면 인덱스 오름차순
        };
        std::nth_element(rank.begin(), rank.begin() + (want - 1), rank.end(), hotter_first);
        {
            // 경계 동률 — 컷값과 같은 값인데 선별되지 못한 요소 (nth_element 뒤쪽 구간)
            const double cutv = rank[want - 1].first;
            const double tol = 1e-9 * std::max(std::abs(cutv), 1e-300);
            int ties = 0;
            for (size_t q = want; q < rank.size(); ++q) {
                if (std::abs(rank[q].first - cutv) <= tol) ++ties;
            }
            res.cut_ties_unselected = ties;
        }
        rank.resize(want);
        // 컷값 = 선별된 것 중 가장 덜 뜨거운 값 (max 방향이면 최솟값, min 방향이면 최댓값)
        res.threshold_value = rank.empty() ? 0.0
                            : std::max_element(rank.begin(), rank.end(), hotter_first)->first;
        if (!rank.empty()) {
            res.value_extreme = std::min_element(rank.begin(), rank.end(), hotter_first)->first;
            res.value_extreme_valid = true;
            const double tol = 1e-9 * std::max(std::abs(res.value_extreme), 1e-300);
            res.uniform = (std::abs(res.value_extreme - res.threshold_value) <= tol) &&
                          res.cut_ties_unselected > 0;
        }

        std::vector<ClusterElement> sel;
        sel.reserve(rank.size());
        for (const auto& rk : rank) {
            const size_t k = rk.second;
            const size_t ei = idxs[k];
            const double v = rk.first;

            ClusterElement ce;
            ce.element_id = (ei < elem_uids.size())
                          ? elem_uids[ei]
                          : static_cast<int32_t>(ei + 1);
            ce.element_idx = ei;
            ce.x = geo[k].x; ce.y = geo[k].y; ce.z = geo[k].z;
            ce.volume = geo[k].v;
            ce.area = geo[k].a;
            ce.layer = (have_layer && ei < ex.layer.size()) ? ex.layer[ei] : -1;
            ce.value = v;
            ce.peak_time = (ei < elem_max_time.size()) ? elem_max_time[ei] : 0.0;
            ce.has_strain = have_strain && ei < elem_strain.size();
            ce.strain = ce.has_strain ? elem_strain[ei] : 0.0;
            sel.push_back(ce);
        }
        res.element_count_selected = static_cast<int>(sel.size());
        if (sel.empty() || !(res.distance_threshold > 0.0)) {
            out.push_back(res);
            continue;
        }

        // ── 4) 군집화 ──
        const std::vector<int> labels = clusterByDistance(sel, res.distance_threshold);
        int n_lab = 0;
        for (int l : labels) n_lab = std::max(n_lab, l + 1);

        std::vector<std::vector<size_t>> groups(static_cast<size_t>(n_lab));
        for (size_t i = 0; i < labels.size(); ++i) {
            if (labels[i] >= 0) groups[static_cast<size_t>(labels[i])].push_back(i);
        }

        // ── 5) 덩어리별 통계 (전부 부피 가중) ──
        std::vector<HotspotCluster> clusters;
        for (const auto& g : groups) {
            if (static_cast<int>(g.size()) < cfg.min_cluster_elements) continue;

            // 가장 '차가운' 값으로 초기화 — max 방향은 −∞, min 방향은 +∞.
            const bool is_min = hotspotCriterionIsMin(crit);
            const double coldest = is_min ?  std::numeric_limits<double>::max()
                                          : -std::numeric_limits<double>::max();

            double sumV = 0.0, sumSV = 0.0;      // Σ V,  Σ σ·V (부호 유지 — 평균용)
            double sumWV = 0.0;                  // Σ w·V (심각도 가중 — 중심용)
            double wx = 0.0, wy = 0.0, wz = 0.0; // Σ w·V·x
            double s_max = coldest;
            double e_sum = 0.0, e_max = coldest;
            int32_t peak_id = 0;
            double peak_t = 0.0;
            int peak_layer = -1;
            double sumA = 0.0;                   // 셸 면적 합 (보고용)
            bool any_strain = false;

            for (size_t i : g) {
                const ClusterElement& e = sel[i];
                sumV += e.volume;
                sumSV += e.value * e.volume;
                // 🔴 중심 가중에 부호 있는 값을 그대로 쓰면 음수 가중이 중심을 덩어리
                //    밖으로 튀게 한다. 뜨거운 방향으로 양수화하고 반대 부호는 0 으로.
                //    von Mises(≥0)에서는 이 식이 기존 σ·V 와 정확히 같다.
                const double wv = std::max(0.0, hotspotSeverity(crit, e.value)) * e.volume;
                sumWV += wv;
                wx += wv * e.x; wy += wv * e.y; wz += wv * e.z;
                sumA += e.area;
                if (hotspotHotter(crit, e.value, s_max)) {
                    s_max = e.value; peak_id = e.element_id; peak_t = e.peak_time;
                    peak_layer = e.layer;
                }
                if (e.has_strain) {
                    any_strain = true;
                    e_sum += e.strain * e.volume;
                    if (hotspotHotter(crit, e.strain, e_max)) e_max = e.strain;
                }
            }
            if (!(sumV > 0.0)) continue;

            HotspotCluster c;
            c.element_count = static_cast<int>(g.size());
            if (is_shell) {
                // 셸: 면적은 항상, 부피(면적×두께)는 두께가 있을 때만
                c.has_area = true;
                c.area = sumA;
                c.volume_valid = (res.weight_measure == "area_x_thickness");
                c.volume = c.volume_valid ? sumV : 0.0;
            } else {
                c.volume = sumV;
            }

            // 중심 = 심각도×부피 가중. 분모가 0 이면(전부 0 또는 반대 부호) 부피 가중으로 폴백.
            if (sumWV > 0.0) {
                c.center[0] = wx / sumWV; c.center[1] = wy / sumWV; c.center[2] = wz / sumWV;
            } else {
                double vx = 0, vy = 0, vz = 0;
                for (size_t i : g) { vx += sel[i].x * sel[i].volume;
                                     vy += sel[i].y * sel[i].volume;
                                     vz += sel[i].z * sel[i].volume; }
                c.center[0] = vx / sumV; c.center[1] = vy / sumV; c.center[2] = vz / sumV;
            }

            // 부피 가중 평균 — 산술평균은 작은 요소를 과대평가한다.
            c.stress_mean = sumSV / sumV;
            c.stress_max = s_max;
            c.strain_available = any_strain;
            if (any_strain) { c.strain_mean = e_sum / sumV; c.strain_max = e_max; }
            c.peak_element_id = peak_id;
            c.peak_time = peak_t;
            c.peak_layer = peak_layer;

            // 포함 반경 = 중심에서 구성 요소의 **최원 절점**까지 (정확).
            // 요소 도심까지의 거리로 재면 덩어리 가장자리 요소의 두께를 놓친다.
            double r2max = 0.0, rms_acc = 0.0;
            for (size_t i : g) {
                const auto& elem = elems[sel[i].element_idx];
                for (size_t n = 0; n < elem.node_ids.size() && n < 8; ++n) {
                    const int64_t ni = static_cast<int64_t>(elem.node_ids[n]) - 1;
                    if (ni < 0 || static_cast<size_t>(ni) >= n_nodes) continue;
                    const Node& nd = mesh.nodes[static_cast<size_t>(ni)];
                    const double dx = nd.x - c.center[0];
                    const double dy = nd.y - c.center[1];
                    const double dz = nd.z - c.center[2];
                    r2max = std::max(r2max, dx * dx + dy * dy + dz * dz);
                }
                const double dx = sel[i].x - c.center[0];
                const double dy = sel[i].y - c.center[1];
                const double dz = sel[i].z - c.center[2];
                rms_acc += sel[i].volume * (dx * dx + dy * dy + dz * dz);
            }
            c.radius_enclosing = std::sqrt(r2max);
            c.radius_rms = std::sqrt(rms_acc / sumV);

            clusters.push_back(c);
            res.element_count_clustered += c.element_count;
        }

        // 뜨거운 순 정렬 후 순위 부여 (σ3 이면 가장 음수인 덩어리가 1위)
        std::sort(clusters.begin(), clusters.end(),
                  [crit](const HotspotCluster& a, const HotspotCluster& b) {
                      return hotspotHotter(crit, a.stress_max, b.stress_max);
                  });
        if (cfg.max_clusters_per_part > 0 &&
            clusters.size() > static_cast<size_t>(cfg.max_clusters_per_part)) {
            clusters.resize(static_cast<size_t>(cfg.max_clusters_per_part));
        }
        for (size_t i = 0; i < clusters.size(); ++i) {
            clusters[i].rank = static_cast<int>(i) + 1;
        }
        res.clusters = std::move(clusters);
        out.push_back(res);
    }

    return out;
}

}  // namespace analysis
}  // namespace kood3plot
