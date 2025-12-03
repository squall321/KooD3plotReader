#include "kood3plot/D3plotReader.hpp"
#include <iostream>
#include <iomanip>
#include <algorithm>
#include <map>

int main(int argc, char* argv[]) {
    std::string filepath = "../results/d3plot";
    if (argc > 1) {
        filepath = argv[1];
    }

    std::cout << "NARBS (Arbitrary Numbering) 데이터 확인\n";
    std::cout << "======================================\n\n";

    // 파일 열기
    kood3plot::D3plotReader reader(filepath);
    auto err = reader.open();
    if (err != kood3plot::ErrorCode::SUCCESS) {
        std::cerr << "파일 열기 실패!\n";
        return 1;
    }

    auto cd = reader.get_control_data();
    auto mesh = reader.read_mesh();

    std::cout << "파일: " << filepath << "\n";
    std::cout << "NARBS 크기: " << cd.NARBS << " words\n\n";

    if (cd.NARBS == 0) {
        std::cout << "NARBS 섹션이 없습니다. 순차 번호를 사용합니다.\n";
        return 0;
    }

    // ========================================
    // 1. 노드 ID 매핑
    // ========================================
    std::cout << std::string(80, '=') << "\n";
    std::cout << "1. 노드 ID 매핑 (Internal Index → Real ID)\n";
    std::cout << std::string(80, '=') << "\n\n";

    std::cout << "총 " << mesh.real_node_ids.size() << "개 노드\n";
    std::cout << "처음 20개 노드:\n\n";
    std::cout << "Internal Index   Real Node ID   Coordinates (X, Y, Z)\n";
    std::cout << "--------------   ------------   ----------------------------------\n";

    int show_nodes = std::min(20, (int)mesh.nodes.size());
    for (int i = 0; i < show_nodes; ++i) {
        const auto& node = mesh.nodes[i];
        std::cout << std::setw(14) << i << "   "
                  << std::setw(12) << node.id << "   "
                  << "(" << std::setw(10) << node.x << ", "
                  << std::setw(10) << node.y << ", "
                  << std::setw(10) << node.z << ")\n";
    }

    // 노드 ID 범위
    auto [min_node_it, max_node_it] = std::minmax_element(
        mesh.real_node_ids.begin(), mesh.real_node_ids.end());

    std::cout << "\n노드 ID 범위:\n";
    std::cout << "  최소: " << *min_node_it << "\n";
    std::cout << "  최대: " << *max_node_it << "\n";
    std::cout << "  범위: " << (*max_node_it - *min_node_it + 1) << "\n";

    // ========================================
    // 2. 요소 ID 매핑
    // ========================================
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "2. 요소 ID 매핑 (Solid Elements)\n";
    std::cout << std::string(80, '=') << "\n\n";

    std::cout << "총 " << mesh.real_solid_ids.size() << "개 솔리드 요소\n";
    std::cout << "처음 30개 요소:\n\n";
    std::cout << "Internal Index   Real Element ID   Material ID   Node Count\n";
    std::cout << "--------------   ---------------   -----------   ----------\n";

    int show_elems = std::min(30, (int)mesh.solids.size());
    for (int i = 0; i < show_elems; ++i) {
        const auto& elem = mesh.solids[i];
        int material_id = mesh.solid_materials[i];
        std::cout << std::setw(14) << i << "   "
                  << std::setw(15) << elem.id << "   "
                  << std::setw(11) << material_id << "   "
                  << std::setw(10) << elem.node_ids.size() << "\n";
    }

    // 요소 ID 범위
    auto [min_elem_it, max_elem_it] = std::minmax_element(
        mesh.real_solid_ids.begin(), mesh.real_solid_ids.end());

    std::cout << "\n요소 ID 범위:\n";
    std::cout << "  최소: " << *min_elem_it << "\n";
    std::cout << "  최대: " << *max_elem_it << "\n";
    std::cout << "  범위: " << (*max_elem_it - *min_elem_it + 1) << "\n";

    // ========================================
    // 3. 재료 타입
    // ========================================
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "3. 재료(Material) 타입 정보\n";
    std::cout << std::string(80, '=') << "\n\n";

    std::cout << "총 " << mesh.material_types.size() << "개 재료 타입\n\n";

    if (!mesh.material_types.empty()) {
        std::cout << "재료 타입 번호:\n";
        for (size_t i = 0; i < std::min(size_t(30), mesh.material_types.size()); ++i) {
            std::cout << "  " << std::setw(3) << (i+1) << ": " << mesh.material_types[i] << "\n";
        }
        if (mesh.material_types.size() > 30) {
            std::cout << "  ... (" << (mesh.material_types.size() - 30) << " more)\n";
        }
    }

    // ========================================
    // 4. 재료별 요소 개수
    // ========================================
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "4. 재료별 요소 분포\n";
    std::cout << std::string(80, '=') << "\n\n";

    std::map<int32_t, int> material_counts;
    for (int32_t mat_id : mesh.solid_materials) {
        material_counts[mat_id]++;
    }

    std::cout << "재료 ID별 요소 개수 (상위 20개):\n\n";
    std::cout << "Material ID   Element Count   Percentage\n";
    std::cout << "-----------   -------------   ----------\n";

    // Sort by count (descending)
    std::vector<std::pair<int32_t, int>> sorted_materials(
        material_counts.begin(), material_counts.end());
    std::sort(sorted_materials.begin(), sorted_materials.end(),
              [](const auto& a, const auto& b) { return a.second > b.second; });

    int total_elems = mesh.solids.size();
    int show_count = std::min(20, (int)sorted_materials.size());
    for (int i = 0; i < show_count; ++i) {
        int32_t mat_id = sorted_materials[i].first;
        int count = sorted_materials[i].second;
        double percentage = 100.0 * count / total_elems;

        std::cout << std::setw(11) << mat_id << "   "
                  << std::setw(13) << count << "   "
                  << std::fixed << std::setprecision(2)
                  << std::setw(9) << percentage << "%\n";
    }

    if (sorted_materials.size() > 20) {
        std::cout << "  ... (" << (sorted_materials.size() - 20) << " more materials)\n";
    }

    // ========================================
    // 5. ID 연속성 검사
    // ========================================
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "5. ID 연속성 검사\n";
    std::cout << std::string(80, '=') << "\n\n";

    // Check if node IDs are sequential
    bool nodes_sequential = true;
    int expected_node_id = mesh.real_node_ids[0];
    for (size_t i = 0; i < mesh.real_node_ids.size(); ++i) {
        if (mesh.real_node_ids[i] != expected_node_id) {
            nodes_sequential = false;
            break;
        }
        expected_node_id++;
    }

    std::cout << "노드 ID 연속성: " << (nodes_sequential ? "연속" : "비연속 (갭 존재)") << "\n";

    // Check if element IDs are sequential
    bool elems_sequential = true;
    int expected_elem_id = mesh.real_solid_ids[0];
    for (size_t i = 0; i < mesh.real_solid_ids.size(); ++i) {
        if (mesh.real_solid_ids[i] != expected_elem_id) {
            elems_sequential = false;
            break;
        }
        expected_elem_id++;
    }

    std::cout << "요소 ID 연속성: " << (elems_sequential ? "연속" : "비연속 (갭 존재)") << "\n";

    // Find gaps
    if (!nodes_sequential) {
        std::cout << "\n노드 ID 갭 예시 (처음 5개):\n";
        int gap_count = 0;
        for (size_t i = 1; i < mesh.real_node_ids.size() && gap_count < 5; ++i) {
            int diff = mesh.real_node_ids[i] - mesh.real_node_ids[i-1];
            if (diff != 1) {
                std::cout << "  인덱스 " << (i-1) << " → " << i << ": "
                          << "ID " << mesh.real_node_ids[i-1] << " → " << mesh.real_node_ids[i]
                          << " (갭: " << (diff-1) << ")\n";
                gap_count++;
            }
        }
    }

    if (!elems_sequential) {
        std::cout << "\n요소 ID 갭 예시 (처음 5개):\n";
        int gap_count = 0;
        for (size_t i = 1; i < mesh.real_solid_ids.size() && gap_count < 5; ++i) {
            int diff = mesh.real_solid_ids[i] - mesh.real_solid_ids[i-1];
            if (diff != 1) {
                std::cout << "  인덱스 " << (i-1) << " → " << i << ": "
                          << "ID " << mesh.real_solid_ids[i-1] << " → " << mesh.real_solid_ids[i]
                          << " (갭: " << (diff-1) << ")\n";
                gap_count++;
            }
        }
    }

    // ========================================
    // 6. 사용 예제
    // ========================================
    std::cout << "\n" << std::string(80, '=') << "\n";
    std::cout << "6. NARBS 데이터 사용 예제\n";
    std::cout << std::string(80, '=') << "\n\n";

    std::cout << "예제 1: 특정 Real Node ID로 노드 찾기\n";
    std::cout << "---------------------------------------\n";
    int32_t search_node_id = mesh.real_node_ids[10];  // Example
    std::cout << "Real Node ID " << search_node_id << " 찾기...\n";

    // Linear search (could use map for O(1) lookup)
    for (size_t i = 0; i < mesh.real_node_ids.size(); ++i) {
        if (mesh.real_node_ids[i] == search_node_id) {
            const auto& node = mesh.nodes[i];
            std::cout << "  찾음! Internal Index: " << i << "\n";
            std::cout << "  좌표: (" << node.x << ", " << node.y << ", " << node.z << ")\n";
            break;
        }
    }

    std::cout << "\n예제 2: 특정 재료의 모든 요소 찾기\n";
    std::cout << "----------------------------------------\n";
    if (!sorted_materials.empty()) {
        int32_t target_material = sorted_materials[0].first;  // Most common material
        std::cout << "Material ID " << target_material << "인 요소들:\n";

        int count = 0;
        for (size_t i = 0; i < mesh.solid_materials.size() && count < 10; ++i) {
            if (mesh.solid_materials[i] == target_material) {
                std::cout << "  요소 " << mesh.real_solid_ids[i] << " (내부 인덱스: " << i << ")\n";
                count++;
            }
        }
        std::cout << "  ... (총 " << sorted_materials[0].second << "개)\n";
    }

    std::cout << "\n✓ NARBS 분석 완료!\n";
    reader.close();

    return 0;
}
