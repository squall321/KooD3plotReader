// 빔 파트 응력 이력(적분점 극값)을 합성 d3plot 으로 검증하는 시험 — 워드 배치 · 침식 · 값 없는 파트
/**
 * @file test_beam_part_history.cpp
 * @brief SinglePassAnalyzer 의 빔 파트 이력 검증
 *
 * 적분점 응력을 기록한 실제 빔 덱은 하나뿐이고(R13.1.1 · 확장 제어 워드 없음) 워드 순서와 값은 그것으로
 * 맞췄다. 여기서는 실데이터로 볼 수 없는 것 — 확장 제어 워드가 있는 배치(BEMENG · NEIPB), 침식,
 * 값이 없는 파트, 번호가 겹치는 파트 — 을 D3plotWriter 로 값을 미리 아는 덱을 만들어 본다.
 * 기대값은 분석기의 닫힌 꼴과 따로 StressTensor 의 일반 고유값 풀이로 낸다.
 *
 * 검증 항목
 *   1. 받아들이는 배치 — 에너지 워드가 합력 바로 뒤 · 적분점 블록 뒤 · 블록 끝, 이력 변수 유무
 *   2. 못 읽는 배치 — 이력을 만들지 않고 사유를 남긴다(틀린 워드를 응력으로 읽지 않는다)
 *   3. 적분점 값이 전 상태에서 0 인 파트는 빠진다
 *   4. 침식된 빔 · 유한하지 않은 워드 · 잘린 상태의 빔은 통계에서 빠지고, 살아 있는 빔이 없는 상태는 NaN 이다
 *   5. 솔리드 파트와 번호가 같은 빔 파트는 빠지고(솔리드 줄은 그대로), 남은 빔 줄은 파트 번호순으로 선다
 *   6. 응력만 · 변형률만 켠 실행, 나머지 진입점(analyzeParallel · analyzeLegacy)
 *   7. 분석 작업의 parts(AnalysisConfig::part_ids) — 요청한 파트의 줄만 낸다(솔리드 · 빔 · 피크 텐서 · analyzed_parts),
 *      값은 거르지 않은 실행과 같고, 모델에 없는 번호는 사유 한 줄. 비었으면 전부(지금과 같다)
 *
 * Run: ./test_beam_part_history
 */

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/SinglePassAnalyzer.hpp"
#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
#include "kood3plot/analysis/VectorMath.hpp"
#include "kood3plot/writer/D3plotWriter.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <functional>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

