// 단면 렌더의 절점 평균 · 단면 자르기가 침식으로 지워진 요소를 요소 순번(1부터)으로 가려 빼는지 메모리의 메시 · 상태로 검증하는 시험
/**
 * @file test_section_deleted.cpp
 * @brief 지워진 요소 목록 = 그 종류 배열 안의 1부터 세는 순번 (덱 없이 Mesh · ControlData · StateData 를 직접 만든다)
 *
 * StateData::deleted_solids · deleted_thick_shells · deleted_shells 는 요소 ID 가 아니라 순번이다(StateDataParser — MDLOPT 2 의
 * 재질 번호 표에서 0 인 자리). 덱이 요소 번호를 따로 매기면(NARBS) Element::id 는 실제 요소 ID 라 순번과 다르다 —
 * ID 로 견주면 지워진 요소가 그려지고 산 요소가 빠진다.
 *
 * 검증 항목
 *   1. 절점 평균(응력 경로 · 총변형률 경로) — 지워진 요소는 절점 값에 들어가지 않는다(솔리드 · 두꺼운 셸 · 셸)
 *   2. 단면 자르기 — 지워진 요소는 잘림면을 만들지 않고, 산 요소는 빠지지 않는다
 *   3. 요소 번호가 순번과 같은 덱 · 번호가 엇갈려 다른 요소의 순번과 겹치는 덱 모두
 *
 * Run: ./test_section_deleted
 */

#include "kood3plot/section_render/NodalAverager.hpp"
#include "kood3plot/section_render/SectionClipper.hpp"
#include "kood3plot/section_render/SectionPlane.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <string>
#include <utility>
#include <vector>

using namespace kood3plot;
using kood3plot::section_render::ClipPolygon;
using kood3plot::section_render::FieldSelector;
using kood3plot::section_render::NodalAverager;
using kood3plot::section_render::PartMatcher;
using kood3plot::section_render::SectionClipper;
using kood3plot::section_render::SectionPlane;
using kood3plot::section_render::Vec3;

