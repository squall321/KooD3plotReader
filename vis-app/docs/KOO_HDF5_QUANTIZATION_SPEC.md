# KOO-HDF5 지능형 양자화 시스템 명세

**목표**: 물리량의 단위와 유효숫자에 기반한 자동 양자화 시스템
**핵심**: 사용자가 포맷 걱정 없이 설정만으로 최적 압축 + 품질 달성

---

## 1. 핵심 개념: 물리량 기반 양자화

### 1.1 문제 정의

**기존 방식의 문제점**:
```cpp
// ❌ 단순한 min/max 양자화
float min = -100.0f, max = 100.0f;
uint16_t q = (value - min) / (max - min) * 65535;

// 문제:
// 1. 물리적 의미 무시 (변위? 응력? 단위는?)
// 2. 유효숫자 고려 안 함 (0.001mm 필요? 0.1mm 충분?)
// 3. 범위 추정 어려움 (최대값을 모르면?)
```

**KOO-HDF5 방식**:
```cpp
// ✅ 물리량 + 유효숫자 기반
PhysicalQuantity quantity = {
    .type = PhysicalType::DISPLACEMENT,
    .unit = Unit::MILLIMETER,
    .significant_digits = 3,  // 0.001mm 정밀도
    .expected_range = {-500.0, 500.0}  // 일반적인 범위
};

auto quantizer = create_quantizer(quantity);
// → 자동으로 최적 비트수, 스케일 결정
```

### 1.2 물리량 분류 체계

```cpp
enum class PhysicalType {
    // 기하학적 (절대값)
    DISPLACEMENT,          // 변위
    COORDINATE,            // 좌표

    // 역학적 (상대값, 넓은 범위)
    STRESS_VON_MISES,      // Von Mises 응력
    STRESS_COMPONENT,      // 응력 성분 (σx, σy, ...)
    STRAIN,                // 변형률
    PLASTIC_STRAIN,        // 소성 변형률

    // 운동학적
    VELOCITY,              // 속도
    ACCELERATION,          // 가속도

    // 에너지
    INTERNAL_ENERGY,       // 내부 에너지
    KINETIC_ENERGY,        // 운동 에너지

    // 기타
    TEMPERATURE,           // 온도
    DENSITY,               // 밀도
    PRESSURE,              // 압력

    // 정수형
    ELEMENT_ID,            // 요소 ID
    NODE_ID,               // 노드 ID
    PART_ID                // Part ID
};

enum class Unit {
    // 길이
    METER, MILLIMETER, MICROMETER,

    // 응력/압력
    PASCAL, MEGAPASCAL, GIGAPASCAL,

    // 속도
    METER_PER_SECOND, MILLIMETER_PER_SECOND,

    // 에너지
    JOULE, MILLIJOULE,

    // 무차원
    DIMENSIONLESS
};
```

---

## 2. 유효숫자 기반 비트수 자동 결정

### 2.1 정밀도 요구사항 정의

**물리량별 일반적인 유효숫자**:

| 물리량 | 일반 정밀도 | 고정밀도 | 이유 |
|--------|-----------|----------|------|
| **변위** | 0.01mm (2자리) | 0.001mm (3자리) | 육안 판별 한계 ~0.05mm |
| **응력 (MPa)** | 0.1MPa (1자리) | 0.01MPa (2자리) | 재료 항복 응력 대비 |
| **변형률** | 1e-5 (5자리) | 1e-6 (6자리) | 탄성 한계 ~0.002 |
| **속도** | 0.1mm/s | 0.01mm/s | 충돌 속도 m/s 단위 |
| **가속도** | 1mm/s² | 0.1mm/s² | 중력 가속도 ~9810mm/s² |
| **온도** | 1K | 0.1K | 열전달 해석 |

### 2.2 비트수 계산 알고리즘

**핵심 공식**:
```
필요 레벨 수 = (최대값 - 최소값) / 정밀도
필요 비트수 = ceil(log2(필요 레벨 수))
```

**예시 1: 변위 (0.01mm 정밀도)**
```python
range_mm = (-500, 500)  # 1000mm 범위
precision = 0.01        # 0.01mm 정밀도

levels = (500 - (-500)) / 0.01 = 100,000
bits = ceil(log2(100,000)) = 17 bits

→ 실제 사용: 17 bits (custom) 또는 24 bits (3 bytes)
→ 압축률: 25% (vs float32)
```

**예시 2: 응력 (0.1MPa 정밀도, 로그 스케일)**
```python
range_mpa = (0.001, 1000)  # 0.001~1000 MPa (6차수)
precision_relative = 0.001  # 0.1% 상대 오차

# 로그 스케일: log10(1000/0.001) = 6차수
log_range = log10(1000) - log10(0.001) = 6
levels = 6 / (precision_relative) = 6000

bits = ceil(log2(6000)) = 13 bits

→ 실제 사용: 16 bits (2 bytes)
→ 압축률: 50% (vs float32)
```

