// 셸 면적·도심과 두꺼운 셸 면내 크기 추정을 해석해·고해상도 기준값과 대조
#include "kood3plot/analysis/HotspotClusterAnalyzer.hpp"
#include <cstdio>
#include <cmath>
using namespace kood3plot;
using namespace kood3plot::analysis;

static int fails = 0;
static void chk(const char* n, double g, double w, double tol) {
    double e = std::abs(g - w); bool ok = e <= tol * std::max(1.0, std::abs(w)); if (!ok) ++fails;
    printf("  %s %-50s got=%.12g want=%.12g err=%.2g\n", ok?"OK ":"NG ", n, g, w, e);
}
static Node N(int id, double x, double y, double z) { Node n; n.id=id; n.x=x; n.y=y; n.z=z; return n; }

// 기준값: [-1,1]^2 를 m×m 하위 사각형으로 쪼개 각 칸에 4점 가우스 — 사실상 정확
static void refQuad(const Node* p, int m, double& A, double& cx, double& cy, double& cz) {
    static const double gx[4]={-0.8611363115940526,-0.3399810435848563,0.3399810435848563,0.8611363115940526};
    static const double gw[4]={0.3478548451374538,0.6521451548625461,0.6521451548625461,0.3478548451374538};
    static const double qx[4]={-1,1,1,-1}, qy[4]={-1,-1,1,1};
    A=cx=cy=cz=0; const double h=2.0/m;
    for (int a=0;a<m;++a) for (int b=0;b<m;++b) for (int i=0;i<4;++i) for (int j=0;j<4;++j) {
        double xi=-1+h*(a+0.5*(gx[i]+1)), et=-1+h*(b+0.5*(gx[j]+1)), w=gw[i]*gw[j]*h*h/4;
        double P[3]={0,0,0},T[3]={0,0,0},S[3]={0,0,0};
        for(int k=0;k<4;++k){ double u=1+qx[k]*xi, v=1+qy[k]*et; double c[3]={p[k].x,p[k].y,p[k].z};
            for(int r=0;r<3;++r){ P[r]+=0.25*u*v*c[r]; T[r]+=0.25*qx[k]*v*c[r]; S[r]+=0.25*qy[k]*u*c[r]; } }
        double nx=T[1]*S[2]-T[2]*S[1], ny=T[2]*S[0]-T[0]*S[2], nz=T[0]*S[1]-T[1]*S[0];
        double dA=std::sqrt(nx*nx+ny*ny+nz*nz)*w; A+=dA; cx+=P[0]*dA; cy+=P[1]*dA; cz+=P[2]*dA;
    }
    cx/=A; cy/=A; cz/=A;
}

