#include "kood3plot/D3plotReader.hpp"
#include <iostream>
#include <iomanip>
#include <fstream>
#include <cmath>

// 전체 데이터 추출 및 저장 클래스
class D3plotDataExtractor {
private:
    kood3plot::D3plotReader& reader_;
    kood3plot::data::ControlData cd_;
    kood3plot::data::Mesh mesh_;
    std::vector<kood3plot::data::StateData> states_;

public:
    D3plotDataExtractor(kood3plot::D3plotReader& reader)
        : reader_(reader) {
        cd_ = reader_.get_control_data();
        mesh_ = reader_.read_mesh();
        states_ = reader_.read_all_states();
    }

    // 1. 메쉬 정보 출력
    void print_mesh_info() {
        std::cout << "\n" << std::string(80, '=') << "\n";
        std::cout << "메쉬 정보\n";
        std::cout << std::string(80, '=') << "\n";

        std::cout << "노드 수: " << mesh_.get_num_nodes() << "\n";
        std::cout << "총 요소 수: " << mesh_.get_num_elements() << "\n";
        std::cout << "  - Solid 요소: " << mesh_.num_solids << "\n";
        std::cout << "  - Thick shell 요소: " << mesh_.num_thick_shells << "\n";
        std::cout << "  - Beam 요소: " << mesh_.num_beams << "\n";
        std::cout << "  - Shell 요소: " << mesh_.num_shells << "\n";
    }

    // 2. Control data 상세 정보
    void print_control_data() {
        std::cout << "\n" << std::string(80, '=') << "\n";
        std::cout << "Control Data 상세 정보\n";
        std::cout << std::string(80, '=') << "\n";

        std::cout << "[모델 크기]\n";
        std::cout << "  NUMNP  (노드 수): " << cd_.NUMNP << "\n";
        std::cout << "  NEL8   (Solid): " << std::abs(cd_.NEL8) << "\n";
        std::cout << "  NELT   (Thick shell): " << cd_.NELT << "\n";
        std::cout << "  NEL2   (Beam): " << cd_.NEL2 << "\n";
        std::cout << "  NEL4   (Shell): " << cd_.NEL4 << "\n\n";

        std::cout << "[출력 플래그]\n";
        std::cout << "  IT (Temperature): " << cd_.IT << "\n";
        std::cout << "  IU (Displacement): " << cd_.IU << "\n";
        std::cout << "  IV (Velocity): " << cd_.IV << "\n";
        std::cout << "  IA (Acceleration): " << cd_.IA << "\n";
        std::cout << "  ISTRN (Strain): " << cd_.ISTRN << "\n\n";

        std::cout << "[State 데이터 크기]\n";
        std::cout << "  NGLBV (Global vars): " << cd_.NGLBV << "\n";
        std::cout << "  NND (Nodal data words): " << cd_.NND << "\n";
        std::cout << "  NV3D (Solid data): " << cd_.NV3D << "\n";
        std::cout << "  NV3DT (Thick shell data): " << cd_.NV3DT << "\n";
        std::cout << "  NV1D (Beam data): " << cd_.NV1D << "\n";
        std::cout << "  NV2D (Shell data): " << cd_.NV2D << "\n";
    }

    // 3. Time states 요약
    void print_time_states_summary() {
        std::cout << "\n" << std::string(80, '=') << "\n";
        std::cout << "Time States 요약\n";
        std::cout << std::string(80, '=') << "\n";

        std::cout << "총 " << states_.size() << "개 time states\n\n";

        if (states_.empty()) return;

        std::cout << std::fixed << std::setprecision(6);
        std::cout << "State   Time\n";
        std::cout << "-----   ----------\n";

        // 처음 5개
        for (size_t i = 0; i < std::min(size_t(5), states_.size()); ++i) {
            std::cout << std::setw(5) << i << "   " << states_[i].time << "\n";
        }

        if (states_.size() > 10) {
            std::cout << "  ...\n";
        }

        // 마지막 5개
        if (states_.size() > 5) {
            size_t start = states_.size() > 10 ? states_.size() - 5 : 5;
            for (size_t i = start; i < states_.size(); ++i) {
                std::cout << std::setw(5) << i << "   " << states_[i].time << "\n";
            }
        }
    }

    // 4. 메쉬를 CSV로 저장 (노드 좌표)
    void export_mesh_nodes_csv(const std::string& filename) {
        std::cout << "\n메쉬 노드 데이터를 CSV로 저장 중...\n";

        std::ofstream file(filename);
        if (!file) {
            std::cerr << "파일 열기 실패: " << filename << "\n";
            return;
        }

        file << "Node_ID,X,Y,Z\n";
        file << std::fixed << std::setprecision(6);

        for (const auto& node : mesh_.nodes) {
            file << node.id << ","
                 << node.x << ","
                 << node.y << ","
                 << node.z << "\n";
        }

        file.close();
        std::cout << "✓ 저장 완료: " << filename << " (" << mesh_.nodes.size() << " nodes)\n";
    }

