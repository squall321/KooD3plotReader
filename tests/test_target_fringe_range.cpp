// LS-PrePost 타깃 렌더에 걸 색 범위(타깃 파트의 전 상태 값 범위)가 LS-PrePost 가 칠하는 값과 같은 규칙으로 나는지 메모리의 메시 · 상태로 보는 시험
/**
 * @file test_target_fringe_range.cpp
 * @brief render::partFringeRanges 검증 (덱 없이 Mesh · ControlData · StateData 를 직접 만든다)
 *
 * 검증 항목
 *   1. 솔리드 — 요소 값은 값이 실린 적분점 자리의 최대(사면체의 0 자리는 뺀다). 셸 · 두꺼운 셸 — 저장된 층의 최대
 *   2. von Mises · 유효 소성 변형률 · 압력(대수 최대 · 최소) · 최대 전단 (σ1−σ3)/2 — 전 상태의 최소 ~ 최대
 *   3. 지운 요소는 그 상태에서 뺀다(삭제 목록 = 1부터 순번)
 *   4. 변위 · 속도 — 타깃 요소(빔 포함) 절점의 크기, 기록되지 않은 양(IA 0)은 범위 없음
 *   5. 빔만 있는 파트의 응력 · 층 배치를 믿지 못하는 셸 · 모르는 fringe — 범위 없음(자동 범위를 쓴다)
 *   6. 여러 파트를 합친 범위
 * 기대값은 시험 안의 생성식 · 주응력(야코비 회전)으로 따로 낸다.
 *
 * Run: ./test_target_fringe_range
 */

#include "kood3plot/render/TargetFringeRange.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <functional>
#include <limits>
#include <string>
#include <vector>

using namespace kood3plot;
using kood3plot::render::FringeRange;
using kood3plot::render::FringeType;