**예시 3: 변형률 (1e-6 정밀도)**
```python
range_strain = (-0.5, 0.5)  # -50% ~ +50% 변형
precision = 1e-6

levels = (0.5 - (-0.5)) / 1e-6 = 1,000,000
bits = ceil(log2(1,000,000)) = 20 bits

→ 실제 사용: 24 bits (3 bytes)
→ 압축률: 25% (vs float32)
```

### 2.3 자동 비트수 선택 로직

```cpp
struct QuantizationConfig {
    PhysicalType type;
    Unit unit;
    double precision;           // 절대 정밀도
    std::pair<double, double> expected_range;

    // 자동 계산
    int compute_required_bits() const {
        double range = expected_range.second - expected_range.first;
        double levels = range / precision;

        int bits = std::ceil(std::log2(levels));

        // 표준 비트수로 반올림 (8, 12, 16, 24, 32)
        if (bits <= 8) return 8;
        if (bits <= 12) return 12;
        if (bits <= 16) return 16;
        if (bits <= 24) return 24;
        return 32;
    }

    // 실제 달성 정밀도 (비트수 반올림 후)
    double achieved_precision() const {
        int bits = compute_required_bits();
        int levels = (1 << bits) - 1;
        double range = expected_range.second - expected_range.first;
        return range / levels;
    }
};
```

---

## 3. 물리량별 최적 양자화 전략

### 3.1 변위 (Displacement)

**특성**:
- 선형 변화
- 절대값
- 좁은 범위 (보통 ±수백mm)

**전략**:
```cpp
struct DisplacementQuantizer {
    double precision_mm = 0.01;  // 기본 0.01mm

    QuantizationConfig get_config(const std::vector<float>& data) {
        // 실제 데이터 범위 분석
        auto [min_val, max_val] = analyze_range(data);

        // 여유 10% 추가
        double margin = (max_val - min_val) * 0.1;

        return {
            .type = PhysicalType::DISPLACEMENT,
            .unit = Unit::MILLIMETER,
            .precision = precision_mm,
            .expected_range = {min_val - margin, max_val + margin}
        };
    }
};

// 사용 예:
// 범위: -100 ~ +300 mm
// 정밀도: 0.01mm
// → 400 / 0.01 = 40,000 레벨
// → 16 bits (65,536 레벨) ✅
```

### 3.2 Von Mises 응력 (로그 스케일)

**특성**:
- 항상 양수 (0~)
- 넓은 범위 (0.001 ~ 1000+ MPa, 6차수)
- 상대 오차가 중요

**전략**:
```cpp
struct VonMisesQuantizer {
    double relative_precision = 0.01;  // 1% 상대 오차

    // 로그 스케일 양자화
    uint16_t quantize(float stress_mpa) {
        // σ → log10(σ)
        double log_stress = std::log10(std::max(stress_mpa, 1e-6));

        // 범위: log10(1e-6) ~ log10(1e4) = -6 ~ 4 (10차수)
        double log_min = -6.0;
        double log_max = 4.0;

        double normalized = (log_stress - log_min) / (log_max - log_min);
        return static_cast<uint16_t>(normalized * 65535);
    }

    float dequantize(uint16_t q) {
        double normalized = q / 65535.0;
        double log_stress = normalized * (4.0 - (-6.0)) + (-6.0);
        return std::pow(10.0, log_stress);
    }
};

// 효과:
// - 작은 응력 (0.001 MPa): 1% 오차
// - 큰 응력 (1000 MPa): 1% 오차
// - 균일한 상대 정밀도!
```

### 3.3 변형률 (Strain)

**특성**:
- 부호 있음 (압축/인장)
- 작은 값 (탄성: ~0.002, 소성: ~0.5)
- 높은 정밀도 필요

**전략**:
```cpp
struct StrainQuantizer {
    double precision = 1e-6;  // 기본 1 microstrain

    // 범위별 자동 비트수 선택
    int select_bits(double max_strain) {
        if (max_strain < 0.01) {
            // 탄성 변형 (< 1%)
            // 범위: ±0.01, 정밀도: 1e-6
            // → 20,000 레벨 → 15 bits → 16 bits
            return 16;
        } else if (max_strain < 0.1) {
            // 중간 소성 (< 10%)
            // 범위: ±0.1, 정밀도: 1e-6
            // → 200,000 레벨 → 18 bits → 24 bits
            return 24;
        } else {
            // 대변형 (> 10%)
            // 범위: ±0.5, 정밀도: 1e-5 (완화)
            // → 100,000 레벨 → 17 bits → 24 bits
            return 24;
        }
    }
};
```

