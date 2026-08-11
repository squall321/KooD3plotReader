// 셸 d3plot 을 두께셸(NELT) d3plot 으로 변환해 두께셸 분석 경로를 실데이터로 검증하는 도구
/**
 * @file make_tshell_from_shell.cpp
 * @brief 셸 d3plot → 두께셸 d3plot 변환 (검증용)
 *
 * 두께셸 요소를 담은 실 d3plot 이 로컬에 없고 (확인한 모델 전부 NELT=0),
 * LS-DYNA 라이선스도 만료돼 새로 풀 수 없다. 그래서 기존 셸 모델의
 * **실제 지오메트리와 전 상태 변형**을 그대로 쓰되 요소만 두께셸로 바꾼다.
 *
 * 변환 규칙
 *   · 각 4절점 셸 → 8절점 두께셸. 하판은 원래 절점, 상판은 요소 법선 방향으로
 *     두께만큼 밀어낸 새 절점.
 *   · 절점 배열 = [원본 N개][오프셋 N개]. 모든 상태에서 같은 규칙으로 민다.
 *   · 두께셸 결과값(NV3DT)은 셸 결과에서 가져오지 않고 0 으로 둔다 —
 *     이 도구의 목적은 **지오메트리 경로**(요소품질·모션·파트배정) 검증이다.
 *     값까지 옮기면 물리적으로 근거 없는 수치를 만들게 된다.
 *
 * 사용:
 *   ./make_tshell_from_shell <입력 d3plot> <출력 디렉터리> [두께]
 */

#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/writer/D3plotWriter.h"

#include <cmath>
#include <cstdio>
#include <filesystem>
#include <string>
#include <vector>

using namespace kood3plot;

