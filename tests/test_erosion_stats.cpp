// 침식(삭제) 요소가 파트·표면 통계에 0 으로 섞이지 않는지 실덱으로 확인하는 시험.
//
// 빌드·실행:
//   cmake --build build -j4 --target unified_analyzer
//   g++ -std=c++17 -O2 -I include tests/test_erosion_stats.cpp \
//       build/libkood3plot.a -fopenmp -lz -o /tmp/t_erosion && /tmp/t_erosion
//
// 덱: /data/koopark/Test_DTMIN_erode/dtmin_0p1 (MDLOPT=2, 마지막 상태에서 solid 6개 삭제)
//
// 종료 코드: 0 통과 · 1 실패 · 77 덱이 없어 건너뜀(통과가 아니라 '검증 못 함').
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/SinglePassAnalyzer.hpp"
#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
#include <cstdio>
#include <cmath>
#include <map>
#include <set>
#include <string>
#include <vector>

using namespace kood3plot;
using namespace kood3plot::analysis;

static int fails = 0;

static void chk(const char* name, bool ok, const std::string& detail) {
    if (!ok) ++fails;
    printf("  %s %-46s %s\n", ok ? "OK " : "NG ", name, detail.c_str());
}

static void chk_close(const char* name, double got, double want, double tol) {
    const double err = std::abs(got - want);
    char buf[256];
    snprintf(buf, sizeof(buf), "got=%.10g want=%.10g err=%.3g", got, want, err);
    chk(name, err <= tol, buf);
}

static double vonMisesOf(const std::vector<double>& sd, size_t base) {
    const double sxx = sd[base+0], syy = sd[base+1], szz = sd[base+2];
    const double sxy = sd[base+3], syz = sd[base+4], szx = sd[base+5];
    const double a = sxx - syy, b = syy - szz, c = szz - sxx;
    return std::sqrt(0.5 * (a*a + b*b + c*c) + 3.0 * (sxy*sxy + syz*syz + szx*szx));
}

