// 소프트웨어 단면 렌더의 절점 평균(NodalAverager)이 요소 값을 바르게 읽어 절점에 나누는지 메모리의 메시 · 상태로 검증하는 시험
/**
 * @file test_nodal_averager.cpp
 * @brief NodalAverager 의 요소 값 → 절점 값 규칙 검증 (덱 없이 Mesh · ControlData · StateData 를 직접 만든다)
 *
 * 단면 그림의 색, 컬러바 양 끝의 숫자, 세그먼트 라벨의 숫자, `center_mode: peak` 가 고르는 자리가 전부 이 절점 값에서
 * 난다. 기대값은 NodalAverager 코드와 따로, 생성식에서 바로 낸다.
 *
 * 검증 항목
 *   1. 적분점 여덟 자리 솔리드(NINTSLD 8) — 요소 값은 값이 실린 자리 가운데 가장 큰 값이다(LS-PrePost 의 기본
 *      「max IP. value」, 파트 표와 같은 규칙). 첫 자리만 읽으면 요소 한 귀퉁이의 값을 요소 전체의 값처럼 절점에 나눈다
 *   2. 사면체처럼 뒤 자리가 0 으로 실린 요소 — 빈 자리는 세지 않는다(압력이 전부 음수여도 0 이 최대로 뽑히지 않는다)
 *   3. 한 자리 덱, 머리말 식과 맞지 않는 덱은 종전 그대로(요소 블록의 앞 7 워드)
 *   4. 여덟 자리에 같은 값을 적은 덱은 한 자리 덱과 절점 값이 비트까지 같다
 *
 * Run: ./test_nodal_averager
 */

#include "kood3plot/section_render/NodalAverager.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

using namespace kood3plot;
using kood3plot::section_render::FieldSelector;
using kood3plot::section_render::NodalAverager;
using kood3plot::section_render::PartMatcher;

namespace {

constexpr int kElems = 3;                               // 육면체 둘 + 사면체 하나
constexpr int kNodes = 13;
constexpr int kStates = 3;                              // 상태 0 은 전부 0
constexpr int kUsedSlots[kElems] = {8, 8, 4};           // 값이 실리는 적분점 자리 수
constexpr double kHistSentinel = 9.0e5;                 // 이력 변수 자리 — 응력으로 읽히면 바로 드러난다
constexpr int kMaxPrint = 8;                            // 사례 하나에서 찍는 실패 줄 수

// 요소 연결성(1부터 세는 내부 절점 번호). 육면체 A · B 가 면 하나를, B 와 사면체 C 가 절점 셋을 나눠 쓴다.
// 사면체는 d3plot 이 적는 그대로 넷째 절점을 되풀이한다.
constexpr int kConn[kElems][8] = {
    {1, 2, 3, 4, 5, 6, 7, 8},
    {2, 9, 10, 3, 6, 11, 12, 7},
    {9, 10, 11, 13, 13, 13, 13, 13}};
constexpr double kXyz[kNodes][3] = {
    {0, 0, 0}, {1, 0, 0}, {1, 1, 0}, {0, 1, 0}, {0, 0, 1}, {1, 0, 1}, {1, 1, 1}, {0, 1, 1},
    {2, 0, 0}, {2, 1, 0}, {2, 0, 1}, {2, 1, 1}, {3, 0.5, 0.5}};

int g_failed = 0;
int g_checks = 0;
int g_case_failed0 = 0;

void expect(bool ok, const std::string& what) {
    ++g_checks;
    if (ok) return;
    ++g_failed;
    if (g_failed - g_case_failed0 <= kMaxPrint) std::printf("    [FAIL] %s\n", what.c_str());
}

void expectNear(double got, double want, const std::string& what) {
    const bool ok = std::isfinite(got) && std::abs(got - want) <= 1e-12 * std::max(1.0, std::abs(want));
    char buf[96];
    std::snprintf(buf, sizeof(buf), " got=%.15g want=%.15g", got, want);
    expect(ok, what + buf);
}

bool sameBits(const std::vector<double>& a, const std::vector<double>& b) {
    return a.size() == b.size() && (a.empty() || std::memcmp(a.data(), b.data(), a.size() * sizeof(double)) == 0);
}

/// 사례 하나의 머리줄과 결과 줄. 그 사이에는 실패한 검사만(처음 몇 줄) 찍힌다.
struct Case {
    explicit Case(const std::string& name) {
        g_checks = 0;
        g_case_failed0 = g_failed;
        std::printf("%s\n", name.c_str());
    }
    ~Case() {
        if (g_failed == g_case_failed0) std::printf("  [OK]   검사 %d개\n", g_checks);
        else std::printf("  [FAIL] %d건(검사 %d개)\n", g_failed - g_case_failed0, g_checks);
    }
};

/// 솔리드 요소 블록의 워드 배치
struct Deck {
    const char* name;
    int nip;            // 요소 블록에 적는 적분점 자리 수(1 또는 8)
    int hist;           // 변형률을 뺀 이력 변수 수
    bool strain;        // 이력 변수 끝에 변형률 6성분을 싣는다
    bool same = false;  // 여덟 자리에 자리 0 의 값을 그대로 적는다
    int neiph = -1;     // 머리말 NEIPH — 음수면 실제 값(hist + 변형률 6)
    int P() const { return 7 + hist + (strain ? 6 : 0); }
    int nv3d() const { return nip * P(); }
    int headerNeiph() const { return neiph >= 0 ? neiph : hist + (strain ? 6 : 0); }
    /// 여덟 자리로 알아봐야 하는 덱 — NV3D 가 8 × (7 + NEIPH) 와 정확히 맞는다
    bool eight() const { return nip == 8 && headerNeiph() == P() - 7; }
    /// 자리마다 값이 달라 요소 값이 자리 0 과 갈리는 덱
    bool multi() const { return eight() && !same; }
};

struct Ip {
    double s[6] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0};   // σxx σyy σzz σxy σyz σzx
    double ep = 0.0;
};

