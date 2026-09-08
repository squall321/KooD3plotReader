// 파트 내 상위 백분위 요소의 공간 군집화 — 기하 계산과 군집 알고리즘 구현
#include "kood3plot/analysis/HotspotClusterAnalyzer.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <unordered_map>
#include <vector>

namespace kood3plot {
namespace analysis {

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
