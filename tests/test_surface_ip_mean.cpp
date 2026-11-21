// 적분점 여덟 자리 솔리드 덱에서 겉면 응력 · 변형률 분석이 쓰인 적분점의 평균 텐서를 읽는지 합성 d3plot 으로 검증하는 시험
/**
 * @file test_surface_ip_mean.cpp
 * @brief SurfaceStressAnalyzer · SurfaceStrainAnalyzer 의 솔리드 적분점 처리 검증
 *
 * 겉면 분석은 요소의 텐서를 면 법선에 사영한다(수직 · 전단). 적분점 여덟 자리 덱(NINTSLD 8)에서 요소 블록의
 * 앞 6 워드만 읽으면 첫 자리 하나의 응력이고, 블록의 마지막 6 워드를 변형률로 읽으면 여덟째 자리의 변형률이다
 * (사면체는 그 자리가 비어 0 이 된다). 요소의 값은 값이 실린 자리의 평균 텐서 — 요소 중심값, NINTSLD 1 이
 * 적는 값 — 이어야 한다. 기대값은 분석기 코드와 따로, 생성식에서 바로 낸다.
 *
 * 검증 항목
 *   1. 면 응력 — 텐서 6성분이 쓰인 자리의 평균이고, σ_vm · 수직 · 전단 · σ1 · σ3 은 그 평균 텐서에서 난다
 *   2. 사면체처럼 뒤 자리가 0 으로 실린 요소 — 빈 자리는 평균에 끼지 않는다(넷으로 나눈다, 여덟이 아니다)
 *   3. 면 변형률 — ε_p 는 쓰인 자리의 평균, 변형률 6성분은 자리마다 적분점 블록의 마지막 여섯 워드를 평균한다
 *      (이력 변수 자리를 읽지 않고, 여덟째 자리 하나만 읽지도 않는다)
 *   4. 상태 집계(최대 · 최소 · 평균 · 대표 요소)가 면 값에서 그대로 난다
 *   5. 한 자리 덱, 머리말 식과 맞지 않는 덱은 종전 그대로(요소 블록 전체가 적분점 하나)
 *   6. 여덟 자리에 같은 값을 적은 덱은 한 자리 덱과 결과가 비트까지 같다
 *
 * Run: ./test_surface_ip_mean
 */

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/SurfaceExtractor.hpp"
#include "kood3plot/analysis/SurfaceStrainAnalyzer.hpp"
#include "kood3plot/analysis/SurfaceStressAnalyzer.hpp"
#include "kood3plot/analysis/VectorMath.hpp"
#include "kood3plot/writer/D3plotWriter.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <limits>
#include <string>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

namespace {

namespace fs = std::filesystem;

constexpr int kElems = 4;                               // 육면체 셋(파트 1) + 사면체 하나(파트 2)
constexpr int kNodes = 20;
constexpr int kStates = 3;                              // 상태 0 은 전부 0
constexpr int kPartOf[kElems] = {1, 1, 1, 2};
constexpr int kUsedSlots[kElems] = {8, 8, 8, 4};        // 값이 실리는 적분점 자리 수
constexpr double kHistSentinel = 9.0e5;                 // 이력 변수 자리 — 응력 · 변형률로 읽히면 바로 드러난다
constexpr double kDt = 0.125;
constexpr int kMaxPrint = 8;                            // 사례 하나에서 찍는 실패 줄 수
const char* const kComp[6] = {"xx", "yy", "zz", "xy", "yz", "zx"};

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
    /// 자리마다 값이 달라 평균이 자리 0 과 갈리는 덱
    bool multi() const { return eight() && !same; }
};

struct Ip {
    double s[6] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0};   // σxx σyy σzz σxy σyz σzx
    double ep = 0.0;
    double e[6] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0};   // εxx εyy εzz εxy εyz εzx
};

/// 자리 · 성분 · 요소로 도는 정수(-6..6) — 자리마다 부호까지 바뀌고(굽힘처럼) 평균이 어느 한 자리 값과도 같지 않다
int wobble(int e, int p, int k) { return (7 * p + 3 * k + 5 * e) % 13 - 6; }

