# 컨텍스트 노트 — 리포트 그림 꾸러미

## 출발 (11-06)
- 사용자: deep report 단면 · 전체 영상에서 바닥 요소가 커서 타겟이 안 보인다 → 타겟만 크게, 주변 반투명, 최대 응력 순간 SVG +
  호버 파트 이름, 그 밖에 자동 리포팅에 많이 쓸 후처리. 「계획을 잘 세우고 만들자」.
- 앞서 「그런 제안은 없다」 고 답했는데, `VtkSectionView_Plan.md`·`SectionView3D_Plan.md`(C++ 소프트웨어 단면 렌더러, 03·04월)에
  「대상 파트 중심을 보는 직교 카메라」 는 있었다. 바닥 숨기기 · 주변 반투명 · SVG 호버는 없다 — 고쳐 둔다.

## 엔진을 이렇게 정한 까닭
- **LS-PrePost 가 아니라 pyvista(VTK) + lasso** — 운영 SIF 에 이미 있다. LS-PrePost 배치는 반투명 · 화면 맞춤 · 고해상도 정지 그림이
  어렵고(배치는 movie 전용 — ROADMAP §4 「PNG 렌더 포맷」), `_zoom.mp4` 는 잘라내기라 해상도가 떨어진다. 한 상태만 읽으면 되므로
  d3plot 전체를 훑지 않는다(v14 1.6 s).
- **SVG 는 직접 투영해서 쓴다** — VTK 의 벡터 내보내기(GL2PS)는 휠에 없을 수 있고, 파트별 호버 속성을 달 수 없다. 같은 평행 투영
  카메라 값으로 그리면 PNG 와 같은 그림이 된다.
- **바깥 면은 파트마다 센다** — 파트끼리 절점을 나눠 써도 각 파트가 닫힌 껍질이 되어, 반투명일 때 파트 경계가 보인다.
- **사면체는 실제 면 위상** — N1 N2 N3 N4 N4 N4 N4 N4 꼴을 육면체 면으로 세면 바닥 면 (1,2,3,4) 가 생긴다(면이 아니다).
  surface_stress_face_index 메모의 교훈.
- **색 범위 기본 0–p99.5** — 시안에서 모서리 한 요소(4,025 MPa)가 범위를 정해 나머지가 다 파랗게 묻혔다(p99.5 = 233). 넘는
  값은 자홍, 최대점은 따로 표시해 숨기지 않는다.
- **화면 맞춤은 쓰는 절점으로** — 시안 1 은 PolyData 에 전 절점(바닥 포함)을 넘겨 맞춤이 모델 전체로 잡혔다. 쓰는 절점만 남긴다.

## 조사에서 나온 것 (11-06)
- C++ 소프트웨어 렌더러 iso_surface 모드가 운영 SIF 에 있고 바깥 면 · 반투명 실루엣 · 스냅샷을 이미 한다. 그래도 엔진은 파이썬
  pyvista — 파트 숨기기 없음 · 삭제 요소 안 거름 · 셸 첫 적분점만 · 5×7 점 글꼴(제목 불가) · SVG 없음을 메우는 것보다 낫다.
- `--section-view` 가 켜지면 RenderConfig(`--per-part-render`·`--part-pattern`)를 안 본다 — 말없이 무시된다(d3plot_reader.py:379).
- 7-1 은 deep 을 소프트웨어 단면(z 축)으로만 돌린다. 새 기능은 deep 기본 동작이어야 셸 수정 없이 자동화에 닿는다.
- analysis_result 의 응력 이력 data 는 상태마다 한 점이고 순서도 같다 — v14 에서 S1 상태 시각과 최대 차 5e-13 s, part 21 의
  time_of_max → 57 번 상태, 그 상태 최대 4024.918866 = global_max. 그래서 최대 시각 → 상태 번호는 이력 순번으로 바로 얻는다.
- ~~SIF 의 한글 글꼴: Droid Sans Fallback · Noto CJK~~ — **틀렸다**. 그 목록은 HOME 을 묶어 들어온 호스트 matplotlib 글꼴
  캐시였다. SIF 에는 DejaVu 만 있다 → def 에 fonts-nanum 을 넣고(실패해도 빌드는 계속), 그림 제목은 영문 기술 표기로 쓴다.

