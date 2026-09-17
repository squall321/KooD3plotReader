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


/// 퇴화 육면체 시험용 작은 메시. 절점 1..12 는 모두 항등 사용자 ID 다.
/// 요소는 호출자가 연결성 8개씩 넘겨 순서까지 지정한다 (요소 인덱스 순서가
/// 동점 처리에 영향을 주므로 시험에서 그 순서를 직접 다뤄야 한다).
static data::Mesh makeSmallMesh(const std::vector<std::vector<int32_t>>& conns) {
    data::Mesh mesh;
    for (int i = 0; i < 12; ++i) {
        Node nd;
        nd.id = i + 1;
        nd.x = i;
        nd.y = 0.0;
        nd.z = 0.0;
        mesh.nodes.push_back(nd);
        mesh.real_node_ids.push_back(i + 1);
    }
    for (size_t e = 0; e < conns.size(); ++e) {
        Element el;
        el.id = static_cast<int32_t>(e) + 1;
        el.type = ElementType::SOLID;
        el.material_id = 1;
        el.node_ids = conns[e];
        mesh.solids.push_back(el);
        mesh.solid_parts.push_back(1);
    }
    mesh.num_solids = mesh.solids.size();
    return mesh;
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


    printf("\n[E] 퇴화 육면체(사면체) — 중복 절점이 진짜 부모를 가로채면 안 된다\n");
    {
        // LS-DYNA 는 사면체를 (a,b,c,d,d,d,d,d) 로 적는다. 절점 d 가 연결성에
        // 5번 들어가므로, 중복을 세면 '절점 1개만 공유한 사면체'(5) 가
        // '절점 4개를 공유한 진짜 부모'(4) 를 이긴다.
        auto mesh = makeSmallMesh({
            {9, 10, 11, 4, 4, 4, 4, 4},          // 요소 0 = 사면체, 절점 4 하나만 공유
            {1, 2, 3, 4, 5, 6, 7, 8},            // 요소 1 = 진짜 육면체
        });
        std::vector<std::array<int32_t, 4>> segs = {{1, 2, 3, 4}};   // 육면체 바닥면
        size_t unresolved = 0;
        auto parents = UnifiedAnalyzer::resolveSegmentParentElements(mesh, segs, unresolved);
        chk("부모 = 육면체(요소 1)", parents == std::vector<int32_t>({1}), listOf(parents));
        chk("미해석 세그먼트 0개", unresolved == 0, "n=" + std::to_string(unresolved));
    }

    printf("\n[F] 퇴화 육면체(피라미드) — 꼭짓점 4회 반복이 동점을 만들면 안 된다\n");
    {
        // 피라미드는 (n1,n2,n3,n4,n5,n5,n5,n5) 라 꼭짓점이 4번 들어간다.
        // 중복을 세면 진짜 부모와 4:4 동점이 되고, 요소 인덱스가 낮은 쪽이 이긴다.
        auto mesh = makeSmallMesh({
            {9, 10, 11, 12, 4, 4, 4, 4},         // 요소 0 = 피라미드, 꼭짓점이 절점 4
            {1, 2, 3, 4, 5, 6, 7, 8},            // 요소 1 = 진짜 육면체
        });
        std::vector<std::array<int32_t, 4>> segs = {{1, 2, 3, 4}};
        size_t unresolved = 0;
        auto parents = UnifiedAnalyzer::resolveSegmentParentElements(mesh, segs, unresolved);
        chk("부모 = 육면체(요소 1)", parents == std::vector<int32_t>({1}), listOf(parents));
        chk("미해석 세그먼트 0개", unresolved == 0, "n=" + std::to_string(unresolved));
    }

    printf("\n[G] 절점 1개만 걸친 세그먼트 — 중복이 3개 임계를 통과시키면 안 된다\n");
    {
        // 셸 면처럼 solid 부모가 없는 세그먼트. 절점 하나가 사면체의 중복 슬롯에
        // 걸리면 중복 계수로는 hit=5 가 되어 'best_n >= 3' 임계가 무력화된다.
        auto mesh = makeSmallMesh({
            {1, 2, 3, 4, 5, 6, 7, 8},
            {9, 10, 11, 4, 4, 4, 4, 4},
        });
        std::vector<std::array<int32_t, 4>> segs = {{4, 900001, 900002, 900003}};
        size_t unresolved = 0;
        auto parents = UnifiedAnalyzer::resolveSegmentParentElements(mesh, segs, unresolved);
        chk("부모 없음", parents.empty(), listOf(parents));
        chk("미해석 1개", unresolved == 1, "n=" + std::to_string(unresolved));
    }

    printf("\n%s  실패 %d 건\n", fails ? "[FAIL]" : "[PASS]", fails);
    return fails ? 1 : 0;
}
