// 기준량 확장(σ1·σ3) 검증 — 부호·방향·NaN 표식·가중 중심을 해석 답과 대조
#include "kood3plot/analysis/HotspotClusterAnalyzer.hpp"
#include <cstdio>
#include <cmath>
#include <map>
#include <vector>
using namespace kood3plot;
using namespace kood3plot::analysis;

static int fails = 0;
static void chk(const char* n, double g, double w, double t) {
    double e = std::abs(g - w); bool ok = e <= t; if (!ok) ++fails;
    printf("  %s %-46s got=%.8g want=%.8g err=%.2g\n", ok?"OK ":"NG ", n, g, w, e);
}
static void chkb(const char* n, bool ok) {
    if (!ok) ++fails;
    printf("  %s %-46s\n", ok?"OK ":"NG ", n);
}

struct Grid {
    data::Mesh mesh; int nx, ny, nz;
    Grid(int X, int Y, int Z) : nx(X), ny(Y), nz(Z) {
        int NX=nx+1, NY=ny+1, NZ=nz+1;
        for (int k=0;k<NZ;++k) for (int j=0;j<NY;++j) for (int i=0;i<NX;++i) {
            Node n; n.id=(int32_t)mesh.nodes.size()+1; n.x=i; n.y=j; n.z=k; mesh.nodes.push_back(n);
        }
        auto nid=[&](int i,int j,int k){ return k*NY*NX + j*NX + i + 1; };
        for (int k=0;k<nz;++k) for (int j=0;j<ny;++j) for (int i=0;i<nx;++i) {
            Element e; e.id=(int32_t)mesh.solids.size()+1; e.type=ElementType::SOLID;
            e.node_ids={ nid(i,j,k),nid(i+1,j,k),nid(i+1,j+1,k),nid(i,j+1,k),
                         nid(i,j,k+1),nid(i+1,j,k+1),nid(i+1,j+1,k+1),nid(i,j+1,k+1) };
            mesh.solids.push_back(e); mesh.solid_parts.push_back(1);
        }
        mesh.num_solids = mesh.solids.size();
    }
    size_t idx(int i,int j,int k) const { return (size_t)k*ny*nx + (size_t)j*nx + i; }
};