## 사용자 결정 (11-06)
- 그림 꾸러미는 deep 기본 산출(--no-figures 로 끔) — 7-1 셸을 안 고쳐도 자동화에서 나온다.
- 파트별 그림은 상위 5개(안전율이 있으면 낮은 순, 없으면 최대 응력 순), 파트마다 iso + 최대점 시점. --figure-parts 로 직접.
- 색 지도 jet(LS-PrePost 관례).
- 1~4단계를 중간 확인 없이 한 번에.

## 만들면서 정한 것 (11-06)
- **그림 제목은 영문 기술 표기**(Part · state · color · view · hidden) — PNG 는 SIF 글꼴로 그려지는데 한글 글꼴이 없으면 한글이 지워져
  문장이 깨진다. 파트 이름만 원문(나눔이 있으면 한글 그대로, 없으면 ASCII 만). 설명(caption) · 차트 · 탭은 한글(브라우저 글꼴).
- **타겟은 늘 맨 위** — 한 번에 그리면 타겟 앞을 가린 반투명 주변 파트가 겹겹이 쌓여 타겟 색이 회색으로 바랬다(v14 PKG 10,
  기기 안쪽 파트일수록 심하다. 폰 낙하에서 보고 싶은 PKG · PCB 가 다 안쪽이다). PNG 는 주변(반투명, 흰 바탕)과 타겟(불투명,
  투명 바탕)을 따로 그려 겹치고, SVG 는 주변을 먼저 · 타겟을 나중에 그린다. 앞에 있는 주변 파트가 뒤로 가는 것은 감수한다.
- **범례 · 최대점 · 제목은 PIL** — PNG · SVG 가 같은 자리(colors.legend_box · label_box)에 같은 모양으로. 이름표는 범례 · 제목 띠에
  걸리면 왼쪽 · 아래로 뒤집는다.
- **그림의 「최대」 는 그 순간 파트 모든 요소의 최대**(StateSurface.part_max) — 바깥 면만 세면 최대 요소가 안쪽일 때 낮게 적힌다.
  최대점 표시는 바깥 면 최대 자리이고, 둘이 다르면 이름표가 「surface max」 다. 파트 그림은 해석기 파트 최대와 대조해 1e-4 넘게
  다르면 notes 에 남긴다 — v14 다섯 파트 모두 끝자리까지 같다(4024.918866 · 251.261421 · 167.405738 · 103.061631 · 93.372781).
- **안전율 · 판정 색은 deep 값 그대로**(PartSummary.safety_factor · stress_warning: 응력비 ≥ 1 CRITICAL, ≥ 0.8 WARNING) — 캠페인
  쪽 규칙(SF < 1.5 WARNING)을 쓰면 같은 보고서 안에서 판정이 둘이 된다.
- **단위** — 해석기 라벨(deck_units 아니면) → 덱 밀도 판정(ontology.deep.detect_units) → 「덱 단위」. 시간은 ms 로 보여 준다
  (g-mm-ms 덱은 이미 ms). 판정 못 하면 시간도 덱 단위 그대로.
- **상태 번호** — 이력이 잘렸거나 점 수 ≠ 상태 수면 순번을 믿지 않고 그 파트는 그리지 않는다. 읽은 상태 시각이 이력 최대 시각과
  상대 1e-5 넘게 다르면 notes.
- **배치는 스레드** — Xvfb · VTK · DISPLAY 환경변수가 프로세스 전역이라 스냅샷 구간은 프로세스 잠금 하나로 줄 세운다. 상태는 한 번에
  하나만 메모리에(같은 상태 그림끼리 묶어 읽기 한 번).
- **SVG 크기** — 화면 밖 면을 버린다(카메라가 타겟에 맞춰져 멀리 있는 주변 면이 많다). v14 큰 파트 2 MB, 작은 PKG 0.1 MB.
  HTML 탭은 PNG 미리보기만 싣고, 누르면 모달에 SVG(<object>, 호버 됨)를 연다. 차트는 탭에 바로 <object>.
