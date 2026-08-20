# Custom Report 컨텍스트 노트

작업 중 내린 결정과 이유. 다음 세션이 재추론 없이 이어가기 위한 기록.
(계속 append)

## 2026-08-20 설계 착수

- **세트 파싱 = C++ 소유.** 지표 계산·렌더 타깃 모두 C++ 이 ID 를 쓰므로.
  Python 은 analysis_result.json 의 resolved 결과만 읽는다.
- **파서 토큰화는 콤마+공백 혼용.** 고정 10칸을 엄격히 지키지 않는 파일이
  많고, 세트 카드 필드는 공백을 품지 않으므로 안전. 고정폭 중간 공란
  필드(GENERATE 쌍 어긋남)는 이론상 오독 가능 — 홀수 필드 경고로 방어.
- **parseInt 는 "1.0" 허용.** LS-DYNA 카드에 정수를 실수로 쓰는 파일 실존
  (COLUMN 의 뒤 컬럼). 진짜 소수는 거부.
- **GENERATE 전개 상한 5M.** 오타로 1..10^9 같은 범위가 오면 메모리 폭발
  대신 경고 후 스킵.
- **_ADD(세트의 세트) 미지원 + 경고.** 재귀 해석은 필요해지면. GENERAL 은
  NODE 행만 (BOX/PART 행은 경고).
- **테스트 기대값 실수 있었음** — 픽스처 유효 세트는 7개 (1,10,20,30,40,60,70).
  세트 수를 셀 때 _ADD 스킵과 *END 제외를 함께 고려할 것.
- **렌더 경로 = 소프트웨어 래스터라이저.** LSPrePost 는 서버 헤드리스에서
  래퍼 필요 + 세그폴트 이력 (memory: render_pipeline_sif_diagnosis).
  SectionViewRenderer 에 no-clip set_view 모드 추가가 최소 변경.
- **호버=PNG / 클릭=MP4.** 사용자가 용량 우려를 명시. 인라인 base64 금지,
  run 폴더 상대경로 참조 (sphere 렌더 갤러리 관례와 동일).
- **미계측 규약 유지.** 이 세션 앞부분에서 확립한 원칙 (0 위장 금지,
  measured 플래그, 사유 문자열) 을 세트 지표에도 그대로 적용한다.
- **기존 보고서 불변 원칙.** sphere/impact 는 탭 추가만. set_reports 가
  YAML 에 없으면 어떤 경로도 동작이 달라지지 않아야 한다.

## YAML 파서 구조 (P1 구현 참고)

- UnifiedConfigParser::parse 는 수제 라인 파서. 최상위 섹션은 indent==0
  분기 (line ~385), 리스트 블록은 in_xxx 플래그 + flush_xxx 램다.
- **가장 좋은 본보기 = part_section_renders** (line ~456-548): 리스트 항목
  시작(`- name:`), indent 4 필드, indent 6 output 서브섹션, parseIntArray/
  parseStringArray 헬퍼. set_reports 는 이 패턴을 그대로 따른다.
- section_views 는 yaml_block 원문 축적 방식 (자체 파서에 재위임) — set_reports
  에는 부적합 (필드가 적고 구조적이므로 직접 파싱).

## 2026-08-20 정찰 워크플로 결과 (7 에이전트, 상세는 scratchpad/recon/*.json)

- **P2 렌더 확정**: IsoSurface 모드가 이미 "클리핑 없는 전체 외곽면 컨투어"
  파이프라인 — 새 PartTopView 는 renderIsoSurface 복제 + ① target 외 면 제외
  ② 배경 실루엣 패스 삭제 ③ 축 정렬 카메라. **핵심 함정: SectionCamera::setup()
  은 view_dir_ 를 안 채워서 재사용 불가** — setupAxisAligned 신설 필요.
  스냅샷은 snapshot_state 키로 프레임 복사. YAML 은 SectionViewJobSpec.yaml_block
  통과라 UnifiedConfigParser 무수정 (SectionViewConfig 파서에만 키 추가).
