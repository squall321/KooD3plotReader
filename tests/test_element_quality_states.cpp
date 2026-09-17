// 요소 품질이 전 상태를 보는지(=표본 10개로 피크를 놓치지 않는지) 확인하는 시험.
//
// 빌드·실행:
//   cmake --build build -j4 --target unified_analyzer
//   g++ -std=c++17 -O2 -I include tests/test_element_quality_states.cpp \
//       build/libkood3plot.a -fopenmp -lz -o /tmp/t_quality && /tmp/t_quality
//
// 덱: /data/battery_study/case_01_phase1_stacked_tier-1 (22상태, 셸+두꺼운셸+솔리드)
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/UnifiedAnalyzer.hpp"
#include <cstdio>
#include <cmath>
#include <set>
#include <string>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

static int fails = 0;

static void chk(const char* name, bool ok, const std::string& detail) {
    if (!ok) ++fails;
    printf("  %s %-44s %s\n", ok ? "OK " : "NG ", name, detail.c_str());
}

/// 수정 전 표본 규칙 — 등간격 10개
static std::set<size_t> oldSampleIndices(size_t n_states) {
    std::set<size_t> s;
    const size_t n_samples = std::min<size_t>(n_states, 10);
    if (n_samples <= 1) {
        s.insert(0);
        if (n_states > 1) s.insert(n_states - 1);
    } else {
        for (size_t i = 0; i < n_samples; ++i) s.insert(i * (n_states - 1) / (n_samples - 1));
    }
    return s;
}

int main(int argc, char** argv) {
    const std::string deck = (argc > 1)
        ? argv[1]
        : "/data/battery_study/case_01_phase1_stacked_tier-1/d3plot";

    size_t n_states = 0;
    {
        D3plotReader probe(deck);
        if (probe.open() != ErrorCode::SUCCESS) {
            printf("[SKIP] 덱을 열 수 없음: %s\n", deck.c_str());
            return 0;
        }
        n_states = probe.get_num_states();
    }
    printf("[준비] 상태 %zu개\n", n_states);
    if (n_states < 12) {
        printf("[SKIP] 표본 10개와 구분되지 않는 짧은 덱\n");
        return 0;
    }

    UnifiedConfig cfg;
    cfg.d3plot_path = deck;
    cfg.surface_defaults = false;
    cfg.verbose = false;
    AnalysisJob q;
    q.name = "Quality";
    q.type = AnalysisJobType::ELEMENT_QUALITY;
    cfg.analysis_jobs.push_back(q);

    UnifiedAnalyzer analyzer;
    auto res = analyzer.analyze(cfg);

    printf("\n[A] 시점 개수 — 상태 수와 같아야 한다\n");
    {
        size_t bad = 0;
        for (const auto& qs : res.element_quality) {
            if (qs.data.size() != n_states) ++bad;
        }
        chk("모든 파트의 data[] 길이 == 상태 수", bad == 0,
            "파트 " + std::to_string(res.element_quality.size()) +
            "개 중 어긋남 " + std::to_string(bad) + "개" +
            (res.element_quality.empty() ? "" :
             " (첫 파트 " + std::to_string(res.element_quality.front().data.size()) + "점)"));
    }

    printf("\n[B] 표본 10개였다면 놓쳤을 극값이 실제로 있는지\n");
    {
        const std::set<size_t> sampled = oldSampleIndices(n_states);
        int missed_parts = 0;
        std::string first;
        for (const auto& qs : res.element_quality) {
            if (qs.data.size() != n_states) continue;
            double full_ar = -1e300, samp_ar = -1e300;
            for (size_t i = 0; i < qs.data.size(); ++i) {
                if (!qs.data[i].aspect_measured) continue;
                const double v = qs.data[i].aspect_ratio_max;
                if (v > full_ar) full_ar = v;
                if (sampled.count(i) && v > samp_ar) samp_ar = v;
            }
            if (full_ar > samp_ar && full_ar > 0) {
                ++missed_parts;
                if (first.empty()) {
                    char buf[192];
                    snprintf(buf, sizeof(buf),
                             "파트 %d peak_AR 전상태=%.6g 표본10=%.6g",
                             qs.part_id, full_ar, samp_ar);
                    first = buf;
                }
            }
        }
        chk("표본 10개가 과소평가하는 파트가 있음", missed_parts > 0,
            std::to_string(missed_parts) + "개" + (first.empty() ? "" : " — " + first));
    }

    printf("\n%s  실패 %d 건\n", fails ? "[FAIL]" : "[PASS]", fails);
    return fails ? 1 : 0;
}