int main(){
    printf("[1] 이름 왕복 · 방향 · 심각도\n");
    {
        HotspotCriterion c;
        chkb("von_mises 파싱",      parseHotspotCriterion("von_mises", c) && c==HotspotCriterion::VonMises);
        chkb("Max-Principal 관용",  parseHotspotCriterion("Max-Principal", c) && c==HotspotCriterion::MaxPrincipal);
        chkb("sigma3 별칭",         parseHotspotCriterion("sigma3", c) && c==HotspotCriterion::MinPrincipal);
        chkb("모르는 이름 거부",     !parseHotspotCriterion("tresca", c));
        chkb("이름 왕복",           std::string(hotspotCriterionName(HotspotCriterion::MinPrincipal))=="min_principal");
        chkb("σ3 만 min 방향",      hotspotCriterionIsMin(HotspotCriterion::MinPrincipal)
                                  && !hotspotCriterionIsMin(HotspotCriterion::MaxPrincipal)
                                  && !hotspotCriterionIsMin(HotspotCriterion::VonMises));
        chkb("hotter: σ3 는 작은 값", hotspotHotter(HotspotCriterion::MinPrincipal, -500, -100)
                                  && !hotspotHotter(HotspotCriterion::MinPrincipal, -100, -500));
        chkb("hotter: σ1 은 큰 값",  hotspotHotter(HotspotCriterion::MaxPrincipal, 300, 100));
        chk ("심각도(σ3, −500)",     hotspotSeverity(HotspotCriterion::MinPrincipal, -500), 500, 0);
        chk ("심각도(σ1, 300)",      hotspotSeverity(HotspotCriterion::MaxPrincipal, 300), 300, 0);
        std::vector<std::string> unk;
        auto list = parseHotspotCriteria({"von_mises","tresca","min_principal","von_mises"}, &unk);
        chk ("목록: 중복 제거·순서 유지", (double)list.size(), 2, 0);
        chkb("목록: 모르는 이름 수집",  unk.size()==1 && unk[0]=="tresca");
        chkb("목록: 순서",             list[0]==HotspotCriterion::VonMises && list[1]==HotspotCriterion::MinPrincipal);
        chkb("NaN 표식 판정",          hotspotIsUnrecorded(hotspotUnrecorded()) && !hotspotIsUnrecorded(-1e300));
    }

    printf("\n[2] σ3 군집 — 가장 압축인 덩어리가 1위, 음수는 걸러지지 않는다\n");
    {
        Grid g(20,3,3);                                        // 180 요소
        std::vector<double> v(g.mesh.solids.size(), -10.0);   // 배경: 약한 압축
        for (int i=1;i<=3;++i)   v[g.idx(i,1,1)] = -500.0;    // A: 강한 압축 3개
        for (int i=16;i<=18;++i) v[g.idx(i,1,1)] = -400.0;    // B: 중간 압축 3개
        v[g.idx(9,1,1)] = +900.0;                              // 인장 최대 — σ3 기준에서는 가장 '차가움'

        HotspotClusterConfig cfg; cfg.enabled=true; cfg.criterion=HotspotCriterion::MinPrincipal;
        cfg.top_percent=3.4; cfg.distance_factor=1.5; cfg.min_cluster_elements=3;
        auto res = computeHotspotClusters(g.mesh, v, {}, {}, {}, cfg);
        chk ("파트 수", (double)res.size(), 1, 0);
        const auto& p = res[0];
        chkb("criterion 이름",     p.criterion=="min_principal");
        chkb("direction=min",      p.direction=="min");
        chkb("strain_measure",     p.strain_measure=="min_principal");
        chk ("선별 6개 (음수 6개)",  p.element_count_selected, 6, 0);
        chk ("컷값 = 덜 압축인 −400", p.threshold_value, -400, 0);
        chk ("덩어리 2개",          (double)p.clusters.size(), 2, 0);
        if (p.clusters.size()==2) {
            chk ("1위 극값 −500 (가장 압축)", p.clusters[0].stress_max, -500, 0);
            chk ("2위 극값 −400",            p.clusters[1].stress_max, -400, 0);
            chk ("1위 평균 −500 (부호 유지)", p.clusters[0].stress_mean, -500, 1e-12);
            chk ("1위 중심 x = 2.5",         p.clusters[0].center[0], 2.5, 1e-12);   // 요소 1..3 → 도심 1.5,2.5,3.5
            chk ("2위 중심 x = 17.5",        p.clusters[1].center[0], 17.5, 1e-12);
            chkb("+900 요소는 어느 덩어리에도 없음",
                 p.clusters[0].peak_element_id != (int32_t)g.idx(9,1,1)+1 &&
                 p.clusters[1].peak_element_id != (int32_t)g.idx(9,1,1)+1);
        }
    }

    printf("\n[3] σ1 군집 — 전부 음수인 파트도 선별된다 (예전 −DBL_MAX 표식이면 0개)\n");
    {
        Grid g(10,2,2);
        std::vector<double> v(g.mesh.solids.size(), -300.0);  // 전부 압축 (σ1 < 0)
        for (int i=1;i<=3;++i) v[g.idx(i,1,1)] = -50.0;        // 가장 덜 압축 = σ1 기준 최대
        HotspotClusterConfig cfg; cfg.enabled=true; cfg.criterion=HotspotCriterion::MaxPrincipal;
        cfg.top_percent=7.5; cfg.distance_factor=1.5; cfg.min_cluster_elements=3;   // floor(40*.075)=3
        auto res = computeHotspotClusters(g.mesh, v, {}, {}, {}, cfg);
        chk ("선별 3개", res.empty()?-1:res[0].element_count_selected, 3, 0);
        chk ("컷값 −50", res.empty()?0:res[0].threshold_value, -50, 0);
        chk ("덩어리 1개", res.empty()?-1:(double)res[0].clusters.size(), 1, 0);
        if (!res.empty() && !res[0].clusters.empty()) {
            chk ("극값 −50", res[0].clusters[0].stress_max, -50, 0);
            chkb("direction=max", res[0].direction=="max");
            // 심각도 가중이 전부 음수(=0 클램프) → 부피 가중 폴백 → 기하 중심
            chk ("중심 x (부피 가중 폴백)", res[0].clusters[0].center[0], 2.5, 1e-12);
        }
    }

    printf("\n[4] NaN 미기록은 제외, 0 과 음수는 정상값\n");
    {
        Grid g(10,2,2);
        std::vector<double> v(g.mesh.solids.size(), hotspotUnrecorded());
        v[g.idx(1,1,1)] = 0.0; v[g.idx(2,1,1)] = -1.0; v[g.idx(3,1,1)] = -2.0;
        HotspotClusterConfig cfg; cfg.enabled=true; cfg.criterion=HotspotCriterion::MinPrincipal;
        cfg.top_percent=100.0; cfg.distance_factor=1.5; cfg.min_cluster_elements=3;
        auto res = computeHotspotClusters(g.mesh, v, {}, {}, {}, cfg);
        chk ("선별 = 기록된 3개 (0·음수 포함)", res.empty()?-1:res[0].element_count_selected, 3, 0);
        chk ("극값 −2", (res.empty()||res[0].clusters.empty())?1:res[0].clusters[0].stress_max, -2, 0);
    }

    printf("\n[5] 짝 변형률도 방향을 따른다 (σ3 → ε3 최솟값)\n");
    {
        Grid g(10,2,2);
        std::vector<double> v(g.mesh.solids.size(), 0.0), e(g.mesh.solids.size(), 0.0);
        for (int i=1;i<=3;++i) { v[g.idx(i,1,1)] = -100.0 - i; e[g.idx(i,1,1)] = -0.01 * i; }
        HotspotClusterConfig cfg; cfg.enabled=true; cfg.criterion=HotspotCriterion::MinPrincipal;
        cfg.top_percent=7.5; cfg.distance_factor=1.5; cfg.min_cluster_elements=3;
        auto res = computeHotspotClusters(g.mesh, v, {}, e, {}, cfg);
        bool ok = !res.empty() && !res[0].clusters.empty();
        chk ("strain_max = ε3 최솟값 −0.03", ok?res[0].clusters[0].strain_max:1, -0.03, 1e-15);
        chk ("strain_mean = −0.02",         ok?res[0].clusters[0].strain_mean:1, -0.02, 1e-15);
    }

    printf("\n[6] 회귀 — von_mises 는 예전과 동일 (심각도 가중 = σ·V, 컷 = 최솟값)\n");
    {
        Grid g(20,3,3);
        std::vector<double> v(g.mesh.solids.size(), 10.0);
        for (int i=1;i<=3;++i)   v[g.idx(i,1,1)] = 500.0;
        for (int i=16;i<=18;++i) v[g.idx(i,1,1)] = 400.0;
        HotspotClusterConfig cfg; cfg.enabled=true;   // 기본 = VonMises
        cfg.top_percent=3.4; cfg.distance_factor=1.5; cfg.min_cluster_elements=3;
        auto res = computeHotspotClusters(g.mesh, v, {}, {}, {}, cfg);
        const auto& p = res[0];
        chkb("criterion=von_mises · direction=max · equivalent",
             p.criterion=="von_mises" && p.direction=="max" && p.strain_measure=="equivalent");
        chk ("컷값 400", p.threshold_value, 400, 0);
        chk ("1위 500", p.clusters.empty()?0:p.clusters[0].stress_max, 500, 0);
        chk ("1위 중심 x 2.5", p.clusters.empty()?0:p.clusters[0].center[0], 2.5, 1e-12);
    }

    printf("\n%s 실패 %d 건\n", fails?"[FAIL]":"[PASS]", fails);
    return fails ? 1 : 0;
}
