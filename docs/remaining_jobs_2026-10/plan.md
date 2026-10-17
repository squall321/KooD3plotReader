# 남은 잡 정리 — 2026-10-17

전수 조사로 추린 미결을 한 번에 닫는다. 조사 근거는 `context-notes.md` 참조.

## 1. 🔴 PR #2 — DynaForge export 요청 (유일한 **외부 요청** 미결)

브랜치 `docs/dynaforge-sphere-data-export-request` 4커밋이 main 에 없다. 작업은
2026-09-04 에 끝났는데 머지가 안 됐고 그 뒤 main 이 211커밋 나갔다. **지금 배포본에
그 데이터가 안 나간다** — main 에 `peak_plastic_strain`·`principal_ts`·`vm_strain_ts` 0건.

- 내용: 스키마 호환 키(별칭) + σ1·σ3·ε1·ε3·ε_vm 시계열 5종 + 시계열 탭 가용성 필터
- 파일: `json_report.py`(+58) · `html_report.py`(+123) · 요청서 문서(신규)
- 충돌 2곳 예상 — `html_report.py` 는 이번 분기에 가장 많이 고친 파일이다
- **머지로 올린다**(리베이스 아님) — 브랜치 커밋이 main 의 조상이 돼야 PR #2 가 닫힌다

## 2. hotspot-cluster 검증 3건 (자체 숙제)

- 기존 `analysis_result.json` 타 필드 불변 증명 (군집 기능이 필드만 더했는지)
- 실덱 — 단면 뷰 컨투어와 육안 대조
- 성능 — 요소 수십만 규모에서 분석 시간 증가폭

## 3. impact-sota V5·V6

- V5: Test_Impact_A 실데이터를 **SIF 안에서** (≤6s, 배지 PASS 다수, Finding>2)
- V6: pyKooCAE probe 연동 — 상류 협의 필요

## 4. custom_report — KooChainRun 통합 실전 확인 (상류 의존)

## 범위 밖
- `BuildAll.sh` Phase 4 (상류 소관, pykoocae-53 이 사용자에게 보고함)
- `compute-node-images` 기본 검사 포함 — 사용자가 "됐다" 고 함
