# KooD3plot V3 - Quick Reference Guide

> **5분 안에 시작하기** - 가장 자주 사용하는 명령과 패턴

---

## 🚀 Quick Start

### 1. 기본 쿼리 (CLI)

```bash
# Part의 응력 추출
kood3plot query -d crash.d3plot \
  --parts "Hood" \
  --quantity "von_mises" \
  -o hood_stress.csv

# 여러 Part 동시에
kood3plot query -d crash.d3plot \
  --parts "Hood,Door_LF,Door_RF" \
  --quantity "von_mises" \
  -o stress.csv

# 패턴 매칭
kood3plot query -d crash.d3plot \
  --parts-pattern "Door_*" \
  --quantity "von_mises" \
  -o doors_stress.csv

# 마지막 스텝만
kood3plot query -d crash.d3plot \
  --parts "Hood" \
  --quantity "von_mises" \
  --time -1 \
  -o final_stress.csv
```

### 2. Python API

```python
from kood3plot import D3plotReader, Query

# Reader 생성
reader = D3plotReader("crash.d3plot")

# 기본 쿼리
result = (Query(reader)
    .select_parts(names=["Hood"])
    .select_quantities(["von_mises"])
    .execute()
)

# DataFrame으로 변환
df = result.to_dataframe()
print(df.head())

# 최대값 찾기
max_stress = result.get_max("value")
print(f"Max stress: {max_stress} MPa")
```

### 3. YAML 설정

```yaml
# query.yaml
query:
  data:
    parts: {names: ["Hood"]}
    quantities: {types: ["von_mises"]}
  output:
    file: "result.csv"
```

```bash
kood3plot query -c query.yaml -d crash.d3plot
```

---

## 📋 주요 선택자 (Selectors)

### Part 선택

```yaml
parts:
  # 방법 1: 이름
  names: ["Hood", "Door_LF"]

  # 방법 2: ID
  ids: [1, 2, 3]

  # 방법 3: 패턴
  patterns:
    - pattern: "Door_*"
    - pattern: "^Pillar_[AB]"
      type: "regex"

  # 방법 4: 재질
  materials: [10, 11]

  # 방법 5: 전체
  special: "all"
```

```bash
# CLI
--parts "Hood,Door_LF"
--parts-id 1,2,3
--parts-pattern "Door_*"
--parts-material 10,11
--parts-all
```

```python
# Python
.select_parts(names=["Hood"])
.select_parts(ids=[1, 2, 3])
.select_parts(pattern="Door_*")
.select_parts(material=[10, 11])
.select_parts_all()
```

### 물리량 선택

```yaml
quantities:
  # 개별 타입
  types: ["von_mises", "effective_strain", "displacement_magnitude"]

  # 카테고리
  categories: ["stress_all", "strain_all"]

  # 성분별
  components:
    stress: ["x", "y", "z", "von_mises"]
```

```bash
# CLI
--quantity "von_mises"
--quantity "stress_all"
```

```python
# Python
.select_quantities(["von_mises"])
.select_stress_all()
.select_strain_all()
```

**주요 물리량**:
- `von_mises` - Von Mises 응력
- `effective_strain` - 유효 변형률
- `plastic_strain` - 소성 변형률
- `displacement_magnitude` - 변위 크기
- `energy_internal` - 내부 에너지
- `triaxiality` - 삼축 응력도

### 시간 선택

```yaml
time:
  # 특정 스텝
  steps: [0, 10, 20, -1]  # -1 = 마지막

  # 범위
  time_range:
    start: 0.0
    end: 0.05
    step: 0.001

  # 특수
  special: ["first", "last", "all"]
```

```bash
# CLI
--time "0,10,20,-1"
--time-range "0:0.05:0.001"
--time-all
--time-last
```

```python
# Python
.where_time(steps=[0, 10, 20, -1])
.where_time_range(0.0, 0.05, 0.001)
.where_time_all()
.where_time_last()
```

---

## 🔍 필터링 (Filters)

### 값 필터

```yaml
filter:
  # 범위
  range: {min: 100.0, max: 500.0}

  # 조건
  conditions:
    - field: "von_mises"
      operator: ">"
      value: 100.0

  # 표현식
  expression: "von_mises > 100 && effective_strain < 0.3"

  # 백분위
  percentile: {above: 90}  # 상위 10%
```

```bash
# CLI
--filter "value > 100"
--filter-range "100:500"
--filter-percentile 90
```

