# Fibonacci Sphere Sampling + Mollweide Projection을 이용한 전각도 낙하 응력 분석

## 1. 문제 정의: 왜 전각도 낙하 시험이 필요한가

제품 낙하 시험에서 충격 방향은 **단위 구(unit sphere) S² 위의 한 점**으로 표현된다.
기존 규격(IEC 60068-2-31 등)은 면(face) 6방향, 모서리(edge) 12방향, 꼭짓점(corner) 8방향 — 총 26방향만 평가한다.

$$
\mathbf{d} = (\sin\theta\cos\phi,\; \sin\theta\sin\phi,\; \cos\theta) \in S^2
$$

여기서 θ는 극각(polar angle), φ는 방위각(azimuthal angle)이다.

26방향은 정육면체의 대칭축에 해당하며, 이들 사이의 "빈 공간"에 최악 방향이 존재할 수 있다. 예를 들어 면과 모서리 사이의 중간 각도, 또는 꼭짓점에서 약간 벗어난 방향에서 응력이 최대가 되는 경우가 흔하다.

**전각도 낙하 분석의 목적**: 구 전체를 균일하게 샘플링하여, 방향 의존적 응력 분포의 전체 맵을 구성하고, 최악 방향을 놓치지 않는 것.

---

## 2. Fibonacci Lattice Sampling

### 2.1 알고리즘

Fibonacci lattice는 **황금비(golden ratio)**를 이용하여 구 위에 N개의 점을 준균일(quasi-uniform)하게 배치하는 방법이다.

$$
\phi = \frac{1 + \sqrt{5}}{2} \approx 1.6180 \quad \text{(황금비)}
$$

N개의 점 $\mathbf{p}_k$ ($k = 0, 1, \ldots, N-1$)의 구면 좌표:

$$
\theta_k = \arccos\!\left(1 - \frac{2k + 1}{N}\right)
$$

$$
\varphi_k = 2\pi k \cdot \frac{1}{\phi^2} = 2\pi k \cdot (2 - \phi) \approx 2\pi k \cdot 0.3820
$$

여기서:
- $\theta_k$ — 극각. $\cos\theta$를 $[1, -1]$ 구간에서 균등 분할하여 **위도 방향 균일성**을 보장
- $\varphi_k$ — 방위각. 황금비의 제곱의 역수($\phi^{-2}$)만큼 회전하여 **경도 방향 비반복 분산**을 달성

### 2.2 왜 황금비인가

황금비는 "가장 무리수적인 무리수(most irrational number)"로, 연분수 전개에서 모든 계수가 1이다:

$$
\phi = 1 + \cfrac{1}{1 + \cfrac{1}{1 + \cfrac{1}{1 + \cdots}}}
$$

이 성질 때문에 연속적인 점들이 가장 균일하게 분산된다. 각 새로운 점은 기존 점들 사이의 **가장 큰 간격(largest gap)**을 분할하는 경향이 있어, 임의의 N에서도 준최적 분포를 달성한다.

### 2.3 Cuboid 26방향과의 비교

| 항목 | Cuboid 26 | Fibonacci 100 | Fibonacci 1,146 |
|------|-----------|---------------|-----------------|
| 방향 수 | 26 | 100 | 1,146 |
| 평균 이웃 간격 | 15.9° | 7.9° | ~6° |
| 구 커버리지 | ~12% | ~12% | ~99% |
| 분포 특성 | 정육면체 대칭축만 | 준균일 | 준균일, 고밀도 |
| 최악 방향 탐지 | 제한적 | 양호 | 우수 |
| 시뮬레이션 비용 | 낮음 | 중간 | 높음 |

**Cuboid의 한계**: 26방향은 정육면체 기하학에 종속되어 있어, 면과 모서리 사이의 약 15°~30° 범위의 방향을 전혀 평가하지 못한다. 제품 형상이 직육면체가 아닌 경우(비대칭 내부 구조, 편심 질량 등) 최악 방향이 이 "사각지대"에 놓일 확률이 높다.

