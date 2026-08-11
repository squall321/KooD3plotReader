// 표면 변형률 분석이 쓰는 텐서 수식(수직/전단/ε1/ε3/ε_vm)을 손계산 값과 대조하는 테스트
/**
 * @file test_surface_strain_math.cpp
 * @brief SurfaceStrainAnalyzer 가 면마다 적용하는 텐서 수식 검증
 *
 * SurfaceStrainAnalyzer 는 d3plot solid 워드 7-12 를 StressTensor 에 담아
 * 응력과 동일한 사영식을 쓴다. 여기서는 그 수식들이 손계산과 맞는지만 본다
 * (워드 오프셋 자체는 SinglePassAnalyzer::extractStrainTensor 와 동일).
 *
 * Run: ./test_surface_strain_math
 */

#include "kood3plot/analysis/VectorMath.hpp"
#include <cmath>
#include <iostream>

using namespace kood3plot::analysis;

namespace {

int g_failed = 0;

void check(const char* what, double got, double want, double eps) {
    const bool ok = std::abs(got - want) <= eps;
    if (!ok) ++g_failed;
    std::cout << (ok ? "  [OK]   " : "  [FAIL] ") << what
              << "  got=" << got << "  want=" << want << "\n";
}

/// SurfaceStrainAnalyzer 안의 ε_vm 식과 같은 형태 (sqrt(2/3 · e_dev:e_dev))
double vonMisesStrain(const StressTensor& e) {
    const double em = (e.xx + e.yy + e.zz) / 3.0;
    const double dxx = e.xx - em, dyy = e.yy - em, dzz = e.zz - em;
    return std::sqrt(2.0 / 3.0 * (dxx * dxx + dyy * dyy + dzz * dzz +
                                  2.0 * (e.xy * e.xy + e.yz * e.yz + e.zx * e.zx)));
}

/// 대각 텐서 — 주변형률이 성분 그대로여서 손계산이 자명하다.
void test_diagonal() {
    std::cout << "대각 텐서 diag(3e-3, 1e-3, -2e-3)\n";
    const StressTensor e(3e-3, 1e-3, -2e-3, 0, 0, 0);

    check("e1 (max principal)", e.maxPrincipal(), 3e-3, 1e-12);
    check("e3 (min principal)", e.minPrincipal(), -2e-3, 1e-12);

    // 평균 = 2/3 e-3. 편차 = (7/3, 1/3, -8/3) e-3.
    // e_vm = sqrt(2/3 · (49+1+64)/9) e-3 = sqrt(2·114/27) e-3
    const double want_vm = std::sqrt(2.0 * 114.0 / 27.0) * 1e-3;
    check("e_vm", vonMisesStrain(e), want_vm, 1e-12);

    // +Z 면(법선 0,0,1) 의 수직 변형률 = ezz, 전단 = 0 (비대각 없음)
    const Vec3 nz(0, 0, 1);
    check("normal on +Z", e.normalStress(nz), -2e-3, 1e-12);
    check("shear  on +Z", e.shearStress(nz), 0.0, 1e-12);

    // +X 면의 수직 = exx
    check("normal on +X", e.normalStress(Vec3(1, 0, 0)), 3e-3, 1e-12);
}

/// 순수 전단 — 주변형률이 ±γ 로 갈리고 수직 성분은 0 이 되어야 한다.
void test_pure_shear() {
    std::cout << "순수 전단 exy = 2e-3\n";
    const double g = 2e-3;
    const StressTensor e(0, 0, 0, g, 0, 0);

    check("e1", e.maxPrincipal(), g, 1e-12);
    check("e3", e.minPrincipal(), -g, 1e-12);

    // 편차 = 텐서 그대로(trace 0). e_vm = sqrt(2/3 · 2·g²) = 2g/sqrt(3)
    check("e_vm", vonMisesStrain(e), 2.0 * g / std::sqrt(3.0), 1e-12);

    // +Z 면: 법선 방향 성분 없음 → 수직 0, 전단도 0 (exy 는 Z 면에 안 실린다)
    check("normal on +Z", e.normalStress(Vec3(0, 0, 1)), 0.0, 1e-12);
    check("shear  on +Z", e.shearStress(Vec3(0, 0, 1)), 0.0, 1e-12);

    // +X 면: e·n = (0, g, 0) → 수직 0, 전단 g
    check("normal on +X", e.normalStress(Vec3(1, 0, 0)), 0.0, 1e-12);
    check("shear  on +X", e.shearStress(Vec3(1, 0, 0)), g, 1e-12);
}

/// ±Z 필터가 서로 다른 값을 주는지 — 상/하면 비대칭 텐서로 확인.
void test_updown_asymmetry() {
    std::cout << "상/하면 비대칭 (ezx 존재)\n";
    const StressTensor e(1e-3, 0, -1e-3, 0, 0, 5e-4);

    const double n_up = e.normalStress(Vec3(0, 0, 1));
    const double n_dn = e.normalStress(Vec3(0, 0, -1));
    // 수직 성분은 n·e·n 이라 부호를 뒤집어도 같다 — 면 방향 필터는
    // '어느 요소를 고르냐' 를 바꾸지 '값의 부호' 를 바꾸지 않는다.
    check("normal(+Z) == normal(-Z)", n_up, n_dn, 1e-15);
    check("normal(+Z) == ezz", n_up, -1e-3, 1e-12);

    // 전단은 |e·n - (n·e·n)n| = |ezx| (n=±Z 일 때)
    check("shear on +Z", e.shearStress(Vec3(0, 0, 1)), 5e-4, 1e-12);
}

}  // namespace

int main() {
    std::cout << "=== SurfaceStrainAnalyzer 텐서 수식 검증 ===\n\n";
    test_diagonal();
    std::cout << "\n";
    test_pure_shear();
    std::cout << "\n";
    test_updown_asymmetry();
    std::cout << "\n";

    if (g_failed) {
        std::cout << g_failed << "건 실패\n";
        return 1;
    }
    std::cout << "전부 통과\n";
    return 0;
}