```python
# Python
.filter_value(min=100, max=500)
.filter_expression("value > 100 && strain < 0.3")
.filter_percentile(above=90)
```

### 공간 필터

```yaml
spatial:
  bounding_box:
    min: [0, -100, 0]
    max: [1000, 100, 500]

  section_plane:
    base_point: [500, 0, 0]
    normal: [1, 0, 0]
```

```python
# Python
.filter_spatial_bbox(min=[0, -100, 0], max=[1000, 100, 500])
.filter_spatial_plane(base=[500, 0, 0], normal=[1, 0, 0])
```

---

## 📤 출력 설정 (Output)

### 기본 설정

```yaml
output:
  file: "result.csv"
  format: "csv"  # csv, json, hdf5, parquet
  aggregation: "none"  # none, max, min, mean, history
  precision: 6
  units: "mm_ton_s"
  fields: ["time", "part_name", "element_id", "value"]
```

```bash
# CLI
-o result.csv
--output-format json
--output-agg max
--output-precision 6
--output-fields "time,part_name,value"
```

```python
# Python
.output(
    file="result.csv",
    format="csv",
    aggregation="max",
    precision=6,
    fields=["time", "part_name", "value"]
)
```

### 집계 모드

| Mode | 설명 | 사용 예 |
|------|------|---------|
| `none` | 전체 데이터 | 모든 요소, 모든 시간 |
| `max` | 최대값만 | 전체 중 최대 응력 |
| `min` | 최소값만 | 전체 중 최소 값 |
| `mean` | 평균값 | Part 평균 응력 |
| `history` | 시간 이력 | 시간별 최대값 추적 |
| `spatial_max` | 공간 최대값 | 각 시간의 최대 요소 |

---

## 🎯 템플릿 (Templates)

### 사용법

```bash
# 템플릿 목록
kood3plot template list

# 템플릿 정보
kood3plot template info max_stress_history

# 템플릿 실행
kood3plot template max_stress_history \
  -d crash.d3plot \
  --params parts="Hood,Door_LF" \
  --params stress_type="von_mises"
```

```python
# Python
from kood3plot import Template

result = Template.load("max_stress_history").execute(
    reader,
    parts=["Hood", "Door_LF"],
    stress_type="von_mises"
)
```

### 기본 템플릿

| 템플릿 | 설명 | 매개변수 |
|--------|------|----------|
| `max_stress_history` | Part별 최대 응력 이력 | parts, stress_type |
| `stress_distribution` | 응력 분포 | parts, bins |
| `critical_elements` | 임계값 초과 요소 | threshold, quantity |
| `energy_absorption` | 에너지 흡수 이력 | parts |
| `section_analysis` | 섹션 분석 | part, orientation, position |
| `part_comparison` | Part 비교 | parts, quantity |
| `full_summary` | 전체 요약 | - |

---

## 💡 일반적 사용 사례

### 1. Part의 최대 응력 찾기

```bash
kood3plot query -d crash.d3plot \
  --parts "Hood" \
  --quantity "von_mises" \
  --output-agg max \
  -o hood_max.json
```

```python
result = Query.part_max_stress(reader, "Hood", "von_mises")
print(f"Max: {result.value} MPa at element {result.element_id}")
```

### 2. 시간 이력 추출

```bash
kood3plot query -d crash.d3plot \
  --parts "Hood" \
  --quantity "von_mises" \
  --time-all \
  --output-agg spatial_max \
  -o hood_history.csv
```

```python
result = Query.part_stress_history(reader, "Hood", "von_mises")
df = result.to_dataframe()
df.plot(x='time', y='value')
```

### 3. 여러 Part 비교

```bash
kood3plot query -d crash.d3plot \
  --parts "Hood,Door_LF,Door_RF" \
  --quantity "von_mises" \
  --time -1 \
  --output-agg max \
  -o comparison.json
```

```python
parts = ["Hood", "Door_LF", "Door_RF"]
for part in parts:
    result = Query.part_max_stress(reader, part)
    print(f"{part}: {result.value} MPa")
```

### 4. 임계값 초과 요소

```bash
kood3plot query -d crash.d3plot \
  --parts-all \
  --quantity "von_mises" \
  --filter "value > 400" \
  -o critical.csv
```

```python
result = (Query(reader)
    .select_parts_all()
    .select_quantities(["von_mises"])
    .filter_value(min=400)
    .execute()
)
print(f"Critical elements: {result.num_rows}")
```

