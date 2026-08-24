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


## 2026-08-21 전수 검증 (워크플로 12 에이전트 + Playwright 스윕) 결과 반영

- 42체크 중 실결함 3건 발견·즉시 수정: ① metric_source 가 C++ 내부에만 있고
  exporter 가 metrics.json 에 안 실었음(dfc70a8 약속 위반) → 수출 추가.
  ② custom_report HTML 이 _FIELD_LABELS 밖 필드(노드셋 disp/vel/acc, 미지 필드
  note)를 무음 탈락 → 목록 밖 필드도 원어 키로 표시. ③ make_stl JSON bbox 가
  데시메이션 이전 기준이라 정점과 최대 1.75 불일치 → 최종 정점 기준으로 통일.
- 추가 정직성 수정: 스피어/임팩트 세트 탭에서 전부-null 지표의 범위를
  0.00~1.00 으로 지어내던 표시 → '산출 없음'.
- 보강 검증으로 닫은 공백: 7필드 전체 CSV 정합(σ3 min집계 -191.97 골든 일치,
  미계측 3필드는 note), 3면(xy/yz/zx) 렌더 12미디어, CLI --sets/--part-set 경로,
  부분결측 세트(999 포함) missing_parts 기록+교집합 진행.
- 미검증으로 남긴 경로(합성 데이터 필요): MP4 상한 60 초과 시 생략+고지,
  set_report 전무 데이터셋의 s10 자기 은닉(코드 가드는 존재), 다세트 케이스의
  세트별 뷰 메타 선택. 차단: STRFLG=1 실덱(라이선스 만료).
- test_keyword_set_parser 실측 27케이스 (체크리스트 28 표기는 오기 — 수정).

## 2026-08-21 STL 자세 미리보기 — 원본 파일 + 방향 규약 (사용자: "전각도에서 잘 보이는지 보자")

- 16각도 몽타주 검사에서 바닥 플레이트(파트 23)가 기기와 같이 회전하는 것 발견.
  사용자 지시에 따라 **바닥을 지우는 게 아니라 시나리오 원본 모델(.k)에서 시작** —
  KeywordMeshParser 추가, make_stl 이 .k 를 직접 읽음. 스피어 보고서는
  runner_config.json 의 model_file 을 1순위로 사용.
- 충격 방향 수식이 덱과 반대였음: 1144런의 *INITIAL_VELOCITY 와 대조해
  Rᵀ·(0,0,−1) 로 교정 (최악 내적 +1.0000). 구식 수식은 정반대 면을 아래로 그렸다.
- 복셀/데시메이션 격자 등방화 (얇은 기기에서 플러드필 누수·거친 면 해결).

## 2026-08-21 자세 미리보기 파트별 색 (사용자: "파트별 색 붙여줘")

- make_stl JSON 에 `p`(삼각형별 파트 ID)·`parts`(파트 bbox) 추가. 그룹 고정 팔레트 +
  선택 파트 주황 강조 + 내부 파트 bbox 고스트 + 범례(기존 면 범례 자리 대체).
- 초기엔 강조 없음(그룹색만) — 드롭다운으로 고른 뒤에만 강조 (partPicked 플래그).
- 적대적 리뷰에서 미지 그룹 해시 색이 Display 와 충돌(ΔE 3.2) → 2차 고정 리스트.
  범례 오버플로 지적은 판정자가 반박(텍스트가 패널 배경 위에 칠해짐)했지만
  패널 height:auto 로 외관 정리.
- 뒷면 선택 파트: 경계 변 외곽선은 데시메이션 메시에서 점박이로 흩어져 폐기, bbox 고스트
  + [뒷면] 로 통일 (가려짐 판정 = 주황 픽셀 < 칠해진 픽셀의 1.5%).

## 2026-08-24 Mollweide 규약 통일 (사용자: "최신 KMM KVR에 맞게 후처리 정리")

- 최신 KMM(KooDynaAdvancedModification.DropAttitude) 소스 확인: 각도 부호 반전 후
  Rz(-y)·Ry(-p)·Rx(-r) 적용 = Rᵀ·(0,0,-1) — 1144런 덱 실측과 해석적으로 일치.
- 지도(eulerToLonLat)의 별도 공식 + Swap R/P 토글(기본 ON, 평균 33° 왜곡) 폐기 →
  impactDirBody() 단일 소스로 지도·3D 자세 통일. KVR 는 KooChainRun(1.4.0) 으로
  해석(체인: KooChainRun → StepConfigBuilder → KMM).
