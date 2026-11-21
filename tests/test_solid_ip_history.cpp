// 솔리드가 적분점 여덟 개를 기록한 덱(NINTSLD 8)의 파트 이력 · 핫스팟 · 피크 텐서를 합성 d3plot 으로 검증하는 시험
/**
 * @file test_solid_ip_history.cpp
 * @brief SinglePassAnalyzer 의 솔리드 적분점 처리 검증
 *
 * 적분점 여덟 개를 기록한 실제 덱은 값이 자리마다 다른 것이 하나(ElasticBeam)뿐이고 변형률이 실린 것은 없다.
 * 여기서는 D3plotWriter 로 자리마다 값을 미리 아는 덱을 만들어, 분석기가 어느 자리를 읽고 어떻게 합치는지를 본다.
 * 기대값은 분석기 코드와 따로, 생성식에서 바로 낸다(StressTensor 의 일반 고유값 풀이).
 *
 * 검증 항목
 *   1. 파트 이력 — 요소 값은 값이 실린 적분점의 극값(σ_vm · σ1 · ε_p · 변형률은 최대, σ3 · ε3 는 최소)
 *   2. 사면체 · 오면체처럼 뒤 자리가 0 으로 실린 요소 — 빈 자리는 극값 · 평균에 끼지 않는다
 *   3. 변형률 6성분은 적분점 블록마다 이력 변수의 마지막 여섯 워드다(이력 변수 자리를 변형률로 읽지 않는다)
 *   4. 핫스팟 요소 극값 — 가장 뜨거운 적분점의 값과 그 적분점의 변형률, ε_p · 소성 일은 적분점 평균
 *   5. 군집 시각 집계 — 적분점 평균
 *   6. 피크 요소 텐서 이력 — 피크 시각에 극값을 낸 적분점 하나의 이력
 *   7. 한 자리 덱, 머리말 식과 맞지 않는 덱은 종전 그대로(요소 블록 전체가 적분점 하나)
 *   8. 여덟 자리에 같은 값을 적은 덱은 한 자리 덱과 결과가 비트까지 같다
 *   9. 나머지 진입점(analyzeParallel · analyzeLegacy)
 *
 * Run: ./test_solid_ip_history
 */

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/HotspotClusterAnalyzer.hpp"
#include "kood3plot/analysis/SinglePassAnalyzer.hpp"
#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
#include "kood3plot/analysis/VectorMath.hpp"
#include "kood3plot/writer/D3plotWriter.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <limits>
#include <map>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

namespace {

namespace fs = std::filesystem;

constexpr int kElems = 8;
constexpr int kStates = 4;                              // 상태 0 은 전부 0
constexpr int kParts = 3;
constexpr int kPartOf[kElems] = {1, 1, 1, 2, 2, 2, 3, 3};
// 값이 실리는 적분점 자리 수 — 파트 1 은 육면체(8), 파트 2 는 사면체 둘(4)과 오면체(6), 파트 3 은 여덟 자리가 같은 값
constexpr int kUsedSlots[kElems] = {8, 8, 8, 4, 4, 6, 8, 8};
constexpr double kHistSentinel = 9.0e5;                 // 이력 변수 자리 — 응력 · 변형률로 읽히면 바로 드러난다
constexpr double kDt = 0.125;

enum Q { Q_VM, Q_S1, Q_S3, Q_EP, Q_EVM, Q_E1, Q_E3, kQ };
const char* const kQuantity[kQ] = {"von_mises", "max_principal_stress", "min_principal_stress",
                                   "eff_plastic_strain", "von_mises_strain", "max_principal_strain",
                                   "min_principal_strain"};
bool isMinQ(int q) { return q == Q_S3 || q == Q_E3; }

int g_failed = 0;
int g_checks = 0;

void expect(bool ok, const std::string& what) {
    ++g_checks;
    if (ok) return;
    ++g_failed;
    std::printf("    [FAIL] %s\n", what.c_str());
}

void expectNear(double got, double want, const std::string& what) {
    const bool ok = std::isfinite(got) && std::abs(got - want) <= 1e-9 * std::max(1.0, std::abs(want));
    char buf[96];
    std::snprintf(buf, sizeof(buf), " got=%.12g want=%.12g", got, want);
    expect(ok, what + buf);
}

bool sameBits(const std::vector<double>& a, const std::vector<double>& b) {
    return a.size() == b.size() && (a.empty() || std::memcmp(a.data(), b.data(), a.size() * sizeof(double)) == 0);
}

/// 사례 하나의 머리줄과 결과 줄. 그 사이에는 실패한 검사만 찍힌다.
struct Case {
    int failed0 = g_failed;
    explicit Case(const std::string& name) {
        g_checks = 0;
        std::printf("%s\n", name.c_str());
    }
    ~Case() {
        if (g_failed == failed0) std::printf("  [OK]   검사 %d개\n", g_checks);
        else std::printf("  [FAIL] %d건(검사 %d개)\n", g_failed - failed0, g_checks);
    }
};

/// 솔리드 요소 블록의 워드 배치
struct Deck {
    const char* name;
    int nip;            // 요소 블록에 적는 적분점 자리 수(1 또는 8)
    int hist;           // 변형률을 뺀 이력 변수 수
    bool strain;        // 이력 변수 끝에 변형률 6성분을 싣는다(IDTDT = 10000)
    bool same = false;  // 여덟 자리에 자리 0 의 값을 그대로 적는다
    int neiph = -1;     // 머리말 NEIPH — 음수면 실제 값(hist + 변형률 6)
    int P() const { return 7 + hist + (strain ? 6 : 0); }
    int nv3d() const { return nip * P(); }
    int headerNeiph() const { return neiph >= 0 ? neiph : hist + (strain ? 6 : 0); }
    /// 분석기가 여덟 자리로 알아봐야 하는 덱 — NV3D 가 8 × (7 + NEIPH) 와 정확히 맞는다
    bool eight() const { return nip == 8 && headerNeiph() == P() - 7; }
    /// 자리마다 값이 달라 적분점 극값이 자리 0 과 갈리는 덱
    bool multi() const { return eight() && !same; }
};

struct Ip {
    double s[6] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0};   // σxx σyy σzz σxy σyz σzx
    double ep = 0.0;
    double e[6] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0};   // εxx εyy εzz εxy εyz εzx
};

