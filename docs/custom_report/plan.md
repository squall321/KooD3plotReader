# Custom Report 개발 계획

작성 2026-08-20. 요청 요지와 아키텍처 결정, 단계별 계획을 기록한다.
진행 상태는 [checklist.md](checklist.md), 결정 이력은 [context-notes.md](context-notes.md).

## 1. 요구사항 (사용자 요청 원문 요지)

1. **Custom Report 모드 (신규)** — d3plot + LS-DYNA 포맷 세트 정의(*SET_PART /
   *SET_NODE / *SET_SEGMENT)를 입력으로 받아, YAML 에서 "어떤 세트를 어떻게
   후처리할지"를 정의한다.
2. **1차 목표 = 파트셋 뷰** — 정의된 파트셋의 파트들만 표시한 상태에서
   xy/yz/zx 3면 탑뷰로 fit 하여
   - 전 상태 응력/변형률 컨투어 **영상**
   - **최대 응력/최대 변형률 시각의 스냅샷**
   - 그 파트셋 내부의 **최대 응력·최대 변형률 수치**
   를 낸다. 단면(section)은 하지 않는다. 노드셋/세그먼트셋도 같은 틀로 확장.
3. **sphere/impact 연동 (기존 기능 불변, 새 탭)** —
   - 전각도 낙하: 세트별 피크 응력/변형률을 구면(Mollweide)에 표시. 각도 점
     **호버 = 그 각도의 피크 시각 컨투어 PNG**, **클릭 = 영상**.
   - 전위치 부분충격: 충격 위치 호버 = 그 위치의 세트 결과(피크 컨투어),
     클릭 = 영상. 용량 관리를 위해 호버는 정적 PNG, 영상은 클릭 시에만.
4. **보편성** — 이후 노드 간 상대 거동, 세트 조합 등 복잡한 메커니즘 분석을
   같은 YAML 틀에 추가할 수 있는 스키마.

## 2. 아키텍처 결정

### 세트 파싱은 C++ (KeywordSetParser)
unified_analyzer 가 지표 계산과 렌더 타깃 선정에 파트/노드 ID 를 직접 쓰므로
C++ 이 파싱을 소유한다. Python 은 resolved 결과를 analysis_result.json 으로
받는다. 세그먼트→요소 매핑도 메시를 가진 C++ 쪽이 유일하게 효율적이다.
미지원 변형(_ADD 등)은 **무음 스킵 금지** — warnings 로 남긴다.

### 렌더는 소프트웨어 래스터라이저 확장 (LSPrePost 아님)
서버 헤드리스에서 LSPrePost 는 래퍼 미경유 시 깨지는 이력이 있다
(render_pipeline_sif_diagnosis). 단면뷰 래스터라이저(SectionViewRenderer)가
이미 target_parts 필터·컨투어·PNG/MP4 출력을 갖고 있으므로 "클리핑 없는
축 정렬 뷰" 모드를 추가하는 것이 최소 변경이다.

### 산출물 규약 (per-run)
```
<output>/set_reports/<safe_name>/
    metrics.json                  # 피크·시계열·resolved/missing·warnings
    view_xy_von_mises.mp4         # 평면별·필드별 영상
    peak_xy_von_mises.png         # 필드별 피크 시각 스냅샷
    ...
analysis_result.json              # set_reports 요약 배열 포함
```
sphere/impact 는 run 폴더(analysis_results/<Run>/set_reports/)를 스캔해
집계한다. 호버 = PNG 참조, 클릭 = MP4 참조 (인라인 금지, 상대경로).

### YAML 스키마 (보편성)
`set_reports` 는 리스트이고 각 항목은 `set` 참조 + capability 블록들이다.
새 분석(예: 상대 거동)은 새 블록을 추가하는 방식 — 기존 블록과 독립.

```yaml
sets:
  file: "sets.k"            # 생략 시 d3plot 근처 키워드 파일 자동 탐색

set_reports:
  - name: "PKG 모듈"
    set_type: part          # part | node | segment
    set_id: 5
    fields: [von_mises, eff_plastic_strain]   # 생략 시 가용 전부
    planes: [xy, yz, zx]
    video: true
    peak_snapshot: true
    width: 1280
    height: 720
    # (미래) history: ..., relative_motion: ..., combine: ...
```
알 수 없는 키/블록은 경고 후 무시 (보고서는 계속 간다).

### 미계측 규약 (이 세션에서 확립한 원칙 유지)
값이 없으면 0 이 아니라 키 자체를 빼거나 measured=false. 세트가 메시에 없는
파트를 참조하면 missing_parts 로 남기고 교집합으로 진행. 교집합이 비면
사유와 함께 스킵.

## 3. 단계

| 단계 | 내용 | 검증 |
|---|---|---|
| P0 | KeywordSetParser (*SET_ 3종, LIST/TITLE/GENERATE/COLUMN/GENERAL) | 픽스처 테스트 (완료) |
| P1 | YAML sets/set_reports + 파트셋 피크 지표 (σ_vm/ε 시계열·피크·요소ID) | Test_006 + 수제 sets.k — per-part CSV 와 교차 대조 |
| P2 | SectionViewRenderer 에 set_view 모드 (no-clip, 축 정렬 ortho, 3면, fit) → MP4 + 피크 PNG | case_shell/Test_006 렌더 산출물 확인 |
| P3 | koo_custom_report 패키지 — YAML 오케스트레이션 + 단독 HTML (뷰 갤러리 + 피크 표) | 실행 → HTML Playwright 확인 |
| P4 | sphere "Set Report" 탭 — Mollweide 피크 + 호버 PNG + 클릭 MP4 | Test_006 6런으로 통합 확인 |
| P5 | impact "Set Report" 탭 — 그리드 히트맵 + 호버/클릭 | Test_Impact_A 로 확인 |
| P6 | node/segment 셋 지표(노드: 변위/속도, 세그먼트: 부모 요소 응력) + 뷰 | 합성 + 실데이터 |

각 단계는 독립 커밋. 기존 경로(sphere/impact/deep)는 새 탭·새 블록 추가만
하고 기본 동작을 바꾸지 않는다.

## 4. 위험과 대응

- **보고서 용량** — 호버는 PNG(수십 KB), MP4 는 파일 참조로 클릭 시 로드.
  impact 는 tier 정책(energy_flow_topk 패턴)을 따른다.
- **세트 파일 *INCLUDE** — P0 은 따라가지 않고 경고. 필요해지면 후속.
- **노드셋 지표의 의미** — 노드셋은 요소값이 아니라 절점 운동(변위·속도)이
  1차 지표. 요소 응력은 "그 절점을 포함한 요소" 정의로 P6 에서.
- **렌더 시간** — set_view 는 상태 전수 렌더라 992 스텝 모델에서 수 분.
  프레임 다운샘플 옵션(max_frames)을 P2 에 포함.
