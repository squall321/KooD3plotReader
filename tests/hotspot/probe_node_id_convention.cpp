// 실덱에서 연결성 값이 '내부 인덱스'인지 '사용자 ID'인지 확정
#include "kood3plot/D3plotReader.hpp"
#include <cstdio>
#include <set>
#include <algorithm>
using namespace kood3plot;
int main(int argc, char** argv){
    D3plotReader r(argv[1]);
    if (r.open() != ErrorCode::SUCCESS) { printf("open 실패: %s\n", argv[1]); return 1; }
    auto mesh = r.read_mesh();
    printf("덱: %s\n", argv[1]);
    printf("  절점 %zu, 솔리드 %zu\n", mesh.nodes.size(), mesh.solids.size());
    printf("  real_node_ids %zu, real_solid_ids %zu\n",
           mesh.real_node_ids.size(), mesh.real_solid_ids.size());

    // 연결성 값 범위
    int32_t mn = 1<<30, mx = -(1<<30);
    for (const auto& e : mesh.solids)
        for (int32_t v : e.node_ids) { mn = std::min(mn,v); mx = std::max(mx,v); }
    printf("  연결성 값 범위: %d ~ %d  (절점 수 %zu)\n", mn, mx, mesh.nodes.size());

    // real_node_ids 항등성
    bool ident = true;
    size_t first_bad = 0;
    for (size_t i = 0; i < mesh.real_node_ids.size(); ++i)
        if (mesh.real_node_ids[i] != (int32_t)(i+1)) { ident=false; first_bad=i; break; }
    printf("  real_node_ids 항등? %s", ident ? "예\n" : "");
    if (!ident) printf("아니오 (인덱스 %zu 에서 %d)\n", first_bad, mesh.real_node_ids[first_bad]);

    if (!ident) {
        // 역맵으로 조회 시 MISS 되는 요소 수
        std::set<int32_t> idset(mesh.real_node_ids.begin(), mesh.real_node_ids.end());
        size_t miss_elems = 0, miss_nodes = 0;
        for (const auto& e : mesh.solids) {
            bool any = false;
            for (int32_t v : e.node_ids)
                if (!idset.count(v)) { any = true; ++miss_nodes; }
            if (any) ++miss_elems;
        }
        printf("  🔴 역맵 조회 시 MISS: 요소 %zu / %zu (%.2f%%), 절점참조 %zu\n",
               miss_elems, mesh.solids.size(),
               100.0*miss_elems/mesh.solids.size(), miss_nodes);
        printf("  -> 연결성 값은 '사용자 ID' 가 아니라 '내부 인덱스' 임을 뜻한다\n");
    }
    // nid-1 규약이 항상 유효한가
    size_t oob = 0;
    for (const auto& e : mesh.solids)
        for (int32_t v : e.node_ids)
            if (v < 1 || (size_t)v > mesh.nodes.size()) ++oob;
    printf("  nid-1 규약 범위 위반: %zu 건 %s\n", oob, oob? "🔴":"✅");
    return 0;
}