/// 요소 e(0부터) · 적분점 자리 p · 상태 s 의 값. 전부 단정밀도로 정확히 실리고(Writer 는 float 로 쓴다),
/// 넷 · 여덟으로 나눈 평균도 배정밀도에서 정확하다.
Ip ipValue(int e, int p, int s) {
    Ip v;
    if (s == 0 || p >= kUsedSlots[e]) return v;

    static const double s_base[kElems][6] = {
        { 96.0,  32.0, -16.0,  24.0,  -8.0,  12.0},
        {-64.0, 128.0,  40.0, -20.0,  28.0,   4.0},
        { 48.0, -80.0, 144.0,  36.0,  16.0, -44.0},
        {160.0, 112.0,  72.0,  20.0, -12.0,  28.0}};
    static const double e_base[kElems][6] = {
        { 12.0,  -4.0,  -3.0,  2.0, -1.0,  1.0},
        { -6.0,  14.0,  -5.0, -2.0,  3.0,  1.0},
        {  5.0,  -9.0,  16.0,  3.0,  2.0, -4.0},
        { 18.0,  -7.0,  -6.0,  2.0, -1.0,  3.0}};
    for (int k = 0; k < 6; ++k) {
        v.s[k] = s * (s_base[e][k] + 16.0 * wobble(e, p, k));
        v.e[k] = s * (e_base[e][k] + wobble(e, p, k + 2)) / 4096.0;
    }
    v.ep = s * (1 + (3 * p + e) % 8) / 1024.0;
    return v;
}

/// 덱 D 의 요소 블록에 실제로 실리는 값 — 한 자리 덱 · 「같은 값」 덱은 자리 0 의 값이다
Ip deckValue(const Deck& D, int e, int p, int s) { return ipValue(e, (D.nip == 1 || D.same) ? 0 : p, s); }

/// 분석기가 요소 하나에서 읽어야 하는 상태
struct ElemState {
    double s[6] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
    double ep = 0.0;
    double e[6] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
};

ElemState wantState(const Deck& D, int e, int s) {
    ElemState w;
    if (!D.multi()) {
        // 요소 블록 전체가 적분점 하나 — 응력 · ε_p 는 블록의 앞 7 워드, 변형률은 블록의 마지막 여섯 워드.
        // 여덟 자리가 같은 값인 덱은 어느 자리를 읽어도 같다.
        const Ip head = deckValue(D, e, 0, s);
        const Ip tail = deckValue(D, e, D.nip - 1, s);
        for (int k = 0; k < 6; ++k) {
            w.s[k] = head.s[k];
            w.e[k] = tail.e[k];
        }
        w.ep = head.ep;
        return w;
    }
    // 쓰인 자리 — 앞 7 워드(응력 6 · ε_p) 중 하나라도 0 이 아닌 자리 — 의 평균. 쓰인 자리가 없으면 전부 0 이다.
    int n = 0;
    for (int p = 0; p < 8; ++p) {
        const Ip v = ipValue(e, p, s);
        bool any = (v.ep != 0.0);
        for (double x : v.s) any = any || (x != 0.0);
        if (!any) continue;
        ++n;
        for (int k = 0; k < 6; ++k) {
            w.s[k] += v.s[k];
            w.e[k] += v.e[k];
        }
        w.ep += v.ep;
    }
    if (n == 0) return w;
    for (int k = 0; k < 6; ++k) {
        w.s[k] /= n;
        w.e[k] /= n;
    }
    w.ep /= n;
    return w;
}

/// 텐서(xx yy zz xy yz zx)의 면 값 — 분석기와 따로 쓴 식. 주값만 StressTensor 의 고유값 풀이를 빌린다.
struct Proj { double vm, n, tau, p1, p3, evm; };

