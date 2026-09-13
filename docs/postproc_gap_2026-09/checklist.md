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

### P0-3. 산출물 버전 각인
- [ ] `analysis_result.json > metadata.tool_version {version, built, capabilities_hash}`
- [ ] deep / sphere / impact HTML 푸터
      → verify: 서로 다른 두 빌드 산출물에서 값이 다름

### P0-4. 배포 검증 스크립트
- [ ] `scripts/verify_deploy.sh <경로>` — VERSION ↔ `--capabilities` version 대조
- [ ] 호스트 경로와 SIF 안을 둘 다 확인
      → verify: 현재 `/data/SmartTwinPostprocessor` 에서 **실패** (eaffe54 vs 4815f55)

### P0-5. 9/13 소성일 배포
- [ ] SIF 재빌드 → node001 배포 → P0-4 통과

## P1. 조용히 틀리는 물리 경로

### P1-1. top_percent 독립 절대량
- [ ] 파트 단위 `n_yield` / `vol_yield` / `sum_eps_vol` / `max_eps` / `plastic_work_total`
- [ ] ε_p 는 이력 최댓값 사용 (단조 가정 금지 — 실덱에서 감소 확인됨)
      → verify: `--hotspot-top-percent 3` vs `5` 에서 **파트 절대량 동일**,
      클러스터 종속량(`volume`/`energy_total`)은 달라짐
- [ ] `energy_total` 이 top_percent 종속임을 리포트에 명시 (또는 파트 절대량 병기)

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