### 3.4 Part ID (무손실 압축)

**특성**:
- 정수
- 연속적 (1, 1, 1, 2, 2, 3, ...)
- 반복 패턴

**전략** (이전 개선안 + 추가):
```cpp
struct PartIDCompressor {
    // 1. Delta encoding
    std::vector<int16_t> delta_encode(const std::vector<int32_t>& ids) {
        std::vector<int16_t> deltas;
        deltas.push_back(ids[0]);  // 첫 값은 그대로

        for (size_t i = 1; i < ids.size(); ++i) {
            deltas.push_back(ids[i] - ids[i-1]);  // 대부분 0!
        }
        return deltas;
    }

    // 2. Run-Length Encoding (RLE)
    struct RLEPair {
        int16_t value;
        uint32_t count;
    };

    std::vector<RLEPair> rle_encode(const std::vector<int16_t>& deltas) {
        std::vector<RLEPair> result;

        int16_t current = deltas[0];
        uint32_t count = 1;

        for (size_t i = 1; i < deltas.size(); ++i) {
            if (deltas[i] == current) {
                count++;
            } else {
                result.push_back({current, count});
                current = deltas[i];
                count = 1;
            }
        }
        result.push_back({current, count});

        return result;
    }

    // 3. Varint encoding (가변 길이)
    void write_varint(std::ostream& out, uint64_t value) {
        while (value >= 128) {
            out.put(static_cast<uint8_t>((value & 0x7F) | 0x80));
            value >>= 7;
        }
        out.put(static_cast<uint8_t>(value));
    }
};

// 압축 효과 예시:
// 원본: [1,1,1,1,1,2,2,2,3,3,3,3,3,3] (14개 × 4 bytes = 56 bytes)
// Delta: [1,0,0,0,0,1,0,0,1,0,0,0,0,0] (14개 × 2 bytes = 28 bytes)
// RLE: [(1,1), (0,4), (1,1), (0,2), (1,1), (0,5)] (6쌍)
// Varint: ~15 bytes
// → 압축률: 73% (56 → 15 bytes)
```

---

## 4. KOO-HDF5 메타데이터 포맷

### 4.1 양자화 설정 저장 (HDF5 attributes)

**각 데이터셋마다 첨부**:
```python
# HDF5 구조
/Results/time_050/NodeData/displacement
  - Dataset: int16[N, 3]
  - Attributes:
      "physical_type": "DISPLACEMENT"
      "unit": "MILLIMETER"
      "precision": 0.01
      "scale": [0.015259, 0.015259, 0.015259]  # 실제 계산된 스케일
      "offset": [-100.0, -100.0, -100.0]
      "bits": 16
      "range_actual": [-100.0, 900.0]          # 실제 데이터 범위
      "compression_method": "linear"           # or "logarithmic"
```

**전역 설정** (`/Quantization/Config`):
```yaml
# /Quantization/Config (YAML 형식, HDF5 string attribute)
version: "1.0"
defaults:
  displacement:
    precision_mm: 0.01
    bits: 16
  von_mises:
    relative_precision: 0.01
    bits: 16
    log_scale: true
  strain:
    precision: 1.0e-6
    bits: 24

# 사용자 오버라이드
overrides:
  - path: "/Results/*/NodeData/displacement"
    precision_mm: 0.001  # 고정밀 모드
    bits: 24
```

### 4.2 자동 복원 (무손실 메타데이터)

**핵심**: HDF5 파일만 있으면 **아무 정보 없이** 완벽 복원

```cpp
class HDF5DequantizerAuto {
public:
    std::vector<float> read_and_dequantize(
        H5::DataSet& dataset
    ) {
        // 1. 메타데이터 자동 읽기
        auto type = dataset.Attribute("physical_type").readString();
        auto unit = dataset.Attribute("unit").readString();
        auto scale = dataset.Attribute("scale").readVector<float>();
        auto offset = dataset.Attribute("offset").readVector<float>();
        auto compression = dataset.Attribute("compression_method").readString();

        // 2. 양자화 데이터 읽기
        std::vector<int16_t> quantized;
        dataset.read(quantized);

        // 3. 자동 역양자화
        std::vector<float> result(quantized.size());

        if (compression == "linear") {
            for (size_t i = 0; i < quantized.size(); ++i) {
                result[i] = quantized[i] * scale[i % 3] + offset[i % 3];
            }
        } else if (compression == "logarithmic") {
            for (size_t i = 0; i < quantized.size(); ++i) {
                double normalized = quantized[i] / 65535.0;
                double log_val = normalized * (log_max - log_min) + log_min;
                result[i] = std::pow(10.0, log_val);
            }
        }

        return result;
    }
};

// 사용:
auto data = auto_dequantizer.read_and_dequantize(h5file.getDataset(path));
// → 끝! 포맷 걱정 전혀 없음!
```