- **셸 파트** — 응력 이력이 솔리드 전용이라 자동 선택에는 안 든다. `--figure-parts` 로 주면 전역 최대 순간에 그린다(셸 값은 층 최대).
- **UA_OUTPUT_SCHEMA 는 안 올렸다** — UA 산출물이 아니라 그 위의 산출이다. `--skip-existing` 로 건너뛴 옛 case 는 다시 돌려야 그림이 생긴다.
- **실측(v14, 호스트)** — 꾸러미 7.6 s(스냅샷 11 · 차트 7), 최대 RSS 667 MB, 폴더 약 20 MB.

## 자동화 길 · 캠페인 (11-06)
- **새 래퍼를 만들지 않았다** — 호스트 배포본(/data/SmartTwinPostprocessor)은 `koo_*_report` 래퍼만 lib/ 형식으로 새로
  짓고 나머지 bin 은 SIF 에서 그대로 복사한다. 그래서 `koo_ontology` 는 호스트에서 SIF 식 `python/` 경로를 가리켜
  env.sh 없이 돌리면 `No module named koo_deep_report` 로 죽는다(실측 — 기존 결함, 검증기도 `koo_*_report` 만 본다).
  그림은 `koo_deep_report figures pack|snap|campaign` 하위 명령으로 붙여 이 함정을 피했다. koo_ontology 결함은 따로 보고.
- **캠페인 상태 번호는 CSV 줄 번호** — `stress/part_<PID>_von_mises.csv` 는 상태마다 한 줄. 시각은 소수 6자리라 상태 간격
  1 µs 와 겹쳐 시각으로 찾으면 틀린다. 런마다 수십 MB 인 analysis_result.json 은 열지 않는다.
- **Test_006(2026-02 산출물)의 CSV · report.json 값은 틀렸다** — 줄 번호 = 상태 번호는 맞는데(시각 일치) 값이 다르다
  (파트 17 상태 216: CSV 561.3, 그림 엔진 10.158). 현 분석기(SIF eccde7f)로 그 런을 다시 재니 상태 216 = 10.15794394 로
  그림 엔진과 끝자리까지 같고, 파트 17 의 실제 최대는 상태 801 의 71.07. 2026-09 무결성 수정 이전 분석기 값이다.
  → 캠페인 그림은 이런 불일치를 notes · caption(⚠) · manifest `check` 로 드러낸다. 최악 런 고르기 자체가 옛 값에
  기대므로, 옛 캠페인은 다시 분석해야 그림의 대상 · 순간이 옳다.
- **post_analyze 단계 자리** — sphere 바로 다음(deep 앞). 캠페인 그림은 수십 초라 수 시간짜리 deep 보다 먼저 나온다.
  `--no-figures` 하나로 캠페인 그림과 deep 그림을 함께 끈다.
- **실측** — Test_006 캠페인 그림 11.4 s(스냅샷 11 · 차트 1, 런 다섯 개 d3plot 을 하나씩), 최대 RSS 672 MB.