Proj project(const double* t, const Vec3& nrm) {
    Proj r;
    r.vm = std::sqrt(0.5 * ((t[0] - t[1]) * (t[0] - t[1]) + (t[1] - t[2]) * (t[1] - t[2]) +
                            (t[2] - t[0]) * (t[2] - t[0])) +
                     3.0 * (t[3] * t[3] + t[4] * t[4] + t[5] * t[5]));
    const double tx = t[0] * nrm.x + t[3] * nrm.y + t[5] * nrm.z;
    const double ty = t[3] * nrm.x + t[1] * nrm.y + t[4] * nrm.z;
    const double tz = t[5] * nrm.x + t[4] * nrm.y + t[2] * nrm.z;
    r.n = tx * nrm.x + ty * nrm.y + tz * nrm.z;
    const double rx = tx - r.n * nrm.x, ry = ty - r.n * nrm.y, rz = tz - r.n * nrm.z;
    r.tau = std::sqrt(rx * rx + ry * ry + rz * rz);
    const auto p = StressTensor(t[0], t[1], t[2], t[3], t[4], t[5]).principalStresses();
    r.p1 = p[0];
    r.p3 = p[2];
    // 등가 변형률 ε_vm = sqrt(2/3 · e_dev : e_dev)
    const double m = (t[0] + t[1] + t[2]) / 3.0;
    const double dx = t[0] - m, dy = t[1] - m, dz = t[2] - m;
    r.evm = std::sqrt(2.0 / 3.0 * (dx * dx + dy * dy + dz * dz + 2.0 * (t[3] * t[3] + t[4] * t[4] + t[5] * t[5])));
    return r;
}

/// 면 값의 최대 · 최소 · 평균과 대표 요소(먼저 난 쪽이 이긴다)
struct Agg {
    double max = -std::numeric_limits<double>::max();
    double min = std::numeric_limits<double>::max();
    double sum = 0.0;
    int n = 0;
    int32_t max_id = 0, min_id = 0;
    void add(double v, int32_t id) {
        if (v > max) { max = v; max_id = id; }
        if (v < min) { min = v; min_id = id; }
        sum += v;
        ++n;
    }
    double avg() const { return sum / n; }
};

/// 육면체 셋을 x 로 이어 붙인 줄(파트 1)과 따로 떨어진 사면체 하나(파트 2). 요소 ID = 순번 + 1(NARBS 0).
/// 겉면은 육면체 줄 14면 + 사면체 4면 — -Z 로는 육면체 셋의 밑면과 사면체의 밑면, (1,1,1) 로는 사면체의 기운 면 하나.
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

/// 생성식 자체의 성질 — 이것이 깨지면 아래 사례가 첫 자리만 읽는 코드에서도 통과해 버린다
void caseReference() {
    Case c("생성식 — 평균이 어느 한 자리 값과도 다르다");
    const Deck multi{"", 8, 0, true};
    for (int e = 0; e < kElems; ++e) {
        const ElemState w = wantState(multi, e, 1);
        const Ip first = ipValue(e, 0, 1);
        const Ip last = ipValue(e, 7, 1);
        double ds = 0.0, de = 0.0;              // 성분 가운데 가장 크게 갈리는 폭
        for (int k = 0; k < 6; ++k) {
            ds = std::max(ds, std::abs(w.s[k] - first.s[k]));
            de = std::max(de, std::abs(w.e[k] - last.e[k]));
        }
        const std::string id = " [요소 " + std::to_string(e) + "]";
        expect(ds > 8.0, "응력 평균이 첫 자리 값과 다르다" + id);
        expect(std::abs(w.ep - first.ep) > 1e-4, "ε_p 평균이 첫 자리 값과 다르다" + id);
        expect(de > 1e-4, "변형률 평균이 여덟째 자리 값과 다르다" + id);
    }
    // 사면체 — 넷으로 나눈 평균은 여덟으로 나눈 것의 두 배다
    double sum = 0.0;
    for (int p = 0; p < 8; ++p) sum += ipValue(3, p, 1).s[0];
    expectNear(wantState(multi, 3, 1).s[0], sum / 4.0, "사면체 σxx 는 쓰인 네 자리의 평균");
    expect(std::abs(sum / 4.0 - sum / 8.0) > 8.0, "사면체 — 빈 자리를 넣은 평균과 갈린다");
}

void pushAgg(std::vector<double>* sink, std::initializer_list<double> v) { sink->insert(sink->end(), v); }

