#include "kood3plot/D3plotReader.hpp"
#include <iostream>
#include <iomanip>
#include <cmath>
#include <algorithm>

// Von Mises 응력 계산
double calculate_von_mises(double sx, double sy, double sz,
                          double txy, double tyz, double tzx) {
    return std::sqrt(0.5 * (
        (sx - sy) * (sx - sy) +
        (sy - sz) * (sy - sz) +
        (sz - sx) * (sz - sx)
    ) + 3.0 * (txy*txy + tyz*tyz + tzx*tzx));
}

// 예제 1: 특정 state의 모든 요소 응력 출력
void example1_all_elements(kood3plot::D3plotReader& reader) {
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "예제 1: 특정 State의 모든 요소 응력 출력\n";
    std::cout << std::string(80, '=') << "\n";

    auto cd = reader.get_control_data();
    auto states = reader.read_all_states();

    if (states.empty()) {
        std::cout << "State 데이터가 없습니다.\n";
        return;
    }

    // 마지막 state 사용
    const auto& state = states.back();
    int nv3d = cd.NV3D;
    int num_elements = std::abs(cd.NEL8);

    std::cout << "Time: " << state.time << " 초\n";
    std::cout << "총 " << num_elements << "개 요소\n\n";

    // 처음 10개 요소만 출력
    int show_count = std::min(10, num_elements);
    std::cout << "처음 " << show_count << "개 요소의 응력:\n\n";

    std::cout << std::fixed << std::setprecision(3);
    std::cout << "Elem    σx          σy          σz          τxy         τyz         τzx         ε_eff       σ_vm\n";
    std::cout << "----    ----------  ----------  ----------  ----------  ----------  ----------  ----------  ----------\n";

    for (int i = 0; i < show_count; ++i) {
        int offset = i * nv3d;

        double sx = state.solid_data[offset + 0];
        double sy = state.solid_data[offset + 1];
        double sz = state.solid_data[offset + 2];
        double txy = state.solid_data[offset + 3];
        double tyz = state.solid_data[offset + 4];
        double tzx = state.solid_data[offset + 5];
        double eff_pstrain = state.solid_data[offset + 6];

        double s_vm = calculate_von_mises(sx, sy, sz, txy, tyz, tzx);

        std::cout << std::setw(4) << (i + 1) << "    "
                  << std::setw(10) << sx << "  "
                  << std::setw(10) << sy << "  "
                  << std::setw(10) << sz << "  "
                  << std::setw(10) << txy << "  "
                  << std::setw(10) << tyz << "  "
                  << std::setw(10) << tzx << "  "
                  << std::setw(10) << eff_pstrain << "  "
                  << std::setw(10) << s_vm << "\n";
    }
}

// 예제 2: 특정 요소의 응력 추출
void example2_specific_element(kood3plot::D3plotReader& reader, int elem_id) {
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "예제 2: 특정 요소의 응력 상세 정보\n";
    std::cout << std::string(80, '=') << "\n";

    auto cd = reader.get_control_data();
    auto states = reader.read_all_states();

    if (states.empty()) {
        std::cout << "State 데이터가 없습니다.\n";
        return;
    }

    const auto& state = states.back();
    int nv3d = cd.NV3D;
    int num_elements = std::abs(cd.NEL8);

    if (elem_id < 1 || elem_id > num_elements) {
        std::cout << "잘못된 요소 번호: " << elem_id << "\n";
        return;
    }

    int offset = (elem_id - 1) * nv3d;

    std::cout << "요소 번호: " << elem_id << "\n";
    std::cout << "Time: " << state.time << " 초\n\n";

    double sx = state.solid_data[offset + 0];
    double sy = state.solid_data[offset + 1];
    double sz = state.solid_data[offset + 2];
    double txy = state.solid_data[offset + 3];
    double tyz = state.solid_data[offset + 4];
    double tzx = state.solid_data[offset + 5];
    double eff_pstrain = state.solid_data[offset + 6];

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "[응력 텐서]\n";
    std::cout << "  σx  = " << std::setw(12) << sx << " (수직응력 X)\n";
    std::cout << "  σy  = " << std::setw(12) << sy << " (수직응력 Y)\n";
    std::cout << "  σz  = " << std::setw(12) << sz << " (수직응력 Z)\n";
    std::cout << "  τxy = " << std::setw(12) << txy << " (전단응력 XY)\n";
    std::cout << "  τyz = " << std::setw(12) << tyz << " (전단응력 YZ)\n";
    std::cout << "  τzx = " << std::setw(12) << tzx << " (전단응력 ZX)\n\n";

    double s_vm = calculate_von_mises(sx, sy, sz, txy, tyz, tzx);
    std::cout << "[유도 응력]\n";
    std::cout << "  Von Mises 응력 = " << s_vm << "\n";
    std::cout << "  유효 소성 변형률 = " << eff_pstrain << "\n\n";

    // 주응력 계산 (간단한 근사)
    double mean_stress = (sx + sy + sz) / 3.0;
    std::cout << "[기타]\n";
    std::cout << "  평균 응력 (Hydrostatic) = " << mean_stress << "\n";
}