---

## 5. CLI 통합: `kood3plot_cli`

### 5.1 양자화 프로파일 시스템

**사전 정의된 프로파일**:
```bash
# 1. 기본 프로파일 (균형)
kood3plot_cli --mode export --format hdf5 \
              --profile default \
              d3plot output.h5

# 2. 고정밀 프로파일 (연구용)
kood3plot_cli --mode export --format hdf5 \
              --profile high_precision \
              d3plot output.h5

# 3. 저용량 프로파일 (빠른 미리보기)
kood3plot_cli --mode export --format hdf5 \
              --profile low_storage \
              d3plot output.h5

# 4. 사용자 정의
kood3plot_cli --mode export --format hdf5 \
              --quantization-config custom.yaml \
              d3plot output.h5
```

**프로파일 정의** (`profiles/default.yaml`):
```yaml
name: "Default Profile"
description: "Balanced precision and compression"

quantization:
  displacement:
    precision_mm: 0.01
    auto_range: true      # 자동 범위 감지

  von_mises:
    relative_precision: 0.01
    log_scale: true
    min_value: 1.0e-3     # 0.001 MPa 이하는 0으로

  strain:
    precision: 1.0e-6
    adaptive: true        # 탄성/소성 자동 감지

  velocity:
    precision_mm_s: 0.1

  part_id:
    compression: "delta_rle_varint"
    lossless: true

hdf5:
  compression: "gzip"
  compression_level: 6
  chunking: "auto"
```

**고정밀 프로파일** (`profiles/high_precision.yaml`):
```yaml
name: "High Precision Profile"
description: "Research-grade accuracy"

quantization:
  displacement:
    precision_mm: 0.001   # 10배 정밀
    bits: 24              # 명시적 지정

  von_mises:
    relative_precision: 0.001  # 0.1%
    bits: 20

  strain:
    precision: 1.0e-7     # 10배 정밀
    bits: 32              # float32 유지

  # 나머지 동일...
```

### 5.2 대화형 프로파일 생성

```bash
kood3plot_cli --mode create-profile --interactive

# 대화형 프롬프트:
> What is the typical displacement range in your simulation? (mm)
  [-500, 500]

> What precision do you need for displacement? (mm)
  [0.01] (default)

> What is the maximum Von Mises stress? (MPa)
  [1000]

> Do you need high precision for strain? (y/n)
  [n]

# 자동 생성:
# → profiles/my_simulation.yaml
# → 최적 비트수, 압축 설정 자동 계산
```

### 5.3 검증 및 보고서

```bash
# 양자화 품질 미리보기
kood3plot_cli --mode validate \
              --quantization-config default.yaml \
              --sample-timesteps 10 \
              d3plot

# 출력:
===============================================
Quantization Validation Report
===============================================

Displacement:
  - Precision: 0.01 mm
  - Actual range: [-123.45, 678.90] mm
  - Bits required: 16
  - Max error: 0.0098 mm (98% of target)
  - SNR: 78.2 dB
  - Status: ✅ PASS

Von Mises Stress:
  - Precision: 1% relative
  - Actual range: [0.01, 850.3] MPa
  - Bits required: 16 (log scale)
  - Max relative error: 0.98%
  - SNR: 82.1 dB
  - Status: ✅ PASS

Strain:
  - Precision: 1.0e-6
  - Actual range: [-0.0123, 0.0456]
  - Bits required: 16
  - Max error: 9.8e-7
  - SNR: 74.5 dB
  - Status: ✅ PASS

Estimated compression:
  - Original size: 15.2 GB
  - Compressed size: 2.3 GB (85% reduction)
  - HDF5 file size: 1.8 GB (88% reduction, with gzip)

===============================================
```

---

## 6. Python 간편 접근

### 6.1 투명한 API

```python
import kood3plot

# 1. 자동 역양자화 (포맷 걱정 없음!)
with kood3plot.HDF5File('output.h5') as f:
    # 메타데이터 자동 읽기 → 자동 역양자화
    disp = f.get_displacement(timestep=50)
    # → numpy array, float32, 단위: mm

    stress = f.get_von_mises(timestep=50)
    # → numpy array, float32, 단위: MPa

    strain = f.get_strain(timestep=50, component='xx')
    # → numpy array, float32, 무차원

# 2. 물리량 자동 인식
print(disp.unit)  # "MILLIMETER"
print(disp.precision)  # 0.01
print(disp.physical_type)  # "DISPLACEMENT"

# 3. 단위 변환 (자동)
disp_m = disp.to_unit('METER')
# → 자동 변환: mm → m
```

