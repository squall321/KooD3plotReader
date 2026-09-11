// 셸·두꺼운 셸 군집 — 합성 격자로 면적/두께 가중, 면내 대표 크기, 층 전달, bbox 를 해석 답과 대조
#include "kood3plot/analysis/HotspotClusterAnalyzer.hpp"
#include <cstdio>
#include <cmath>
#include <vector>
using namespace kood3plot;
using namespace kood3plot::analysis;

static int fails = 0;
static void chk(const char* n, double g, double w, double t) {
    double e = std::abs(g - w); bool ok = e <= t; if (!ok) ++fails;
    printf("  %s %-52s got=%.10g want=%.10g err=%.2g\n", ok?"OK ":"NG ", n, g, w, e);
}
static void chkb(const char* n, bool ok) { if (!ok) ++fails; printf("  %s %-52s\n", ok?"OK ":"NG ", n); }

// nx×ny 셸 격자 (요소 크기 h, 평면 z=0)
struct ShellGrid {
    data::Mesh mesh; int nx, ny;
    ShellGrid(int X, int Y, double h) : nx(X), ny(Y) {
        for (int j=0;j<=ny;++j) for (int i=0;i<=nx;++i) {
            Node n; n.id=(int32_t)mesh.nodes.size()+1; n.x=i*h; n.y=j*h; n.z=0; mesh.nodes.push_back(n); }
        auto nid=[&](int i,int j){ return j*(nx+1)+i+1; };
        for (int j=0;j<ny;++j) for (int i=0;i<nx;++i) {
            Element e; e.id=(int32_t)mesh.shells.size()+1; e.type=ElementType::SHELL;
            e.node_ids={nid(i,j),nid(i+1,j),nid(i+1,j+1),nid(i,j+1)};
            mesh.shells.push_back(e); mesh.shell_parts.push_back(7); mesh.real_shell_ids.push_back(5000+e.id);
        }
        mesh.num_shells=mesh.shells.size();
    }
    size_t idx(int i,int j) const { return (size_t)j*nx+i; }
};

// nx×ny 두꺼운 셸 격자 (면내 h, 두께 t — 1층)
struct TShellGrid {
    data::Mesh mesh; int nx, ny;
    TShellGrid(int X, int Y, double h, double t) : nx(X), ny(Y) {
        for (int k=0;k<=1;++k) for (int j=0;j<=ny;++j) for (int i=0;i<=nx;++i) {
            Node n; n.id=(int32_t)mesh.nodes.size()+1; n.x=i*h; n.y=j*h; n.z=k*t; mesh.nodes.push_back(n); }
        const int L=(nx+1)*(ny+1);
        auto nid=[&](int i,int j,int k){ return k*L + j*(nx+1)+i+1; };
        for (int j=0;j<ny;++j) for (int i=0;i<nx;++i) {
            Element e; e.id=(int32_t)mesh.thick_shells.size()+1; e.type=ElementType::THICK_SHELL;
            e.node_ids={nid(i,j,0),nid(i+1,j,0),nid(i+1,j+1,0),nid(i,j+1,0),
                        nid(i,j,1),nid(i+1,j,1),nid(i+1,j+1,1),nid(i,j+1,1)};
            mesh.thick_shells.push_back(e); mesh.thick_shell_parts.push_back(9);
        }
        mesh.num_thick_shells=mesh.thick_shells.size();
    }
    size_t idx(int i,int j) const { return (size_t)j*nx+i; }
};

