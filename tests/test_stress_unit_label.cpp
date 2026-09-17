// 응력 시계열의 unit 라벨이 덱 단위계를 단정하지 않는가 — 실덱 회귀
//
// 잡으려는 결함: SinglePassAnalyzer 가 stress/max_principal/min_principal 의
// unit 을 무조건 "MPa" 로 박았다. d3plot 은 단위계를 싣지 않는다 — kg-mm-ms
// 덱이면 응력은 GPa, SI 덱이면 Pa 다. 실덱
// /data/battery_study/case_01_phase1_stacked_tier-1 은 피크가 0.23 인데
// "0.23 MPa" 로 읽히면 실제 230 MPa 를 3자리 틀리게 본다.
//
// 라벨은 "모른다" 를 말해야 한다. 변형률 계열이 이미 빈 문자열(무차원)로
// 구분되고 있으므로, 응력은 '미상' 을 뜻하는 별도 라벨을 쓴다.
//
// Run:
//   g++ -std=c++17 -O2 -I include tests/test_stress_unit_label.cpp \
//       build/libkood3plot.a -fopenmp -lz -o /tmp/t_unit
//   /tmp/t_unit [d3plot 경로]
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
#include "kood3plot/analysis/SinglePassAnalyzer.hpp"
#include <cstdio>
#include <string>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

static int fails = 0;

static void checkUnit(const char* label, const std::vector<PartTimeSeriesStats>& series,
                      const char* want) {
    if (series.empty()) {
        printf("  -- %-28s 계열 없음 (건너뜀)\n", label);
        return;
    }
    bool good = true;
    for (const auto& s : series) if (s.unit != want) good = false;
    if (!good) ++fails;
    printf("  %s %-28s unit=\"%s\" (기대 \"%s\")\n",
           good ? "OK " : "NG ", label, series[0].unit.c_str(), want);
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
    printf("응력 unit 라벨이 덱 단위계를 단정하지 않는가\n");
    checkUnit("von_mises", res.stress_history, "deck_units");
    checkUnit("max_principal_stress", res.max_principal_history, "deck_units");
    checkUnit("min_principal_stress", res.min_principal_history, "deck_units");
    printf("변형률은 무차원이라 빈 문자열 그대로여야 한다\n");
    checkUnit("eff_plastic_strain", res.strain_history, "");
    checkUnit("von_mises_strain", res.vm_strain_history, "");

    printf("\n%s  (%d fail)\n", fails ? "실패" : "전부 통과", fails);
    return fails ? 1 : 0;
}
