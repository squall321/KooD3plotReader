// 세트 리포트가 지운 부모 요소의 0 · 값이 없는(NaN) 절점의 초기값을 세트 값으로 내지 않는지 합성 d3plot 으로 보는 시험
/**
 * @file test_set_deleted_parents.cpp
 * @brief set 리포트 — 침식(요소 삭제)과 NaN 절점
 *
 * LS-DYNA 는 지운 요소의 응력 · ε_p 워드를 0 으로 적는다(erode7 실측). segments 세트는 부모 요소의 최대를 내는데
 * 지운 부모를 거르지 않으면
 *   - 부모가 전부 지워진 상태의 값이 0 이 되고(값 없음이어야 한다),
 *   - 살아 있는 부모의 ε_p 워드가 음수인 덱(그 워드가 소성 변형률이 아닌 재료)에서는 지운 부모의 0 이 최대가 된다.
 *   그리고 훑기가 초기값 −1 에서 시작해, 산 부모의 ε_p 가 전부 −1 보다 작으면 −1 이 값으로 나갔다(erode7 세트 44 · 47 — 산 부모 −3.42 · −4.50).
 * 절점 세트는 세트 절점의 변위가 전부 NaN 인 상태에 초기값 −1 을 값으로 냈다. 값이 없는 상태는 점을 찍지 않는다
 * (부모 블록이 없는 상태를 건너뛰는 것과 같은 규칙).
 * 절점 세트는 그 상태에서 산 요소에 하나도 속하지 않는 절점(지운 요소에만 속해 떨어져 나간 절점)을 뺀다 —
 * 그 좌표는 발산해도 유한값일 수 있다(erode7 ~1e21). 다 빠지면 그 상태는 점이 없다.
 *
 * 덱 — 육면체 셋(파트 1)을 x 로 이어 붙인 줄, 적분점 하나(NV3D 7), MDLOPT 2(요소 삭제 표).
 *   요소 e · 상태 s: σxx = 128 (e+1)(s+1) (σ_vm 과 같다), ε_p = (s+1)/64 · (s+1)/32 · −1.5 (s+1).
 *   상태 2 에서 요소 0, 상태 3 에서 요소 0 · 1 이 지워진다(워드 0). 절점은 상태마다 x 로 0.5 s 움직이고,
 *   상태 3 에서 절점 1~4(요소 0 에만 속한다)가 NaN 이 된다.
 *
 * 지표 계산이 private 이라 UnifiedAnalyzer::analyze 를 끝에서 끝까지 돌린다 — 렌더 끈 빌드에서만 링크된다.
 *
 * Run: ./test_set_deleted_parents
 */

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/UnifiedAnalyzer.hpp"
#include "kood3plot/writer/D3plotWriter.h"

#include <cmath>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <limits>
#include <string>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