## 3단계 — 영상 보완 (11-06)
- **숨김은 두 백엔드 모두** — 분석기 YAML 키 `hide_part_ids`(render_jobs · part_section_renders), 소프트웨어 단면은
  `hidden_parts: ids: [...]`. 비면 키를 쓰지 않는다(종전 출력 그대로). 옛 분석기는 모르는 키를 버리거나 배경 목록에 섞을
  뿐이라(배경은 이미 「*」) 새 deep + 옛 SIF 도 깨지지 않는다.
  - LS-PrePost: **`-M <id>`** 를 fringe/pfringe 뒤 · 첫 `ac` 앞에(카메라가 숨긴 파트를 빼고 맞춘다), 그리고
    `selectpart all on` 이 나오는 자리마다(writeRestoreAll · iso 맞춤 · 슬라이딩) 다시. **`selectpart part N on/off` 는 못 쓴다**
    — 실측(LS-PrePost 4.12 mesa 배치, Test_006)에서 켜고 끄기가 아니라 「N 만 보이기」 였다(off → 바닥만 남음, 여러 줄 on →
    마지막 하나만 남음, 첫 시도 영상이 빈 화면). 후보 여섯을 직접 돌려 `-M 23` 만 바닥 하나를 정확히 뺐다
    (.work/report_figs/lspp_exp). 메모의 「selectpart part N on 검증됨」 은 한 파트만 켜는 용도에서였다.
  - 실측(Test_006, x, 타겟 17): 범례 최소가 0(바닥 요소) → 0.5 로 바닥이 색 범위에서 빠지고, 파트별 iso-clip 은 기준(바닥까지
    맞춰 타겟이 작다) 대비 기기에 맞춰 크게 나온다. 개관 단면 위치 · `_zoom` 자르기 기준
    상자도 숨긴 파트를 뺀 상자(visibleModelBounds) — 전체 상자는 바닥이 크면 가운데가 바닥 한가운데다.
  - 소프트웨어: 잘림면 분류(SectionClipper classify)에서 숨김을 먼저 거른다('background 가 비면 타겟 아닌 전부' 보다 앞),
    3D · iso 외피 면에서 빼고, 자동 중심 · 슬라이딩 상자는 숨긴 파트를 뺀 요소 절점으로.
- **`--hide-floor` 는 선택**(계획 그대로) — 기존 영상 출력을 바꾸므로 기본으로 켜지 않았다. 바닥 감지는 그림 엔진과 같은 규칙을
  d3plot 초기 형상(lasso, 상태 값 없이)으로 — v14 · Test_006 모두 파트 23, 0.2 s. 실패하면 숨김만 빠지고 분석은 간다.
  `--hide-parts` 는 그림 · 영상 공통.
- **`--section-view-target-ids` → 그 파트들의 파트별 단면**(분석 대상은 안 좁힘, 2차 패스 없음). 종전엔 타겟 id 를 주면 파트별이
  꺼지고 바닥까지 맞춘 개관만 나왔다. 소프트웨어는 타겟이 하나면 개관이 곧 그 파트(카메라도 타겟)라 파트별을 다시 만들지 않는다.
  설정 파일 `per_part: true` 가 명시적 `--no-section-view-per-part` 를 덮어쓰던 3-상태 결함도 고쳤다.
- **쓰이지 않는 옵션은 `[설정]` 경고**(보고서 갤러리에도, 제목은 「렌더 설정」) — `--section-view` 와 함께 준 `--per-part-render` ·
  `--part-pattern`, 소프트웨어 단면의 이름 패턴(렌더러가 파트 이름을 몰라 안 맞는다) · `--section-view-state-step`(전 상태를 그린다
  — 실측 50 간격을 줘도 992 프레임 41 s), LS-PrePost 의 둘째 이후 대상 패턴.
- **실측(소프트웨어, Test_006 x · iso_surface 스냅샷)** — 숨김 끔: 거대한 바닥판 위 작은 기기(카메라가 바닥에 맞춤), 켬: 바닥이
  빠지고 카메라가 기기에 맞춰 2~3배. 외피 삼각형 50,032 → 45,952(바닥 4,080 제외).
- **메모리** — v14(4,952 상태) 소프트웨어 단면은 분석기가 상태를 통째로 들어 가용 6% 까지 떨어져 earlyoom 이 python 을 죽였다.
  검증은 Test_006(992 상태)으로 했다.

## 사용자 결정 (11-06, 마감) — 배포 · 바닥 숨김 기본 · koo_ontology
- **push + SIF 배포 요청**(상류 표준 경로).
- **`--hide-floor` 기본 켬** — 끄려면 `--no-hide-floor`(post_analyze 도 같은 이름으로 deep 에 넘긴다). 손으로 지은 Namespace(GUI 등)도
  기본(켬)을 따른다. 기존 영상 모양이 바뀐다(바닥이 빠지고 카메라 · 단면 위치가 기기에 맞는다).
