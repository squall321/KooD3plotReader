// LS-PrePost 명령 스크립트가 사용자가 준 색 범위(fringe_range)를 타겟 있는 렌더에도 적는지 보는 시험
//
// 타겟(highlight_parts)이 있으면 스크립트는 genselect 로 타겟만 색을 입힌다(7d33676, 2026-04). 그때 `range userdef` 가
// 타겟 없는 갈래로만 옮겨져, 렌더 잡에 `fringe_range: {min, max}` 와 `parts:` 를 함께 주면 범위가 말없이 빠졌다 —
// 영상은 LS-PrePost 자동 범위(모델 전체의 그 상태 최소 ~ 최대)로 나왔다(2026-11-22 실측, Test_006).
// 자동 범위(auto_fringe_range)일 때는 지금처럼 아무 범위도 적지 않는다.
//
// 빌드·실행:
//   cd build && make test_lspp_fringe_range && ./tests/test_lspp_fringe_range
#include "kood3plot/render/LSPrePostRenderer.h"

#include <cstdio>
#include <string>

using kood3plot::render::LSPrePostRenderer;
using kood3plot::render::RenderOptions;

namespace {

int g_failed = 0;

void chk(const std::string& what, bool ok, const std::string& detail = "") {
    if (!ok) ++g_failed;
    std::printf("  %s %-60s %s\n", ok ? "OK " : "NG ", what.c_str(), detail.c_str());
}

size_t count(const std::string& s, const std::string& what) {
    size_t n = 0;
    for (size_t p = s.find(what); p != std::string::npos; p = s.find(what, p + what.size())) ++n;
    return n;
}

}  // namespace

int main() {
    LSPrePostRenderer r("/nonexistent/lsprepost");
    const std::string range = "range userdef 0 50;\n";   // 색 범위 숫자는 유효숫자 10자리(작은 변형률 범위가 뭉개지지 않게)

    std::printf("[1] 사용자 범위 — 타겟이 있어도 적는다(색을 입힌 바로 뒤)\n");
    {
        RenderOptions o;
        o.highlight_parts = {6};
        o.auto_fringe_range = false;
        o.fringe_min = 0.0;
        o.fringe_max = 50.0;
        const std::string s = r.generateScript("/x/d3plot", "/x/out", o);
        chk("`range userdef 0 50` 이 한 번 적힌다", count(s, range) == 1, std::to_string(count(s, range)) + "번");
        chk("타겟에 색을 입힌 `pfringe` 바로 뒤에 온다", s.find("fringe 9\npfringe\n" + range) != std::string::npos);
    }

    std::printf("[2] 사용자 범위 — 타겟이 없으면 예전 그대로\n");
    {
        RenderOptions o;
        o.auto_fringe_range = false;
        o.fringe_min = 0.0;
        o.fringe_max = 50.0;
        const std::string s = r.generateScript("/x/d3plot", "/x/out", o);
        chk("`fringe 9 / pfringe / range userdef 0 50`", s.find("fringe 9\npfringe\n" + range) != std::string::npos && count(s, range) == 1);
    }

    std::printf("[3] 작은 범위도 자릿수를 잃지 않는다(유효숫자 10자리)\n");
    {
        RenderOptions o;
        o.highlight_parts = {6};
        o.auto_fringe_range = false;
        o.fringe_min = 0.0;
        o.fringe_max = 2.5e-06;
        const std::string s = r.generateScript("/x/d3plot", "/x/out", o);
        chk("`range userdef 0 2.5e-06;`", s.find("range userdef 0 2.5e-06;\n") != std::string::npos);
    }

    std::printf("[4] 자동 범위 — 타겟이 있든 없든 범위를 적지 않는다\n");
    for (bool target : {false, true}) {
        RenderOptions o;
        if (target) o.highlight_parts = {6};
        const std::string s = r.generateScript("/x/d3plot", "/x/out", o);
        chk(std::string(target ? "타겟 있음" : "타겟 없음") + " — `range userdef` 없음", s.find("range userdef") == std::string::npos);
    }

    std::printf("\n%s\n", g_failed ? (std::to_string(g_failed) + "건 실패").c_str() : "전부 통과");
    return g_failed ? 1 : 0;
}