int main(){
    printf("[1] 셸 두 핫스팟 — 면적×두께 가중, 대표 크기 √A, 층 전달\n");
    {
        ShellGrid g(20,4,2.0);                               // 요소 80개, 면적 4
        ElementExtremes ex;
        ex.value.assign(g.mesh.shells.size(), 10.0);
        ex.time.assign(g.mesh.shells.size(), 0.5);
        ex.layer.assign(g.mesh.shells.size(), 0);
        // 값이 겹치지 않게 (피크 요소가 동률이면 어느 쪽이든 정답이라 시험이 모호해진다)
        for (int i=1;i<=2;++i) for (int j=1;j<=2;++j) { ex.value[g.idx(i,j)] = 500.0 + i + 0.1*j; ex.layer[g.idx(i,j)] = 2; }
        for (int i=16;i<=17;++i) for (int j=1;j<=2;++j) { ex.value[g.idx(i,j)] = 300.0; ex.layer[g.idx(i,j)] = 1; }
        std::vector<double> th(g.mesh.shells.size(), 1.6);
        HotspotClusterConfig cfg; cfg.enabled=true; cfg.top_percent=10.0;   // floor(80*.1)=8
        cfg.distance_factor=1.5; cfg.min_cluster_elements=3;
        auto res = computeHotspotClusters(g.mesh, HotspotElementKind::Shell, ex, th, "mid_inner_outer", {}, cfg);
        chk("파트 1개", (double)res.size(), 1, 0);
        const auto& p = res[0];
        chkb("element_type=shell", p.element_type=="shell");
        chkb("weight_measure=area_x_thickness", p.weight_measure=="area_x_thickness");
        chkb("layer_scheme 전달", p.layer_scheme=="mid_inner_outer");
        chk ("대표 크기 = √4 = 2", p.element_size_ref, 2.0, 1e-12);
        chk ("선별 8", p.element_count_selected, 8, 0);
        chk ("덩어리 2", (double)p.clusters.size(), 2, 0);
        if (p.clusters.size()==2) {
            const auto& a = p.clusters[0];
            chk ("1위 극값 502.2", a.stress_max, 502.2, 1e-12);
            chk ("1위 면적 4×4 = 16", a.area, 16, 1e-12);
            chk ("1위 부피 16×1.6 = 25.6", a.volume, 25.6, 1e-12);
            chkb("1위 area·volume 출력 플래그", a.has_area && a.volume_valid);
            chk ("1위 피크 층 = 2(바깥쪽)", a.peak_layer, 2, 0);
            chk ("1위 피크 요소 사용자 ID (2,2)", a.peak_element_id, 5000 + (int)g.idx(2,2) + 1, 0);
            // 중심: 요소 (i,j) 도심 x = 2i+1, 가중 = σ(i,j) (면적·두께 동일) → Σ x·σ / Σ σ
            double sw=0, sx=0; for (int i=1;i<=2;++i) for (int j=1;j<=2;++j) { double w=500.0+i+0.1*j; sw+=w; sx+=(2*i+1)*w; }
            chk ("1위 중심 x (심각도 가중)", a.center[0], sx/sw, 1e-12);
            chk ("2위 피크 층 = 1(안쪽)", p.clusters[1].peak_layer, 1, 0);
        }
        chkb("bbox 유효", p.bbox_valid);
        chk ("bbox max x = 40", p.bbox_max[0], 40, 1e-12);
        chk ("bbox max y = 8",  p.bbox_max[1], 8, 1e-12);
    }

    printf("\n[2] 두께 없으면 면적 가중으로 떨어지고 volume 을 내지 않는다\n");
    {
        ShellGrid g(10,3,1.0);
        ElementExtremes ex; ex.value.assign(g.mesh.shells.size(), 1.0);
        for (int i=1;i<=3;++i) ex.value[g.idx(i,1)] = 100.0;
        HotspotClusterConfig cfg; cfg.enabled=true; cfg.top_percent=10.0; cfg.distance_factor=1.5; cfg.min_cluster_elements=3;
        auto res = computeHotspotClusters(g.mesh, HotspotElementKind::Shell, ex, {}, "index", {}, cfg);
        chkb("weight_measure=area", !res.empty() && res[0].weight_measure=="area");
        bool ok = !res.empty() && !res[0].clusters.empty();
        chkb("volume_valid=false (0 을 부피로 내지 않음)", ok && !res[0].clusters[0].volume_valid);
        chk ("면적 3", ok?res[0].clusters[0].area:0, 3, 1e-12);
        // 파트 안에 두께 0 이 하나라도 섞이면 전체를 면적 가중으로 (단위 혼합 방지)
        std::vector<double> th(g.mesh.shells.size(), 2.0); th[0] = 0.0;
        auto r2 = computeHotspotClusters(g.mesh, HotspotElementKind::Shell, ex, th, "index", {}, cfg);
        chkb("두께 0 혼재 → area", !r2.empty() && r2[0].weight_measure=="area");
    }

    printf("\n[3] 삼각형 셸 섞임 — 면적·중심 정확\n");
    {
        ShellGrid g(6,2,2.0);
        // 요소 (1,0) 을 삼각형으로 (4번 절점 = 3번)
        auto& e = g.mesh.shells[g.idx(1,0)]; e.node_ids[3] = e.node_ids[2];
        ElementExtremes ex; ex.value.assign(g.mesh.shells.size(), 0.0);
        ex.value[g.idx(0,0)] = 9; ex.value[g.idx(1,0)] = 9; ex.value[g.idx(2,0)] = 9;
        HotspotClusterConfig cfg; cfg.enabled=true; cfg.top_percent=25.0; cfg.distance_factor=1.5; cfg.min_cluster_elements=3;
        auto res = computeHotspotClusters(g.mesh, HotspotElementKind::Shell, ex, {}, "index", {}, cfg);
        bool ok = !res.empty() && res[0].clusters.size()==1;
        chk ("면적 4 + 2 + 4 = 10", ok?res[0].clusters[0].area:0, 10, 1e-12);
    }

    printf("\n[4] 얇은 두꺼운 셸 — 면내 크기로 묶인다 (∛V 였다면 전부 흩어짐)\n");
    {
        TShellGrid g(20,4,2.0,0.05);                          // 면내 2, 두께 0.05
        ElementExtremes ex; ex.value.assign(g.mesh.thick_shells.size(), 1.0);
        ex.layer.assign(g.mesh.thick_shells.size(), 1);
        for (int i=2;i<=4;++i) for (int j=1;j<=2;++j) ex.value[g.idx(i,j)] = 200.0;
        HotspotClusterConfig cfg; cfg.enabled=true; cfg.top_percent=7.5; cfg.distance_factor=1.5; cfg.min_cluster_elements=3; // floor(80*.075)=6
        auto res = computeHotspotClusters(g.mesh, HotspotElementKind::ThickShell, ex, {}, "mid_inner_outer", {}, cfg);
        bool ok = !res.empty();
        chkb("element_type=thick_shell · weight=volume", ok && res[0].element_type=="thick_shell" && res[0].weight_measure=="volume");
        chk ("대표 크기 = 면내 2", ok?res[0].element_size_ref:0, 2.0, 1e-12);
        chk ("덩어리 1개, 6요소", ok&&!res[0].clusters.empty()?res[0].clusters[0].element_count:0, 6, 0);
        chk ("부피 6 × 4 × 0.05 = 1.2", ok&&!res[0].clusters.empty()?res[0].clusters[0].volume:0, 1.2, 1e-12);
        const double cbrtV = std::cbrt(4.0*0.05);
        printf("     참고: ∛V = %.3f → 임계 %.3f < 면내 간격 2 — 기존 정의였다면 이웃이 안 묶였다\n", cbrtV, 1.5*cbrtV);
        chkb("∛V 임계가 면내 간격보다 작음을 확인", 1.5*cbrtV < 2.0);
    }

    printf("\n[5] 솔리드 경로 불변 — 기존 진입점과 종류 일반판이 같은 답\n");
    {
        TShellGrid tg(10,2,1.0,1.0);            // 정육면체 요소를 솔리드로 재사용
        data::Mesh m; m.nodes = tg.mesh.nodes; m.solids = tg.mesh.thick_shells;
        m.solid_parts.assign(m.solids.size(), 3); m.num_solids = m.solids.size();
        std::vector<double> v(m.solids.size(), 1.0); v[1]=50; v[2]=60; v[3]=70;
        HotspotClusterConfig cfg; cfg.enabled=true; cfg.top_percent=15.0; cfg.distance_factor=1.5; cfg.min_cluster_elements=3;
        auto a = computeHotspotClusters(m, v, {}, {}, {}, cfg);
        ElementExtremes ex; ex.value = v;
        auto b = computeHotspotClusters(m, HotspotElementKind::Solid, ex, {}, "", {}, cfg);
        bool ok = a.size()==1 && b.size()==1 && a[0].clusters.size()==b[0].clusters.size() && !a[0].clusters.empty();
        chkb("같은 덩어리 수", ok);
        if (ok) { chk("같은 중심 x", a[0].clusters[0].center[0], b[0].clusters[0].center[0], 0);
                  chk("같은 부피", a[0].clusters[0].volume, b[0].clusters[0].volume, 0);
                  chkb("솔리드는 area·peak_layer 미출력", !a[0].clusters[0].has_area && a[0].clusters[0].peak_layer==-1); }
    }

    printf("\n%s 실패 %d 건\n", fails?"[FAIL]":"[PASS]", fails);
    return fails?1:0;
}
