# 후처리 갭 대응 — 체크리스트

계획: [plan.md](plan.md) · 결정 기록: [context-notes.md](context-notes.md)

## P0. 진단이 거짓말하지 않게 ★먼저

### P0-1. 배포 tar 패키징 스크립트화 — 완료
- [x] `scripts/verify_package.sh` — 아카이브 독립 검증 도구 (기존 tar 에도 쓸 수 있게 분리)
- [x] `scripts/package_module.sh` — 배포 디렉토리를 묶고 **반드시** 검증, 실패하면 삭제
      → verify: VERSION 없는 디렉토리는 묶기 전에 거부, 아카이브 미생성
- [x] `--version-from <sif>` — SIF 안 `/opt/kood3plot/VERSION` 을 가져와 덮음
      → verify: 디렉토리 VERSION 이 `abc1234` 여도 아카이브는 `4815f55`
- [x] 아카이브 자기검증 6종 → verify: 정상 통과 / `unknown` 버전 / VERSION 누락 /
      lib 누락 / 최상위 2개 / 손상 tar — 6/6 의도대로
- [x] v29~v32 실물 재현 → verify: **v29 통과(eaffe54), v30·v31·v32 실패(VERSION 누락)**
      = 이번 사건의 재현 테스트

### P0-2. `unified_analyzer --capabilities` — 완료
- [x] JSON 출력 (tool/version/built/hotspot.{criteria,element_kinds,plastic_work,
      time_aggregate}/render.{lsprepost,section_view})
- [x] CMake 가 `git describe --tags --always --dirty` 를 빌드 시 주입
      → verify: `v2.4.0-233-gb86fe75-dirty` 출력, git 없으면 `unknown`
- [x] `allHotspotCriteria()` — 이름↔파서 **왕복으로 유도**, 손으로 적지 않음
      → verify: `tests/hotspot/test_capabilities.cpp` 10항목 전부 통과.
      목록 밖 enum 값(3..63)에 숨은 기준이 없음까지 확인
- [x] 광고 목록 == 실제 수용 집합 → verify: 실행 파일 JSON 의 3개 이름을 별도
      바이너리로 파싱해 정규 이름이 그대로 돌아옴 (교차 확인)
- [x] d3plot 없이 동작 → verify: 인자 없이 `--capabilities` exit 0

### P0-3. 산출물 버전 각인 — 완료 (deep 까지)
- [x] `Version::build_commit()` / `build_date()` — `src/Version.cpp` 로 분리
      (헤더 인라인에 매크로를 걸면 ODR 위반)
- [x] `analysis_result.json > metadata.tool_commit` / `tool_built`
      → verify: 실해석에서 `v2.4.0-234-g7d8a75d-dirty` / `2026-09-13T11:31:33Z`,
      `--capabilities` 의 version 과 **일치**
- [x] 기존 `kood3plot_version` 은 그대로 둔다 — 계속 `1.0.0` 이라 구분이 안 되지만
      읽는 쪽(HTML)이 있어 깨지 않는다. 새 필드를 병기
- [x] 없으면 키를 만들지 않는다 → verify: 옛 산출물이면 JSON 키 없음
- [x] deep report 푸터 → verify: 있으면 `빌드 | 커밋 · 시각`, 키를 지우면 줄 자체가
      사라짐, `tool_built` 만 없으면 커밋만 표시 (3경우 확인)
- [x] sphere — 런마다 다른 빌드로 분석됐는지까지 드러낸다
      → verify: 섞임 `⚠ builds: <커밋>(1), 기록 없음(3)` / 전부 같음 `build <커밋>` /
      기록 전무 시 아무것도 적지 않음. 1144각도 기존 리포트 회귀 없음
- [ ] impact / federate / custom 푸터 — 구조가 제각각이라 별도 (P0-6)

### P0-4. 배포 검증 스크립트 — 완료
- [x] `scripts/verify_deploy.sh <경로|sif> [...]` — VERSION ↔ `--capabilities` 대조
- [x] 디렉토리와 SIF 를 둘 다 받고, **대상 간에도** 대조 (호스트 vs SIF 가 이번 사건 형태)
- [x] 재현 테스트 → verify: 현재 배포본에서 **실패 3건** —
      호스트 `eaffe54` / SIF `4815f55` 불일치가 자동으로 드러남
- [x] 통과·실패 5경우 → verify: 일치 0 / VERSION 만 낡음 1 / VERSION 없음 1 /
      경로 없음 1 / 두 대상 같은 판 0
- [x] `set -u` 빈 배열 참조 버그 수정 (카운터로 대체)