### 6.2 배치 처리

```python
# 모든 타임스텝 한 번에
all_disp = f.get_displacement_all_timesteps()
# → shape: (num_timesteps, num_nodes, 3)
# → 자동 temporal delta 복원!

# 특정 노드만
node_ids = [100, 200, 300]
disp_subset = f.get_displacement(timestep=50, nodes=node_ids)

# NumPy/Pandas 직접 연동
import pandas as pd
df = pd.DataFrame({
    'x': disp[:, 0],
    'y': disp[:, 1],
    'z': disp[:, 2],
    'magnitude': np.linalg.norm(disp, axis=1)
})
```

---

## 7. 압축률 비교 (실제 예상)

### 7.1 케이스: 자동차 충돌 해석

**모델**:
- 노드: 1,000,000
- 타임스텝: 100
- 변위 범위: -200 ~ +600 mm
- 응력 범위: 0.01 ~ 800 MPa
- 변형률 범위: -0.05 ~ +0.15

**압축 결과**:

| 데이터 | 원본 (GB) | KOO-HDF5 (GB) | 압축률 | 비트수 |
|--------|----------|---------------|--------|--------|
| 좌표 | 0.012 | 0.006 | 50% | 16-bit |
| 변위 (t=0) | 0.012 | 0.006 | 50% | 16-bit (0.01mm) |
| 변위 (t>0) | 1.188 | **0.149** | **87.5%** | 8-bit delta |
| Von Mises (t=0) | 0.004 | 0.002 | 50% | 16-bit log |
| Von Mises (t>0) | 0.396 | **0.050** | **87.5%** | 8-bit delta |
| 변형률 (t=0) | 0.004 | 0.003 | 25% | 24-bit (1e-6) |
| 변형률 (t>0) | 0.396 | **0.297** | **25%** | 24-bit delta |
| Part ID | 0.004 | **0.0004** | **90%** | RLE |
| **Total** | **2.016** | **0.513** | **74.5%** | - |
| **+ gzip** | **2.016** | **0.308** | **84.7%** | - |

**결론**: 단순 float32 대비 **85% 압축** 달성!

---

## 8. 실제 구현 예시 (KooD3plot 통합)

### 8.1 VectorMath 통합

**기존 라이브러리 활용**:
```cpp
#include <kood3plot/analysis/VectorMath.hpp>

using namespace kood3plot::analysis;

// 변위 벡터 양자화 (Vec3 활용)
struct DisplacementQuantizer {
    Vec3 offset;
    Vec3 scale;
    std::array<double, 3> precision = {0.01, 0.01, 0.01};  // mm

    void calibrate(const std::vector<Vec3>& displacements) {
        Vec3 min_vec = displacements[0];
        Vec3 max_vec = displacements[0];

        // SIMD-friendly bounding box calculation
        for (const auto& d : displacements) {
            min_vec = Vec3::min(min_vec, d);
            max_vec = Vec3::max(max_vec, d);
        }

        // 10% margin
        Vec3 range = max_vec - min_vec;
        offset = min_vec - range * 0.1;
        Vec3 adjusted_max = max_vec + range * 0.1;

        // Scale calculation (per component)
        scale.x = (adjusted_max.x - offset.x) / 65535.0;
        scale.y = (adjusted_max.y - offset.y) / 65535.0;
        scale.z = (adjusted_max.z - offset.z) / 65535.0;
    }

    std::array<uint16_t, 3> quantize(const Vec3& displacement) const {
        return {
            static_cast<uint16_t>((displacement.x - offset.x) / scale.x),
            static_cast<uint16_t>((displacement.y - offset.y) / scale.y),
            static_cast<uint16_t>((displacement.z - offset.z) / scale.z)
        };
    }

    Vec3 dequantize(const std::array<uint16_t, 3>& q) const {
        return Vec3(
            q[0] * scale.x + offset.x,
            q[1] * scale.y + offset.y,
            q[2] * scale.z + offset.z
        );
    }
};
```

### 8.2 응력 텐서 양자화 (StressTensor 활용)

