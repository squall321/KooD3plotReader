// 빔 단면력 분석기를 합성 d3plot(축력 값을 미리 알고 있는)으로 검증하는 테스트
/**
 * @file test_beam_analyzer.cpp
 * @brief BeamAnalyzer 검증 — 워드 오프셋·부호·파트 분리
 *
 * 로컬에 빔 요소를 담은 실 d3plot 이 없어(확인한 12개 모델 전부 NEL2=0),
 * D3plotWriter 로 축력을 미리 아는 모델을 만들어 왕복 검증한다.
 *
 * 검증 항목
 *   1. 축력이 워드 0 에서 읽히는가 (전단/모멘트와 섞이지 않는가)
 *   2. 압축(−) 이 절대값으로 뭉개지지 않고 min 으로 나오는가
 *   3. 파트별로 분리 집계되는가
 *   4. NV1D < 6 이면 0 을 내지 않고 실패로 보고하는가
 *
 * Run: ./test_beam_analyzer
 */

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/BeamAnalyzer.hpp"
#include "kood3plot/writer/D3plotWriter.h"

#include <cmath>
#include <cstdio>
#include <filesystem>
#include <string>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

namespace {

int g_failed = 0;

void check(const char* what, double got, double want, double eps = 1e-9) {
    const bool ok = std::abs(got - want) <= eps;
    if (!ok) ++g_failed;
    std::printf("  %s %-42s got=%g want=%g\n", ok ? "[OK]  " : "[FAIL]", what, got, want);
}

void checkTrue(const char* what, bool cond) {
    if (!cond) ++g_failed;
    std::printf("  %s %s\n", cond ? "[OK]  " : "[FAIL]", what);
}

/// 빔 4개(파트 1에 2개, 파트 2에 2개), 2 상태짜리 d3plot 을 만든다.
/// 축력은 파트/요소마다 다른 값을 넣어 집계가 섞이지 않는지 본다.
bool writeSyntheticBeamD3plot(const std::string& path, int nv1d) {
    data::ControlData control;
    control.NDIM = 4;
    control.NUMNP = 5;
    control.NEL8 = 0;
    control.NELT = 0;
    control.NEL4 = 0;
    control.NEL2 = 4;
    control.NV1D = nv1d;
    control.NV3D = 0;
    control.NV2D = 0;
    control.NUMMAT2 = 2;
    control.NMMAT = 2;
    control.IU = 1;
    control.IV = 0;
    control.IA = 0;
    control.IT = 0;
    control.NGLBV = 6;
    control.ENN = control.NEL2 * control.NV1D;
    control.NND = 3 * control.NUMNP;

    data::Mesh mesh;
    mesh.nodes.resize(5);
    for (int i = 0; i < 5; ++i) {
        mesh.nodes[i] = {i + 1, static_cast<double>(i), 0.0, 0.0};
    }

    mesh.beams.resize(4);
    mesh.beam_parts = {1, 1, 2, 2};
    for (int i = 0; i < 4; ++i) {
        mesh.beams[i].id = 101 + i;
        mesh.beams[i].node_ids = {i + 1, i + 2};
    }
    mesh.num_solids = 0;
    mesh.num_thick_shells = 0;
    mesh.num_shells = 0;
    mesh.num_beams = 4;

    std::vector<data::StateData> states;

    // 축력(워드 0): 파트1 = {+100, -250}, 파트2 = {+40, +60}
    // 전단(워드 1)에는 축력과 헷갈리기 쉬운 큰 값을 넣어 오프셋 오류를 잡는다.
    const double axial[4] = {100.0, -250.0, 40.0, 60.0};
    const double shear[4] = {9999.0, 9999.0, 9999.0, 9999.0};

    for (int s = 0; s < 2; ++s) {
        data::StateData st;
        st.time = 0.001 * s;
        st.global_vars.assign(control.NGLBV, 0.0);
        st.node_displacements.resize(control.NUMNP * 3);
        for (int i = 0; i < control.NUMNP; ++i) {
            st.node_displacements[i * 3 + 0] = mesh.nodes[i].x;
            st.node_displacements[i * 3 + 1] = mesh.nodes[i].y;
            st.node_displacements[i * 3 + 2] = mesh.nodes[i].z;
        }
        st.beam_data.assign(static_cast<size_t>(control.NEL2) * nv1d, 0.0);
        for (int b = 0; b < 4; ++b) {
            // 두 번째 상태에서 축력을 2배로 — 시간에 따라 변하는지 확인
            st.beam_data[b * nv1d + 0] = axial[b] * (s == 0 ? 1.0 : 2.0);
            if (nv1d > 1) st.beam_data[b * nv1d + 1] = shear[b];
        }
        states.push_back(std::move(st));
    }

    writer::D3plotWriter w(path);
    w.setControlData(control);
    w.setMesh(mesh);
    w.setStates(states);
    return w.write() == ErrorCode::SUCCESS;
}

void runFullCase(const std::string& path) {
    std::printf("빔 4개 / 파트 2개 / 상태 2개, NV1D=6\n");

    D3plotReader reader(path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::printf("  [FAIL] 합성 d3plot 열기 실패\n");
        ++g_failed;
        return;
    }
    auto states = reader.read_all_states();
    checkTrue("상태 2개 로드", states.size() == 2);
    if (states.size() != 2) return;

    BeamAnalyzer an(reader);
    checkTrue("initialize 성공", an.initialize());
    check("빔 개수", an.numBeams(), 4);

    auto res = an.analyze(states, {BeamComponent::AXIAL_FORCE});
    checkTrue("파트 2개분 산출", res.size() == 2);
    if (res.size() != 2) return;

    for (const auto& st : res) {
        checkTrue("quantity 이름이 beam_axial_force",
                  st.quantity == "beam_axial_force");
        const auto& t0 = st.data[0];
        const auto& t1 = st.data[1];
        if (st.part_id == 1) {
            // 파트1 = {+100, -250}: 최대 +100, 최소 -250 (압축이 절대값으로 뭉개지면 실패)
            check("part1 t0 max (인장)", t0.max_value, 100.0);
            check("part1 t0 min (압축)", t0.min_value, -250.0);
            check("part1 t0 avg", t0.avg_value, -75.0);
            // 합성 파일은 NARBS=0 이라 요소 ID 가 순차(1..4)로 매겨진다.
            // 중요한 건 **어느 빔이 지목되는가** — 압축 -250 은 두 번째 빔이다.
            check("part1 t0 min 요소 = 두 번째 빔", t0.min_element_id, 2);
            check("part1 t1 max (2배)", t1.max_value, 200.0);
            check("part1 t1 min (2배)", t1.min_value, -500.0);
        } else {
            check("part2 t0 max", t0.max_value, 60.0);
            check("part2 t0 min", t0.min_value, 40.0);
            check("part2 t0 max 요소 = 네 번째 빔", t0.max_element_id, 4);
        }
    }

    // 전단 워드가 축력으로 새지 않았는지 — 9999 가 어디에도 안 나와야 한다
    auto shear = an.analyze(states, {BeamComponent::SHEAR_S});
    checkTrue("전단은 별도 워드에서 9999", !shear.empty() &&
              std::abs(shear[0].data[0].max_value - 9999.0) < 1e-9);
}

void runShortNv1dCase(const std::string& path) {
    std::printf("\nNV1D=3 (단면력 미기록) — 0 을 내지 않고 실패로 보고해야 한다\n");
    D3plotReader reader(path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::printf("  [FAIL] 열기 실패\n");
        ++g_failed;
        return;
    }
    BeamAnalyzer an(reader);
    const bool ok = an.initialize();
    checkTrue("initialize 가 false", !ok);
    checkTrue("사유에 NV1D 언급", an.getLastError().find("NV1D") != std::string::npos);
    if (!an.getLastError().empty()) {
        std::printf("         사유: %s\n", an.getLastError().c_str());
    }
}

}  // namespace

int main() {
    std::printf("=== BeamAnalyzer 검증 (합성 d3plot) ===\n\n");

    namespace fs = std::filesystem;
    const fs::path dir = fs::temp_directory_path() / "kood3plot_beam_test";
    fs::create_directories(dir);
    const std::string full = (dir / "d3plot").string();
    const std::string shortnv = (dir / "short" / "d3plot").string();
    fs::create_directories(dir / "short");

    if (!writeSyntheticBeamD3plot(full, 6)) {
        std::printf("합성 d3plot 생성 실패 — 테스트 불가\n");
        return 1;
    }
    runFullCase(full);

    if (writeSyntheticBeamD3plot(shortnv, 3)) {
        runShortNv1dCase(shortnv);
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
