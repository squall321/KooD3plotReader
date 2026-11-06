# 리포트 그림 꾸러미 — 계획 (2026-11-06)

**요청(사용자)** deep report 의 단면·전체 영상에서 바닥판 요소가 커서 타겟 파트가 잘 안 보인다. 타겟 파트만 가까이 크게,
주변 파트는 반투명으로 깔끔한 시뮬레이션 그림을 만들어 달라. 최대 응력 순간을 SVG 로 뽑아 호버하면 파트 이름이 뜨게.
그 밖에도 후처리 자동화가 리포트를 만들 때 많이 가져다 쓸 후처리를 기존 기능 말고 더 만들어 달라. 계획을 잘 세우고 만들자.

## 1. 현황 — 확인한 것

**지금 deep report 에서 되는 것**
- 파트별 단면 영상(LS-PrePost) — 그 파트만 켠 채 카메라를 맞추고(`ac`/`vauto`) 여백(`zin`, `--section-view-section-margin`
  기본 −0.3 = 30% 넓게)만큼 물러난 뒤, **영상은 모든 파트를 다시 켜서** 찍는다 → 타겟이 바닥 가까이 있으면 바닥 단면이 보인다.
  대상 목록은 `--parts`(분석 대상도 좁힌다)에서 오고, `--section-view-target-ids` 만 주면 파트별 모드가 꺼져 바닥까지 맞춘 전체 단면만 나온다.
- 전체 뷰 + 타겟 — 카메라는 바닥 포함 전 파트에 맞추고 타겟은 색으로만 강조. `_zoom.mp4` 는 다 찍은 1280×720 영상에서
  색 든 화소를 찾아 잘라낸 것이라 해상도가 낮다(가로 256~850 px). 로드맵은 이 자르기를 다시 짓지 않기로 했다(ROADMAP §4).
- 옛 계획 `VtkSectionView_Plan.md`·`SectionView3D_Plan.md`(2026-03·04, C++ 소프트웨어 단면 렌더러)에 「대상 파트 중심을 보는
  직교 카메라」 는 있으나, 바닥 숨기기·주변 반투명(opacity 는 「향후 확장」)·SVG·호버는 없다.
- **`--section-view` 를 켜면 `--per-part-render`·`--part-pattern` 이 말없이 무시된다**(core/d3plot_reader.py:379 — RenderConfig 를
  안 본다). `RenderOptions.context_parts`·`zoom_factor` 도 스크립트가 읽지 않는다. 「타겟을 줘도 안 된다」 의 한 원인.
- LS-PrePost 는 이 프로젝트가 아는 **반투명 명령이 없다**. 배치에서 확인된 것은 `selectpart part N on/off`·`vauto`·`zin` 등이고,
  `fringe/pfringe` 가 감추기를 되돌리므로 바닥 감추기는 그 뒤에 와야 한다.
- **자동화 길** — 7-1(pyKooCAE deep_report.sh)은 deep 을 `--section-view --section-view-backend software --section-view-axes z`
  로 부른다(LS-PrePost 렌더 없음, 덧붙일 인자는 `deep_extra_args`). post_analyze 는 LS-PrePost 가 있으면 그것으로 x·y·z 파트별
  단면. → 새 기능이 deep 의 **기본 동작**이면 셸을 안 고쳐도 두 길에서 나온다.
- deep HTML 은 `renders/` 를 매번 지우고 다시 훑어 링크한다(심지 않는다). 파이썬 리포트끼리 나눠 쓰는 SVG 모듈은 없다
  (scatter·sphere·impact 가 각자 `<title>` 툴팁).

**C++ 소프트웨어 렌더러(운영 SIF 에 있음)** — `section_views` 의 `view_mode: iso_surface` + `snapshot_state` 가 한 순간을 PNG 로
그린다: 바깥 면(사면체 · 오면체 · 피라미드 · 육면체를 고유 절점 수로 가름, 셸 · 두꺼운 셸), 직교 iso 카메라(방향 고정, 여백 3배),
대상 응력 색(절점 평균), **주변 파트 반투명 실루엣**(background_alpha 0.3), 범례. 모자란 것 — 파트 숨기기 없음(바닥이 반투명으로
그려진다), 삭제 요소 거르기 없음(변 6배 늘어남 휴리스틱만), 셸은 첫 적분점만, 글자는 5×7 점 글꼴(제목 · 파트 이름 불가), SVG 없음,
이름 패턴 타겟 무시(ID 만).