/// 자리 · 성분 · 요소로 도는 정수(-6..6) — 자리마다 부호까지 바뀌고, 어느 값에서도 가장 큰 자리가 첫 자리가 아니다
int wobble(int e, int p, int k) { return (7 * p + 3 * k + 5 * e + 5) % 13 - 6; }

/// 요소 e(0부터) · 적분점 자리 p · 상태 s 의 값
Ip ipValue(int e, int p, int s) {
    Ip v;
    if (s == 0 || p >= kUsedSlots[e]) return v;

    static const double s_base[kElems][6] = {
        { 96.0,  32.0, -16.0,  24.0,  -8.0,  12.0},
        {-64.0, 128.0,  40.0, -20.0,  28.0,   4.0},
        {160.0, 112.0,  72.0,  20.0, -12.0,  28.0}};
    for (int k = 0; k < 6; ++k) v.s[k] = s * (s_base[e][k] + 16.0 * wobble(e, p, k));
    v.ep = s * (40.0 + 8.0 * e + wobble(e, p, 6)) / 4096.0;
    return v;
}

/// 덱이 요소 e 의 자리 p 에 실제로 적는 값 — 같은 값 덱은 자리 0 의 값을 여덟 번 적는다
Ip written(const Deck& d, int e, int p, int s) { return ipValue(e, d.same ? 0 : p, s); }

/// 값이 실린 자리의 평균 텐서 · ε_p — 기준값 점검에서만 쓴다(가장 큰 자리의 값과 갈리는지)
Ip meanOfUsed(int e, int s) {
    Ip m;
    const int n = kUsedSlots[e];
    for (int p = 0; p < n; ++p) {
        const Ip v = ipValue(e, p, s);
        for (int k = 0; k < 6; ++k) m.s[k] += v.s[k];
        m.ep += v.ep;
    }
    for (int k = 0; k < 6; ++k) m.s[k] /= n;
    m.ep /= n;
    return m;
}

double vonMises(const double* s) {
    const double a = s[0] - s[1], b = s[1] - s[2], c = s[2] - s[0];
    return std::sqrt(0.5 * (a * a + b * b + c * c) + 3.0 * (s[3] * s[3] + s[4] * s[4] + s[5] * s[5]));
}

struct Field {
    FieldSelector sel;
    const char* name;
};
const Field kFields[] = {
    {FieldSelector::VonMises, "σ_vm"},
    {FieldSelector::EffectivePlasticStrain, "ε_p"},
    {FieldSelector::PressureStress, "압력"},
};

