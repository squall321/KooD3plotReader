// MotionAnalyzer 검증 — 절점 ID 규약 · 없는 파트 요청 · 첫 상태 속도
//
// 로컬 실덱은 real_node_ids 가 전부 항등(1..N)이라 "내부 순번을 절점 ID 로
// 내보내는" 결함이 드러나지 않는다. 그래서 D3plotWriter 로 NARBS 가 비항등인
// 모델을 만들어 왕복 검증한다.
//
// 검증 항목
//   1. Max_Disp_Node_ID 가 내부 순번(idx+1)이 아니라 사용자 절점 ID 인가
//   2. 메시에 없는 파트를 요청하면 전 0 시계열을 만들지 않고 걸러내는가
//   3. d3plot 이 절점 속도(IV)·가속도(IA)를 싣고 있으면 그것을 쓰는가
//      (첫 상태 속도가 차분 불가라고 0 으로 나가면 안 된다)
//   4. 침식 덱 — 그 상태에서 산 요소에 하나도 속하지 않는 절점(지운 요소에만 속해 떨어져 나간 절점)은
//      운동 지표에서 뺀다. 그 좌표 · 속도는 발산해도 유한값일 수 있다(erode7 ~1e21). 파트가 통째로 지워진
//      상태는 0 이 아니라 값 없음(NaN)이다.
//
// Run:
//   # --target unified_analyzer 만으로는 kood3plot_writer 가 빌드되지 않는다
//   # (unified_analyzer 는 kood3plot 만 링크한다). 대상에 함께 적어야 한다.
//   cmake --build build -j4 --target unified_analyzer kood3plot_writer
//   g++ -std=c++17 -O2 -I include tests/test_motion_analyzer.cpp \
//       build/libkood3plot.a build/libkood3plot_writer.a -fopenmp -lz -o /tmp/t_motion
//   /tmp/t_motion
//
// ctest 에 등록되어 있으므로 `ctest -R MotionAnalyzer` 로도 돌릴 수 있다.

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/MotionAnalyzer.hpp"
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

void check(const char* what, double got, double want, double eps = 1e-6) {
    const bool ok = std::abs(got - want) <= eps;
    if (!ok) ++g_failed;
    std::printf("  %s %-46s got=%g want=%g\n", ok ? "[OK]  " : "[FAIL]", what, got, want);
}

void checkTrue(const char* what, bool cond) {
    if (!cond) ++g_failed;
    std::printf("  %s %s\n", cond ? "[OK]  " : "[FAIL]", what);
}

// 절점 8개(hex 1개) 짜리 파트 2개, 상태 3개.
// 절점 ID 는 일부러 비항등 — 1..8 이 아니라 1001.. 로 띄운다.
// 내부 순번 idx+1 (1..16) 과 사용자 ID (1001..1016) 가 절대 겹치지 않는다.
constexpr int kNumNodes = 16;
constexpr int kNodeIdBase = 1000;   // 사용자 절점 ID = 1000 + (idx+1)
constexpr double kV0 = 5000.0;      // *INITIAL_VELOCITY 5000 mm/s (−Z)

