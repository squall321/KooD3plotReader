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

## 4. 옛 산출물 그림 + sphere 연결 (11-07)
- **HTML 을 다시 짓지 않는다** — 옛 deep 산출물의 report.html 을 SingleResult 로 다시 엮어 쓰면 그때 준 옵션(--yield-stress · 설계 기준
  덮어쓰기 등)을 몰라 안전율이 바뀌거나 접촉 탭이 빠진다. 대신 그림 폴더마다 독립 갤러리 `figures/index.html`(PNG 격자 · 누르면 호버
  SVG · 차트 · 알림, 외부 라이브러리 없음)을 쓰고, 기존 HTML 에는 표지 주석(`kood3plot.figures:begin/end`) 사이의 고정 버튼만 끼운다
  (다시 돌려도 하나, `</body>` 앞).
- `koo_deep_report figures pack <폴더> --link-html`(옛 산출물 채우기), `figures campaign` 은 report.json 옆 sphere HTML(같은 이름 줄기)에
  기본으로 링크(`--no-link-html`). pack · campaign 모두 index.html 을 쓴다(_OURS 정리 대상).
- 실데이터(사본): v14 옛 deep 산출물(2026-09, 그림 탭 없음)에 스냅샷 11 · 차트 7 + 링크, Test_006 sphere 리포트(7.3 MB) 사본에 링크 ·
  갤러리 3장 · 차트, 크로미움에서 버튼 · 갤러리 · 모달 SVG 확인(오류 0).
- **post_analyze 자동 채우기는 보류** — v45 굽기 중 배포 세션이 apptainer/ · scripts/ 를 작업 트리에서도 바꾸지 말아 달라고 했다
  (def · build.sh · deploy_from_sif.sh 를 작업 트리에서 읽는다). 굽기 완료 알림 뒤에 붙인다.

## 2. 메모리 안전장치 (11-07, 사용자 결정 「안전장치만」)
- UnifiedAnalyzer::analyze 가 전 상태를 읽기 직전에 어림한다 — 상태 하나 = 헤더 워드 수(1 + NGLBV + NND + ENN + DELNN, StateDataParser
  와 같은 셈) × 8 바이트, × 상태 수 × 1.1. 가용 = /proc/meminfo MemAvailable 과 자기 cgroup 한도(v2 memory.max − current, v1 limit −
  usage, /proc/self/cgroup 경로) 중 작은 것. 넘으면 숫자와 함께 실패(분석기 rc 1 · 그것을 부른 deep 은 rc 3, 「Analysis failed: 메모리 부족 예상으로 멈춘다 — …」),
  70% 넘으면 경고. `KOOD3PLOT_MEMORY_CHECK=warn` 경고만 · `off` 안 봄.
- **함정**: 처음엔 상태 0 을 `reader.read_state(0)` 로 읽어 크기를 쟀는데, read_state 는 첫 호출에서 **전 상태를 리더 캐시에 올린다** —
  뒤의 전 상태 읽기와 합쳐 두 벌(Test_006: 6.7 → 13.6 GB, 27 → 212 s). 헤더 셈으로 바꿔 원래 수준(6.84 GB)으로 돌아왔다.
- 실측: 상한 4 GB scope(systemd-run MemoryMax=4G)에서 「상태 992개 × 7.0 MB ≈ 7.5 GB 필요, 가용 4.0 GB」 로 바로 멈춘다(분석기 직접 실행, rc 1).
  어림 7.0 MB/상태 ≈ 실측 6.7 MB/상태. 평소 조건은 경고 없이 통과.

## 4 마감 — post_analyze 자동 채우기 (11-07, v45 배포 뒤)
- run_step_deep 이 최신이라 건너뛴 산출물에 figures/manifest.json 이 없으면 `koo_deep_report figures pack <산출물> --d3plot <d3plot>
  --link-html` 을 부른다(분석 다시 안 돎, HTML 은 링크만). `--no-figures` · 옛 SIF(figures 명령 없음)면 안 한다. 요약 줄에 채운 수.
- 셸 시험 [14] 6개. [13] 의 「--deep-only 면 부르지 않는다」 는 `figs` 줄 전부를 세던 것을 `figs campaign` 만 세게 좁혔다
  (뜻은 캠페인 그림 단계 여부 — 새 채우기 호출이 섞였다).
- v45(5e589fb) 배포 완료(11-07, 배포 세션) — 단면 _zoom 이 더는 안 생기고 나머지 영상은 v44 와 md5 같음.

## v46 배포 · 확인 (11-07)
- 배포 세션(pykoocae-53)이 229806e 를 굽고 네 곳에 깔았다 — 헤드리스 bbd1d1dc · GUI 96659d89, 빌드 원본 · /data · compute-node-images ·
  헤드 /opt 동일, tar v46. 헤드 /opt 의 v45 는 `*_backup_20261107_062425.sif`. 노드(node001 · 002)는 down 이라 아직 옛 판.
- 이쪽에서 헤드 /opt SIF 를 `--no-home`(노드처럼 호스트 홈 없이)으로 다시 돌렸다(`.work/followups/v46_check.sh`).
  - a: sha256 bbd1d1dc · VERSION 229806e.
  - w: Test_006 report.json 사본 + 빈 test_dir → 객체 20632, warnings 두 줄(덱 못 찾음 · DropSet 못 읽음).
  - m: 사용자 scope MemoryMax=4G(sudo 없이 `systemd-run --user --scope`, user@ 에 memory 위임됨)에서 deep rc 3 ·
    「상태 992개 × 7.0 MB ≈ 7.5 GB 필요, 가용 3.9 GB」 · Killed/oom 0. 가용이 4.0 보다 작은 것은 memory.max − current(deep 파이썬 몫).
    **deep 의 rc 3 은 분석기 실패 일반**(__main__.py 의 `except RuntimeError → sys.exit(3)`) — 분석기 자체는 rc 1. v45 는 같은 조건에서
    커널 cgroup OOM 이 분석기를 4.1 GB 에서 죽여 deep 로그에 사유 없이 rc 3 이었다(배포 세션 대조).
  - s: 상태 간격 20 → 50 프레임 · 2.084 s · [설정] 경고 0 · 최대 RSS 6.85 GB(경과 46 s, 분석 포함). v45 는 992 프레임 · 41.3 s · 경고 2.
  - f: v14 옛 deep 산출물 사본에 `figures pack --link-html` 두 번 — 둘 다 rc 0 · 표지 1 · index.html 1, 「스냅샷 11장 · 차트 7개 ·
    대상 파트 [21, 1, 20, 2, 12] · 알림 1건」, manifest 18 · 판 229806e · 바닥 [23] 숨김 알림.
  - c-1(배포 세션): deep --no-render 그림 18 · index.html 1 · 꾸러미 warnings 키 없음 · 최대 RSS 6,840,652 kB(v45 6,840,720 — 캐시 함정 없음).
    a9 sphere 회귀도 통과(사이드카 바이트 동일, 덱 없는 캠페인에서 warnings 1건).
