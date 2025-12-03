#include "kood3plot/D3plotReader.hpp"
#include <iostream>
#include <iomanip>
#include <cmath>

int main(int argc, char* argv[]) {
    std::string filepath = "../results/d3plot";
    if (argc > 1) {
        filepath = argv[1];
    }

    std::cout << "응력/변형률 데이터 출력 프로그램\n";
    std::cout << "==============================\n\n";

    // 파일 열기
    kood3plot::D3plotReader reader(filepath);
    auto err = reader.open();
    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "파일 열기 실패!\n";
        return 1;
    }

    auto cd = reader.get_control_data();
    auto mesh = reader.read_mesh();
    auto states = reader.read_all_states();

    if (states.empty()) {
        std::cerr << "State 데이터가 없습니다!\n";
        return 1;
    }

    // 마지막 state 사용
    const auto& state = states.back();

    std::cout << "파일: " << filepath << "\n";
    std::cout << "Time: " << std::fixed << std::setprecision(6) << state.time << " 초\n";
    std::cout << "총 노드 수: " << cd.NUMNP << "\n";
    std::cout << "총 요소 수: " << std::abs(cd.NEL8) << "\n\n";

    // ========================================
    // 1. 노드 변위 데이터 (처음 20개)
    // ========================================
    std::cout << std::string(100, '=') << "\n";
    std::cout << "노드 변위 데이터 (Node Displacements)\n";
    std::cout << std::string(100, '=') << "\n\n";

    if (!state.node_displacements.empty()) {
        std::cout << "Node ID   Ux            Uy            Uz            |U|           Vx            Vy            Vz\n";
        std::cout << "-------   -----------   -----------   -----------   -----------   -----------   -----------   -----------\n";

        int show_nodes = std::min(20, cd.NUMNP);
        bool has_velocity = !state.node_velocities.empty();

        for (int i = 0; i < show_nodes; ++i) {
            int idx = i * cd.NDIM;

            double ux = state.node_displacements[idx + 0];
            double uy = state.node_displacements[idx + 1];
            double uz = state.node_displacements[idx + 2];
            double mag = std::sqrt(ux*ux + uy*uy + uz*uz);

            std::cout << std::setw(7) << (i + 1) << "   "
                      << std::setw(11) << ux << "   "
                      << std::setw(11) << uy << "   "
                      << std::setw(11) << uz << "   "
                      << std::setw(11) << mag;

            if (has_velocity) {
                double vx = state.node_velocities[idx + 0];
                double vy = state.node_velocities[idx + 1];
                double vz = state.node_velocities[idx + 2];
                std::cout << "   " << std::setw(11) << vx
                          << "   " << std::setw(11) << vy
                          << "   " << std::setw(11) << vz;
            }

            std::cout << "\n";
        }
    } else {
        std::cout << "변위 데이터 없음 (IU=0)\n";
    }

    // ========================================
    // 2. 요소 응력/변형률 데이터 (처음 30개)
    // ========================================
    std::cout << "\n\n" << std::string(100, '=') << "\n";
    std::cout << "요소 응력/변형률 데이터 (Element Stress/Strain)\n";
    std::cout << std::string(100, '=') << "\n\n";

    if (!state.solid_data.empty()) {
        int nv3d = cd.NV3D;
        int num_solids = std::abs(cd.NEL8);
        int show_elements = std::min(30, num_solids);

        std::cout << "요소 번호별 응력 텐서 성분:\n\n";
        std::cout << "Elem ID   σx            σy            σz            τxy           τyz           τzx           ε_eff\n";
        std::cout << "-------   -----------   -----------   -----------   -----------   -----------   -----------   -----------\n";

        for (int i = 0; i < show_elements; ++i) {
            int offset = i * nv3d;

            double sx = state.solid_data[offset + 0];
            double sy = state.solid_data[offset + 1];
            double sz = state.solid_data[offset + 2];
            double txy = state.solid_data[offset + 3];
            double tyz = state.solid_data[offset + 4];
            double tzx = state.solid_data[offset + 5];
            double eff_pstrain = state.solid_data[offset + 6];

            std::cout << std::setw(7) << (i + 1) << "   "
                      << std::setw(11) << sx << "   "
                      << std::setw(11) << sy << "   "
                      << std::setw(11) << sz << "   "
                      << std::setw(11) << txy << "   "
                      << std::setw(11) << tyz << "   "
                      << std::setw(11) << tzx << "   "
                      << std::setw(11) << eff_pstrain << "\n";
        }

        // Von Mises 응력 계산 및 출력
        std::cout << "\n\nVon Mises 응력 (처음 30개 요소):\n\n";
        std::cout << "Elem ID   σ_vm          Mean σ        Max |τ|\n";
        std::cout << "-------   -----------   -----------   -----------\n";

        for (int i = 0; i < show_elements; ++i) {
            int offset = i * nv3d;

            double sx = state.solid_data[offset + 0];
            double sy = state.solid_data[offset + 1];
            double sz = state.solid_data[offset + 2];
            double txy = state.solid_data[offset + 3];
            double tyz = state.solid_data[offset + 4];
            double tzx = state.solid_data[offset + 5];

            // Von Mises
            double s_vm = std::sqrt(0.5 * (
                (sx - sy) * (sx - sy) +
                (sy - sz) * (sy - sz) +
                (sz - sx) * (sz - sx)
            ) + 3.0 * (txy*txy + tyz*tyz + tzx*tzx));

            // Mean stress (Hydrostatic pressure)
            double mean_stress = (sx + sy + sz) / 3.0;

            // Maximum shear stress
            double max_shear = std::max(std::abs(txy), std::max(std::abs(tyz), std::abs(tzx)));

            std::cout << std::setw(7) << (i + 1) << "   "
                      << std::setw(11) << s_vm << "   "
                      << std::setw(11) << mean_stress << "   "
                      << std::setw(11) << max_shear << "\n";
        }

    } else {
        std::cout << "응력 데이터 없음\n";
    }

    // ========================================
    // 3. 최대값 찾기
    // ========================================
    std::cout << "\n\n" << std::string(100, '=') << "\n";
    std::cout << "최대값 통계\n";
    std::cout << std::string(100, '=') << "\n\n";

    // 최대 변위
    if (!state.node_displacements.empty()) {
        double max_disp = 0.0;
        int max_node = 0;
        double max_ux = 0, max_uy = 0, max_uz = 0;

        for (int i = 0; i < cd.NUMNP; ++i) {
            int idx = i * cd.NDIM;
            double ux = state.node_displacements[idx + 0];
            double uy = state.node_displacements[idx + 1];
            double uz = state.node_displacements[idx + 2];
            double mag = std::sqrt(ux*ux + uy*uy + uz*uz);

            if (mag > max_disp) {
                max_disp = mag;
                max_node = i + 1;
                max_ux = ux;
                max_uy = uy;
                max_uz = uz;
            }
        }

        std::cout << "[최대 변위]\n";
        std::cout << "  노드 번호: " << max_node << "\n";
        std::cout << "  |U| = " << max_disp << "\n";
        std::cout << "  Ux = " << max_ux << ", Uy = " << max_uy << ", Uz = " << max_uz << "\n\n";
    }

    // 최대 Von Mises 응력
    if (!state.solid_data.empty()) {
        double max_vm = 0.0;
        int max_elem = 0;
        double max_sx = 0, max_sy = 0, max_sz = 0;
        double max_txy = 0, max_tyz = 0, max_tzx = 0;

        int nv3d = cd.NV3D;
        int num_solids = std::abs(cd.NEL8);

        for (int i = 0; i < num_solids; ++i) {
            int offset = i * nv3d;

            double sx = state.solid_data[offset + 0];
            double sy = state.solid_data[offset + 1];
            double sz = state.solid_data[offset + 2];
            double txy = state.solid_data[offset + 3];
            double tyz = state.solid_data[offset + 4];
            double tzx = state.solid_data[offset + 5];

            double s_vm = std::sqrt(0.5 * (
                (sx - sy) * (sx - sy) +
                (sy - sz) * (sy - sz) +
                (sz - sx) * (sz - sx)
            ) + 3.0 * (txy*txy + tyz*tyz + tzx*tzx));

            if (s_vm > max_vm) {
                max_vm = s_vm;
                max_elem = i + 1;
                max_sx = sx;
                max_sy = sy;
                max_sz = sz;
                max_txy = txy;
                max_tyz = tyz;
                max_tzx = tzx;
            }
        }

        std::cout << "[최대 Von Mises 응력]\n";
        std::cout << "  요소 번호: " << max_elem << "\n";
        std::cout << "  σ_vm = " << max_vm << "\n";
        std::cout << "  응력 성분:\n";
        std::cout << "    σx  = " << max_sx << "\n";
        std::cout << "    σy  = " << max_sy << "\n";
        std::cout << "    σz  = " << max_sz << "\n";
        std::cout << "    τxy = " << max_txy << "\n";
        std::cout << "    τyz = " << max_tyz << "\n";
        std::cout << "    τzx = " << max_tzx << "\n";
    }

    std::cout << "\n✓ 완료!\n";
    reader.close();

    return 0;
}