void checkStress(D3plotReader& reader, const Deck& D, std::vector<double>* sink) {
    SurfaceExtractor ex(reader);
    expect(ex.initialize(), "겉면 추출기 초기화");
    const std::vector<Face> all = ex.extractSolidExteriorSurfaces().faces;
    const std::vector<Face> down = SurfaceExtractor::filterByDirection(all, Vec3(0, 0, -1), 45.0);
    expect(all.size() == 18, "솔리드 겉면 18개(육면체 줄 14 + 사면체 4) — " + std::to_string(all.size()));
    expect(down.size() == 4, "-Z 면 4개(육면체 셋 + 사면체) — " + std::to_string(down.size()));

    SurfaceStressAnalyzer an(reader);
    for (int s = 0; s < kStates; ++s) {
        const data::StateData st = reader.read_state(s);
        const std::string at = " [상태 " + std::to_string(s);

        // 1 · 2. 면 하나 — 텐서는 쓰인 자리의 평균, 나머지 값은 그 텐서에서
        for (const Face& f : all) {
            const FaceStressResult r = an.analyzeFace(f, st);
            const ElemState w = wantState(D, f.element_id, s);
            const Proj p = project(w.s, f.normal);
            const std::string id = at + " · 요소 " + std::to_string(f.element_id) + " · 면 " +
                                   std::to_string(f.face_local_index) + "]";
            expect(r.valid, "면 응력을 읽었다" + id);
            const double got[6] = {r.sxx, r.syy, r.szz, r.sxy, r.syz, r.szx};
            for (int k = 0; k < 6; ++k) expectNear(got[k], w.s[k], std::string("응력 ") + kComp[k] + id);
            expectNear(r.von_mises, p.vm, "σ_vm" + id);
            expectNear(r.normal_stress, p.n, "수직 응력" + id);
            expectNear(r.shear_stress, p.tau, "전단 응력" + id);
            expectNear(r.max_principal, p.p1, "σ1" + id);
            expectNear(r.min_principal, p.p3, "σ3" + id);
        }

        // 4. 상태 집계
        const std::vector<Face>* const subsets[2] = {&all, &down};
        const char* const subset_name[2] = {"전체", "-Z"};
        for (int k = 0; k < 2; ++k) {
            const SurfaceStressStats got = an.analyzeState(*subsets[k], st);
            Agg vm, sn, tau, p1, p3;
            for (const Face& f : *subsets[k]) {
                const ElemState w = wantState(D, f.element_id, s);
                const Proj p = project(w.s, f.normal);
                vm.add(p.vm, f.element_real_id);
                sn.add(p.n, f.element_real_id);
                tau.add(p.tau, f.element_real_id);
                p1.add(p.p1, f.element_real_id);
                p3.add(p.p3, f.element_real_id);
            }
            const std::string id = at + " · " + subset_name[k] + "]";
            expect(got.num_faces == subsets[k]->size() && got.num_faces_skipped == 0, "면이 전부 집계에 든다" + id);
            expectNear(got.von_mises_max, vm.max, "σ_vm 최대" + id);
            expectNear(got.von_mises_min, vm.min, "σ_vm 최소" + id);
            expectNear(got.von_mises_avg, vm.avg(), "σ_vm 평균" + id);
            expectNear(got.normal_stress_max, sn.max, "수직 응력 최대" + id);
            expectNear(got.normal_stress_min, sn.min, "수직 응력 최소" + id);
            expectNear(got.normal_stress_avg, sn.avg(), "수직 응력 평균" + id);
            expectNear(got.shear_stress_max, tau.max, "전단 응력 최대" + id);
            expectNear(got.shear_stress_min, tau.min, "전단 응력 최소" + id);
            expectNear(got.shear_stress_avg, tau.avg(), "전단 응력 평균" + id);
            expectNear(got.max_principal_max, p1.max, "σ1 최대" + id);
            expectNear(got.max_principal_min, p1.min, "σ1 최소" + id);
            expectNear(got.max_principal_avg, p1.avg(), "σ1 평균" + id);
            expectNear(got.min_principal_max, p3.max, "σ3 최대" + id);
            expectNear(got.min_principal_min, p3.min, "σ3 최소" + id);
            expectNear(got.min_principal_avg, p3.avg(), "σ3 평균" + id);
            if (s > 0) {                        // 상태 0 은 전부 0 이라 대표 요소가 뜻이 없다
                expect(got.von_mises_max_element == vm.max_id, "σ_vm 최대 요소" + id);
                expect(got.normal_stress_max_element == sn.max_id, "수직 응력 최대 요소" + id);
                expect(got.shear_stress_max_element == tau.max_id, "전단 응력 최대 요소" + id);
                expect(got.max_principal_max_element == p1.max_id, "σ1 최대 요소" + id);
                expect(got.min_principal_min_element == p3.min_id, "σ3 최소 요소" + id);
            }
            pushAgg(sink, {got.von_mises_max, got.von_mises_min, got.von_mises_avg,
                           got.normal_stress_max, got.normal_stress_min, got.normal_stress_avg,
                           got.shear_stress_max, got.shear_stress_min, got.shear_stress_avg,
                           got.max_principal_max, got.max_principal_min, got.max_principal_avg,
                           got.min_principal_max, got.min_principal_min, got.min_principal_avg});
        }
    }
}