int main(){
    double A,cx,cy,cz;
    printf("[1] 평면 직사각형 3×2 (z=5)\n");
    { Node p[4]={N(1,0,0,5),N(2,3,0,5),N(3,3,2,5),N(4,0,2,5)};
      computeShellAreaAndCentroid(p,A,cx,cy,cz);
      chk("면적 6",A,6,1e-14); chk("cx 1.5",cx,1.5,1e-14); chk("cy 1",cy,1,1e-14); chk("cz 5",cz,5,1e-14); }

    printf("[2] 평면 사다리꼴 (밑변 4, 윗변 2, 높이 3) — 도심 y = h(a+2b)/(3(a+b))\n");
    { Node p[4]={N(1,0,0,0),N(2,4,0,0),N(3,3,3,0),N(4,1,3,0)};
      computeShellAreaAndCentroid(p,A,cx,cy,cz);
      chk("면적 9",A,9,1e-14); chk("cx 2 (대칭)",cx,2,1e-14);
      chk("cy = 3·(4+2·2)/(3·6) = 4/3",cy,3.0*(4+2*2)/(3.0*6),1e-14); }

    printf("[3] 평면 일반 볼록 사각형 — 두 삼각형 면적가중 도심과 일치\n");
    { Node p[4]={N(1,0,0,0),N(2,5,1,0),N(3,4,4,0),N(4,-1,3,0)};
      computeShellAreaAndCentroid(p,A,cx,cy,cz);
      auto tri=[](const Node&a,const Node&b,const Node&c,double&ar,double&x,double&y){
          ar=0.5*std::abs((b.x-a.x)*(c.y-a.y)-(c.x-a.x)*(b.y-a.y)); x=(a.x+b.x+c.x)/3; y=(a.y+b.y+c.y)/3; };
      double a1,x1,y1,a2,x2,y2; tri(p[0],p[1],p[2],a1,x1,y1); tri(p[0],p[2],p[3],a2,x2,y2);
      chk("면적",A,a1+a2,1e-13); chk("cx",cx,(a1*x1+a2*x2)/(a1+a2),1e-13); chk("cy",cy,(a1*y1+a2*y2)/(a1+a2),1e-13);
      // 기울어진 평면에 놓아도 같아야 한다 (3D 회전 불변)
      Node q[4]; for(int i=0;i<4;++i){ q[i]=p[i]; double y=p[i].y; q[i].y=y*0.6; q[i].z=y*0.8+2; }
      double A2,x3,y3,z3; computeShellAreaAndCentroid(q,A2,x3,y3,z3);
      chk("기울인 평면 면적 불변",A2,a1+a2,1e-13); chk("기울인 평면 cz = 0.8·cy+2",z3,0.8*cy+2,1e-13); }

    printf("[4] 삼각형 (4번 = 3번 절점)\n");
    { Node p[4]={N(1,0,0,0),N(2,4,0,0),N(3,0,3,0),N(3,0,3,0)};
      bool ok=computeShellAreaAndCentroid(p,A,cx,cy,cz);
      chk("유효",ok,1,0); chk("면적 6",A,6,1e-14); chk("cx 4/3",cx,4.0/3,1e-14); chk("cy 1",cy,1,1e-14); }

    printf("[5] 완전 축퇴(고유 절점 2개) → 무효\n");
    { Node p[4]={N(1,0,0,0),N(2,1,0,0),N(2,1,0,0),N(1,0,0,0)};
      chk("무효",computeShellAreaAndCentroid(p,A,cx,cy,cz),0,0); }

    printf("[6] 뒤틀린 사각형 — 고해상도 기준값 대비 (피적분함수 비다항식)\n");
    for (double warp : {0.1, 0.5, 1.0}) {
        Node p[4]={N(1,0,0,0),N(2,2,0,warp),N(3,2,2,0),N(4,0,2,warp)};
        computeShellAreaAndCentroid(p,A,cx,cy,cz);
        double Ar,xr,yr,zr; refQuad(p,32,Ar,xr,yr,zr);
        char b[96];
        snprintf(b,sizeof b,"warp=%.1f 면적 상대오차",warp); chk(b,A/Ar,1.0,1e-6);
        snprintf(b,sizeof b,"warp=%.1f cz",warp); chk(b,cz,zr,1e-6);
    }

    printf("[7] 두꺼운 셸 면내 크기 √(V/h_min)\n");
    { // 평평한 벽돌 2×2×0.1 — 면내 크기 2, ∛V=0.74 는 면내 간격보다 작다
      Node p[8]={N(1,0,0,0),N(2,2,0,0),N(3,2,2,0),N(4,0,2,0),N(5,0,0,.1),N(6,2,0,.1),N(7,2,2,.1),N(8,0,2,.1)};
      double h=hexMinFaceSeparation(p); chk("h_min = 0.1",h,0.1,1e-14);
      double V,x,y,z; computeSolidVolumeAndCentroid(p,V,x,y,z);
      chk("√(V/h) = 2",std::sqrt(std::abs(V)/h),2.0,1e-13);
      // 절점 순서를 돌려(두께가 1-4→5-8 방향이 아니게) 놓아도 같아야 한다
      Node r[8]={N(1,0,0,0),N(2,0,0,.1),N(3,2,0,.1),N(4,2,0,0),N(5,0,2,0),N(6,0,2,.1),N(7,2,2,.1),N(8,2,2,0)};
      double hr=hexMinFaceSeparation(r); chk("절점 순서 무관 h_min",hr,0.1,1e-14); }
    { Node p[8]={N(1,0,0,0),N(2,1,0,0),N(3,1,1,0),N(4,0,1,0),N(5,0,0,1),N(6,1,0,1),N(7,1,1,1),N(8,0,1,1)};
      double V,x,y,z; computeSolidVolumeAndCentroid(p,V,x,y,z);
      chk("정육면체 √(V/h) = ∛V = 1",std::sqrt(std::abs(V)/hexMinFaceSeparation(p)),1.0,1e-14); }

    printf("\n%s 실패 %d 건\n", fails?"[FAIL]":"[PASS]", fails);
    return fails?1:0;
}