- **호스트 koo_ontology 래퍼 수정** — deploy_from_sif.sh 가 `python -m` 래퍼(MODWRAPS: koo_ontology)를 SIF 에서 복사하지 않고
  `koo_*_report` 와 같은 lib/ 형식으로 짓는다. verify_deploy.sh 가 그것도 환경변수 없이 실행해 본다. 시뮬레이션(.work/deploy_sim2,
  호스트 lib/ 를 가리킴): 새 래퍼는 `koo_ontology vocab` 이 돌고, 지금 배포된 래퍼는 `No module named koo_deep_report`.
- **`-M` 접두어 꼴(배포 요청 뒤 보강, 로컬 커밋)** — /data 의 GUI 세션 기록(lspost.cfile)은 `-M H31`(솔리드) · `-M S21`(셸) ·
  `-M T2004`(두꺼운 셸)처럼 형식 접두어를 붙인다. 배치 실측(Test_006 솔리드 바닥): 맨 숫자 `-M 23`, 접두어 `-M H23`, 둘 다 —
  셋 모두 같은 화면. 맨 숫자가 셸에도 먹는지는 셸 d3plot 이 없어 못 봤다 → 형식을 알면 두 꼴을 함께 쓴다(셸 바닥 대비).
  실렌더는 종전 숨김 영상과 픽셀까지 같다. 141317c 배포가 끝난 뒤 push 한다(빌드가 main HEAD 를 clone).

## v44 굽기 실패 → def 보강 (11-06)
- v44(141317c) 빌드 %test 에서 `import pyvista` 가 ModuleNotFoundError(배포 세션 보고, 배포된 것 없음). **SIF 에는 pyvista · vtk ·
  PIL · matplotlib 이 없었다** — 내가 「SIF 안에서 돈다」 고 본 것은 `apptainer exec` 가 호스트 홈을 묶어 ~/.local 의 pip 패키지가
  보였기 때문이다(글꼴 목록 착각과 같은 함정). `--no-home` 으로 v43 을 열면 넷 다 없다(numpy 1.26.4 · lasso · yaml 은 있다).
- def 에 `pip install pyvista==0.46.4 vtk==9.3.1 Pillow==11.3.0 matplotlib==3.10.7`(호스트 검증 판). 굽지 않고 확인 — v43 SIF 안
  `--system-site-packages` venv(.work/sif_venv)에 같은 판을 SIF 의 pip 로 설치(numpy 는 시스템 1.26.4 그대로), `--no-home` 으로 v14
  꾸러미를 그렸다: 스냅샷 11 · 차트 7, 최대값 동일, 알림은 바닥 숨김뿐. 읽기 전용 홈이면 matplotlib · Mesa 가 캐시 경고를 낸다(무해).
- 내가 넣은 %test(`python3 -c "import pyvista, lasso.dyna, PIL, matplotlib"`)가 이 빈틈을 바르게 잡았다.

## v44 배포 (11-06, 마감)
- **v44 = e86fd1b**(141317c + 1c9a093 · 591ba55 · e86fd1b) — 헤드리스 a1ca45cc(1,156,435,968 B) · GUI 15cf8e0f 가 빌드 원본 · /data ·
  compute-node-images · 헤드 /opt 네 곳에서 같다. v43 은 헤드 /opt 에 하드 링크 백업(…_backup_20261106_214703.sif). tar v44 도 나갔다.
- 배포 세션 확인(모두 `--no-home`): a VERSION e86fd1b · 래퍼 7개 환경변수 없이 실행, b 호스트 koo_ontology vocab 정상(v43 은 No module),
  c-1 rc 0(41.6 s, RSS 6.84 GB) 스냅샷 11 · 차트 7 · 바닥 [23] 숨김 · 「리포트 그림」 탭, c-2 rc 0(72 s) 영상 셋에 형상 · 바닥 없음.
  이쪽 재확인: 헤드 /opt 로 --no-home 에서 의존성 import · v14 꾸러미(최대 4024.9189, manifest 판 e86fd1b).
- GUI SIF 에는 그림 의존성이 없다 — 뷰어는 deep 을 실행하지 않고 명령줄(`<d3plot_path>` 자리표시)만 보여 준다. GUI def 는 원래 numpy ·
  lasso 도 없어 GUI 안 deep 은 전부터 반쪽이었다. 그대로 둔다.