void checkStrain(D3plotReader& reader, const Deck& D, std::vector<double>* sink) {
    struct Spec {
        const char* name;
        Vec3 dir;
        double angle;
        std::vector<int32_t> parts;
        size_t faces;
    };
    const Spec specs[3] = {
        {"+Z", Vec3(0, 0, 1), 45.0, {}, 3},
        {"-Z", Vec3(0, 0, -1), 45.0, {}, 4},
        {"사면체의 기운 면", Vec3(1, 1, 1), 30.0, {2}, 1},
    };

    SurfaceStrainAnalyzer sa(reader);
    for (const Spec& sp : specs) sa.addSurface(sp.name, sp.dir, sp.angle, sp.parts);
    expect(sa.initialize(), "변형률 분석기 초기화");
    for (int s = 0; s < kStates; ++s) sa.processState(reader.read_state(s));
    const std::vector<SurfaceStrainStats> res = sa.getResults();
    expect(res.size() == 3, "겉면 셋의 결과");
    if (res.size() != 3) return;

    SurfaceExtractor ex(reader);
    expect(ex.initialize(), "겉면 추출기 초기화");
    for (int i = 0; i < 3; ++i) {
        const Spec& sp = specs[i];
        const std::vector<Face> faces = SurfaceExtractor::filterByDirection(
            ex.extractSolidExteriorSurfaces(sp.parts).faces, sp.dir.normalized(), sp.angle);
        const std::string surf = std::string(" [") + sp.name;
        expect(faces.size() == sp.faces && static_cast<size_t>(res[i].num_faces) == sp.faces,
               "면 수" + surf + "] — " + std::to_string(faces.size()));
        expect(res[i].has_strain_tensor == D.strain, "변형률 텐서 유무" + surf + "]");
        expect(D.strain ? res[i].note.empty() : !res[i].note.empty(), "텐서가 없으면 사유를 남긴다" + surf + "]");
        expect(res[i].data.size() == static_cast<size_t>(kStates), "상태마다 한 줄" + surf + "]");
        if (res[i].data.size() != static_cast<size_t>(kStates)) continue;

        for (int s = 0; s < kStates; ++s) {
            const SurfaceStrainTimePoint& tp = res[i].data[s];
            Agg ep, en, es, e1, e3, evm;
            for (const Face& f : faces) {
                const ElemState w = wantState(D, f.element_id, s);
                const Proj p = project(w.e, f.normal);
                ep.add(w.ep, f.element_real_id);
                en.add(p.n, f.element_real_id);
                es.add(p.tau, f.element_real_id);
                e1.add(p.p1, f.element_real_id);
                e3.add(p.p3, f.element_real_id);
                evm.add(p.evm, f.element_real_id);
            }
            const std::string id = surf + " · 상태 " + std::to_string(s) + "]";

            // 3. ε_p 는 쓰인 자리의 평균
            expectNear(tp.eff_plastic_strain_max, ep.max, "ε_p 최대" + id);
            expectNear(tp.eff_plastic_strain_min, ep.min, "ε_p 최소" + id);
            expectNear(tp.eff_plastic_strain_avg, ep.avg(), "ε_p 평균" + id);
            if (s > 0) expect(tp.eff_plastic_strain_max_element_id == ep.max_id, "ε_p 최대 요소" + id);

            // 3. 변형률 텐서 — 없는 덱은 전부 0 으로 남는다
            const double z = D.strain ? 1.0 : 0.0;
            expectNear(tp.normal_strain_max, z * en.max, "수직 변형률 최대" + id);
            expectNear(tp.normal_strain_min, z * en.min, "수직 변형률 최소" + id);
            expectNear(tp.normal_strain_avg, z * en.avg(), "수직 변형률 평균" + id);
            expectNear(tp.shear_strain_max, z * es.max, "전단 변형률 최대" + id);
            expectNear(tp.shear_strain_avg, z * es.avg(), "전단 변형률 평균" + id);
            expectNear(tp.max_principal_strain_max, z * e1.max, "ε1 최대" + id);
            expectNear(tp.max_principal_strain_min, z * e1.min, "ε1 최소" + id);
            expectNear(tp.max_principal_strain_avg, z * e1.avg(), "ε1 평균" + id);
            expectNear(tp.min_principal_strain_max, z * e3.max, "ε3 최대" + id);
            expectNear(tp.min_principal_strain_min, z * e3.min, "ε3 최소" + id);
            expectNear(tp.min_principal_strain_avg, z * e3.avg(), "ε3 평균" + id);
            expectNear(tp.vm_strain_max, z * evm.max, "ε_vm 최대" + id);
            expectNear(tp.vm_strain_min, z * evm.min, "ε_vm 최소" + id);
            expectNear(tp.vm_strain_avg, z * evm.avg(), "ε_vm 평균" + id);
            if (D.strain && s > 0) {
                expect(tp.normal_strain_max_element_id == en.max_id, "수직 변형률 최대 요소" + id);
                expect(tp.shear_strain_max_element_id == es.max_id, "전단 변형률 최대 요소" + id);
                expect(tp.max_principal_strain_max_element_id == e1.max_id, "ε1 최대 요소" + id);
                expect(tp.min_principal_strain_min_element_id == e3.min_id, "ε3 최소 요소" + id);
                expect(tp.vm_strain_max_element_id == evm.max_id, "ε_vm 최대 요소" + id);
            }
            pushAgg(sink, {tp.eff_plastic_strain_max, tp.eff_plastic_strain_min, tp.eff_plastic_strain_avg,
                           tp.normal_strain_max, tp.normal_strain_min, tp.normal_strain_avg,
                           tp.shear_strain_max, tp.shear_strain_avg,
                           tp.max_principal_strain_max, tp.max_principal_strain_min, tp.max_principal_strain_avg,
                           tp.min_principal_strain_max, tp.min_principal_strain_min, tp.min_principal_strain_avg,
                           tp.vm_strain_max, tp.vm_strain_min, tp.vm_strain_avg});
        }
    }
}