namespace {

struct V3 { double x = 0, y = 0, z = 0; };

V3 sub(const V3& a, const V3& b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
V3 cross(const V3& a, const V3& b) {
    return {a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x};
}
double len(const V3& a) { return std::sqrt(a.x * a.x + a.y * a.y + a.z * a.z); }

/// 절점 좌표를 상태에서 읽는다 (d3plot 규약: node_displacements = 현재 좌표).
V3 coordAt(const data::Mesh& mesh, const data::StateData& st, size_t idx) {
    if (idx * 3 + 2 < st.node_displacements.size()) {
        return {st.node_displacements[idx * 3 + 0],
                st.node_displacements[idx * 3 + 1],
                st.node_displacements[idx * 3 + 2]};
    }
    if (idx < mesh.nodes.size()) {
        return {mesh.nodes[idx].x, mesh.nodes[idx].y, mesh.nodes[idx].z};
    }
    return {};
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 3) {
        std::printf("사용: %s <입력 d3plot> <출력 디렉터리> [두께]\n", argv[0]);
        return 2;
    }
    const std::string in_path = argv[1];
    const std::string out_dir = argv[2];
    const double thickness = (argc > 3) ? std::atof(argv[3]) : 1.0;

    D3plotReader reader(in_path);
    if (reader.open() != ErrorCode::SUCCESS) {
        std::printf("입력 d3plot 열기 실패: %s\n", in_path.c_str());
        return 1;
    }
    const auto& cd_in = reader.get_control_data();
    auto mesh_in = reader.read_mesh();
    auto states_in = reader.read_all_states();

    if (mesh_in.shells.empty()) {
        std::printf("셸 요소가 없습니다 (NEL4=%d) — 변환할 것이 없습니다\n", cd_in.NEL4);
        return 1;
    }
    std::printf("입력: 절점 %zu, 셸 %zu, 상태 %zu\n",
                mesh_in.nodes.size(), mesh_in.shells.size(), states_in.size());

    const size_t n_node = mesh_in.nodes.size();
    const size_t n_elem = mesh_in.shells.size();

    // ---- 제어 데이터 ----
    data::ControlData cd;
    cd.NDIM = 4;
    cd.NUMNP = static_cast<int32_t>(n_elem * 8);
    cd.NEL8 = 0;
    cd.NEL4 = 0;
    cd.NEL2 = 0;
    cd.NELT = static_cast<int32_t>(n_elem);
    cd.NV3DT = 22;                 // 두께셸 요소당 값 (기본 레이아웃)
    cd.NV3D = 0;
    cd.NV2D = 0;
    cd.NV1D = 0;
    cd.NUMMATT = cd_in.NUMMAT4 > 0 ? cd_in.NUMMAT4 : 1;
    cd.NMMAT = cd.NUMMATT;
    cd.IU = 1;
    cd.IV = 0;
    cd.IA = 0;
    cd.IT = 0;
    cd.NGLBV = 6;
    cd.NND = 3 * cd.NUMNP;
    cd.ENN = cd.NELT * cd.NV3DT;

    // ---- 메시 ----
    // **요소마다 독립 8절점**. 절점을 공유하면 인접 셸의 법선을 평균낼 때
    // 방향이 상쇄·반전돼 일부 요소가 뒤집힌 hex 가 된다 (실측: scaled Jacobian
    // -1.0, 음수 2536/3750). 각 요소가 제 법선으로 밀려야 형상이 성립한다.
    data::Mesh mesh;
    const size_t n_out_node = n_elem * 8;
    mesh.nodes.resize(n_out_node);
    for (size_t i = 0; i < n_out_node; ++i) {
        mesh.nodes[i].id = static_cast<int32_t>(i + 1);
    }
    mesh.num_solids = 0;
    mesh.num_beams = 0;
    mesh.num_shells = 0;
    mesh.num_thick_shells = n_elem;
    mesh.thick_shells.resize(n_elem);
    mesh.thick_shell_materials.resize(n_elem);
    mesh.thick_shell_parts.resize(n_elem);

    for (size_t e = 0; e < n_elem; ++e) {
        const auto& sh = mesh_in.shells[e];
        auto& ts = mesh.thick_shells[e];
        ts.id = sh.id;
        ts.node_ids.resize(8);
        for (int k = 0; k < 8; ++k) {
            ts.node_ids[k] = static_cast<int32_t>(e * 8 + k + 1);   // 1-based
        }
        (void)sh;
        const int32_t mat = (e < mesh_in.shell_materials.size()) ? mesh_in.shell_materials[e] : 1;
        mesh.thick_shell_materials[e] = mat;
        mesh.thick_shell_parts[e] = (e < mesh_in.shell_parts.size()) ? mesh_in.shell_parts[e] : mat;
    }

    // ---- 상태: 하판은 원본 좌표, 상판은 법선 방향 오프셋 ----
    std::vector<data::StateData> states;
    states.reserve(states_in.size());
    for (const auto& si : states_in) {
        data::StateData st;
        st.time = si.time;
        st.global_vars.assign(cd.NGLBV, 0.0);
        st.node_displacements.assign(static_cast<size_t>(cd.NUMNP) * 3, 0.0);

        // 요소마다 제 4절점과 제 법선으로 8절점을 만든다.
        // hex 규약: 코너 0 의 (p1-p0)x(p3-p0)·(p4-p0) 이 양수여야 뒤집히지 않는다.
        // 사각형 0→1→2→3 에서 n = (p1-p0)x(p2-p0) 로 잡고 상판을 +n 으로 밀면
        // 그 삼중곱이 양수가 된다.
        for (size_t e = 0; e < n_elem; ++e) {
            const auto& sh = mesh_in.shells[e];
            V3 q[4];
            for (int k = 0; k < 4; ++k) {
                const int32_t nid = (k < static_cast<int>(sh.node_ids.size()))
                                    ? sh.node_ids[k] : sh.node_ids.back();
                const size_t ni = static_cast<size_t>(nid - 1);
                q[k] = coordAt(mesh_in, si, ni);
            }
            V3 n = cross(sub(q[1], q[0]), sub(q[2], q[0]));
            const double L = len(n);
            if (L > 1e-20) { n.x /= L; n.y /= L; n.z /= L; }
            else { n = {0, 0, 1}; }

            for (int k = 0; k < 4; ++k) {
                const size_t lo = (e * 8 + k) * 3;
                const size_t hi = (e * 8 + 4 + k) * 3;
                st.node_displacements[lo + 0] = q[k].x;
                st.node_displacements[lo + 1] = q[k].y;
                st.node_displacements[lo + 2] = q[k].z;
                st.node_displacements[hi + 0] = q[k].x + n.x * thickness;
                st.node_displacements[hi + 1] = q[k].y + n.y * thickness;
                st.node_displacements[hi + 2] = q[k].z + n.z * thickness;
            }
        }

        // 두께셸 결과값은 넣지 않는다 (근거 없는 수치를 만들지 않기 위해).
        st.thick_shell_data.assign(static_cast<size_t>(cd.NELT) * cd.NV3DT, 0.0);
        states.push_back(std::move(st));
    }

    // 기하 섹션 = 첫 상태와 같게 맞춘다 (기준 형상 불일치 경고를 피한다)
    if (!states.empty()) {
        for (size_t i = 0; i < mesh.nodes.size(); ++i) {
            mesh.nodes[i].x = states[0].node_displacements[i * 3 + 0];
            mesh.nodes[i].y = states[0].node_displacements[i * 3 + 1];
            mesh.nodes[i].z = states[0].node_displacements[i * 3 + 2];
        }
    }

    std::filesystem::create_directories(out_dir);
    const std::string out_path = out_dir + "/d3plot";
    writer::D3plotWriter w(out_path);
    w.setControlData(cd);
    w.setMesh(mesh);
    w.setStates(states);
    if (w.write() != ErrorCode::SUCCESS) {
        std::printf("쓰기 실패: %s\n", out_path.c_str());
        return 1;
    }

    std::printf("출력: %s\n  절점 %d (원본 %zu x 2), 두께셸 %d, 상태 %zu, 두께 %g\n",
                out_path.c_str(), cd.NUMNP, n_node, cd.NELT, states.size(), thickness);
    return 0;
}