- **YAML 파서**: validate() 1082행이 "잡 하나 필수" — set_reports 단독 설정
  허용하려면 조건 확장 필수. 블록 스타일 문자열 리스트('- xy')는 파싱 안 됨
  → planes 는 반드시 인라인 [xy, yz]. findKeywordFile 은 익명 네임스페이스 —
  재사용하려면 public static 승격.
- **sphere**: 탭 15로 맨 끝 추가 (setupTabs 가 DOM 순서 인덱스 바인딩이라 중간
  삽입 금지). 호버는 1725행 최근접점 패턴, 미디어는 경로 참조(base64 금지),
  모달은 sphere 에 없어서 이식 필요.
- **impact**: s10 섹션 신설. 미디어는 `<stem>_data/` 형제 디렉터리 규약
  (file:// 에서 fetch 는 막히지만 img/video src 는 동작). 캐시 _CACHE_SCHEMA
  6→7 범프 + _run_fingerprint 에 set_reports stat 추가 필수.
- **산출물 규약 안전 확인**: `<out>/set_reports/<safe_name>/` 는 sphere Run_
  필터·deep renders/ 스캔·impact stat 지문·--skip-existing 판정 어느 것과도
  충돌 없음.
- **LSPrePost 대비**: cfile 원자 명령은 다 있으나 서버 헤드리스 리스크로
  소프트웨어 래스터라이저 우선 결정 유지.

## 2026-08-20 P5 구현 중 결정

- **오버레이 UX (사용자 요청 반영)**: impact 는 별도 히트맵이 아니라 **세트
  응력 뷰 이미지 위에 충격 위치 마커를 겹친다**. 같은 메시·같은 카메라라
  마커는 고정, 호버 시 배경 이미지만 그 위치 것으로 스왑.
- **뷰 변환 메타**: PartTopView 가 view_meta.json (origin/u/v/half_w/half_h)
  을 내보내고 processSetViews 가 view_<plane>.meta.json 으로 배치. JS 는
  내적 기반 매핑이라 기저 방향(u=+Y, v=-X 실측)과 무관.
- **좌표계 함정**: ImpactPosition.x/y 는 디바이스 로컬(step_config LocationX/Y),
  뷰 메타는 모델 좌표. 로컬을 그대로 매핑하면 전부 뷰 밖 (실측 25/25).
  다리 = report.impactor_trajectories[pid].pos_x/y[0] (모델 좌표 상태값).
- **캐시 무변경**: per-position 세트 스캔을 pickle 이 아니라 payload 빌드
  시점 파일 직스캔으로 설계 → _CACHE_SCHEMA 범프·지문 수정 불요 (정찰의
  권고는 pickle 저장 가정이었음).
- **Test_Impact_A 특성**: 전 파트 σ 피크가 초기 프리로드 상태(t≈2μs)에서
  나와 위치 간 동일 — 파이프라인 문제 아님 (런별 CSV md5 상이 확인).
  파트 5,6,7 은 y≈126 픽스처였음. 데모 세트는 20,12,11 로 교체.


## 2026-08-20 P6·임팩터 실형상 결정

- **metric_source 규율**: node/segment 셋 지표는 파트 이력 집계가 아니라
  상태 직스윕 (computeDirectSetMetrics). 파트 이력 피크를 셋 값으로
  위장하지 않기 위해 metrics.json 에 metric_source 명시.
- **make_stl 파트 필터 함정 3연쇄**: ① 데시메이션·bbox 가 mesh.nodes
  전체를 써서 필터해도 전체 모델 크기로 잡힘 → 사용 정점 압축으로 해결.
  ② 셀 평균 정점이 곡면 안쪽으로 파고들어 구가 우둘투둘 → 최근접 원본
  절점 스냅. ③ 소형 bbox 에 VR=128 이면 복셀이 잘아 플러드필이 새서
  내부 제거 0 → 임팩터는 VR=32 (실측 스윕 16/24/32/48).
- **캔버스 비율**: 버퍼 400×220 에 CSS height 고정이면 찌그러짐 —
  height:auto 로 비율 유지 (사용자 즉시 지적).
- **test_quantization 2건 실패는 기존 건**: HDF5 로그 양자화기 하한
  0.1 MPa vs 테스트 기대 0.001 MPa — 이번 작업과 무관.