/// 요소 e(0부터) · 적분점 자리 p · 상태 s 의 값. 전부 단정밀도로 정확히 실리는 값이다(Writer 는 float 로 쓴다).
///
/// - 응력 크기 A = 8·T·(16 + q), q 는 자리 · 상태 · 요소로 도는 순열 — 가장 뜨거운 자리가 상태마다 바뀐다.
/// - 파트 1 의 육면체는 자리마다 응력 꼴이 다르다(단축 인장 · 전단 · 압축 · 인장) — σ_vm · σ1 · σ3 의 극값이 서로 다른
///   자리에서 난다. 요소 0 은 전단 꼴, 요소 1 은 인장 꼴, 요소 2 는 압축 꼴을 두 배로 실어 파트의 σ_vm · σ1 · σ3
///   피크가 서로 다른 요소에서 나고, 요소마다 피크 상태도 다르다.
/// - 요소 3 은 전부 압축, 요소 4 는 전부 인장 — 빈 자리(0)를 넣으면 σ1 최대 · σ3 최소가 가짜 0 이 된다.
/// - ε_p 와 변형률은 응력과 다른 순열을 탄다 — 응력이 가장 큰 자리와 변형률이 가장 큰 자리가 다르다.
Ip ipValue(int e, int p, int s) {
    Ip v;
    if (s == 0 || p >= kUsedSlots[e]) return v;

    static const int T[kElems][kStates] = {
        {0, 2, 6, 4}, {0, 2, 4, 6}, {0, 6, 2, 4},
        {0, 2, 4, 6}, {0, 6, 4, 2}, {0, 2, 6, 4},
        {0, 1, 2, 3}, {0, 3, 2, 1}};
    static const int E[kElems][kStates] = {
        {0, 1, 2, 3}, {0, 1, 2, 3}, {0, 3, 1, 2},       // 요소 2 는 ε_p 가 한 번 내려간다(러닝맥스 적분)
        {0, 1, 2, 3}, {0, 1, 2, 3}, {0, 1, 2, 3},
        {0, 1, 2, 3}, {0, 0, 0, 0}};                     // 요소 7 은 탄성(ε_p 0)
    static const double hex_shape[4][6] = {
        { 1.0,  0.25,  0.0,  0.25, 0.0,  0.0 },
        { 0.25, 0.0,  -0.25, 1.0,  0.5,  0.0 },
        {-2.0, -1.5,  -2.5,  0.0,  0.25, 0.0 },
        { 1.5,  1.25,  0.5,  0.0,  0.0,  0.25}};
    static const int hex_boost[3] = {1, 3, 2};
    static const double wedge_shape[3][6] = {
        { 2.0,  0.0,  0.0, 0.5, 0.0, 0.0},
        {-2.0, -1.0,  0.0, 0.0, 0.5, 0.0},
        { 0.0,  1.0, -1.0, 0.0, 0.0, 1.0}};
    static const double comp_shape[6] = {-3.0, -2.0, -1.0, 0.25, 0.0, 0.0};
    static const double tens_shape[6] = { 3.0,  2.0,  1.0, 0.0, 0.25, 0.0};
    static const double flat_shape[2][6] = {
        { 1.0, 0.0,  0.0, 0.0,  0.0, 0.0},
        {-0.5, 0.25, 0.0, 0.25, 0.0, 0.0}};

    const int pp = (e >= 6) ? 0 : p;                    // 파트 3 은 자리와 무관한 값
    const int q = (pp + 3 * s + 5 * e) % 8;
    const double A = 8.0 * T[e][s] * (16 + q);

    const double* shape = nullptr;
    double boost = 1.0;
    if (e < 3) {
        const int k = (pp + e) % 4;
        shape = hex_shape[k];
        if (k == hex_boost[e]) boost = 2.0;
    } else if (e == 3) {
        shape = comp_shape;
    } else if (e == 4) {
        shape = tens_shape;
    } else if (e == 5) {
        shape = wedge_shape[pp % 3];
    } else {
        shape = flat_shape[e - 6];
    }
    for (int k = 0; k < 6; ++k) v.s[k] = shape[k] * boost * A;

    v.ep = E[e][s] * (1 + (3 * pp + e) % 8) / 1024.0;

    const int q2 = (5 * pp + s + 3 * e) % 8;
    const double u = s / 4096.0;
    if (e == 3) {                                       // 주변형률이 전부 음수
        v.e[0] = -4.0 * (q2 + 1) * u;
        v.e[1] = -3.0 * (q2 + 1) * u;
        v.e[2] = -2.0 * (pp + 1) * u;
        v.e[3] = -0.5 * u;
    } else {
        v.e[0] = 4.0 * (q2 + 1) * u;
        v.e[1] = -1.0 * (q2 + 1) * u;
        v.e[2] = -2.0 * (pp + 1) * u;
        v.e[3] = (q2 + 2) * u;
        v.e[4] = 0.5 * (pp + 1) * u;
        v.e[5] = u;
    }
    return v;
}

/// 덱 D 의 요소 블록에 실제로 실리는 값 — 한 자리 덱 · 「같은 값」 덱은 자리 0 의 값이다
Ip deckValue(const Deck& D, int e, int p, int s) { return ipValue(e, (D.nip == 1 || D.same) ? 0 : p, s); }

/// 분석기가 봐야 하는 적분점 자리 — 앞 7 워드(응력 6 · ε_p) 중 하나라도 0 이 아닌 자리. 없으면 자리 0.
/// 여덟 자리로 알아볼 수 없는 덱 · 여덟 자리가 같은 값인 덱은 자리 0 하나다.
std::vector<int> usedIps(const Deck& D, int e, int s) {
    if (!D.multi()) return {0};
    std::vector<int> used;
    for (int p = 0; p < 8; ++p) {
        const Ip v = ipValue(e, p, s);
        bool any = (v.ep != 0.0);
        for (double x : v.s) any = any || (x != 0.0);
        if (any) used.push_back(p);
    }
    if (used.empty()) used.push_back(0);
    return used;
}