namespace {

namespace fs = std::filesystem;

constexpr int kBeams = 6;        // 파트 1 = 빔 1·2, 파트 2 = 빔 3·4, 파트 3 = 빔 5·6(적분점 값이 늘 0)
constexpr int kStates = 3;       // 상태 0 은 전부 0
const char* const kQuantity[4] = {"von_mises", "max_principal_stress", "min_principal_stress",
                                  "eff_plastic_strain"};

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

/// 빔 요소 블록의 워드 배치. nv1d 가 0 이면 규격 공식대로 센다.
struct Layout {
    const char* name;
    int nip;        // BEAMIP
    int neipb;      // 적분점 이력 변수 수(확장 워드 67)
    int extra;      // 확장 제어 워드 수
    int bemeng;     // 에너지 워드 자리(확장 워드 80, 1부터 셈). 0 이면 없다
    int nv1d = 0;
    int nv() const { return nv1d ? nv1d : 6 + 5 * nip + neipb * (3 + nip) + (bemeng > 0 ? 1 : 0); }
    int ipOff() const { return bemeng == 7 ? 7 : 6; }
};

struct Ip { double sig, trs, ttr, ep, eax; };

/// 빔 b(0부터) · 적분점 k · 상태 s 의 적분점 워드. 전부 단정밀도로 정확히 실리는 값이다(Writer 는 float 로 쓴다).
/// 인장 · 압축이 적분점마다 번갈아 나와 σ_vm · σ1 · σ3 의 극값이 서로 다른 적분점에서 난다.
Ip ipValue(int b, int k, int s) {
    if (s == 0 || b >= 4) return {0.0, 0.0, 0.0, 0.0, 0.0};
    static const double base[4] = {300.0, 100.0, 200.0, 400.0};
    const double amp = base[b] + 10.0 * ((3 * k + b) % 4);
    return {(k % 2 ? -amp : amp) * s, static_cast<double>((3 * k + b) * s), -static_cast<double>((2 * k + 1) * s),
            static_cast<double>((b + 1) * (k + 1) * s) / 1024.0, 0.5};
}

/// 요소 값 = 적분점 극값(σ_vm · σ1 · ε_p 는 최대, σ3 는 최소). 국부계 텐서 {σ, 0, 0, τ_rs, 0, τ_tr} 의 일반 풀이.
std::array<double, 4> elementWant(int b, int nip, int s) {
    const double big = std::numeric_limits<double>::max();
    std::array<double, 4> v = {-big, -big, big, -big};
    for (int k = 0; k < nip; ++k) {
        const Ip ip = ipValue(b, k, s);
        const StressTensor t(ip.sig, 0.0, 0.0, ip.trs, 0.0, ip.ttr);
        const auto p = t.principalStresses();
        v[0] = std::max(v[0], t.vonMises());
        v[1] = std::max(v[1], p[0]);
        v[2] = std::min(v[2], p[2]);
        v[3] = std::max(v[3], ip.ep);
    }
    return v;
}

/// 절점 8개(정육면체 꼭짓점)에 빔 6개를 잇는다. with_solid 면 파트 2 인 육면체 하나를 더한다(σ_vm = 100).
bool writeDeck(const std::string& path, const Layout& L, bool with_solid = false) {
    const int nv = L.nv();

    data::ControlData control;
    control.NDIM = 4;
    control.NUMNP = 8;
    control.NEL8 = with_solid ? 1 : 0;
    control.NELT = 0;
    control.NEL4 = 0;
    control.NEL2 = kBeams;
    control.NV3D = with_solid ? 7 : 0;
    control.NV2D = 0;
    control.NV1D = nv;
    control.NUMMAT8 = with_solid ? 1 : 0;
    control.NUMMAT2 = 3;
    control.NMMAT = control.NUMMAT8 + control.NUMMAT2;
    control.IU = 1;
    control.IV = 0;
    control.IA = 0;
    control.IT = 0;
    control.NGLBV = 6;
    control.EXTRA = L.extra;
    control.NEIPB = L.neipb;
    control.BEMENG = L.bemeng;
    control.NND = 3 * control.NUMNP;
    control.ENN = control.NEL8 * control.NV3D + control.NEL2 * control.NV1D;

    data::Mesh mesh;
    mesh.nodes.resize(8);
    for (int i = 0; i < 8; ++i) {
        const int k = i % 4;
        mesh.nodes[i].id = i + 1;
        mesh.nodes[i].x = (k == 1 || k == 2) ? 1.0 : 0.0;
        mesh.nodes[i].y = (k >= 2) ? 1.0 : 0.0;
        mesh.nodes[i].z = i / 4;
    }
    if (with_solid) {
        mesh.solids.resize(1);
        mesh.solid_parts = {2};
        mesh.solids[0].id = 1;
        mesh.solids[0].type = ElementType::SOLID;
        mesh.solids[0].material_id = 2;
        for (int k = 1; k <= 8; ++k) mesh.solids[0].node_ids.push_back(k);
    }
    mesh.beams.resize(kBeams);
    mesh.beam_parts = {1, 1, 2, 2, 3, 3};
    for (int b = 0; b < kBeams; ++b) {
        mesh.beams[b].id = b + 1;
        mesh.beams[b].node_ids = {b + 1, b + 2};
    }
    mesh.num_solids = with_solid ? 1 : 0;
    mesh.num_thick_shells = 0;
    mesh.num_shells = 0;
    mesh.num_beams = kBeams;

    std::vector<data::StateData> states;
    for (int s = 0; s < kStates; ++s) {
        data::StateData st;
        st.time = 0.125 * s;
        st.global_vars.assign(control.NGLBV, 0.0);
        st.node_displacements.resize(control.NUMNP * 3);
        for (int i = 0; i < control.NUMNP; ++i) {
            st.node_displacements[i * 3 + 0] = mesh.nodes[i].x;
            st.node_displacements[i * 3 + 1] = mesh.nodes[i].y;
            st.node_displacements[i * 3 + 2] = mesh.nodes[i].z;
        }
        if (with_solid) {
            st.solid_data.assign(control.NV3D, 0.0);
            st.solid_data[0] = 100.0;   // sxx → σ_vm = 100
        }
        // 요소 블록 — 다른 자리를 응력으로 읽으면 바로 드러나게 큰 값으로 채운다.
        st.beam_data.assign(static_cast<size_t>(kBeams) * nv, 9.0e5);        // 이력 변수 자리
        for (int b = 0; b < kBeams; ++b) {
            double* blk = &st.beam_data[static_cast<size_t>(b) * nv];
            for (int w = 0; w < 6 && w < nv; ++w) blk[w] = 7000.0 + w;      // 합력
            for (int k = 0; k < L.nip; ++k) {
                const Ip ip = ipValue(b, k, s);
                double* p = blk + L.ipOff() + 5 * k;
                p[0] = ip.sig;
                p[1] = ip.trs;
                p[2] = ip.ttr;
                p[3] = ip.ep;
                p[4] = ip.eax;
            }
            if (L.bemeng > 0 && L.bemeng <= nv) blk[L.bemeng - 1] = 6.0e6;  // 내부 에너지
        }
        states.push_back(std::move(st));
    }

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
    std::string err;        // 분석 중 std::cerr 에 찍힌 것
};

/// tweak 은 읽어 온 상태를 고친다 — Writer 가 삭제 표를 쓰지 않아 침식은 여기서 넣는다(WithStates 에서만).
Run runDeck(const std::string& path, bool stress, bool strain, Entry entry = Entry::WithStates,
            const std::function<void(std::vector<data::StateData>&)>& tweak = nullptr,
            const std::vector<int32_t>& parts = {}) {
    Run r;
    D3plotReader reader(path);
    if (reader.open() != ErrorCode::SUCCESS) return r;
    r.opened = true;

    AnalysisConfig cfg;
    cfg.d3plot_path = path;
    cfg.analyze_stress = stress;
    cfg.analyze_strain = strain;
    cfg.part_ids = parts;

    std::ostringstream cap;
    std::streambuf* old = std::cerr.rdbuf(cap.rdbuf());
    SinglePassAnalyzer sp(reader);
    if (entry == Entry::WithStates) {
        auto states = reader.read_all_states();
        if (tweak) tweak(states);
        r.res = sp.analyzeWithStates(cfg, states, nullptr);
    } else if (entry == Entry::Parallel) {
        r.res = sp.analyzeParallel(cfg);
    } else {
        r.res = sp.analyzeLegacy(cfg);
    }
    std::cerr.rdbuf(old);
    r.err = cap.str();
    return r;
}

/// 파트 pid 에서 상태 s 에 살아 있는 빔(0부터 순번).
using Live = std::function<std::vector<int>(int pid, int s)>;

std::vector<int> allLive(int pid, int) { return {2 * (pid - 1), 2 * (pid - 1) + 1}; }

const PartTimeSeriesStats* findRow(const std::vector<PartTimeSeriesStats>& hist, int pid) {
    for (const auto& r : hist) {
        if (r.part_id == pid) return &r;
    }
    return nullptr;
}

bool sortedByPart(const std::vector<PartTimeSeriesStats>& hist) {
    return std::is_sorted(hist.begin(), hist.end(), [](const PartTimeSeriesStats& a, const PartTimeSeriesStats& b) {
        return a.part_id < b.part_id;
    });
}

/// 빔 파트 pid 의 이력 줄 하나(양 q)를 기대값과 맞춘다. 합성 덱은 NARBS 가 0 이라 요소 ID = 순번 + 1 이다.
void checkBeamRow(const std::vector<PartTimeSeriesStats>& hist, int pid, int q, int nip, const Live& live) {
    const std::string tag = std::string(kQuantity[q]) + " 파트 " + std::to_string(pid);
    const PartTimeSeriesStats* row = findRow(hist, pid);
    expect(row != nullptr, tag + ": 이력 줄이 있다");
    if (!row) return;
    expect(row->element_type == "beam", tag + ": element_type 이 beam");
    expect(row->quantity == kQuantity[q], tag + ": quantity 이름(" + row->quantity + ")");
    expect(row->data.size() == static_cast<size_t>(kStates), tag + ": 상태 수");

    for (int s = 0; s < kStates && s < static_cast<int>(row->data.size()); ++s) {
        const auto& tp = row->data[s];
        const std::string at = tag + " 상태 " + std::to_string(s);
        expectNear(tp.time, 0.125 * s, at + " 시각");

        const std::vector<int> alive = live(pid, s);
        if (alive.empty()) {
            expect(std::isnan(tp.max_value) && std::isnan(tp.min_value) && std::isnan(tp.avg_value),
                   at + ": 살아 있는 빔이 없으면 0 이 아니라 NaN");
            expect(tp.max_element_id == 0 && tp.min_element_id == 0, at + ": 요소 ID 는 0");
            continue;
        }
        double mx = 0.0, mn = 0.0, sum = 0.0;
        int mx_id = 0, mn_id = 0;
        for (size_t i = 0; i < alive.size(); ++i) {
            const double v = elementWant(alive[i], nip, s)[q];
            if (i == 0 || v > mx) { mx = v; mx_id = alive[i] + 1; }
            if (i == 0 || v < mn) { mn = v; mn_id = alive[i] + 1; }
            sum += v;
        }
        expectNear(tp.max_value, mx, at + " 최대");
        expectNear(tp.min_value, mn, at + " 최소");
        expectNear(tp.avg_value, sum / static_cast<double>(alive.size()), at + " 평균");
        expect(tp.max_element_id == mx_id,
               at + " 최대 요소 got=" + std::to_string(tp.max_element_id) + " want=" + std::to_string(mx_id));
        expect(tp.min_element_id == mn_id,
               at + " 최소 요소 got=" + std::to_string(tp.min_element_id) + " want=" + std::to_string(mn_id));
    }
}

/// 빔만 있는 덱의 네 이력 — 파트 1 · 2 는 기대값대로 있고 파트 3 은 없다. 끈 분석에는 줄이 없다.
void checkBeamHistories(const AnalysisResult& res, int nip, const Live& live, bool stress = true,
                        bool strain = true) {
    const std::vector<PartTimeSeriesStats>* hist[4] = {&res.stress_history, &res.max_principal_history,
                                                       &res.min_principal_history, &res.strain_history};
    for (int q = 0; q < 4; ++q) {
        const std::string tag = kQuantity[q];
        if (!((q < 3) ? stress : strain)) {
            expect(hist[q]->empty(), tag + ": 끈 분석에는 줄이 없다");
            continue;
        }
        expect(hist[q]->size() == 2, tag + ": 줄 2개(값이 없는 파트 3 은 빠진다)");
        expect(sortedByPart(*hist[q]), tag + ": 파트 번호순");
        for (int pid : {1, 2}) checkBeamRow(*hist[q], pid, q, nip, live);
    }
    expect(res.metadata.analyzed_parts == std::vector<int32_t>({1, 2}), "analyzed_parts = {1, 2}");
    expect(res.metadata.num_states == kStates, "num_states");
    expectNear(res.metadata.start_time, 0.0, "start_time");
    expectNear(res.metadata.end_time, 0.125 * (kStates - 1), "end_time");
}

void caseAccepted(const fs::path& dir, const Layout& L, const std::string& folder) {
    Case c(std::string("[배치] ") + L.name + " — NV1D " + std::to_string(L.nv()));
    const std::string path = deckPath(dir, folder);
    if (!writeDeck(path, L)) return expect(false, "합성 d3plot 생성");
    const Run r = runDeck(path, true, true);
    expect(r.opened, "d3plot 열기");

    checkBeamHistories(r.res, L.nip, allLive);
    expect(r.err.find("[parts] 빔:") == std::string::npos, "배치 사유 줄이 없다");
    expect(r.err.find("빔 파트 3") != std::string::npos &&
               r.err.find("적분점 값이 전 상태에서 0") != std::string::npos,
           "값이 없는 파트 3 은 사유와 함께 빠진다");
    expect(r.res.toJSON().find("\"element_type\": \"beam\"") != std::string::npos, "JSON 에 element_type beam");
}

void caseRejected(const fs::path& dir, const Layout& L, const char* key, const std::string& folder) {
    Case c(std::string("[거부] ") + L.name + " — NV1D " + std::to_string(L.nv()));
    const std::string path = deckPath(dir, folder);
    if (!writeDeck(path, L)) return expect(false, "합성 d3plot 생성");
    const Run r = runDeck(path, true, true);
    expect(r.opened, "d3plot 열기");

    expect(r.res.stress_history.empty() && r.res.max_principal_history.empty() &&
               r.res.min_principal_history.empty() && r.res.strain_history.empty(),
           "이력을 만들지 않는다");
    expect(r.res.metadata.analyzed_parts.empty(), "analyzed_parts 가 비어 있다");
    expect(r.err.find("[parts] 빔:") != std::string::npos, "사유 줄이 있다");
    expect(r.err.find(key) != std::string::npos, std::string("사유에 「") + key + "」");
}

void caseErosion(const fs::path& dir) {
    Case c("[침식] 삭제된 빔은 통계에서 빠지고, 살아 있는 빔이 없는 상태는 NaN 이다");
    const Layout L = {"", 4, 0, 64, 7};
    const std::string path = deckPath(dir, "erosion");
    if (!writeDeck(path, L)) return expect(false, "합성 d3plot 생성");
    // deleted_beams 는 빔 배열 안의 1부터 세는 순번이다
    const Run r = runDeck(path, true, true, Entry::WithStates, [](std::vector<data::StateData>& st) {
        st[2].deleted_beams = {1};        // 파트 1 은 빔 2 만 남는다
        st[1].deleted_beams = {3, 4};     // 파트 2 는 이 상태에 살아 있는 빔이 없다
    });
    expect(r.opened, "d3plot 열기");
    checkBeamHistories(r.res, L.nip, [](int pid, int s) -> std::vector<int> {
        if (pid == 1 && s == 2) return {1};
        if (pid == 2 && s == 1) return {};
        return allLive(pid, s);
    });
}

void caseNonFinite(const fs::path& dir) {
    Case c("[발산] 유한하지 않은 적분점 워드가 있는 빔은 그 상태 통계에서 빠진다");
    const Layout L = {"", 4, 0, 0, 0};
    const std::string path = deckPath(dir, "nonfinite");
    if (!writeDeck(path, L)) return expect(false, "합성 d3plot 생성");
    const size_t nv = static_cast<size_t>(L.nv()), off = static_cast<size_t>(L.ipOff());
    const Run r = runDeck(path, true, true, Entry::WithStates, [&](std::vector<data::StateData>& st) {
        st[1].beam_data[2 * nv + off + 5 * 1 + 1] = std::numeric_limits<double>::quiet_NaN();   // 빔 3 · τ_rs
        st[2].beam_data[3 * nv + off + 5 * 3 + 4] = std::numeric_limits<double>::infinity();    // 빔 4 · ε_축
    });
    expect(r.opened, "d3plot 열기");
    checkBeamHistories(r.res, L.nip, [](int pid, int s) -> std::vector<int> {
        if (pid == 2 && s == 1) return {3};
        if (pid == 2 && s == 2) return {2};
        return allLive(pid, s);
    });
}

void caseShortState(const fs::path& dir) {
    Case c("[잘림] 상태의 빔 배열이 짧으면 있는 요소까지만 센다");
    const Layout L = {"", 4, 0, 0, 0};
    const std::string path = deckPath(dir, "short");
    if (!writeDeck(path, L)) return expect(false, "합성 d3plot 생성");
    const size_t nv = static_cast<size_t>(L.nv());
    const Run r = runDeck(path, true, true, Entry::WithStates, [&](std::vector<data::StateData>& st) {
        st[1].beam_data.resize(3 * nv + 5);     // 빔 4 의 블록이 중간에 끊긴다
    });
    expect(r.opened, "d3plot 열기");
    checkBeamHistories(r.res, L.nip, [](int pid, int s) -> std::vector<int> {
        if (pid == 2 && s == 1) return {2};
        return allLive(pid, s);
    });
}

void caseSwitches(const fs::path& dir) {
    Case c("[선택] 응력만 · 변형률만 켠 실행");
    const Layout L = {"", 4, 0, 0, 0};
    const std::string path = deckPath(dir, "switches");
    if (!writeDeck(path, L)) return expect(false, "합성 d3plot 생성");
    checkBeamHistories(runDeck(path, true, false).res, L.nip, allLive, true, false);
    checkBeamHistories(runDeck(path, false, true).res, L.nip, allLive, false, true);
}

void caseEntryPoints(const fs::path& dir) {
    Case c("[진입점] analyzeParallel · analyzeLegacy 도 같은 이력을 낸다");
    const Layout L = {"", 4, 2, 64, 27};
    const std::string path = deckPath(dir, "entry");
    if (!writeDeck(path, L)) return expect(false, "합성 d3plot 생성");
    for (Entry e : {Entry::Parallel, Entry::Legacy}) {
        const Run r = runDeck(path, true, true, e);
        expect(r.opened, "d3plot 열기");
        checkBeamHistories(r.res, L.nip, allLive);
    }
}

void caseClash(const fs::path& dir) {
    Case c("[번호 겹침] 솔리드 파트와 번호가 같은 빔 파트는 빠지고, 남은 빔 줄은 솔리드 줄과 번호순으로 선다");
    const Layout L = {"", 4, 0, 0, 0};
    const std::string path = deckPath(dir, "clash");
    if (!writeDeck(path, L, true)) return expect(false, "합성 d3plot 생성");
    const Run r = runDeck(path, true, true);
    expect(r.opened, "d3plot 열기");

    expect(r.err.find("빔 파트 2") != std::string::npos && r.err.find("번호가 같아") != std::string::npos,
           "겹친 빔 파트 2 의 사유 줄");
    const std::vector<PartTimeSeriesStats>* hist[4] = {&r.res.stress_history, &r.res.max_principal_history,
                                                       &r.res.min_principal_history, &r.res.strain_history};
    for (int q = 0; q < 4; ++q) {
        const std::string tag = kQuantity[q];
        expect(hist[q]->size() == 2, tag + ": 줄 2개(빔 파트 1 · 솔리드 파트 2)");
        expect(sortedByPart(*hist[q]), tag + ": 파트 번호순");
        const PartTimeSeriesStats* solid = findRow(*hist[q], 2);
        expect(solid && solid->element_type.empty(), tag + ": 파트 2 는 솔리드 줄");
        checkBeamRow(*hist[q], 1, q, L.nip, allLive);
    }
    // 솔리드 값이 빔 값에 덮이지 않았다
    if (const PartTimeSeriesStats* solid = findRow(r.res.stress_history, 2)) {
        for (size_t s = 0; s < solid->data.size(); ++s) {
            expectNear(solid->data[s].max_value, 100.0, "솔리드 파트 2 σ_vm 상태 " + std::to_string(s));
        }
    }
    expect(r.res.metadata.analyzed_parts == std::vector<int32_t>({1, 2}), "analyzed_parts = {1, 2}");
}

void caseParts(const fs::path& dir) {
    Case c("[parts] 요청한 파트의 줄만 낸다 — 솔리드 · 빔 · 피크 텐서, 값은 그대로, 모델에 없는 번호는 사유 한 줄");
    const Layout L = {"", 4, 0, 0, 0};
    const std::string path = deckPath(dir, "parts");
    if (!writeDeck(path, L, true)) return expect(false, "합성 d3plot 생성");
    const Run all = runDeck(path, true, true);
    expect(all.opened && all.res.stress_history.size() == 2, "거르지 않은 실행 — 빔 파트 1 · 솔리드 파트 2");
    const auto hists = [](const Run& r) {
        return std::array<const std::vector<PartTimeSeriesStats>*, 4>{
            &r.res.stress_history, &r.res.max_principal_history, &r.res.min_principal_history, &r.res.strain_history};
    };
    const auto sameRow = [](const PartTimeSeriesStats* a, const PartTimeSeriesStats* b) {
        if (!a || !b || a->data.size() != b->data.size()) return false;
        for (size_t s = 0; s < a->data.size(); ++s) {
            const auto& x = a->data[s];
            const auto& y = b->data[s];
            const auto same = [](double u, double v) { return (std::isnan(u) && std::isnan(v)) || u == v; };
            if (!same(x.max_value, y.max_value) || !same(x.min_value, y.min_value) || !same(x.avg_value, y.avg_value) ||
                x.max_element_id != y.max_element_id || x.min_element_id != y.min_element_id) return false;
        }
        return true;
    };

    for (Entry e : {Entry::WithStates, Entry::Parallel, Entry::Legacy}) {
        const std::string at = (e == Entry::WithStates) ? "" : (e == Entry::Parallel) ? " (analyzeParallel)" : " (analyzeLegacy)";
        // 빔 파트 1 만
        const Run r = runDeck(path, true, true, e, nullptr, {1});
        expect(r.opened, "d3plot 열기" + at);
        const auto h = hists(r);
        const auto ha = hists(all);
        for (int q = 0; q < 4; ++q) {
            const std::string tag = std::string(kQuantity[q]) + at;
            expect(h[q]->size() == 1 && findRow(*h[q], 1), tag + ": parts [1] — 빔 파트 1 줄 하나(" + std::to_string(h[q]->size()) + "줄)");
            expect(sameRow(findRow(*h[q], 1), findRow(*ha[q], 1)), tag + ": 빔 파트 1 값이 거르지 않은 실행과 같다");
        }
        expect(r.res.metadata.analyzed_parts == std::vector<int32_t>({1}), "analyzed_parts = {1}" + at);
        expect(r.res.peak_element_tensors.empty(), "피크 텐서 — 솔리드 파트 2 를 빼면 없다" + at);
        expect(r.err.find("모델에 없는") == std::string::npos, "있는 번호만 주면 사유 줄이 없다" + at);
    }
    // 솔리드 파트 2 만 — 번호가 같은 빔 파트 2 는 지금처럼 빠진다
    {
        const Run r = runDeck(path, true, true, Entry::WithStates, nullptr, {2});
        const PartTimeSeriesStats* solid = findRow(r.res.stress_history, 2);
        expect(r.res.stress_history.size() == 1 && solid && solid->element_type.empty(), "parts [2] — 솔리드 파트 2 줄 하나");
        expect(sameRow(solid, findRow(all.res.stress_history, 2)), "솔리드 파트 2 값이 거르지 않은 실행과 같다");
        bool peaks_ok = !r.res.peak_element_tensors.empty();
        for (const auto& t : r.res.peak_element_tensors) peaks_ok = peaks_ok && t.part_id == 2;
        expect(peaks_ok, "피크 텐서는 파트 2 것만");
        expect(r.res.peak_element_tensors.size() == all.res.peak_element_tensors.size(), "피크 텐서 수가 거르지 않은 실행과 같다");
    }
    // 모델에 없는 번호를 섞으면 사유 한 줄 — 있는 번호는 그대로 낸다
    {
        const Run r = runDeck(path, true, true, Entry::WithStates, nullptr, {1, 7});
        expect(r.res.stress_history.size() == 1 && findRow(r.res.stress_history, 1), "parts [1, 7] — 빔 파트 1 줄 하나");
        expect(r.err.find("[parts] 파트 7") != std::string::npos && r.err.find("모델에 없는") != std::string::npos,
               "없는 파트 7 의 사유 줄");
    }
}

}  // namespace