**Von Mises 스트레스 로그 스케일**:
```cpp
struct StressTensorQuantizer {
    // Von Mises: 로그 스케일 (16-bit)
    uint16_t quantize_von_mises(const StressTensor& stress) const {
        double vm = stress.vonMises();
        double log_vm = std::log10(std::max(vm, 1e-6));

        // Range: [1e-6, 1e4] MPa → [-6, 4] in log10
        double normalized = (log_vm - (-6.0)) / 10.0;
        return static_cast<uint16_t>(std::clamp(normalized, 0.0, 1.0) * 65535);
    }

    double dequantize_von_mises(uint16_t q) const {
        double normalized = q / 65535.0;
        double log_vm = normalized * 10.0 + (-6.0);
        return std::pow(10.0, log_vm);
    }

    // Principal stresses: 일반 선형 (3개 × 16-bit)
    std::array<uint16_t, 3> quantize_principals(const StressTensor& stress) const {
        auto principals = stress.principalStresses();

        // Typical range: -500 ~ 1000 MPa
        double min_stress = -500.0;
        double max_stress = 1000.0;
        double range = max_stress - min_stress;

        std::array<uint16_t, 3> result;
        for (int i = 0; i < 3; i++) {
            double normalized = (principals[i] - min_stress) / range;
            result[i] = static_cast<uint16_t>(std::clamp(normalized, 0.0, 1.0) * 65535);
        }
        return result;
    }

    // Full tensor: 6 components × 16-bit = 96 bits (vs 192 bits float32)
    std::array<uint16_t, 6> quantize_full(const StressTensor& stress,
                                          double min_normal = -500.0,
                                          double max_normal = 1000.0,
                                          double max_shear = 300.0) const {
        auto arr = stress.toArray();  // [xx, yy, zz, xy, yz, zx]
        std::array<uint16_t, 6> result;

        // Normal stresses (0-2): bipolar range
        for (int i = 0; i < 3; i++) {
            double norm = (arr[i] - min_normal) / (max_normal - min_normal);
            result[i] = static_cast<uint16_t>(std::clamp(norm, 0.0, 1.0) * 65535);
        }

        // Shear stresses (3-5): unipolar range [-max, +max]
        for (int i = 3; i < 6; i++) {
            double norm = (arr[i] + max_shear) / (2.0 * max_shear);
            result[i] = static_cast<uint16_t>(std::clamp(norm, 0.0, 1.0) * 65535);
        }

        return result;
    }
};
```

### 8.3 HDF5 Writer 통합

**완전한 쓰기 예시**:
```cpp
#include <H5Cpp.h>
#include <kood3plot/D3plotReader.hpp>
#include <kood3plot/analysis/VectorMath.hpp>

class KooHDF5Writer {
private:
    H5::H5File file_;
    DisplacementQuantizer disp_quantizer_;
    StressTensorQuantizer stress_quantizer_;

public:
    void write_timestep(int timestep, const StateData& state) {
        std::string group_name = "/Results/time_" +
                                std::to_string(timestep);
        H5::Group group = file_.createGroup(group_name);

        // 1. Write displacement (quantized)
        write_displacement(group, state);

        // 2. Write stress (Von Mises + principals)
        write_stress(group, state);

        // 3. Write Part IDs (compressed)
        write_part_ids(group, state);
    }

private:
    void write_displacement(H5::Group& group, const StateData& state) {
        // Convert to Vec3
        std::vector<Vec3> displacements;
        displacements.reserve(state.node_displacement.size() / 3);

        for (size_t i = 0; i < state.node_displacement.size(); i += 3) {
            displacements.emplace_back(
                state.node_displacement[i],
                state.node_displacement[i + 1],
                state.node_displacement[i + 2]
            );
        }

        // Calibrate quantizer
        disp_quantizer_.calibrate(displacements);

        // Quantize all
        std::vector<uint16_t> quantized;
        quantized.reserve(displacements.size() * 3);

        for (const auto& d : displacements) {
            auto q = disp_quantizer_.quantize(d);
            quantized.push_back(q[0]);
            quantized.push_back(q[1]);
            quantized.push_back(q[2]);
        }

        // Write dataset
        hsize_t dims[2] = {displacements.size(), 3};
        H5::DataSpace dataspace(2, dims);
        H5::DataSet dataset = group.createDataSet(
            "displacement",
            H5::PredType::NATIVE_UINT16,
            dataspace
        );
        dataset.write(quantized.data(), H5::PredType::NATIVE_UINT16);

        // Write metadata
        write_metadata(dataset, "DISPLACEMENT", "MILLIMETER",
                      disp_quantizer_.precision[0],
                      disp_quantizer_.scale.toArray(),
                      disp_quantizer_.offset.toArray());
    }

    void write_stress(H5::Group& group, const StateData& state) {
        // Von Mises only (most common)
        std::vector<uint16_t> vm_quantized;
        vm_quantized.reserve(state.solid_stress.size() / 6);

        for (size_t i = 0; i < state.solid_stress.size(); i += 6) {
            StressTensor tensor(
                state.solid_stress[i],
                state.solid_stress[i + 1],
                state.solid_stress[i + 2],
                state.solid_stress[i + 3],
                state.solid_stress[i + 4],
                state.solid_stress[i + 5]
            );

            vm_quantized.push_back(
                stress_quantizer_.quantize_von_mises(tensor)
            );
        }

        // Write dataset
        hsize_t dims[1] = {vm_quantized.size()};
        H5::DataSpace dataspace(1, dims);
        H5::DataSet dataset = group.createDataSet(
            "von_mises",
            H5::PredType::NATIVE_UINT16,
            dataspace
        );
        dataset.write(vm_quantized.data(), H5::PredType::NATIVE_UINT16);

        // Metadata
        write_metadata(dataset, "STRESS_VON_MISES", "MEGAPASCAL",
                      0.01, {}, {}, "logarithmic");
    }

    void write_metadata(H5::DataSet& dataset,
                       const std::string& physical_type,
                       const std::string& unit,
                       double precision,
                       const std::array<double, 3>& scale = {},
                       const std::array<double, 3>& offset = {},
                       const std::string& compression = "linear") {
        // String attributes
        H5::StrType str_type(H5::PredType::C_S1, H5T_VARIABLE);
        H5::DataSpace attr_space(H5S_SCALAR);

        auto type_attr = dataset.createAttribute("physical_type", str_type, attr_space);
        type_attr.write(str_type, physical_type);

        auto unit_attr = dataset.createAttribute("unit", str_type, attr_space);
        unit_attr.write(str_type, unit);

        auto comp_attr = dataset.createAttribute("compression_method", str_type, attr_space);
        comp_attr.write(str_type, compression);

        // Numeric attributes
        hsize_t dim = 1;
        H5::DataSpace scalar_space(1, &dim);
        auto prec_attr = dataset.createAttribute("precision", H5::PredType::NATIVE_DOUBLE, scalar_space);
        prec_attr.write(H5::PredType::NATIVE_DOUBLE, &precision);

        // Vector attributes
        if (!scale.empty()) {
            hsize_t vec_dim = 3;
            H5::DataSpace vec_space(1, &vec_dim);

            auto scale_attr = dataset.createAttribute("scale", H5::PredType::NATIVE_DOUBLE, vec_space);
            scale_attr.write(H5::PredType::NATIVE_DOUBLE, scale.data());

            auto offset_attr = dataset.createAttribute("offset", H5::PredType::NATIVE_DOUBLE, vec_space);
            offset_attr.write(H5::PredType::NATIVE_DOUBLE, offset.data());
        }
    }
};
```

