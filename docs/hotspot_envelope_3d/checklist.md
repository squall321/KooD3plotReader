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

## G5. 리스크 척도 (색)
- [ ] 응력 / 변형률 / 에너지근사(`σ̄·ε̄·V`) 선택
      → verify: 척도 바꾸면 색 분포가 실제로 바뀜
- [ ] 에너지근사에 **"피크 순간 근사"** 라벨 명시 → verify: 화면에 문구 존재
- [ ] `strain_available=false` 면 변형률·에너지 선택지 감춤 (허구 값 금지)
      → verify: 해당 데이터셋에서 선택지 없음

## G6. 컨투어(리스크 맵)
- [ ] 군집 점·반경 → 커널 누적 격자 → verify: 단일 군집일 때 중심이 최대
- [ ] 리스크 값 가중 → verify: 약한 군집 다수 < 강한 군집 소수
- [ ] 개별 버블 ↔ 컨투어 전환 → verify: 두 모드 모두 JS 예외 0

## 마무리
- [ ] 실데이터 검증 (군집 있는 캠페인)
- [ ] 회귀 — 기존 sphere/deep 리포트 탭 JS 예외 0
- [ ] 오프라인 검증 (네트워크 차단)
- [ ] 커밋 분할 (G0~G6)
