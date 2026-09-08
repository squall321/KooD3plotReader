// 실 d3plot 로 핫스팟 군집 e2e
#include "kood3plot/D3plotReader.hpp"
#include "kood3plot/analysis/TimeHistoryAnalyzer.hpp"
#include "kood3plot/analysis/SinglePassAnalyzer.hpp"
#include "kood3plot/analysis/HotspotClusterAnalyzer.hpp"
#include <cstdio>
#include <map>
#include <chrono>
using namespace kood3plot;
using namespace kood3plot::analysis;

int main(int argc,char**argv){
    const char* path = argv[1];
    double topp = (argc>2)? atof(argv[2]) : 3.0;

    D3plotReader r(path);
    if (r.open()!=ErrorCode::SUCCESS){printf("open fail\n");return 1;}

    auto t0=std::chrono::steady_clock::now();
    SinglePassAnalyzer sp(r);
    AnalysisConfig cfg;
    cfg.analyze_stress = true; cfg.analyze_strain = true;
    cfg.hotspot_enabled = true;
    auto res = sp.analyzeParallel(cfg);
    auto t1=std::chrono::steady_clock::now();

    const auto& emax = sp.elementMaxVonMises();
    printf("\n=== %s ===\n", path);
    printf("분석 %.1f s, 요소별 최대 배열 %zu\n",
           std::chrono::duration<double>(t1-t0).count(), emax.size());
    if (emax.empty()){ printf("🔴 배열 비어 있음\n"); return 1; }

    // 배열 건전성
    size_t unrec=0; double mn=1e30,mx=-1e30;
    for (double v : emax){ if(v<0) ++unrec; else { if(v<mn)mn=v; if(v>mx)mx=v; } }
    printf("미기록 %zu, 기록된 값 범위 %.4g ~ %.4g\n", unrec, mn, mx);

    auto mesh = r.read_mesh();
    std::map<int32_t,std::string> names;
    for (int32_t pid : mesh.solid_parts)
        if (!names.count(pid)) names[pid] = "Part_"+std::to_string(pid);

    HotspotClusterConfig hc;
    hc.enabled=true; hc.top_percent=topp; hc.distance_factor=1.5;
    hc.min_cluster_elements=5; hc.max_clusters_per_part=5;

    auto t2=std::chrono::steady_clock::now();
    auto hs = computeHotspotClusters(mesh, emax, sp.elementMaxVonMisesTime(),
                                     sp.elementMaxStrain(), names, hc);
    auto t3=std::chrono::steady_clock::now();
    printf("군집 %.3f s, 파트 %zu\n\n", std::chrono::duration<double>(t3-t2).count(), hs.size());

    int shown=0;
    for (const auto& p : hs){
        if (p.clusters.empty()) continue;
        if (shown++ >= 4) break;
        printf("파트 %d (%s)  전체 %d, 선별 %d, 군집소속 %d\n",
               p.part_id, p.part_name.c_str(),
               p.element_count_total, p.element_count_selected, p.element_count_clustered);
        printf("  대표크기 %.4g, 임계거리 %.4g, 컷값 %.4g, 변형률 %s\n",
               p.element_size_ref, p.distance_threshold, p.threshold_value,
               p.strain_available?"있음":"없음");
        for (const auto& c : p.clusters){
            printf("   #%d  n=%-4d 중심(%.3f, %.3f, %.3f) R=%.4g Rrms=%.4g "
                   "V=%.4g  σ평균=%.4g σ최대=%.4g  peak elem %d @ %.6g\n",
                   c.rank, c.element_count, c.center[0],c.center[1],c.center[2],
                   c.radius_enclosing, c.radius_rms, c.volume,
                   c.stress_mean, c.stress_max, c.peak_element_id, c.peak_time);
        }
        printf("\n");
    }
    // 건전성 단언
    int bad=0;
    for (const auto& p : hs) for (const auto& c : p.clusters){
        if (!(c.stress_max >= c.stress_mean)) { printf("🔴 최대<평균: 파트%d #%d\n",p.part_id,c.rank); ++bad; }
        if (!(c.radius_enclosing >= c.radius_rms)) { printf("🔴 포함반경<RMS: 파트%d #%d\n",p.part_id,c.rank); ++bad; }
        if (!(c.volume > 0)) { printf("🔴 부피<=0\n"); ++bad; }
        if (c.element_count < hc.min_cluster_elements) { printf("🔴 최소크기 위반\n"); ++bad; }
    }
    printf("건전성 위반: %d 건 %s\n", bad, bad?"🔴":"✅");
    return bad?1:0;
}