**Fibonacci의 장점**: N을 임의로 설정 가능하며, 어떤 N에서도 구 위의 점 분포가 준균일하다. 또한 격자 구조가 없으므로 aliasing(격자 아티팩트)이 없고, **방향 해상도 ↔ 시뮬레이션 비용**의 트레이드오프를 자유롭게 조절할 수 있다.

### 2.4 최소 샘플 수 결정

평균 이웃 간격 $\Delta\theta$는 다음으로 근사된다:

$$
\Delta\theta \approx \sqrt{\frac{4\pi}{N}} \quad \text{(rad)} = \sqrt{\frac{4\pi}{N}} \cdot \frac{180}{\pi} \quad \text{(deg)}
$$

| 목표 해상도 | 필요 N |
|------------|--------|
| 30° | ~46 |
| 15° | ~183 |
| 10° | ~413 |
| 6° | ~1,146 |
| 3° | ~4,584 |
| 1° | ~41,253 |

참고: 구의 총 제곱도(square degrees)는 4π × (180/π)² ≈ 41,253이므로, 1° 해상도는 구 전체를 1° × 1° 셀로 분할하는 것과 동일한 밀도이다.

전각도 낙하 시험에서는 일반적으로 **6°~10° 해상도**가 산업적으로 충분하며, 이는 N = 100~500에 해당한다.

---

## 3. Mollweide Projection (몰바이데 도법)

### 3.1 정의

Mollweide 도법은 **등적(equal-area)** 의사원통 도법으로, 구 위의 면적비가 평면에서도 보존된다. 지도학에서 전세계 분포 패턴 시각화에 사용되며, 본 시스템에서는 충격 방향별 응력 분포를 시각화한다.

경도 λ, 위도 φ에 대해 투영 좌표 (x, y):

$$
x = \frac{2\sqrt{2}}{\pi} \lambda \cos\theta
$$

$$
y = \sqrt{2} \sin\theta
$$

여기서 보조각(auxiliary angle) θ는 다음 방정식의 해이다:

$$
2\theta + \sin(2\theta) = \pi \sin\phi
$$

이 초월방정식은 해석적 해가 없으므로, **Newton-Raphson 반복법**으로 풀이한다:

$$
\theta_{n+1} = \theta_n - \frac{2\theta_n + \sin(2\theta_n) - \pi\sin\phi}{2 + 2\cos(2\theta_n)}
$$

### 3.2 등적 성질의 의미

Mollweide 도법의 핵심은 **등적(equal-area)** 성질이다:

$$
\iint_{S^2} f(\theta, \phi)\, dA = \iint_{\text{map}} f(x, y)\, dx\, dy
$$

이것이 응력 분석에서 중요한 이유:

1. **시각적 면적 비례**: 맵에서 빨간(고응력) 영역의 넓이가 실제 구 위에서 위험 방향이 차지하는 입체각(solid angle)에 비례한다.
2. **정량적 해석 가능**: "전체 방향의 30%에서 항복 응력을 초과"와 같은 진술이 맵의 면적 비율로 직접 읽힌다.
3. **편향 없는 비교**: 극지방과 적도 지역의 면적이 동일하게 표현되어, 특정 방향이 과대/과소 대표되지 않는다.

참고로, 일반 정사각형 위경도 격자(equirectangular projection)에서는 극지방이 심하게 왜곡되어 면적 비율이 의미를 잃는다.

### 3.3 역변환 (Inverse Mollweide)

IDW 보간에서 맵 픽셀 → 구면 좌표 역변환이 필요하다:

$$
\theta = \arcsin\!\left(\frac{y}{\sqrt{2}}\right)
$$

$$
\phi = \arcsin\!\left(\frac{2\theta + \sin(2\theta)}{\pi}\right)
$$

$$
\lambda = \frac{\pi x}{2\sqrt{2}\cos\theta}
$$

### 3.4 Newton-Raphson 수렴 안정화