    // 5. Solid 요소 연결성을 CSV로 저장
    void export_solid_connectivity_csv(const std::string& filename) {
        std::cout << "\nSolid 요소 연결성을 CSV로 저장 중...\n";

        std::ofstream file(filename);
        if (!file) {
            std::cerr << "파일 열기 실패: " << filename << "\n";
            return;
        }

        file << "Element_ID,Material_ID,N1,N2,N3,N4,N5,N6,N7,N8\n";

        for (size_t i = 0; i < mesh_.solids.size(); ++i) {
            const auto& elem = mesh_.solids[i];
            file << elem.id << ","
                 << mesh_.solid_materials[i];

            for (int node_id : elem.node_ids) {
                file << "," << node_id;
            }
            file << "\n";
        }

        file.close();
        std::cout << "✓ 저장 완료: " << filename << " (" << mesh_.solids.size() << " elements)\n";
    }

    // 6. 모든 노드의 변위 데이터 (마지막 state)
    void export_all_displacements_csv(const std::string& filename) {
        std::cout << "\n모든 노드 변위 데이터를 CSV로 저장 중...\n";

        if (states_.empty()) {
            std::cout << "State 데이터가 없습니다.\n";
            return;
        }

        const auto& state = states_.back();
        if (state.node_displacements.empty()) {
            std::cout << "변위 데이터가 없습니다 (IU=0)\n";
            return;
        }

        std::ofstream file(filename);
        if (!file) {
            std::cerr << "파일 열기 실패: " << filename << "\n";
            return;
        }

        file << "Node_ID,Ux,Uy,Uz,Magnitude\n";
        file << std::fixed << std::setprecision(6);

        int ndim = cd_.NDIM;
        for (int i = 0; i < cd_.NUMNP; ++i) {
            int idx = i * ndim;
            double ux = state.node_displacements[idx + 0];
            double uy = state.node_displacements[idx + 1];
            double uz = state.node_displacements[idx + 2];
            double mag = std::sqrt(ux*ux + uy*uy + uz*uz);

            file << (i + 1) << ","
                 << ux << "," << uy << "," << uz << "," << mag << "\n";
        }

        file.close();
        std::cout << "✓ 저장 완료: " << filename << " (" << cd_.NUMNP << " nodes)\n";
    }

    // 7. 모든 노드의 속도 데이터
    void export_all_velocities_csv(const std::string& filename) {
        std::cout << "\n모든 노드 속도 데이터를 CSV로 저장 중...\n";

        if (states_.empty()) {
            std::cout << "State 데이터가 없습니다.\n";
            return;
        }

        const auto& state = states_.back();
        if (state.node_velocities.empty()) {
            std::cout << "속도 데이터가 없습니다 (IV=0)\n";
            return;
        }

        std::ofstream file(filename);
        if (!file) {
            std::cerr << "파일 열기 실패: " << filename << "\n";
            return;
        }

        file << "Node_ID,Vx,Vy,Vz,Magnitude\n";
        file << std::fixed << std::setprecision(6);

        int ndim = cd_.NDIM;
        for (int i = 0; i < cd_.NUMNP; ++i) {
            int idx = i * ndim;
            double vx = state.node_velocities[idx + 0];
            double vy = state.node_velocities[idx + 1];
            double vz = state.node_velocities[idx + 2];
            double mag = std::sqrt(vx*vx + vy*vy + vz*vz);

            file << (i + 1) << ","
                 << vx << "," << vy << "," << vz << "," << mag << "\n";
        }

        file.close();
        std::cout << "✓ 저장 완료: " << filename << " (" << cd_.NUMNP << " nodes)\n";
    }

