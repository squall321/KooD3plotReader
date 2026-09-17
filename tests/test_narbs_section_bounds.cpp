// NARBS 구역 경계를 지키는지 보는 시험 — material types 가 구역 밖 워드를 읽지 않는가.
//
// 규격상 NARBS = 헤더(10 또는 16) + NUMNP + NEL8 + NEL2 + NEL4 + NELT + 3*NMMAT 다.
// 남은 워드를 셀 때 헤더를 빼먹으면 remaining 이 항상 정확히 헤더 크기가 되어,
// 구역이 끝난 지점에서 10~16 워드를 더 읽어 다음 구역의 이진 쓰레기를
// material_types 에 담는다. 이 저장소 D3plotWriter 는 규격에 없는 4번째 NMMAT
// 배열(재질 타입)을 더 쓰므로, 그 파일에서는 진짜 NMMAT 개만 나와야 한다.
//
// 빌드·실행:
//   g++ -std=c++17 -O2 -I include tests/test_narbs_section_bounds.cpp \
//       .work/build/libkood3plot.a .work/build/libkood3plot_writer.a \
//       -fopenmp -lz -o .work/t_narbs && .work/t_narbs
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/writer/D3plotWriter.h"

#include <cstdio>
#include <filesystem>
#include <string>
#include <vector>

using namespace kood3plot;

namespace {

int g_failed = 0;

void chk(const char* what, bool ok, const std::string& detail) {
    if (!ok) ++g_failed;
    std::printf("  %s %-52s %s\n", ok ? "OK " : "NG ", what, detail.c_str());
}

const int kNumNodes = 12;
const int kNumSolids = 2;
const int kNumParts = 3;

/// 솔리드 2개·파트 3개짜리 d3plot 을 NARBS 포함으로 쓴다.
/// 재질 타입은 파트마다 다른 값(11,22,33)을 넣어 구역 밖 워드와 구별한다.
bool writeDeck(const std::string& path) {
    data::ControlData control;
    control.NDIM = 4;
    control.NUMNP = kNumNodes;
    control.NEL8 = kNumSolids;
    control.NELT = 0;
    control.NEL4 = 0;
    control.NEL2 = 0;
    control.NV3D = 7;
    control.NUMMAT8 = kNumParts;
    control.NMMAT = kNumParts;
    control.IU = 1;
    control.NGLBV = 6;
    control.MAXINT = 3;
    control.NND = 3 * control.NUMNP;
    control.ENN = kNumSolids * control.NV3D;
    // D3plotWriter 가 쓰는 배치: 헤더 10 + NUMNP + NEL8 + NELT + NEL2 + NEL4 + 4*NMMAT
    control.NARBS = 10 + control.NUMNP + kNumSolids + 4 * kNumParts;

    data::Mesh mesh;
    mesh.nodes.resize(kNumNodes);
    for (int i = 0; i < kNumNodes; ++i) {
        mesh.nodes[i].id = i + 1;
        mesh.nodes[i].x = i / 4;
        mesh.nodes[i].y = (i % 4 == 1 || i % 4 == 2) ? 1.0 : 0.0;
        mesh.nodes[i].z = (i % 4 >= 2) ? 1.0 : 0.0;
    }
    mesh.solids.resize(kNumSolids);
    mesh.solid_parts = {1, 2};
    for (int e = 0; e < kNumSolids; ++e) {
        mesh.solids[e].id = 101 + e;
        mesh.solids[e].type = ElementType::SOLID;
        mesh.solids[e].material_id = e + 1;
        for (int k = 1; k <= 8; ++k) mesh.solids[e].node_ids.push_back(4 * e + k);
    }
    mesh.num_solids = kNumSolids;
    mesh.real_node_ids.clear();
    for (int i = 0; i < kNumNodes; ++i) mesh.real_node_ids.push_back(i + 1);
    mesh.real_solid_ids = {101, 102};
    mesh.material_types = {11, 22, 33};

    data::StateData st;
    st.time = 0.001;
    st.global_vars.assign(control.NGLBV, 0.0);
    st.node_displacements.resize(control.NUMNP * 3);
    for (int i = 0; i < control.NUMNP; ++i) {
        st.node_displacements[i * 3 + 0] = mesh.nodes[i].x;
        st.node_displacements[i * 3 + 1] = mesh.nodes[i].y;
        st.node_displacements[i * 3 + 2] = mesh.nodes[i].z;
    }
    st.solid_data.assign(static_cast<size_t>(kNumSolids) * control.NV3D, 0.0);

    writer::D3plotWriter w(path);
    w.setControlData(control);
    w.setMesh(mesh);
    w.setStates({st});
    return w.write() == ErrorCode::SUCCESS;
}

}  // namespace

int main(int argc, char** argv) {
    namespace fs = std::filesystem;
    // 산출물은 저장소 안 .work/ 에 둔다 (/tmp 는 세션이 끊기면 사라진다).
    const fs::path dir = (argc > 1) ? fs::path(argv[1]) : fs::path(".work") / "narbs_test";
    std::error_code ec;
    fs::create_directories(dir, ec);
    const std::string path = (dir / "d3plot").string();

    if (!writeDeck(path)) {
        std::printf("[FAIL] 합성 덱 생성 실패\n");
        return 1;
    }

    D3plotReader reader(path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::printf("[FAIL] 합성 덱을 열지 못함\n");
        return 1;
    }
    const auto mesh = reader.read_mesh();

    std::printf("[A] material types 가 NARBS 구역 안에서만 읽힌다\n");
    chk("개수 = NMMAT", mesh.material_types.size() == static_cast<size_t>(kNumParts),
        "n=" + std::to_string(mesh.material_types.size()));
    if (mesh.material_types.size() == static_cast<size_t>(kNumParts)) {
        chk("값이 쓴 그대로", mesh.material_types == std::vector<int32_t>({11, 22, 33}),
            std::to_string(mesh.material_types[0]) + "," +
                std::to_string(mesh.material_types[1]) + "," +
                std::to_string(mesh.material_types[2]));
    }

    std::printf("\n[B] 앞 블록들은 그대로 읽힌다 (회귀 없음)\n");
    chk("절점 ID 12개", mesh.real_node_ids.size() == kNumNodes,
        "n=" + std::to_string(mesh.real_node_ids.size()));
    chk("솔리드 ID = 101,102", mesh.real_solid_ids == std::vector<int32_t>({101, 102}),
        mesh.real_solid_ids.empty() ? "(없음)" : std::to_string(mesh.real_solid_ids[0]));

    fs::remove_all(dir, ec);
    std::printf("\n%s  실패 %d 건\n", g_failed ? "[FAIL]" : "[PASS]", g_failed);
    return g_failed ? 1 : 0;
}
