// LS-PrePost 명령 스크립트의 카메라 타겟 맞춤(fit_highlight) — 켰을 때의 줄 순서와, 껐을 때 한 글자도 달라지지 않는지 보는 시험
//
// 화면은 단면을 넣는 순간(`splane projectview`) 보이는 파트의 상자에 맞는다(실측 2026-11-20, LS-PrePost 4.12 배치).
// 그래서 순서가 전부다 — 방향을 정하는 `ac` 는 모델 전체가 보일 때, 단면은 타겟만 보일 때, 영상은 다시 전체가 보일 때.
// 틀려도 영상은 나온다(조용한 실패):
//   - 타겟만 켠 뒤 단면 앞에 `ac` 가 끼면 방향이 타겟 단면의 긴 변을 따라 돌아, 기본 영상과 다른 방향이 된다.
//   - `selectpart reverse` 는 `-M` 숨김을 되살린다. 뒤집은 뒤 다시 숨기지 않으면 카메라가 바닥까지 맞춘다.
//   - `selectpart all on` 도 숨김을 되돌린다. 복원한 뒤 다시 숨기지 않으면 바닥이 영상에 돌아온다.
//
// 빌드·실행:
//   cd build && make test_lspp_view_fit && ./tests/test_lspp_view_fit
#include "kood3plot/render/LSPrePostRenderer.h"

#include <cstdio>
#include <string>

using kood3plot::render::LSPrePostRenderer;
using kood3plot::render::RenderOptions;
using kood3plot::render::SectionPlane;
using kood3plot::render::ViewOrientation;

namespace {

int g_failed = 0;

void chk(const char* what, bool ok, const std::string& detail = "") {
    if (!ok) ++g_failed;
    std::printf("  %s %-62s %s\n", ok ? "OK " : "NG ", what, detail.c_str());
}

size_t count(const std::string& s, const std::string& what) {
    size_t n = 0;
    for (size_t p = s.find(what); p != std::string::npos; p = s.find(what, p + what.size())) ++n;
    return n;
}

std::string without(std::string s, const std::string& what) {
    const size_t p = s.find(what);
    if (p != std::string::npos) s.erase(p, what.size());
    return s;
}

// 실측한 경우 그대로 — 타겟 6, 숨김 23(솔리드), Z 단면, 1280×720, 보폭 400
RenderOptions measured() {
    RenderOptions o;
    o.view = ViewOrientation::TOP;
    o.highlight_parts = {6};
    o.hidden_parts = {23};
    o.hidden_kinds = {'H'};
    o.section_planes.push_back(SectionPlane({4.0, 49.5, -1.05}, {0.0, 0.0, 1.0}));
    o.create_animation = true;
    o.fps = 24;
    o.image_width = 1280;
    o.image_height = 720;
    o.state_step = 400;
    return o;
}

}  // namespace