표준 Newton-Raphson은 특정 위도에서 발산할 수 있다. 도함수 $f'(\theta) = 2 + 2\cos(2\theta)$가 $\theta = \pm\pi/4$ 부근에서 작아지면 스텝이 과도하게 커져 theta가 유효 범위 $[-\pi/2, \pi/2]$를 벗어나고, $\sin(\text{huge number})$가 무작위 값을 반환하여 y좌표가 뒤집히는 현상이 발생한다.

해결: **감쇠 Newton-Raphson (Damped Newton-Raphson)**

$$
\theta_{n+1} = \text{clamp}\!\left(\theta_n - \text{clamp}(\Delta\theta,\, -0.3,\, 0.3),\; -\frac{\pi}{2}+\epsilon,\; \frac{\pi}{2}-\epsilon\right)
$$

- 스텝 크기를 최대 0.3 rad로 제한
- θ를 항상 $[-\pi/2+\epsilon,\, \pi/2-\epsilon]$ 범위로 클램핑
- 극점($|\phi| > \pi/2 - \epsilon$)에서는 직접 $\theta = \pm\pi/2$ 할당

---

## 4. IDW (Inverse Distance Weighting) 구면 보간

### 4.1 알고리즘

N개의 데이터 포인트 $(\lambda_i, \phi_i, v_i)$가 주어졌을 때, 임의의 위치 $(\lambda_0, \phi_0)$에서의 보간값:

$$
\hat{v}(\lambda_0, \phi_0) = \frac{\sum_{i=1}^{N} w_i \cdot v_i}{\sum_{i=1}^{N} w_i}
$$

$$
w_i = \frac{1}{d(\mathbf{p}_0, \mathbf{p}_i)^p}
$$

여기서 $d(\mathbf{p}_0, \mathbf{p}_i)$는 **구면 대원 거리(great-circle distance, Haversine 공식)**:

$$
d = 2\arcsin\!\sqrt{\sin^2\!\frac{\Delta\phi}{2} + \cos\phi_1\cos\phi_2\sin^2\!\frac{\Delta\lambda}{2}}
$$

### 4.2 파라미터 선택

| 파라미터 | 값 | 이유 |
|---------|-----|------|
| 거듭제곱 p | 3.5 | 높은 값 → 날카로운 피크, 데이터 포인트에서 정확한 값 보존 |
| Snap 반경 | 0.02 rad (~1.1°) | 데이터 포인트 근처에서 보간 대신 정확값 사용 |
| 그리드 스텝 | 3px | 성능과 정밀도의 균형. 이중선형 보간으로 픽셀 해상도 복원 |

거듭제곱 p의 선택은 시각화 품질에 직접 영향을 미친다:
- **p = 2** (표준): 부드러운 보간이지만 피크가 퍼져서 최대값이 보존되지 않음
- **p = 3.5** (본 시스템): 데이터 포인트 위치에서 원래 값이 거의 정확히 재현되면서도 사이 영역은 자연스럽게 보간

### 4.3 왜 구면 거리인가

Mollweide 맵 좌표 상의 유클리드 거리 대신 구면 대원 거리를 사용하는 이유:

$$
d_{\text{euclidean}}(\mathbf{p}, \mathbf{q}) \neq d_{\text{spherical}}(\mathbf{p}, \mathbf{q})
$$

Mollweide 도법은 등적이지만 **등거(equidistant)**는 아니다. 즉, 맵 상의 직선 거리가 실제 구면 거리와 일치하지 않는다. 유클리드 거리를 사용하면:

- 극지방 근처에서 가까운 점이 멀게, 먼 점이 가깝게 계산됨
- 경도 ±180° 경계에서 불연속 발생
- 보간 결과에 투영 왜곡이 그대로 반영

구면 거리를 사용하면 투영 방식에 무관하게 물리적으로 정확한 보간이 이루어진다.

---

## 5. 충격 방향 매핑

### 5.1 3D 방향 벡터 → (경도, 위도)

