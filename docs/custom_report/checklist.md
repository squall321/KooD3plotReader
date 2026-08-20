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
- [x] 패키지 뼈대 (pyproject + runner + report, 얇은 오케스트레이션)
- [x] YAML 합성 → unified_analyzer 실행 → per-set 산출물 수집
- [x] 단독 HTML — 피크 표(미계측 '—')·경고·3면 갤러리·클릭→영상 모달
- [x] Playwright 검증 (콘솔 에러 favicon 뿐, 모달 영상 재생 확인)
- [x] CLI: --config / --sets --part-set 속성 조합, 스키마 마커
- [ ] KooChainRun 통합 실전 확인 (sphere/impact 탭과 함께 P4·P5 에서)

## P4 — sphere Set Report 탭
- [x] _set_report_payload — analysis_results/<run>/custom_report/set_reports 스캔,
      세트×각도 행렬 (미실행=None, 0 금지), 미디어 상대경로
- [x] 탭 15 맨 끝 추가 (setupTabs DOM 순서 바인딩 준수, 기존 탭 불변)
- [x] Mollweide 세트 피크 + 미실행 회색점 + 호버=PNG 스왑 + 클릭=MP4 모달
- [x] Playwright 확인 — 1144점 중 12 데이터, 호버 최근접(P0001 212.89),
      PNG 실로드(naturalWidth 640), 모달 영상 src 정상

## P5 — impact s10 섹션 (오버레이 방식 — 사용자 요청 반영)
- [x] 뷰 변환 메타 (C++ 카메라 → view_<plane>.meta.json) — 모델좌표↔픽셀 매핑
- [x] 좌표계 다리: 위치 로컬좌표 ≠ 모델좌표 → 임팩터 궤적 첫 샘플(mx/my) 사용
      (실측: 로컬 그대로 매핑 시 25/25 전부 뷰 밖 — 궤적 사용 후 기하 예측과
      일치하는 9/25 안쪽)
- [x] s10: 세트 응력 뷰 **위에** 위치 마커 오버레이 — 호버=그 위치 피크 PNG 스왑,
      클릭=MP4 모달, 뷰 밖 위치는 가장자리 점선 링
- [x] emit: <stem>_data/set_media/ 복사 (PNG 전부, MP4 상한 60 + 사유 고지)
- [x] 캐시 무변경 설계 — payload 빌드 시 파일 직스캔이라 _CACHE_SCHEMA 범프 불요
- [x] 산출물 없으면 섹션·네비 자기 은닉
- [x] Playwright 확인 — 마커 25(안 9 + 점선 16), 호버 PNG 실로드, 모달 MP4

## P6 — node/segment 셋 확장
- [ ] 노드셋: 절점 변위/속도 피크 + (절점 포함 요소) 응력
- [ ] 세그먼트셋: 부모 요소 응력/변형률
- [ ] 뷰: 해당 요소만 표시