double scalarOf(FieldSelector f, const Ip& v) {
    switch (f) {
        case FieldSelector::EffectivePlasticStrain: return v.ep;
        case FieldSelector::PressureStress:         return -(v.s[0] + v.s[1] + v.s[2]) / 3.0;
        default:                                    return vonMises(v.s);
    }
}

/// NodalAverager 가 요소 값으로 삼아야 하는 값 — 값이 실린 자리마다 낸 스칼라 가운데 가장 큰 것
double expectedElem(const Deck& d, int e, int s, FieldSelector f) {
    if (!d.multi()) return scalarOf(f, written(d, e, 0, s));   // 한 자리 · 같은 값 · 머리말 불일치 — 앞 7 워드
    if (s == 0) return scalarOf(f, Ip{});                      // 전부 0 인 상태 — 쓰인 자리가 없어 첫 자리를 읽는다
    double best = scalarOf(f, ipValue(e, 0, s));
    for (int p = 1; p < kUsedSlots[e]; ++p) best = std::max(best, scalarOf(f, ipValue(e, p, s)));
    return best;
}

data::Mesh buildMesh() {
    data::Mesh mesh;
    for (int i = 0; i < kNodes; ++i) mesh.nodes.push_back({i + 1, kXyz[i][0], kXyz[i][1], kXyz[i][2]});
    for (int e = 0; e < kElems; ++e) {
        Element el;
        el.id = e + 1;
        el.type = ElementType::SOLID;
        el.material_id = 1;
        el.node_ids.assign(kConn[e], kConn[e] + 8);
        mesh.solids.push_back(el);
        mesh.solid_parts.push_back(1);
    }
    mesh.num_solids = kElems;
    return mesh;
}

data::ControlData buildControl(const Deck& d) {
    data::ControlData c;
    c.NUMNP = kNodes;
    c.NEL8 = kElems;
    c.NV3D = d.nv3d();
    c.IOSOL[0] = 1;
    c.IOSOL[1] = 1;
    c.NEIPH = d.headerNeiph();
    c.ISTRN = d.strain ? 1 : 0;
    return c;
}

data::StateData buildState(const Deck& d, int s) {
    data::StateData st;
    st.time = 0.125 * s;
    st.solid_data.assign(static_cast<size_t>(kElems) * d.nv3d(), 0.0);
    for (int e = 0; e < kElems; ++e) {
        for (int p = 0; p < d.nip; ++p) {
            double* w = st.solid_data.data() + static_cast<size_t>(e) * d.nv3d() + static_cast<size_t>(p) * d.P();
            const Ip v = written(d, e, p, s);
            const bool used = d.same ? (s != 0) : (s != 0 && p < kUsedSlots[e]);
            for (int k = 0; k < 6; ++k) w[k] = v.s[k];
            w[6] = v.ep;
            if (!used) continue;                          // 빈 자리는 이력 변수 · 변형률도 0 으로 실린다
            for (int h = 0; h < d.hist; ++h) w[7 + h] = kHistSentinel;
            if (d.strain) for (int k = 0; k < 6; ++k) w[7 + d.hist + k] = v.s[k] / 65536.0;
        }
    }
    return st;
}

/// 절점 n(0부터)에 닿는 요소들 — 요소마다 한 번
std::vector<int> elemsOfNode(int n) {
    std::vector<int> out;
    for (int e = 0; e < kElems; ++e) {
        if (std::find(kConn[e], kConn[e] + 8, n + 1) != kConn[e] + 8) out.push_back(e);
    }
    return out;
}

