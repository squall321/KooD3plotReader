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
- [x] **노드 로컬 `/opt/apptainers` 교체** (헤드·node001·node002)
      🔴 `deploy_from_sif.sh` 는 NFS(`/data/SmartTwinPostprocessor`)만 갱신한다.
      KooChainRun 자동 후처리(`DEFAULT_SIF_PATH`)와 smarttwin-tool(`STMC_POST_SIF`)은
      **노드 로컬** `/opt/apptainers/SmartTwinPostprocessor.sif` 를 쓰는데 그건 NFS 가
      아니라 같이 안 바뀐다. 2026-10-17 pykoocae-53 지적으로 드러났고, 직접 확인한
      결과 세 대 모두 이전 릴리스(601e9d86 = `3992a94`, 10/2)였다.
      → `.work/deploy_2026-10/deploy_nodes.sh` (백업 후 원자적 교체)
      → verify: 세 대 모두 `7142a658…`, 노드에서 VERSION `be9d2b0` ·
        capabilities 기준 7종/집계 3종 · Plotly 번들 3개 확인
- [x] pykoocae-53 에 배포 완료 통보 — VERSION·SIF sha256·tar 경로·verify 결과 전달
- [x] **저쪽 e2e 통과 — 요청서 대응 종결** (2026-10-17, pykoocae-53 보고)
      스택: Pre SIF v118(1147567e) · Post SIF 7142a658 · KooChainRun 493a86d · smarttwin-mcp 7dae7698
      · MCP `post_deep_report` (잡 1211): 46항목(max_shear 23 + x_tension 23), 군집 65개 전부
        `mean_timemax`, 부등식 위반 0/65, HTML 에 라벨 노출
      · KooChainRun 캠페인 (잡 1214): `scenario.postprocess.hotspot_criterion`/`_time_aggregate`
        → deep_report.sh 인자로 전달, 46항목·군집 58개·위반 0.
        **분석 단계까지만이다** — 시험 시나리오 time_limit 40분에 걸려 구역 뷰 16/23 파트에서
        TIMEOUT, HTML 은 안 나왔다. 핫스팟 탭 확인은 잡 1211 의 report.html 로 했다
        (저쪽 정정, 2026-10-17). 핫스팟 배선 판정에는 영향 없다 — 판정 근거인
        `analysis_result.json` 은 분석 단계에서 이미 완성된다
      · 대조군(잡 1212, 시간집계 기본): `mean_timemax` 0개 —
        "기본값이면 엔진 YAML 에 안 쓴다" 는 결정대로 동작
      · `max_shear` 의 `stress_mean` 이 두 실행에서 23/23 파트 동일 — 시간집계를 켜도 기존 값 불변
- [x] **§2 CLI 도 상류 배선 확인** (KooChainRun 493a86d) —
      `postprocess.sphere_viewer` → `--viewer`, `postprocess.hotspot_part` → `--hotspot-part`.
      prepare 가 생성한 `sphere_report.sh` 에 `--hotspot-part 1,2 --viewer plotly` 가
      박히는 것까지 저쪽에서 확인. **요청서 §1·§2 양쪽 모두 상류 연결 완료.**

## 배포 지점 전수 (2026-10-17 마감)
- [x] `/data/SmartTwinPostprocessor` (NFS) — headless `7142a658` / GUI `1a22ebe2`
- [x] 노드 로컬 `/opt/apptainers` — 헤드·node001·node002 전부 같은 두 판
- [x] `compute-node-images` (노드 재설치 원본) — 두 판 모두 교체됨
- [x] GUI 변종 — `672e835` 로 재빌드, %test(Plotly 검사 포함) 통과
- [x] 여섯 지점 sha256 직접 대조 — 전부 일치
- [x] **절차 보강** — `verify_deploy.sh --all-sites` 추가. 기준 SIF 의 **sha256** 을
      compute-node-images·헤드·노드 `/opt/apptainers` 와 대조한다
      → verify: 기본 경로 출력이 **바이트 동일**(상류 표준 빌드 영향 0),
      정상 상태 rc=0, 음성 대조 4종 전부 rc=1
      (원본이 다른 판 / 원본 없음 / 없는 노드 / SIF 인자 누락).
      GUI SIF 로도 동작. 지점은 `KOOD3PLOT_SITE_IMAGES`·`KOOD3PLOT_SITE_NODES` 로 조정
      ⚠ 기본 검사에는 **넣지 않았다** — 표준 빌드는 노드 배포 전에 이 도구를 부르므로
      기본에 넣으면 모든 빌드가 거기서 멈춘다 (상류 요청 2026-10-17)
- [x] **상류 독립 확인** — 698c693 으로 통합·단독 두 경로의 동기화 단계를 떼어 돌려
      둘 다 PASS. 임시 배포 결과가 호스트와 bin 11·lib 6·env.sh·VERSION·SIF 해시까지
      동일. 기본 검증 출력에 노드 줄 없음. 저쪽에서 돌린 `--all-sites` 도 헤드리스·GUI
      둘 다 네 지점 ✓ rc=0
- [ ] `compute-node-images` 를 **기본 검사**에도 넣을지 — 보류(사용자 판단).
      표준 빌드는 그 전에 이미 복사하므로 어느 쪽이든 영향 없음. 우리 단독 배포 때만
      '먼저 채워야 통과' 로 동작이 바뀐다
- [x] `deploy_from_sif.sh` 가 상류 공개 인터페이스가 됨 — 계약 셋을 머리말에 못박고
      실제 호출로 확인(인자 없음·없는 SIF 둘 다 exit 1)
- [x] 상류 `BuildSmartTwinPostprocessorOnly.sh` 패키지 목록 — 저쪽이 6개로 수정(확인함)
- [ ] **⚠ `BuildAll.sh` Phase 4 는 패키지 둘만 동기화 (미결, 상류)** — impact·federate·
      custom·scatter 넷이 옛 판으로 남는다. 통합 빌드로 Post 를 릴리스하지 말 것