namespace {

int g_failed = 0;
int g_checks = 0;

void expect(bool ok, const std::string& what) {
    ++g_checks;
    if (ok) return;
    ++g_failed;
    std::printf("    [FAIL] %s\n", what.c_str());
}

void expectRange(const FringeRange& r, double lo, double hi, const std::string& what, double rel = 1e-12) {
    const auto near = [&](double a, double b) { return std::abs(a - b) <= rel * std::max(1.0, std::abs(b)); };
    char buf[160];
    std::snprintf(buf, sizeof(buf), " got ok=%d %.12g ~ %.12g want %.12g ~ %.12g", r.ok, r.min, r.max, lo, hi);
    expect(r.ok && near(r.min, lo) && near(r.max, hi), what + buf);
}

constexpr int kStates = 3;                 // 상태 0 은 응력 0 · 절점 제자리
constexpr int kSlots = 8;                  // 솔리드 적분점 자리(NINTSLD 8)
constexpr int kLayers = 3;                 // 셸 · 두꺼운 셸 층(MAXINT 3)
constexpr int kNodes = 35;
constexpr double kSentinel = 9.0e5;        // 지운 요소의 워드 — 빼지 않으면 범위가 이 값까지 커진다

// 솔리드 셋: 0 = 육면체(파트 1), 1 = 사면체(파트 1, 뒤 네 자리 0), 2 = 육면체(파트 5, 상태 2 에서 지움)
constexpr int kSolidPart[3] = {1, 1, 5};
constexpr int kUsedSlots[3] = {8, 4, 8};
constexpr int kSolidConn[3][8] = {{1, 2, 3, 4, 5, 6, 7, 8}, {2, 3, 9, 10, 10, 10, 10, 10}, {11, 12, 13, 14, 15, 16, 17, 18}};
// 셸 둘(파트 2), 두꺼운 셸 하나(파트 3), 빔 둘(파트 4)
constexpr int kShellConn[2][4] = {{19, 20, 21, 22}, {20, 23, 24, 21}};
constexpr int kTshellConn[8] = {25, 26, 27, 28, 29, 30, 31, 32};
constexpr int kBeamConn[2][2] = {{33, 34}, {34, 35}};
constexpr double kZ[kLayers] = {0.0, -1.0, 1.0};   // 층 0 = 중립면

int wobble(int e, int p, int k) { return (7 * p + 3 * k + 5 * e + 5) % 13 - 6; }

struct Ip {
    double s[6] = {0, 0, 0, 0, 0, 0};
    double ep = 0.0;
};

Ip solidIp(int e, int p, int s) {
    Ip v;
    if (s == 0 || p >= kUsedSlots[e]) return v;
    static const double base[3][6] = {{96, 32, -16, 24, -8, 12}, {-64, 128, 40, -20, 28, 4}, {160, 112, 72, 20, -12, 28}};
    for (int k = 0; k < 6; ++k) v.s[k] = s * (base[e][k] + 16.0 * wobble(e, p, k));
    v.ep = s * (40.0 + 8.0 * e + wobble(e, p, 6)) / 4096.0;
    return v;
}

/// 층 요소 e(0, 1 = 셸, 2 = 두꺼운 셸)의 층 l 값 — 막 + z × 굽힘
Ip layerIp(int e, int l, int s) {
    Ip v;
    if (s == 0) return v;
    static const double mem[3][6] = {{40, -20, 0, 10, 0, 0}, {-30, 50, 0, -15, 0, 0}, {60, 30, 20, 12, -8, 6}};
    static const double bend[3][6] = {{200, 60, 0, 30, 0, 0}, {-120, -180, 0, 40, 0, 0}, {150, -90, 40, 24, 10, -14}};
    for (int k = 0; k < 6; ++k) v.s[k] = s * (mem[e][k] + kZ[l] * bend[e][k]);
    v.ep = s * (0.010 + 0.004 * e + kZ[l] * (e == 1 ? -0.003 : 0.002));
    return v;
}

std::array<double, 3> eigen(const double* s) {
    double a[3][3] = {{s[0], s[3], s[5]}, {s[3], s[1], s[4]}, {s[5], s[4], s[2]}};
    for (int sweep = 0; sweep < 64; ++sweep) {
        const double off = a[0][1] * a[0][1] + a[0][2] * a[0][2] + a[1][2] * a[1][2];
        if (off <= 1e-34 * (a[0][0] * a[0][0] + a[1][1] * a[1][1] + a[2][2] * a[2][2]) || off == 0.0) break;
        for (int p = 0; p < 2; ++p) {
            for (int q = p + 1; q < 3; ++q) {
                if (a[p][q] == 0.0) continue;
                const double th = (a[q][q] - a[p][p]) / (2.0 * a[p][q]);
                const double t = (th >= 0 ? 1.0 : -1.0) / (std::abs(th) + std::sqrt(th * th + 1.0));
                const double c = 1.0 / std::sqrt(t * t + 1.0), sn = t * c;
                for (int k = 0; k < 3; ++k) {
                    const double x = a[k][p], y = a[k][q];
                    a[k][p] = c * x - sn * y;
                    a[k][q] = sn * x + c * y;
                }
                for (int k = 0; k < 3; ++k) {
                    const double x = a[p][k], y = a[q][k];
                    a[p][k] = c * x - sn * y;
                    a[q][k] = sn * x + c * y;
                }
            }
        }
    }
    std::array<double, 3> ev = {a[0][0], a[1][1], a[2][2]};
    std::sort(ev.begin(), ev.end(), std::greater<double>());
    return ev;
}

double scalar(FringeType t, const Ip& v) {
    switch (t) {
        case FringeType::EFFECTIVE_PLASTIC_STRAIN: return v.ep;
        case FringeType::PRESSURE: return -(v.s[0] + v.s[1] + v.s[2]) / 3.0;
        case FringeType::MAX_SHEAR_STRESS: {
            const auto ev = eigen(v.s);
            return (ev[0] - ev[2]) / 2.0;
        }
        default: {
            const double a = v.s[0] - v.s[1], b = v.s[1] - v.s[2], c = v.s[2] - v.s[0];
            return std::sqrt(0.5 * (a * a + b * b + c * c) + 3.0 * (v.s[3] * v.s[3] + v.s[4] * v.s[4] + v.s[5] * v.s[5]));
        }
    }
}

double nodeX(int i) { return i; }
double nodeY(int i) { return i % 3; }
double nodeZ(int i) { return i % 5; }

data::Mesh buildMesh() {
    data::Mesh m;
    for (int i = 1; i <= kNodes; ++i) m.nodes.push_back({i, nodeX(i), nodeY(i), nodeZ(i)});
    auto el = [](ElementType t, int id, const int* conn, int n) {
        Element e;
        e.id = id;
        e.type = t;
        e.material_id = 1;
        e.node_ids.assign(conn, conn + n);
        return e;
    };
    for (int e = 0; e < 3; ++e) {
        m.solids.push_back(el(ElementType::SOLID, e + 1, kSolidConn[e], 8));
        m.solid_parts.push_back(kSolidPart[e]);
    }
    for (int e = 0; e < 2; ++e) {
        m.shells.push_back(el(ElementType::SHELL, e + 1, kShellConn[e], 4));
        m.shell_parts.push_back(2);
    }
    m.thick_shells.push_back(el(ElementType::THICK_SHELL, 1, kTshellConn, 8));
    m.thick_shell_parts.push_back(3);
    for (int e = 0; e < 2; ++e) {
        m.beams.push_back(el(ElementType::BEAM, e + 1, kBeamConn[e], 2));
        m.beam_parts.push_back(4);
    }
    m.num_solids = 3;
    m.num_shells = 2;
    m.num_thick_shells = 1;
    m.num_beams = 2;
    return m;
}

data::ControlData buildControl(int nv2d) {
    data::ControlData c;
    c.NDIM = 4;
    c.NUMNP = kNodes;
    c.IU = 1;
    c.IV = 1;
    c.IA = 0;
    c.NEL8 = 3;
    c.NV3D = kSlots * 7;
    c.IOSOL[0] = c.IOSOL[1] = 1;
    c.NEIPH = 0;
    c.NEL4 = 2;
    c.NV2D = nv2d;
    c.NELT = 1;
    c.NV3DT = kLayers * 7;
    c.MAXINT = kLayers;
    c.NEIPS = 0;
    c.IOSHL[0] = c.IOSHL[1] = 1;
    c.NEL2 = 2;
    return c;
}

/// 상태 s — 솔리드 2 는 상태 2 에서 지워지고 워드에 큰 값이 실린다(삭제 목록을 읽어야 빠진다)
data::StateData buildState(int s, int nv2d) {
    data::StateData st;
    st.time = 0.5 * s;
    for (int i = 1; i <= kNodes; ++i) {
        st.node_displacements.push_back(nodeX(i) + s * 0.01 * i);
        st.node_displacements.push_back(nodeY(i) + s * 0.002);
        st.node_displacements.push_back(nodeZ(i) - s * 0.003 * (i % 4));
        st.node_velocities.push_back(s * 0.1 * i);
        st.node_velocities.push_back(s * 0.5);
        st.node_velocities.push_back(0.0);
    }
    st.solid_data.assign(3 * kSlots * 7, 0.0);
    for (int e = 0; e < 3; ++e) {
        for (int p = 0; p < kSlots; ++p) {
            double* w = &st.solid_data[(static_cast<size_t>(e) * kSlots + p) * 7];
            const Ip v = solidIp(e, p, s);
            for (int k = 0; k < 6; ++k) w[k] = v.s[k];
            w[6] = v.ep;
            if (e == 2 && s == 2) std::fill(w, w + 7, kSentinel);
        }
    }
    if (s == 2) st.deleted_solids = {3};
    const auto fill = [&](std::vector<double>& d, int e, size_t base) {
        for (int l = 0; l < kLayers; ++l) {
            const Ip v = layerIp(e, l, s);
            for (int k = 0; k < 6; ++k) d[base + l * 7 + k] = v.s[k];
            d[base + l * 7 + 6] = v.ep;
        }
    };
    st.shell_data.assign(2 * static_cast<size_t>(nv2d), 0.0);
    fill(st.shell_data, 0, 0);
    fill(st.shell_data, 1, nv2d);
    st.thick_shell_data.assign(kLayers * 7, 0.0);
    fill(st.thick_shell_data, 2, 0);
    return st;
}

struct Want {
    double lo = std::numeric_limits<double>::infinity();
    double hi = -std::numeric_limits<double>::infinity();
    void add(double v) {
        lo = std::min(lo, v);
        hi = std::max(hi, v);
    }
};

/// 기대 범위 — 파트 하나, 응력 계열
Want wantElem(int pid, FringeType t) {
    Want w;
    for (int s = 0; s < kStates; ++s) {
        for (int e = 0; e < 3; ++e) {
            if (kSolidPart[e] != pid || (e == 2 && s == 2)) continue;
            double v = -std::numeric_limits<double>::infinity();
            const int used = s == 0 ? 1 : kUsedSlots[e];    // 상태 0 — 쓰인 자리가 없어 자리 0 을 읽는다
            for (int p = 0; p < used; ++p) v = std::max(v, scalar(t, solidIp(e, p, s)));
            w.add(v);
        }
        const auto layer = [&](int e) {
            double v = -std::numeric_limits<double>::infinity();
            for (int l = 0; l < kLayers; ++l) v = std::max(v, scalar(t, layerIp(e, l, s)));
            w.add(v);
        };
        if (pid == 2) { layer(0); layer(1); }
        if (pid == 3) layer(2);
    }
    return w;
}

std::vector<int> nodesOf(int pid) {
    std::vector<int> n;
    for (int e = 0; e < 3; ++e)
        if (kSolidPart[e] == pid) n.insert(n.end(), kSolidConn[e], kSolidConn[e] + 8);
    if (pid == 2) for (const auto& c : kShellConn) n.insert(n.end(), c, c + 4);
    if (pid == 3) n.insert(n.end(), kTshellConn, kTshellConn + 8);
    if (pid == 4) for (const auto& c : kBeamConn) n.insert(n.end(), c, c + 2);
    return n;
}

Want wantNode(int pid, FringeType t) {
    Want w;
    for (int s = 0; s < kStates; ++s) {
        for (int i : nodesOf(pid)) {
            double x, y, z;
            if (t == FringeType::DISPLACEMENT) { x = s * 0.01 * i; y = s * 0.002; z = -s * 0.003 * (i % 4); }
            else { x = s * 0.1 * i; y = s * 0.5; z = 0.0; }
            w.add(std::sqrt(x * x + y * y + z * z));
        }
    }
    return w;
}

std::map<int32_t, FringeRange> run(FringeType t, const std::vector<int32_t>& parts, int nv2d = kLayers * 7) {
    const data::Mesh mesh = buildMesh();
    const data::ControlData c = buildControl(nv2d);
    return render::partFringeRanges(mesh, c, kStates, [&](size_t i, data::StateData& out) {
        out = buildState(static_cast<int>(i), nv2d);
        return true;
    }, parts, t);
}

}  // namespace