충격 방향 벡터 $\mathbf{d} = (d_x, d_y, d_z)$를 몰바이데 맵 좌표로 변환:

$$
\lambda = \text{atan2}(d_x,\, -d_z) \quad \text{(경도)}
$$

$$
\phi = \arcsin(d_y) \quad \text{(위도)}
$$

**좌표 컨벤션**:
- 맵 중심 (0°, 0°) = Back 방향 (-Z)
- 동쪽 (+90°) = Right 방향 (+X)
- 서쪽 (-90°) = Left 방향 (-X)
- 북극 (+90°) = Top 방향 (+Y)
- 남극 (-90°) = Bottom 방향 (-Y)
- ±180° = Front 방향 (+Z)

### 5.2 Euler 각도에서의 변환

시뮬레이션에서 충격 방향은 Euler 각도 (roll, pitch, yaw)로 정의된다. 초기 충격 벡터 $[0, 0, -1]$에 회전 행렬을 적용:

$$
\mathbf{d} = R_x(\text{roll}) \cdot R_y(\text{pitch}) \cdot R_z(\text{yaw}) \cdot \begin{bmatrix}0\\0\\-1\end{bmatrix}
$$

전개하면:

$$
d_x = -\sin(\text{pitch})
$$
$$
d_y = \sin(\text{roll})\cos(\text{pitch})
$$
$$
d_z = -\cos(\text{roll})\cos(\text{pitch})
$$

---

## 6. 분석 파이프라인 요약

```
                    ┌──────────────────────┐
                    │  Fibonacci Sampling   │
                    │  N개 방향 (θₖ, φₖ)    │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  LS-DYNA Simulation   │
                    │  방향별 d3plot 출력     │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Unified Analyzer     │
                    │  응력/변형률/가속도 추출  │
                    └──────────┬───────────┘
                               │
              ┌────────────────▼────────────────┐
              │  KooReport                       │
              │  ┌──────────────────────────────┐│
              │  │ Euler → 방향벡터 → (λ, φ)    ││
              │  │ Mollweide 투영 (λ,φ) → (x,y) ││
              │  │ 구면 IDW 보간                  ││
              │  │ 컨투어 맵 렌더링               ││
              │  └──────────────────────────────┘│
              └─────────────────────────────────┘
```

## 7. 결론

Fibonacci lattice sampling과 Mollweide equal-area projection의 조합은 전각도 낙하 시뮬레이션 분석에 다음과 같은 이점을 제공한다:

1. **균일 샘플링**: 구 위의 모든 방향을 편향 없이 평가하여 최악 방향을 놓치지 않음
2. **확장 가능성**: 26개(cuboid) → 100개 → 1,000개로 점진적으로 해상도를 높일 수 있음
3. **등적 시각화**: 맵에서 위험 영역의 넓이가 실제 입체각에 비례하여 정량적 해석 가능
4. **투영 무관 보간**: 구면 대원 거리 기반 IDW가 투영 왜곡을 완전히 회피
5. **산업 적용성**: 기존 26방향 규격과 호환되면서도, 제품 형상 의존적 취약 방향을 추가로 탐지

---

## 참고 문헌

1. González, Á. (2010). "Measurement of areas on a sphere using Fibonacci and latitude–longitude lattices." *Mathematical Geosciences*, 42(1), 49–64.
2. Swinbank, R., & Purser, R. J. (2006). "Fibonacci grids: A novel approach to global modelling." *Quarterly Journal of the Royal Meteorological Society*, 132(619), 1769–1793.
3. Snyder, J. P. (1987). *Map Projections — A Working Manual*. U.S. Geological Survey Professional Paper 1395. (Mollweide projection: pp. 249–252)
4. Shepard, D. (1968). "A two-dimensional interpolation function for irregularly-spaced data." *Proceedings of the 1968 ACM National Conference*, 517–524. (IDW 원 논문)
5. IEC 60068-2-31:2008. *Environmental testing — Part 2-31: Tests — Test Ec: Rough handling shocks, primarily for equipment-type specimens.*