struct Meas { double vm, s1, s3, tau, ep, evm, e1, e3; };

Meas measure(const Ip& v) {
    const StressTensor t(v.s[0], v.s[1], v.s[2], v.s[3], v.s[4], v.s[5]);
    const auto p = t.principalStresses();
    const StressTensor et(v.e[0], v.e[1], v.e[2], v.e[3], v.e[4], v.e[5]);
    const auto pe = et.principalStresses();
    return {t.vonMises(), p[0], p[2], 0.5 * (p[0] - p[2]), v.ep,
            equivalentStrain(v.e[0], v.e[1], v.e[2], v.e[3], v.e[4], v.e[5]), pe[0], pe[2]};
}

double quantityOf(const Meas& m, int q) {
    switch (q) {
        case Q_VM: return m.vm;
        case Q_S1: return m.s1;
        case Q_S3: return m.s3;
        case Q_EP: return m.ep;
        case Q_EVM: return m.evm;
        case Q_E1: return m.e1;
        default: return m.e3;
    }
}

/// 요소 값 = 값이 실린 적분점의 극값
double elemValue(const Deck& D, int e, int s, int q) {
    const double big = std::numeric_limits<double>::max();
    double v = isMinQ(q) ? big : -big;
    for (int p : usedIps(D, e, s)) {
        const double x = quantityOf(measure(ipValue(e, p, s)), q);
        v = isMinQ(q) ? std::min(v, x) : std::max(v, x);
    }
    return v;
}

/// 핫스팟 기준 k(HotspotCriterion 의 값 0~6)의 적분점 값
double critValue(const Ip& v, const Meas& m, int k) {
    switch (k) {
        case 0: return m.vm;
        case 1: return m.s1;
        case 2: return m.s3;
        case 3: return m.tau;
        default: return v.s[k - 4];
    }
}

/// 기준 k 의 짝 변형률 측도
double strainMeasure(const Ip& v, const Meas& m, int k) {
    switch (k) {
        case 0: return m.evm;
        case 1: return m.e1;
        case 2: return m.e3;
        case 3: return 0.5 * (m.e1 - m.e3);
        default: return v.e[k - 4];
    }
}

struct HotRef {
    double value[7], time[7], strain[7];
    double ep_max = 0.0, ep_time = 0.0, work = 0.0;
};

/// 요소 e 의 핫스팟 극값 — 상태마다 가장 뜨거운 적분점, 그 가운데 가장 뜨거운 상태(먼저 난 쪽이 이긴다).
/// ε_p 와 소성 일은 적분점 평균 ε_p · σ_vm 으로 센다(셸 계열의 층 평균과 같은 규칙).
HotRef hotRef(const Deck& D, int e) {
    const double big = std::numeric_limits<double>::max();
    HotRef h;
    int best_s[7], best_p[7];
    for (int k = 0; k < 7; ++k) {
        h.value[k] = (k == 2) ? big : -big;
        best_s[k] = 0;
        best_p[k] = 0;
    }
    double prev_vm = 0.0, ep_run = 0.0;
    bool have_prev = false;
    for (int s = 0; s < kStates; ++s) {
        const std::vector<int> used = usedIps(D, e, s);
        double cur[7];
        int cur_p[7];
        for (int k = 0; k < 7; ++k) {
            cur[k] = (k == 2) ? big : -big;
            cur_p[k] = used.front();
        }
        double vm_sum = 0.0, ep_sum = 0.0;
        for (int p : used) {
            const Ip v = ipValue(e, p, s);
            const Meas m = measure(v);
            for (int k = 0; k < 7; ++k) {
                const double c = critValue(v, m, k);
                if ((k == 2) ? (c < cur[k]) : (c > cur[k])) { cur[k] = c; cur_p[k] = p; }
            }
            vm_sum += m.vm;
            ep_sum += v.ep;
        }
        const double vm_now = vm_sum / static_cast<double>(used.size());
        const double ep_now = ep_sum / static_cast<double>(used.size());
        if (ep_now > h.ep_max) { h.ep_max = ep_now; h.ep_time = kDt * s; }
        if (have_prev) {
            const double dep = ep_now - ep_run;
            if (dep > 0.0) h.work += 0.5 * (vm_now + prev_vm) * dep;
        }
        if (ep_now > ep_run) ep_run = ep_now;
        prev_vm = vm_now;
        have_prev = true;
        for (int k = 0; k < 7; ++k) {
            if ((k == 2) ? (cur[k] < h.value[k]) : (cur[k] > h.value[k])) {
                h.value[k] = cur[k];
                best_s[k] = s;
                best_p[k] = cur_p[k];
            }
        }
    }
    for (int k = 0; k < 7; ++k) {
        const Ip v = ipValue(e, best_p[k], best_s[k]);
        h.time[k] = kDt * best_s[k];
        h.strain[k] = strainMeasure(v, measure(v), k);
    }
    return h;
}

/// 군집 — (요소 순번, 가중)
const std::vector<std::pair<std::vector<size_t>, std::vector<double>>>& clusters() {
    static const std::vector<std::pair<std::vector<size_t>, std::vector<double>>> c = {
        {{0, 1, 2}, {1.0, 2.0, 4.0}}, {{3, 4, 5}, {1.0, 1.0, 1.0}}, {{6, 7}, {1.0, 3.0}}};
    return c;
}

