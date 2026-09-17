// *SET_SEGMENT 부모 solid 요소 조회가 절점 규약(내부 인덱스 vs 사용자 ID)을
// 지키는지 확인하는 시험. 합성 메시만 쓰므로 덱이 필요 없다.
//
// 빌드·실행:
//   cmake --build build -j4 --target unified_analyzer
//   g++ -std=c++17 -O2 -I include tests/test_segment_parent_lookup.cpp \
//       build/libkood3plot.a -fopenmp -lz -o /tmp/t_segparent && /tmp/t_segparent
#include "kood3plot/analysis/UnifiedAnalyzer.hpp"
#include "kood3plot/data/Mesh.hpp"
#include <array>
#include <cstdio>
#include <string>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

static int fails = 0;

static void chk(const char* name, bool ok, const std::string& detail) {
    if (!ok) ++fails;
    printf("  %s %-46s %s\n", ok ? "OK " : "NG ", name, detail.c_str());
}

static std::string listOf(const std::vector<int32_t>& v) {
    std::string s = "{";
    for (size_t i = 0; i < v.size(); ++i) {
        if (i) s += ",";
        s += std::to_string(v[i]);
    }
    return s + "}";
}

/// 육면체 N개를 x 방향으로 이어 붙인 막대. 슬라이스 s 의 절점은 내부 1-based
/// 번호로 4s+1 .. 4s+4, 요소 e 의 연결성은 4e+1 .. 4e+8 이다.
static data::Mesh makeBar(int n_elem, bool renumber) {
    data::Mesh mesh;
    const int n_nodes = 4 * (n_elem + 1);
    for (int i = 0; i < n_nodes; ++i) {
        Node nd;
        nd.id = i + 1;
        nd.x = i / 4;
        nd.y = (i % 4 == 1 || i % 4 == 2) ? 1.0 : 0.0;
        nd.z = (i % 4 >= 2) ? 1.0 : 0.0;
        mesh.nodes.push_back(nd);
    }
    for (int e = 0; e < n_elem; ++e) {
        Element el;
        el.id = e + 1;
        el.type = ElementType::SOLID;
        el.material_id = 1;
        for (int k = 1; k <= 8; ++k) el.node_ids.push_back(4 * e + k);
        mesh.solids.push_back(el);
        mesh.solid_parts.push_back(1);
    }
    mesh.num_solids = mesh.solids.size();

    // 사용자 절점 ID. renumber 면 앞 100개는 1..100, 나머지는 151.. 로 건너뛴다
    // (실덱 results/d3plot 이 인덱스 28293 부터 비항등인 것과 같은 모양).
    mesh.real_node_ids.resize(n_nodes);
    for (int i = 0; i < n_nodes; ++i) {
        mesh.real_node_ids[i] = renumber ? ((i < 100) ? (i + 1) : (i + 51)) : (i + 1);
    }
    return mesh;
}

/// 요소 e 의 **옆면**(z=0 쪽, 슬라이스 e·e+1 의 절점 2개씩)을 사용자 ID 로 만든
/// 세그먼트. 막대의 옆면은 이웃 요소와 공유하지 않으므로 부모가 하나뿐이다
/// (슬라이스 면을 쓰면 앞뒤 두 요소가 절점 4개를 모두 공유해 부모가 애매해진다).
static std::array<int32_t, 4> sideFaceSegment(const data::Mesh& mesh, int e) {
    const int internal[4] = {4 * e + 1, 4 * e + 2, 4 * e + 6, 4 * e + 5};
    std::array<int32_t, 4> seg{};
    for (int k = 0; k < 4; ++k) {
        seg[k] = mesh.real_node_ids[internal[k] - 1];   // 내부 1-based → 사용자 ID
    }
    return seg;
}

int main() {
    const int N = 49;   // 절점 200개

    printf("[A] 비항등 real_node_ids — 재번호 구간의 세그먼트\n");
    {
        auto mesh = makeBar(N, /*renumber=*/true);
        std::vector<std::array<int32_t, 4>> segs = {sideFaceSegment(mesh, 30)};
        printf("      세그먼트 사용자 절점 = %d,%d,%d,%d (요소 30 의 옆면)\n",
               segs[0][0], segs[0][1], segs[0][2], segs[0][3]);

        size_t unresolved = 0;
        auto parents = UnifiedAnalyzer::resolveSegmentParentElements(mesh, segs, unresolved);
        chk("부모 = 요소 30", parents == std::vector<int32_t>({30}), listOf(parents));
        chk("미해석 세그먼트 0개", unresolved == 0, "n=" + std::to_string(unresolved));
    }

    printf("\n[B] 비항등 덱의 항등 구간 — 회귀 없음\n");
    {
        auto mesh = makeBar(N, /*renumber=*/true);
        std::vector<std::array<int32_t, 4>> segs = {sideFaceSegment(mesh, 3)};
        size_t unresolved = 0;
        auto parents = UnifiedAnalyzer::resolveSegmentParentElements(mesh, segs, unresolved);
        chk("부모 = 요소 3", parents == std::vector<int32_t>({3}), listOf(parents));
        chk("미해석 세그먼트 0개", unresolved == 0, "n=" + std::to_string(unresolved));
    }

    printf("\n[C] 항등 덱 — 두 규약이 같은 답을 내는 경우\n");
    {
        auto mesh = makeBar(N, /*renumber=*/false);
        std::vector<std::array<int32_t, 4>> segs = {sideFaceSegment(mesh, 30),
                                                    sideFaceSegment(mesh, 7)};
        size_t unresolved = 0;
        auto parents = UnifiedAnalyzer::resolveSegmentParentElements(mesh, segs, unresolved);
        chk("부모 = 요소 7,30", parents == std::vector<int32_t>({7, 30}), listOf(parents));
        chk("미해석 세그먼트 0개", unresolved == 0, "n=" + std::to_string(unresolved));
    }

    printf("\n[D] 메시에 없는 절점만 가진 세그먼트 — 사유로 셈\n");
    {
        auto mesh = makeBar(N, /*renumber=*/true);
        std::vector<std::array<int32_t, 4>> segs = {{900001, 900002, 900003, 900004}};
        size_t unresolved = 0;
        auto parents = UnifiedAnalyzer::resolveSegmentParentElements(mesh, segs, unresolved);
        chk("부모 없음", parents.empty(), listOf(parents));
        chk("미해석 1개", unresolved == 1, "n=" + std::to_string(unresolved));
    }

    printf("\n%s  실패 %d 건\n", fails ? "[FAIL]" : "[PASS]", fails);
    return fails ? 1 : 0;
}
