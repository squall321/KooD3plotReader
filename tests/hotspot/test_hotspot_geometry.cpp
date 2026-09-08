// 실제 구현(HotspotClusterAnalyzer.cpp)에 대한 단위 검증
#include "kood3plot/analysis/HotspotClusterAnalyzer.hpp"
#include <cstdio>
#include <cmath>
#include <vector>
using namespace kood3plot;
using namespace kood3plot::analysis;

static int fails = 0;
static void chk(const char* n, double got, double want, double tol) {
    double e = std::abs(got - want); bool ok = e <= tol;
    if (!ok) ++fails;
    printf("  %s %-40s got=%.12g want=%.12g err=%.2g\n", ok?"OK ":"NG ", n, got, want, e);
}
static Node N(int id,double x,double y,double z){ Node n; n.id=id; n.x=x; n.y=y; n.z=z; return n; }

int main(){
    double V,cx,cy,cz;

    printf("[1] 단위 정육면체 (해석 V=1, c=0.5,0.5,0.5)\n");
    { Node p[8]={N(1,0,0,0),N(2,1,0,0),N(3,1,1,0),N(4,0,1,0),
                 N(5,0,0,1),N(6,1,0,1),N(7,1,1,1),N(8,0,1,1)};
      bool ok=computeSolidVolumeAndCentroid(p,V,cx,cy,cz);
      chk("ok",ok?1:0,1,0); chk("V",V,1.0,1e-14);
      chk("cx",cx,0.5,1e-14); chk("cy",cy,0.5,1e-14); chk("cz",cz,0.5,1e-14); }

    printf("[2] 뒤틀린 육면체 — 고차 구적과 동일해야 (정확성)\n");
    { Node p[8]={N(1,0,0,0),N(2,1,0,0),N(3,1.2,1.1,0.3),N(4,0,1,0),
                 N(5,0.1,0.2,1),N(6,1.1,-0.1,1.2),N(7,1,1,1),N(8,-0.2,1.1,0.9)};
      computeSolidVolumeAndCentroid(p,V,cx,cy,cz);
      chk("V(뒤틀림)",V,1.06775,1e-5);
      printf("      참고: 5-사면체 분해는 0.986667 (7.6%% 과소)\n"); }

    printf("[3] 실덱 tet 패턴 P1 (A,B,C,D,D,D,D,D) — 해석 V=1/6, c=0.25\n");
    { Node A=N(1,0,0,0),B=N(2,1,0,0),C=N(3,0,1,0),Dn=N(4,0,0,1);
      Node p[8]={A,B,C,Dn,Dn,Dn,Dn,Dn};
      bool ok=computeSolidVolumeAndCentroid(p,V,cx,cy,cz);
      chk("ok",ok?1:0,1,0);
      chk("V(tet P1)",std::abs(V),1.0/6.0,1e-15);
      chk("cx",cx,0.25,1e-15); chk("cy",cy,0.25,1e-15); chk("cz",cz,0.25,1e-15); }

    printf("[4] tet 패턴 P2 (A,B,C,C,D,D,D,D) — 같은 해석해\n");
    { Node A=N(1,0,0,0),B=N(2,1,0,0),C=N(3,0,1,0),Dn=N(4,0,0,1);
      Node p[8]={A,B,C,C,Dn,Dn,Dn,Dn};
      computeSolidVolumeAndCentroid(p,V,cx,cy,cz);
      chk("V(tet P2)",std::abs(V),1.0/6.0,1e-15); chk("cz",cz,0.25,1e-15); }

    printf("[5] 쐐기(wedge) — 해석 V=1, c=(1/3,1/3,1)\n");
    { Node p[8]={N(1,0,0,0),N(2,1,0,0),N(3,0,1,0),N(3,0,1,0),
                 N(5,0,0,2),N(6,1,0,2),N(7,0,1,2),N(7,0,1,2)};
      computeSolidVolumeAndCentroid(p,V,cx,cy,cz);
      chk("V(wedge)",std::abs(V),1.0,1e-13);
      chk("cx",cx,1.0/3,1e-13); chk("cz",cz,1.0,1e-13); }

    printf("[6] 사각뿔(pyramid) — 밑면 1x1, 높이 3: V=1, c_z=0.75\n");
    { Node p[8]={N(1,0,0,0),N(2,1,0,0),N(3,1,1,0),N(4,0,1,0),
                 N(5,.5,.5,3),N(5,.5,.5,3),N(5,.5,.5,3),N(5,.5,.5,3)};
      computeSolidVolumeAndCentroid(p,V,cx,cy,cz);
      chk("V(pyramid)",std::abs(V),1.0,1e-13); chk("cz",cz,0.75,1e-13); }

    printf("[7] 완전 축퇴(모든 절점 동일) — 실패로 알려야\n");
    { Node p[8]; for(int i=0;i<8;++i) p[i]=N(9,1,2,3);
      bool ok=computeSolidVolumeAndCentroid(p,V,cx,cy,cz);
      chk("ok(=false)",ok?1:0,0,0); }

    printf("[8] 등가응력 / 등가변형률\n");
    chk("sig 단축",equivalentStress(100,0,0,0,0,0),100.0,1e-12);
    chk("sig 순수전단",equivalentStress(0,0,0,50,0,0),50*std::sqrt(3.0),1e-12);
    chk("sig 정수압=0",equivalentStress(80,80,80,0,0,0),0.0,1e-12);
    chk("eps 단축비압축",equivalentStrain(0.01,-0.005,-0.005,0,0,0),0.01,1e-15);
    chk("eps 정수압=0",equivalentStrain(0.02,0.02,0.02,0,0,0),0.0,1e-15);

    printf("[9] 대표 요소 크기 — 중앙값의 세제곱근\n");
    { std::vector<double> v={1,8,27,1000000};   // 중앙값=(8+27)/2=17.5
      chk("size",representativeElementSize(v),std::cbrt(17.5),1e-12);
      std::vector<double> v2={-1,0,8};          // 유효한 것만 -> {8}
      chk("size(무효 제외)",representativeElementSize(v2),2.0,1e-12);
      std::vector<double> v3;
      chk("size(빈 입력)",representativeElementSize(v3),0.0,0); }

    printf("[10] 군집화 — 떨어진 두 덩어리\n");
    { std::vector<ClusterElement> e;
      for(int i=0;i<5;++i){ ClusterElement c; c.x=i*1.0; c.y=0; c.z=0; e.push_back(c); }
      for(int i=0;i<4;++i){ ClusterElement c; c.x=100+i*1.0; c.y=0; c.z=0; e.push_back(c); }
      auto lab=clusterByDistance(e,1.5);
      int n0=0,n1=0; for(size_t i=0;i<lab.size();++i){ if(lab[i]==lab[0])n0++; else n1++; }
      chk("덩어리1 개수",n0,5,0); chk("덩어리2 개수",n1,4,0);
      int distinct=0; std::vector<int> seen;
      for(int l:lab){ bool f=false; for(int s:seen) if(s==l) f=true; if(!f){seen.push_back(l);distinct++;} }
      chk("덩어리 수",distinct,2,0); }

    printf("[11] 군집화 — 임계값 미만이면 전부 분리\n");
    { std::vector<ClusterElement> e;
      for(int i=0;i<6;++i){ ClusterElement c; c.x=i*10.0; c.y=0; c.z=0; e.push_back(c); }
      auto lab=clusterByDistance(e,1.0);
      std::vector<int> seen; for(int l:lab){bool f=false;for(int s:seen)if(s==l)f=true;if(!f)seen.push_back(l);}
      chk("전부 개별",seen.size(),6,0); }

    printf("[12] 군집화 — 사슬 연결(단일 연결)은 하나로\n");
    { std::vector<ClusterElement> e;
      for(int i=0;i<50;++i){ ClusterElement c; c.x=i*1.0; c.y=0; c.z=0; e.push_back(c); }
      auto lab=clusterByDistance(e,1.1);
      std::vector<int> seen; for(int l:lab){bool f=false;for(int s:seen)if(s==l)f=true;if(!f)seen.push_back(l);}
      chk("사슬은 1덩어리",seen.size(),1,0); }

    printf("[13] 군집화 — 빈 입력 / 임계값 0\n");
    { std::vector<ClusterElement> e; auto lab=clusterByDistance(e,1.0);
      chk("빈 입력",lab.size(),0,0);
      std::vector<ClusterElement> e2(3); auto l2=clusterByDistance(e2,0.0);
      std::vector<int> seen; for(int l:l2){bool f=false;for(int s:seen)if(s==l)f=true;if(!f)seen.push_back(l);}
      chk("임계 0 -> 전부 분리",seen.size(),3,0); }

    printf("\n%s  실패 %d 건\n", fails?"[FAIL]":"[PASS]", fails);
    return fails?1:0;
}
