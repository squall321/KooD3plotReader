# 핫스팟 군집 3D 인벨롭 — 체크리스트

## G0. 데이터 경로 (sphere 가 군집을 받게)
- [x] `loader.py` 가 런별 `analysis_result.json` 의 `hotspot_clusters` 수집
      → verify: 미니 캠페인(Test_001 에서 4각도, 핫스팟 켜고 재분석)에서
      원본 92항목 중 군집이 있는 27항목만 수집, `report.json` 과 정확히 일치
- [x] 지정 파트 필터 (`--hotspot-part <pid>[,pid...]`)
      → verify: `15` → 4항목/파트{15}, `1,21` → 8항목/파트{1,21} (다른 파트 0건).
      값이 파트 ID 가 아니면 exit 2 + 사유 (조용히 무시하지 않음)
- [x] `--from-json` 왕복 보존 + 필터 → verify: 군집 항목이 바이트 단위로 동일,
      `--from-json --hotspot-part 15` 도 4항목/파트{15}
- [x] 군집이 없으면 데이터를 싣지 않고 사유를 말한다 (있을때/없을때 규율)
      → verify: `--hotspot-clusters` 없이 돌린 캠페인 → "산출물에 없습니다 …" 안내 후
      `report.json` 에 키 없음(0/4). 존재하지 않는 파트 지정 → "파트 [99] 에 해당하는
      군집이 없습니다" 안내 후 0건. 빈 배열로 채우지 않는다
      (탭 자체를 감추는 UI 게이트는 G2 에서 `has_hotspot` 로 붙인다)
- [x] 회귀 → verify: 군집 없는 기존 1144각도 report.json 재생성 정상(7.1MB, 1.7s),
      브라우저 JS 예외 0

## G1. 파트 메쉬
- [x] `make_stl` 로 지정 파트만 추출 (`parts_csv`)
      → verify: `--hotspot-part 15` → p 집합 {15}(744삼각형), `1,21` → {1,21}(5392).
      빠진 파트는 사유를 단정하지 않고 세 가능성 + `--hotspot-part` 안내
- [x] 메쉬 payload 를 리포트에 임베드 (device_preview 규약 재사용 — 서명·원자 교체)
      → verify: 군집 중심 85/85 가 메쉬 bbox 안(여유 2%). **형상 소스는 런의
      d3plot** — 원본 `.k` 는 평행이동만큼 어긋나 90/104 가 밖으로 나갔다.
      좌표계가 어긋나면 메쉬를 싣지 않는 가드 + 시험 9건 (test_hotspot_mesh.py)

## G2. 자체 캔버스 3D 뷰어 (기본)
- [x] 군집 payload 를 HTML 에 싣기 — 짧은 키·자릿수 축소(583→113B), 상한 20,000
      **순위 라운드로빈** → verify: 시험 9건. 상한에 걸려도 어느 런·기준량도
      통째로 빠지지 않음. 전수는 report.json 에 그대로
- [x] 탭 16 `Hotspot 3D` + 군집 없으면 탭 자체를 감춤 (G0 에서 미뤄 둔 게이트)
      → verify: 군집 없는 Test_001(26각도)에서 탭 숨김·payload 키 없음·탭 17개 순회 예외 0
- [x] `drawDeviceMesh` 기반 회전 뷰어 — 드래그 회전 · 휠 줌
      → verify: 브라우저 실조작 — 드래그·휠로 그림 바뀜, JS 예외 0
      (`.work/envelope_g1/check_g2.py`)
- [x] 반투명 메쉬 + 군집 구 깊이 정렬 (한 목록에 섞어 뒤→앞)
      → verify: 합성 장면(평판+앞뒤 구)으로 픽셀 대조 — 판 뒤 구가 앞보다 어둡고
      (177 vs 187) 좌우를 바꿔도 결론 동일 (`.work/envelope_g1/check_depth.py`)
- [x] 각도명+순위 문자 라벨 — 앞쪽부터 16개, 겹치면 건너뜀, 지시선
      → verify: 중복 라벨 0건. 순위는 파트·기준량별이라 둘 이상이면 `p21`·기준량을 덧붙임
- [x] 각도 체크박스 on/off → verify: 108→0→108, 끈 각도의 구가 사라짐
- [x] **파트 체크박스** (계획 외 — 필요해서 추가). 바닥 플레이트(300mm)가 섞이면
      기기(70mm)가 안 보인다. 배율을 켜진 파트에서 다시 잡는다
      → verify: 파트 23 끄면 삼각형 5482→1405, 전체 해제 시 0/0 + 안내
- [x] **색 범위 2~98 분위** (계획 외 — 필요해서 추가). 실측 104군집에서 98개가
      색 범위 하위 10% 에 몰렸다(최대/중앙 17.5배) → verify: 범례에 `≤`/`≥` 와
      전체 범위를 함께 적고 '전체 min~max' 로 전환 가능

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