### 8.4 HDF5 Reader 통합 (자동 역양자화)

```cpp
class KooHDF5Reader {
private:
    H5::H5File file_;

public:
    // 완전 자동 복원 - 사용자는 포맷 몰라도 됨!
    std::vector<Vec3> read_displacement(int timestep) {
        std::string path = "/Results/time_" + std::to_string(timestep) +
                          "/displacement";
        H5::DataSet dataset = file_.openDataSet(path);

        // 1. Read metadata
        auto metadata = read_metadata(dataset);

        // 2. Read quantized data
        H5::DataSpace dataspace = dataset.getSpace();
        hsize_t dims[2];
        dataspace.getSimpleExtentDims(dims);

        std::vector<uint16_t> quantized(dims[0] * dims[1]);
        dataset.read(quantized.data(), H5::PredType::NATIVE_UINT16);

        // 3. Auto-dequantize
        std::vector<Vec3> result;
        result.reserve(dims[0]);

        for (size_t i = 0; i < dims[0]; i++) {
            Vec3 disp(
                quantized[i * 3 + 0] * metadata.scale[0] + metadata.offset[0],
                quantized[i * 3 + 1] * metadata.scale[1] + metadata.offset[1],
                quantized[i * 3 + 2] * metadata.scale[2] + metadata.offset[2]
            );
            result.push_back(disp);
        }

        return result;
    }

    std::vector<double> read_von_mises(int timestep) {
        std::string path = "/Results/time_" + std::to_string(timestep) +
                          "/von_mises";
        H5::DataSet dataset = file_.openDataSet(path);

        auto metadata = read_metadata(dataset);

        // Read quantized
        H5::DataSpace dataspace = dataset.getSpace();
        hsize_t dims[1];
        dataspace.getSimpleExtentDims(dims);

        std::vector<uint16_t> quantized(dims[0]);
        dataset.read(quantized.data(), H5::PredType::NATIVE_UINT16);

        // Dequantize (log scale)
        std::vector<double> result;
        result.reserve(dims[0]);

        if (metadata.compression_method == "logarithmic") {
            for (auto q : quantized) {
                double normalized = q / 65535.0;
                double log_vm = normalized * 10.0 + (-6.0);
                result.push_back(std::pow(10.0, log_vm));
            }
        } else {
            // Linear fallback
            for (auto q : quantized) {
                result.push_back(q * metadata.scale[0] + metadata.offset[0]);
            }
        }

        return result;
    }

private:
    struct Metadata {
        std::string physical_type;
        std::string unit;
        std::string compression_method;
        double precision;
        std::array<double, 3> scale;
        std::array<double, 3> offset;
    };

    Metadata read_metadata(H5::DataSet& dataset) {
        Metadata meta;

        // Read string attributes
        H5::StrType str_type(H5::PredType::C_S1, H5T_VARIABLE);
        dataset.openAttribute("physical_type").read(str_type, meta.physical_type);
        dataset.openAttribute("unit").read(str_type, meta.unit);
        dataset.openAttribute("compression_method").read(str_type, meta.compression_method);

        // Read numeric
        dataset.openAttribute("precision").read(H5::PredType::NATIVE_DOUBLE, &meta.precision);

        // Read vectors (if exist)
        if (dataset.attrExists("scale")) {
            dataset.openAttribute("scale").read(H5::PredType::NATIVE_DOUBLE, meta.scale.data());
            dataset.openAttribute("offset").read(H5::PredType::NATIVE_DOUBLE, meta.offset.data());
        }

        return meta;
    }
};
```

