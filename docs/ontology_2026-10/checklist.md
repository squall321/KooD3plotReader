# 체크리스트 — 해석 결과 온톨로지화

## 설계
- [x] 조사: DynaForge 온톨로지 모듈(정의 꼴 · 검증기 · DB · API · 시험 · 관례)
- [x] 조사: 후처리가 내는 사실(런별 · 각도 사이 · 에너지 흐름 · report.json · 단위)
- [x] 어휘 초안 v0 `dynaforge-cae.draft.json` — DynaForge 검증기 결함 0 · 주의 0(core 와 합쳐도 0)
- [x] 설계안 v0 `plan.md`
- [ ] 사용자 결정 4건(단위 · 세밀도 · 기본 산출 · DynaForge 작업 주체)
- [ ] DynaForge(kooremapper) · koo_sphere_report(a9) 와 범위 맞춤

## 구현 — KooD3plotReader
- [ ] 공용 모듈 koo_deep_report/ontology (어휘 사본 · 꾸러미 작성기 · 검증 · 단위 정규화)
- [ ] sphere 매핑 + 각도 사이 집계(포락 · 안전율 · 변동계수 · 하중 경로)
- [ ] contact_map 카드 이름 보존 · 에너지 흐름 단위
- [ ] impact · deep 매핑
- [ ] 시험(합성 · 실캠페인 · 리포트 수치 일치 · 크기)
- [ ] 각 리포트에서 ontology.json 산출 연결

## DynaForge (담당 결정 뒤)
- [ ] 어휘 채택 · 런타임 적재 · 시험 갱신
- [ ] 리포트 적재 때 꾸러미 upsert
- [ ] 질의 도구 · 화면
