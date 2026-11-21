// 적분점 여덟 자리 솔리드 덱에서 세그먼트 세트 리포트의 σ_vm · 유효소성변형률이 부모 요소의 적분점 극값인지 합성 d3plot 으로 검증하는 시험
/**
 * @file test_set_segment_ip.cpp
 * @brief set 리포트 segments 지표의 솔리드 적분점 처리 검증
 *
 * *SET_SEGMENT 를 가리키는 set 리포트는 세그먼트가 붙은 솔리드(부모 요소)만 훑어 σ_vm · ε_p 의 세트 최대를 낸다
 * — 파트 이력을 쓰면 「파트 전체 최대」 가 세트 값으로 실리기 때문이다. 요소의 값은 파트 이력과 같은 정의여야 한다.
 * 적분점 여덟 자리 덱(NINTSLD 8)에서는 값이 실린 적분점 가운데 가장 큰 값이다. 요소 블록의 앞 7 워드만 읽으면
 * 첫 자리 하나의 값이라, 파트의 요소를 다 덮는 세트가 그 파트의 이력보다 낮게 나온다.
 * 기대값은 분석기 코드와 따로, 생성식에서 바로 낸다.
 *
 * 검증 항목
 *   1. 상태마다 세트 값 = 부모 요소 · 쓰인 적분점에 걸친 최대(σ_vm · ε_p 따로)
 *   2. 피크(값 · 시각 · 상태 · 요소 · 파트) — 첫 자리로 고르면 다른 요소가 나오는 세트를 넣었다
 *   3. 뒤 자리가 0 으로 실린 요소(사면체) — 쓰인 자리에서만 고른다. 7번째 워드가 음수인 요소는 빈 자리의 0 이
 *      최대가 되면 안 된다
 *   4. 파트의 요소를 다 덮는 세트는 그 파트의 이력 최대와 같다
 *   5. 한 자리 덱, 머리말 식과 맞지 않는 덱은 종전 그대로(요소 블록 전체가 적분점 하나)
 *   6. 여덟 자리에 같은 값을 적은 덱은 한 자리 덱과 결과가 비트까지 같다
 *
 * 지표 계산이 private 이라 UnifiedAnalyzer::analyze 를 끝에서 끝까지 돌린다 — LS-PrePost 렌더러를 켠 빌드에서는
 * 링크되지 않는다(렌더 함수가 실행 파일 쪽에 있다).
 *
 * Run: ./test_set_segment_ip
 */

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/UnifiedAnalyzer.hpp"
#include "kood3plot/writer/D3plotWriter.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

namespace {

namespace fs = std::filesystem;

constexpr int kElems = 4;                               // 육면체 셋(파트 1) + 사면체 하나(파트 2)
constexpr int kNodes = 20;
constexpr int kStates = 4;
constexpr int kAmp[kStates] = {0, 2, 3, 1};             // 상태 0 은 전부 0, 피크는 가운데 상태(2)
constexpr int kPartOf[kElems] = {1, 1, 1, 2};
constexpr int kUsedSlots[kElems] = {8, 8, 8, 4};        // 값이 실리는 적분점 자리 수
constexpr int kRot[kElems] = {7, 0, 0, 0};              // 요소 0 은 가장 큰 값이 첫 자리에 온다
constexpr double kHistSentinel = 9.0e5;                 // 이력 변수 자리 — 응력 · ε_p 로 읽히면 바로 드러난다
constexpr double kDt = 0.125;
constexpr int kMaxPrint = 8;                            // 사례 하나에서 찍는 실패 줄 수

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
    const bool ok = std::isfinite(got) && std::abs(got - want) <= 1e-9 * std::max(1.0, std::abs(want));
    char buf[96];
    std::snprintf(buf, sizeof(buf), " got=%.12g want=%.12g", got, want);
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
};

/// 자리 · 성분 · 요소로 도는 정수(-6..6)
int wobble(int e, int p, int k) { return (7 * p + 3 * k + 5 * e) % 13 - 6; }

