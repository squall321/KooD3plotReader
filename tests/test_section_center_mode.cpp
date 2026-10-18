// 단면 자를 자리(center_mode) YAML 파싱 — 오타가 조용히 기본값으로 떨어지지 않는지
//
// auto_center 는 형상의 AABB 가운데를 자른다. 형상 가운데가 응력 피크가 있는
// 자리라는 보장은 없다 — 실측(400상태 덱)에서 AABB 는 z=-10.025, σ_vm 피크
// (310.4 @state 22)는 z=-2.300 으로 7.7mm 비켜 갔고, AABB 단면은 점 몇 개뿐인
// 거의 빈 화면이었다. 컬러바는 그대로 310.4 를 띄우므로 "여긴 괜찮네" 로 읽힌다.
//
// center_mode: peak 가 그 자리를 피크로 옮긴다. 그래서 **오타가 조용히 aabb 로
// 떨어지면 안 된다** — 피크를 자르라고 쓴 사람이 빈 화면을 받고도 모른다.
//
// 빌드·실행:
//   cd build && make test_section_center_mode && ./tests/test_section_center_mode
#include "kood3plot/section_render/SectionViewConfig.hpp"

#include <cstdio>
#include <string>

using kood3plot::section_render::SectionViewConfig;

namespace {

int g_failed = 0;

void chk(const char* what, bool ok, const std::string& detail) {
    if (!ok) ++g_failed;
    std::printf("  %s %-52s %s\n", ok ? "OK " : "NG ", what, detail.c_str());
}

SectionViewConfig parse(const std::string& extra) {
    SectionViewConfig c;
    const std::string yaml =
        "plane:\n  axis: z\nauto_center: true\n" + extra + "field: von_mises\n";
    c.loadFromString(yaml);
    return c;
}

const char* name(SectionViewConfig::CenterMode m) {
    return m == SectionViewConfig::CenterMode::FieldPeak ? "FieldPeak" : "AabbCenter";
}

}  // namespace

int main() {
    std::printf("[A] 기본값은 종전 동작(AabbCenter) — 조용히 그림이 바뀌지 않는다\n");
    {
        SectionViewConfig c;
        chk("기본 center_mode", c.center_mode == SectionViewConfig::CenterMode::AabbCenter,
            name(c.center_mode));
        SectionViewConfig p = parse("");
        chk("키를 안 쓴 YAML", p.center_mode == SectionViewConfig::CenterMode::AabbCenter,
            name(p.center_mode));
    }

    std::printf("[B] peak 를 적으면 피크로 간다\n");
    for (const char* v : {"peak", "field_peak", "PEAK", "Peak"}) {
        SectionViewConfig c = parse(std::string("center_mode: ") + v + "\n");
        chk(v, c.center_mode == SectionViewConfig::CenterMode::FieldPeak, name(c.center_mode));
    }

    std::printf("[C] aabb 를 적으면 형상 가운데\n");
    for (const char* v : {"aabb", "aabb_center", "center"}) {
        SectionViewConfig c = parse(std::string("center_mode: ") + v + "\n");
        chk(v, c.center_mode == SectionViewConfig::CenterMode::AabbCenter, name(c.center_mode));
    }

    std::printf("[D] 오타는 경고를 찍고 aabb 로 — 위 stderr 에 WARNING 이 보여야 한다\n");
    {
        SectionViewConfig c = parse("center_mode: pek\n");
        chk("pek → aabb", c.center_mode == SectionViewConfig::CenterMode::AabbCenter,
            name(c.center_mode));
    }

    std::printf("%s (%d 실패)\n", g_failed ? "FAILED" : "PASSED", g_failed);
    return g_failed ? 1 : 0;
}
