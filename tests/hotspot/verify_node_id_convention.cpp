// 수정 검증 — nid-1 규약이 실덱 전 요소를 커버하는가 (역맵은 몇 개를 잃는가)
#include "kood3plot/D3plotReader.hpp"
#include <cstdio>
#include <map>
using namespace kood3plot;
int main(int argc, char** argv){
    D3plotReader r(argv[1]);
    if (r.open() != ErrorCode::SUCCESS) { printf("open 실패\n"); return 1; }
    auto mesh = r.read_mesh();

    std::map<int32_t,int32_t> rev;              // 수정 전 관례
    for (size_t i=0;i<mesh.real_node_ids.size();++i) rev[mesh.real_node_ids[i]]=(int32_t)i;

    size_t n_fix_ok=0, n_fix_miss=0, n_old_ok=0, n_old_miss=0;
    auto scan=[&](const std::vector<Element>& els){
        for (const auto& e : els) for (int32_t v : e.node_ids) {
            // 수정 후
            int64_t i2 = (int64_t)v - 1;
            if (i2>=0 && (size_t)i2 < mesh.nodes.size()) ++n_fix_ok; else ++n_fix_miss;
            // 수정 전
            if (mesh.real_node_ids.empty()) { ++n_old_ok; }
            else { auto it=rev.find(v); if(it!=rev.end()) ++n_old_ok; else ++n_old_miss; }
        }
    };
    scan(mesh.solids); scan(mesh.shells);

    printf("%s\n", argv[1]);
    printf("  절점참조 총 %zu\n", n_fix_ok+n_fix_miss);
    printf("  수정 후 (nid-1)      : 성공 %zu, 실패 %zu\n", n_fix_ok, n_fix_miss);
    printf("  수정 전 (real_node_ids 역맵): 성공 %zu, 실패 %zu\n", n_old_ok, n_old_miss);
    if (n_old_miss > n_fix_miss)
        printf("  ✅ 수정으로 절점참조 %zu 개가 복구됨\n", n_old_miss - n_fix_miss);
    else if (n_old_miss == n_fix_miss)
        printf("  = 이 덱에서는 두 규약이 동일 (real_node_ids 항등)\n");
    return 0;
}
