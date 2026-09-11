// computeHotspotClusters 통합 검증 — 인공 메시로 알려진 답과 대조
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
    printf("  %s %-38s got=%.8g want=%.8g err=%.2g\n", ok?"OK ":"NG ", n, g, w, e);
}

// 정육면체 요소들로 이루어진 격자 메시를 만든다.
// nx x ny x nz 개의 단위 정육면체, 절점은 (nx+1)(ny+1)(nz+1) 개.
struct Grid {
    data::Mesh mesh;
    int nx, ny, nz;
    Grid(int X, int Y, int Z) : nx(X), ny(Y), nz(Z) {
        int NX=nx+1, NY=ny+1, NZ=nz+1;
        mesh.nodes.reserve(NX*NY*NZ);
        for (int k=0;k<NZ;++k) for (int j=0;j<NY;++j) for (int i=0;i<NX;++i) {
            Node n; n.id = (int32_t)mesh.nodes.size()+1;
            n.x=i; n.y=j; n.z=k;
            mesh.nodes.push_back(n);
        }
        auto nid=[&](int i,int j,int k){ return k*NY*NX + j*NX + i + 1; };  // 1-based 내부 인덱스
        for (int k=0;k<nz;++k) for (int j=0;j<ny;++j) for (int i=0;i<nx;++i) {
            Element e; e.id=(int32_t)mesh.solids.size()+1; e.type=ElementType::SOLID;
            e.node_ids = { nid(i,j,k), nid(i+1,j,k), nid(i+1,j+1,k), nid(i,j+1,k),
                           nid(i,j,k+1), nid(i+1,j,k+1), nid(i+1,j+1,k+1), nid(i,j+1,k+1) };
            mesh.solids.push_back(e);
            mesh.solid_parts.push_back(1);
        }
        mesh.num_solids = mesh.solids.size();
    }
    size_t idx(int i,int j,int k) const { return (size_t)k*ny*nx + (size_t)j*nx + i; }
};

