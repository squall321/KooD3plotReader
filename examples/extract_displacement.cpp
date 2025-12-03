#include "kood3plot/D3plotReader.hpp"
#include <iostream>
#include <iomanip>
#include <fstream>
#include <cmath>
#include <algorithm>

// 변위 크기 계산
double calculate_magnitude(double ux, double uy, double uz) {
    return std::sqrt(ux*ux + uy*uy + uz*uz);
}

// 예제 1: 특정 state의 모든 노드 변위 출력
void example1_all_nodes(kood3plot::D3plotReader& reader) {
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "예제 1: 특정 State의 모든 노드 변위 출력\n";
    std::cout << std::string(80, '=') << "\n";

    auto cd = reader.get_control_data();
    auto states = reader.read_all_states();

    if (states.empty()) {
        std::cout << "State 데이터가 없습니다.\n";
        return;
    }

    // 마지막 state 사용
    const auto& state = states.back();
    int ndim = cd.NDIM;
    int numnp = cd.NUMNP;

    std::cout << "Time: " << state.time << " 초\n";
    std::cout << "총 " << numnp << "개 노드\n";
    std::cout << "차원: " << ndim << "\n\n";

    if (state.node_displacements.empty()) {
        std::cout << "변위 데이터가 없습니다 (IU=0)\n";
        return;
    }

    // 처음 15개 노드만 출력
    int show_count = std::min(15, numnp);
    std::cout << "처음 " << show_count << "개 노드의 변위:\n\n";

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "Node    Ux          Uy          Uz          |U|\n";
    std::cout << "----    ----------  ----------  ----------  ----------\n";

    for (int i = 0; i < show_count; ++i) {
        double ux = state.node_displacements[i * ndim + 0];
        double uy = state.node_displacements[i * ndim + 1];
        double uz = state.node_displacements[i * ndim + 2];
        double mag = calculate_magnitude(ux, uy, uz);

        std::cout << std::setw(4) << (i + 1) << "    "
                  << std::setw(10) << ux << "  "
                  << std::setw(10) << uy << "  "
                  << std::setw(10) << uz << "  "
                  << std::setw(10) << mag << "\n";
    }
}

// 예제 2: 특정 노드의 변위 상세 정보
void example2_specific_node(kood3plot::D3plotReader& reader, int node_id) {
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "예제 2: 특정 노드의 변위 상세 정보\n";
    std::cout << std::string(80, '=') << "\n";

    auto cd = reader.get_control_data();
    auto states = reader.read_all_states();

    if (states.empty()) {
        std::cout << "State 데이터가 없습니다.\n";
        return;
    }

    const auto& state = states.back();
    int ndim = cd.NDIM;
    int numnp = cd.NUMNP;

    if (node_id < 1 || node_id > numnp) {
        std::cout << "잘못된 노드 번호: " << node_id << "\n";
        return;
    }

    if (state.node_displacements.empty()) {
        std::cout << "변위 데이터가 없습니다 (IU=0)\n";
        return;
    }

    std::cout << "노드 번호: " << node_id << "\n";
    std::cout << "Time: " << state.time << " 초\n\n";

    int idx = (node_id - 1) * ndim;
    double ux = state.node_displacements[idx + 0];
    double uy = state.node_displacements[idx + 1];
    double uz = state.node_displacements[idx + 2];
    double mag = calculate_magnitude(ux, uy, uz);

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "[변위 벡터]\n";
    std::cout << "  Ux = " << std::setw(12) << ux << " (X 방향)\n";
    std::cout << "  Uy = " << std::setw(12) << uy << " (Y 방향)\n";
    std::cout << "  Uz = " << std::setw(12) << uz << " (Z 방향)\n";
    std::cout << "  |U| = " << std::setw(12) << mag << " (크기)\n\n";

    // 속도 정보
    if (!state.node_velocities.empty()) {
        double vx = state.node_velocities[idx + 0];
        double vy = state.node_velocities[idx + 1];
        double vz = state.node_velocities[idx + 2];
        double vmag = calculate_magnitude(vx, vy, vz);

        std::cout << "[속도 벡터]\n";
        std::cout << "  Vx = " << std::setw(12) << vx << "\n";
        std::cout << "  Vy = " << std::setw(12) << vy << "\n";
        std::cout << "  Vz = " << std::setw(12) << vz << "\n";
        std::cout << "  |V| = " << std::setw(12) << vmag << "\n\n";
    }

    // 가속도 정보
    if (!state.node_accelerations.empty()) {
        double ax = state.node_accelerations[idx + 0];
        double ay = state.node_accelerations[idx + 1];
        double az = state.node_accelerations[idx + 2];
        double amag = calculate_magnitude(ax, ay, az);

        std::cout << "[가속도 벡터]\n";
        std::cout << "  Ax = " << std::setw(12) << ax << "\n";
        std::cout << "  Ay = " << std::setw(12) << ay << "\n";
        std::cout << "  Az = " << std::setw(12) << az << "\n";
        std::cout << "  |A| = " << std::setw(12) << amag << "\n";
    }
}

