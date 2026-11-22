// LS-PrePost 단면 렌더 잡이 단면 위치 상자에 넣을 타겟을 고르는 규칙(면이 있고 숨기지 않은 타겟만)을 메모리의 메시로 보는 시험
//
// 렌더 잡의 단면 위치 = 타겟 상자의 min + position × (max − min). 상자는 타겟마다 GeometryAnalyzer::calculatePartBounds 를
// 합쳐 냈는데, 그 함수는 솔리드 · 셸 · 두꺼운 셸 요소가 없는 파트(빔 · 질량 · 모델에 없는 번호)에 모델 전체 상자를 돌려준다.
// 그런 타겟이나 숨긴 타겟(바닥 등)이 하나만 섞여도 상자가 모델 전체로 커져 단면이 타겟을 비켜 갔다.
//
// 빌드·실행:
//   cd build && make test_section_box_targets && ./tests/test_section_box_targets
#include "kood3plot/data/Mesh.hpp"
#include "kood3plot/render/GeometryAnalyzer.h"

#include <cstdio>
#include <string>
#include <vector>

using kood3plot::render::GeometryAnalyzer;

namespace {

int g_failed = 0;

void chk(const std::string& what, bool ok, const std::string& detail = "") {
    if (!ok) ++g_failed;
    std::printf("  %s %-58s %s\n", ok ? "OK " : "NG ", what.c_str(), detail.c_str());
}

std::string str(const std::vector<int32_t>& v) {
    std::string s = "{";
    for (size_t i = 0; i < v.size(); ++i) s += (i ? ", " : "") + std::to_string(v[i]);
    return s + "}";
}

}  // namespace

int main() {
    // 솔리드 파트 1 · 셸 파트 2 · 두꺼운 셸 파트 3 · 빔 파트 4(요소마다의 파트 배열 — 같은 번호가 되풀이된다)
    kood3plot::data::Mesh mesh;
    mesh.solid_parts = {1, 1, 1};
    mesh.shell_parts = {2, 2};
    mesh.thick_shell_parts = {3};
    mesh.beam_parts = {4, 4};

    struct Case {
        const char* what;
        std::vector<int32_t> targets, hidden, want;
    };
    const Case cases[] = {
        {"면이 있는 타겟은 종류와 무관하게 넣는다(타겟 순서 그대로)", {3, 1, 2}, {}, {3, 1, 2}},
        {"빔 파트 · 모델에 없는 번호는 뺀다(상자가 모델 전체가 된다)", {1, 4, 99}, {}, {1}},
        {"숨긴 타겟은 뺀다(바닥이 상자를 키운다)", {1, 2}, {2}, {1}},
        {"넣을 타겟이 없으면 빈 목록 — 부르는 쪽이 보이는 모델 상자를 쓴다", {4, 99, 2}, {2}, {}},
        {"같은 번호를 두 번 주면 한 번만", {1, 1}, {}, {1}},
    };
    for (const Case& c : cases) {
        const std::vector<int32_t> got = GeometryAnalyzer::boxTargets(mesh, c.targets, c.hidden);
        chk(c.what, got == c.want, "got " + str(got) + " want " + str(c.want));
    }

    std::printf("\n%s\n", g_failed ? (std::to_string(g_failed) + "건 실패").c_str() : "전부 통과");
    return g_failed ? 1 : 0;
}
