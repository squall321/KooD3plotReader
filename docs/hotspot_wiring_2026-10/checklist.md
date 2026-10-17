# 핫스팟 배선 — 체크리스트

## 준비
- [x] 요청서 커밋 (f085359)
- [x] 결함 재현 — `--hotspot-criterion max_shear` rc=1 (로컬, case_01)
- [x] 이름 확정·pykoocae-53 에 통보 (제안 그대로)

## 구현
- [x] 기준 7종 + 엔진과 같은 별칭, capabilities 에서 허용 목록 읽기 → verify: 단위 시험
- [x] `--hotspot-time-aggregate` CLI + YAML → verify: 엔진 YAML 에 `time_aggregate:` 방출
- [x] YAML `criteria` 블록 목록 → verify: 3형식 모두 같은 결과
- [x] 검증을 분석 전으로 (single·batch) → verify: 잘못된 이름이 glstat 읽기 전에 rc≠0
- [x] HTML 라벨·짝 변형률 라벨·`mean_timemax` 열 → verify: 브라우저 JS 예외 0
- [x] `--help` 갱신 + `docs/hotspot-cluster-usage.md`

## 검증
- [x] 새 시험이 수정 전 코드에서 FAIL — 옛 코드로 블록 목록·max_shear·time_aggregate 3동작 실패 확인
- [x] 기존 시험 전부 통과 — 84 passed (기존 66 + 신규 18)
- [x] e2e (case_01) — 두 기준 항목·`mean_timemax`·HTML
- [x] 새 기준 값 독립 대조 (lasso 60건, 3.5e-10) · `mean_timemax` 는 멤버 미노출로 불변식만

## 배포 (2026-10-17)
- [x] 커밋·push — origin/main `be9d2b0` (§2 3D 인벨롭 G1~G6 도 같이 올라감)
- [x] Post SIF 빌드 — `--fakeroot`, %test 통과(Plotly 번들 3개 존재 검사 포함).
      시작 통보 완료, 그쪽이 빌드 대기 회신
- [x] `deploy_from_sif.sh` → 호스트·SIF 모두 `be9d2b0`, 래퍼 6개 환경변수 없이 실행,
      node001 `be9d2b0` + SIF sha256 호스트와 동일(NFS 공유)
      SIF sha256 `7142a658c67ec4b8e0460537…`
- [x] tar — `SmartTwinPostprocessor_20261017_v39.tar.gz` (524M), 검증 통과
- [x] 배포본으로 요청서 verify 재실행 — `.work/deploy_2026-10/verify_request.sh`
      `--hotspot-criterion max_shear,x_tension --hotspot-time-aggregate both` rc=0,
      JSON 에 두 기준(max_shear 6 · x_tension 7), `mean_timemax` 60군집·불변식 위반 0,
      모르는 기준은 즉시 rc=1 로 거절, HTML 7.2MB 생성
      §2 도 배포본으로 확인 — sphere canvas/plotly·프리셋·deep 폐쇄망 전부 PASS
- [ ] pykoocae-53 에 배포 완료 통보
