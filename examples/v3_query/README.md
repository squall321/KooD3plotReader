# KooD3plot V3 Query System - Examples

이 디렉토리에는 KooD3plot V3 Query System의 사용 예제가 포함되어 있습니다.

## 📚 예제 목록

### ✅ 01_basic_query.cpp (완료)
**기본 쿼리 사용법**

Query System의 핵심 기능을 보여주는 기본 예제:
- D3plot 파일 열기
- 간단한 쿼리 구성
- Part, Quantity, Time 선택
- 쿼리 검증
- 다양한 선택 패턴

**실행 방법**:
```bash
./01_basic_query crash.d3plot
```

**학습 내용**:
- D3plotQuery 빌더 패턴 사용법
- Selector 클래스 활용
- 정적 팩토리 메서드 (maxVonMises, finalState)
- 쿼리 검증 및 디버깅

---

### 📋 02_part_selection.cpp (예정)
**Part 선택 상세 예제**

다양한 Part 선택 방법:
- ID로 선택
- 이름으로 선택
- 패턴 매칭 (Glob/Regex)
- 재질 ID로 선택
- 속성 필터링
- 논리 연산 (AND/OR/NOT)

---

### 📋 03_time_selection.cpp (예정)
**Time 선택 상세 예제**

시간/스텝 선택 방법:
- 특정 스텝 선택
- 시간 범위 선택
- 특수 선택자 (first, last, all, every)
- 이벤트 기반 선택

---

### 📋 04_filtering.cpp (예정)
**값 필터링 상세 예제**

ValueFilter 활용:
- 범위 필터
- 비교 연산
- 백분위수 필터
- 통계 필터 (outlier, std dev)
- 복합 조건

---

### 📋 05_output_formats.cpp (예정)
**출력 포맷 예제**

다양한 출력 옵션:
- CSV 출력
- JSON 출력 (Phase 4)
- HDF5 출력 (Phase 4)
- 메타데이터 포함
- 커스텀 필드 선택
- Aggregation

---

## 🔧 빌드 방법

### CMake 사용 (권장)
```bash
cd /path/to/KooD3plotReader
mkdir build && cd build
cmake ..
make
```

예제 프로그램들은 `build/examples/` 디렉토리에 생성됩니다.

### 수동 컴파일
```bash
g++ -std=c++17 \
    01_basic_query.cpp \
    -I../../include \
    -L../../build \
    -lkood3plot_query \
    -lkood3plot \
    -o 01_basic_query
```

---

## 📖 사용 가이드

### 기본 패턴

모든 V3 쿼리는 다음 패턴을 따릅니다:

```cpp
#include "kood3plot/query/D3plotQuery.h"

// 1. Reader 생성
D3plotReader reader("crash.d3plot");

// 2. Query 구성
D3plotQuery(reader)
    .selectParts(...)      // 어떤 Part를
    .selectQuantities(...) // 어떤 물리량을
    .selectTime(...)       // 언제
    .whereValue(...)       // 어떤 조건으로
    .output(...)           // 어떤 형식으로
    .writeCSV("output.csv"); // 출력
```

### 선택자 (Selectors)

**PartSelector** - Part 선택:
```cpp
// By ID
PartSelector().byId({1, 2, 3})

// By name
PartSelector().byName({"Hood", "Roof"})

// By pattern
PartSelector().byPattern("Door_*")

// All parts
PartSelector::all()
```

**QuantitySelector** - 물리량 선택:
```cpp
// 개별 선택
QuantitySelector().add("von_mises")

// 카테고리 선택
QuantitySelector().addStressAll()

// 정적 팩토리
QuantitySelector::commonCrash()  // von_mises, effective_strain, displacement
```

**TimeSelector** - 시간 선택:
```cpp
// 특정 스텝
TimeSelector().addStep(0).addStep(-1)  // First and last

// 시간 범위
TimeSelector().addTimeRange(0.0, 10.0, 1.0)

// 정적 팩토리
TimeSelector::lastState()
TimeSelector::allStates()
```

**ValueFilter** - 값 필터:
```cpp
// 단순 필터
ValueFilter().greaterThan(500.0)

// 복합 필터
ValueFilter()
    .greaterThan(100.0)
    .lessThan(1000.0)

// 통계 필터
ValueFilter().inTopPercentile(10)
```

### OutputSpec - 출력 설정:
```cpp
OutputSpec::csv()
    .precision(6)
    .includeHeader(true)
    .includeMetadata(true)
    .fields({"part_id", "element_id", "von_mises"})
```

---

## 🎯 학습 경로

1. **시작**: `01_basic_query.cpp` - 전체 시스템 개요
2. **Part 선택**: `02_part_selection.cpp` - Part 선택 마스터
3. **Time 선택**: `03_time_selection.cpp` - 시간 선택 패턴
4. **필터링**: `04_filtering.cpp` - 고급 필터링 기법
5. **출력**: `05_output_formats.cpp` - 다양한 출력 옵션

---

## 💡 실전 예제

### 예제 1: 최대 응력 찾기
```cpp
D3plotQuery::maxVonMises(reader, {1, 2, 3})
    .writeCSV("max_stress.csv");
```

### 예제 2: 최종 상태 전체 데이터
```cpp
D3plotQuery::finalState(reader)
    .writeCSV("final_state.csv");
```

### 예제 3: 특정 부품 시간 이력
```cpp
D3plotQuery::timeHistory(reader, 100, 5000)
    .writeCSV("time_history.csv");
```

### 예제 4: 고응력 영역 추출
```cpp
D3plotQuery(reader)
    .selectAllParts()
    .selectQuantities({"von_mises"})
    .selectTime({-1})
    .whereValue(ValueFilter().greaterThan(500.0))
    .writeCSV("high_stress.csv");
```

---

## 📊 Phase 1 vs Phase 2

### Phase 1 (현재) ✅
- ✅ Query API 완전 구현
- ✅ Selector 시스템 완성
- ✅ 쿼리 검증 및 introspection
- ✅ OutputSpec 설정
- ⏳ 실제 데이터 추출은 미구현

### Phase 2 (다음) 🚧
- 🚧 실제 d3plot 데이터 읽기
- 🚧 물리량 계산 (von Mises, effective strain 등)
- 🚧 ValueFilter 적용
- 🚧 QueryResult 구현
- 🚧 실제 파일 쓰기 완성

---

## 🐛 문제 해결

### 컴파일 에러
- C++17 이상 필요: `g++ -std=c++17 ...`
- Include 경로 확인: `-I../../include`
- 라이브러리 링크: `-lkood3plot_query -lkood3plot`

### 실행 에러
- D3plot 파일 경로 확인
- 파일 읽기 권한 확인
- Phase 2 기능은 아직 미구현 (데이터 추출)

---

## 📚 추가 리소스

- [V3 Master Plan](../../KOOD3PLOT_V3_MASTER_PLAN.md)
- [V3 Quick Reference](../../KOOD3PLOT_V3_QUICKREF.md)
- [V3 Progress](../../V3_PROGRESS.md)
- [API Documentation](../../docs/api/)

---

**마지막 업데이트**: 2025-11-21
**Phase 1 상태**: 80% 완료 (8/10 tasks)