### P0-5. 배포 — P1·P2 까지 쌓고 한 번에 (2026-09-13 사용자 결정)
- [ ] main 에 push (SIF def 가 GitHub main 을 clone 하므로 필수)
- [ ] SIF 재빌드 → node001 배포 → `verify_deploy.sh` 통과
- [ ] `package_module.sh` 로 v33 tar 생성 → `verify_package.sh` 통과
- 참고: P0 검증 도구는 리포지토리에서 바로 쓸 수 있어 배포 전에도 효력이 있다

## P1. 조용히 틀리는 물리 경로

### P1-1. top_percent 독립 절대량 — 완료
- [x] `SinglePassAnalyzer::plasticStrainMax()` — 요소별 ε_p **이력 최댓값**
      (솔리드·셸·두꺼운 셸). 소성일과 조건이 달라 상태 1개짜리 덱에서도 기록
- [x] 파트 단위 `n_yield` / `vol_yield` / `vol_total` / `sum_eps_vol` / `max_eps` /
      `plastic_work_total` — **상위 백분위로 자르기 전에** 파트 전체로 집계
- [x] `yield_eps_threshold` 설정 (기본 0 = ε_p>0 이면 소성)
- [x] 없으면 키를 만들지 않는다 (`plastic_zone_available` / `plastic_work_available`)
- [x] 셸이 면적 가중이면 `plastic_work_total` 을 내지 않는다 (단위 불일치)
- [x] top_percent 독립성 → verify: `3%` vs `5%` 에서 **파트 절대량 34/34 동일**,
      선별 요소 수 30/34·클러스터 volume 합 21/34 달라짐
- [x] 독립 검증 → verify: d3plot 을 직접 읽는 별도 프로그램과 **5/5 항목 상대오차 0**
      (part 100: n_yield 1150, vol_yield 13089.06761, sum_eps_vol 0.01029100171,
      max_eps 8.689126844e-06)
- [x] 항등식 → verify: `vol_yield ≤ vol_total`, `n_yield ≤ element_count_total` 위반 0건
- [x] `--capabilities` 에 `plastic_zone: true` 반영
- [x] **기존 결함 동반 수정** — `jnum` 이 `fixed<<setprecision(8)` 이라 소수점 8자리에서
      잘렸다. ε_p(1e-6)는 유효숫자 3자리만 남고 1e-9 이하는 `0.00000000` 이 되어
      진짜 0 과 구분되지 않았다 → 유효숫자 10자리(defaultfloat)
      → verify: `4.347530478e-07` (이전 `0.00000043`), JSON 파싱 정상, 리포트 회귀 0

### P1-2. 시간 집계 옵션
- [ ] `--hotspot-time-aggregate {elemmax_then_mean|mean_then_timemax|both}`
      → verify: 모든 군집에서 `mean_then_timemax ≤ elemmax_then_mean`

### P1-3. 기준량 잔여
- [ ] `max_shear = (σ1−σ3)/2` → verify: 단축 인장에서 `σ_vm/2`
- [ ] `x_tension` — 축 지정 방식 설계 후 구현
- [ ] `--capabilities` 목록에 자동 반영 → verify: P0-2 테스트가 새 이름을 잡음

## P2. 오보를 낸 통계 경로

### P2-1. 공통 DOE 교집합
- [ ] `--common-doe-only` 기본 ON
- [ ] 표본수 · 제외 DOE · 미완주 과제 명시
- [ ] 교집합 임계 미달이면 비교 거부
      → verify: 33런 미완주 과제를 섞으면 거부 + 사유에 과제명

### P2-2. 통계 검정 유틸
- [ ] 평균순위 검정 — 귀무 `(N+1)/2` **코드 고정**
- [ ] Spearman ρ → verify: `scipy.stats.spearmanr` 와 일치
- [ ] recall@k, 편차각 구간 프로파일
- [ ] 산출물에 사용한 귀무가설 명시
      → verify: 균일난수 1000회에서 p 분포가 균일

## P3. 캠페인 그릇
- [ ] `koo_scatter_report` 신설
- [ ] `runner_config.postprocess.auto_scatter` 훅
- [ ] `campaign_metrics.parquet` 롱포맷

## P4. 나머지
- [ ] A-4 `--hotspot-source {d3plot|elout}`
- [ ] A-5 `--segment-boxes segments.json`
- [ ] A-6 `metadata.coordinate_transform`
- [ ] B-1 면 기준 편차각 `dev_roll`/`dev_pitch`/`dev_angle`
- [ ] B-5 ground truth 스키마
- [ ] C 그림 9종

## 마무리
- [ ] 갭 문서 작성자에게 A-1 정정 회신 (이미 구현·배포됨 + 원인)
- [ ] 회귀 — 기존 리포트 5종 JS 예외 0