**새 길이 열려 있다 — 실측(11-06)**
- 운영 SIF(v43)에 VTK 9.3.1 · pyvista 0.46.4 · lasso · numpy · h5py · matplotlib · PIL · Xvfb 가 있다(rsvg·inkscape 는 없다).
- 시안: v14 런(4,952 상태, d3plot 250 파일 · HDD)에서 **최대 응력 상태 하나만** lasso 로 1.6 s 에 읽고, 파트별 바깥 면
  34,122 개를 0.2 s 에 뽑아, pyvista(Xvfb) 로 1 s 안에 그렸다. 타겟은 응력 색, 주변은 반투명, 바닥 숨김, 평행 투영으로
  타겟에 꽉 맞춤, 색 범위 0–p99.5(넘는 값 자홍) + 최대점 표시. 최대값 4024.92 MPa 가 S1 게이트 값과 같다.
  → LS-PrePost 없이 반투명·바닥 숨김·카메라·해상도를 마음대로 정할 수 있다.

## 2. 무엇을 만드나

### 2-1. 스냅샷 엔진 (새 모듈 `koo_deep_report/figures/`)
한 런의 고른 순간 하나를 그림으로. LS-PrePost 도 C++ 소프트웨어 렌더러도 쓰지 않고 pyvista(VTK) 로 그린다 — 글꼴 · 안티에일리어싱 ·
범례가 리포트 품질이고, 파트 숨기기 · 반투명 · 카메라를 마음대로 정할 수 있으며, SVG 와 같은 면 · 같은 카메라를 쓴다.
면 규칙(고유 절점 수로 요소 모양 가르기, 사면체 실제 면)은 C++ 렌더러와 같게 둔다.
- **읽기** — lasso 로 d3plot 의 그 상태만(`state_filter` + `buffered_reading`): 현재 좌표, 솔리드·셸 응력, 삭제 플래그.
- **바깥 면** — 파트마다 한 번만 나오는 면. 퇴화 육면체(오면체 등)는 겹친 절점을 지우고, 사면체(N4 반복 꼴)는 실제
  면 위상(4 삼각형) — 예전에 실제로 틀렸던 자리다. 셸은 그대로, 삭제된 요소는 뺀다.
- **값** — 요소 von Mises(솔리드, 셸은 층 최대). 리포트 정본(analysis_result 의 파트 최대)과 같은지 시험으로 지킨다.
- **순간** — 타겟 파트의 최대 시각(analysis_result `time_of_max`) → 상태 번호. 전역 최대 · 첫 접촉 · 끝 상태도 고를 수 있게.
- **그리기(PNG)** — pyvista 오프스크린(Xvfb 는 비어 있는 화면 번호를 골라 띄운다 — LS-PrePost 워커와 안 겹치게).
  - 타겟: 응력 색(jet, 0–p99.5 기본, 넘는 값 자홍, 고정 범위 선택 — 예: 항복값), 윤곽선.
  - 주변 파트: 회색 반투명(기본 opacity 0.15) + 옅은 윤곽선. 바닥: 숨김 — 자동 감지는 make_stl 의 규칙과 같게(다른 파트를
    다 합친 상자보다 두 축 이상에서 1.5배 넘게 큰 파트 = 환경), `--hide-parts` 로 덧붙인다.
  - 카메라: 평행 투영, 시점 iso + **최대점이 보이는 시점**(최대 요소 바깥 면의 법선 쪽), 화면 투영 크기로 맞춤, 범례 자리 비움.
  - 제목(파트 · 최대값 · 시각 · 런 — 한글 파트 이름은 SIF 의 Droid Sans Fallback 글꼴), 최대점 표시, 범례.
