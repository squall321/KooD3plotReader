#include "kood3plot/D3plotReader.hpp"
#include <iostream>
#include <iomanip>
#include <cmath>

int main(int argc, char* argv[]) {
    std::string filepath = "../results/d3plot";

    if (argc > 1) {
        filepath = argv[1];
    }

    std::cout << "D3plot 결과 데이터 검증 프로그램" << std::endl;
    std::cout << "================================" << std::endl;
    std::cout << "파일: " << filepath << std::endl << std::endl;

    // D3plot 파일 열기
    kood3plot::D3plotReader reader(filepath);
    auto err = reader.open();

    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "파일 열기 실패!" << std::endl;
        return 1;
    }

    std::cout << "✓ 파일 열기 성공" << std::endl;

    // Control data 가져오기
    auto cd = reader.get_control_data();

    std::cout << "\n[모델 정보]" << std::endl;
    std::cout << "  노드 수: " << cd.NUMNP << std::endl;
    std::cout << "  솔리드 요소 수: " << std::abs(cd.NEL8) << std::endl;
    std::cout << "  NDIM: " << cd.NDIM << " (좌표 차원)" << std::endl;
    std::cout << "  IU: " << cd.IU << " (변위 출력)" << std::endl;
    std::cout << "  IV: " << cd.IV << " (속도 출력)" << std::endl;
    std::cout << "  IA: " << cd.IA << " (가속도 출력)" << std::endl;
    std::cout << "  NV3D: " << cd.NV3D << " (솔리드 요소당 데이터 개수)" << std::endl;

    // State 데이터 읽기
    std::cout << "\n[State 데이터 읽기 중...]" << std::endl;
    auto states = reader.read_all_states();
    std::cout << "✓ " << states.size() << "개 time states 로드 완료" << std::endl;

    if (states.empty()) {
        std::cout << "\n⚠ State 데이터가 없습니다." << std::endl;
        return 0;
    }

    // 첫 번째와 마지막 state 분석
    std::cout << "\n════════════════════════════════════════" << std::endl;
    std::cout << "State 0 (초기 상태)" << std::endl;
    std::cout << "════════════════════════════════════════" << std::endl;

    const auto& state0 = states[0];
    std::cout << std::fixed << std::setprecision(6);
    std::cout << "시간: " << state0.time << " 초" << std::endl;

    // 노드 변위 분석
    if (!state0.node_displacements.empty() && cd.IU > 0) {
        std::cout << "\n[노드 변위 데이터]" << std::endl;
        std::cout << "  총 데이터 크기: " << state0.node_displacements.size() << std::endl;
        std::cout << "  노드당 값 개수: " << cd.NDIM << std::endl;

        int numnp = state0.node_displacements.size() / cd.NDIM;
        std::cout << "  계산된 노드 수: " << numnp << std::endl;

        // 처음 10개 노드의 변위 출력
        std::cout << "\n  처음 10개 노드 변위:" << std::endl;
        std::cout << "  Node    Ux           Uy           Uz           |U|" << std::endl;
        std::cout << "  ----    ----------   ----------   ----------   ----------" << std::endl;

        for (int i = 0; i < std::min(10, numnp); ++i) {
            double ux = state0.node_displacements[i * cd.NDIM + 0];
            double uy = state0.node_displacements[i * cd.NDIM + 1];
            double uz = state0.node_displacements[i * cd.NDIM + 2];
            double mag = std::sqrt(ux*ux + uy*uy + uz*uz);

            std::cout << "  " << std::setw(4) << (i+1) << "    "
                      << std::setw(10) << ux << "   "
                      << std::setw(10) << uy << "   "
                      << std::setw(10) << uz << "   "
                      << std::setw(10) << mag << std::endl;
        }

        // 최대 변위 찾기
        double max_disp = 0.0;
        int max_node = 0;
        for (int i = 0; i < numnp; ++i) {
            double ux = state0.node_displacements[i * cd.NDIM + 0];
            double uy = state0.node_displacements[i * cd.NDIM + 1];
            double uz = state0.node_displacements[i * cd.NDIM + 2];
            double mag = std::sqrt(ux*ux + uy*uy + uz*uz);
            if (mag > max_disp) {
                max_disp = mag;
                max_node = i + 1;
            }
        }

        std::cout << "\n  최대 변위: " << max_disp << " (노드 " << max_node << ")" << std::endl;
    } else {
        std::cout << "\n  ⚠ 변위 데이터 없음" << std::endl;
    }

    // 노드 속도 분석
    if (!state0.node_velocities.empty() && cd.IV > 0) {
        std::cout << "\n[노드 속도 데이터]" << std::endl;
        int numnp = state0.node_velocities.size() / cd.NDIM;

        std::cout << "  처음 5개 노드 속도:" << std::endl;
        std::cout << "  Node    Vx           Vy           Vz           |V|" << std::endl;
        std::cout << "  ----    ----------   ----------   ----------   ----------" << std::endl;

        for (int i = 0; i < std::min(5, numnp); ++i) {
            double vx = state0.node_velocities[i * cd.NDIM + 0];
            double vy = state0.node_velocities[i * cd.NDIM + 1];
            double vz = state0.node_velocities[i * cd.NDIM + 2];
            double mag = std::sqrt(vx*vx + vy*vy + vz*vz);

            std::cout << "  " << std::setw(4) << (i+1) << "    "
                      << std::setw(10) << vx << "   "
                      << std::setw(10) << vy << "   "
                      << std::setw(10) << vz << "   "
                      << std::setw(10) << mag << std::endl;
        }
    }

    // 노드 가속도 분석
    if (!state0.node_accelerations.empty() && cd.IA > 0) {
        std::cout << "\n[노드 가속도 데이터]" << std::endl;
        int numnp = state0.node_accelerations.size() / cd.NDIM;

        std::cout << "  처음 5개 노드 가속도:" << std::endl;
        std::cout << "  Node    Ax           Ay           Az           |A|" << std::endl;
        std::cout << "  ----    ----------   ----------   ----------   ----------" << std::endl;

        for (int i = 0; i < std::min(5, numnp); ++i) {
            double ax = state0.node_accelerations[i * cd.NDIM + 0];
            double ay = state0.node_accelerations[i * cd.NDIM + 1];
            double az = state0.node_accelerations[i * cd.NDIM + 2];
            double mag = std::sqrt(ax*ax + ay*ay + az*az);

            std::cout << "  " << std::setw(4) << (i+1) << "    "
                      << std::setw(10) << ax << "   "
                      << std::setw(10) << ay << "   "
                      << std::setw(10) << az << "   "
                      << std::setw(10) << mag << std::endl;
        }
    }

    // 솔리드 요소 응력 분석
    if (!state0.solid_data.empty()) {
        std::cout << "\n[솔리드 요소 응력 데이터]" << std::endl;
        std::cout << "  총 데이터 크기: " << state0.solid_data.size() << std::endl;
        std::cout << "  요소당 값 개수 (NV3D): " << cd.NV3D << std::endl;

        int num_solids = state0.solid_data.size() / cd.NV3D;
        std::cout << "  계산된 요소 수: " << num_solids << std::endl;

        // 처음 5개 요소의 응력 출력
        std::cout << "\n  처음 5개 요소 응력 (σx, σy, σz, τxy, τyz, τzx, ε_eff):" << std::endl;
        std::cout << "  Elem    σx           σy           σz           τxy          τyz          τzx          ε_eff" << std::endl;
        std::cout << "  ----    ----------   ----------   ----------   ----------   ----------   ----------   ----------" << std::endl;

        for (int i = 0; i < std::min(5, num_solids); ++i) {
            int offset = i * cd.NV3D;

            // LS-DYNA 솔리드 요소 데이터 순서:
            // 0: σx, 1: σy, 2: σz, 3: τxy, 4: τyz, 5: τzx, 6: effective plastic strain
            double sx = state0.solid_data[offset + 0];
            double sy = state0.solid_data[offset + 1];
            double sz = state0.solid_data[offset + 2];
            double sxy = state0.solid_data[offset + 3];
            double syz = state0.solid_data[offset + 4];
            double szx = state0.solid_data[offset + 5];
            double eff_strain = state0.solid_data[offset + 6];

            std::cout << "  " << std::setw(4) << (i+1) << "    "
                      << std::setw(10) << sx << "   "
                      << std::setw(10) << sy << "   "
                      << std::setw(10) << sz << "   "
                      << std::setw(10) << sxy << "   "
                      << std::setw(10) << syz << "   "
                      << std::setw(10) << szx << "   "
                      << std::setw(10) << eff_strain << std::endl;
        }

        // Von Mises 응력 계산
        std::cout << "\n  Von Mises 응력 (처음 5개 요소):" << std::endl;
        std::cout << "  Elem    σ_vm" << std::endl;
        std::cout << "  ----    ----------" << std::endl;

        for (int i = 0; i < std::min(5, num_solids); ++i) {
            int offset = i * cd.NV3D;
            double sx = state0.solid_data[offset + 0];
            double sy = state0.solid_data[offset + 1];
            double sz = state0.solid_data[offset + 2];
            double sxy = state0.solid_data[offset + 3];
            double syz = state0.solid_data[offset + 4];
            double szx = state0.solid_data[offset + 5];

            // Von Mises stress: √(0.5*((σx-σy)² + (σy-σz)² + (σz-σx)²) + 3*(τxy² + τyz² + τzx²))
            double s_vm = std::sqrt(0.5 * (
                (sx-sy)*(sx-sy) + (sy-sz)*(sy-sz) + (sz-sx)*(sz-sx)
            ) + 3.0 * (sxy*sxy + syz*syz + szx*szx));

            std::cout << "  " << std::setw(4) << (i+1) << "    "
                      << std::setw(10) << s_vm << std::endl;
        }

        // 최대 Von Mises 응력 찾기
        double max_vm = 0.0;
        int max_elem = 0;
        for (int i = 0; i < num_solids; ++i) {
            int offset = i * cd.NV3D;
            double sx = state0.solid_data[offset + 0];
            double sy = state0.solid_data[offset + 1];
            double sz = state0.solid_data[offset + 2];
            double sxy = state0.solid_data[offset + 3];
            double syz = state0.solid_data[offset + 4];
            double szx = state0.solid_data[offset + 5];

            double s_vm = std::sqrt(0.5 * (
                (sx-sy)*(sx-sy) + (sy-sz)*(sy-sz) + (sz-sx)*(sz-sx)
            ) + 3.0 * (sxy*sxy + syz*syz + szx*szx));

            if (s_vm > max_vm) {
                max_vm = s_vm;
                max_elem = i + 1;
            }
        }

        std::cout << "\n  최대 Von Mises 응력: " << max_vm << " (요소 " << max_elem << ")" << std::endl;
    } else {
        std::cout << "\n  ⚠ 솔리드 요소 데이터 없음" << std::endl;
    }

    // 마지막 state 분석
    if (states.size() > 1) {
        std::cout << "\n════════════════════════════════════════" << std::endl;
        std::cout << "State " << (states.size()-1) << " (마지막 상태)" << std::endl;
        std::cout << "════════════════════════════════════════" << std::endl;

        const auto& last_state = states[states.size()-1];
        std::cout << "시간: " << last_state.time << " 초" << std::endl;

        // 마지막 state의 최대 변위
        if (!last_state.node_displacements.empty()) {
            int numnp = last_state.node_displacements.size() / cd.NDIM;
            double max_disp = 0.0;
            int max_node = 0;

            for (int i = 0; i < numnp; ++i) {
                double ux = last_state.node_displacements[i * cd.NDIM + 0];
                double uy = last_state.node_displacements[i * cd.NDIM + 1];
                double uz = last_state.node_displacements[i * cd.NDIM + 2];
                double mag = std::sqrt(ux*ux + uy*uy + uz*uz);
                if (mag > max_disp) {
                    max_disp = mag;
                    max_node = i + 1;
                }
            }

            std::cout << "\n  최대 변위: " << max_disp << " (노드 " << max_node << ")" << std::endl;
        }

        // 마지막 state의 최대 Von Mises 응력
        if (!last_state.solid_data.empty()) {
            int num_solids = last_state.solid_data.size() / cd.NV3D;
            double max_vm = 0.0;
            int max_elem = 0;

            for (int i = 0; i < num_solids; ++i) {
                int offset = i * cd.NV3D;
                double sx = last_state.solid_data[offset + 0];
                double sy = last_state.solid_data[offset + 1];
                double sz = last_state.solid_data[offset + 2];
                double sxy = last_state.solid_data[offset + 3];
                double syz = last_state.solid_data[offset + 4];
                double szx = last_state.solid_data[offset + 5];

                double s_vm = std::sqrt(0.5 * (
                    (sx-sy)*(sx-sy) + (sy-sz)*(sy-sz) + (sz-sx)*(sz-sx)
                ) + 3.0 * (sxy*sxy + syz*syz + szx*szx));

                if (s_vm > max_vm) {
                    max_vm = s_vm;
                    max_elem = i + 1;
                }
            }

            std::cout << "  최대 Von Mises 응력: " << max_vm << " (요소 " << max_elem << ")" << std::endl;
        }
    }

    // Global variables
    std::cout << "\n[Global Variables (처음 10개)]" << std::endl;
    if (!state0.global_vars.empty()) {
        std::cout << "  Kinetic Energy (KE): " << state0.global_vars[0] << std::endl;
        if (state0.global_vars.size() > 1)
            std::cout << "  Internal Energy (IE): " << state0.global_vars[1] << std::endl;
        if (state0.global_vars.size() > 2)
            std::cout << "  Total Energy (TE): " << state0.global_vars[2] << std::endl;

        std::cout << "\n  전체 " << state0.global_vars.size() << "개 global variables 로드됨" << std::endl;
    }

    std::cout << "\n✓ 데이터 검증 완료!" << std::endl;

    reader.close();
    return 0;
}