int main() {
    std::printf("=== LS-PrePost 타깃 색 범위(partFringeRanges) 검증 ===\n\n");
    const std::vector<int32_t> all = {1, 2, 3, 4, 5};

    std::printf("[1] 응력 계열 — 솔리드 적분점 최대 · 셸 층 최대, 전 상태, 지운 요소 뺌\n");
    const std::pair<FringeType, const char*> elem_types[] = {{FringeType::VON_MISES, "σ_vm"},
                                                            {FringeType::EFFECTIVE_PLASTIC_STRAIN, "ε_p"},
                                                            {FringeType::PRESSURE, "압력"},
                                                            {FringeType::MAX_SHEAR_STRESS, "최대 전단"}};
    for (const auto& [t, name] : elem_types) {
        const auto r = run(t, all);
        const double rel = t == FringeType::MAX_SHEAR_STRESS ? 1e-9 : 1e-12;
        for (int pid : {1, 2, 3, 5}) {
            const Want w = wantElem(pid, t);
            expectRange(r.at(pid), w.lo, w.hi, std::string(name) + " 파트 " + std::to_string(pid), rel);
        }
        expect(!r.at(4).ok, std::string(name) + " 빔만 있는 파트 4 — 범위 없음");
    }

    std::printf("[2] 첫 자리 · 첫 층 · 마지막 층만 읽으면 다른 범위가 난다(시험이 규칙을 가를 수 있는지)\n");
    {
        Want first;
        for (int s = 1; s < kStates; ++s) first.add(scalar(FringeType::VON_MISES, solidIp(0, 0, s)));
        expect(first.hi < wantElem(1, FringeType::VON_MISES).hi - 1.0, "파트 1 — 첫 자리 최대가 적분점 최대보다 작다");
        Want mid;
        for (int s = 1; s < kStates; ++s) { mid.add(scalar(FringeType::VON_MISES, layerIp(0, 0, s))); mid.add(scalar(FringeType::VON_MISES, layerIp(1, 0, s))); }
        expect(mid.hi < wantElem(2, FringeType::VON_MISES).hi - 1.0, "파트 2 — 중립면 최대가 층 최대보다 작다");
        expect(run(FringeType::VON_MISES, {5}).at(5).max < kSentinel, "파트 5 — 지운 요소의 워드가 범위에 들지 않는다");
    }

    std::printf("[3] 변위 · 속도 — 타깃 요소(빔 포함) 절점의 크기. 가속도는 기록되지 않아 범위 없음\n");
    for (auto t : {FringeType::DISPLACEMENT, FringeType::VELOCITY}) {
        const auto r = run(t, all);
        for (int pid : {1, 2, 3, 4, 5}) {
            const Want w = wantNode(pid, t);
            expectRange(r.at(pid), w.lo, w.hi, std::string(t == FringeType::DISPLACEMENT ? "변위" : "속도") + " 파트 " + std::to_string(pid));
        }
    }
    {
        const auto r = run(FringeType::ACCELERATION, all);
        bool none = true;
        for (const auto& kv : r) none = none && !kv.second.ok;
        expect(none, "가속도(IA 0) — 모든 파트 범위 없음");
    }

    std::printf("[4] 믿지 못하는 셸 층 배치 · 모르는 fringe\n");
    {
        const auto r = run(FringeType::VON_MISES, {2, 3}, kLayers * 7 + 1);   // NV2D 가 규격 공식과 한 워드 어긋남
        expect(!r.at(2).ok, "셸 파트 2 — 층 배치를 믿지 못해 범위 없음(첫 7 워드로 지어내지 않는다)");
        const Want w = wantElem(3, FringeType::VON_MISES);
        expectRange(r.at(3), w.lo, w.hi, "두꺼운 셸 파트 3 은 그대로");
        expect(run(FringeType::STRESS_XX, all).empty(), "성분 응력(STRESS_XX) — 계산하지 않는다");
    }

    std::printf("[5] 여러 파트를 합친 범위\n");
    {
        const auto r = run(FringeType::VON_MISES, all);
        const FringeRange m = render::mergeRanges(r, {1, 2, 4});
        const Want a = wantElem(1, FringeType::VON_MISES), b = wantElem(2, FringeType::VON_MISES);
        expectRange(m, std::min(a.lo, b.lo), std::max(a.hi, b.hi), "파트 1 · 2 · 4(값 없음) 합집합");
        expect(!render::mergeRanges(r, {4}).ok, "값이 없는 파트만이면 범위 없음");
    }

    std::printf("\n검사 %d개 · %s\n", g_checks, g_failed ? (std::to_string(g_failed) + "건 실패").c_str() : "전부 통과");
    return g_failed ? 1 : 0;
}