// 예제 3: 시간에 따른 응력 이력 (Time History)
void example3_time_history(kood3plot::D3plotReader& reader, int elem_id) {
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "예제 3: 시간에 따른 응력 이력 (Time History)\n";
    std::cout << std::string(80, '=') << "\n";

    auto cd = reader.get_control_data();
    auto states = reader.read_all_states();

    if (states.empty()) {
        std::cout << "State 데이터가 없습니다.\n";
        return;
    }

    int nv3d = cd.NV3D;
    int num_elements = std::abs(cd.NEL8);

    if (elem_id < 1 || elem_id > num_elements) {
        std::cout << "잘못된 요소 번호: " << elem_id << "\n";
        return;
    }

    std::cout << "요소 번호: " << elem_id << "\n";
    std::cout << "총 " << states.size() << "개 time states\n\n";

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "State   Time        σx          σy          σz          σ_vm\n";
    std::cout << "-----   ----------  ----------  ----------  ----------  ----------\n";

    int offset = (elem_id - 1) * nv3d;

    // 모든 states 순회 (5개씩 건너뛰어 출력)
    for (size_t i = 0; i < states.size(); i += 5) {
        const auto& state = states[i];

        double sx = state.solid_data[offset + 0];
        double sy = state.solid_data[offset + 1];
        double sz = state.solid_data[offset + 2];
        double txy = state.solid_data[offset + 3];
        double tyz = state.solid_data[offset + 4];
        double tzx = state.solid_data[offset + 5];

        double s_vm = calculate_von_mises(sx, sy, sz, txy, tyz, tzx);

        std::cout << std::setw(5) << i << "   "
                  << std::setw(10) << state.time << "  "
                  << std::setw(10) << sx << "  "
                  << std::setw(10) << sy << "  "
                  << std::setw(10) << sz << "  "
                  << std::setw(10) << s_vm << "\n";
    }

    // 마지막 state도 출력
    if ((states.size() - 1) % 5 != 0) {
        const auto& state = states.back();
        double sx = state.solid_data[offset + 0];
        double sy = state.solid_data[offset + 1];
        double sz = state.solid_data[offset + 2];
        double txy = state.solid_data[offset + 3];
        double tyz = state.solid_data[offset + 4];
        double tzx = state.solid_data[offset + 5];
        double s_vm = calculate_von_mises(sx, sy, sz, txy, tyz, tzx);

        std::cout << std::setw(5) << (states.size() - 1) << "   "
                  << std::setw(10) << state.time << "  "
                  << std::setw(10) << sx << "  "
                  << std::setw(10) << sy << "  "
                  << std::setw(10) << sz << "  "
                  << std::setw(10) << s_vm << "\n";
    }
}