/// 생성식 스스로의 점검 — 이 시험이 「가장 큰 자리」 를 「첫 자리」 · 「평균 텐서」 · 「빈 자리까지 센 최대」 와 가를 수 있는 값인지
void caseReference() {
    Case c("기준값 점검 — 가장 큰 자리의 값이 첫 자리 · 평균 텐서 · 빈 자리까지 센 최대와 다르다");
    const Deck multi{"여덟 자리", 8, 0, false};
    const auto differ = [](double a, double b) { return std::abs(a - b) > 1e-6 * std::max(1.0, std::abs(b)); };
    for (int s = 1; s < kStates; ++s) {
        for (int e = 0; e < kElems; ++e) {
            const std::string at = " (요소 " + std::to_string(e) + ")";
            for (int p = 0; p < kUsedSlots[e]; ++p) {
                const Ip v = ipValue(e, p, s);
                bool any = v.ep != 0.0;
                for (int k = 0; k < 6; ++k) any = any || v.s[k] != 0.0;
                expect(any, "쓰인 자리의 앞 7 워드가 전부 0 이면 안 된다 (요소 " + std::to_string(e) + " 자리 " + std::to_string(p) + ")");
            }
            for (const Field& f : kFields) {
                const double best = expectedElem(multi, e, s, f.sel);
                expect(differ(scalarOf(f.sel, ipValue(e, 0, s)), best), std::string(f.name) + " — 첫 자리 값과 달라야 한다" + at);
                expect(differ(scalarOf(f.sel, meanOfUsed(e, s)), best), std::string(f.name) + " — 평균 텐서의 값과 달라야 한다" + at);
            }
            // 빈 자리(0)가 최대로 뽑히면 드러나도록 — 뒤 자리가 빈 요소의 압력은 쓰인 자리에서 전부 음수다
            if (kUsedSlots[e] < 8) {
                expect(expectedElem(multi, e, s, FieldSelector::PressureStress) < -1.0,
                       "압력 — 쓰인 자리의 최대가 음수여야 한다" + at);
            }
        }
    }
}

/// 덱 하나 — 상태 · 값마다 절점 값과 범위를 본다. flat 에는 절점 값을 차례로 모은다(덱끼리 비트 비교용).
void caseDeck(const Deck& d, std::vector<double>* flat) {
    Case c(std::string("덱: ") + d.name + " (NV3D " + std::to_string(d.nv3d()) + ")");
    const data::Mesh mesh = buildMesh();
    const data::ControlData ctrl = buildControl(d);
    NodalAverager avg(mesh, ctrl);
    const PartMatcher all;

    for (int s = 0; s < kStates; ++s) {
        const data::StateData st = buildState(d, s);
        for (const Field& f : kFields) {
            avg.compute(st, f.sel, all);
            double lo = 1e300, hi = -1e300;
            for (int n = 0; n < kNodes; ++n) {
                const std::vector<int> es = elemsOfNode(n);
                double want = 0.0;
                for (int e : es) want += expectedElem(d, e, s, f.sel);
                want /= static_cast<double>(es.size());
                lo = std::min(lo, want);
                hi = std::max(hi, want);
                const double got = avg.nodeValue(n);
                expectNear(got, want, std::string(f.name) + " 상태 " + std::to_string(s) + " 절점 " + std::to_string(n + 1));
                if (flat) flat->push_back(got);
            }
            if (s == 0) continue;                         // 전부 0 인 상태는 범위가 (0, 1) 로 벌어진다
            expectNear(avg.globalMin(), lo, std::string(f.name) + " 상태 " + std::to_string(s) + " 범위 아래");
            expectNear(avg.globalMax(), hi, std::string(f.name) + " 상태 " + std::to_string(s) + " 범위 위");
        }
    }
}

}  // namespace

int main() {
    std::printf("=== 단면 렌더 절점 평균(NodalAverager) 검증 ===\n\n");

    const Deck decks[] = {
        {"한 자리", 1, 0, false},
        {"한 자리 · 이력 변수 2 · 변형률", 1, 2, true},
        {"여덟 자리", 8, 0, false},
        {"여덟 자리 · 이력 변수 2 · 변형률", 8, 2, true},
        {"여덟 자리가 같은 값 · 이력 변수 2 · 변형률", 8, 2, true, true},
        {"머리말 식과 맞지 않는다 — 한 자리로 읽는다", 8, 1, true, false, 6},
    };
    constexpr int kDecks = static_cast<int>(sizeof(decks) / sizeof(decks[0]));

    caseReference();
    std::vector<std::vector<double>> flat(kDecks);
    for (int i = 0; i < kDecks; ++i) caseDeck(decks[i], &flat[i]);
    {
        Case c("여덟 자리가 같은 값인 덱 = 한 자리 덱(비트까지)");
        expect(!flat[4].empty() && sameBits(flat[4], flat[1]), "절점 값이 비트까지 같다");
    }

    std::printf("\n");
    if (g_failed) {
        std::printf("%d건 실패\n", g_failed);
        return 1;
    }
    std::printf("전부 통과\n");
    return 0;
}
