# 남은 잡 — 체크리스트

## 1. PR #2 (DynaForge export)
- [ ] 브랜치 머지 — 충돌 해소 (`html_report.py`·`json_report.py`)
- [ ] 시험 통과 + 새 키가 실제 산출물에 나오는지 실덱 확인
- [ ] 브라우저 회귀 — 시계열 탭 JS 예외 0
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
