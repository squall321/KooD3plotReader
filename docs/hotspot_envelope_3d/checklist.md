# 핫스팟 군집 3D 인벨롭 — 체크리스트

## G0. 데이터 경로 (sphere 가 군집을 받게)
- [ ] `loader.py` 가 런별 `analysis_result.json` 의 `hotspot_clusters` 수집
      → verify: 군집 있는 캠페인에서 각도별 군집 수가 0 이 아님
- [ ] 지정 파트 필터 (`--hotspot-part <pid>`) → verify: 다른 파트 군집이 안 섞임
- [ ] 군집 없는 캠페인에서 탭 자체를 감춤 (있을때/없을때 규율)
      → verify: Test_006 로 렌더 시 탭 미노출·경고 없음

## G1. 파트 메쉬
- [ ] `make_stl` 로 지정 파트만 추출 (`parts_csv`) → verify: p 배열 pid 집합 == {지정 pid}
- [ ] 메쉬 payload 를 리포트에 임베드 (기존 device_preview 규약 재사용)
      → verify: 삼각형 수·bbox 가 군집 bbox 와 같은 좌표계

## G2. 자체 캔버스 3D 뷰어 (기본)
- [ ] `drawDeviceMesh` 기반 회전 뷰어 — 드래그 회전 · 휠 줌
      → verify: 마우스 조작으로 시점 변화, JS 예외 0
- [ ] 반투명 메쉬 + 군집 구 깊이 정렬 → verify: 앞뒤 가림이 뒤집히지 않음
- [ ] 각도명+순위 문자 라벨 → verify: 겹침 시 가독성 (거리순 선별)
- [ ] 각도 체크박스 on/off → verify: 끈 각도의 구가 사라짐

## G3. Plotly 번들 옵션
- [ ] `--viewer {canvas,plotly}` CLI → verify: 둘 다 렌더됨
- [ ] Plotly 3.60MB **번들**(CDN 아님) → verify: 네트워크 차단 상태에서 동작
- [ ] **deep report 오프라인화** — `cdn.plot.ly` 참조 제거
      → verify: 네트워크 차단 상태에서 기존 핫스팟 탭 정상

## G4. 각도 선택
- [ ] 26방향 군 프리셋 — F1~F6 · E01~E12 · C1~C8 → verify: 26개 선택됨
- [ ] 커스텀 각도 목록 → verify: 지정한 것만 나옴
- [ ] 전체 → verify: 캠페인 전 각도

## G5. 리스크 척도 (색) — 참에너지 적분

### G5a. C++ — 소성일 적분 (w_p = ∫σ_vm dε_p)
- [x] `accumulateElementExtremes` 요소 루프에 사다리꼴 누적 추가 (솔리드·셸·두꺼운셸)
      → verify: 독립 프로그램 재계산과 일치 (1.29499e-05 == 1.295e-05)
- [x] ~~Δε_p<0 버림~~ → **러닝맥스 초과분만** (실측으로 규칙 교체, context-notes 참조)
      → verify: 상한 σ_max·ε_max 의 50.0% = 삼각형 적분과 일치
- [x] ε_p 비단조 경고 (10% 초과 시) → verify: 실덱에서 42.9% 로 출력됨
- [x] 상태 1개면 NaN(미기록) → verify: work_ok=(ns>=2) 로 배열 자체를 비움
- [x] `plasticWorkDensity(kind)` 접근자 + `computeHotspotClusters` 인자로 전달
      → verify: 기준량과 무관한 양이라 ElementExtremes 와 분리 (복제 방지)
- [x] 군집 집계 `energy_total`(Σw·V) · `energy_max` · `energy_mean` · `energy_available`
      → verify: mean×volume == total 일치, 40/40 군집에서 available
- [x] JSON 내보내기 (미계산이면 키 생략) → verify: 실덱 40군집에 필드 등장, 기존 필드 회귀 0건

### G5b. 리포트 — 색 척도 선택
- [x] 응력 / 변형률 / **에너지(소성일)** / 소성일 밀도 선택 → verify: 파트 1012(thick_shell)
      에서 4척도 모두 컬러바 범위·도형 색이 각각 달라짐 (2D shape fillcolor, 3D mesh intensity)
- [x] 단위 표기 — `energy_total` [mJ], `energy_max` [mJ/mm³]
      → verify: 셀렉트 4항목과 2D/3D 컬러바 제목 모두 단위 포함
- [x] `energy_available=false` · `strain_available=false` 면 각각 선택지 감춤
      → verify: 실덱은 21/21 전부 가용이라 해당 분기를 밟지 못해, 브라우저에서 필드를
      지운 사본으로 확인 — 에너지 제거 시 선택지 [응력, 변형률], 변형률 제거 시
      [응력, 소성일, 소성일 밀도], 상태에 남은 감춰진 척도는 응력으로 폴백
- [x] 균일값(전부 0)일 때 최고위험 색으로 칠하지 않음 → verify: 파트 13 에서 중립 회색
      + 컬러바 숨김 + "소성 변형이 없습니다 (탄성 거동)" 주석
- [x] 툴팁이 색 척도와 일치 → verify: 에너지 선택 시 툴팁에 소성일 값 한 줄 추가
      (1e-5 수준이 `0.00` 으로 뭉개지지 않도록 전용 포매터)

## G6. 컨투어(리스크 맵)
- [ ] 군집 점·반경 → 커널 누적 격자 → verify: 단일 군집일 때 중심이 최대
- [ ] 리스크 값 가중 → verify: 약한 군집 다수 < 강한 군집 소수
- [ ] 개별 버블 ↔ 컨투어 전환 → verify: 두 모드 모두 JS 예외 0

## 마무리
- [ ] 실데이터 검증 (군집 있는 캠페인)
- [ ] 회귀 — 기존 sphere/deep 리포트 탭 JS 예외 0
- [ ] 오프라인 검증 (네트워크 차단)
- [ ] 커밋 분할 (G0~G6)