namespace {

namespace fs = std::filesystem;

constexpr int kElems = 3;
constexpr int kNodes = 16;
constexpr int kStates = 4;
constexpr double kDt = 0.125;

int g_failed = 0;
int g_checks = 0;

void expect(bool ok, const std::string& what) {
    ++g_checks;
    if (ok) return;
    ++g_failed;
    std::printf("  FAIL %s\n", what.c_str());
}

void expectNear(double got, double want, const std::string& what) {
    expect(std::abs(got - want) <= 1e-9 * std::max(1.0, std::abs(want)),
           what + " — " + std::to_string(got) + " (기대 " + std::to_string(want) + ")");
}

double vmOf(int e, int s) { return 128.0 * (e + 1) * (s + 1); }
double epOf(int e, int s) {
    const double n = s + 1;
    return e == 0 ? n / 64.0 : e == 1 ? n / 32.0 : -1.5 * n;     // 요소 2 는 −1 보다 작다 — 훑기의 초기값 −1 이 새면 드러난다
}
bool deleted(int e, int s) { return (e == 0 && s >= 2) || (e == 1 && s >= 3); }

bool writeDeck(const std::string& path) {
    data::ControlData control;
    control.NDIM = 4;
    control.NUMNP = kNodes;
    control.NEL8 = kElems;
    control.NV3D = 7;
    control.NEIPH = 0;
    control.MAXINT = -10003;                    // MDLOPT 2 — 상태마다 요소 삭제 표
    control.NUMMAT8 = 1;
    control.NMMAT = 1;
    control.IU = 1;
    control.NGLBV = 6;
    control.NND = 3 * control.NUMNP;
    control.ENN = control.NEL8 * control.NV3D;

    data::Mesh mesh;
    mesh.nodes.resize(kNodes);
    for (int i = 0; i < kNodes; ++i) {          // x = 0..3 의 단면 넷, 단면마다 절점 넷
        const int k = i % 4;
        mesh.nodes[i].id = i + 1;
        mesh.nodes[i].x = i / 4;
        mesh.nodes[i].y = (k == 1 || k == 2) ? 1.0 : 0.0;
        mesh.nodes[i].z = (k >= 2) ? 1.0 : 0.0;
    }
    mesh.solids.resize(kElems);
    mesh.solid_parts.assign(kElems, 1);
    for (int e = 0; e < kElems; ++e) {
        mesh.solids[e].id = e + 1;
        mesh.solids[e].type = ElementType::SOLID;
        mesh.solids[e].material_id = 1;
        for (int k = 1; k <= 8; ++k) mesh.solids[e].node_ids.push_back(4 * e + k);
    }
    mesh.num_solids = kElems;

    std::vector<data::StateData> states;
    for (int s = 0; s < kStates; ++s) {
        data::StateData st;
        st.time = kDt * s;
        st.global_vars.assign(control.NGLBV, 0.0);
        st.node_displacements.resize(kNodes * 3);
        for (int i = 0; i < kNodes; ++i) {      // IU 1 — 현재 좌표
            const bool nan = (s == 3 && i < 4);
            st.node_displacements[i * 3 + 0] = nan ? std::numeric_limits<double>::quiet_NaN() : mesh.nodes[i].x + 0.5 * s;
            st.node_displacements[i * 3 + 1] = nan ? std::numeric_limits<double>::quiet_NaN() : mesh.nodes[i].y;
            st.node_displacements[i * 3 + 2] = nan ? std::numeric_limits<double>::quiet_NaN() : mesh.nodes[i].z;
        }
        st.solid_data.assign(static_cast<size_t>(kElems) * 7, 0.0);
        for (int e = 0; e < kElems; ++e) {
            if (deleted(e, s)) {                // 지운 요소의 워드는 0 이다
                st.deleted_solids.push_back(e + 1);
                continue;
            }
            st.solid_data[static_cast<size_t>(e) * 7 + 0] = vmOf(e, s);
            st.solid_data[static_cast<size_t>(e) * 7 + 6] = epOf(e, s);
        }
        states.push_back(std::move(st));
    }

    writer::D3plotWriter w(path);
    w.setControlData(control);
    w.setMesh(mesh);
    w.setStates(states);
    return w.write() == ErrorCode::SUCCESS;
}

bool writeSets(const std::string& path) {
    std::ofstream f(path);
    f << "*KEYWORD\n"
         "*SET_SEGMENT\n        21\n"          // 요소 0 의 끝면 · 요소 1 의 옆면 — 상태 3 에서 부모가 다 지워진다
         "         1         2         3         4\n"
         "         5         8        12         9\n"
         "*SET_SEGMENT\n        22\n"          // 요소 0 의 끝면 · 요소 2 의 끝면 — 요소 2 의 ε_p 는 음수다
         "         1         2         3         4\n"
         "        13        14        15        16\n"
         "*SET_NODE_LIST\n        31\n"        // 요소 0 에만 속한 절점 — 상태 2 부터 떨어져 나간 절점, 상태 3 에서 다 NaN
         "         1         2         3         4\n"
         "*SET_NODE_LIST\n        33\n"        // 요소 0 · 1 이 함께 쓰는 절점 — 요소 1 이 살아 있는 상태 2 까지 산 절점
         "         5         6         7         8\n"
         "*END\n";
    return static_cast<bool>(f);
}

const SetFieldResult* field(const SetReportResult& sr, const char* name) {
    for (const auto& f : sr.fields) {
        if (f.field == name) return &f;
    }
    return nullptr;
}

/// 상태 states 에서 값 want 가 차례로 찍혔는지
void checkSeries(const SetFieldResult* f, const std::vector<int>& states, const std::vector<double>& want,
                 const std::string& id) {
    expect(f != nullptr, "필드가 있다" + id);
    if (!f) return;
    expect(f->times.size() == states.size() && f->values.size() == states.size(),
           "값이 있는 상태만 점이 찍힌다" + id + " — " + std::to_string(f->values.size()) + "점 (기대 " +
               std::to_string(states.size()) + ")");
    for (size_t i = 0; i < states.size() && i < f->values.size() && i < f->times.size(); ++i) {
        const std::string at = id + " [상태 " + std::to_string(states[i]) + "]";
        expectNear(f->times[i], kDt * states[i], "시각" + at);
        expectNear(f->values[i], want[i], "값" + at);
    }
}

}  // namespace

