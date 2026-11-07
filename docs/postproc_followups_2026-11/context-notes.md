# 컨텍스트 노트 — 후처리 후속 4건

## 출발 (11-07)
- 사용자가 「더 개발해야 하는 거」 목록에서 네 가지 모두 골랐다. 앞 작업은 docs/report_figures_2026-11.
- 확인한 사실: 소프트웨어 단면은 state_step 키가 없다(SectionViewConfig.cpp 에 없음, iso_surface 만 max_frames). 온톨로지
  package.py 에 머리 warnings 가 없다.
- DynaForge 제안 원문은 대화 기록에서 못 찾았다 — 앞선 요약의 「꾸러미 머리 `warnings`, test_dir · 덱 · DropSet 을 못 읽을 때」
  를 따르고 DynaForge 검사기로 통과를 확인한다.
- v45(5e589fb) 빌드 중 — push 는 빌드 완료 알림 뒤.

## 1. 소프트웨어 단면 상태 간격 (11-07)
- section_views YAML `state_step`(1 이면 키 없음) → SectionViewConfig.state_step → 2D · 3D · iso 세 경로가 같은 「그릴 상태 목록」
  (0, N, 2N …). 프레임 파일은 순번으로 짓는다(상태 번호로 지으면 ffmpeg 순번이 끊긴다). 색 범위(global_range)도 그리는 상태들로.
  iso 의 max_frames 가 있으면 그쪽이 우선. `[설정]` 경고는 지웠다.
- 실측(Test_006, z, 타겟 17): 전 상태 992 프레임 · 41.3 s 영상 · 분석기 189 s → 보폭 20 이면 50 프레임 · 2.1 s · 20 s.

## 2. 메모리 — 전제가 틀렸다 (11-07)
- 실측(Test_006, 분석기 직접, /usr/bin/time): 분석만 6,680 MB · 분석 + 소프트웨어 단면(보폭 20) 6,680 MB · (전 상태) 6,680 MB.
  **소프트웨어 단면은 메모리를 더 쓰지 않는다.** 메모리는 분석기가 분석용으로 상태를 통째로 읽는 데서 나온다
  (UnifiedAnalyzer.cpp:77 read_all_states_parallel — 상태당 약 6.7 MB). v14(4,952 상태)면 약 33 GB — 단면을 꺼도 deep 분석이 그만큼 쓴다.
- 고치려면 분석기를 흘려 읽기(for_each_state 는 있다)로 개편해야 한다 — all_states 를 UnifiedAnalyzer 57곳 · SinglePassAnalyzer 51곳에서
  쓴다. 값 회귀 위험이 큰 일이라 사용자에게 범위를 다시 묻는다(큰 개편 / 읽기 전 메모리 어림 · 분명한 경고 / 보류).

## 3. 온톨로지 머리 warnings (11-07)
- `Package.warn()` → 머리 `warnings: [사유 …]`(사유가 있을 때만 — 「값이 없으면 키를 뺀다」 규약). 사유: sphere — test_dir 없음 · 못 찾음,
  덱(.k) 못 찾음 · 못 읽음, DropSet.json 못 읽음 / impact — 덱 못 찾음 · 못 읽음 / deep — 덱 못 찾음 · 못 읽음, binout 이 있는데 흐름 실패.
  binout 이 없어 흐름이 없는 것은 실패가 아니라 싣지 않는다.
- **DynaForge 검사기(KooRemapper platform/backend/app/reports/onto_package.check)가 이미 머리 warnings 를 받는다**(167행, 문자열 목록을
  자기 경고에 이어 붙임). 경고가 실린 sphere 꾸러미를 넣어 통과 · 사유가 그대로 보이는 것을 확인했다.
