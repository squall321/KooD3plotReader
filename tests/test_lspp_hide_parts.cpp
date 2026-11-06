// LS-PrePost 명령 스크립트에서 숨길 파트(바닥 등)가 fringe 뒤 · 첫 ac 앞에 숨겨지는지 보는 시험
//
// fringe/pfringe 와 `selectpart all on` 은 감추기를 되돌린다. 숨김은 `-M <id>` 로만 한다 — `selectpart part N on/off` 는
// 「N 만 보이기」 라 여러 파트를 다루면 다 사라진다(실측 2026-11-06). 그래서 숨김은 fringe 블록 뒤에 와야 하고,
// 카메라가 숨긴 파트를 빼고 맞추려면 첫 `ac` 앞에 와야 한다. 순서가 틀리면 바닥이 그대로 영상에 남거나
// (조용히) 카메라가 바닥까지 맞춰 타겟이 작게 나온다 — 리포트 그림 꾸러미 3단계(2026-11).
//
// 빌드·실행:
//   cd build && make test_lspp_hide_parts && ./tests/test_lspp_hide_parts
#include "kood3plot/render/LSPrePostRenderer.h"

#include <cstdio>
#include <string>

using kood3plot::render::LSPrePostRenderer;
using kood3plot::render::RenderOptions;

namespace {

int g_failed = 0;

void chk(const char* what, bool ok, const std::string& detail = "") {
    if (!ok) ++g_failed;
    std::printf("  %s %-56s %s\n", ok ? "OK " : "NG ", what, detail.c_str());
}

size_t find_after(const std::string& s, const std::string& what, size_t from) {
    return from == std::string::npos ? std::string::npos : s.find(what, from);
}

}  // namespace

int main() {
    LSPrePostRenderer r("/nonexistent/lsprepost");
    for (bool targets : {false, true}) {
        RenderOptions o;
        o.hidden_parts = {23, 24};
        if (targets) o.highlight_parts = {5};
        const std::string sc = r.generateScript("/x/d3plot", "/x/out.png", o);
        const size_t pf = sc.rfind("pfringe");
        const size_t m23 = sc.find("\n-M 23\n");
        const size_t m24 = sc.find("\n-M 24\n");
        const size_t ac = find_after(sc, "\nac\n", m24);
        std::printf("%s\n", targets ? "[타겟 있음]" : "[타겟 없음]");
        chk("숨길 파트 둘 다 -M 으로 뺀다", m23 != std::string::npos && m24 != std::string::npos);
        chk("fringe(pfringe) 뒤에 뺀다", pf != std::string::npos && m23 > pf);
        chk("그 뒤에 ac 가 온다(카메라가 숨긴 파트를 뺀다)", ac != std::string::npos);
        chk("'selectpart part N on/off' 를 쓰지 않는다(「N 만 보이기」 라 다 사라진다)",
            sc.find("selectpart part 23") == std::string::npos && sc.find("selectpart part 24") == std::string::npos);
        chk("숨긴 뒤 'all on' 으로 되살리지 않는다", find_after(sc, "selectpart all on", m23) == std::string::npos);
    }
    {
        RenderOptions o;
        chk("숨길 것이 없으면 아무것도 쓰지 않는다",
            r.generateScript("/x/d3plot", "/x/out.png", o).find("-M ") == std::string::npos);
    }
    std::printf("\n%s — 실패 %d건\n", g_failed ? "FAIL" : "PASS", g_failed);
    return g_failed ? 1 : 0;
}