/// 군집 ci 의 max_t(가중평균) — 요소 값은 적분점 평균. crit 는 HotspotCriterion 의 값(7 = ε_p).
double clusterRef(const Deck& D, size_t ci, int crit, double* t_out) {
    const auto& mem = clusters()[ci];
    double best = std::numeric_limits<double>::quiet_NaN();
    *t_out = 0.0;
    for (int s = 0; s < kStates; ++s) {
        double num = 0.0, den = 0.0;
        for (size_t i = 0; i < mem.first.size(); ++i) {
            const int e = static_cast<int>(mem.first[i]);
            const std::vector<int> used = usedIps(D, e, s);
            double acc = 0.0;
            for (int p : used) {
                const Ip v = ipValue(e, p, s);
                acc += (crit == 7) ? v.ep : critValue(v, measure(v), crit);
            }
            num += mem.second[i] * acc / static_cast<double>(used.size());
            den += mem.second[i];
        }
        const double m = num / den;
        if (!std::isfinite(best) || ((crit == 2) ? (m < best) : (m > best))) { best = m; *t_out = kDt * s; }
    }
    return best;
}

/// 절점 8개(정육면체 꼭짓점)를 함께 쓰는 솔리드 8개. 요소 ID = 순번 + 1(NARBS 0).
bool writeDeck(const std::string& path, const Deck& D) {
    data::ControlData control;
    control.NDIM = 4;
    control.NUMNP = 8;
    control.NEL8 = kElems;
    control.NELT = 0;
    control.NEL4 = 0;
    control.NEL2 = 0;
    control.NV3D = D.nv3d();
    control.NV2D = 0;
    control.NV1D = 0;
    control.NEIPH = D.headerNeiph();
    control.IDTDT = D.strain ? 10000 : 0;       // 10000 자리 = ISTRN
    control.NUMMAT8 = kParts;
    control.NMMAT = control.NUMMAT8;
    control.IU = 1;
    control.IV = 0;
    control.IA = 0;
    control.IT = 0;
    control.NGLBV = 6;
    control.NND = 3 * control.NUMNP;
    control.ENN = control.NEL8 * control.NV3D;

    data::Mesh mesh;
    mesh.nodes.resize(8);
    for (int i = 0; i < 8; ++i) {
        const int k = i % 4;
        mesh.nodes[i].id = i + 1;
        mesh.nodes[i].x = (k == 1 || k == 2) ? 1.0 : 0.0;
        mesh.nodes[i].y = (k >= 2) ? 1.0 : 0.0;
        mesh.nodes[i].z = i / 4;
    }
    mesh.solids.resize(kElems);
    mesh.solid_parts.assign(kPartOf, kPartOf + kElems);
    for (int e = 0; e < kElems; ++e) {
        mesh.solids[e].id = e + 1;
        mesh.solids[e].type = ElementType::SOLID;
        mesh.solids[e].material_id = kPartOf[e];
        for (int k = 1; k <= 8; ++k) mesh.solids[e].node_ids.push_back(k);
    }
    mesh.num_solids = kElems;
    mesh.num_thick_shells = 0;
    mesh.num_shells = 0;
    mesh.num_beams = 0;

    const int P = D.P();
    const int nv = D.nv3d();
    bool exact = true;
    std::vector<data::StateData> states;
    for (int s = 0; s < kStates; ++s) {
        data::StateData st;
        st.time = kDt * s;
        st.global_vars.assign(control.NGLBV, 0.0);
        st.node_displacements.resize(control.NUMNP * 3);
        for (int i = 0; i < control.NUMNP; ++i) {
            st.node_displacements[i * 3 + 0] = mesh.nodes[i].x;
            st.node_displacements[i * 3 + 1] = mesh.nodes[i].y;
            st.node_displacements[i * 3 + 2] = mesh.nodes[i].z;
        }
        st.solid_data.assign(static_cast<size_t>(kElems) * nv, 0.0);
        for (int e = 0; e < kElems; ++e) {
            for (int p = 0; p < D.nip; ++p) {
                const Ip v = deckValue(D, e, p, s);
                double* w = &st.solid_data[static_cast<size_t>(e) * nv + static_cast<size_t>(p) * P];
                for (int k = 0; k < 6; ++k) w[k] = v.s[k];
                w[6] = v.ep;
                for (int k = 0; k < D.hist; ++k) w[7 + k] = kHistSentinel;
                if (D.strain) {
                    for (int k = 0; k < 6; ++k) w[7 + D.hist + k] = v.e[k];
                }
            }
        }
        for (double x : st.solid_data) exact = exact && (static_cast<double>(static_cast<float>(x)) == x);
        states.push_back(std::move(st));
    }
    expect(exact, "덱에 적는 값이 전부 단정밀도로 정확히 실린다");

    writer::D3plotWriter w(path);
    w.setControlData(control);
    w.setMesh(mesh);
    w.setStates(states);
    return w.write() == ErrorCode::SUCCESS;
}

std::string deckPath(const fs::path& dir, const std::string& name) {
    fs::create_directories(dir / name);
    return (dir / name / "d3plot").string();
}

enum class Entry { WithStates, Parallel, Legacy };

struct Run {
    bool opened = false;
    AnalysisResult res;
    std::string out;                            // 분석 중 std::cout 에 찍힌 것
    std::string err;                            // 분석 중 std::cerr 에 찍힌 것
    // 핫스팟 — WithStates 진입점에서만 채운다. 키는 HotspotCriterion 의 값
    std::map<int, ElementExtremes> ex;
    std::vector<double> ep_max, work;
    std::map<int, std::vector<double>> agg_v, agg_t;
};

Run runDeck(const std::string& path, Entry entry) {
    Run r;
    D3plotReader reader(path);
    if (reader.open() != ErrorCode::SUCCESS) return r;
    r.opened = true;

    AnalysisConfig cfg;
    cfg.d3plot_path = path;
    cfg.analyze_stress = true;
    cfg.analyze_strain = true;
    cfg.hotspot_enabled = (entry == Entry::WithStates);
    cfg.hotspot_criteria.clear();
    for (HotspotCriterion c : allHotspotCriteria()) cfg.hotspot_criteria.push_back(hotspotCriterionName(c));

    std::ostringstream cap_out, cap_err;
    std::streambuf* old_out = std::cout.rdbuf(cap_out.rdbuf());
    std::streambuf* old_err = std::cerr.rdbuf(cap_err.rdbuf());
    {
        SinglePassAnalyzer sp(reader);
        if (entry == Entry::WithStates) {
            auto states = reader.read_all_states();
            r.res = sp.analyzeWithStates(cfg, states, nullptr);
            for (HotspotCriterion c : allHotspotCriteria()) {
                const int k = static_cast<int>(c);
                r.ex[k] = sp.elementExtremes(HotspotElementKind::Solid, c);
                sp.clusterTimeAggregate(states, HotspotElementKind::Solid, c, clusters(), r.agg_v[k], r.agg_t[k]);
            }
            r.ep_max = sp.plasticStrainMax(HotspotElementKind::Solid);
            r.work = sp.plasticWorkDensity(HotspotElementKind::Solid);
        } else if (entry == Entry::Parallel) {
            r.res = sp.analyzeParallel(cfg);
        } else {
            r.res = sp.analyzeLegacy(cfg);
        }
    }
    std::cout.rdbuf(old_out);
    std::cerr.rdbuf(old_err);
    r.out = cap_out.str();
    r.err = cap_err.str();
    return r;
}