    // 8. 모든 Solid 요소의 응력 데이터
    void export_all_solid_stress_csv(const std::string& filename) {
        std::cout << "\n모든 Solid 요소 응력 데이터를 CSV로 저장 중...\n";

        if (states_.empty()) {
            std::cout << "State 데이터가 없습니다.\n";
            return;
        }

        const auto& state = states_.back();
        if (state.solid_data.empty()) {
            std::cout << "Solid 응력 데이터가 없습니다.\n";
            return;
        }

        std::ofstream file(filename);
        if (!file) {
            std::cerr << "파일 열기 실패: " << filename << "\n";
            return;
        }

        file << "Element_ID,Sigma_X,Sigma_Y,Sigma_Z,Tau_XY,Tau_YZ,Tau_ZX,Eff_Plastic_Strain,Von_Mises\n";
        file << std::fixed << std::setprecision(6);

        int nv3d = cd_.NV3D;
        int num_solids = std::abs(cd_.NEL8);

        for (int i = 0; i < num_solids; ++i) {
            int offset = i * nv3d;

            double sx = state.solid_data[offset + 0];
            double sy = state.solid_data[offset + 1];
            double sz = state.solid_data[offset + 2];
            double txy = state.solid_data[offset + 3];
            double tyz = state.solid_data[offset + 4];
            double tzx = state.solid_data[offset + 5];
            double eff_pstrain = state.solid_data[offset + 6];

            // Von Mises
            double s_vm = std::sqrt(0.5 * (
                (sx - sy) * (sx - sy) +
                (sy - sz) * (sy - sz) +
                (sz - sx) * (sz - sx)
            ) + 3.0 * (txy*txy + tyz*tyz + tzx*tzx));

            file << (i + 1) << ","
                 << sx << "," << sy << "," << sz << ","
                 << txy << "," << tyz << "," << tzx << ","
                 << eff_pstrain << "," << s_vm << "\n";
        }

        file.close();
        std::cout << "✓ 저장 완료: " << filename << " (" << num_solids << " elements)\n";
    }

    // 9. Global variables 시간 이력
    void export_global_vars_time_history_csv(const std::string& filename) {
        std::cout << "\nGlobal variables 시간 이력을 CSV로 저장 중...\n";

        if (states_.empty()) {
            std::cout << "State 데이터가 없습니다.\n";
            return;
        }

        std::ofstream file(filename);
        if (!file) {
            std::cerr << "파일 열기 실패: " << filename << "\n";
            return;
        }

        // 헤더 (일반적으로 첫 몇 개는 KE, IE, TE 등)
        file << "State,Time";
        for (int i = 0; i < cd_.NGLBV; ++i) {
            file << ",Var_" << (i + 1);
        }
        file << "\n";

        file << std::fixed << std::setprecision(6);

        for (size_t s = 0; s < states_.size(); ++s) {
            const auto& state = states_[s];
            file << s << "," << state.time;

            for (const auto& val : state.global_vars) {
                file << "," << val;
            }
            file << "\n";
        }

        file.close();
        std::cout << "✓ 저장 완료: " << filename << " (" << states_.size() << " states)\n";
    }

    // 10. 특정 노드의 시간 이력
    void export_node_time_history_csv(const std::string& filename, int node_id) {
        std::cout << "\n노드 " << node_id << "의 시간 이력을 CSV로 저장 중...\n";

        if (states_.empty()) {
            std::cout << "State 데이터가 없습니다.\n";
            return;
        }

        if (node_id < 1 || node_id > cd_.NUMNP) {
            std::cout << "잘못된 노드 번호: " << node_id << "\n";
            return;
        }

        std::ofstream file(filename);
        if (!file) {
            std::cerr << "파일 열기 실패: " << filename << "\n";
            return;
        }

        file << "State,Time,Ux,Uy,Uz,U_Mag,Vx,Vy,Vz,V_Mag,Ax,Ay,Az,A_Mag\n";
        file << std::fixed << std::setprecision(6);

        int ndim = cd_.NDIM;
        int idx = (node_id - 1) * ndim;

        for (size_t s = 0; s < states_.size(); ++s) {
            const auto& state = states_[s];
            file << s << "," << state.time;

            // 변위
            if (!state.node_displacements.empty()) {
                double ux = state.node_displacements[idx + 0];
                double uy = state.node_displacements[idx + 1];
                double uz = state.node_displacements[idx + 2];
                double umag = std::sqrt(ux*ux + uy*uy + uz*uz);
                file << "," << ux << "," << uy << "," << uz << "," << umag;
            } else {
                file << ",0,0,0,0";
            }

            // 속도
            if (!state.node_velocities.empty()) {
                double vx = state.node_velocities[idx + 0];
                double vy = state.node_velocities[idx + 1];
                double vz = state.node_velocities[idx + 2];
                double vmag = std::sqrt(vx*vx + vy*vy + vz*vz);
                file << "," << vx << "," << vy << "," << vz << "," << vmag;
            } else {
                file << ",0,0,0,0";
            }

            // 가속도
            if (!state.node_accelerations.empty()) {
                double ax = state.node_accelerations[idx + 0];
                double ay = state.node_accelerations[idx + 1];
                double az = state.node_accelerations[idx + 2];
                double amag = std::sqrt(ax*ax + ay*ay + az*az);
                file << "," << ax << "," << ay << "," << az << "," << amag;
            } else {
                file << ",0,0,0,0";
            }

            file << "\n";
        }

        file.close();
        std::cout << "✓ 저장 완료: " << filename << " (" << states_.size() << " states)\n";
    }

