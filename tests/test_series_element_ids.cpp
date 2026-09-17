// SinglePassAnalyzer 시계열의 요소 ID 두 컬럼이 모두 실제 ID 인가 — 실덱 회귀
//
// 잡으려는 결함: σ1 계열은 max_element_id 만, σ3 계열은 min_element_id 만
// 채워졌고 반대쪽은 기본값 0 이 그대로 나갔다. ε_p·ε_vm·ε1 은 max 만, ε3 은
// min 만 채워졌다. writePartCSV 는 두 컬럼을 다 쓰므로 CSV 에 "0" 이 실재
// 요소 ID 처럼 실렸고(LS-DYNA 요소 ID 는 1 부터라 0 은 없다), 구 리포트는
// 모든 계열에서 Max_Element_ID 를 읽어 σ3·ε3 계열이 전부 0 이 됐다.
//
// 실행:
//   g++ -std=c++17 -O2 -I include tests/test_series_element_ids.cpp \
//       build/libkood3plot.a -fopenmp -lz -o /tmp/t_eid
//   /tmp/t_eid [d3plot 경로]
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
#include "kood3plot/analysis/SinglePassAnalyzer.hpp"
#include <cstdio>
#include <string>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

static int fails = 0;

// 데이터가 있는 계열이라면 두 ID 컬럼이 모두 실제 요소 ID(>0) 여야 한다.
static void checkSeries(const char* label, const std::vector<PartTimeSeriesStats>& series) {
    if (series.empty()) {
        printf("  -- %-28s 계열 없음 (건너뜀)\n", label);
        return;
    }
    size_t zero_max = 0, zero_min = 0, total = 0;
    for (const auto& s : series) {
        for (const auto& tp : s.data) {
            ++total;
            if (tp.max_element_id == 0) ++zero_max;
            if (tp.min_element_id == 0) ++zero_min;
        }
    }
    bool good = (zero_max == 0 && zero_min == 0);
    if (!good) ++fails;
    printf("  %s %-28s 시점 %zu — max_id=0 %zu건, min_id=0 %zu건\n",
           good ? "OK " : "NG ", label, total, zero_max, zero_min);
}

int main(int argc, char** argv) {
    const std::string path = (argc > 1)
        ? argv[1]
        : "/data/battery_study/case_01_phase1_stacked_tier-1/d3plot";

    D3plotReader r(path);
    if (r.open() != ErrorCode::SUCCESS) {
        printf("d3plot 열기 실패: %s\n", path.c_str());
        return 2;
    }

    SinglePassAnalyzer sp(r);
    AnalysisConfig cfg;
    cfg.d3plot_path = path;
    cfg.analyze_stress = true;
    cfg.analyze_strain = true;
    AnalysisResult res = sp.analyzeParallel(cfg);

    printf("\n=== %s ===\n", path.c_str());
    printf("파트 시계열의 Max/Min_Element_ID 가 둘 다 실재 ID 인가\n");
    checkSeries("von_mises", res.stress_history);
    checkSeries("max_principal_stress", res.max_principal_history);
    checkSeries("min_principal_stress", res.min_principal_history);
    checkSeries("eff_plastic_strain", res.strain_history);
    checkSeries("von_mises_strain", res.vm_strain_history);
    checkSeries("max_principal_strain", res.max_principal_strain_history);
    checkSeries("min_principal_strain", res.min_principal_strain_history);

    printf("\n%s  (%d fail)\n", fails ? "실패" : "전부 통과", fails);
    return fails ? 1 : 0;
}