const PartTimeSeriesStats* findRow(const std::vector<PartTimeSeriesStats>& hist, int pid) {
    for (const auto& r : hist) {
        if (r.part_id == pid) return &r;
    }
    return nullptr;
}

const std::vector<PartTimeSeriesStats>& historyOf(const AnalysisResult& res, int q) {
    switch (q) {
        case Q_VM: return res.stress_history;
        case Q_S1: return res.max_principal_history;
        case Q_S3: return res.min_principal_history;
        case Q_EP: return res.strain_history;
        case Q_EVM: return res.vm_strain_history;
        case Q_E1: return res.max_principal_strain_history;
        default: return res.min_principal_strain_history;
    }
}

/// 파트 이력 일곱 종을 기대값과 맞춘다 — 상태마다 요소 값의 최대 · 최소 · 평균과 그 요소 ID.
void checkRows(const Deck& D, const AnalysisResult& res) {
    for (int q = 0; q < kQ; ++q) {
        const auto& hist = historyOf(res, q);
        const std::string qt = kQuantity[q];
        if (q > Q_EP && !D.strain) {
            expect(hist.empty(), qt + ": 변형률을 기록하지 않은 덱 — 이력이 없다");
            continue;
        }
        expect(hist.size() == static_cast<size_t>(kParts), qt + ": 파트 줄 수");
        for (int pid = 1; pid <= kParts; ++pid) {
            const std::string tag = qt + " 파트 " + std::to_string(pid);
            const PartTimeSeriesStats* row = findRow(hist, pid);
            expect(row != nullptr, tag + ": 이력 줄이 있다");
            if (!row) continue;
            expect(row->element_type.empty(), tag + ": element_type 이 비어 있다(솔리드)");
            expect(row->quantity == kQuantity[q], tag + ": quantity 이름(" + row->quantity + ")");
            expect(row->data.size() == static_cast<size_t>(kStates), tag + ": 상태 수");

            for (int s = 0; s < kStates && s < static_cast<int>(row->data.size()); ++s) {
                const auto& tp = row->data[s];
                const std::string at = tag + " 상태 " + std::to_string(s);
                double vmax = -std::numeric_limits<double>::max(), vmin = std::numeric_limits<double>::max();
                double sum = 0.0;
                int emax = -1, emin = -1, nmax = 0, nmin = 0, n = 0;
                for (int e = 0; e < kElems; ++e) {
                    if (kPartOf[e] != pid) continue;
                    const double x = elemValue(D, e, s, q);
                    if (x > vmax) { vmax = x; emax = e; nmax = 1; } else if (x == vmax) ++nmax;
                    if (x < vmin) { vmin = x; emin = e; nmin = 1; } else if (x == vmin) ++nmin;
                    sum += x;
                    ++n;
                }
                expectNear(tp.time, kDt * s, at + " 시각");
                expectNear(tp.max_value, vmax, at + " 최대");
                expectNear(tp.min_value, vmin, at + " 최소");
                expectNear(tp.avg_value, sum / n, at + " 평균");
                // 값이 같은 요소가 둘이면(상태 0 — 전부 0) 어느 쪽 ID 든 맞다
                if (nmax == 1) expect(tp.max_element_id == emax + 1, at + " 최대 요소 ID");
                if (nmin == 1) expect(tp.min_element_id == emin + 1, at + " 최소 요소 ID");
            }
        }
    }
    expect(res.metadata.analyzed_parts == std::vector<int32_t>({1, 2, 3}), "analyzed_parts = {1, 2, 3}");
}

