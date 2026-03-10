# KooD3plotReader 수학적 이론 기술 문서

**KooD3plotReader / Drop Analysis Platform — 수학적 기반 완전 참조**
작성일: 2026-03-09 | 버전: 2.0

---

## 목차

1. [LS-DYNA d3plot 데이터 구조](#1-ls-dyna-d3plot-데이터-구조)
2. [응력 텐서와 Von Mises 응력](#2-응력-텐서와-von-mises-응력)
3. [변형률 분석](#3-변형률-분석)
4. [낙하 방향 표현 — 오일러 각과 회전 행렬](#4-낙하-방향-표현--오일러-각과-회전-행렬)
5. [피보나치 격자 구면 균등 분포](#5-피보나치-격자-구면-균등-분포)
6. [Mollweide 등적도 투영](#6-mollweide-등적도-투영)
7. [구면 IDW 보간](#7-구면-idw-보간)
8. [요소 품질 지표](#8-요소-품질-지표)
9. [충격 응답 스펙트럼 (SRS)](#9-충격-응답-스펙트럼-srs)
10. [CAI 균열 정지 지수 (Crack Arrest Index)](#10-cai-균열-정지-지수-crack-arrest-index)

---

## 1. LS-DYNA d3plot 데이터 구조

### 1.1 바이너리 포맷 개요

LS-DYNA d3plot은 빅/리틀 엔디안 바이너리 파일로, Fortran unformatted sequential record 형식을 사용한다. 파일은 단일 파일(d3plot)과 연속 패밀리 파일(d3plot01, d3plot02, ...)로 구성된다.

```
파일 구조 (계층):
+-----------------------------+
|   Control Section (헤더)    |  - 제어 워드: NDIM, NUMNP, NEL8, NELSH ...
|   Title Record              |  - 80바이트 ASCII 제목
|   State Independent Data    |  - 절점 좌표, 연결성, 파트 정보
|   ---------------------------
|   State 1 (time = t_1)      |  - 절점 변위/속도/가속도
|   State 2 (time = t_2)      |  - 요소 응력/변형률
|   ...                       |
|   State N (time = t_N)      |
+-----------------------------+
```

**주요 제어 워드 (Control Word)**

| 워드 | 의미 | 소스 위치 |
|------|------|-----------|
| `NDIM` | 차원 수 (일반적으로 3) | `ControlData.hpp` |
| `NUMNP` | 절점(Node) 수 | `ControlData.hpp` |
| `NEL8` | 8절점 육면체 솔리드 요소 수 | `ControlData.hpp` |
| `NEL4` (= NELSH) | 쉘 요소 수 | `ControlData.hpp` |
| `NELT` | 두꺼운 쉘 요소 수 | `ControlData.hpp` |
| `NUMMAT8` | 솔리드 재료 수 | `ControlData.hpp` |
| `NEIPH` | 요소당 추가 역사 변수 수 | `ControlData.hpp` |
| `NEIPS` | 쉘 통합점당 추가 변수 수 | `ControlData.hpp` |
| `MAXINT` | 쉘 두께 방향 통합점 수 | `ControlData.hpp` |
| `NV3D` | 솔리드 요소당 변수 개수 | `ControlData.hpp` |
| `NV2D` | 쉘 요소당 변수 개수 | `ControlData.hpp` |
| `ISTRN` | 변형률 텐서 출력 플래그 | `ControlData.hpp` |
| `NMMAT` | 총 재료(파트) 수 (워드 51) | `ControlData.hpp` |

### 1.2 상태 데이터 (State Data) 구조

각 상태는 시뮬레이션의 한 시간 스냅샷을 저장한다.

```
State Record 구조:
+----------------------------------------+
|  float  time                           |  4바이트
|  float  global_data[NGLBV]             |  글로벌 에너지/모멘텀
|  float  node_data[NUMNP x (IU*3+IV*3+IA*3)]  변위.속도.가속도
|  float  solid_stress[NEL8 x NV3D]     |  솔리드 응력 텐서 성분
|  float  shell_stress[NEL4 x NV2D]     |  쉘 응력 텐서 성분
+----------------------------------------+
```

**절점 데이터 인덱싱**

절점 i의 변위는:

```
displacement[i] = {
  dx: node_data[i*3 + 0],
  dy: node_data[i*3 + 1],
  dz: node_data[i*3 + 2]
}
```

현재 위치:

```
pos_current[i] = pos_initial[i] + displacement[i]
```

코드 구현 (`UnifiedAnalyzer.cpp`):
```cpp
Vec3Q getNodePos(const Mesh& mesh, const StateData& state, size_t node_idx) {
    double dx = state.node_displacements[node_idx*3 + 0];
    double dy = state.node_displacements[node_idx*3 + 1];
    double dz = state.node_displacements[node_idx*3 + 2];
    return {mesh.nodes[node_idx].x + dx,
            mesh.nodes[node_idx].y + dy,
            mesh.nodes[node_idx].z + dz};
}
```

### 1.3 응력/변형률 텐서 저장 형식

LS-DYNA 솔리드 요소는 각 통합점에서 다음 순서로 데이터를 저장한다 (`PartAnalyzer.cpp` 참조):

```
solid_data[elem_idx * NV3D + offset]:
  Word 0: sigma_xx     (수직 응력 XX)
  Word 1: sigma_yy     (수직 응력 YY)
  Word 2: sigma_zz     (수직 응력 ZZ)
  Word 3: sigma_xy     (전단 응력 XY)
  Word 4: sigma_yz     (전단 응력 YZ)
  Word 5: sigma_zx     (전단 응력 ZX)
  Word 6: eps_p        (유효 소성 변형률)
  Word 7-12: eps_xx, eps_yy, eps_zz, eps_xy, eps_yz, eps_zx
             (변형률 텐서, ISTRN != 0인 경우에만)
```

쉘 요소는 두께 방향 통합점별로 저장:

```
shell_data[elem_idx][integ_pt] = {sigma_xx, sigma_yy, sigma_zz, sigma_xy, sigma_yz, sigma_zx, eps_p, ...}
```

### 1.4 파트/요소/절점 데이터 계층

```
파트 계층:
Part (파트)
+-- Part ID (정수)
+-- Part Name (키워드 파일에서 파싱)
+-- Elements (요소 목록)
    +-- Shell Elements (쉘 요소, NEL4개)
    |   +-- Element ID
    |   +-- Node IDs [4] -- 4절점 쿼드 또는 퇴화 삼각형
    +-- Solid Elements (솔리드 요소, NEL8개)
        +-- Element ID
        +-- Node IDs [8] -- 8절점 육면체
```

파트-요소 매핑은 `mesh.shell_parts[i]` 및 `mesh.solid_parts[i]` 배열을 통해 수행된다. 인덱스 i의 요소는 해당 배열의 값에 해당하는 Part ID에 속한다.

### 1.5 멀티파일 구조와 병렬 읽기

패밀리 파일(d3plot, d3plot01, d3plot02, ...)은 기저 파일에 제어 데이터 + 기하 데이터가, 이후 파일에 상태 데이터만 저장된다. `D3plotReader.cpp`에서 병렬 읽기는 각 패밀리 파일을 별도 스레드에서 독립적으로 읽어 I/O 병렬성을 최대화한다.

```cpp
// D3plotReader.cpp (read_all_states_parallel)
auto read_file = [this, &output_mutex](size_t file_idx) -> FileResult {
    auto family_reader = std::make_shared<core::BinaryReader>(file_path);
    // 각 스레드가 독립된 BinaryReader 인스턴스 사용
    parsers::StateDataParser state_parser(family_reader, control_data_, is_family_file);
    return state_parser.parse_all();
};
```

기본 스레드 수는 `std::thread::hardware_concurrency()` 또는 사용자 설정값(`num_threads`)이다.

---

## 2. 응력 텐서와 Von Mises 응력

### 2.1 응력 텐서 정의

3차원 응력 텐서 sigma는 대칭 2차 텐서(Symmetric second-order tensor)이다.

```
            | sigma_xx  sigma_xy  sigma_xz |
sigma_ij =  | sigma_xy  sigma_yy  sigma_yz |
            | sigma_xz  sigma_yz  sigma_zz |
```

대각 성분 (sigma_xx, sigma_yy, sigma_zz)는 수직 응력(Normal stress), 비대각 성분 (sigma_xy, sigma_yz, sigma_xz)는 전단 응력(Shear stress)이다. 대칭성에 의해 sigma_ij = sigma_ji이므로 독립 성분은 6개이다.

본 시스템에서 응력 텐서는 `StressTensor` 클래스(`VectorMath.hpp`)로 구현된다:

```cpp
class StressTensor {
public:
    double xx, yy, zz;  // 수직 응력
    double xy, yz, zx;  // 전단 응력
    // LS-DYNA Voigt 표기: [sigma_xx, sigma_yy, sigma_zz, sigma_xy, sigma_yz, sigma_zx]
};
```

### 2.2 응력 불변량 (Stress Invariants)

응력 텐서의 불변량은 좌표계 변환에 무관한 스칼라 값이다 (`VectorMath.hpp` 구현):

```
I_1 = sigma_xx + sigma_yy + sigma_zz             (제1 불변량: 트레이스)

I_2 = sigma_xx*sigma_yy + sigma_yy*sigma_zz + sigma_zz*sigma_xx
      - sigma_xy^2 - sigma_yz^2 - sigma_xz^2      (제2 불변량)

I_3 = det(sigma_ij)                                (제3 불변량: 행렬식)
```

코드 구현:
```cpp
double StressTensor::I1() const { return xx + yy + zz; }
double StressTensor::I2() const {
    return xx*yy + yy*zz + zz*xx - xy*xy - yz*yz - zx*zx;
}
double StressTensor::I3() const {
    return xx*(yy*zz - yz*yz)
         - xy*(xy*zz - yz*zx)
         + zx*(xy*yz - yy*zx);
}
```

### 2.3 주응력 (Principal Stress) 유도

주응력은 응력 텐서의 고유값(Eigenvalue)이다. 다음 특성 방정식을 풀어 구한다.

```
det(sigma_ij - lambda * delta_ij) = 0
```

전개하면 3차 방정식:

```
lambda^3 - I_1 * lambda^2 + I_2 * lambda - I_3 = 0
```

본 시스템은 3차 방정식의 해석적 해법(Lode 각 방법)을 사용한다 (`VectorMath.hpp` principalStresses):

**편차 응력의 J_2, J_3 불변량 계산:**

```
sigma_m = I_1 / 3                           (평균 정수압 응력)

s_ij = sigma_ij - sigma_m * delta_ij         (편차 응력 텐서)

J_2 = (1/2) * s_ij * s_ij
    = (1/2)(s_xx^2 + s_yy^2 + s_zz^2 + 2*s_xy^2 + 2*s_yz^2 + 2*s_zx^2)

J_3 = det(s_ij)
```

**Lode 각 계산:**

```
r = sqrt(J_2 / 3)
cos(3*theta_L) = J_3 / (2 * r^3)

theta_L = (1/3) * arccos(J_3 / (2 * r^3))
```

**주응력:**

```
sigma_1 = sigma_m + 2*r * cos(theta_L)
sigma_2 = sigma_m + 2*r * cos(theta_L - 2*pi/3)
sigma_3 = sigma_m + 2*r * cos(theta_L + 2*pi/3)
```

정렬: sigma_1 >= sigma_2 >= sigma_3

코드 구현:
```cpp
std::array<double, 3> StressTensor::principalStresses() const {
    double mean = i1 / 3.0;
    double J2 = 0.5 * (s_xx*s_xx + s_yy*s_yy + s_zz*s_zz + 2.0*(xy*xy + yz*yz + zx*zx));
    double J3 = s_xx*(s_yy*s_zz - yz*yz) - xy*(xy*s_zz - yz*zx) + zx*(xy*yz - s_yy*zx);
    double r = std::sqrt(J2 / 3.0);
    double cos3theta = std::max(-1.0, std::min(1.0, J3 / (2.0 * r*r*r)));
    double theta = std::acos(cos3theta) / 3.0;
    principals[0] = mean + 2.0*r * std::cos(theta);
    principals[1] = mean + 2.0*r * std::cos(theta - 2.0*M_PI/3.0);
    principals[2] = mean + 2.0*r * std::cos(theta + 2.0*M_PI/3.0);
    // Sort descending
}
```

### 2.4 Von Mises 등가응력 유도 (에너지 기반)

Von Mises 응력(sigma_VM)은 편차 응력 텐서의 크기를 기반으로 정의된다.

**편차 응력 텐서 (Deviatoric stress tensor)**

정수압 응력을 제거한 성분:

```
s_ij = sigma_ij - (1/3) * I_1 * delta_ij
```

**전단 변형 에너지 밀도 (Distortion Energy Density)**

등방성 선형 탄성체에서 전단 변형 에너지 밀도 U_d는:

```
U_d = (1 + nu) / (3E) * J_2
```

여기서 J_2는 편차 응력 텐서의 제2 불변량:

```
J_2 = (1/2) * s_ij * s_ij
```

주응력으로 표현하면:

```
J_2 = (1/6)[(sigma_1 - sigma_2)^2 + (sigma_2 - sigma_3)^2 + (sigma_3 - sigma_1)^2]
```

**Von Mises 등가응력**

단축 인장 항복 시 J_2 = sigma_y^2/3이므로, Von Mises 등가응력을 단축 등가 응력으로 정의:

```
sigma_VM = sqrt(3 * J_2)
         = sqrt((3/2) * s_ij * s_ij)
```

텐서 성분으로 전개:

```
sigma_VM = sqrt[(1/2)((sigma_xx - sigma_yy)^2 + (sigma_yy - sigma_zz)^2 + (sigma_zz - sigma_xx)^2
                     + 6*(sigma_xy^2 + sigma_yz^2 + sigma_xz^2))]
```

주응력으로 표현:

```
sigma_VM = sqrt[(1/2)((sigma_1 - sigma_2)^2 + (sigma_2 - sigma_3)^2 + (sigma_3 - sigma_1)^2)]
```

코드 구현 (`PartAnalyzer.cpp` 및 `VectorMath.hpp`):
```cpp
// PartAnalyzer.cpp
double PartAnalyzer::calculate_von_mises(double sxx, double syy, double szz,
                                          double sxy, double syz, double szx) {
    double d1 = sxx - syy;
    double d2 = syy - szz;
    double d3 = szz - sxx;
    double vm_sq = 0.5 * (d1*d1 + d2*d2 + d3*d3) + 3.0 * (sxy*sxy + syz*syz + szx*szx);
    return std::sqrt(vm_sq);
}

// VectorMath.hpp (StressTensor 클래스 내)
double StressTensor::vonMises() const {
    double d1 = xx - yy;
    double d2 = yy - zz;
    double d3 = zz - xx;
    double shear_sum = xy*xy + yz*yz + zx*zx;
    return std::sqrt(0.5 * (d1*d1 + d2*d2 + d3*d3 + 6.0 * shear_sum));
}
```

두 구현은 동일하며, `0.5*(d1^2+d2^2+d3^2) + 3*(sxy^2+syz^2+szx^2)` 형태를 사용한다.

### 2.5 항복 조건 (Von Mises Yield Criterion)

재료가 항복하는 조건:

```
sigma_VM >= sigma_y
```

여기서 sigma_y는 재료의 단축 항복응력이다. 기하학적으로 이는 편차 응력 공간(Deviatoric stress space, pi-plane)에서 반지름 sqrt(2/3)*sigma_y의 원으로 표현된다.

### 2.6 안전계수 (Safety Factor) 계산

```
SF = sigma_y / sigma_VM_peak
```

| SF 범위 | 판정 |
|---------|------|
| SF >= 2.0 | 안전 (Safe) |
| 1.5 <= SF < 2.0 | 주의 (Marginal) |
| 1.0 <= SF < 1.5 | 경고 (Warning) |
| SF < 1.0 | 항복 (Yielding) |

`koo_report` HTML 리포트 구현:

```python
sf = yield_stress / worst_stress   # MPa 단위
```

### 2.7 삼축성 지수 (Triaxiality Index)

응력 삼축성은 정수압 응력과 Von Mises 응력의 비로 정의된다.

```
eta = sigma_m / sigma_VM
```

여기서 sigma_m은 평균 정수압 응력:

```
sigma_m = (1/3) * I_1 = (sigma_xx + sigma_yy + sigma_zz) / 3
```

코드 구현:
```cpp
double StressTensor::meanStress() const { return (xx + yy + zz) / 3.0; }
double StressTensor::hydrostaticPressure() const { return -(xx + yy + zz) / 3.0; }
```

삼축성은 연성 파괴(Ductile fracture)를 예측하는 중요한 지표이다. 높은 양의 삼축성(eta > 1/3)에서는 공동 성장(Void growth)이 촉진되어 연성 파괴가 발생하기 쉽다.

### 2.8 면응력 분석: 수직 응력과 전단 응력

면에 작용하는 응력은 트랙션 벡터(Traction vector)로부터 분해된다 (`VectorMath.hpp`):

**트랙션 벡터:**

```
t = sigma * n
```

여기서 n은 면의 단위 법선 벡터이다.

**수직 응력 (Normal stress on plane):**

```
sigma_n = n . t = n . sigma . n
```

**전단 응력 (Shear stress on plane):**

```
tau = sqrt(|t|^2 - sigma_n^2)
```

코드 구현:
```cpp
Vec3 StressTensor::tractionVector(const Vec3& normal) const {
    return Vec3(xx*normal.x + xy*normal.y + zx*normal.z,
                xy*normal.x + yy*normal.y + yz*normal.z,
                zx*normal.x + yz*normal.y + zz*normal.z);
}
double StressTensor::normalStress(const Vec3& normal) const {
    return tractionVector(normal).dot(normal);
}
double StressTensor::shearStress(const Vec3& normal) const {
    Vec3 traction = tractionVector(normal);
    double sigma_n = traction.dot(normal);
    double diff = traction.magnitudeSquared() - sigma_n*sigma_n;
    return std::sqrt(std::max(0.0, diff));
}
```

---

## 3. 변형률 분석

### 3.1 변형률 텐서 정의

변형률 텐서 epsilon은 변위장의 대칭 기울기(Symmetric gradient of displacement field)이다:

```
epsilon_ij = (1/2)(du_i/dx_j + du_j/dx_i)
```

응력 텐서와 마찬가지로 대칭이며 6개의 독립 성분을 가진다:

```
            | eps_xx  eps_xy  eps_xz |
eps_ij   =  | eps_xy  eps_yy  eps_yz |
            | eps_xz  eps_yz  eps_zz |
```

LS-DYNA d3plot에서 변형률 텐서는 `ISTRN != 0`인 경우에만 출력된다 (`ControlData.hpp`).

### 3.2 유효 소성 변형률 (Effective Plastic Strain)

유효 소성 변형률(Effective plastic strain) eps_p는 LS-DYNA 솔리드 요소 데이터의 Word 6에 저장된다. 이 값은 시뮬레이션 시작부터의 누적 소성 변형률이며, 다음과 같이 정의된다:

```
eps_p = integral_0^t sqrt(2/3) * ||eps_dot_p|| dt
```

여기서 eps_dot_p는 소성 변형률 속도 텐서이다. 스칼라 eps_p는 단조 증가(Non-decreasing)하며, 재료의 소성 변형 이력을 나타낸다.

코드에서 유효 소성 변형률 추출:
```cpp
// PartAnalyzer.cpp (extract_stress 함수)
case StressComponent::EFF_PLASTIC:
    return solid_data[base + 6];  // Word 6
```

### 3.3 체적 변형률과 편차 변형률

변형률 텐서도 응력 텐서와 동일하게 체적(Volumetric)과 편차(Deviatoric) 성분으로 분리할 수 있다.

**체적 변형률 (Volumetric strain):**

```
eps_v = eps_xx + eps_yy + eps_zz = tr(epsilon)
```

체적 변형률은 재료의 부피 변화를 나타낸다:

```
dV/V_0 = eps_v   (미소 변형률 근사)
```

**편차 변형률 텐서 (Deviatoric strain tensor):**

```
e_ij = eps_ij - (1/3) * eps_v * delta_ij
```

편차 변형률은 형상 변화(Distortion)만을 나타내며, 체적 변화는 포함하지 않는다.

### 3.4 변형률 텐서와 응력 텐서의 관계

등방성 선형 탄성체에서 일반화된 Hooke의 법칙:

```
eps_ij = (1+nu)/E * sigma_ij - nu/E * tr(sigma) * delta_ij
```

또는 역관계:

```
sigma_ij = E/(1+nu) * [eps_ij + nu/(1-2*nu) * tr(epsilon) * delta_ij]
```

여기서 E는 영률(Young's modulus), nu는 푸아송 비(Poisson's ratio)이다.

**특수 경우:**
- 비압축성 재료(nu = 0.5): eps_v = 0 (체적 변화 없음)
- 일축 인장(Uniaxial tension): eps_xx = sigma_xx/E, eps_yy = eps_zz = -nu*sigma_xx/E

### 3.5 변형률 성분 추출

LS-DYNA에서 변형률 텐서 성분은 `ISTRN != 0`일 때 솔리드 요소 데이터의 Word 7~12에 저장된다:

```cpp
// PartAnalyzer.cpp (extract_stress 함수)
case StressComponent::STRAIN_XX:
    return (control_data_.ISTRN != 0 && base+7 < solid_data.size())
         ? solid_data[base + 7] : 0.0;
case StressComponent::STRAIN_YY:
    return (control_data_.ISTRN != 0 && base+8 < solid_data.size())
         ? solid_data[base + 8] : 0.0;
// ... STRAIN_ZZ(9), STRAIN_XY(10), STRAIN_YZ(11), STRAIN_ZX(12)
```

`StressComponent` 열거형에서:

| 열거값 | 인덱스 | 의미 |
|--------|--------|------|
| `STRAIN_XX` | Word 7 | 수직 변형률 XX |
| `STRAIN_YY` | Word 8 | 수직 변형률 YY |
| `STRAIN_ZZ` | Word 9 | 수직 변형률 ZZ |
| `STRAIN_XY` | Word 10 | 전단 변형률 XY |
| `STRAIN_YZ` | Word 11 | 전단 변형률 YZ |
| `STRAIN_ZX` | Word 12 | 전단 변형률 ZX |

---

## 4. 낙하 방향 표현 -- 오일러 각과 회전 행렬

### 4.1 Euler 각도 정의

낙하 자세(Drop orientation)는 3개의 Euler 각도로 정의된다.

| 각도 | 기호 | 회전 축 | 범위 |
|------|------|---------|------|
| Roll (롤) | alpha | X축 | [-180 deg, 180 deg] |
| Pitch (피치) | beta | Y축 | [-90 deg, 90 deg] |
| Yaw (요) | gamma | Z축 | [-180 deg, 180 deg] |

낙하 방향은 기준 낙하 방향(-Z축 방향, 즉 중력 방향)을 Euler 각도로 회전시켜 결정한다.

### 4.2 회전 행렬

**X축 회전 (Roll):**

```
      | 1    0         0      |
Rx =  | 0  cos(alpha)  -sin(alpha) |
      | 0  sin(alpha)   cos(alpha) |
```

**Y축 회전 (Pitch):**

```
      |  cos(beta)  0  sin(beta) |
Ry =  |    0        1    0      |
      | -sin(beta)  0  cos(beta) |
```

**Z축 회전 (Yaw):**

```
      | cos(gamma)  -sin(gamma)  0 |
Rz =  | sin(gamma)   cos(gamma)  0 |
      |   0            0         1 |
```

### 4.3 합성 회전: 방향 벡터 계산

낙하 방향 벡터 **d** = (dx, dy, dz)는 내재적 ZYX Euler 각도 적용으로 계산된다.

```
d = Rz(gamma) * Ry(beta) * Rx(alpha) * [0, 0, -1]^T
```

행렬을 순차적으로 전개하면:

**1단계: Rx(alpha) * [0, 0, -1]^T**

```
[0, 0, -1] 에 Rx 적용:
x1 = 0
y1 = 0*cos(alpha) - (-1)*sin(alpha) = sin(alpha)
z1 = 0*sin(alpha) + (-1)*cos(alpha) = -cos(alpha)
```

**2단계: Ry(beta) * [x1, y1, z1]^T**

```
x2 = x1*cos(beta) + z1*sin(beta) = -cos(alpha)*sin(beta)
y2 = y1 = sin(alpha)
z2 = -x1*sin(beta) + z1*cos(beta) = -cos(alpha)*cos(beta)
```

**3단계: Rz(gamma) * [x2, y2, z2]^T**

완전한 전개 결과:
```
dx =  cos(gamma)*sin(beta)*cos(alpha) + sin(gamma)*sin(alpha)
dy =  sin(gamma)*sin(beta)*cos(alpha) - cos(gamma)*sin(alpha)
dz = -cos(beta)*cos(alpha)
```

### 4.4 koo_report의 간소화 구현

`html_report.py`에서 Yaw = 0 가정하의 간소화 구현 (대부분의 낙하 DOE에서 yaw는 사용하지 않음):

```javascript
// Rx(roll) * [0, 0, -1]
const x1 = 0, y1 = Math.sin(r), z1 = -Math.cos(r);
// Ry(pitch) * above
const x2 = x1 * Math.cos(p) + z1 * Math.sin(p);
const y2 = y1;
const z2 = -x1 * Math.sin(p) + z1 * Math.cos(p);
```

이는 위 일반 공식에서 gamma = 0 (yaw = 0)을 대입한 결과와 일치한다:
```
dx = sin(beta)*cos(alpha)       (= -cos(alpha)*sin(beta) 부호 주의: 실제 구현에서 sin(p) 곱셈 순서)
dy = sin(alpha)
dz = -cos(beta)*cos(alpha)
```

### 4.5 방향 벡터 -> 구면 좌표 (위도, 경도)

방향 벡터 **d** = (dx, dy, dz)를 구면 좌표로 변환한다.

```
lambda = atan2(dx, -dz)      [경도, longitude, -pi <= lambda <= pi]
phi = arcsin(dy)              [위도, latitude,  -pi/2 <= phi <= pi/2]
```

코드 구현 (`html_report.py`):
```javascript
function directionToLonLat(dir) {
  const [x, y, z] = dir;
  const lon = Math.atan2(x, -z) * 180 / Math.PI;
  const lat = Math.asin(Math.max(-1, Math.min(1, y))) * 180 / Math.PI;
  return [lon, Math.max(-85, Math.min(85, lat))];
}
```

**주의**: dy는 정규화된 방향 벡터의 y-성분이므로 |dy| <= 1이 보장되어야 arcsin이 유효하다. 극점(lat = +/-90 deg)은 시각화를 위해 +/-85 deg로 클램프한다.

---

## 5. 피보나치 격자 구면 균등 분포

### 5.1 황금비 정의

황금비(Golden ratio) phi는 다음으로 정의된다:

```
phi = (1 + sqrt(5)) / 2 = 1.6180339887...
```

황금비는 황금각(Golden angle)을 결정한다:

```
theta_gold = 2*pi * (1 - 1/phi) = 2*pi / phi^2 = 137.508 deg
```

이 각도는 연속된 점들이 주기성 없이 가장 균일하게 분포하도록 하는 성질을 가진다.

### 5.2 Fibonacci 격자 공식

N개의 점을 구면에 균등하게 배분하는 Fibonacci 격자:

```
theta_i = arccos(1 - 2i/(N-1))     [극각, 0 <= i <= N-1]
phi_i = 2*pi * i / phi              [방위각, mod 2*pi]
```

직교 좌표로 변환:

```
x_i = sin(theta_i) * cos(phi_i)
y_i = sin(theta_i) * sin(phi_i)
z_i = cos(theta_i)
```

해당 구면 좌표 (경도lambda, 위도phi) = (atan2(x_i, -z_i), arcsin(y_i)).

### 5.3 균등성 증명 (면적 보존)

**정리**: Fibonacci 격자의 극각 분포는 구면 면적 보존(Area-preserving)이다.

**증명**: 극각 theta_i = arccos(1 - 2i/(N-1))에서:

```
cos(theta_i) = 1 - 2i/(N-1)
```

구면대(Spherical zone) 면적은 극각으로:

```
dA = 2*pi * sin(theta) * d(theta) = -2*pi * d(cos theta)
```

cos(theta_i)가 등차수열이므로 d(cos theta_i) = 2/(N-1) = 상수이다. 즉, 인접 theta 값 사이의 구면대 면적이 모두 동일하며, 이는 극각이 면적 균등 분포를 보장함을 의미한다.

방위각 phi_i = 2*pi*i/phi는 Weyl 수열(Weyl sequence)의 구면 버전으로, 황금각을 사용하므로 어떤 정수 배수와도 유리 근사를 갖지 않아 방위각 방향 클러스터링이 방지된다.

### 5.4 26방향 큐보이드 대비 장점 분석

| 항목 | 26방향 큐보이드 | Fibonacci N점 |
|------|----------------|--------------|
| 방향 수 | 고정 26 | N 임의 설정 |
| 극점 집중 | 없음 | 없음 |
| 적도 집중 | 없음 | 없음 |
| 방향 편향 | 직육면체 대칭 편향 | 없음 |
| 확장성 | 불가 | N 변경으로 즉시 확장 |
| 최대 각도 공백 | ~35 deg (코너 방향 부재 시) | N=100: ~18 deg, N=500: ~8 deg |

Fibonacci 방식에서 최대 각도 공백(Maximum angular gap)은 근사적으로:

```
Delta_theta_max = sqrt(4*pi/N) 라디안 = 2*sqrt(pi/N) 라디안
```

N=1144에서 Delta_theta_max = 6.0 deg (0.105 rad).

### 5.5 구면 커버리지 정량화

N개 방향 점에 대한 이상 각도 간격:

```
A_ideal = 4*pi / N           [단위 구 표면적 / 점 수]
ideal_spacing = sqrt(4*pi/N) [라디안]
```

koo_report의 `analyzer.py` 구현에서 커버리지 품질을 평가:

```python
def _compute_sphere_coverage(angles):
    n = len(angles)
    ideal_spacing = math.degrees(math.sqrt(4 * math.pi / n))
    actual_spacing = compute_angular_spacing(angles)
    if actual_spacing <= ideal_spacing:
        return 1.0   # 이상보다 밀함 -> 100%
    return min(1.0, (ideal_spacing / actual_spacing) ** 2)  # 면적 비례 추정
```

---

## 6. Mollweide 등적도 투영

### 6.1 정의 및 특성

Mollweide 투영(Mollweide projection)은 1805년 Karl Brandan Mollweide가 제안한 등적도(Equal-area) 투영법이다.

**핵심 특성:**
- **등적 (Equal-area)**: 지도상 면적 = 구면 면적 비율 (왜곡 없이 보존)
- **타원형 경계**: 가로 세로 2:1 비율의 타원
- **경선**: 타원형 곡선 (적도 제외)
- **위선**: 수평 직선

낙하 분석에서 등적 투영의 의미: 지도에서 빨간 영역(취약 방향)이 전체 면적의 x%이면, 실제로 전체 낙하 방향의 x%가 취약하다.

### 6.2 순변환 (Forward Projection): Newton-Raphson으로 theta 수치해

입력: 경도 lambda in [-pi, pi], 위도 phi in [-pi/2, pi/2]
출력: 지도 좌표 (x, y)

**1단계: 보조각 theta 계산**

다음 초월 방정식을 theta에 대해 풀어야 한다:

```
F(theta) = 2*theta + sin(2*theta) - pi*sin(phi) = 0
```

이 방정식은 닫힌 형태의 해가 없으므로 Newton-Raphson 반복법으로 수치해를 구한다.

**2단계: Newton-Raphson 반복**

```
초기값: theta_0 = phi    (위도를 초기 추정으로 사용)

반복:
    F(theta_n)  = 2*theta_n + sin(2*theta_n) - pi*sin(phi)
    F'(theta_n) = 2 + 2*cos(2*theta_n)
    theta_{n+1} = theta_n - F(theta_n) / F'(theta_n)
```

수렴 조건: |theta_{n+1} - theta_n| < epsilon (일반적으로 epsilon = 10^-7)

**3단계: 투영 좌표 계산**

```
x = (2*sqrt(2) / pi) * lambda * cos(theta)
y = sqrt(2) * sin(theta)
```

**극점 처리:**

phi = +/-pi/2 (극점)에서 theta = +/-pi/2이며, 별도 처리:
```
x = 0
y = +/-sqrt(2)
```

**감쇠 처리 (Damped Newton):**

코드에서는 스텝 크기를 0.3 이내로 제한하고, theta를 (-pi/2, pi/2) 범위로 클램프하여 수치 안정성을 확보한다.

코드 구현 (`html_report.py`):
```javascript
function mollweideProject(lonDeg, latDeg) {
  const lon = lonDeg * Math.PI / 180;
  const lat = latDeg * Math.PI / 180;
  if (Math.abs(lat) > Math.PI/2 - 1e-10) {
    return [0, lat > 0 ? Math.SQRT2 : -Math.SQRT2];
  }
  const target = Math.PI * Math.sin(lat);
  let theta = lat;
  for (let i = 0; i < 100; i++) {
    const f = 2*theta + Math.sin(2*theta) - target;
    const fp = 2 + 2*Math.cos(2*theta);
    if (Math.abs(fp) < 1e-12) { theta += (lat > 0 ? -0.1 : 0.1); continue; }
    let dt = f / fp;
    if (Math.abs(dt) > 0.3) dt = dt > 0 ? 0.3 : -0.3;   // 감쇠
    theta -= dt;
    theta = Math.max(-Math.PI/2+1e-10, Math.min(Math.PI/2-1e-10, theta)); // 클램프
    if (Math.abs(dt) < 1e-7) break;
  }
  const x = (2*Math.SQRT2/Math.PI) * lon * Math.cos(theta);
  const y = Math.SQRT2 * Math.sin(theta);
  return [x, y];
}
```

### 6.3 역변환 (Inverse): 지도 좌표 -> 구면 좌표

입력: 정규화된 지도 좌표 (x, y)
출력: (lambda, phi)

```
theta = arcsin(y / sqrt(2))

phi = arcsin((2*theta + sin(2*theta)) / pi)

lambda = (pi * x) / (2*sqrt(2) * cos(theta))
```

단, cos(theta) = 0 (극점)인 경우 lambda는 정의되지 않는다.

코드 구현:
```javascript
function mollweideInverse(x, y) {
  const theta = Math.asin(Math.max(-1, Math.min(1, y / Math.SQRT2)));
  const lat = Math.asin(Math.max(-1, Math.min(1, (2*theta + Math.sin(2*theta)) / Math.PI)));
  const cosTheta = Math.cos(theta);
  if (Math.abs(cosTheta) < 1e-10) return [0, lat >= 0 ? 89.99999 : -89.99999];
  const lon = (Math.PI * x) / (2*Math.SQRT2 * cosTheta);
  if (Math.abs(lon) > Math.PI) return null;
  return [lon * 180 / Math.PI, lat * 180 / Math.PI];
}
```

### 6.4 Newton-Raphson 수렴 분석

**보조 정리**: F(theta) = 2*theta + sin(2*theta) - C (C = pi*sin(phi))에 대해 Newton-Raphson이 수렴한다.

**분석:**

F'(theta) = 2 + 2*cos(2*theta) >= 0 (등호는 theta = pi/2 + n*pi에서만)

F는 (-pi/2, pi/2)에서 단조증가이므로 해의 유일성이 보장된다.

Newton-Raphson 오차 수렴 속도:

```
|e_{n+1}| <= (M / 2m) * |e_n|^2
```

여기서 M = max|F''| = 4, m = min|F'| >= 2 (theta가 +/-pi/2에서 멀 때). 실제 3~5회 반복으로 double precision 수준의 정밀도에 도달한다.

### 6.5 면적 보존 증명

Jacobian 행렬식을 계산하여 등적 투영을 증명한다.

구면 면적 요소:

```
dA_sphere = cos(phi) * d(lambda) * d(phi)
```

편미분 계산:

```
partial(x)/partial(lambda) = (2*sqrt(2)/pi)*cos(theta)
partial(y)/partial(lambda) = 0
partial(y)/partial(phi) = sqrt(2)*cos(theta)*(partial(theta)/partial(phi))
```

방정식 2*theta + sin(2*theta) = pi*sin(phi)를 phi로 미분:

```
(2 + 2*cos(2*theta)) * (partial(theta)/partial(phi)) = pi*cos(phi)
partial(theta)/partial(phi) = pi*cos(phi) / (4*cos^2(theta))
```

Jacobian 행렬식:

```
|J| = |partial(x)/partial(lambda) * partial(y)/partial(phi)|
    = (2*sqrt(2)/pi)*cos(theta) * sqrt(2)*cos(theta) * pi*cos(phi)/(4*cos^2(theta))
    = cos(phi)
```

따라서:

```
dA_map = |J| * d(lambda) * d(phi) = cos(phi) * d(lambda) * d(phi) = dA_sphere
```

등적 투영 증명 완료.

---

## 7. 구면 IDW 보간

### 7.1 Haversine 대권 거리 공식

이산된 시뮬레이션 방향 점들 사이의 거리는 유클리드 거리가 아닌 대권 거리(Great-circle distance)를 사용한다. 이는 극점 근방에서 경도 차이가 과장되는 문제를 방지한다.

두 점 P_i = (lambda_i, phi_i), P_j = (lambda_j, phi_j)의 Haversine 대권 거리:

```
Delta_phi = phi_j - phi_i
Delta_lambda = lambda_j - lambda_i

a = sin^2(Delta_phi/2) + cos(phi_i)*cos(phi_j)*sin^2(Delta_lambda/2)

d_ij = 2*arcsin(sqrt(a))
```

단위 구(R=1)에서 d_ij in [0, pi].

코드 구현 (`html_report.py`):
```javascript
function sphericalDist(lon1d, lat1d, lon2d, lat2d) {
  const toR = Math.PI / 180;
  const lat1 = lat1d * toR, lat2 = lat2d * toR;
  const dlon = (lon2d - lon1d) * toR;
  const dlat = lat2 - lat1;
  const a = Math.sin(dlat/2)**2 + Math.cos(lat1)*Math.cos(lat2)*Math.sin(dlon/2)**2;
  return 2 * Math.asin(Math.sqrt(Math.min(1, a)));
}
```

Haversine 공식은 수치적으로 안정적이다. arccos 기반 공식은 두 점이 매우 가까울 때 수치 오차가 크지만, Haversine은 작은 각도에서도 정밀하게 계산된다.

### 7.2 IDW 가중치 계산

역거리 가중(Inverse Distance Weighting, IDW) 방법에서 각 표본 점의 가중치:

```
w_j = 1 / d_ij^p        (d_ij != 0인 경우)
```

여기서 p는 멱지수(Power exponent)이다. 본 시스템에서 **p = 3.5**를 사용한다.

보간점 q와 동일한 위치에 표본이 있는 경우 (d_ij -> 0):

```
lim_{d->0} w_j = +infinity
```

이 경우 해당 표본의 값을 직접 반환한다 (스냅 반경 0.02 rad = 약 1.1 deg).

### 7.3 보간 공식: Shepard's Method

쿼리 점 q에서의 보간값 sigma(q):

```
sigma(q) = sum_j [w_j * sigma_j] / sum_j w_j
         = sum_j [sigma_j / d_qj^p] / sum_j [1 / d_qj^p]
```

여기서 합산은 모든 N개의 표본 점에 대해 수행한다.

코드 구현 (`html_report.py` drawMollweideContour):
```javascript
const pw = 3.5;  // IDW 멱지수
for (const dp of dataPoints) {
    const dist = sphericalDist(plon, plat, dp.lon, dp.lat);
    if (dist < 0.02) { vsum = dp.v; wsum = 1; break; }  // 스냅 반경
    const w = 1 / Math.pow(dist, pw);
    wsum += w;
    vsum += w * dp.v;
}
gridVals[...] = wsum > 0 ? (vsum / wsum - vmin) / vrange : 0;
```

### 7.4 멱지수 p 선택의 수학적 근거

IDW의 멱지수 p는 보간의 평활도(Smoothness)와 국소성(Locality)을 제어한다.

```
p = 0:   균등 평균 (거리 무관)
p = 1:   선형 거리 역수
p = 2:   표준 IDW (가장 일반적)
p -> inf: 최근접 이웃(Nearest neighbor) 보간
```

**p = 3.5의 선택 이유:**

1. **국소성 강화**: 취약 방향은 공간적으로 집중되는 경향이 있다. 높은 p 값은 가까운 표본에 더 집중하여 이 국소적 특성을 더 잘 포착한다.

2. **등고선 연속성**: p >= 2이면 보간 함수가 C^0 연속(연속이나 미분 불가)이다. p = 3.5는 시각적으로 부드러운 등고선을 제공한다.

3. **극점 안전성**: 구면 좌표에서 극점(phi = +/-pi/2) 근방에서는 경도 방향 표본 밀도가 낮아진다. 높은 p는 불균등 분포의 영향을 줄인다.

수학적으로 p = 2에서 p = 3.5로 증가시키면 가중치 비율이:

```
w_near / w_far = (d_far / d_near)^p
```

d_near = 5 deg, d_far = 30 deg 기준:
- p = 2.0: (30/5)^2 = 36
- p = 3.5: (30/5)^3.5 = 216

즉 p = 3.5에서 인접 점의 영향이 원거리 점 대비 ~216배 강하여 국소 취약 방향 패턴을 선명하게 표현한다.

### 7.5 컨투어 렌더링 파이프라인

Mollweide 컨투어 생성은 2단계로 수행된다:

**1단계: 조밀 격자(Coarse grid) IDW 계산**

- 격자 간격: 3픽셀
- 각 격자점에서 Mollweide 역변환으로 (lon, lat) 추출
- Haversine 구면 거리 기반 IDW 보간값 계산

**2단계: 쌍선형 보간(Bilinear interpolation) 렌더링**

- 전체 픽셀에 대해 격자값을 쌍선형 보간
- 타원 영역 내부만 렌더링 (`isInsideMollweide`)
- 보간된 값을 색상 맵으로 변환

---

## 8. 요소 품질 지표

요소 품질(Element quality) 분석은 시뮬레이션 진행 중 메시 왜곡을 추적하여 수치 불안정성과 결과 신뢰성을 평가한다. 본 시스템은 쉘(Shell)과 솔리드(Solid) 요소에 대해 각각 다른 지표를 사용한다.

코드 출처: `UnifiedAnalyzer.cpp` (익명 네임스페이스 내 함수들).

### 8.1 Aspect Ratio (가로세로비)

**정의**: 요소의 최장 모서리와 최단 모서리의 비.

```
AR = L_max / L_min
```

이상적인 값: AR = 1.0 (정사각형/정육면체)
경고 임계값: AR > 5.0 (본 시스템에서 `n_high_aspect` 카운트)

**쉘 요소 (4절점 쿼드)**: 4개 모서리 길이를 계산한다.

```
edges = {|p_1 - p_0|, |p_2 - p_1|, |p_3 - p_2|, |p_0 - p_3|}

AR_shell = max(edges) / min(edges)
```

코드 (`computeAspectRatio4`):
```cpp
double edges[4] = {
    (p1-p0).mag(), (p2-p1).mag(), (p3-p2).mag(), (p0-p3).mag()
};
double mn = min(edges), mx = max(edges);
return (mn > 1e-20) ? mx/mn : 1e6;   // 영길이 방어
```

**삼각형 요소 (퇴화 쿼드, node_2 == node_3)**: 3개 모서리 사용.

```cpp
double e0 = (p[1]-p[0]).mag(), e1 = (p[2]-p[1]).mag(), e2 = (p[0]-p[2]).mag();
double mn = std::min({e0,e1,e2}), mx = std::max({e0,e1,e2});
ar = (mn > 1e-20) ? mx / mn : 1e6;
```

**솔리드 요소 (8절점 육면체)**: 12개 모서리 모두 사용.

```
육면체 12개 모서리:
  하면(Bottom): {0-1, 1-2, 2-3, 3-0}
  상면(Top):    {4-5, 5-6, 6-7, 7-4}
  기둥(Pillars):{0-4, 1-5, 2-6, 3-7}

AR_hex = max(12 edges) / min(12 edges)
```

코드 (`computeAspectRatio8`):
```cpp
int edges[12][2] = {
    {0,1},{1,2},{2,3},{3,0},   // 하면
    {4,5},{5,6},{6,7},{7,4},   // 상면
    {0,4},{1,5},{2,6},{3,7}    // 기둥
};
```

### 8.2 Jacobian 행렬식

**Jacobian 행렬 정의**

요소 Jacobian 행렬은 자연 좌표(Natural coordinates, xi, eta, zeta)에서 전역 좌표(x, y, z)로의 변환이다.

```
J = partial(x,y,z)/partial(xi,eta,zeta)
```

8절점 육면체 요소에서 자연 좌표 (xi, eta, zeta) in [-1,1]^3의 형상함수:

```
N_i(xi,eta,zeta) = (1/8)(1 + xi_i*xi)(1 + eta_i*eta)(1 + zeta_i*zeta)
```

**음수 Jacobian의 의미**

det(J) < 0이면 요소가 반전(Inverted)되었음을 의미한다. 이는 수치 적분에서 음의 체적이 계산되어 유한요소 해석이 불안정해진다.

**본 시스템의 구현 (단순화)**

본 시스템은 완전한 Jacobian 계산 대신 체적 부호를 사용한다:

```cpp
double vol = computeHexVolume(p);
double jac = (vol >= 0) ? 1.0 : -1.0;   // 부호만 추적
```

이는 반전 여부를 신속하게 판별하기 위한 실용적 단순화이다. 체적이 양수이면 정상, 음수이면 반전 요소로 분류한다.

### 8.3 Warpage (쉘 요소 비틀림)

**정의**: 쿼드 쉘 요소의 4개 절점이 동일 평면에 있지 않은 정도.

**계산 방법**: 두 삼각형으로 분할하여 각 삼각형의 법선 벡터를 구하고, 두 법선의 사잇각을 계산한다.

```
삼각형 1: Triangle(p_0, p_1, p_2)  ->  n_1 = (p_1 - p_0) x (p_2 - p_0)
삼각형 2: Triangle(p_0, p_2, p_3)  ->  n_2 = (p_2 - p_0) x (p_3 - p_0)

theta_warp = arccos(n_1 . n_2 / (|n_1| * |n_2|))  [라디안]
theta_warp_deg = theta_warp * 180/pi                [도]
```

이상적인 값: theta_warp = 0 deg (완전 평면)

코드 (`computeWarpage4`):
```cpp
Vec3Q n1 = (p1-p0).cross(p2-p0);
Vec3Q n2 = (p2-p0).cross(p3-p0);
double cosA = clamp(n1.dot(n2)/(n1.mag()*n2.mag()), -1, 1);
return acos(cosA) * 180.0 / M_PI;
```

### 8.4 Skewness (왜곡도, 쉘 요소)

**정의**: 쿼드 요소의 4개 꼭짓점 각도가 90 deg에서 벗어난 최대 편차를 정규화한 값.

```
각도 계산 (꼭짓점 b에서):
  theta(a,b,c) = arccos(((a-b)/|a-b|) . ((c-b)/|c-b|))

4개 꼭짓점 각도:
  theta_0 = theta(p_3, p_0, p_1)
  theta_1 = theta(p_0, p_1, p_2)
  theta_2 = theta(p_1, p_2, p_3)
  theta_3 = theta(p_2, p_3, p_0)

Skewness = max(|theta_i - 90 deg|) / 90 deg
```

이상적인 값: Skewness = 0 (정사각형, 모든 각도 = 90 deg)
최악 값: Skewness = 1 (퇴화 요소)

코드 (`computeSkewness4`):
```cpp
auto angle = [](const Vec3Q& a, const Vec3Q& b, const Vec3Q& c) -> double {
    Vec3Q ba = a-b, bc = c-b;
    double cosA = clamp(ba.dot(bc)/(ba.mag()*bc.mag()), -1, 1);
    return acos(cosA) * 180.0 / M_PI;
};
double max_dev = 0;
for (int i = 0; i < 4; ++i)
    max_dev = max(max_dev, abs(angles[i] - 90.0) / 90.0);
```

### 8.5 Volume Change Ratio (체적 변화율, 솔리드 요소)

**정의**: 현재 요소 체적과 초기 요소 체적의 비.

```
R_vol = V_current / V_initial
```

이상적인 값: R_vol = 1.0 (체적 불변)

**5-사면체 분해법 (5-Tetrahedron Decomposition)**

8절점 육면체(Hex8)의 체적을 5개의 사면체로 분해하여 계산한다.

분해 방식 (절점 번호 0~7):

```
tet1: 절점 {0, 1, 3, 4}
tet2: 절점 {1, 2, 3, 6}
tet3: 절점 {1, 4, 5, 6}
tet4: 절점 {3, 4, 6, 7}
tet5: 절점 {1, 3, 4, 6}
```

각 사면체 체적 공식 (벡터 혼합곱):

```
V_tet(a, b, c, d) = (1/6) * (b - a) . [(c - a) x (d - a)]
```

코드 (`computeHexVolume`):
```cpp
auto tetVol = [](Vec3Q a, Vec3Q b, Vec3Q c, Vec3Q d) -> double {
    return (b-a).dot((c-a).cross(d-a)) / 6.0;
};
double vol = tetVol(p[0],p[1],p[3],p[4])
           + tetVol(p[1],p[2],p[3],p[6])
           + tetVol(p[1],p[4],p[5],p[6])
           + tetVol(p[3],p[4],p[6],p[7])
           + tetVol(p[1],p[3],p[4],p[6]);
```

체적 변화율 계산:
```cpp
double vol_ratio = (init_vol > 1e-20) ? abs(vol)/init_vol : 1.0;
```

### 8.6 면적 변화율 (쉘 요소)

**정의**: 현재 요소 면적과 초기 요소 면적의 비.

```
R_area = A_current / A_initial
```

**쿼드 면적 계산 (두 삼각형 합)**:

```
A_quad = A(Triangle p_0,p_1,p_2) + A(Triangle p_0,p_2,p_3)
       = (1/2)|(p_1-p_0) x (p_2-p_0)| + (1/2)|(p_2-p_0) x (p_3-p_0)|
```

코드 (`computeArea4`):
```cpp
return 0.5 * ((p1-p0).cross(p2-p0).mag() + (p2-p0).cross(p3-p0).mag());
```

### 8.7 품질 지표 요약 및 임계값

| 지표 | 대상 | 이상값 | 경고 임계값 |
|------|------|--------|-----------|
| Aspect Ratio | Shell + Solid | 1.0 | > 5.0 |
| Jacobian | Solid | +1.0 | < 0 (반전) |
| Warpage | Shell | 0 deg | > 15 deg |
| Skewness | Shell | 0 | > 0.5 |
| Volume Change | Solid | 1.0 | < 0.1 or > 10.0 |
| Area Change | Shell | 1.0 | < 0.1 or > 10.0 |

### 8.8 샘플링 전략

계산 비용을 절감하기 위해 전체 상태(State) 중 최대 10개를 균등 간격으로 샘플링한다.

```cpp
size_t n_samples = std::min(n_states, size_t(10));
for (size_t i = 0; i < n_samples; ++i) {
    size_t idx = i * (n_states - 1) / (n_samples - 1);
    sample_indices.push_back(idx);
}
```

---

## 9. 충격 응답 스펙트럼 (SRS)

### 9.1 단자유도계(SDOF) 운동방정식

충격 응답 스펙트럼(Shock Response Spectrum, SRS)은 단자유도계(Single Degree of Freedom System, SDOF) 모델을 기반으로 한다.

기저 가진(Base excitation)하의 SDOF 운동방정식:

```
m*x_abs_ddot + c*(x_abs_dot - x_base_dot) + k*(x_abs - x_base) = 0
```

상대 좌표 z = x_abs - x_base로 변환:

```
z_ddot + 2*zeta*omega_n*z_dot + omega_n^2*z = -x_base_ddot
```

여기서:
- omega_n = sqrt(k/m): 비감쇠 고유진동수 [rad/s]
- zeta = c/(2*m*omega_n): 감쇠비 [무차원]
- f_n = omega_n/(2*pi): 고유진동수 [Hz]

### 9.2 SRS 정의

SRS(f_n)는 주파수 f_n인 SDOF 시스템이 충격 입력 x_base_ddot(t)에 의해 경험하는 최대 절대 가속도 응답이다.

```
SRS(f_n) = max_{t >= 0} |x_abs_ddot(t; f_n, zeta)|
```

또는 등가적으로:

```
SRS(f_n) = max_{t >= 0} |omega_n^2*z(t) + 2*zeta*omega_n*z_dot(t) + x_base_ddot(t)|
```

### 9.3 감쇠비와 주파수 범위

본 시스템에서는 표준값 zeta = 0.05를 사용한다 (MIL-STD-810 표준).

**주파수 스윕 범위**: 10 Hz ~ 10,000 Hz (로그 스케일, 1/6 옥타브 간격)

### 9.4 수치 적분법 (Runge-Kutta 4차)

SRS 계산은 각 주파수 f_n에 대해 SDOF 방정식을 수치 적분한다.

상태 벡터 y = [z, z_dot]로 정의하면:

```
dy/dt = [z_dot, -omega_n^2*z - 2*zeta*omega_n*z_dot - a_input(t)]
```

Runge-Kutta 4차 (RK4) 스텝:

```
k_1 = f(t_n, y_n)
k_2 = f(t_n + h/2, y_n + h*k_1/2)
k_3 = f(t_n + h/2, y_n + h*k_2/2)
k_4 = f(t_n + h, y_n + h*k_3)

y_{n+1} = y_n + (h/6)(k_1 + 2*k_2 + 2*k_3 + k_4)
```

RK4의 전역 오차는 O(h^4)이다.

적분 시간 스텝 h 안정성 조건:

```
h <= 1 / (20*f_n)   (최고 주파수의 20배 이상 샘플링)
```

### 9.5 SRS와 낙하 분석의 관계

koo_report HTML 리포트의 충격 분석 탭(Tab 8: Impact Analysis)에서 SRS 관련 분석은 다음과 같이 활용된다:

1. **충격 펄스 특성화**: 가속도 시계열에서 피크, 펄스폭(반파사인 등가) 추출
2. **주파수 의존성 평가**: 펄스폭이 방향에 따라 크게 변하면 SRS 분석을 방향별 별도로 수행해야 함
3. **규격 참조**: IEC 60068-2-27 반파사인 등가 파라미터

---

## 10. CAI 균열 정지 지수 (Crack Arrest Index)

### 10.1 정의

CAI(Crack Arrest Index)는 낙하 충격 후 균열이 정지(Arrest)될 가능성을 평가하는 복합 지표이다. 값이 높을수록 균열 정지에 유리하다.

```
CAI = w_1*SDR_score + w_2*LoadRate_score + w_3*SCF_score + w_4*Diss_score
```

가중치: w_1 = 0.30, w_2 = 0.20, w_3 = 0.25, w_4 = 0.25

### 10.2 4개 하위 지표 상세

**Indicator 1: 응력 지속비 (Stress Duration Ratio, SDR)**

응력이 임계값 이상인 시간 비율:

```
threshold = min(sigma_y, 0.7*sigma_peak)    [항복응력이 있는 경우]
          = 0.7*sigma_peak                  [항복응력 미지정]

SDR = T_above / T_total
SDR_score = 1 - SDR       [높을수록 균열 정지에 유리]
```

코드 구현:
```javascript
const threshold = ys > 0 ? Math.min(ys, peakStress * 0.7) : peakStress * 0.7;
let aboveTime = 0;
for (let i = 1; i < n; i++) {
  if (sMax[i] >= threshold || sMax[i-1] >= threshold) {
    aboveTime += times[i] - times[i-1];
  }
}
const sdr = aboveTime / totalDuration;
const sdrScore = 1 - sdr;
```

**Indicator 2: 하중 속도 점수 (Loading Rate Score)**

피크 전 최대 응력 상승률:

```
maxRate = max_{i=1..peakIdx} [(sigma_max[i] - sigma_max[i-1]) / (t[i] - t[i-1])]

logRate = log10(maxRate)
LoadRate_score = clamp(1 - (logRate - 6) / 4, 0, 1)
```

로그 스케일 정규화: 10^6 MPa/s = 0점(취성적), 10^10 MPa/s 이상 = 0점. 높은 하중 속도는 취성 파괴를 촉진하므로 균열 정지에 불리하다.

코드 구현:
```javascript
const logRate = maxRate > 0 ? Math.log10(maxRate) : 0;
const loadRateScore = Math.max(0, Math.min(1, 1 - (logRate - 6) / 4));
```

**Indicator 3: 응력 집중 계수 점수 (Stress Concentration Factor Score)**

피크 시간에서의 최대/평균 응력비:

```
SCF = sigma_peak / sigma_avg_at_peak

SCF_score = clamp(1 - (SCF - 1) / 3, 0, 1)
```

SCF = 1 (균일 분포) -> score = 1 (유리)
SCF >= 4 -> score = 0 (불리: 높은 집중은 소성 영역이 작아 정지 불리)

코드 구현:
```javascript
const scf = avgAtPeak > 0 ? peakStress / avgAtPeak : 1;
const scfScore = Math.max(0, Math.min(1, 1 - (scf - 1) / 3));
```

**Indicator 4: 에너지 소산율 점수 (Energy Dissipation Score)**

피크 후 응력 감소 속도 — 실제 곡선하 면적 대비 지속 피크 가정 면적의 비:

```
postPeakArea = sum_{i=peakIdx+1}^{N} sigma_max[i] * dt[i]
sustainedArea = sum_{i=peakIdx+1}^{N} sigma_peak * dt[i]

dissRatio = postPeakArea / sustainedArea
Diss_score = clamp(1 - dissRatio, 0, 1)
```

빠른 감쇠(dissRatio -> 0) = 높은 점수(균열 정지에 유리)
지속적 고응력(dissRatio -> 1) = 낮은 점수(불리)

코드 구현:
```javascript
let postPeakArea = 0, sustainedArea = 0;
for (let i = peakIdx + 1; i < n; i++) {
  const dt = times[i] - times[i-1];
  postPeakArea += sMax[i] * dt;
  sustainedArea += peakStress * dt;
}
const dissRatio = sustainedArea > 0 ? postPeakArea / sustainedArea : 1;
const dissScore = Math.max(0, Math.min(1, 1 - dissRatio));
```

### 10.3 CAI 합성

```javascript
const cai = sdrScore * 0.30 + loadRateScore * 0.20 + scfScore * 0.25 + dissScore * 0.25;
```

### 10.4 CAI 해석 기준

| CAI 범위 | 판정 | 색상 코드 |
|---------|------|---------|
| CAI >= 0.6 | 정지 가능 (Arrest Likely) | 녹색 |
| 0.3 <= CAI < 0.6 | 한계 (Marginal) | 황색 |
| CAI < 0.3 | 정지 불가 (Arrest Unlikely) | 적색 |

### 10.5 방향별 CAI 분포

각 낙하 방향에서의 CAI를 계산하여:

1. **통계 집계**: 평균 CAI, 최악(최소) CAI, 정지불가/한계/가능 방향 수
2. **스트립 차트**: 모든 방향을 CAI 오름차순으로 정렬한 막대 그래프
3. **레이더 차트**: 4개 하위 지표의 평균을 레이더 다이어그램으로 시각화

### 10.6 물리적 근거와 한계

CAI는 ASTM E1221 (균열 정지 파괴인성) 및 BS 7910 (구조 건전성 평가)의 개념을 차용하되, 연속체 역학 시계열 데이터로부터 도출한 **간접 프록시(Indirect proxy)**이다.

한계:
- 실제 균열 형상(Crack geometry)을 모델링하지 않음
- K_IC/J-integral 등 파괴역학 파라미터를 직접 계산하지 않음
- 규격 수준의 평가(BS 7910 Level 3)에는 별도의 XFEM 또는 cohesive zone 해석이 필요

---

## 부록 A: 수식 참조표

### A.1 응력 관련

```
Von Mises: sigma_VM = sqrt[(1/2)((sigma_1-sigma_2)^2+(sigma_2-sigma_3)^2+(sigma_3-sigma_1)^2)]

안전계수:  SF = sigma_yield / sigma_VM_peak

삼축성:    eta = sigma_m / sigma_VM
           sigma_m = (sigma_xx + sigma_yy + sigma_zz) / 3

주응력:    Lode 각 theta_L = (1/3)*arccos(J_3 / (2*r^3)),  r = sqrt(J_2/3)
```

### A.2 방향 변환

```
방향벡터:  d = Rz(gamma) * Ry(beta) * Rx(alpha) * [0,0,-1]^T

구면좌표:  lambda = atan2(dx, -dz)
           phi = arcsin(dy)
```

### A.3 Mollweide 투영

```
방정식:    2*theta + sin(2*theta) = pi*sin(phi)   [Newton-Raphson, 감쇠 스텝]
투영:      x = (2*sqrt(2)/pi)*lambda*cos(theta)
           y = sqrt(2)*sin(theta)
```

### A.4 Fibonacci 격자

```
황금비:    phi_g = (1+sqrt(5))/2 = 1.618...

격자점:    theta_i = arccos(1 - 2i/(N-1))
           phi_i = 2*pi*i/phi_g  (mod 2*pi)
```

### A.5 구면 IDW

```
Haversine: d_ij = 2*arcsin(sqrt(sin^2(Delta_phi/2) + cos(phi_i)*cos(phi_j)*sin^2(Delta_lambda/2)))

IDW:       sigma(q) = sum_j(sigma_j/d_qj^p) / sum_j(1/d_qj^p)   (p = 3.5)
```

### A.6 요소 품질

```
Aspect Ratio:  AR = L_max / L_min

Warpage:       theta_warp = arccos(n_1.n_2 / (|n_1|*|n_2|))

Skewness:      S = max|theta_i - 90 deg| / 90 deg

Hex Volume:    V = sum_k (1/6)(b-a).[(c-a)x(d-a)]   (5-tet decomp)

Vol Ratio:     R = V_current / V_initial
```

### A.7 CAI 균열 정지 지수

```
CAI = 0.30*(1-SDR) + 0.20*LoadRate_score + 0.25*SCF_score + 0.25*Diss_score

SDR = T_above_threshold / T_total
LoadRate_score = clamp(1 - (log10(dSigma/dt) - 6)/4, 0, 1)
SCF_score = clamp(1 - (sigma_max/sigma_avg - 1)/3, 0, 1)
Diss_score = clamp(1 - postPeakArea/sustainedArea, 0, 1)
```

---

## 부록 B: 단위 체계

LS-DYNA 표준 단위계 (mm, ms, t, N, MPa):

| 물리량 | 단위 | 변환 |
|--------|------|------|
| 길이 | mm | x 10^-3 = m |
| 시간 | ms | x 10^-3 = s |
| 질량 | t (metric ton) | x 10^3 = kg |
| 힘 | N | = N |
| 응력 | MPa = N/mm^2 | x 10^6 = Pa |
| 가속도 | mm/ms^2 | x 10^3 = m/s^2 |
| G-force | G (무차원) | a[m/s^2] / 9.81 |

가속도 단위 변환:

```
a [mm/ms^2] x (1m/1000mm) x (1000ms/1s)^2 = a x 1000 [m/s^2]

G = a [mm/ms^2] x 1000 / 9.81 = a x 101.97

koo_report 구현: g_factor = 9810.0   [mm/s^2 = 1 G]
```

---

*KooD3plotReader Project -- Mathematical Theory Reference Document*
*최종 수정: 2026-03-09*