int main(){
    printf("[1] 떨어진 두 핫스팟 — 개수·중심·반경\n");
    {
        Grid g(20,3,3);                      // 요소 180개, 크기 1
        std::vector<double> vm(g.mesh.solids.size(), 10.0);   // 배경 10
        // 핫스팟 A: i=1..3, j=1, k=1  (3개)
        // 핫스팟 B: i=16..18, j=1, k=1 (3개)  — 12칸 떨어짐
        for (int i=1;i<=3;++i) vm[g.idx(i,1,1)] = 500.0;
        for (int i=16;i<=18;++i) vm[g.idx(i,1,1)] = 400.0;

        HotspotClusterConfig cfg;
        cfg.enabled = true;
        // 🔴 상위 N개는 '값이 큰 순서로 정확히 N개' 다. N 이 진짜 핫한 요소 수보다
        //    크면 배경 요소가 딸려 들어와 덩어리에 붙고 평균이 희석된다.
        //    여기서는 핫한 요소가 6개이므로 floor(180*0.034)=6 이 되게 잡는다.
        cfg.top_percent = 3.4;
        cfg.distance_factor = 1.5;           // 임계 1.5 (요소 크기 1)
        cfg.min_cluster_elements = 3;
        std::map<int32_t,std::string> names{{1,"TEST"}};
        auto res = computeHotspotClusters(g.mesh, vm, {}, {}, names, cfg);

        chk("파트 수", res.size(), 1, 0);
        if (!res.empty()) {
            const auto& r = res[0];
            printf("      선별=%d, 대표크기=%.4f, 임계거리=%.4f, 덩어리=%zu\n",
                   r.element_count_selected, r.element_size_ref, r.distance_threshold, r.clusters.size());
            chk("대표 요소 크기(=1)", r.element_size_ref, 1.0, 1e-12);
            chk("덩어리 수", r.clusters.size(), 2, 0);
            if (r.clusters.size() == 2) {
                // rank1 = 응력 큰 쪽(500) = 핫스팟 A, 중심 x = (1.5+2.5+3.5)/3 = 2.5
                chk("rank1 최대응력", r.clusters[0].stress_max, 500.0, 1e-12);
                chk("rank1 평균응력", r.clusters[0].stress_mean, 500.0, 1e-12);
                chk("rank1 중심 x", r.clusters[0].center[0], 2.5, 1e-12);
                chk("rank1 중심 y", r.clusters[0].center[1], 1.5, 1e-12);
                chk("rank1 요소수", r.clusters[0].element_count, 3, 0);
                chk("rank1 부피", r.clusters[0].volume, 3.0, 1e-12);
                chk("rank2 최대응력", r.clusters[1].stress_max, 400.0, 1e-12);
                chk("rank2 중심 x", r.clusters[1].center[0], 17.5, 1e-12);
                // 포함 반경: 중심(2.5,1.5,1.5)에서 최원 절점 (1,1,1)or(4,2,2) -> sqrt(1.5^2+0.5^2+0.5^2)
                chk("rank1 포함반경", r.clusters[0].radius_enclosing,
                    std::sqrt(1.5*1.5+0.5*0.5+0.5*0.5), 1e-12);
            }
        }
    }

    printf("[2] 최소 크기 필터 — 미달 덩어리는 버려진다\n");
    {
        Grid g(20,3,3);
        std::vector<double> vm(g.mesh.solids.size(), 10.0);
        for (int i=1;i<=3;++i) vm[g.idx(i,1,1)] = 500.0;   // 3개
        vm[g.idx(18,1,1)] = 400.0;                          // 1개 (고립)
        HotspotClusterConfig cfg; cfg.enabled=true; cfg.top_percent=5.0;
        cfg.distance_factor=1.5; cfg.min_cluster_elements=3;
        auto res = computeHotspotClusters(g.mesh, vm, {}, {}, {}, cfg);
        chk("덩어리 수(고립 1개 버림)", res.empty()?-1:(double)res[0].clusters.size(), 1, 0);
    }

    printf("[3] 부피 가중 평균 — 산술평균과 달라야\n");
    {
        // 요소 크기가 다른 두 덩어리를 만들 수 없으므로 부피를 직접 검증:
        // 균일 격자에서는 부피 가중 == 산술평균 이어야 한다(모두 부피 1)
        Grid g(10,2,2);
        std::vector<double> vm(g.mesh.solids.size(), 1.0);
        vm[g.idx(1,1,1)] = 300.0;
        vm[g.idx(2,1,1)] = 100.0;
        HotspotClusterConfig cfg; cfg.enabled=true; cfg.top_percent=5.0;  // floor(40*0.05)=2
        cfg.distance_factor=1.5; cfg.min_cluster_elements=2;
        auto res = computeHotspotClusters(g.mesh, vm, {}, {}, {}, cfg);
        if (!res.empty() && res[0].clusters.size() > 0) {
            chk("균일부피 평균=(300+100)/2", res[0].clusters[0].stress_mean, 200.0, 1e-12);
            // 중심은 응력 가중: (300*1.5 + 100*2.5)/400 = (450+250)/400 = 1.75
            chk("응력가중 중심 x", res[0].clusters[0].center[0], 1.75, 1e-12);
        }
    }

    printf("[4] 미기록(-1) 요소는 제외된다\n");
    {
        Grid g(10,2,2);
        std::vector<double> vm(g.mesh.solids.size(), hotspotUnrecorded());   // 전부 미기록(NaN)
        for (int i=1;i<=3;++i) vm[g.idx(i,1,1)] = 500.0;
        HotspotClusterConfig cfg; cfg.enabled=true; cfg.top_percent=100.0;
        cfg.distance_factor=1.5; cfg.min_cluster_elements=3;
        auto res = computeHotspotClusters(g.mesh, vm, {}, {}, {}, cfg);
        chk("선별 = 기록된 3개만", res.empty()?-1:(double)res[0].element_count_selected, 3, 0);
    }

    printf("[5] 경계 — 비활성 / 빈 입력 / 전부 한 덩어리\n");
    {
        Grid g(6,2,2);
        std::vector<double> vm(g.mesh.solids.size(), 100.0);
        HotspotClusterConfig off; off.enabled=false;
        chk("비활성 -> 빈 결과", computeHotspotClusters(g.mesh, vm, {}, {}, {}, off).size(), 0, 0);

        HotspotClusterConfig cfg; cfg.enabled=true; cfg.top_percent=100.0;
        cfg.distance_factor=1.5; cfg.min_cluster_elements=1;
        auto res = computeHotspotClusters(g.mesh, vm, {}, {}, {}, cfg);
        chk("전부 한 덩어리", res.empty()?-1:(double)res[0].clusters.size(), 1, 0);
        if (!res.empty() && res[0].clusters.size()==1)
            chk("전 요소 포함", res[0].clusters[0].element_count, (double)g.mesh.solids.size(), 0);

        std::vector<double> empty;
        chk("빈 배열 -> 빈 결과", computeHotspotClusters(g.mesh, empty, {}, {}, {}, cfg).size(), 0, 0);
    }

    printf("[6] 변형률 병기\n");
    {
        Grid g(10,2,2);
        std::vector<double> vm(g.mesh.solids.size(), 1.0);
        std::vector<double> ep(g.mesh.solids.size(), 0.001);
        for (int i=1;i<=3;++i){ vm[g.idx(i,1,1)]=500.0; ep[g.idx(i,1,1)]=0.05; }
        HotspotClusterConfig cfg; cfg.enabled=true; cfg.top_percent=7.5;  // floor(40*0.075)=3
        cfg.distance_factor=1.5; cfg.min_cluster_elements=3;
        auto res = computeHotspotClusters(g.mesh, vm, {}, ep, {}, cfg);
        if (!res.empty() && res[0].clusters.size()>=1) {
            chk("변형률 사용가능", res[0].clusters[0].strain_available?1:0, 1, 0);
            chk("변형률 평균", res[0].clusters[0].strain_mean, 0.05, 1e-12);
            chk("변형률 최대", res[0].clusters[0].strain_max, 0.05, 1e-12);
        } else { printf("  NG  덩어리 없음\n"); ++fails; }
    }

    printf("[7] 성질 — N 이 핫한 요소보다 크면 배경이 딸려와 평균이 희석된다\n");
    {
        Grid g(20,3,3);                        // 180 요소
        std::vector<double> vm(g.mesh.solids.size(), 10.0);
        for (int i=1;i<=3;++i) vm[g.idx(i,1,1)] = 500.0;   // 진짜 핫한 것은 3개뿐
        HotspotClusterConfig cfg; cfg.enabled=true;
        cfg.top_percent = 5.0;                 // floor(180*0.05)=9 -> 6개는 배경
        cfg.distance_factor=1.5; cfg.min_cluster_elements=3;
        auto res = computeHotspotClusters(g.mesh, vm, {}, {}, {}, cfg);
        if (!res.empty()) {
            chk("선별 개수", res[0].element_count_selected, 9, 0);
            printf("      -> 사용자는 top_percent 를 실제 집중 범위에 맞춰야 한다\n");
        } else { printf("  NG  결과 없음\n"); ++fails; }
    }

    printf("\n%s  실패 %d 건\n", fails?"[FAIL]":"[PASS]", fails);
    return fails?1:0;
}
