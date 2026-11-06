# 체크리스트 — 리포트 그림 꾸러미

## 계획
- [x] 현황 조사 — deep 렌더 · 단면 카메라 · `_zoom.mp4` · 옛 계획 문서
- [x] SIF 도구 확인 — VTK · pyvista · lasso · Xvfb 있음, SVG→PNG 변환기 없음
- [x] 시안 — v14 최대 응력 상태 하나 읽기 · 바깥 면 · 반투명 · 바닥 숨김 · 맞춤 · 강건한 색 범위
- [x] 조사 결과 반영(C++ 재사용 · LS-PrePost 반투명 · HTML 갤러리 · SVG 도우미 · 자동화 플래그)
- [x] 사용자 결정 — 기본 산출 · 상위 5 · jet · 1~4단계 한 번에

## 1단계 — 스냅샷 엔진
- [x] 읽기(lasso, 한 상태) · 파트 이름 · 시각 → 상태 번호(이력 순번, 잘림 · 점 수 불일치는 거절)
- [x] 바깥 면(파트별, 오면체 · 사면체 · 셸 · 삭제 요소)
- [x] 값(von Mises, 파트 모든 요소 최대) — analysis_result 파트 최대와 대조(v14 5/5 일치, 시험)
- [x] 바닥 자동 감지 + `--hide-parts`
- [x] 카메라(평행, iso · 최대점 시점, 투영 크기 맞춤, 범례 자리)
- [x] PNG(pyvista · Xvfb 빈 화면 번호, 두 겹 — 타겟 맨 위)
- [x] SVG(직접 투영 · 깊이 순서 · 음영 · 호버 스크립트 · `<title>` 폴백 · 화면 밖 면 버림)
- [x] 합성 시험 + 실데이터 대조(tests/test_figures.py 26개)

## 2단계 — 그림 꾸러미
- [x] overview · 상위 N 파트 · 에너지 · 파트 요약 · 이력(응력 + 가속도 G) 그림
- [x] manifest.json(kood3plot.figures v1)
- [x] deep 연결(기본 켬, 단일 · 배치) · HTML 「리포트 그림」 탭 · CLI `python -m koo_deep_report.figures pack|snap`
- [x] SIF 안에서 돌기 — v43 SIF 에 개발 소스를 묶어 꾸러미 · deep 경로 모두 통과(DejaVu 만 — 제목 문장부호 보존 수정)
- [x] post_analyze · 7-1 길 — 둘 다 deep 단일 모드라 기본으로 나온다(옛 산출물은 「최신이면 건너뜀」 — `koo_deep_report figures pack` 으로 채움)

## 3단계 — LS-PrePost 영상 보완
- [x] `--hide-parts` / `--hide-floor` — LS-PrePost(`-M`) · 소프트웨어 모두, 실렌더 확인
- [ ] `--view-fit target` / `--view-margin`
- [x] 타겟 지정만으로 파트별 단면(분석 대상 안 좁힘) · 무시 옵션 `[설정]` 경고 · 3-상태 결함

## 4단계 — sphere 최악 방향 그림
- [x] 파트별 최악 런 고르기 · 그림 · manifest(scope=campaign) — `koo_deep_report figures campaign`
- [x] post_analyze 단계(sphere 다음, deep 앞) · `--no-figures` · 셸 시험 [13]
- [x] 실데이터 Test_006(1144 런) — 11.4 s, 옛 CSV 값 불일치를 잡음(현 분석기와 대조)

## 5단계 — 배포
- [ ] 시험 전부 · SIF 배포 요청 · 배포판에서 확인