    // 11. 특정 요소의 응력 시간 이력
    void export_element_time_history_csv(const std::string& filename, int elem_id) {
        std::cout << "\n요소 " << elem_id << "의 응력 시간 이력을 CSV로 저장 중...\n";

        if (states_.empty()) {
            std::cout << "State 데이터가 없습니다.\n";
            return;
        }

        int num_solids = std::abs(cd_.NEL8);
        if (elem_id < 1 || elem_id > num_solids) {
            std::cout << "잘못된 요소 번호: " << elem_id << "\n";
            return;
        }

        std::ofstream file(filename);
        if (!file) {
            std::cerr << "파일 열기 실패: " << filename << "\n";
            return;
        }

        file << "State,Time,Sigma_X,Sigma_Y,Sigma_Z,Tau_XY,Tau_YZ,Tau_ZX,Eff_Plastic_Strain,Von_Mises\n";
        file << std::fixed << std::setprecision(6);

        int nv3d = cd_.NV3D;
        int offset = (elem_id - 1) * nv3d;

        for (size_t s = 0; s < states_.size(); ++s) {
            const auto& state = states_[s];

            if (state.solid_data.empty()) continue;

            double sx = state.solid_data[offset + 0];
            double sy = state.solid_data[offset + 1];
            double sz = state.solid_data[offset + 2];
            double txy = state.solid_data[offset + 3];
            double tyz = state.solid_data[offset + 4];
            double tzx = state.solid_data[offset + 5];
            double eff_pstrain = state.solid_data[offset + 6];

            double s_vm = std::sqrt(0.5 * (
                (sx - sy) * (sx - sy) +
                (sy - sz) * (sy - sz) +
                (sz - sx) * (sz - sx)
            ) + 3.0 * (txy*txy + tyz*tyz + tzx*tzx));

            file << s << "," << state.time << ","
                 << sx << "," << sy << "," << sz << ","
                 << txy << "," << tyz << "," << tzx << ","
                 << eff_pstrain << "," << s_vm << "\n";
        }

        file.close();
        std::cout << "✓ 저장 완료: " << filename << " (" << states_.size() << " states)\n";
    }

    // 전체 데이터 추출
    void extract_all(const std::string& output_dir = ".") {
        std::cout << "\n" << std::string(80, '=') << "\n";
        std::cout << "모든 데이터 추출 시작\n";
        std::cout << std::string(80, '=') << "\n";

        export_mesh_nodes_csv(output_dir + "/mesh_nodes.csv");
        export_solid_connectivity_csv(output_dir + "/solid_connectivity.csv");
        export_all_displacements_csv(output_dir + "/displacements_last_state.csv");
        export_all_velocities_csv(output_dir + "/velocities_last_state.csv");
        export_all_solid_stress_csv(output_dir + "/solid_stress_last_state.csv");
        export_global_vars_time_history_csv(output_dir + "/global_vars_history.csv");
        export_node_time_history_csv(output_dir + "/node_1000_history.csv", 1000);
        export_element_time_history_csv(output_dir + "/element_100_history.csv", 100);

        std::cout << "\n" << std::string(80, '=') << "\n";
        std::cout << "✓ 모든 데이터 추출 완료!\n";
        std::cout << std::string(80, '=') << "\n";
    }
};

int main(int argc, char* argv[]) {
    std::string filepath = "../results/d3plot";
    std::string output_dir = ".";

    if (argc > 1) {
        filepath = argv[1];
    }
    if (argc > 2) {
        output_dir = argv[2];
    }

    std::cout << "D3plot 전체 데이터 추출 프로그램\n";
    std::cout << "================================\n";
    std::cout << "입력 파일: " << filepath << "\n";
    std::cout << "출력 디렉토리: " << output_dir << "\n";

    // D3plot 파일 열기
    kood3plot::D3plotReader reader(filepath);
    auto err = reader.open();

    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "파일 열기 실패: " << kood3plot::error_to_string(err) << "\n";
        return 1;
    }

    std::cout << "✓ 파일 열기 성공\n";

    // 데이터 추출
    D3plotDataExtractor extractor(reader);

    extractor.print_mesh_info();
    extractor.print_control_data();
    extractor.print_time_states_summary();

    // 전체 데이터 CSV 저장
    extractor.extract_all(output_dir);

    reader.close();
    std::cout << "\n✓ 프로그램 종료\n";

    return 0;
}
