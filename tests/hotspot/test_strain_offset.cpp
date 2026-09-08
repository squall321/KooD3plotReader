// d3plot solid 변형률 워드 위치 회귀 — 규격은 "NEIPH 확장값의 마지막 6개"
//
// 규격(ls-dyna_database.txt:2981-2987):
//   7.          유효소성변형률
//   8..         NEIPH extra values
//   7+NEIPH-5 .. 7+NEIPH   Epsilon-x .. Epsilon-zx   (1-based)
// NV3D = 7 + NEIPH 이므로 0-based 시작 = base + NV3D - 6.
#include "kood3plot/analysis/HotspotClusterAnalyzer.hpp"
#include <cstdio>
#include <cmath>
#include <vector>
using namespace kood3plot::analysis;

static int fails = 0;
static void chk(const char* n, double g, double w, double t) {
    double e = std::abs(g - w); bool ok = e <= t; if (!ok) ++fails;
    printf("  %s %-44s got=%.8g want=%.8g\n", ok?"OK ":"NG ", n, g, w);
}

// 구현이 쓰는 공식
static size_t strain_offset(size_t base, int nv3d) { return base + (size_t)nv3d - 6; }
// 수정 전 공식 (비교용)
static size_t old_offset(size_t base, int)          { return base + 7; }

int main(){
    printf("[1] NV3D=13 (NEIPH=6) — 두 공식이 같아야 (기존 덱 회귀 없음)\n");
    chk("nv3d-6", (double)strain_offset(0,13), 7.0, 0);
    chk("base+7 (구식)", (double)old_offset(0,13), 7.0, 0);

    printf("[2] 실덱 NV3D 값들 — 두 공식이 갈린다\n");
    const int NV[] = {26, 29, 30};      // /data/battery_study 실측
    for (int nv : NV) {
        char nm[64];
        snprintf(nm, sizeof nm, "NV3D=%d 올바른 오프셋", nv);
        chk(nm, (double)strain_offset(0, nv), (double)(nv - 6), 0);
        snprintf(nm, sizeof nm, "  구식(base+7)과 다름");
        chk(nm, (double)(old_offset(0,nv) != strain_offset(0,nv)), 1.0, 0);
    }

    printf("[3] 합성 요소 데이터로 실제 값 추출 검증 (NV3D=19, NEIPH=12)\n");
    {
        const int nv3d = 19;
        std::vector<double> sd(nv3d, 0.0);
        // 워드 1-6: 응력
        sd[0]=100; sd[1]=0; sd[2]=0; sd[3]=0; sd[4]=0; sd[5]=0;
        sd[6]=0.02;                       // 워드 7: 유효소성변형률
        for (int i=7;i<13;++i) sd[i]=0.9; // 워드 8-13: 이력변수 (변형률 아님!)
        // 워드 14-19 (0-based 13-18): 진짜 변형률
        sd[13]=1e-3; sd[14]=-5e-4; sd[15]=-5e-4; sd[16]=0; sd[17]=0; sd[18]=0;

        size_t off = strain_offset(0, nv3d);
        chk("오프셋", (double)off, 13.0, 0);
        double eq = equivalentStrain(sd[off+0],sd[off+1],sd[off+2],sd[off+3],sd[off+4],sd[off+5]);
        chk("등가변형률(진짜 값)", eq, 1e-3, 1e-15);

        size_t bad = old_offset(0, nv3d);
        double eq_bad = equivalentStrain(sd[bad+0],sd[bad+1],sd[bad+2],sd[bad+3],sd[bad+4],sd[bad+5]);
        printf("      구식 오프셋(%zu) 로 읽으면 = %.6g  (이력변수 0.9 를 변형률로 오독)\n", bad, eq_bad);
        chk("구식은 틀린 값을 냄", (double)(std::abs(eq_bad - 1e-3) > 1e-6), 1.0, 0);
    }

    printf("[4] 등가변형률 정의 재확인 (단축 비압축)\n");
    chk("eps_eq", equivalentStrain(0.01,-0.005,-0.005,0,0,0), 0.01, 1e-15);

    printf("\n%s  실패 %d 건\n", fails?"[FAIL]":"[PASS]", fails);
    return fails?1:0;
}