/// 피크 요소 텐서 이력 — 피크 시각에 극값을 낸 적분점 하나의 이력이어야 한다.
/// 어느 요소 · 어느 시각이 피크인지는 (checkRows 가 따로 맞춘) 파트 이력에서 분석기와 같은 규칙으로 고른다.
void checkPeakTensors(const Deck& D, const AnalysisResult& res) {
    struct Want { int part; int elem; const char* reason; double value; double time; int q; };
    std::vector<Want> want;
    const struct { int q; const char* reason; } src[3] = {
        {Q_VM, "peak_von_mises"}, {Q_S1, "peak_max_principal"}, {Q_S3, "peak_min_principal"}};
    for (const auto& sr : src) {
        const bool is_min = isMinQ(sr.q);
        for (const auto& row : historyOf(res, sr.q)) {
            double best = is_min ? std::numeric_limits<double>::infinity() : -std::numeric_limits<double>::infinity();
            int elem = 0;
            double t = 0.0;
            for (const auto& tp : row.data) {
                const double v = is_min ? tp.min_value : tp.max_value;
                if (is_min ? (v < best) : (v > best)) {
                    best = v;
                    elem = is_min ? tp.min_element_id : tp.max_element_id;
                    t = tp.time;
                }
            }
            if (elem == 0) continue;
            bool dup = false;
            for (const Want& w : want) dup = dup || (w.part == row.part_id && w.elem == elem);
            if (!dup) want.push_back({row.part_id, elem, sr.reason, best, t, sr.q});
        }
    }

    expect(res.peak_element_tensors.size() == want.size(),
           "피크 텐서 이력 수 " + std::to_string(res.peak_element_tensors.size()) + " (기대 " +
               std::to_string(want.size()) + ")");
    if (D.multi()) {
        // 설계 — 파트 1 은 σ_vm · σ1 · σ3 피크가 요소 1 · 2 · 3 에서 따로 난다(적분점 고르는 규칙 셋을 다 탄다)
        int hit = 0;
        for (const Want& w : want) {
            if (w.part != 1) continue;
            if ((w.q == Q_VM && w.elem == 1) || (w.q == Q_S1 && w.elem == 2) || (w.q == Q_S3 && w.elem == 3)) ++hit;
        }
        expect(hit == 3, "파트 1 의 σ_vm · σ1 · σ3 피크가 요소 1 · 2 · 3 에서 난다");
    }

    for (size_t i = 0; i < want.size() && i < res.peak_element_tensors.size(); ++i) {
        const Want& w = want[i];
        const auto& h = res.peak_element_tensors[i];
        const std::string tag = std::string(w.reason) + " 파트 " + std::to_string(w.part) + " 요소 " +
                                std::to_string(w.elem);
        expect(h.part_id == w.part && h.element_id == w.elem && h.reason == w.reason,
               tag + ": 순서 · 사유(" + h.reason + " 파트 " + std::to_string(h.part_id) + " 요소 " +
                   std::to_string(h.element_id) + ")");
        expectNear(h.peak_value, w.value, tag + " 피크 값");
        expectNear(h.peak_time, w.time, tag + " 피크 시각");

        // 피크 상태에서 이 사유의 극값을 낸 적분점(먼저 난 쪽)
        const int e = w.elem - 1;
        const int si = static_cast<int>(std::lround(w.time / kDt));
        const bool is_min = isMinQ(w.q);
        int ip = -1;
        double bv = 0.0;
        for (int p : usedIps(D, e, si)) {
            const double v = quantityOf(measure(ipValue(e, p, si)), w.q);
            if (ip < 0 || (is_min ? (v < bv) : (v > bv))) { bv = v; ip = p; }
        }
        expectNear(bv, w.value, tag + ": 그 적분점의 값이 피크 값이다");

        const bool sized = h.time.size() == static_cast<size_t>(kStates) && h.sxx.size() == h.time.size() &&
                           h.syy.size() == h.time.size() && h.szz.size() == h.time.size() &&
                           h.sxy.size() == h.time.size() && h.syz.size() == h.time.size() &&
                           h.szx.size() == h.time.size();
        expect(sized, tag + ": 이력 길이");
        if (!sized) continue;
        for (int s = 0; s < kStates; ++s) {
            const Ip v = ipValue(e, ip, s);
            const double got[6] = {h.sxx[s], h.syy[s], h.szz[s], h.sxy[s], h.syz[s], h.szx[s]};
            const std::string at = tag + " 상태 " + std::to_string(s);
            expectNear(h.time[s], kDt * s, at + " 시각");
            for (int k = 0; k < 6; ++k) expectNear(got[k], v.s[k], at + " 성분 " + std::to_string(k));
        }
    }
}

/// 핫스팟 요소 극값 · ε_p 최대 · 소성 일 · 군집 시각 집계
void checkHotspots(const Deck& D, const Run& r) {
    const double t_end = kDt * (kStates - 1);
    for (int k = 0; k < kHotspotCritSlots; ++k) {
        const std::string tag = std::string("핫스팟 ") + hotspotCriterionName(static_cast<HotspotCriterion>(k));
        const auto it = r.ex.find(k);
        const bool sized = it != r.ex.end() && it->second.value.size() == static_cast<size_t>(kElems) &&
                           it->second.time.size() == static_cast<size_t>(kElems);
        expect(sized, tag + ": 요소 극값 배열");
        if (!sized) return;
        const ElementExtremes& ex = it->second;
        expect(ex.layer.empty(), tag + ": 솔리드는 층 번호를 싣지 않는다");
        if (k < kHotspotStressCritSlots && D.strain) {
            expect(ex.strain.size() == static_cast<size_t>(kElems), tag + ": 짝 변형률 배열");
        } else {
            expect(ex.strain.empty(), tag + ": 짝 변형률이 없다");
        }
    }
    expect(r.ep_max.size() == static_cast<size_t>(kElems) && r.work.size() == static_cast<size_t>(kElems),
           "ε_p 최대 · 소성 일 배열");
    if (r.ep_max.size() != static_cast<size_t>(kElems) || r.work.size() != static_cast<size_t>(kElems)) return;

    for (int e = 0; e < kElems; ++e) {
        const HotRef h = hotRef(D, e);
        for (int k = 0; k < kHotspotStressCritSlots; ++k) {
            const ElementExtremes& ex = r.ex.at(k);
            const std::string at = std::string("핫스팟 ") + hotspotCriterionName(static_cast<HotspotCriterion>(k)) +
                                   " 요소 " + std::to_string(e + 1);
            expectNear(ex.value[e], h.value[k], at + " 값");
            expectNear(ex.time[e], h.time[k], at + " 시각");
            if (ex.strain.size() == static_cast<size_t>(kElems)) expectNear(ex.strain[e], h.strain[k], at + " 짝 변형률");
        }
        const std::string at = "요소 " + std::to_string(e + 1);
        expectNear(r.ep_max[e], h.ep_max, at + " ε_p 최대(적분점 평균)");
        expectNear(r.work[e], h.work, at + " 소성 일(적분점 평균 σ_vm · ε_p)");
        const ElementExtremes& ep = r.ex.at(static_cast<int>(HotspotCriterion::PlasticStrain));
        const ElementExtremes& wk = r.ex.at(static_cast<int>(HotspotCriterion::PlasticWork));
        expectNear(ep.value[e], h.ep_max, at + " plastic_strain 기준 값");
        expectNear(ep.time[e], h.ep_time, at + " plastic_strain 기준 시각");
        expectNear(wk.value[e], h.work, at + " plastic_work 기준 값");
        expectNear(wk.time[e], t_end, at + " plastic_work 기준 시각(끝)");
    }

    static const int crits[] = {0, 1, 2, 3, 4, 7};
    for (int c : crits) {
        const std::string tag = std::string("군집 ") + hotspotCriterionName(static_cast<HotspotCriterion>(c));
        const auto iv = r.agg_v.find(c);
        const auto itv = r.agg_t.find(c);
        const bool sized = iv != r.agg_v.end() && itv != r.agg_t.end() && iv->second.size() == clusters().size() &&
                           itv->second.size() == clusters().size();
        expect(sized, tag + ": 집계 배열");
        if (!sized) continue;
        for (size_t ci = 0; ci < clusters().size(); ++ci) {
            double t = 0.0;
            const double v = clusterRef(D, ci, c, &t);
            expectNear(iv->second[ci], v, tag + " " + std::to_string(ci) + " 값(적분점 평균)");
            expectNear(itv->second[ci], t, tag + " " + std::to_string(ci) + " 시각");
        }
    }
    const auto iw = r.agg_v.find(static_cast<int>(HotspotCriterion::PlasticWork));
    expect(iw != r.agg_v.end() && iw->second.size() == clusters().size() && std::isnan(iw->second[0]),
           "군집 plastic_work: 시각 집계를 내지 않는다(NaN)");
}