// 예제 4: 최대 응력 요소 찾기
void example4_find_max_stress(kood3plot::D3plotReader& reader) {
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "예제 4: 최대 Von Mises 응력 요소 찾기\n";
    std::cout << std::string(80, '=') << "\n";

    auto cd = reader.get_control_data();
    auto states = reader.read_all_states();

    if (states.empty()) {
        std::cout << "State 데이터가 없습니다.\n";
        return;
    }

    const auto& state = states.back();
    int nv3d = cd.NV3D;
    int num_elements = std::abs(cd.NEL8);

    std::cout << "Time: " << state.time << " 초\n";
    std::cout << "총 " << num_elements << "개 요소 검색 중...\n\n";

    double max_vm = 0.0;
    int max_elem = 0;
    double max_sx = 0.0, max_sy = 0.0, max_sz = 0.0;
    double max_txy = 0.0, max_tyz = 0.0, max_tzx = 0.0;

    // 모든 요소 순회
    for (int i = 0; i < num_elements; ++i) {
        int offset = i * nv3d;

        double sx = state.solid_data[offset + 0];
        double sy = state.solid_data[offset + 1];
        double sz = state.solid_data[offset + 2];
        double txy = state.solid_data[offset + 3];
        double tyz = state.solid_data[offset + 4];
        double tzx = state.solid_data[offset + 5];

        double s_vm = calculate_von_mises(sx, sy, sz, txy, tyz, tzx);

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

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "[최대 Von Mises 응력]\n";
    std::cout << "  요소 번호: " << max_elem << "\n";
    std::cout << "  σ_vm = " << max_vm << "\n\n";

    std::cout << "[응력 성분]\n";
    std::cout << "  σx  = " << max_sx << "\n";
    std::cout << "  σy  = " << max_sy << "\n";
    std::cout << "  σz  = " << max_sz << "\n";
    std::cout << "  τxy = " << max_txy << "\n";
    std::cout << "  τyz = " << max_tyz << "\n";
    std::cout << "  τzx = " << max_tzx << "\n";
}

// 예제 5: CSV 파일로 내보내기
void example5_export_to_csv(kood3plot::D3plotReader& reader, const std::string& filename) {
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "예제 5: 응력 데이터 CSV 파일로 내보내기\n";
    std::cout << std::string(80, '=') << "\n";

    auto cd = reader.get_control_data();
    auto states = reader.read_all_states();

    if (states.empty()) {
        std::cout << "State 데이터가 없습니다.\n";
        return;
    }

    // 마지막 state 사용
    const auto& state = states.back();
    int nv3d = cd.NV3D;
    int num_elements = std::abs(cd.NEL8);

    std::ofstream csv_file(filename);
    if (!csv_file) {
        std::cerr << "파일 열기 실패: " << filename << "\n";
        return;
    }

    // CSV 헤더
    csv_file << "Element,Sigma_X,Sigma_Y,Sigma_Z,Tau_XY,Tau_YZ,Tau_ZX,Eff_Plastic_Strain,Von_Mises\n";

    // 모든 요소 데이터 쓰기
    csv_file << std::fixed << std::setprecision(6);
    for (int i = 0; i < num_elements; ++i) {
        int offset = i * nv3d;

        double sx = state.solid_data[offset + 0];
        double sy = state.solid_data[offset + 1];
        double sz = state.solid_data[offset + 2];
        double txy = state.solid_data[offset + 3];
        double tyz = state.solid_data[offset + 4];
        double tzx = state.solid_data[offset + 5];
        double eff_pstrain = state.solid_data[offset + 6];

        double s_vm = calculate_von_mises(sx, sy, sz, txy, tyz, tzx);

        csv_file << (i + 1) << ","
                 << sx << ","
                 << sy << ","
                 << sz << ","
                 << txy << ","
                 << tyz << ","
                 << tzx << ","
                 << eff_pstrain << ","
                 << s_vm << "\n";
    }

    csv_file.close();
    std::cout << "✓ CSV 파일 저장 완료: " << filename << "\n";
    std::cout << "  총 " << num_elements << "개 요소 데이터 저장\n";
}

int main(int argc, char* argv[]) {
    std::string filepath = "../results/d3plot";

    if (argc > 1) {
        filepath = argv[1];
    }

    std::cout << "응력 데이터 추출 예제 프로그램\n";
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
    example1_all_elements(reader);
    example2_specific_element(reader, 100);  // 100번 요소
    example3_time_history(reader, 100);      // 100번 요소의 시간 이력
    example4_find_max_stress(reader);
    example5_export_to_csv(reader, "stress_output.csv");

    reader.close();
    std::cout << "\n✓ 모든 예제 완료!\n";

    return 0;
}
