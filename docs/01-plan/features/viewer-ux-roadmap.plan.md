# Viewer UX Roadmap — KooViewer

## Executive Summary

| 관점 | 내용 |
|------|------|
| Problem | DeepReport/SphereReport는 기능이 풍부하지만 분석 결과를 다른 사람과 공유하거나 두 설계안을 비교하거나 파트를 선택해 여러 탭에서 동시에 추적하는 워크플로우가 없음 |
| Solution | A/B 비교, 파트 크로스탭 하이라이트, 카테고리 필터, 단축키 가이드, HTML 내보내기, 에너지 파이차트 순서로 단계적 구현 |
| UX Effect | 단일 시뮬레이션 분석 → 설계 비교 + 공유 가능한 리포트 생성 워크플로우로 확장 |
| Core Value | CAE 엔지니어가 회의실에서 바로 쓸 수 있는 분석 결과 공유 도구 |

---

## 구현 계획표

| # | 기능 | 앱 | 우선순위 | 상태 |
|---|------|----|----------|------|
| 1 | **A/B 비교 모드** — 두 JSON 드래그 드롭, Delta Mollweide, 파트별 SF 변화량 표 | Sphere | 최고 | ✅ 완료 |
| 2 | **파트 크로스탭 하이라이트** — 파트 테이블 클릭 → 3D 뷰어 강조, Mollweide 파트 기준 컬러 | 공통 | 높음 | ✅ 완료 |
| 3 | **각도 카테고리 필터** — KPI바 face/edge/corner/fibonacci 토글 → Mollweide/Heatmap 반영 | Sphere | 높음 | ✅ 완료 |
| 4 | **단축키 헬프 오버레이** — `?` 키 → 반투명 오버레이로 모든 단축키/조작법 표시 | 공통 | 중간 | ✅ 완료 |
| 5 | **HTML 리포트 내보내기** — Ctrl+E → self-contained .html (Mollweide SVG + 표 + Findings) | Sphere | 중간 | ✅ 완료 |
| 6 | **에너지 비율 파이차트** — 최종 프레임 KE/IE/HE/SE 비율 + hourglass 경고 | Deep | 낮음 | ✅ 완료 |
| 7 | **방향 민감도 레이더** — 카테고리별 평균 stress 레이더 차트 | Sphere | 낮음 | ✅ 완료 |
| 8 | **세션 저장/복원** — 마지막 실행 경로 자동 복원 (SessionState.hpp) | 공통 | 낮음 | ✅ 완료 |

> 이미 구현된 것: 3D Fringe overlay, 타임스텝 스크러버 (Play/Pause + SliderInt), 섹션뷰 3D, IDW Mollweide contour, Globe recording

---

## 기능 상세

### 1. A/B 비교 모드 (SphereReport)

**트리거**: 두 번째 JSON 파일 드래그 드롭

**UI 변경**:
- KPI바: `B: [project_name]  [X Clear]` 표시
- Mollweide 탭에 "Δ Compare" 서브탭 추가 — A-B 차이를 파란(개선)/빨간(악화) 컬러로 Mollweide에 표시
- Angle Table: B값 열 + Δ열 추가
- Failure 탭: B SF열 + ΔSF열 추가

**상태 추가**:
```cpp
SphereData dataB_;
bool hasDataB_ = false;
```

---

### 2. 파트 크로스탭 하이라이트 (공통)

**트리거**: 파트 테이블 행 클릭

**Deep**: 3D 뷰어에서 선택 파트 → bright yellow, 나머지 → 반투명 회색
**Sphere**: Mollweide 컬러를 "전체 max 대비" → "선택 파트 값 기준"으로 전환

**상태 추가** (이미 `selectedPartId_` 있음, Deep에 추가 필요):
```cpp
int highlightPartId_ = -1;  // DeepReportApp
```

---

### 3. 각도 카테고리 필터 (SphereReport)

**UI**: KPI바 아래 또는 Mollweide 상단에 토글 버튼 4개
```
[✓ Face] [✓ Edge] [✓ Corner] [✓ Fibonacci]
```

**효과**: `data_.results` 전체를 순회할 때 `categoryFilter_` 비교해 필터링

**상태 추가**:
```cpp
std::set<std::string> categoryFilter_ = {"face","edge","corner","fibonacci"};
```

---

### 4. 단축키 헬프 오버레이 (공통)

**트리거**: `?` 키

**내용**:
- Deep: Ctrl+S 스크린샷, 드래그 드롭, 3D 마우스 조작, Play/Pause
- Sphere: Ctrl+S 스크린샷, 드래그 드롭(JSON/STL), 두 번째 JSON=비교모드

---

### 5. HTML 리포트 내보내기 (SphereReport)

**트리거**: Ctrl+E 또는 버튼

**내용**:
- Mollweide SVG (inline, D3.js 없이 순수 SVG path 계산)
- Worst angles 표
- Part failure table
- Findings 텍스트
- 파일명: `{project_name}_sphere_report.html`

---

### 6. 에너지 비율 파이차트 (DeepReport)

**위치**: Energy 탭 하단 추가 섹션

**내용**: ImPlot 파이차트 — KE / IE / HE / SE 비율 (최종 프레임)
**자동 경고**: HE/KE_max > 10% → "Hourglass energy exceeds 10% — check mesh quality"

---

### 7. 방향 민감도 레이더 (SphereReport)

**위치**: Directional 탭 하단 추가 섹션

**내용**: ImPlot radar — face/edge/corner/fibonacci별 평균 stress
