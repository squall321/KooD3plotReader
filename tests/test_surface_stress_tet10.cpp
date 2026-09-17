// TET10 덱(NEL8 < 0)에서도 표면 응력의 침식(삭제) 요소 제외가 켜지는지 보는 시험.
//
// NEL8 이 음수라는 것은 '10절점 사면체라 절점 2개가 더 실린다' 는 규격상 정상
// 표식이다(ls-dyna_database.txt). 부호를 그대로 요소 개수로 쓰면 침식 마스크가
// 비어 버려 삭제된 요소의 응력 0 이 '실측 0' 으로 집계에 섞인다.
//
// 빌드·실행:
//   cmake -S . -B .work/build -DCMAKE_BUILD_TYPE=Release \
//         -DKOOD3PLOT_BUILD_V4_RENDER=OFF -DKOOD3PLOT_BUILD_TESTS=OFF
//   cmake --build .work/build -j4 --target unified_analyzer
//   g++ -std=c++17 -O2 -I include tests/test_surface_stress_tet10.cpp \
//       .work/build/libkood3plot.a .work/build/libkood3plot_writer.a \
//       -fopenmp -lz -o .work/t_tet10 && .work/t_tet10
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/SurfaceExtractor.hpp"
#include "kood3plot/analysis/SurfaceStressAnalyzer.hpp"
#include "kood3plot/writer/D3plotWriter.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

namespace {

int g_failed = 0;

void chk(const char* what, bool ok, const std::string& detail) {
    if (!ok) ++g_failed;
    std::printf("  %s %-46s %s\n", ok ? "OK " : "NG ", what, detail.c_str());
}

/// 육면체 2개(요소 0 = 살아 있음, 요소 1 = 침식)짜리 d3plot 을 만든다.
/// nel8_sign 이 -1 이면 NEL8 을 음수로 적어 TET10 표식을 흉내낸다.
///
/// D3plotWriter 는 삭제(MDLOPT) 구역을 쓰지 않으므로, 상태가 하나뿐인 점을
/// 이용해 EOF 표식 앞에 삭제 워드를 직접 끼워 넣는다.
bool writeDeck(const std::string& path, int nel8_sign) {
    data::ControlData control;
    control.NDIM = 4;
    control.NUMNP = 12;
    control.NEL8 = 2 * nel8_sign;
    control.NELT = 0;
    control.NEL4 = 0;
    control.NEL2 = 0;
    control.NV3D = 7;
    control.NV2D = 0;
    control.NV1D = 0;
    control.NUMMAT8 = 1;
    control.NMMAT = 1;
    control.IU = 1;
    control.IV = 0;
    control.IA = 0;
    control.IT = 0;
    control.NGLBV = 6;
    control.MAXINT = -10003;   // MDLOPT=2 (삭제 목록 있음), MAXINT=3
    control.NND = 3 * control.NUMNP;
    control.ENN = 2 * control.NV3D;

    // 육면체 2개를 x 방향으로 이어 붙인다. 절점 1..12 (내부 1-based).
    data::Mesh mesh;
    mesh.nodes.resize(12);
    for (int i = 0; i < 12; ++i) {
        const int slice = i / 4;
        const int k = i % 4;
        mesh.nodes[i].id = i + 1;
        mesh.nodes[i].x = slice;
        mesh.nodes[i].y = (k == 1 || k == 2) ? 1.0 : 0.0;
        mesh.nodes[i].z = (k >= 2) ? 1.0 : 0.0;
    }
    mesh.solids.resize(2);
    mesh.solid_parts = {1, 1};
    for (int e = 0; e < 2; ++e) {
        mesh.solids[e].id = e + 1;
        mesh.solids[e].type = ElementType::SOLID;
        mesh.solids[e].material_id = 1;
        for (int k = 1; k <= 8; ++k) mesh.solids[e].node_ids.push_back(4 * e + k);
    }
    mesh.num_solids = 2;
    mesh.num_shells = 0;
    mesh.num_beams = 0;
    mesh.num_thick_shells = 0;

    // 상태 1개. 요소 0 은 σ_vm = 100, 침식된 요소 1 은 응력 워드가 전부 0.
    data::StateData st;
    st.time = 0.001;
    st.global_vars.assign(control.NGLBV, 0.0);
    st.node_displacements.resize(control.NUMNP * 3);
    for (int i = 0; i < control.NUMNP; ++i) {
        st.node_displacements[i * 3 + 0] = mesh.nodes[i].x;
        st.node_displacements[i * 3 + 1] = mesh.nodes[i].y;
        st.node_displacements[i * 3 + 2] = mesh.nodes[i].z;
    }
    st.solid_data.assign(static_cast<size_t>(2) * control.NV3D, 0.0);
    st.solid_data[0] = 100.0;   // sxx → σ_vm = 100

    writer::D3plotWriter w(path);
    w.setControlData(control);
    w.setMesh(mesh);
    w.setStates({st});
    if (w.write() != ErrorCode::SUCCESS) return false;

    // EOF 표식(-999999.0f) 을 떼고 삭제 워드(0 = 삭제) 2개를 넣은 뒤 다시 붙인다.
    namespace fs = std::filesystem;
    const auto size = fs::file_size(path);
    if (size < 4) return false;
    std::vector<char> bytes(static_cast<size_t>(size));
    {
        FILE* f = std::fopen(path.c_str(), "rb");
        if (!f) return false;
        const size_t got = std::fread(bytes.data(), 1, bytes.size(), f);
        std::fclose(f);
        if (got != bytes.size()) return false;
    }
    const float del[2] = {1.0f, 0.0f};   // 요소 1 은 살아 있고 요소 2 는 삭제
    const float eof_marker = -999999.0f;
    {
        FILE* f = std::fopen(path.c_str(), "wb");
        if (!f) return false;
        std::fwrite(bytes.data(), 1, bytes.size() - 4, f);   // EOF 표식 제거
        std::fwrite(del, sizeof(float), 2, f);
        std::fwrite(&eof_marker, sizeof(float), 1, f);
        std::fclose(f);
    }
    return true;
}

/// 덱 하나를 읽어 표면 응력 통계를 낸다. 성공하면 true.
bool runDeck(const std::string& path, SurfaceStressStats& stats, size_t& n_deleted) {
    D3plotReader reader(path);
    if (reader.open() != ErrorCode::SUCCESS) return false;

    auto mesh = reader.read_mesh();
    auto states = reader.read_all_states();
    if (states.empty()) return false;
    n_deleted = states.back().deleted_solids.size();

    SurfaceExtractor extractor(reader);
    (void)mesh;
    auto surfaces = extractor.extractExteriorSurfaces();

    SurfaceStressAnalyzer analyzer(reader);
    stats = analyzer.analyzeState(surfaces.faces, states.back());
    return true;
}

}  // namespace

