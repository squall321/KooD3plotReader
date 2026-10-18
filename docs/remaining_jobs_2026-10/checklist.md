# 남은 잡 — 체크리스트

## 1. PR #2 (DynaForge export)
- [x] 브랜치 머지 — 충돌 7곳 해소. main 규약(round_keep_sig·극값보존·키생략) 유지 +
      PR 의 새 키를 그 규약에 맞춰 얹음. 자동 병합된 `_series_payload` 가 옛 규약이라
      같이 고침(안 그러면 신규 시계열 5종만 회귀)
- [x] 시험 — 120개 통과. 신규 6건은 옛 규약에서 4건 FAIL (헛돌지 않음을 확인)
- [x] 실덱 — Test_001 442파트에서 `peak_plastic_strain` 390개·값 일치,
      `g_ts.max`/`disp_ts.max` 390/390 일치, 불일치 0.
      σ1·ε 시계열은 어느 캠페인에도 CSV 가 없어 미확인(요청서가 짚은 '분석 잡 미실행')
- [x] 브라우저 회귀 — 탭 17개, JS 예외 0, 외부요청 0
- [x] push — 머지커밋 3e02720, 브랜치가 main 의 조상이 되어 PR #2 가 닫힌다
- [x] (곁다리) σ1·σ3 시계열이 실데이터로 나오는 것 확인 — 분석을 `csv: true` 로 돌리면
      `principal_ts` 23개(최대 358.0) · `principal_min_ts` 에 압축측 `min`(−270.7).
      ε 계열 3종은 변형률 텐서(STRFLG)가 필요해 이 덱엔 없다

## 2. hotspot-cluster 검증  ✅ 완료
- [x] 타 필드 불변 — 전 필드 재귀 대조, 차이는 `analysis_date` 2초뿐.
      **이 대조가 결함을 잡았다** — 군집을 꺼도 `hotspot_clusters: []` 가 나갔다 (65ab673 수정)
- [x] 실덱 대조 — 값·시각·피크요소 ID 완전 일치 + lasso 독립 계산 6/6.
      육안 대조는 한계가 있었다(절단면이 군집을 비켜가고, 피크가 요소 1개)
- [x] 성능 — 45,457 솔리드·400상태 1.01초 → 1.41초 (+38%). '수십만' 덱은 이 머신에 없다

## 3. impact V5·V6
- [ ] V5 — 배포본 SIF 안에서 Test_Impact_A 실행·시간·배지·Finding 확인
      ⚠ 1차 시도가 죽었다 — 기본 `parallel_runs=16 × threads 2` = 32 동시 읽기.
      가용 메모리 23GB(VM·cpptools 점유)에서 OOM. `--parallel-runs 4 --threads-per-run 2`
      로 재실행 중 (기억의 'max 2 threads' 권고와 같은 맥락)
- [ ] V6 — pyKooCAE probe 연동 (상류 협의)

## 4. custom_report
- [x] **KooChainRun 경유 — 해당 없음** (상류 회신 2026-10-18).
      pyKooCAE Runner 전체에 custom_report 참조 0건이고 그런 postprocess 키가 없다.
      부르려면 KooChainRun 에 새 키(auto_custom 등)가 필요하다 — 신규 기능이라
      상류가 사용자께 문의 중. 우리 쪽에서 더 할 일은 없다
- [x] 배포본 단독 실행 확인 (2026-10-18) — SIF 안에서 rc=0,
      `set_reports/Seg_1/metrics.json`(set_type=segment·metric_source=segments·
      resolved_parts·missing_parts·fields·highlights) + HTML + 미디어 2개
      덱: `/data/Tests/Test_001_Full26_1Step/MinimumModel.k` (*SET_SEGMENT 50개)
- [ ] MCP `post_custom_report` 경유 확인 — 상류가 노드 잡으로 돌려 주기로 함.
      재료(캠페인·덱·세트 YAML) 전달 완료