int main() {
    std::printf("=== 빔 파트 응력 이력 검증 (합성 d3plot) ===\n\n");

    const fs::path dir = fs::temp_directory_path() / "kood3plot_beam_part_history_test";
    fs::remove_all(dir);

    const Layout accepted[] = {
        {"확장 워드 없음(R13 꼴) · 적분점 4", 4, 0, 0, 0},
        {"에너지 워드가 블록 끝(BEMENG 27)", 4, 0, 64, 27},
        {"에너지 워드가 합력 바로 뒤(BEMENG 7) — 적분점 블록이 한 칸 밀린다", 4, 0, 64, 7},
        {"이력 변수 2 · 에너지 워드가 적분점 블록 바로 뒤(BEMENG 27)", 4, 2, 64, 27},
        {"이력 변수 2 · 에너지 워드가 블록 끝(BEMENG 41)", 4, 2, 64, 41},
        {"이력 변수 3 · 적분점 2 · 에너지 워드 없음", 2, 3, 64, 0},
    };
    int n = 0;
    for (const Layout& L : accepted) caseAccepted(dir, L, "ok" + std::to_string(n++));

    struct Bad {
        Layout L;
        const char* key;    // 사유 줄에 있어야 하는 말
    };
    const Bad rejected[] = {
        {{"BEMENG 10 — 에너지 워드가 적분점 워드 안", 4, 0, 64, 10}, "BEMENG=10"},
        {{"BEMENG 3 — 에너지 워드가 합력 워드 안", 4, 0, 64, 3}, "BEMENG=3"},
        {{"BEMENG 40 — 에너지 워드가 요소 블록 밖", 4, 0, 64, 40}, "BEMENG=40"},
        {{"NV1D 가 규격 공식과 맞지 않는다", 4, 0, 0, 0, 28}, "규격 공식"},
        {{"합력 워드도 다 없다", 0, 0, 0, 0, 3}, "합력 6 워드"},
        {{"적분점 응력 미기록(R13 꼴)", 0, 0, 0, 0}, "적분점 응력이 기록되지 않은"},
        {{"적분점 응력 미기록(R16 꼴 · BEMENG 7)", 0, 0, 64, 7}, "적분점 응력이 기록되지 않은"},
    };
    n = 0;
    for (const Bad& b : rejected) caseRejected(dir, b.L, b.key, "bad" + std::to_string(n++));

    caseErosion(dir);
    caseNonFinite(dir);
    caseShortState(dir);
    caseSwitches(dir);
    caseEntryPoints(dir);
    caseClash(dir);
    caseParts(dir);

    fs::remove_all(dir);

    std::printf("\n");
    if (g_failed) {
        std::printf("%d건 실패\n", g_failed);
        return 1;
    }
    std::printf("전부 통과\n");
    return 0;
}
