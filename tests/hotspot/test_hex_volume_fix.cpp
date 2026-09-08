// computeHexVolume 수정 검증 — 실제 구현의 isoparametricHexVolume 대조
#include "kood3plot/analysis/HotspotClusterAnalyzer.hpp"
#include <cstdio>
#include <cmath>
using namespace kood3plot;
using namespace kood3plot::analysis;
static int fails=0;
static void chk(const char*n,double g,double w,double t){
    double e=std::abs(g-w); bool ok=e<=t; if(!ok)++fails;
    printf("  %s %-34s got=%.12g want=%.12g err=%.2g\n",ok?"OK ":"NG ",n,g,w,e);
}
static double tet(const double a[3],const double b[3],const double c[3],const double d[3]){
    double u[3],v[3],w[3];
    for(int i=0;i<3;++i){u[i]=b[i]-a[i];v[i]=c[i]-a[i];w[i]=d[i]-a[i];}
    return (u[0]*(v[1]*w[2]-v[2]*w[1])-u[1]*(v[0]*w[2]-v[2]*w[0])+u[2]*(v[0]*w[1]-v[1]*w[0]))/6.0;
}
static double old5tet(const double p[8][3]){
    return tet(p[0],p[1],p[3],p[4])+tet(p[1],p[2],p[3],p[6])+tet(p[1],p[4],p[5],p[6])
          +tet(p[3],p[4],p[6],p[7])+tet(p[1],p[3],p[4],p[6]);
}
int main(){
    printf("[A] 정육면체 — 두 방식 모두 정확해야 (회귀 없음)\n");
    { double p[8][3]={{0,0,0},{1,0,0},{1,1,0},{0,1,0},{0,0,1},{1,0,1},{1,1,1},{0,1,1}};
      chk("새 구적",isoparametricHexVolume(p),1.0,1e-14);
      chk("기존 5-tet",old5tet(p),1.0,1e-14); }

    printf("[B] 평면면 직육면체(비등방) — 회귀 없음\n");
    { double p[8][3]={{0,0,0},{3,0,0},{3,7,0},{0,7,0},{0,0,11},{3,0,11},{3,7,11},{0,7,11}};
      chk("새 구적",isoparametricHexVolume(p),231.0,1e-11);
      chk("기존 5-tet",old5tet(p),231.0,1e-11); }

    printf("[C] 전단 평행육면체 — 회귀 없음\n");
    { double p[8][3];
      double a[3]={2,0,0},b[3]={1,3,0},c[3]={0.5,0.7,4};
      int bs[8][3]={{0,0,0},{1,0,0},{1,1,0},{0,1,0},{0,0,1},{1,0,1},{1,1,1},{0,1,1}};
      for(int i=0;i<8;++i)for(int r=0;r<3;++r)
          p[i][r]=bs[i][0]*a[r]+bs[i][1]*b[r]+bs[i][2]*c[r];
      chk("새 구적",isoparametricHexVolume(p),24.0,1e-11);
      chk("기존 5-tet",old5tet(p),24.0,1e-11); }

    printf("[D] 뒤틀린 육면체 — 여기서 갈린다\n");
    { double p[8][3]={{0,0,0},{1,0,0},{1.2,1.1,0.3},{0,1,0},
                      {0.1,0.2,1},{1.1,-0.1,1.2},{1,1,1},{-0.2,1.1,0.9}};
      double vn=isoparametricHexVolume(p), vo=old5tet(p);
      printf("      새 구적=%.12g  기존 5-tet=%.12g  기존 오차=%+.4f%%\n",
             vn,vo,100.0*(vo-vn)/vn);
      chk("새 구적(정확값)",vn,1.06775,1e-5); }

    printf("[E] 부호 보존 — 뒤집힌 요소는 음수여야\n");
    { double p[8][3]={{0,0,1},{1,0,1},{1,1,1},{0,1,1},{0,0,0},{1,0,0},{1,1,0},{0,1,0}};
      double v=isoparametricHexVolume(p);
      printf("      상하 뒤집은 정육면체 V=%.12g\n", v);
      chk("음수",v<0?1:0,1,0); chk("크기",std::abs(v),1.0,1e-14); }

    printf("[F] 쐐기·사각뿔 축퇴 — 회귀 없음\n");
    { double w[8][3]={{0,0,0},{1,0,0},{0,1,0},{0,1,0},{0,0,2},{1,0,2},{0,1,2},{0,1,2}};
      chk("wedge 새",std::abs(isoparametricHexVolume(w)),1.0,1e-13);
      chk("wedge 기존",std::abs(old5tet(w)),1.0,1e-13);
      double q[8][3]={{0,0,0},{1,0,0},{1,1,0},{0,1,0},{.5,.5,3},{.5,.5,3},{.5,.5,3},{.5,.5,3}};
      chk("pyramid 새",std::abs(isoparametricHexVolume(q)),1.0,1e-13);
      chk("pyramid 기존",std::abs(old5tet(q)),1.0,1e-13); }

    printf("[G] 두 경로 일관성 — isoparametricHexVolume vs computeSolidVolumeAndCentroid\n");
    { Node n[8]; double p[8][3]={{0,0,0},{1,0,0},{1.2,1.1,0.3},{0,1,0},
                                 {0.1,0.2,1},{1.1,-0.1,1.2},{1,1,1},{-0.2,1.1,0.9}};
      for(int i=0;i<8;++i){ n[i].id=i+1; n[i].x=p[i][0]; n[i].y=p[i][1]; n[i].z=p[i][2]; }
      double V,cx,cy,cz; computeSolidVolumeAndCentroid(n,V,cx,cy,cz);
      chk("두 경로 동일",V,isoparametricHexVolume(p),0.0); }

    printf("\n%s  실패 %d 건\n", fails?"[FAIL]":"[PASS]", fails);
    return fails?1:0;
}