bool writeSyntheticMotionD3plot(const std::string& path) {
    data::ControlData control;
    control.NDIM = 4;
    control.NUMNP = kNumNodes;
    control.NEL8 = 2;
    control.NELT = 0;
    control.NEL4 = 0;
    control.NEL2 = 0;
    control.NV3D = 7;
    control.NV1D = 0;
    control.NV2D = 0;
    control.NUMMAT8 = 2;
    control.NMMAT = 2;
    control.IU = 1;
    control.IV = 1;     // 절점 속도 기록
    control.IA = 0;
    control.IT = 0;
    control.NGLBV = 6;
    control.ENN = control.NEL8 * control.NV3D;
    control.NND = 3 * control.NUMNP;
    // NARBS = 10 + NUMNP + NEL8 + NELT + NEL2 + NEL4 + 4*NMMAT
    control.NARBS = 10 + control.NUMNP + control.NEL8 + 4 * control.NMMAT;

    data::Mesh mesh;
    mesh.nodes.resize(kNumNodes);
    mesh.real_node_ids.resize(kNumNodes);
    for (int i = 0; i < kNumNodes; ++i) {
        const int uid = kNodeIdBase + i + 1;
        // hex 두 개를 z 로 쌓는다. 절점 8..15 (두 번째 hex) 가 더 멀리 움직인다.
        mesh.nodes[i] = {uid,
                         static_cast<double>(i % 2),
                         static_cast<double>((i / 2) % 2),
                         static_cast<double>(i / 4)};
        mesh.real_node_ids[i] = uid;
    }

    mesh.solids.resize(2);
    mesh.solid_parts = {1, 2};
    for (int e = 0; e < 2; ++e) {
        mesh.solids[e].id = 501 + e;
        mesh.solids[e].type = ElementType::SOLID;
        mesh.solids[e].material_id = e + 1;
        // 연결성은 **내부 1-based 순번**이다 (real_node_ids 역맵이 아니다).
        mesh.solids[e].node_ids.resize(8);
        for (int k = 0; k < 8; ++k) mesh.solids[e].node_ids[k] = e * 8 + k + 1;
    }
    mesh.solid_materials = {1, 2};
    mesh.real_solid_ids = {501, 502};
    mesh.num_solids = 2;
    mesh.num_shells = 0;
    mesh.num_beams = 0;
    mesh.num_thick_shells = 0;

    // 파트 2 의 마지막 절점(내부 idx 15, 사용자 ID 1016)이 가장 크게 움직인다.
    std::vector<data::StateData> states;
    for (int s = 0; s < 3; ++s) {
        data::StateData st;
        st.time = 1e-3 * s;
        st.global_vars.assign(control.NGLBV, 0.0);
        st.node_displacements.resize(kNumNodes * 3);
        st.node_velocities.resize(kNumNodes * 3);
        for (int i = 0; i < kNumNodes; ++i) {
            const double extra = (i == 15) ? 2.0 : 0.0;   // 최대 변위 절점
            st.node_displacements[i * 3 + 0] = mesh.nodes[i].x;
            st.node_displacements[i * 3 + 1] = mesh.nodes[i].y;
            st.node_displacements[i * 3 + 2] = mesh.nodes[i].z - (1.0 + extra) * s;
            // 기록된 절점 속도 — 전 상태 동일한 −Z 방향 kV0
            st.node_velocities[i * 3 + 0] = 0.0;
            st.node_velocities[i * 3 + 1] = 0.0;
            st.node_velocities[i * 3 + 2] = -kV0;
        }
        st.solid_data.assign(static_cast<size_t>(control.NEL8) * control.NV3D, 0.0);
        states.push_back(std::move(st));
    }

    writer::D3plotWriter w(path);
    w.setControlData(control);
    w.setMesh(mesh);
    w.setStates(states);
    return w.write() == ErrorCode::SUCCESS;
}

