# Custom Report 체크리스트

계획: [plan.md](plan.md) · 결정 이력: [context-notes.md](context-notes.md)

## P0 — 세트 파서
- [x] KeywordSetParser.hpp/.cpp (*SET_PART/NODE/SEGMENT, LIST/TITLE/GENERATE/COLUMN/GENERAL)
- [x] 미지원 변형(_ADD, GENERAL BOX 등) 경고 경로
- [x] 콤마/고정폭 혼용, 소문자 키워드, $ 주석, *END
- [x] tests/test_keyword_set_parser (28 케이스 전부 통과)

## P1 — YAML + 파트셋 피크 지표
- [x] UnifiedConfig: sets_file, set_reports (SetReportSpec)
- [x] UnifiedConfigParser: sets: / set_reports: 파싱 + 예제 생성기
- [x] prepareSetReports/finalizeSetReports — 파트셋 7필드 시계열·피크
- [x] 세트 파트 자동 잡 주입 (processSolidJobs 합집합이라 중복 비용 없음)
- [x] missing_parts / 빈 교집합 / 파일 부재 / node·segment 사유 처리
- [x] JSON set_reports 블록 + CSV 시계열 + metrics.json
- [x] Test_006 교차 대조 — σ_vm 212.889924 · σ3 -191.97 per-part CSV 와 일치

## P2 — 세트 뷰 렌더
- [x] SectionViewConfig: PartTopView + snapshot_state + max_frames
- [x] SectionCamera::setupAxisAligned (setup() 은 view_dir_ 미충전 함정 회피)
- [x] renderIsoSurface 파라미터화 (타깃만·백페이스 컷 해제·프레임 다운샘플)
- [x] processSetViews — planes×fields 렌더, 피크 상태 스냅샷, 규약 이름으로 배치
- [x] Test_006 확인 — view_xy/zx mp4 + peak png 4종, 이미지 스팟체크 정상
- [x] 기존 단면뷰 회귀 (avg_edge 1.7290, 992 프레임)

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