### 8.5 CLI 통합 예시

```cpp
// kood3plot_cli.cpp

void export_hdf5_quantized(const std::string& d3plot_path,
                           const std::string& output_path,
                           const std::string& profile) {
    // 1. Read profile
    QuantizationProfile qprofile = load_profile(profile);

    // 2. Open D3plot
    kood3plot::D3plotReader reader(d3plot_path);
    reader.open();

    // 3. Create HDF5 writer
    KooHDF5Writer writer(output_path, qprofile);

    // 4. Write mesh (once)
    auto mesh = reader.read_mesh();
    writer.write_mesh(mesh);

    // 5. Write all timesteps
    auto states = reader.read_all_states();

    std::cout << "Converting " << states.size() << " timesteps...\n";

    for (size_t i = 0; i < states.size(); i++) {
        writer.write_timestep(i, states[i]);

        if ((i + 1) % 10 == 0) {
            std::cout << "  Progress: " << (i + 1) << "/" << states.size() << "\n";
        }
    }

    std::cout << "Conversion complete!\n";
    writer.print_summary();  // Compression ratio, file size, etc.
}
```

---

## 9. 구현 우선순위

### Phase 1 (Week 1-2): 핵심 인프라
- [ ] `PhysicalQuantity` 클래스 체계
- [ ] 자동 비트수 계산 알고리즘
- [ ] 메타데이터 스키마 정의

### Phase 2 (Week 2-3): 양자화 구현
- [ ] 변위 양자화 (linear, 16-bit)
- [ ] Von Mises 양자화 (log, 16-bit)
- [ ] Part ID 압축 (delta+RLE+varint)
- [ ] Temporal delta compression

### Phase 3 (Week 3-4): HDF5 통합
- [ ] 메타데이터 자동 저장
- [ ] 자동 역양자화 Reader
- [ ] 프로파일 시스템

### Phase 4 (Week 4-5): CLI 통합
- [ ] `--profile` 옵션
- [ ] `--mode validate` 검증
- [ ] 대화형 프로파일 생성

### Phase 5 (Week 5-6): 검증 및 최적화
- [ ] 실제 케이스 테스트
- [ ] 압축률 벤치마크
- [ ] 품질 검증

---

## 9. 결론

### 9.1 차별화 요소

**KOO-HDF5의 핵심 가치**:
1. ✅ **물리량 기반 자동 양자화**: 사용자가 물리적 의미만 지정, 비트수 자동
2. ✅ **유효숫자 보장**: 공학적으로 의미 있는 정밀도 유지
3. ✅ **투명한 복원**: 메타데이터만으로 완벽 복원, 포맷 걱정 없음
4. ✅ **프로파일 시스템**: 사전 정의 + 사용자 정의 + 대화형 생성
5. ✅ **검증 도구**: 변환 전 품질 미리보기

### 9.2 사용자 경험

**Before (일반 HDF5)**:
```python
# 사용자가 직접 역양자화 계산 필요 😰
data = h5file['displacement'][:]
scale = h5file['displacement'].attrs['scale']
offset = h5file['displacement'].attrs['offset']
real_data = data * scale + offset  # 수동 변환
```

**After (KOO-HDF5)**:
```python
# 그냥 읽으면 끝! 😎
data = koo_file.get_displacement(50)
# → 자동 역양자화, 단위 포함, 메타데이터 완비
```

**이것이 진정한 "포맷 걱정 없는" 시스템입니다!**
