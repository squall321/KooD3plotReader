// d3plot 의 절점·요소 실제 ID 배열을 JSON 으로 찍어 외부 리더·원본 덱과 대조하게 하는 도구
//
// 빌드·사용:
//   g++ -std=c++17 -O2 -I include tests/ids/dump_element_ids.cpp \
//       build/libkood3plot.a -fopenmp -lz -o /tmp/dump_ids && /tmp/dump_ids <d3plot> > ids.json
//
// 검증: tests/ids/verify_element_ids_lasso.py 가 이 출력을 lasso 및 원본 .k 와 대조한다.
#include "kood3plot/D3plotReader.hpp"
#include <cstdio>
#include <vector>

using namespace kood3plot;

static void dump(const char* name, const std::vector<int32_t>& v, bool last = false) {
    printf("  \"%s\": [", name);
    for (size_t i = 0; i < v.size(); ++i) {
        printf("%s%d", i ? "," : "", v[i]);
    }
    printf("]%s\n", last ? "" : ",");
}

int main(int argc, char** argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: dump_element_ids <d3plot>\n");
        return 2;
    }
    D3plotReader reader(argv[1]);
    if (reader.open() != ErrorCode::SUCCESS) {
        fprintf(stderr, "open failed: %s\n", argv[1]);
        return 1;
    }
    const auto& c = reader.get_control_data();
    auto mesh = reader.read_mesh();

    printf("{\n");
    printf("  \"counts\": {\"NUMNP\": %d, \"NEL8\": %d, \"NEL2\": %d, \"NEL4\": %d, \"NELT\": %d, \"NARBS\": %d},\n",
           (int)c.NUMNP, (int)c.NEL8, (int)c.NEL2, (int)c.NEL4, (int)c.NELT, (int)c.NARBS);
    dump("node", mesh.real_node_ids);
    dump("solid", mesh.real_solid_ids);
    dump("beam", mesh.real_beam_ids);
    dump("shell", mesh.real_shell_ids);
    dump("tshell", mesh.real_thick_shell_ids, true);
    printf("}\n");
    return 0;
}
