/**
 * @file max_displacement_history.cpp
 * @brief 파트별 시간 스텝별 최대 변위 이력 출력
 */

#include "kood3plot/D3plotReader.hpp"
#include <iostream>
#include <iomanip>
#include <cmath>
#include <fstream>
#include <map>
#include <set>

int main(int argc, char* argv[]) {
    std::string filepath = "results/d3plot";
    if (argc > 1) filepath = argv[1];

    std::cout << "=== 파트별 시간 스텝별 최대 변위 이력 ===\n\n";
    std::cout << "파일: " << filepath << "\n\n";

    kood3plot::D3plotReader reader(filepath);
    auto err = reader.open();
    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "파일 열기 실패\n";
        return 1;
    }

    auto cd = reader.get_control_data();
    int ndim = (cd.NDIM >= 4) ? 3 : cd.NDIM;
    int numnp = cd.NUMNP;

    std::cout << "노드 수: " << numnp << "\n";
    std::cout << "IU=" << cd.IU << " (변위)\n";

    if (cd.IU == 0) {
        std::cerr << "변위 데이터가 없습니다 (IU=0)\n";
        return 1;
    }

    // Mesh 읽기 (노드-파트 매핑 구축용)
    auto mesh = reader.read_mesh();
    std::cout << "Solid 요소 수: " << mesh.num_solids << "\n";
    std::cout << "Shell 요소 수: " << mesh.num_shells << "\n\n";

    // 노드 -> 파트 ID 매핑 구축
    std::map<int, int> node_to_part;  // node_index -> part_id
    std::set<int> part_ids;

    // Solid 요소에서 노드-파트 매핑
    for (size_t i = 0; i < mesh.solids.size(); ++i) {
        int part_id = mesh.solid_parts.empty() ? 1 : mesh.solid_parts[i];
        part_ids.insert(part_id);
        for (int node_id : mesh.solids[i].node_ids) {
            node_to_part[node_id - 1] = part_id;  // 0-indexed
        }
    }

    // Shell 요소에서 노드-파트 매핑
    for (size_t i = 0; i < mesh.shells.size(); ++i) {
        int part_id = mesh.shell_parts.empty() ? 1 : mesh.shell_parts[i];
        part_ids.insert(part_id);
        for (int node_id : mesh.shells[i].node_ids) {
            node_to_part[node_id - 1] = part_id;  // 0-indexed
        }
    }

    std::cout << "파트 수: " << part_ids.size() << "\n";
    std::cout << "파트 ID: ";
    for (int pid : part_ids) std::cout << pid << " ";
    std::cout << "\n\n";

    // 모든 state 읽기
    auto states = reader.read_all_states();
    std::cout << "총 " << states.size() << " 개 타임스텝\n\n";

    // 파트별 CSV 파일
    std::ofstream csv("max_displacement_by_part.csv");
    csv << "State,Time";
    for (int pid : part_ids) {
        csv << ",Part" << pid << "_MaxDisp,Part" << pid << "_MaxNode";
    }
    csv << "\n";

    // 파트별 전역 최대값 추적
    std::map<int, double> global_max_disp;
    std::map<int, int> global_max_state;
    std::map<int, int> global_max_node;
    std::map<int, double> global_max_time;
    for (int pid : part_ids) {
        global_max_disp[pid] = 0.0;
        global_max_state[pid] = 0;
        global_max_node[pid] = 0;
        global_max_time[pid] = 0.0;
    }

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "State   Time        ";
    for (int pid : part_ids) {
        std::cout << "Part" << std::setw(2) << pid << "_MaxDisp  ";
    }
    std::cout << "\n";
    std::cout << "------  ----------  ";
    for (size_t i = 0; i < part_ids.size(); ++i) {
        std::cout << "--------------  ";
    }
    std::cout << "\n";

    for (size_t s = 0; s < states.size(); ++s) {
        const auto& state = states[s];
        if (state.node_displacements.empty()) continue;

        // 파트별 최대 변위 계산
        std::map<int, double> part_max_disp;
        std::map<int, int> part_max_node;
        for (int pid : part_ids) {
            part_max_disp[pid] = 0.0;
            part_max_node[pid] = 0;
        }

        for (int i = 0; i < numnp; ++i) {
            auto it = node_to_part.find(i);
            if (it == node_to_part.end()) continue;

            int part_id = it->second;
            int idx = i * ndim;
            double ux = state.node_displacements[idx + 0];
            double uy = state.node_displacements[idx + 1];
            double uz = state.node_displacements[idx + 2];
            double mag = std::sqrt(ux*ux + uy*uy + uz*uz);

            if (mag > part_max_disp[part_id]) {
                part_max_disp[part_id] = mag;
                part_max_node[part_id] = i + 1;
            }
        }

        // 전역 최대값 업데이트
        for (int pid : part_ids) {
            if (part_max_disp[pid] > global_max_disp[pid]) {
                global_max_disp[pid] = part_max_disp[pid];
                global_max_state[pid] = s;
                global_max_node[pid] = part_max_node[pid];
                global_max_time[pid] = state.time;
            }
        }

        // 출력 (매 100번째 또는 처음/마지막)
        if (s % 100 == 0 || s == states.size() - 1 || s < 3) {
            std::cout << std::setw(6) << s << "  "
                      << std::setw(10) << state.time << "  ";
            for (int pid : part_ids) {
                std::cout << std::setw(14) << part_max_disp[pid] << "  ";
            }
            std::cout << "\n";
        }

        // CSV 저장
        csv << s << "," << state.time;
        for (int pid : part_ids) {
            csv << "," << part_max_disp[pid] << "," << part_max_node[pid];
        }
        csv << "\n";
    }

    csv.close();

    // 파트별 전역 최대값 출력
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "파트별 전역 최대 변위 결과:\n";
    std::cout << std::string(80, '=') << "\n";
    std::cout << std::setw(8) << "Part" << std::setw(12) << "Max_Disp"
              << std::setw(10) << "State" << std::setw(14) << "Time"
              << std::setw(10) << "Node" << "\n";
    std::cout << std::string(60, '-') << "\n";

    for (int pid : part_ids) {
        std::cout << std::setw(8) << pid
                  << std::setw(12) << global_max_disp[pid]
                  << std::setw(10) << global_max_state[pid]
                  << std::setw(14) << global_max_time[pid]
                  << std::setw(10) << global_max_node[pid] << "\n";
    }
    std::cout << std::string(80, '=') << "\n";

    std::cout << "\n✓ CSV 저장: max_displacement_by_part.csv\n";

    return 0;
}