/// 기대값 계산 자체를 손으로 푼 값과 맞춘다 — 아래 사례들이 빈 검사가 되지 않게.
void caseReference() {
    Case c("기준 계산 점검 — 손으로 푼 값 · 덱 설계");
    const Deck one{"", 1, 0, false};
    const Deck eight{"", 8, 0, false};

    // 요소 6(0부터)은 x 축 단축 인장 — σ_vm = σxx = 8·T·(16 + q). 상태 3: T 3 · q 7 → 552
    expectNear(elemValue(one, 6, 3, Q_VM), 552.0, "요소 6 σ_vm(한 자리)");
    expectNear(elemValue(eight, 6, 3, Q_VM), 552.0, "요소 6 σ_vm(여덟 자리 — 같은 값)");
    // 요소 4 는 (3, 2, 1, 0, 0.25, 0)·A — σ_vm = A·√3.1875. 상태 2 에서 자리 0 은 A 576, 가장 큰 자리(3)는 672
    expectNear(elemValue(one, 4, 2, Q_VM), 576.0 * std::sqrt(3.1875), "요소 4 σ_vm(자리 0)");
    expectNear(elemValue(eight, 4, 2, Q_VM), 672.0 * std::sqrt(3.1875), "요소 4 σ_vm(적분점 최대)");
    // 전부 압축인 요소 3 · 전부 인장인 요소 4 — 빈 자리(0)가 끼면 0 이 된다
    expect(elemValue(eight, 3, 2, Q_S1) < 0.0, "요소 3 의 σ1 최대는 음수다");
    expect(elemValue(eight, 4, 2, Q_S3) > 0.0, "요소 4 의 σ3 최소는 양수다");
    expect(elemValue(eight, 3, 2, Q_E1) < 0.0, "요소 3 의 ε1 최대는 음수다");
    expect(usedIps(eight, 0, 2).size() == 8 && usedIps(eight, 3, 2).size() == 4 &&
               usedIps(eight, 5, 2).size() == 6 && usedIps(eight, 0, 0).size() == 1,
           "값이 실린 자리 수 — 육면체 8 · 사면체 4 · 오면체 6 · 상태 0 은 자리 0 하나");

    // 파트 1 — σ_vm · σ1 · σ3 피크가 요소 0 · 1 · 2 에서, 서로 다른 상태에 난다
    const int want_e[3] = {0, 1, 2};
    const int want_s[3] = {2, 3, 1};
    const int qs[3] = {Q_VM, Q_S1, Q_S3};
    for (int i = 0; i < 3; ++i) {
        const bool is_min = isMinQ(qs[i]);
        double best = 0.0;
        int be = -1, bs = -1;
        for (int s = 0; s < kStates; ++s) {
            for (int e = 0; e < 3; ++e) {
                const double x = elemValue(eight, e, s, qs[i]);
                if (be < 0 || (is_min ? (x < best) : (x > best))) { best = x; be = e; bs = s; }
            }
        }
        expect(be == want_e[i] && bs == want_s[i],
               std::string(kQuantity[qs[i]]) + " 파트 1 피크 — 요소 " + std::to_string(be) + " 상태 " +
                   std::to_string(bs));
    }

    // 여덟 자리 덱의 요소 값이 자리 0 값과 실제로 갈린다(파트 1 · 2 의 모든 양)
    int differ = 0, total = 0;
    for (int q = 0; q <= Q_EP; ++q) {
        for (int e = 0; e < 6; ++e) {
            for (int s = 1; s < kStates; ++s) {
                ++total;
                if (elemValue(one, e, s, q) != elemValue(eight, e, s, q)) ++differ;
            }
        }
    }
    expect(differ * 2 > total, "적분점 극값이 자리 0 값과 다른 경우가 절반을 넘는다(" + std::to_string(differ) + "/" +
                                   std::to_string(total) + ")");
}

void caseDeck(const fs::path& dir, const Deck& D, const std::string& folder) {
    Case c(std::string(D.name) + " — NV3D " + std::to_string(D.nv3d()) + " · NEIPH " +
           std::to_string(D.headerNeiph()));
    const std::string path = deckPath(dir, folder);
    expect(writeDeck(path, D), "덱 쓰기");

    const Run r = runDeck(path, Entry::WithStates);
    expect(r.opened, "덱 열기");
    if (!r.opened) return;
    checkRows(D, r.res);
    checkPeakTensors(D, r.res);
    checkHotspots(D, r);
    // 적분점을 나눠 읽었다는 안내 한 줄 — 여덟 자리로 알아본 덱에서만
    const bool said = r.out.find("적분점 8개") != std::string::npos;
    expect(said == D.eight(), D.eight() ? "여덟 자리로 읽었다는 안내 줄이 있다" : "한 자리 덱에는 안내 줄이 없다");

    static const std::pair<Entry, const char*> others[] = {{Entry::Parallel, "analyzeParallel"},
                                                           {Entry::Legacy, "analyzeLegacy"}};
    for (const auto& o : others) {
        const int failed0 = g_failed;
        const Run ro = runDeck(path, o.first);
        expect(ro.opened, "덱 열기");
        if (!ro.opened) continue;
        checkRows(D, ro.res);
        checkPeakTensors(D, ro.res);
        if (g_failed != failed0) std::printf("    (위 %d건은 %s 진입점)\n", g_failed - failed0, o.second);
    }
}