void runCases(const std::string& path) {
    D3plotReader reader(path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::printf("  [FAIL] 합성 d3plot 열기 실패\n");
        ++g_failed;
        return;
    }
    auto states = reader.read_all_states();
    checkTrue("상태 3개 로드", states.size() == 3);
    if (states.size() != 3) return;
    checkTrue("절점 속도(IV)가 실려 있음", !states[0].node_velocities.empty());

    auto mesh = reader.read_mesh();
    checkTrue("real_node_ids 가 비항등", !mesh.real_node_ids.empty() &&
              mesh.real_node_ids[0] != 1);

    std::printf("\n[1] Max_Disp_Node_ID 가 사용자 절점 ID 인가\n");
    {
        MotionAnalyzer an(reader);
        an.setParts({2});
        checkTrue("initialize 성공", an.initialize());
        for (const auto& st : states) an.processState(st);
        auto res = an.getResults();
        checkTrue("파트 2 결과 1개", res.size() == 1);
        if (res.size() == 1 && res[0].data.size() == 3) {
            const auto& last = res[0].data.back();
            // 내부 idx 15 → 순번 16, 사용자 ID 1016.
            check("최대 변위 절점 ID", last.max_displacement_node_id,
                  kNodeIdBase + 16);
            checkTrue("내부 순번 16 을 그대로 내보내지 않음",
                      last.max_displacement_node_id != 16);
        } else {
            ++g_failed;
            std::printf("  [FAIL] 파트 2 시계열이 3점이 아님\n");
        }
    }

    std::printf("\n[2] 메시에 없는 파트를 요청하면\n");
    {
        MotionAnalyzer an(reader);
        an.setParts({2, 999});
        const bool init_ok = an.initialize();
        checkTrue("initialize 성공 (성한 파트가 남아 있으므로)", init_ok);
        for (const auto& st : states) an.processState(st);
        auto res = an.getResults();
        bool has_999 = false;
        for (const auto& r : res) if (r.part_id == 999) has_999 = true;
        checkTrue("파트 999 시계열을 만들지 않음", !has_999);
        checkTrue("파트 2 는 남음", res.size() == 1 && res[0].part_id == 2);
        checkTrue("걸러낸 사실을 사유로 남김",
                  an.getLastError().find("999") != std::string::npos);
    }

    std::printf("\n[3] 없는 파트만 요청하면 실패로 보고\n");
    {
        MotionAnalyzer an(reader);
        an.setParts({999});
        checkTrue("initialize 실패", !an.initialize());
        checkTrue("사유에 999 가 들어감",
                  an.getLastError().find("999") != std::string::npos);
    }

    std::printf("\n[4] 기록된 절점 속도(IV)를 쓰는가 — 첫 상태가 0 이면 안 된다\n");
    {
        MotionAnalyzer an(reader);
        an.setParts({2});
        an.initialize();
        for (const auto& st : states) an.processState(st);
        auto res = an.getResults();
        if (res.size() == 1 && res[0].data.size() == 3) {
            check("t=0 속도 크기", res[0].data[0].avg_velocity_magnitude, kV0, 1e-3);
            check("t=0 속도 Z", res[0].data[0].avg_velocity.z, -kV0, 1e-3);
            check("t=2 속도 크기", res[0].data[2].avg_velocity_magnitude, kV0, 1e-3);
        } else {
            ++g_failed;
            std::printf("  [FAIL] 시계열이 3점이 아님\n");
        }
    }
}

// 침식 덱 — 육면체 둘이 면(절점 순번 5~8)을 공유한다. 둘 다 파트 1. MDLOPT 2(삭제 표).
// 상태 2 에서 요소 1(순번) · 상태 3 에서 요소 1 · 2 가 지워진다. 요소 1 에만 속한 절점 1~4 는 상태 2 부터
// 좌표가 x 로 1e6 · 속도가 1e9 로 튄다(떨어져 나간 절점 — 유한값). 나머지 절점은 상태마다 z 로 0.1 s 내려가고 속도 −100.
constexpr int kErodeNodes = 12;

bool writeErosionD3plot(const std::string& path) {
    data::ControlData control;
    control.NDIM = 4;
    control.NUMNP = kErodeNodes;
    control.NEL8 = 2;
    control.NV3D = 7;
    control.NUMMAT8 = 1;
    control.NMMAT = 1;
    control.IU = 1;
    control.IV = 1;
    control.NGLBV = 6;
    control.MAXINT = -10003;            // MDLOPT 2 — 상태마다 요소 삭제 표
    control.ENN = control.NEL8 * control.NV3D;
    control.NND = 3 * control.NUMNP;

    data::Mesh mesh;
    mesh.nodes.resize(kErodeNodes);
    for (int i = 0; i < kErodeNodes; ++i) {
        mesh.nodes[i] = {i + 1, static_cast<double>(i % 2), static_cast<double>((i / 2) % 2), static_cast<double>(i / 4)};
    }
    mesh.solids.resize(2);
    mesh.solid_parts = {1, 1};
    for (int e = 0; e < 2; ++e) {
        mesh.solids[e].id = e + 1;
        mesh.solids[e].type = ElementType::SOLID;
        mesh.solids[e].material_id = 1;
        for (int k = 0; k < 8; ++k) mesh.solids[e].node_ids.push_back(4 * e + k + 1);   // 요소 1: 1~8, 요소 2: 5~12
    }
    mesh.num_solids = 2;

    std::vector<data::StateData> states;
    for (int s = 0; s < 4; ++s) {
        data::StateData st;
        st.time = 1e-3 * s;
        st.global_vars.assign(control.NGLBV, 0.0);
        st.node_displacements.resize(kErodeNodes * 3);
        st.node_velocities.resize(kErodeNodes * 3);
        for (int i = 0; i < kErodeNodes; ++i) {
            const bool debris = (s >= 2 && i < 4);
            st.node_displacements[i * 3 + 0] = mesh.nodes[i].x + (debris ? 1e6 : 0.0);
            st.node_displacements[i * 3 + 1] = mesh.nodes[i].y;
            st.node_displacements[i * 3 + 2] = mesh.nodes[i].z - 0.1 * s;
            st.node_velocities[i * 3 + 0] = debris ? 1e9 : 0.0;
            st.node_velocities[i * 3 + 1] = 0.0;
            st.node_velocities[i * 3 + 2] = -100.0;
        }
        st.solid_data.assign(static_cast<size_t>(control.NEL8) * control.NV3D, 0.0);
        if (s >= 2) st.deleted_solids.push_back(1);
        if (s >= 3) st.deleted_solids.push_back(2);
        states.push_back(std::move(st));
    }

    writer::D3plotWriter w(path);
    w.setControlData(control);
    w.setMesh(mesh);
    w.setStates(states);
    return w.write() == ErrorCode::SUCCESS;
}