// 예제 3: 시간에 따른 변위 이력 (Time History)
void example3_time_history(kood3plot::D3plotReader& reader, int node_id) {
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "예제 3: 시간에 따른 변위 이력 (Time History)\n";
    std::cout << std::string(80, '=') << "\n";

    auto cd = reader.get_control_data();
    auto states = reader.read_all_states();

    if (states.empty()) {
        std::cout << "State 데이터가 없습니다.\n";
        return;
    }

    int ndim = cd.NDIM;
    int numnp = cd.NUMNP;

    if (node_id < 1 || node_id > numnp) {
        std::cout << "잘못된 노드 번호: " << node_id << "\n";
        return;
    }

    std::cout << "노드 번호: " << node_id << "\n";
    std::cout << "총 " << states.size() << "개 time states\n\n";

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "State   Time        Ux          Uy          Uz          |U|\n";
    std::cout << "-----   ----------  ----------  ----------  ----------  ----------\n";

    int idx = (node_id - 1) * ndim;

    // 5개씩 건너뛰어 출력
    for (size_t i = 0; i < states.size(); i += 5) {
        const auto& state = states[i];

        if (state.node_displacements.empty()) continue;

        double ux = state.node_displacements[idx + 0];
        double uy = state.node_displacements[idx + 1];
        double uz = state.node_displacements[idx + 2];
        double mag = calculate_magnitude(ux, uy, uz);

        std::cout << std::setw(5) << i << "   "
                  << std::setw(10) << state.time << "  "
                  << std::setw(10) << ux << "  "
                  << std::setw(10) << uy << "  "
                  << std::setw(10) << uz << "  "
                  << std::setw(10) << mag << "\n";
    }

    // 마지막 state도 출력
    if ((states.size() - 1) % 5 != 0) {
        const auto& state = states.back();
        if (!state.node_displacements.empty()) {
            double ux = state.node_displacements[idx + 0];
            double uy = state.node_displacements[idx + 1];
            double uz = state.node_displacements[idx + 2];
            double mag = calculate_magnitude(ux, uy, uz);

            std::cout << std::setw(5) << (states.size() - 1) << "   "
                      << std::setw(10) << state.time << "  "
                      << std::setw(10) << ux << "  "
                      << std::setw(10) << uy << "  "
                      << std::setw(10) << uz << "  "
                      << std::setw(10) << mag << "\n";
        }
    }
}

// 예제 4: 최대 변위 노드 찾기
void example4_find_max_displacement(kood3plot::D3plotReader& reader) {
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "예제 4: 최대 변위 노드 찾기\n";
    std::cout << std::string(80, '=') << "\n";

    auto cd = reader.get_control_data();
    auto states = reader.read_all_states();

    if (states.empty()) {
        std::cout << "State 데이터가 없습니다.\n";
        return;
    }

    const auto& state = states.back();
    int ndim = cd.NDIM;
    int numnp = cd.NUMNP;

    if (state.node_displacements.empty()) {
        std::cout << "변위 데이터가 없습니다 (IU=0)\n";
        return;
    }

    std::cout << "Time: " << state.time << " 초\n";
    std::cout << "총 " << numnp << "개 노드 검색 중...\n\n";

    double max_disp = 0.0;
    int max_node = 0;
    double max_ux = 0.0, max_uy = 0.0, max_uz = 0.0;

    // 모든 노드 순회
    for (int i = 0; i < numnp; ++i) {
        int idx = i * ndim;
        double ux = state.node_displacements[idx + 0];
        double uy = state.node_displacements[idx + 1];
        double uz = state.node_displacements[idx + 2];
        double mag = calculate_magnitude(ux, uy, uz);

        if (mag > max_disp) {
            max_disp = mag;
            max_node = i + 1;
            max_ux = ux;
            max_uy = uy;
            max_uz = uz;
        }
    }

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "[최대 변위]\n";
    std::cout << "  노드 번호: " << max_node << "\n";
    std::cout << "  |U| = " << max_disp << "\n\n";

    std::cout << "[변위 성분]\n";
    std::cout << "  Ux = " << max_ux << "\n";
    std::cout << "  Uy = " << max_uy << "\n";
    std::cout << "  Uz = " << max_uz << "\n";
}

