# 체크리스트 — 해석 결과 온톨로지화

## 설계
- [x] 조사: DynaForge 온톨로지 모듈(정의 꼴 · 검증기 · DB · API · 시험 · 관례)
- [x] 조사: 후처리가 내는 사실(런별 · 각도 사이 · 에너지 흐름 · report.json · 단위)
- [x] 어휘 초안 — DynaForge 검증기 결함 0 · 주의 0(core 와 합쳐도 0)
- [x] 설계안 `plan.md`, 꾸러미 계약 `package-contract.md`
- [ ] 사용자 확인 — 권장안 4건으로 진행했다(plan.md §7)
- [x] koo_sphere_report(a9) 와 범위 맞춤 — 사후 읽기라 겹치지 않음, 캐시 결함 · 화면 안전율 고침(2eeb7c0)
- [ ] DynaForge(kooremapper) 검토 · 채택

## 구현 — KooD3plotReader
- [x] 공용 모듈 koo_deep_report/ontology (어휘 정본 · 꾸러미 작성기 · 검증 · 단위 정규화)
- [x] sphere 어댑터 + 각도 사이 집계(포락 · 안전율 · 변동계수 · 하중 경로)
- [x] contact_map 카드 이름 보존
- [x] impact · deep 어댑터, deep 리포트가 ontology.json 을 함께 쓴다
- [x] 시험 — 합성 27건 · post_analyze [12] 8건 · 실데이터 대조(v14 · Test_Impact_A · 핫스팟 런)
- [x] post_analyze 마지막 단계 · koo_ontology 래퍼 · SIF %test
- [ ] SIF 재빌드 · 배포 (상류 표준 경로)
- [ ] sphere report.json 에 런 끝 시각 · 분석기 커밋 · 소견 파트 번호 (a9 가 하기로)

## DynaForge (담당 결정 뒤)
- [ ] 어휘 채택 · 런타임 적재 · 시험 갱신
- [ ] 리포트 적재 때 꾸러미 upsert
- [ ] 질의 도구 · 화면