/// 요소 e(0부터) · 적분점 자리 p · 상태 s 의 값. 전부 단정밀도로 정확히 실린다(Writer 는 float 로 쓴다).
/// 사면체(요소 3)의 7번째 워드는 음수다 — 탄성 재료처럼 그 워드가 소성변형률이 아닌 덱에서 빈 자리의 0 이
/// 최대로 뽑히지 않는지 본다.
Ip ipValue(int e, int p, int s) {
    Ip v;
    const int a = kAmp[s];
    if (a == 0 || p >= kUsedSlots[e]) return v;

    static const double s_base[kElems][6] = {
        { 96.0,  32.0, -16.0,  24.0,  -8.0,  12.0},
        {-64.0, 128.0,  40.0, -20.0,  28.0,   4.0},
        { 48.0, -80.0, 144.0,  36.0,  16.0, -44.0},
        {160.0, 112.0,  72.0,  20.0, -12.0,  28.0}};
    static const int ep_base[kElems] = {12, 20, 11, 2};
    const int q = (p + kRot[e]) % 8;
    for (int k = 0; k < 6; ++k) v.s[k] = a * (s_base[e][k] + 16.0 * wobble(e, q, k));
    const int n = ep_base[e] + (3 * p + e) % 8;
    v.ep = a * (e == 3 ? -n : n) / 1024.0;
    return v;
}

/// 덱 D 의 요소 블록에 실제로 실리는 값 — 한 자리 덱 · 「같은 값」 덱은 자리 0 의 값이다
Ip deckValue(const Deck& D, int e, int p, int s) { return ipValue(e, (D.nip == 1 || D.same) ? 0 : p, s); }

/// von Mises — 분석기와 따로 쓴 식
double vonMises(const double* t) {
    return std::sqrt(0.5 * ((t[0] - t[1]) * (t[0] - t[1]) + (t[1] - t[2]) * (t[1] - t[2]) +
                            (t[2] - t[0]) * (t[2] - t[0])) +
                     3.0 * (t[3] * t[3] + t[4] * t[4] + t[5] * t[5]));
}

/// 분석기가 요소 하나에서 읽어야 하는 값
struct ElemValue { double vm = 0.0, ep = 0.0; };

/// first_only — 자리 0 만 읽은 값(고치기 전 동작, 한 자리 덱의 값)
ElemValue wantElem(const Deck& D, int e, int s, bool first_only = false) {
    ElemValue w;
    if (first_only || !D.multi()) {
        // 요소 블록 전체가 적분점 하나 — 블록의 앞 7 워드
        const Ip head = deckValue(D, e, 0, s);
        w.vm = vonMises(head.s);
        w.ep = head.ep;
        return w;
    }
    // 쓰인 자리 — 앞 7 워드(응력 6 · ε_p) 중 하나라도 0 이 아닌 자리 — 가운데 최대. 쓰인 자리가 없으면 0 이다.
    bool any_used = false;
    for (int p = 0; p < 8; ++p) {
        const Ip v = ipValue(e, p, s);
        bool used = (v.ep != 0.0);
        for (double x : v.s) used = used || (x != 0.0);
        if (!used) continue;
        const double vm = vonMises(v.s);
        if (!any_used || vm > w.vm) w.vm = vm;
        if (!any_used || v.ep > w.ep) w.ep = v.ep;
        any_used = true;
    }
    return w;
}

/// 세트 하나 — 세그먼트(실 절점 ID, N4 = 0 이면 삼각형)와 그 부모 요소
struct SetDef {
    int sid;
    const char* name;
    std::vector<std::vector<int>> segments;
    std::vector<int> parents;       // 요소 순번(오름차순)
    int part;                       // 부모 요소의 파트
    int covers_part;                // 이 파트의 요소를 다 덮는다(아니면 0)
};

const std::vector<SetDef>& sets() {
    static const std::vector<SetDef> k = {
        // 육면체 0 · 2 의 끝면
        {11, "ends", {{1, 2, 3, 4}, {13, 14, 15, 16}}, {0, 2}, 1, 0},
        // 육면체 0 의 끝면 · 육면체 1 의 옆면
        {12, "pair", {{1, 2, 3, 4}, {5, 8, 12, 9}}, {0, 1}, 1, 0},
        // 사면체의 밑면(삼각형)
        {13, "tet", {{17, 18, 19, 0}}, {3}, 2, 2},
        // 육면체 셋의 옆면 — 파트 1 의 요소 전부
        {14, "part1", {{1, 4, 8, 5}, {5, 8, 12, 9}, {9, 12, 16, 13}}, {0, 1, 2}, 1, 1},
    };
    return k;
}

/// 세트 값 하나 — 부모 요소에 걸친 최대와 그 요소(먼저 난 쪽이 이긴다)
struct Pick { double v = 0.0; int e = -1; };

struct SetWant {
    Pick vm[kStates], ep[kStates];
    int vm_peak = 0, ep_peak = 0;   // 피크 상태(먼저 난 쪽이 이긴다)
};