namespace {

// 솔리드 셋(x [0,1] [1,2] [2,3], 파트 1), 두꺼운 셸 둘(앞 두 솔리드의 윗면 위 z [1, 1.2], 파트 2), 셸 둘(z 2 평면, 파트 3).
// 단면은 y = 0.5 — 모든 요소를 가로지른다. 지우는 요소는 솔리드 3번째 · 두꺼운 셸 1번째 · 셸 2번째(순번)이고,
// 지운 요소마다 그 요소에만 닿는 절점이 있다(x = 3 의 솔리드 절점, x = 0 의 두꺼운 셸 윗 절점, x = 2 의 셸 절점).
enum Kind { kSolid = 0, kTshell = 1, kShell = 2 };
constexpr int kKinds = 3;
constexpr const char* kKindName[kKinds] = {"솔리드", "두꺼운 셸", "셸"};
constexpr int kCount[kKinds] = {3, 2, 2};
constexpr int kPart[kKinds] = {1, 2, 3};
constexpr int kDeletedOrd[kKinds] = {3, 1, 2};                 // 지우는 요소의 순번(1부터)
constexpr int kCrossedId[kKinds][3] = {{2, 3, 1}, {2, 1, 0}, {2, 1, 0}};   // 엇갈린 요소 번호 — 순번 k 의 요소 ID
constexpr double kElemValue[kKinds][3] = {{100.0, 200.0, 300.0}, {1000.0, 2000.0, 0.0}, {10000.0, 20000.0, 0.0}};
constexpr int kNV = 7;                                         // 요소 블록 워드 수(응력 6 + ε_p, 층 · 자리 하나)
constexpr int kMaxPrint = 8;

// 절점 번호(1부터) — 솔리드 격자 (i, j, l) → 1 + i + 4j + 8l (16개), 두꺼운 셸 윗면 (i, j) z 1.2 → 17 + i + 3j (6개),
// 셸 (i, j) z 2 → 23 + i + 3j (6개)
constexpr int kNodes = 28;
int nSolid(int i, int j, int l) { return 1 + i + 4 * j + 8 * l; }
int nTop(int i, int j) { return 17 + i + 3 * j; }
int nShell(int i, int j) { return 23 + i + 3 * j; }

std::vector<int32_t> connOf(int k, int e) {
    switch (k) {
        case kSolid:
            return {nSolid(e, 0, 0), nSolid(e + 1, 0, 0), nSolid(e + 1, 1, 0), nSolid(e, 1, 0),
                    nSolid(e, 0, 1), nSolid(e + 1, 0, 1), nSolid(e + 1, 1, 1), nSolid(e, 1, 1)};
        case kTshell:
            return {nSolid(e, 0, 1), nSolid(e + 1, 0, 1), nSolid(e + 1, 1, 1), nSolid(e, 1, 1),
                    nTop(e, 0), nTop(e + 1, 0), nTop(e + 1, 1), nTop(e, 1)};
        default:
            return {nShell(e, 0), nShell(e + 1, 0), nShell(e + 1, 1), nShell(e, 1)};
    }
}

Vec3 xyzOf(int n) {
    if (n <= 16) {
        const int m = n - 1;
        return Vec3(m % 4, (m / 4) % 2, m / 8);
    }
    if (n <= 22) {
        const int m = n - 17;
        return Vec3(m % 3, m / 3, 1.2);
    }
    const int m = n - 23;
    return Vec3(m % 3, m / 3, 2.0);
}

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

data::Mesh buildMesh(bool crossed) {
    data::Mesh mesh;
    for (int n = 1; n <= kNodes; ++n) {
        const Vec3 p = xyzOf(n);
        mesh.nodes.push_back({n, p.x, p.y, p.z});
    }
    for (int k = 0; k < kKinds; ++k) {
        for (int e = 0; e < kCount[k]; ++e) {
            Element el;
            el.id = crossed ? kCrossedId[k][e] : e + 1;
            el.type = (k == kSolid) ? ElementType::SOLID : (k == kTshell) ? ElementType::THICK_SHELL : ElementType::SHELL;
            el.material_id = 1;
            el.node_ids = connOf(k, e);
            if (k == kSolid) {
                mesh.solids.push_back(el);
                mesh.solid_parts.push_back(kPart[k]);
            } else if (k == kTshell) {
                mesh.thick_shells.push_back(el);
                mesh.thick_shell_parts.push_back(kPart[k]);
            } else {
                mesh.shells.push_back(el);
                mesh.shell_parts.push_back(kPart[k]);
            }
        }
    }
    mesh.num_solids = mesh.solids.size();
    mesh.num_thick_shells = mesh.thick_shells.size();
    mesh.num_shells = mesh.shells.size();
    mesh.num_beams = 0;
    return mesh;
}

data::ControlData buildControl() {
    data::ControlData c;
    c.NDIM = 4;
    c.NUMNP = kNodes;
    c.IU = 1;
    c.NEL8 = kCount[kSolid];
    c.NV3D = kNV;
    c.IOSOL[0] = c.IOSOL[1] = 1;
    c.NELT = kCount[kTshell];
    c.NV3DT = kNV;
    c.NEL4 = kCount[kShell];
    c.NV2D = kNV;
    c.MAXINT = 1;
    c.IOSHL[0] = c.IOSHL[1] = 1;
    return c;
}

/// 상태 하나 — 요소마다 σxx 하나만 실어 von Mises 가 그 값이 되게 하고, 절점은 x 방향으로 1 % 늘인다(총변형률이 0 이 아니게)
data::StateData buildState(bool with_deleted) {
    data::StateData st;
    st.time = 1.0;
    for (int n = 1; n <= kNodes; ++n) {
        const Vec3 p = xyzOf(n);   // IU 1 이면 node_displacements 가 현재 좌표다
        st.node_displacements.push_back(1.01 * p.x);
        st.node_displacements.push_back(p.y);
        st.node_displacements.push_back(p.z);
    }
    std::vector<double>* data[kKinds] = {&st.solid_data, &st.thick_shell_data, &st.shell_data};
    for (int k = 0; k < kKinds; ++k) {
        data[k]->assign(static_cast<size_t>(kCount[k]) * kNV, 0.0);
        for (int e = 0; e < kCount[k]; ++e) (*data[k])[static_cast<size_t>(e) * kNV] = kElemValue[k][e];
    }
    if (with_deleted) {
        st.deleted_solids = {kDeletedOrd[kSolid]};
        st.deleted_thick_shells = {kDeletedOrd[kTshell]};
        st.deleted_shells = {kDeletedOrd[kShell]};
    }
    return st;
}

bool alive(int k, int e, bool with_deleted) { return !(with_deleted && e + 1 == kDeletedOrd[k]); }

/// 절점 n(1부터)에 닿는 산 요소들 — (종류, 순번 0부터)
std::vector<std::pair<int, int>> aliveAt(int n, bool with_deleted) {
    std::vector<std::pair<int, int>> out;
    for (int k = 0; k < kKinds; ++k) {
        for (int e = 0; e < kCount[k]; ++e) {
            const std::vector<int32_t> c = connOf(k, e);
            if (alive(k, e, with_deleted) && std::find(c.begin(), c.end(), n) != c.end()) out.emplace_back(k, e);
        }
    }
    return out;
}

std::string deckName(bool crossed, bool with_deleted) {
    return std::string(crossed ? "요소 번호가 순번과 엇갈린 덱" : "요소 번호 = 순번") + (with_deleted ? " · 지운 요소 있음" : " · 지운 요소 없음");
}

/// 절점 평균 — 응력 경로는 값까지, 총변형률 경로는 「산 요소가 닿는 절점만 값이 있다」 를 본다
void caseAverager(bool crossed, bool with_deleted) {
    Case c("절점 평균: " + deckName(crossed, with_deleted));
    const data::Mesh mesh = buildMesh(crossed);
    const data::ControlData ctrl = buildControl();
    const data::StateData st = buildState(with_deleted);
    NodalAverager avg(mesh, ctrl);
    const PartMatcher all;

    avg.compute(st, FieldSelector::VonMises, all);
    double lo = 1e300, hi = -1e300;
    for (int n = 1; n <= kNodes; ++n) {
        const auto es = aliveAt(n, with_deleted);
        double want = 0.0;                                    // 산 요소가 하나도 닿지 않으면 값이 없다(0)
        for (const auto& ke : es) want += kElemValue[ke.first][ke.second];
        if (!es.empty()) {
            want /= static_cast<double>(es.size());
            lo = std::min(lo, want);
            hi = std::max(hi, want);
        }
        expectNear(avg.nodeValue(n - 1), want, "σ_vm 절점 " + std::to_string(n));
    }
    expectNear(avg.globalMin(), lo, "σ_vm 범위 아래");
    expectNear(avg.globalMax(), hi, "σ_vm 범위 위");

    avg.compute(st, FieldSelector::TotalStrain, all);
    for (int n = 1; n <= kNodes; ++n) {
        const double v = avg.nodeValue(n - 1);
        const bool touched = !aliveAt(n, with_deleted).empty();
        expect(touched ? (std::isfinite(v) && v > 1e-6) : v == 0.0,
               "총변형률 절점 " + std::to_string(n) + (touched ? " — 값이 있어야 한다" : " — 지운 요소에만 닿으니 값이 없어야 한다") +
               " got=" + std::to_string(v));
    }
}

/// 단면 자르기 — 잘림면 하나하나가 어느 요소에서 났는지 (파트, x 중심)로 가려 산 요소 목록과 견준다
void caseClipper(bool crossed, bool with_deleted) {
    Case c("단면 자르기: " + deckName(crossed, with_deleted));
    const data::Mesh mesh = buildMesh(crossed);
    const data::ControlData ctrl = buildControl();
    const data::StateData st = buildState(with_deleted);
    NodalAverager avg(mesh, ctrl);
    const PartMatcher all;
    avg.compute(st, FieldSelector::VonMises, all);

    const SectionPlane plane = SectionPlane::fromAxis('y', Vec3(0.0, 0.5, 0.0));   // 자르개는 면을 참조로 쥔다 — 이름 있는 변수로
    SectionClipper clipper(mesh, ctrl, plane);
    std::vector<ClipPolygon> tgt, bg;
    std::vector<float> bg_alphas;
    clipper.clip(st, avg, all, all, tgt, bg, bg_alphas);
    expect(bg.empty(), "타겟이 전부라 배경 잘림면은 없어야 한다");

    // 잘림면 → (파트, x 중심을 늘이기 전 좌표의 칸 번호 0부터)
    std::vector<std::pair<int, int>> got, want;
    for (const ClipPolygon& poly : tgt) {
        double sx = 0.0;
        for (const auto& v : poly) sx += v.position.x;
        const int pid = poly.empty() ? -1 : poly.front().part_id;
        got.emplace_back(pid, static_cast<int>(std::floor(sx / poly.size() / 1.01)));
        const bool shell = (pid == kPart[kShell]);
        expect(shell ? poly.size() == 2 : poly.size() >= 3,
               "파트 " + std::to_string(pid) + " 잘림면의 꼭짓점 수 " + std::to_string(poly.size()));
    }
    for (int k = 0; k < kKinds; ++k) {
        for (int e = 0; e < kCount[k]; ++e) {
            if (alive(k, e, with_deleted)) want.emplace_back(kPart[k], e);
        }
    }
    std::sort(got.begin(), got.end());
    std::sort(want.begin(), want.end());
    std::string g, w;
    for (const auto& p : got) g += " " + std::string(kKindName[p.first - 1]) + "#" + std::to_string(p.second + 1);
    for (const auto& p : want) w += " " + std::string(kKindName[p.first - 1]) + "#" + std::to_string(p.second + 1);
    expect(got == want, "잘림면을 낸 요소(순번) — got:" + g + " · want:" + w);
}

}  // namespace

int main() {
    std::printf("=== 단면 렌더의 지운 요소(순번) 검증 ===\n\n");
    for (bool crossed : {false, true}) {
        for (bool with_deleted : {false, true}) {
            caseAverager(crossed, with_deleted);
            caseClipper(crossed, with_deleted);
        }
    }
    std::printf("\n");
    if (g_failed) {
        std::printf("%d건 실패\n", g_failed);
        return 1;
    }
    std::printf("전부 통과\n");
    return 0;
}
