# 후처리 후속 4건 — 계획 (2026-11-07)

**요청(사용자)** 리포트 그림 작업 뒤 남은 개발 거리 중 네 가지를 모두 한다 — 소프트웨어 단면 상태 간격 · 소프트웨어 단면 메모리 ·
온톨로지 꾸러미 머리 warnings · 옛 산출물 그림 채우기와 sphere 연결.

## 1. 소프트웨어 단면 상태 간격
- 지금: `--section-view-state-step` 은 LS-PrePost 만 쓴다(`anim incr N`). 소프트웨어(7-1 백엔드)는 전 상태를 그린다 — 992 상태면
  41 s 영상, 렌더 수 분. 경고만 낸다(`[설정]`).
- 할 일: section_views YAML 에 `state_step`, SectionViewConfig 가 읽고 렌더러가 0, N, 2N … 만 그린다(마지막 상태 포함 여부는
  LS-PrePost 와 같게 — 상태 0, N, 2N …). 경고를 지운다. 색 범위(global_range)는 그리는 상태들로.

## 2. 소프트웨어 단면 메모리
- 지금: 분석기가 상태를 모두 메모리에 올린 채 단면 렌더러에 넘긴다(v14 4,952 상태에서 가용 6% → earlyoom).
- 할 일: 먼저 어디서 얼마나 쥐는지 잰다(코드 경로 + 실측). 그다음 단면 렌더가 필요한 상태만(1 의 보폭) 필요할 때 읽게 바꾼다.
  분석(응력 이력 등) 결과는 바뀌면 안 된다 — 시험 · 실데이터로 대조.

## 3. 온톨로지 꾸러미 머리 warnings
- DynaForge 제안(10-31 채택 회신): test_dir · 덱 · DropSet 을 못 읽으면 꾸러미 머리 `warnings` 에 사유를 싣는다(지금은 조용히 빈 값).
- 할 일: sphere · impact · deep 어댑터에서 읽기 실패를 모아 머리에 싣고, DynaForge 검사기(app/reports/onto_package.check)로 통과 확인.

## 4. 옛 산출물 그림 채우기 + sphere 연결
- 지금: 「최신이면 건너뜀」 이라 옛 deep 산출물엔 그림이 없다. `koo_deep_report figures pack` 은 figures/ 만 만들고 HTML 탭은 없다.
  캠페인 그림은 `<test_dir>/figures/` 에 있지만 sphere 리포트 HTML 에서 닿는 길이 없다.
- 할 일:
  - `figures pack --update-html` — 산출물에서 결과를 다시 엮어 report.html 을 그림 탭과 함께 다시 쓴다(분석기는 다시 안 돈다).
  - post_analyze 가 건너뛴(최신) deep 산출물에 그림이 없으면 위를 부른다(--no-figures 면 안 함).
  - 캠페인 그림 폴더에 독립 갤러리 `figures/index.html`(PNG 격자 + 누르면 호버 SVG), sphere 리포트 HTML 에 그 링크를 끼운다
    (표지 주석 사이만 갈아 끼워 여러 번 돌려도 하나).

## 순서 · 배포
1 → 2(1 의 보폭이 메모리도 줄인다) → 3 → 4. v45 빌드가 끝난 뒤 push, 다음 배포(v46)에 싣는다. 사용자 승인 후 상류 표준 경로.