### 5. 특정 영역 분석

```bash
kood3plot query -d crash.d3plot \
  --parts "Hood" \
  --quantity "von_mises" \
  --spatial-bbox "400,-50,100:600,50,200" \
  -o region.csv
```

```python
result = (Query(reader)
    .select_parts(names=["Hood"])
    .select_quantities(["von_mises"])
    .filter_spatial_bbox(
        min=[400, -50, 100],
        max=[600, 50, 200]
    )
    .execute()
)
```

---

## 🔧 고급 기능

### 배치 쿼리

```yaml
# batch.yaml
batch:
  parallel: true
  queries:
    - name: "hood_stress"
      query: {...}
    - name: "door_strain"
      query: {...}
```

```bash
kood3plot batch -c batch.yaml -d crash.d3plot
```

### 스트리밍 (대용량)

```python
# 메모리 효율적 처리
stream = query.stream()
while stream.hasNext():
    row = stream.next()
    process(row)  # 한 번에 한 row
```

### 커스텀 템플릿

```yaml
# my_template.yaml
template:
  name: "my_analysis"
  parameters:
    - name: "parts"
      required: true
  query:
    data:
      parts: {names: "{{parts}}"}
      quantities: {types: ["von_mises"]}
```

```bash
kood3plot template create my_analysis -f my_template.yaml
kood3plot template my_analysis --params parts="Hood"
```

---

## 📊 출력 포맷 예제

### CSV

```csv
time,state,part_name,element_id,value
0.000000,0,Hood,1234,0.000000
0.001000,1,Hood,1234,125.456
```

### JSON

```json
{
  "data": [
    {
      "time": 0.0,
      "part_name": "Hood",
      "value": 0.0
    }
  ]
}
```

### Python DataFrame

```python
df = result.to_dataframe()
#        time  state part_name  element_id    value
# 0  0.000000      0      Hood        1234    0.000
# 1  0.001000      1      Hood        1234  125.456
```

---

## 🐛 문제 해결

### 문제: Part를 찾을 수 없음

```bash
# Part 목록 확인
kood3plot info -d crash.d3plot --parts

# 출력:
# Part 1: Hood (12345 elements)
# Part 2: Door_LF (5678 elements)
# ...
```

### 문제: 메모리 부족

```python
# 스트리밍 모드 사용
stream = query.stream()
# 또는 청크 크기 설정
query.setChunkSize(1000)
```

### 문제: 느린 쿼리

```python
# 캐싱 활성화
query.enableCache(True)

# 병렬 처리
query.setParallel(True, threads=8)

# 필요한 필드만 선택
.output(fields=["time", "value"])  # 좌표 제외
```

---

## 📚 더 알아보기

- 📖 **전체 계획서**: [KOOD3PLOT_V3_MASTER_PLAN.md](KOOD3PLOT_V3_MASTER_PLAN.md)
- 🔄 **V2 vs V3**: [V2_VS_V3_COMPARISON.md](V2_VS_V3_COMPARISON.md)
- 💻 **API 문서**: (구현 후 생성 예정)
- 🎓 **튜토리얼**: (구현 후 생성 예정)

---

## 🎯 명령어 치트시트

### CLI

```bash
# 기본 쿼리
kood3plot query -d <d3plot> --parts <names> --quantity <type> -o <output>

# 필터링
--filter "value > 100"
--filter-range "100:500"

# 시간
--time "0,10,-1"
--time-all
--time-last

# 출력
--output-format csv|json|hdf5
--output-agg none|max|min|mean
--output-fields "time,part,value"

# 템플릿
kood3plot template <name> --params key=value

# 정보
kood3plot info -d <d3plot>
kood3plot info -d <d3plot> --parts
```

### Python 핵심 패턴

```python
from kood3plot import D3plotReader, Query

reader = D3plotReader("crash.d3plot")

# 기본
result = (Query(reader)
    .select_parts(names=["Hood"])
    .select_quantities(["von_mises"])
    .execute()
)

# 필터
result = (query
    .filter_value(min=100)
    .filter_spatial_bbox(min=[...], max=[...])
    .execute()
)

# 결과 처리
df = result.to_dataframe()
max_val = result.get_max("value")
mean_val = result.get_mean("value")
```

---

**Version**: 3.0.0 Quick Reference
**Last Updated**: 2025-11-21