void expectSameHistory(const std::vector<PartTimeSeriesStats>& a, const std::vector<PartTimeSeriesStats>& b,
                       const std::string& what) {
    bool same = a.size() == b.size();
    for (size_t i = 0; same && i < a.size(); ++i) {
        same = a[i].part_id == b[i].part_id && a[i].quantity == b[i].quantity &&
               a[i].element_type == b[i].element_type && a[i].data.size() == b[i].data.size();
        for (size_t s = 0; same && s < a[i].data.size(); ++s) {
            const auto& x = a[i].data[s];
            const auto& y = b[i].data[s];
            const double xv[5] = {x.time, x.max_value, x.min_value, x.avg_value, x.rms_value};
            const double yv[5] = {y.time, y.max_value, y.min_value, y.avg_value, y.rms_value};
            same = std::memcmp(xv, yv, sizeof(xv)) == 0 && x.max_element_id == y.max_element_id &&
                   x.min_element_id == y.min_element_id;
        }
    }
    expect(same, what + ": 비트까지 같다");
}

/// 여덟 자리에 같은 값을 적은 덱(1점 적분 요소를 NINTSLD 8 로 적은 덱 — 배터리 · 테이프 덱)은
/// 한 자리 덱과 결과가 비트까지 같아야 한다.
void caseSameBits(const fs::path& dir, const Deck& same, const Deck& one, const std::string& folder) {
    Case c(std::string("비트 대조 — 「") + same.name + "」 대 「" + one.name + "」");
    const std::string pa = deckPath(dir, folder + "_same");
    const std::string pb = deckPath(dir, folder + "_one");
    expect(writeDeck(pa, same) && writeDeck(pb, one), "덱 쓰기");
    const Run a = runDeck(pa, Entry::WithStates);
    const Run b = runDeck(pb, Entry::WithStates);
    expect(a.opened && b.opened, "덱 열기");
    if (!a.opened || !b.opened) return;

    for (int q = 0; q < kQ; ++q) expectSameHistory(historyOf(a.res, q), historyOf(b.res, q), kQuantity[q]);

    bool peaks = a.res.peak_element_tensors.size() == b.res.peak_element_tensors.size();
    for (size_t i = 0; peaks && i < a.res.peak_element_tensors.size(); ++i) {
        const auto& x = a.res.peak_element_tensors[i];
        const auto& y = b.res.peak_element_tensors[i];
        peaks = x.element_id == y.element_id && x.part_id == y.part_id && x.reason == y.reason &&
                sameBits({x.peak_value, x.peak_time}, {y.peak_value, y.peak_time}) && sameBits(x.time, y.time) &&
                sameBits(x.sxx, y.sxx) && sameBits(x.syy, y.syy) && sameBits(x.szz, y.szz) &&
                sameBits(x.sxy, y.sxy) && sameBits(x.syz, y.syz) && sameBits(x.szx, y.szx);
    }
    expect(peaks, "피크 요소 텐서 이력: 비트까지 같다");

    for (int k = 0; k < kHotspotCritSlots; ++k) {
        const std::string tag = std::string("핫스팟 ") + hotspotCriterionName(static_cast<HotspotCriterion>(k));
        const auto ia = a.ex.find(k);
        const auto ib = b.ex.find(k);
        const bool have = ia != a.ex.end() && ib != b.ex.end() && !ia->second.value.empty();
        expect(have, tag + ": 요소 극값이 있다");
        if (!have) continue;
        expect(sameBits(ia->second.value, ib->second.value) && sameBits(ia->second.time, ib->second.time) &&
                   sameBits(ia->second.strain, ib->second.strain),
               tag + " 요소 극값: 비트까지 같다");
        expect(sameBits(a.agg_v.at(k), b.agg_v.at(k)) && sameBits(a.agg_t.at(k), b.agg_t.at(k)),
               tag + " 군집 집계: 비트까지 같다");
    }
    expect(!a.ep_max.empty() && sameBits(a.ep_max, b.ep_max), "ε_p 최대: 비트까지 같다");
    expect(!a.work.empty() && sameBits(a.work, b.work), "소성 일: 비트까지 같다");
}

}  // namespace

int main() {
    std::printf("=== 솔리드 적분점 여덟 개 덱 검증 (합성 d3plot) ===\n\n");

    const fs::path dir = fs::temp_directory_path() / "kood3plot_solid_ip_history_test";
    fs::remove_all(dir);

    const Deck decks[] = {
        {"한 자리", 1, 0, false},
        {"한 자리 · 이력 변수 3 · 변형률", 1, 3, true},
        {"여덟 자리", 8, 0, false},
        {"여덟 자리 · 이력 변수 3 · 변형률", 8, 3, true},
        {"여덟 자리 · 변형률만", 8, 0, true},
        {"여덟 자리가 같은 값", 8, 0, false, true},
        {"여덟 자리가 같은 값 · 이력 변수 3 · 변형률", 8, 3, true, true},
        {"머리말 식과 맞지 않는다 — 한 자리로 읽는다", 8, 0, false, false, 1},
    };

    caseReference();
    int n = 0;
    for (const Deck& D : decks) caseDeck(dir, D, "deck" + std::to_string(n++));
    caseSameBits(dir, decks[5], decks[0], "bits0");
    caseSameBits(dir, decks[6], decks[1], "bits1");

    fs::remove_all(dir);

    std::printf("\n");
    if (g_failed) {
        std::printf("%d건 실패\n", g_failed);
        return 1;
    }
    std::printf("전부 통과\n");
    return 0;
}