- c-2 의 `section_view_zoom.mp4`(256×144, 거의 한 색)는 기존 기능(타겟 강조 개관의 응력 색 화소 자르기). 40 상태 간격이라 프레임 25장 →
  50번째 프레임이 없어 t=0(전부 파랑)으로 넘어가 최소 크기로 잘렸다. 단면(projectview)과 맞지 않는 것은 미해결 목록에 이미 있다 —
  고칠지는 사용자 결정.
- 남은 것: 노드(node001 · 002) 로컬 SIF(노드 down).

## 단면 영상의 `_zoom.mp4` 끄기 (11-06, 사용자 요청)
- `--section-view` LS-PrePost 개관(타겟 강조)은 확대본을 만들지 않는다 — 분석기 YAML render_jobs 의 새 키 `zoom_crop: false`(기본 true,
  옛 분석기는 무시). 타겟은 파트별 단면이 따로 맞춰 나오고, 자르기는 50번째 프레임의 따뜻한 응력 색을 못 찾으면 최소 크기(가로/5 =
  256×144)로 잘라 거의 한 색 영상이 갤러리에 실렸다(v44 c-2). `--section-view` 없는 예전 `--per-part-render` 의 확대본은 그대로.
- **곁에서 찾은 기존 결함**: `_zoom` 파일 이름을 전체 경로의 마지막 점에 끼워 만들어, 폴더 이름에 점이 있으면(`.work/`, `v1.2/`)
  `/src/_zoom.work/...` 같은 없는 경로가 되어 ffmpeg 가 조용히 실패했다 — 그래서 이쪽 로컬 렌더에선 확대본이 한 번도 안 생겼다.
  파일 이름 안의 점만 본다.
- 확인(호스트, 새 분석기): 점 없는 경로 + `zoom_crop: false` → 확대본 없음 / 키 없음 → 「Cropped」 확대본 / `.work/` 경로 + 키 없음 →
  이제 제자리에 확대본. 새 분석기는 호스트 glibc 2.38 로 빌드돼 SIF(22.04) 안에서는 못 돌린다 — SIF 확인은 다음 배포판에서.

## Xvfb 리셋 경쟁 — 그림이 가끔 abort(rc 134)로 deep 를 통째로 죽이던 결함 (11-07, v46 부터)
- 배포 세션(pykoocae-53)이 v48 판정 중 찾았다 — 「vtkXOpenGLRenderWindow: bad X server connection. DISPLAY=:140. Aborting.」
- 원인: `xvfb.display()` 가 Xvfb 를 `-noreset` 없이 띄웠다. 기본 Xvfb 는 마지막 클라이언트가 끊길 때 서버를 리셋하는데(약 60 ms),
  `png._layer` 가 겹마다 Plotter 를 열고 닫아 다음 겹이 1.6~2.0 ms 만에 리셋 도중으로 들어온다 → 그 연결이 함께 닫혀 XOpenDisplay 가
  NULL → VTK abort(). 파이썬 예외가 아니라 pack 의 try/except 가 못 잡고 deep · 캠페인 그림 프로세스 전체가 죽는다. abort 하면
  display() 의 finally 가 안 돌아 Xvfb 가 고아(PPID 1)로 남아 apptainer 마운트를 붙잡는다.
- 고침: `xvfb_cmd()` — `-noreset` + `setpriv --pdeathsig TERM --`(부모가 죽으면 Xvfb 도 죽는다, setpriv 없으면 그냥).
- 실측(헤드 load ~50/32, DISPLAY 없이 그림 코드가 Xvfb 를 직접 띄움, 셸 파우치 snap 10회씩): v48 SIF 코드 8/10 · abort 2 · 고아 Xvfb 2,
  고친 코드 10/10 · abort 0 · 새 고아 0. 고친 코드로 display() 안에서 os.abort() → Xvfb 도 사라짐. 부하가 낮으면 드물다(그래서 판정
  deep airbag 11장은 통과했었다).
- 렌더를 자식 프로세스로 떼어 abort 해도 deep 가 사는 방식은 하지 않았다 — 알려진 원인은 위에서 없앴다(필요하면 다음에).