int main() {
    std::printf("세트 리포트 — 지운 부모 요소 · NaN 절점\n");
    const fs::path dir = fs::temp_directory_path() / "kood3plot_test_set_deleted_parents";
    fs::remove_all(dir);
    fs::create_directories(dir);
    const std::string d3 = (dir / "d3plot").string();
    const std::string sets = (dir / "sets.k").string();
    expect(writeDeck(d3), "덱 쓰기");
    expect(writeSets(sets), "세트 파일 쓰기");

    // 덱 왕복 — 삭제 표가 읽힌다
    {
        D3plotReader reader(d3);
        expect(reader.open() == ErrorCode::SUCCESS, "덱 열기");
        const auto all = reader.read_all_states();
        expect(all.size() == static_cast<size_t>(kStates), "상태 수");
        if (all.size() == static_cast<size_t>(kStates)) {
            expect(all[1].deleted_solids.empty(), "상태 1 은 지운 요소가 없다");
            expect(all[2].deleted_solids == std::vector<int32_t>{1}, "상태 2 는 요소 1(순번)");
            expect(all[3].deleted_solids == std::vector<int32_t>({1, 2}), "상태 3 은 요소 1 · 2(순번)");
        }
    }

    UnifiedConfig cfg;
    cfg.d3plot_path = d3;
    cfg.output_directory = (dir / "out").string();
    cfg.num_threads = 2;
    cfg.surface_defaults = false;
    cfg.verbose = false;
    cfg.sets_file = sets;
    const struct { const char* name; const char* type; int sid; } specs[] = {
        {"gone", "segment", 21}, {"mixed", "segment", 22}, {"nan_nodes", "node", 31}, {"shared_nodes", "node", 33}};
    for (const auto& s : specs) {
        SetReportSpec spec;
        spec.name = s.name;
        spec.set_type = s.type;
        spec.set_id = s.sid;
        spec.video = false;
        spec.peak_snapshot = false;
        cfg.set_reports.push_back(spec);
    }

    UnifiedAnalyzer analyzer;
    const ExtendedAnalysisResult res = analyzer.analyze(cfg);
    expect(analyzer.getLastError().empty(), "분석이 끝났다 — " + analyzer.getLastError());
    expect(res.set_report_results.size() == 4, "세트 리포트 수 — " + std::to_string(res.set_report_results.size()));
    if (res.set_report_results.size() == 4) {
        const SetReportResult& gone = res.set_report_results[0];
        const SetReportResult& mixed = res.set_report_results[1];
        const SetReportResult& nodes = res.set_report_results[2];

        // 부모 둘이 상태 3 에서 다 지워진다 — 상태 2 는 산 요소 1 의 값, 상태 3 은 점이 없다
        checkSeries(field(gone, "von_mises"), {0, 1, 2}, {vmOf(1, 0), vmOf(1, 1), vmOf(1, 2)}, " [gone σ_vm]");
        checkSeries(field(gone, "eff_plastic_strain"), {0, 1, 2}, {epOf(1, 0), epOf(1, 1), epOf(1, 2)}, " [gone ε_p]");

        // 요소 0 이 지워진 뒤 ε_p 는 산 요소 2 의 음수 — 지운 요소의 0 이 아니다
        checkSeries(field(mixed, "von_mises"), {0, 1, 2, 3}, {vmOf(2, 0), vmOf(2, 1), vmOf(2, 2), vmOf(2, 3)},
                    " [mixed σ_vm]");
        checkSeries(field(mixed, "eff_plastic_strain"), {0, 1, 2, 3}, {epOf(0, 0), epOf(0, 1), epOf(2, 2), epOf(2, 3)},
                    " [mixed ε_p]");
        const SetFieldResult* mep = field(mixed, "eff_plastic_strain");
        if (mep) {
            expectNear(mep->peak, epOf(0, 1), "피크 [mixed ε_p]");
            expect(mep->peak_element_id == 1, "피크 요소 [mixed ε_p] — " + std::to_string(mep->peak_element_id));
        }

        // 요소 0 에만 속한 절점은 상태 2 부터 떨어져 나간 절점이라 뺀다 — 상태 2 · 3 은 점이 없다(초기값 −1 도 0 도 아니다)
        checkSeries(field(nodes, "disp_mag"), {0, 1}, {0.0, 0.5}, " [nan_nodes 변위]");
        // 요소 0 · 1 이 함께 쓰는 절점은 요소 1 이 살아 있는 상태 2 까지 산 절점, 상태 3 은 둘 다 지워져 점이 없다
        checkSeries(field(res.set_report_results[3], "disp_mag"), {0, 1, 2}, {0.0, 0.5, 1.0}, " [shared_nodes 변위]");
    }

    fs::remove_all(dir);
    if (g_failed == 0) std::printf("  [OK]   검사 %d개\n", g_checks);
    else std::printf("  [FAIL] %d건(검사 %d개)\n", g_failed, g_checks);
    return g_failed == 0 ? 0 : 1;
}
