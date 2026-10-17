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
- [ ] push (PR #2 자동 종료 확인)

## 2. hotspot-cluster 검증
- [ ] 타 필드 불변 — 군집 켜고/끄고 돌려 나머지 필드 전수 대조
- [ ] 실덱 육안 대조 — 군집 위치 vs 단면 뷰
- [ ] 성능 — 요소 수십만 덱에서 켜고/끄고 시간 비교

## 3. impact V5·V6
- [ ] V5 — 배포본 SIF 안에서 Test_Impact_A 실행·시간·배지·Finding 확인
- [ ] V6 — pyKooCAE probe 연동 (상류 협의)

## 4. custom_report
- [ ] KooChainRun 통합 실전 확인 (상류 의존 — 가능 여부부터)