int main(int argc, char** argv) {
    const std::string path = (argc > 1) ? argv[1]
                                        : "/data/koopark/Test_DTMIN_erode/dtmin_0p1/d3plot";

    D3plotReader reader(path);
    if (reader.open() != ErrorCode::SUCCESS) {
        printf("[SKIP] 덱을 열 수 없음: %s — 검증 못 함\n", path.c_str());
        return 77;
    }

    const auto& cd = reader.get_control_data();
    printf("[준비] NEL8=%d NV3D=%d MDLOPT=%d states=%zu\n",
           cd.NEL8, cd.NV3D, cd.MDLOPT, reader.get_num_states());
    if (cd.MDLOPT != 2) {
        printf("[SKIP] MDLOPT != 2 — 삭제 테이블이 없는 덱, 검증 못 함\n");
        return 77;
    }

    auto mesh = reader.read_mesh();

    // 메모리 절약: 전체 상태를 읽은 뒤 마지막 두 상태만 남긴다.
    std::vector<data::StateData> all = reader.read_all_states();
    if (all.size() < 2) { printf("[SKIP] 상태가 2개 미만 — 검증 못 함\n"); return 77; }
    std::vector<data::StateData> states;
    states.push_back(all[all.size() - 2]);
    states.push_back(all.back());
    all.clear();
    all.shrink_to_fit();

    const auto& last = states.back();
    printf("[준비] 마지막 상태 t=%.6g 삭제 solid=%zu 개\n",
           last.time, last.deleted_solids.size());

    printf("\n[A] 삭제 테이블이 실제로 차 있는지 (이 시험의 전제)\n");
    chk("deleted_solids 비어 있지 않음", !last.deleted_solids.empty(),
        "n=" + std::to_string(last.deleted_solids.size()));
    if (last.deleted_solids.empty()) {
        printf("\n[FAIL] 전제 불충족 — 삭제 요소가 없는 덱\n");
        return 1;
    }

    // deleted_solids 는 solid 배열 내 1-based 순번
    std::set<size_t> dead;
    for (int32_t ord : last.deleted_solids) dead.insert(static_cast<size_t>(ord) - 1);

    const size_t nv3d = static_cast<size_t>(cd.NV3D);
    const size_t nel8 = static_cast<size_t>(std::abs(cd.NEL8));

    printf("\n[B] 삭제 요소의 응력 워드가 정말 0 인지 (0 이 통계에 섞이는 경로)\n");
    {
        bool all_zero = true;
        for (size_t ei : dead) {
            const size_t base = ei * nv3d;
            if (base + 6 > last.solid_data.size()) { all_zero = false; break; }
            if (vonMisesOf(last.solid_data, base) != 0.0) { all_zero = false; break; }
        }
        chk("삭제 요소 σ_vm == 0", all_zero, "삭제 " + std::to_string(dead.size()) + "개");
    }

    // ---- 독립 계산: 살아 있는 요소만으로 파트별 최소·평균 ----
    struct Oracle { double min_alive = 1e300; double sum_alive = 0.0; size_t n_alive = 0;
                    double min_naive = 1e300; int32_t min_alive_elem = 0; };
    std::map<int32_t, Oracle> oracle;
    for (size_t ei = 0; ei < nel8 && ei < mesh.solid_parts.size(); ++ei) {
        const size_t base = ei * nv3d;
        if (base + 6 > last.solid_data.size()) continue;
        const double vm = vonMisesOf(last.solid_data, base);
        auto& o = oracle[mesh.solid_parts[ei]];
        if (vm < o.min_naive) o.min_naive = vm;
        if (dead.count(ei)) continue;
        if (vm < o.min_alive) {
            o.min_alive = vm;
            o.min_alive_elem = (ei < mesh.real_solid_ids.size())
                                   ? mesh.real_solid_ids[ei]
                                   : static_cast<int32_t>(ei + 1);
        }
        o.sum_alive += vm;
        ++o.n_alive;
    }

    printf("\n[C] 침식이 실제로 통계를 바꾸는 파트가 있는지 (시험의 유효성)\n");
    {
        int changed = 0;
        for (const auto& kv : oracle) {
            if (kv.second.min_naive == 0.0 && kv.second.min_alive > 0.0) ++changed;
        }
        chk("삭제 포함 시 Min 이 0 으로 붕괴하는 파트 존재", changed > 0,
            "파트 " + std::to_string(changed) + "개");
    }

    // ---- 분석기 실행 ----
    AnalysisConfig cfg;
    cfg.d3plot_path = path;
    cfg.analyze_stress = true;
    cfg.analyze_strain = false;
    SinglePassAnalyzer sp(reader);
    auto res = sp.analyzeWithStates(cfg, states, nullptr);

    printf("\n[D] 파트별 Min/Avg 가 '살아 있는 요소' 기준과 일치하는지\n");
    for (const auto& hist : res.stress_history) {
        auto it = oracle.find(hist.part_id);
        if (it == oracle.end() || it->second.n_alive == 0) continue;
        const auto& o = it->second;
        const auto& tp = hist.data.back();
        const std::string tag = "part " + std::to_string(hist.part_id);
        chk_close((tag + " Min").c_str(), tp.min_value, o.min_alive,
                  std::max(1e-9, std::abs(o.min_alive) * 1e-12));
        chk_close((tag + " Avg").c_str(), tp.avg_value, o.sum_alive / o.n_alive,
                  std::max(1e-9, std::abs(o.sum_alive / o.n_alive) * 1e-12));
        chk((tag + " Min 요소가 삭제 요소가 아님").c_str(),
            tp.min_element_id == o.min_alive_elem,
            "got=" + std::to_string(tp.min_element_id) +
            " want=" + std::to_string(o.min_alive_elem));
    }

    printf("\n%s  실패 %d 건\n", fails ? "[FAIL]" : "[PASS]", fails);
    return fails ? 1 : 0;
}
