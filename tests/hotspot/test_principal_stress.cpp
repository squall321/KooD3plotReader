// 기존 principalStresses() 감사 — 해석적 고유값과 대조
#include "kood3plot/analysis/VectorMath.hpp"
#include <cstdio>
#include <cmath>
#include <array>
#include <algorithm>
using namespace kood3plot::analysis;
static int fails=0;
static void chk(const char*n,double g,double w,double t){
    double e=std::abs(g-w); bool ok=e<=t; if(!ok)++fails;
    printf("  %s %-40s got=%+.10g want=%+.10g err=%.2g\n",ok?"OK ":"NG ",n,g,w,e);
}
int main(){
    printf("[1] 대각 텐서 — 고유값 = 대각 성분\n");
    { StressTensor t(300,-100,50,0,0,0); auto p=t.principalStresses();
      chk("s1",p[0],300,1e-9); chk("s2",p[1],50,1e-9); chk("s3",p[2],-100,1e-9); }

    printf("[2] 순수 전단 (sxy=tau) — 고유값 {tau,0,-tau}\n");
    { double tau=75; StressTensor t(0,0,0,tau,0,0); auto p=t.principalStresses();
      chk("s1",p[0],tau,1e-9); chk("s2",p[1],0,1e-9); chk("s3",p[2],-tau,1e-9); }

    printf("[3] 정수압 — 전부 동일\n");
    { StressTensor t(120,120,120,0,0,0); auto p=t.principalStresses();
      chk("s1",p[0],120,1e-9); chk("s2",p[1],120,1e-9); chk("s3",p[2],120,1e-9); }

    printf("[4] 단축 인장 — {S,0,0}  (Lode 코너: acos 정밀도 한계, 상대 기준)\n");
    { StressTensor t(250,0,0,0,0,0); auto p=t.principalStresses();
      chk("s1",p[0],250,1e-9);
      chk("s2 상대",std::abs(p[1])/250.0,0.0,1e-7);
      chk("s3 상대",std::abs(p[2])/250.0,0.0,1e-7);
      printf("      절대오차 %.3g (250 대비 상대 %.2g) — 공학적 무시 가능\n",
             std::abs(p[1]), std::abs(p[1])/250.0); }

    printf("[4b] 정상 스케일 — numpy eigvalsh 독립 계산과 대조 (회귀 없음 확인)\n");
    { StressTensor t(120,-45,67,23,-31,18); auto p=t.principalStresses();
      chk("s1",p[0], 126.6302442886,1e-8);
      chk("s2",p[1],  72.4485502967,1e-8);
      chk("s3",p[2], -57.0787945853,1e-8); }

    printf("[5] 일반 텐서 — 특성방정식 잔차로 검증\n");
    { StressTensor t(120,-45,67,23,-31,18); auto p=t.principalStresses();
      double I1=120-45+67;
      double I2=120*(-45)+(-45)*67+67*120 - (23*23+(-31)*(-31)+18*18);
      double I3=120*((-45)*67-(-31)*(-31)) - 23*(23*67-(-31)*18) + 18*(23*(-31)-(-45)*18);
      for(int i=0;i<3;++i){
        double s=p[i];
        double res=s*s*s - I1*s*s + I2*s - I3;   // 특성방정식 = 0 이어야
        char nm[48]; snprintf(nm,sizeof nm,"특성방정식 잔차 s%d",i+1);
        chk(nm,res,0.0,1e-6);
      }
      chk("합 = I1",p[0]+p[1]+p[2],I1,1e-9);
      chk("곱 = I3",p[0]*p[1]*p[2],I3,1e-6);
      chk("정렬 s1>=s2",p[0]>=p[1]?1:0,1,0);
      chk("정렬 s2>=s3",p[1]>=p[2]?1:0,1,0); }

    printf("[6] 두 고유값 중복 (축대칭) — {100,100,-50}\n");
    { StressTensor t(100,100,-50,0,0,0); auto p=t.principalStresses();
      chk("s1",p[0],100,1e-8); chk("s2",p[1],100,1e-8); chk("s3",p[2],-50,1e-8); }

    printf("[7] von Mises 일치 — sqrt(3*J2) 와 성분식\n");
    { StressTensor t(120,-45,67,23,-31,18);
      auto p=t.principalStresses();
      double vm_p=std::sqrt(0.5*((p[0]-p[1])*(p[0]-p[1])+(p[1]-p[2])*(p[1]-p[2])+(p[2]-p[0])*(p[2]-p[0])));
      double d1=120-(-45),d2=-45-67,d3=67-120;
      double vm_c=std::sqrt(0.5*(d1*d1+d2*d2+d3*d3)+3.0*(23*23+(-31)*(-31)+18*18));
      chk("주응력식 == 성분식",vm_p,vm_c,1e-8); }

    printf("[8] 큰 스케일 (Pa 단위, 1e9) — 임계값 1e-20 이 문제되나\n");
    { StressTensor t(2.5e8,-1.1e8,7e7,3e7,-2e7,1e7); auto p=t.principalStresses();
      chk("합 = I1",p[0]+p[1]+p[2],2.5e8-1.1e8+7e7,1e-2); }

    printf("[9] 아주 작은 스케일 (1e-12) — isZero(1e-20) 조기반환 오작동?\n");
    { StressTensor t(1e-12,-4e-13,2e-13,0,0,0); auto p=t.principalStresses();
      printf("      s=(%.4g, %.4g, %.4g)\n",p[0],p[1],p[2]);
      chk("s1",p[0],1e-12,1e-20); chk("s3",p[2],-4e-13,1e-20); }

    printf("\n%s  실패 %d 건\n", fails?"[FAIL]":"[PASS]", fails);
    return fails?1:0;
}