- **SVG(호버)** — 같은 카메라로 직접 투영해 쓴다(VTK 에 기대지 않음): 앞면만, 깊이 순서(화가 알고리즘), 램버트 음영,
  다각형마다 파트 번호 속성. 작은 내장 스크립트가 호버한 파트를 강조하고 툴팁(파트 이름 · 최대값 · 안전율)을 띄운다.
  `<title>` 폴백. 외부 라이브러리 0 — 폐쇄망 안전.

### 2-2. 그림 꾸러미 (리포트가 그대로 가져다 쓰는 표준 묶음)
deep 리포트 폴더 `figures/`(`renders/` 는 매번 지워지므로 따로)에, 표준 이름과 설명이 붙은 그림들과 `figures/manifest.json`.
| 그림 | 무엇 |
|---|---|
| `overview_peak.{png,svg}` | 전체 기기(바닥 숨김), 전역 최대 순간 |
| `part_<PID>_peak.{png,svg}` | 상위 N 파트(기본 5, 최대 응력 또는 안전율 순) 각각의 최대 순간, iso + 최대점 시점 |
| `energy.svg` | 에너지 수지(운동 · 내부 · hourglass · 합) 시간 이력 |
| `parts_peak.svg` | 파트별 최대 응력 막대(안전율 · 판정 색) |
| `part_<PID>_history.svg` | 상위 N 파트의 응력 · G 이력(최대 시각 표시) |
- **manifest.json** — 그림마다 `id · kind · part_id · state · time · value · unit · caption · files · camera` — 워드 · DynaForge
  리포트 생성기가 읽는다. 런 키 · 파트 번호가 온톨로지 꾸러미와 같아 서로 이어진다.
- deep HTML 에 「리포트 그림」 탭(SVG 그대로 — 호버가 된다, PNG 받기).

### 2-3. 영상 보완 (앞서 제안해 승인받은 것) — LS-PrePost 와 소프트웨어 렌더러 둘 다
- `--hide-parts PID…` / `--hide-floor` — 영상에서 그 파트를 뺀다. LS-PrePost 는 pfringe 뒤에 `selectpart part N off`,
  소프트웨어 렌더러(7-1 이 쓰는 것)는 그 파트 면을 그리지 않는다. 바닥은 그림 엔진과 같은 감지 규칙.
- `--view-fit target` + `--view-margin` — 전체 뷰도 타겟만 켜고 `vauto` 로 맞춘 뒤 찍는다(잘라내기 아님).
- `--section-view-target-ids` 만으로 그 파트들의 파트별 단면(분석 대상은 안 좁힘), `--section-view` 와 함께 준 렌더 옵션이
  무시될 때는 그렇다고 말한다.
- 주변 반투명은 LS-PrePost 명령이 없어 영상에는 넣지 않는다 — 반투명이 필요한 정지 그림은 그림 꾸러미가 맡는다.

### 2-4. 캠페인(sphere) — 2단계 뒤
- 파트별 **최악 방향 런**의 최대 순간 그림(판정이 CRITICAL/WARNING 인 파트부터) — post_analyze 단계로.

## 3. 단계
1. 엔진: 읽기 · 바깥 면 · 값 · 순간 고르기 · PNG · SVG — 합성 시험 + 실데이터(v14 · 핫스팟 런) 대조.
2. 꾸러미: manifest · 시간 이력 · 요약 SVG · deep 연결(기본값은 결정 사항) · HTML 탭.
3. LS-PrePost 영상 보완.
4. sphere 최악 방향 그림(post_analyze).
5. SIF 배포(상류 표준 경로).

## 4. 정할 것
1. deep 리포트에서 그림 꾸러미를 기본으로 낼지(런마다 10–30 s 늘어남 — 기본이어야 7-1 셸을 안 고쳐도 자동화에서 나온다) / 옵션으로만.
2. 상위 N(기본 5) · 기준(최대 응력 / 안전율).
3. 색 지도 — jet(LS-PrePost 관례) / turbo(눈에 고른 무지개).