int main() {
    LSPrePostRenderer r("/nonexistent/lsprepost");

    const std::string fit_block =
        "$# Fit view to target part(s)\n"
        "genselect target part\n"
        "selectpart select 1\n"
        "genselect part remove part 6/0\n"
        "selectpart reverse\n"
        "selectpart select 0\n"
        "$# Hide parts (floor etc.)\n"
        "-M 23\n"
        "-M H23\n"
        "\n";
    const std::string margin_block =
        "zin -0.300000 -0.300000 1.300000 1.300000\n"
        "genselect target part\n"
        "selectpart select 1\n"
        "selectpart all on\n"
        "selectpart select 0\n"
        "$# Hide parts (floor etc.)\n"
        "-M 23\n"
        "-M H23\n"
        "\n";

    std::printf("[1] 켰을 때 — 실측한 순서 그대로\n");
    {
        RenderOptions o = measured();
        const std::string off = r.generateScript("/x/d3plot", "/x/out", o);
        o.fit_highlight = true;
        const std::string on = r.generateScript("/x/d3plot", "/x/out", o);

        chk("타겟만 남기는 덩이가 시점 `ac` 바로 뒤 · 단면 바로 앞에 온다",
            on.find("$# Set view orientation\ntop\nac\n\n" + fit_block + "$# Apply section planes (1 planes)\n")
                != std::string::npos);
        chk("여백 · 복원 · 숨김 덩이가 단면 `ac` 바로 뒤 · 영상 바로 앞에 온다",
            on.find("splane projectview\nsplane drawcut\nac\n\n" + margin_block + "$# Generate movie output\n")
                != std::string::npos);

        const size_t fit = on.find("$# Fit view to target part(s)\n");
        const size_t sec = on.find("splane dep0 ");
        chk("타겟만 남긴 뒤 단면 전에 `ac` 가 없다(있으면 방향이 타겟을 따라 돈다)",
            fit != std::string::npos && sec != std::string::npos && fit < sec &&
            on.substr(fit, sec - fit).find("\nac\n") == std::string::npos);
        const size_t rev = on.find("selectpart reverse\n", fit);
        const size_t hide = on.find("-M 23\n", rev);
        chk("뒤집은 뒤 · 단면 전에 다시 숨긴다(안 그러면 바닥까지 맞춘다)",
            rev != std::string::npos && rev < sec && hide != std::string::npos && hide < sec);
        const size_t all_on = on.rfind("selectpart all on\n");
        const size_t zin = on.find("zin ");
        const size_t movie = on.find("\nmovie MP4/H264 ");
        chk("단면 → 여백 → 전체 복원 → 숨김 → 영상",
            zin != std::string::npos && all_on != std::string::npos && movie != std::string::npos &&
            sec < zin && zin < all_on && on.find("-M 23\n", all_on) < movie);
        chk("숨김을 세 번 쓴다(색 뒤 · 뒤집은 뒤 · 복원 뒤 — 형식 접두어 꼴 포함)",
            count(on, "\n-M 23\n") == 3 && count(on, "\n-M H23\n") == 3,
            std::to_string(count(on, "\n-M 23\n")) + " · " + std::to_string(count(on, "\n-M H23\n")));

        chk("끈 것 = 켠 것에서 두 덩이만 뺀 것(나머지는 한 글자도 같다)",
            without(without(on, fit_block), margin_block) == off && on != off);
        chk("끄면 맞춤 줄이 없다",
            off.find("Fit view") == std::string::npos && off.find("zin ") == std::string::npos);
    }

    std::printf("[2] 여백 — `zin m m 1-m 1-m`\n");
    {
        RenderOptions o = measured();
        o.fit_highlight = true;
        o.fit_margin = 0.0;
        chk("0 = 꼭 맞게", r.generateScript("/x/d3plot", "/x/out", o)
                               .find("\nzin 0.000000 0.000000 1.000000 1.000000\n") != std::string::npos);
        o.fit_margin = -4.0;
        chk("-4 = 아주 넓게", r.generateScript("/x/d3plot", "/x/out", o)
                                  .find("\nzin -4.000000 -4.000000 5.000000 5.000000\n") != std::string::npos);
    }

    std::printf("[3] 타겟 여럿 · 숨김 없음\n");
    {
        RenderOptions o = measured();
        o.fit_highlight = true;
        o.highlight_parts = {6, 8};
        o.hidden_parts.clear();
        o.hidden_kinds.clear();
        const std::string sc = r.generateScript("/x/d3plot", "/x/out", o);
        chk("타겟마다 한 줄씩 남긴다",
            sc.find("$# Fit view to target part(s)\ngenselect target part\nselectpart select 1\n"
                    "genselect part remove part 6/0\ngenselect part remove part 8/0\n"
                    "selectpart reverse\nselectpart select 0\n\n$# Apply section planes") != std::string::npos);
        chk("숨길 것이 없으면 숨김 줄도 없다", sc.find("-M ") == std::string::npos &&
            sc.find("Hide parts") == std::string::npos);
        chk("복원은 그대로 한다", sc.find("zin -0.300000 -0.300000 1.300000 1.300000\ngenselect target part\n"
                                          "selectpart select 1\nselectpart all on\nselectpart select 0\n\n"
                                          "$# Generate movie output\n") != std::string::npos);
    }

    std::printf("[4] 쓰이지 않는 조합 — 켜도 끈 것과 같다\n");
    {
        RenderOptions o = measured();
        o.highlight_parts.clear();
        const std::string off = r.generateScript("/x/d3plot", "/x/out", o);
        o.fit_highlight = true;
        chk("타겟이 없으면 그대로", r.generateScript("/x/d3plot", "/x/out", o) == off);

        RenderOptions p = measured();
        p.section_planes.clear();
        const std::string off2 = r.generateScript("/x/d3plot", "/x/out", p);
        p.fit_highlight = true;
        chk("단면이 없으면 그대로(맞춤은 단면을 넣는 순간에만 일어난다)",
            r.generateScript("/x/d3plot", "/x/out", p) == off2);
    }

    std::printf("\n%s — 실패 %d건\n", g_failed ? "FAIL" : "PASS", g_failed);
    return g_failed ? 1 : 0;
}