// 예제 5: 변위 데이터를 CSV 파일로 내보내기
void example5_export_to_csv(kood3plot::D3plotReader& reader, const std::string& filename) {
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "예제 5: 변위 데이터 CSV 파일로 내보내기\n";
    std::cout << std::string(80, '=') << "\n";

    auto cd = reader.get_control_data();
    auto states = reader.read_all_states();

    if (states.empty()) {
        std::cout << "State 데이터가 없습니다.\n";
        return;
    }

    // 마지막 state 사용
    const auto& state = states.back();
    int ndim = cd.NDIM;
    int numnp = cd.NUMNP;

    if (state.node_displacements.empty()) {
        std::cout << "변위 데이터가 없습니다 (IU=0)\n";
        return;
    }

    std::ofstream csv_file(filename);
    if (!csv_file) {
        std::cerr << "파일 열기 실패: " << filename << "\n";
        return;
    }

    // CSV 헤더
    csv_file << "Node,Ux,Uy,Uz,Magnitude,Vx,Vy,Vz,V_Magnitude,Ax,Ay,Az,A_Magnitude\n";

    bool has_velocity = !state.node_velocities.empty();
    bool has_acceleration = !state.node_accelerations.empty();

    // 모든 노드 데이터 쓰기
    csv_file << std::fixed << std::setprecision(6);
    for (int i = 0; i < numnp; ++i) {
        int idx = i * ndim;

        double ux = state.node_displacements[idx + 0];
        double uy = state.node_displacements[idx + 1];
        double uz = state.node_displacements[idx + 2];
        double umag = calculate_magnitude(ux, uy, uz);

        csv_file << (i + 1) << ","
                 << ux << "," << uy << "," << uz << "," << umag;

        if (has_velocity) {
            double vx = state.node_velocities[idx + 0];
            double vy = state.node_velocities[idx + 1];
            double vz = state.node_velocities[idx + 2];
            double vmag = calculate_magnitude(vx, vy, vz);
            csv_file << "," << vx << "," << vy << "," << vz << "," << vmag;
        } else {
            csv_file << ",0,0,0,0";
        }

        if (has_acceleration) {
            double ax = state.node_accelerations[idx + 0];
            double ay = state.node_accelerations[idx + 1];
            double az = state.node_accelerations[idx + 2];
            double amag = calculate_magnitude(ax, ay, az);
            csv_file << "," << ax << "," << ay << "," << az << "," << amag;
        } else {
            csv_file << ",0,0,0,0";
        }

        csv_file << "\n";
    }

    csv_file.close();
    std::cout << "✓ CSV 파일 저장 완료: " << filename << "\n";
    std::cout << "  총 " << numnp << "개 노드 데이터 저장\n";
}

// 예제 6: 변위장 시각화용 데이터 (특정 평면)
void example6_slice_data(kood3plot::D3plotReader& reader, double z_plane) {
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "예제 6: 특정 Z 평면의 변위 데이터\n";
    std::cout << std::string(80, '=') << "\n";

    auto cd = reader.get_control_data();
    auto mesh = reader.read_mesh();
    auto states = reader.read_all_states();

    if (states.empty()) {
        std::cout << "State 데이터가 없습니다.\n";
        return;
    }

    const auto& state = states.back();
    int ndim = cd.NDIM;

    if (state.node_displacements.empty()) {
        std::cout << "변위 데이터가 없습니다.\n";
        return;
    }

    std::cout << "Z 평면: " << z_plane << "\n";
    std::cout << "허용 오차: ±0.1\n\n";

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "Node    X           Y           Z           Ux          Uy          Uz\n";
    std::cout << "----    ----------  ----------  ----------  ----------  ----------  ----------\n";

    int count = 0;
    for (size_t i = 0; i < mesh.nodes.size(); ++i) {
        const auto& node = mesh.nodes[i];

        // Z 좌표가 평면에 가까운 노드만 선택
        if (std::abs(node.z - z_plane) < 0.1) {
            int idx = i * ndim;
            double ux = state.node_displacements[idx + 0];
            double uy = state.node_displacements[idx + 1];
            double uz = state.node_displacements[idx + 2];

            std::cout << std::setw(4) << node.id << "    "
                      << std::setw(10) << node.x << "  "
                      << std::setw(10) << node.y << "  "
                      << std::setw(10) << node.z << "  "
                      << std::setw(10) << ux << "  "
                      << std::setw(10) << uy << "  "
                      << std::setw(10) << uz << "\n";

            count++;
            if (count >= 20) break;  // 처음 20개만
        }
    }

    std::cout << "\n총 검색된 노드: " << count << "개\n";
}

int main(int argc, char* argv[]) {
    std::string filepath = "../results/d3plot";

    if (argc > 1) {
        filepath = argv[1];
    }

    std::cout << "변위 데이터 추출 예제 프로그램\n";
    std::cout << "============================\n";
    std::cout << "파일: " << filepath << "\n";

    // D3plot 파일 열기
    kood3plot::D3plotReader reader(filepath);
    auto err = reader.open();

    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "파일 열기 실패: " << kood3plot::error_to_string(err) << "\n";
        return 1;
    }

    std::cout << "✓ 파일 열기 성공\n";

    // 각 예제 실행
    example1_all_nodes(reader);
    example2_specific_node(reader, 1000);    // 1000번 노드
    example3_time_history(reader, 1000);     // 1000번 노드의 시간 이력
    example4_find_max_displacement(reader);
    example5_export_to_csv(reader, "displacement_output.csv");
    example6_slice_data(reader, 0.0);        // Z=0 평면

    reader.close();
    std::cout << "\n✓ 모든 예제 완료!\n";

    return 0;
}