int main(int argc, char** argv) {
    namespace fs = std::filesystem;
    // 산출물은 저장소 안 .work/ 에 둔다 (/tmp 는 세션이 끊기면 사라진다).
    const fs::path dir = (argc > 1) ? fs::path(argv[1]) : fs::path(".work") / "tet10_test";
    std::error_code ec;
    fs::create_directories(dir, ec);
    const std::string pos = (dir / "d3plot_pos").string();
    const std::string neg = (dir / "d3plot_neg").string();

    if (!writeDeck(pos, +1) || !writeDeck(neg, -1)) {
        std::printf("[FAIL] 합성 덱 생성 실패\n");
        return 1;
    }

    SurfaceStressStats s_pos, s_neg;
    size_t del_pos = 0, del_neg = 0;
    if (!runDeck(pos, s_pos, del_pos) || !runDeck(neg, s_neg, del_neg)) {
        std::printf("[FAIL] 합성 덱을 읽지 못함\n");
        return 1;
    }

    std::printf("[준비] NEL8=+2: 삭제목록 %zu개 / NEL8=-2: 삭제목록 %zu개\n", del_pos, del_neg);
    chk("삭제 목록이 두 덱 모두에서 읽힌다 (시험의 전제)",
        del_pos == 1 && del_neg == 1,
        "pos=" + std::to_string(del_pos) + " neg=" + std::to_string(del_neg));

    std::printf("\n[A] NEL8 > 0 — 침식 제외가 켜진다 (대조군)\n");
    chk("침식 면이 제외됨", s_pos.num_faces_skipped > 0,
        "skipped=" + std::to_string(s_pos.num_faces_skipped));
    chk("σ_vm 최소가 0 으로 붕괴하지 않음", s_pos.von_mises_min > 0.0,
        "min=" + std::to_string(s_pos.von_mises_min));

    std::printf("\n[B] NEL8 < 0 (TET10 표식) — 같은 침식 제외가 켜져야 한다\n");
    chk("제외된 면 수가 대조군과 같음",
        s_neg.num_faces_skipped == s_pos.num_faces_skipped,
        "neg=" + std::to_string(s_neg.num_faces_skipped) +
            " pos=" + std::to_string(s_pos.num_faces_skipped));
    chk("σ_vm 최소가 대조군과 같음",
        std::abs(s_neg.von_mises_min - s_pos.von_mises_min) < 1e-9,
        "neg=" + std::to_string(s_neg.von_mises_min) +
            " pos=" + std::to_string(s_pos.von_mises_min));
    chk("σ_vm 평균이 대조군과 같음",
        std::abs(s_neg.von_mises_avg - s_pos.von_mises_avg) < 1e-9,
        "neg=" + std::to_string(s_neg.von_mises_avg) +
            " pos=" + std::to_string(s_pos.von_mises_avg));

    fs::remove_all(dir, ec);
    std::printf("\n%s  실패 %d 건\n", g_failed ? "[FAIL]" : "[PASS]", g_failed);
    return g_failed ? 1 : 0;
}