void runErosionCase(const std::string& path) {
    std::printf("\n[5] 침식 덱 — 떨어져 나간 절점을 운동 지표에서 뺀다\n");
    D3plotReader reader(path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::printf("  [FAIL] 침식 d3plot 열기 실패\n");
        ++g_failed;
        return;
    }
    auto states = reader.read_all_states();
    checkTrue("상태 4개 · 상태 2 에 지운 요소 1개 · 상태 3 에 2개",
              states.size() == 4 && states[2].deleted_solids.size() == 1 && states[3].deleted_solids.size() == 2);
    if (states.size() != 4) return;
    MotionAnalyzer an(reader);
    an.setParts({1});
    checkTrue("initialize 성공", an.initialize());
    for (const auto& st : states) an.processState(st);
    auto res = an.getResults();
    if (res.size() != 1 || res[0].data.size() != 4) {
        ++g_failed;
        std::printf("  [FAIL] 파트 1 시계열이 4점이 아님\n");
        return;
    }
    const auto& d = res[0].data;
    check("상태 1 최대 변위(모든 절점)", d[1].max_displacement_magnitude, 0.1);
    check("상태 2 최대 변위 — 떨어진 절점 1~4 를 뺀다", d[2].max_displacement_magnitude, 0.2);
    check("상태 2 평균 변위 크기", d[2].avg_displacement_magnitude, 0.2);
    check("상태 2 평균 속도 크기 — 떨어진 절점 속도 1e9 를 뺀다", d[2].avg_velocity_magnitude, 100.0, 1e-6);
    checkTrue("상태 3 — 파트가 통째로 지워졌다: 최대 변위는 0 이 아니라 값 없음(NaN)",
              std::isnan(d[3].max_displacement_magnitude));
    checkTrue("상태 3 — 평균 변위도 값 없음(NaN)", std::isnan(d[3].avg_displacement_magnitude));
    res[0].computeGlobalStats();
    check("전 구간 최대 변위 — 산 절점만(0.2)", res[0].max_displacement_magnitude, 0.2);
    check("전 구간 최대 속도 — 산 절점만(100)", res[0].peak_velocity_magnitude, 100.0, 1e-6);
}

}  // namespace

int main() {
    const std::string dir = std::filesystem::temp_directory_path().string()
                          + "/kood3plot_motion_test";
    std::filesystem::create_directories(dir);
    const std::string path = dir + "/d3plot";

    std::printf("합성 d3plot 생성: %s\n", path.c_str());
    if (!writeSyntheticMotionD3plot(path)) {
        std::printf("  [FAIL] 합성 d3plot 쓰기 실패\n");
        return 1;
    }

    runCases(path);

    const std::string erode_dir = dir + "/erode";
    std::filesystem::create_directories(erode_dir);
    if (!writeErosionD3plot(erode_dir + "/d3plot")) {
        std::printf("  [FAIL] 침식 d3plot 쓰기 실패\n");
        ++g_failed;
    } else {
        runErosionCase(erode_dir + "/d3plot");
    }

    std::filesystem::remove_all(dir);
    std::printf("\n%s  (%d fail)\n", g_failed ? "실패" : "전부 통과", g_failed);
    return g_failed ? 1 : 0;
}