SetWant wantSet(const Deck& D, const SetDef& S, bool first_only = false) {
    SetWant w;
    for (int s = 0; s < kStates; ++s) {
        for (int e : S.parents) {
            const ElemValue v = wantElem(D, e, s, first_only);
            if (w.vm[s].e < 0 || v.vm > w.vm[s].v) w.vm[s] = {v.vm, e};
            if (w.ep[s].e < 0 || v.ep > w.ep[s].v) w.ep[s] = {v.ep, e};
        }
        if (w.vm[s].v > w.vm[w.vm_peak].v) w.vm_peak = s;
        if (w.ep[s].v > w.ep[w.ep_peak].v) w.ep_peak = s;
    }
    return w;
}

/// 육면체 셋을 x 로 이어 붙인 줄(파트 1)과 따로 떨어진 사면체 하나(파트 2). 요소 ID = 순번 + 1(NARBS 0).
bool writeDeck(const std::string& path, const Deck& D) {
    data::ControlData control;
    control.NDIM = 4;
    control.NUMNP = kNodes;
    control.NEL8 = kElems;
    control.NELT = 0;
    control.NEL4 = 0;
    control.NEL2 = 0;
    control.NV3D = D.nv3d();
    control.NV2D = 0;
    control.NV1D = 0;
    control.NEIPH = D.headerNeiph();
    control.IDTDT = D.strain ? 10000 : 0;       // 10000 자리 = ISTRN
    control.NUMMAT8 = 2;
    control.NMMAT = control.NUMMAT8;
    control.IU = 1;
    control.IV = 0;
    control.IA = 0;
    control.IT = 0;
    control.NGLBV = 6;
    control.NND = 3 * control.NUMNP;
    control.ENN = control.NEL8 * control.NV3D;

    data::Mesh mesh;
    mesh.nodes.resize(kNodes);
    for (int i = 0; i < 16; ++i) {              // x = 0..3 의 단면 넷, 단면마다 절점 넷
        const int k = i % 4;
        mesh.nodes[i].id = i + 1;
        mesh.nodes[i].x = i / 4;
        mesh.nodes[i].y = (k == 1 || k == 2) ? 1.0 : 0.0;
        mesh.nodes[i].z = (k >= 2) ? 1.0 : 0.0;
    }
    static const double tet_xyz[4][3] = {{10.0, 0.0, 0.0}, {11.0, 0.0, 0.0}, {10.0, 1.0, 0.0}, {10.0, 0.0, 1.0}};
    for (int i = 0; i < 4; ++i) {
        mesh.nodes[16 + i].id = 17 + i;
        mesh.nodes[16 + i].x = tet_xyz[i][0];
        mesh.nodes[16 + i].y = tet_xyz[i][1];
        mesh.nodes[16 + i].z = tet_xyz[i][2];
    }
    mesh.solids.resize(kElems);
    mesh.solid_parts.assign(kPartOf, kPartOf + kElems);
    for (int e = 0; e < kElems; ++e) {
        mesh.solids[e].id = e + 1;
        mesh.solids[e].type = ElementType::SOLID;
        mesh.solids[e].material_id = kPartOf[e];
        for (int k = 1; k <= 8; ++k) {
            // 사면체는 (a, b, c, d, d, d, d, d) 로 싣는다
            mesh.solids[e].node_ids.push_back(e < 3 ? 4 * e + k : 16 + std::min(k, 4));
        }
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
                // 변형률 자리 — 세트 지표는 읽지 않는다. 0 이 아닌 값을 실어 자리 계산이 밀리면 드러나게 한다.
                if (D.strain) {
                    for (int k = 0; k < 6; ++k) w[7 + D.hist + k] = (k + 1) / 4096.0;
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

/// 세트 정의를 *SET_SEGMENT 키워드 파일로 쓴다(둘째 세트는 _TITLE 꼴)
bool writeSets(const std::string& path) {
    std::ofstream f(path);
    f << "*KEYWORD\n";
    for (size_t i = 0; i < sets().size(); ++i) {
        const SetDef& S = sets()[i];
        f << "$ " << S.name << "\n";
        if (i == 1) f << "*SET_SEGMENT_TITLE\n" << S.name << "\n";
        else f << "*SET_SEGMENT\n";
        char buf[64];
        std::snprintf(buf, sizeof(buf), "%10d\n", S.sid);
        f << buf;
        for (const auto& seg : S.segments) {
            std::snprintf(buf, sizeof(buf), "%10d%10d%10d%10d\n", seg[0], seg[1], seg[2], seg[3]);
            f << buf;
        }
    }
    f << "*END\n";
    return static_cast<bool>(f);
}

/// 생성식 자체의 성질 — 이것이 깨지면 아래 사례가 첫 자리만 읽는 코드에서도 통과해 버린다
void caseReference() {
    Case c("생성식 — 적분점 극값이 첫 자리 값과 갈린다");
    const Deck multi{"", 8, 0, false};
    for (const SetDef& S : sets()) {
        const SetWant w = wantSet(multi, S);
        const SetWant f = wantSet(multi, S, true);
        const std::string id = std::string(" [세트 ") + S.name + "]";
        for (int s = 1; s < kStates; ++s) {
            expect(w.vm[s].v > f.vm[s].v + 1.0, "σ_vm 세트 최대가 첫 자리로 낸 값보다 크다" + id);
            expect(w.ep[s].v > f.ep[s].v + 1e-4, "ε_p 세트 최대가 첫 자리로 낸 값보다 크다" + id);
        }
    }
    // 고르는 요소까지 달라지는 세트
    {
        const SetWant w = wantSet(multi, sets()[0]), f = wantSet(multi, sets()[0], true);
        expect(w.ep[w.ep_peak].e != f.ep[f.ep_peak].e, "세트 ends — ε_p 피크 요소가 첫 자리로 고른 요소와 다르다");
    }
    {
        const SetWant w = wantSet(multi, sets()[1]), f = wantSet(multi, sets()[1], true);
        expect(w.vm[w.vm_peak].e != f.vm[f.vm_peak].e, "세트 pair — σ_vm 피크 요소가 첫 자리로 고른 요소와 다르다");
    }
    // 사면체 — 7번째 워드가 음수라, 빈 자리까지 넣으면 최대가 0 이 된다
    {
        const SetWant w = wantSet(multi, sets()[2]);
        expect(w.ep[2].v < -1e-4, "세트 tet — 쓰인 자리의 ε_p 최대는 음수다");
        expect(w.ep_peak == 0, "세트 tet — ε_p 피크는 전부 0 인 상태 0 이다");
    }
}

const PartTimeSeriesStats* findPart(const std::vector<PartTimeSeriesStats>& hist, int part) {
    for (const auto& h : hist) {
        if (h.part_id == part) return &h;
    }
    return nullptr;
}

void checkField(const SetFieldResult& f, const Pick* want, int peak, int part, const std::string& id,
                std::vector<double>* sink) {
    expect(f.measured, "값이 났다" + id);
    expect(f.times.size() == static_cast<size_t>(kStates) && f.values.size() == static_cast<size_t>(kStates),
           "상태마다 한 점" + id + " — " + std::to_string(f.values.size()));
    if (f.values.size() != static_cast<size_t>(kStates)) return;
    for (int s = 0; s < kStates; ++s) {
        expectNear(f.times[s], kDt * s, "시각" + id + " [상태 " + std::to_string(s) + "]");
        expectNear(f.values[s], want[s].v, "세트 최대" + id + " [상태 " + std::to_string(s) + "]");
    }
    expectNear(f.peak, want[peak].v, "피크 값" + id);
    expectNear(f.peak_time, kDt * peak, "피크 시각" + id);
    expect(f.peak_state == peak, "피크 상태" + id + " — " + std::to_string(f.peak_state));
    expect(f.peak_element_id == want[peak].e + 1,
           "피크 요소" + id + " — " + std::to_string(f.peak_element_id) + " (기대 " + std::to_string(want[peak].e + 1) + ")");
    expect(f.peak_part_id == part, "피크 파트" + id + " — " + std::to_string(f.peak_part_id));
    sink->insert(sink->end(), f.values.begin(), f.values.end());
    sink->push_back(f.peak);
}

/// 덱 하나 — 쓰고, 세트 리포트를 돌려, 생성식에서 낸 기대값과 견준다. 분석기가 낸 값은 sink 에 모은다.
void caseDeck(const fs::path& dir, const Deck& D, const std::string& tag, const std::string& sets_path,
              std::vector<double>* sink) {
    Case c(std::string("덱 — ") + D.name + " (NV3D " + std::to_string(D.nv3d()) + ")");
    fs::create_directories(dir / tag);
    const std::string path = (dir / tag / "d3plot").string();
    if (!writeDeck(path, D)) {
        expect(false, "덱 쓰기");
        return;
    }

    UnifiedConfig cfg;
    cfg.d3plot_path = path;
    cfg.output_directory = (dir / tag / "out").string();
    cfg.num_threads = 2;
    cfg.surface_defaults = false;
    cfg.verbose = false;
    cfg.sets_file = sets_path;
    for (const SetDef& S : sets()) {
        SetReportSpec spec;
        spec.name = S.name;
        spec.set_type = "segment";
        spec.set_id = S.sid;
        spec.video = false;             // 뷰는 이 시험의 대상이 아니다
        spec.peak_snapshot = false;
        cfg.set_reports.push_back(spec);
    }

    UnifiedAnalyzer analyzer;
    const ExtendedAnalysisResult res = analyzer.analyze(cfg);
    expect(analyzer.getLastError().empty(), "분석이 끝났다 — " + analyzer.getLastError());
    expect(res.set_report_results.size() == sets().size(),
           "세트 리포트 수 — " + std::to_string(res.set_report_results.size()));
    if (res.set_report_results.size() != sets().size()) return;

    for (size_t i = 0; i < sets().size(); ++i) {
        const SetDef& S = sets()[i];
        const SetReportResult& sr = res.set_report_results[i];
        const std::string id = std::string(" [세트 ") + S.name + "]";
        expect(sr.metric_source == "segments", "지표 출처는 segments" + id + " — " + sr.metric_source);
        expect(sr.num_segments == S.segments.size(), "세그먼트 수" + id);
        expect(sr.parent_elem_idx == std::vector<int32_t>(S.parents.begin(), S.parents.end()), "부모 요소" + id);

        const SetFieldResult* f_vm = nullptr;
        const SetFieldResult* f_ep = nullptr;
        for (const auto& f : sr.fields) {
            if (f.field == "von_mises") f_vm = &f;
            if (f.field == "eff_plastic_strain") f_ep = &f;
        }
        expect(f_vm && f_ep, "필드 둘(von_mises · eff_plastic_strain)" + id);
        if (!f_vm || !f_ep) continue;

        // 1 · 2 · 3. 상태마다의 세트 최대와 피크
        const SetWant w = wantSet(D, S);
        checkField(*f_vm, w.vm, w.vm_peak, S.part, " σ_vm" + id, sink);
        checkField(*f_ep, w.ep, w.ep_peak, S.part, " ε_p" + id, sink);

        // 4. 파트의 요소를 다 덮는 세트 = 그 파트의 이력 최대
        if (S.covers_part == 0) continue;
        const PartTimeSeriesStats* h_vm = findPart(res.stress_history, S.covers_part);
        const PartTimeSeriesStats* h_ep = findPart(res.strain_history, S.covers_part);
        expect(h_vm && h_ep, "파트 이력이 있다" + id);
        if (!h_vm || !h_ep) continue;
        expect(h_vm->data.size() == f_vm->values.size() && h_ep->data.size() == f_ep->values.size(),
               "파트 이력과 상태 수가 같다" + id);
        if (h_vm->data.size() != f_vm->values.size() || h_ep->data.size() != f_ep->values.size()) continue;
        for (size_t s = 0; s < f_vm->values.size(); ++s) {
            const std::string at = id + " [상태 " + std::to_string(s) + "]";
            expectNear(f_vm->values[s], h_vm->data[s].max_value, "σ_vm 이 파트 이력 최대와 같다" + at);
            expectNear(f_ep->values[s], h_ep->data[s].max_value, "ε_p 가 파트 이력 최대와 같다" + at);
        }
    }
}

} // namespace

int main() {
    std::printf("=== set 리포트 segments 지표의 솔리드 적분점 처리 검증 (합성 d3plot) ===\n\n");

    const fs::path dir = fs::temp_directory_path() / "kood3plot_set_segment_ip_test";
    fs::remove_all(dir);
    fs::create_directories(dir);
    const std::string sets_path = (dir / "sets.k").string();
    if (!writeSets(sets_path)) {
        std::printf("세트 파일을 쓰지 못했다 — %s\n", sets_path.c_str());
        return 1;
    }

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
    for (int i = 0; i < kDecks; ++i) caseDeck(dir, decks[i], "deck" + std::to_string(i), sets_path, &flat[i]);
    {
        Case c("여덟 자리가 같은 값인 덱 = 한 자리 덱(비트까지)");
        expect(!flat[4].empty() && sameBits(flat[4], flat[1]), "세트 값이 비트까지 같다");
    }

    fs::remove_all(dir);

    std::printf("\n");
    if (g_failed) {
        std::printf("%d건 실패\n", g_failed);
        return 1;
    }
    std::printf("전부 통과\n");
    return 0;
}
