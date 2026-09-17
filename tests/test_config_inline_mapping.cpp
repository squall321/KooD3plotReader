// 이 수제 YAML 파서가 못 읽는 인라인 매핑(`surface: { ... }`)을 만났을 때
// 그 잡이 기본값으로 조용히 도는 일이 없는지 보는 시험.
//
// 예전에는 경고 한 줄만 찍고 잡을 그대로 통과시켜, 사용자가 붙인 이름표
// (TopSurf/BotSurf)를 단 채 둘 다 기본 방향(-Z, 45°)으로 돌아 완전히 같은
// 값이 나왔다. 산출물에는 그 사실을 알릴 표식이 없었다.
//
// 빌드·실행:
//   g++ -std=c++17 -O2 -I include tests/test_config_inline_mapping.cpp \
//       .work/build/libkood3plot.a -fopenmp -lz -o .work/t_cfg && .work/t_cfg
#include "kood3plot/analysis/UnifiedConfigParser.hpp"

#include <cstdio>
#include <string>

using namespace kood3plot::analysis;

namespace {

int g_failed = 0;

void chk(const char* what, bool ok, const std::string& detail) {
    if (!ok) ++g_failed;
    std::printf("  %s %-52s %s\n", ok ? "OK " : "NG ", what, detail.c_str());
}

}  // namespace

int main() {
    std::printf("[A] 인라인 매핑을 쓴 잡은 기본값으로 돌지 않고 빠진다\n");
    {
        const std::string yaml =
            "input:\n"
            "  d3plot: /tmp/none/d3plot\n"
            "analysis:\n"
            "  surface_defaults: false\n"
            "analysis_jobs:\n"
            "  - name: TopSurf\n"
            "    type: surface_stress\n"
            "    surface: { direction: [0, 0, 1], angle: 30 }\n"
            "  - name: BotSurf\n"
            "    type: surface_stress\n"
            "    surface: { direction: [0, 0, -1], angle: 30 }\n"
            "  - name: Plain\n"
            "    type: von_mises\n";

        UnifiedConfig config;
        UnifiedConfigParser::loadFromYAMLString(yaml, config);

        chk("멀쩡한 잡만 남는다 (1개)", config.analysis_jobs.size() == 1,
            "n=" + std::to_string(config.analysis_jobs.size()));
        if (config.analysis_jobs.size() == 1) {
            chk("남은 잡은 Plain", config.analysis_jobs[0].name == "Plain",
                config.analysis_jobs[0].name);
        }
        chk("사유가 설정에 남는다 (2건)", config.config_issues.size() == 2,
            "n=" + std::to_string(config.config_issues.size()));
        bool names_in_reason = false;
        if (config.config_issues.size() == 2) {
            names_in_reason =
                config.config_issues[0].find("TopSurf") != std::string::npos &&
                config.config_issues[1].find("BotSurf") != std::string::npos;
        }
        chk("사유에 빠진 잡 이름이 들어 있다", names_in_reason,
            config.config_issues.empty() ? "(없음)" : config.config_issues[0]);
    }

    std::printf("\n[B] 인라인 매핑이 없으면 아무 것도 달라지지 않는다 (회귀 없음)\n");
    {
        const std::string yaml =
            "input:\n"
            "  d3plot: /tmp/none/d3plot\n"
            "analysis:\n"
            "  surface_defaults: false\n"
            "analysis_jobs:\n"
            "  - name: TopSurf\n"
            "    type: surface_stress\n"
            "    surface:\n"
            "      direction: [0, 0, 1]\n"
            "      angle: 30\n";

        UnifiedConfig config;
        UnifiedConfigParser::loadFromYAMLString(yaml, config);

        chk("잡이 그대로 남는다", config.analysis_jobs.size() == 1,
            "n=" + std::to_string(config.analysis_jobs.size()));
        chk("사유 없음", config.config_issues.empty(),
            "n=" + std::to_string(config.config_issues.size()));
        if (config.analysis_jobs.size() == 1) {
            const auto& s = config.analysis_jobs[0].surface;
            chk("방향이 +Z 로 읽힌다", s.direction.z > 0.5,
                std::to_string(s.direction.x) + "," + std::to_string(s.direction.y) +
                    "," + std::to_string(s.direction.z));
            chk("각도가 30 으로 읽힌다", s.angle == 30.0,
                std::to_string(s.angle));
        }
    }

    std::printf("\n%s  실패 %d 건\n", g_failed ? "[FAIL]" : "[PASS]", g_failed);
    return g_failed ? 1 : 0;
}