/// 덱 하나 — 쓰고, 읽어, 겉면 응력 · 변형률을 생성식에서 낸 기대값과 견준다. 분석기가 낸 집계 값은 sink 에 모은다.
void caseDeck(const fs::path& dir, const Deck& D, const std::string& tag, std::vector<double>* sink) {
    Case c(std::string("덱 — ") + D.name + " (NV3D " + std::to_string(D.nv3d()) + ")");
    const std::string path = deckPath(dir, tag);
    if (!writeDeck(path, D)) {
        expect(false, "덱 쓰기");
        return;
    }
    D3plotReader reader(path);
    if (reader.open() != ErrorCode::SUCCESS) {
        expect(false, "덱 열기");
        return;
    }
    expect(reader.get_num_states() == static_cast<size_t>(kStates), "상태 수");
    checkStress(reader, D, sink);
    checkStrain(reader, D, sink);
}

} // namespace

int main() {
    std::printf("=== 겉면 응력 · 변형률의 솔리드 적분점 처리 검증 (합성 d3plot) ===\n\n");

    const fs::path dir = fs::temp_directory_path() / "kood3plot_surface_ip_mean_test";
    fs::remove_all(dir);

    const Deck decks[] = {
        {"한 자리", 1, 0, false},
        {"한 자리 · 이력 변수 2 · 변형률", 1, 2, true},
        {"여덟 자리", 8, 0, false},
        {"여덟 자리 · 변형률만", 8, 0, true},
        {"여덟 자리 · 이력 변수 2 · 변형률", 8, 2, true},
        {"여덟 자리가 같은 값 · 이력 변수 2 · 변형률", 8, 2, true, true},
        {"머리말 식과 맞지 않는다 — 한 자리로 읽는다", 8, 1, true, false, 6},
    };
    constexpr int kDecks = static_cast<int>(sizeof(decks) / sizeof(decks[0]));

    caseReference();
    std::vector<std::vector<double>> flat(kDecks);
    for (int i = 0; i < kDecks; ++i) caseDeck(dir, decks[i], "deck" + std::to_string(i), &flat[i]);
    {
        Case c("여덟 자리가 같은 값인 덱 = 한 자리 덱(비트까지)");
        expect(!flat[5].empty() && sameBits(flat[5], flat[1]), "집계 값이 비트까지 같다");
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
