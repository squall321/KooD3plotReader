# Custom Report 체크리스트

계획: [plan.md](plan.md) · 결정 이력: [context-notes.md](context-notes.md)

## P0 — 세트 파서
- [x] KeywordSetParser.hpp/.cpp (*SET_PART/NODE/SEGMENT, LIST/TITLE/GENERATE/COLUMN/GENERAL)
- [x] 미지원 변형(_ADD, GENERAL BOX 등) 경고 경로
- [x] 콤마/고정폭 혼용, 소문자 키워드, $ 주석, *END
- [x] tests/test_keyword_set_parser (28 케이스 전부 통과)

## P1 — YAML + 파트셋 피크 지표
- [ ] UnifiedConfig: sets_file, set_reports (SetReportSpec)
- [ ] UnifiedConfigParser: sets: / set_reports: 파싱 + 예제 생성기
- [ ] UnifiedAnalyzer::processSetReports — 파트셋 σ_vm/ε 시계열·피크 (per-part history 집계)
- [ ] 세트 파트가 stress/strain 잡에 없으면 자동 잡 주입
- [ ] missing_parts / 빈 교집합 사유 처리 (무음 금지)
- [ ] JSON set_reports 블록 + CSV 시계열 + metrics.json
- [ ] Test_006 + 수제 sets.k 로 per-part CSV 교차 대조

## P2 — 세트 뷰 렌더
- [ ] SectionViewConfig: view_mode=set_view, planes, max_frames
- [ ] no-clip 렌더 경로 (축 정렬 ortho, target bbox fit)
- [ ] 전 상태 MP4 + 필드별 피크 시각 PNG
- [ ] set_reports YAML 의 planes/video/peak_snapshot 연결
- [ ] Test_006 렌더 확인 (파일 존재 + 이미지 스팟체크)

## P3 — koo_custom_report 패키지
- [ ] 패키지 뼈대 (koo_deep_report 구조 준용)
- [ ] YAML 오케스트레이션 (unified_analyzer 호출)
- [ ] 단독 HTML (세트별 3면 뷰 갤러리 + 피크 표 + 경고 표시)
- [ ] KooChainRun per-run 산출물 규약 (Output/report/set_reports/)

## P4 — sphere Set Report 탭
- [ ] run 폴더 set_reports 스캔 (loader)
- [ ] 탭 추가 (기존 탭 불변)
- [ ] Mollweide 세트 피크 + 호버 PNG + 클릭 MP4
- [ ] Playwright 확인

## P5 — impact Set Report 탭
- [ ] per-position set_reports 스캔 + 캐시 스키마 범프
- [ ] 그리드 히트맵 + 호버 PNG + 클릭 MP4 (tier 정책 준수)
- [ ] Playwright 확인

## P6 — node/segment 셋 확장
- [ ] 노드셋: 절점 변위/속도 피크 + (절점 포함 요소) 응력
- [ ] 세그먼트셋: 부모 요소 응력/변형률
- [ ] 뷰: 해당 요소만 표시
