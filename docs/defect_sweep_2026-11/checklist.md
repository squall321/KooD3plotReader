# 체크리스트 — 묵은 결함 정리

## 0. 준비
- [x] 목록 다시 훑기 — 항목마다 지금 코드에서 재현되는지 확인하고 가른다(고친다 · 보고만 · 이미 고쳐짐 · 다른 세션 담당)
- [x] 적분점 여덟 개 솔리드 실측 — ElasticBeam(자리마다 다른 값 · 사면체 뒤 네 자리 0), 배터리 · 테이프 덱(여덟 자리 같은 값)
- [x] 머리말 훑기 — d3plot 폴더 3,182개 중 솔리드 있는 2,741개가 「한 자리 2,479 · 여덟 자리 159 · 솔리드 워드 없음 103」 으로 갈린다
- [x] 고치기 전 빌드 보관(`.work/defect_sweep/base/unified_analyzer` = d2f0d6b 소스, 도장은 설정 시점의 `37c5f88-dirty`)
- [x] 계획 · 체크리스트 · 결정 기록

## 1. A1 — 분석기(파트 이력 · 핫스팟 · 피크 텐서)
- [x] `include/kood3plot/data/SolidIpLayout.hpp`(배치 · 쓰인 자리 · 평균)
- [x] 합성 d3plot 시험 `tests/test_solid_ip_history.cpp` — 먼저 쓰고 지금 코드에서 실패하는 것을 본다
- [x] 파트 통계 세 경로(병렬 · 직렬 · 순차) — 적분점 극값
- [x] 변형률 자리(적분점 블록마다 뒤 6워드)
- [x] 핫스팟 1차 훑기 · 군집 집계 · 피크 요소 텐서 이력
- [x] 실덱 — ElasticBeam 파트 1 999.3026 · 파트 2 1001.069, 그림 꾸러미 경고 사라짐
- [x] 회귀 — 한 자리 덱 · 배터리 · 테이프 덱 산출이 고치기 전 빌드와 바이트까지 같다(양쪽을 `-ffp-contract=off` 로 빌드해서. 제품 플래그로는 주응력 끝자리 · 동률 요소 번호가 흔들린다 — 결정 기록 4.1)
- [x] C++ 시험 전체 · 커밋

## 2. A2 — 같은 배치를 읽는 다른 경로
- [x] S1 `solidVonMises`(적분점 최대) · 호출부 둘 · `test_s1_core` · 계약 초안 문구 · 대조 스크립트 → 커밋
- [x] 겉면 응력 · 변형률(쓰인 적분점 평균 텐서) · 시험 → 커밋
- [x] set 리포트 segments 지표(적분점 극값) · 시험 → 커밋
- [x] 소프트웨어 단면 렌더 절점 평균(적분점 최대 — LS-PrePost 「max IP. value」 를 재서 평균 텐서 안을 버렸다) · 시험 → 커밋

## 2b. 단면 렌더에서 같이 찾은 것
- [x] V 셸 · 두꺼운 셸의 층 최대(첫 층 = 중립면만 읽던 것) · 시험 → `ElasticBeam` 셸 파트 59.73 → 999.397(LS-PrePost 와 같다) → 커밋
- [x] S 삭제 요소를 순번으로 견주기(`NodalAverager` · `SectionClipper`) · 시험(고치기 전 40건 실패) → erode7 프레임 그대로 → 커밋
- [x] T 단면뷰 `max_shear` = (σ1−σ3)/2 · 시험(고치기 전 360건 실패) → `ElasticBeam` 576.948 → 499.833(LS-PrePost 와 같다) → 커밋
- [x] U 되풀이 절점을 한 번만 세기(응력 경로 · 총변형률 경로) · 시험(고치기 전 4건 실패) → `ElasticBeam` 사면체 파트 절점 54개 값이 바뀜 → 커밋
- [x] W `computePartFringeRange` — 실렌더로 재현하니 범위가 영상에 실린 적이 없다(타겟 갈래에 범위 줄 없음) → 사용자 `fringe_range` 를 타겟 렌더에도 적고 죽은 자동 범위를 지움 · 시험 → 커밋. 타깃 자동 범위 정책은 보고
- [x] X LS-PrePost 백엔드 fringe 이름 대응 — 실렌더로 재현(`displacement_mag` · `max_shear` · `pressure` 가 von Mises 로 그려졌다) → 이름 표 하나 · 시험 → 커밋. `strain` 의 이름표(「Total Strain」 인데 LS-PrePost 는 유효 소성 변형률)는 사용자 결정으로 보고

## 3. Q — `parts:` 걸러내기
- [x] 재현 시험(합성 덱 — 요청한 파트만 나오는지, 없는 번호 사유 줄, 빔) — 고치기 전 21건 실패
- [x] `SinglePassAnalyzer`(요청 목록 · 빔) · `UnifiedAnalyzer`(핫스팟 군집) — `ElasticBeam` 실덱 [] · [1] · [1, 99]
- [x] deep `--parts 1` 끝까지 — 표 · 그림 꾸러미 · 온톨로지 꾸러미 모두 파트 1 만, 옵션 없으면 지금과 같다
- [x] 커밋

## 4. 렌더 · deep 쪽
- [x] B 단면 위치 상자 — 실렌더로 재현(없는 번호 하나에 빈 화면) → 면이 있고 숨기지 않은 타겟만 · 시험 → 실렌더 → 커밋
- [x] C `--config` 가 `--section-view` 를 끄지 않게 — 시험(고치기 전 실패) → 커밋(D 와 함께 — 「CLI 가 우선」 한 가지)
- [x] D `--config` 도움말 → 커밋(C 와 함께)
- [x] E rc 3 사유 줄 — 시험(고치기 전 실패) → 실분석기로 확인 → 커밋
- [x] L `global_unmeasured` — 시험(deep · impact 고치기 전 실패) → impact 적재기도 고침 → 커밋

## 5. 그 밖
- [x] R `PartAnalyzer::get_nv3d()` — 이력 변수 있는 실덱(bat1x26)으로 전후 대조 · 시험(고치기 전 10건 실패) → 커밋
- [x] P 「lasso 2.2.6」 표기 정정 — 내 문서 2곳 · 메모리 1곳을 lasso-python 2.0.3 으로(a9 원장 `release-verdicts.md:116` 은 알리기만)

- [x] 침식 요소 세 곳 판단(erode7) — 겉면 변형률은 고침(시험 고치기 전 36건 실패), 핫스팟 1차 훑기 · 세트 segments 는 보고만

## 6. 마감
- [x] 전체 시험 — C++(렌더 켠 33 · 끈 8) · 파이썬 여섯 패키지 830 · `test_post_analyze.sh` 71 통과
- [x] 실덱 회귀 한 번 더(작업 전 d2f0d6b 와 대조 — ElasticBeam · erode7 은 의도한 변경, 테이프 동률 번호는 FMA)
- [x] 소비자 알림 — a9 · kooremapper-4a 알림, pykoocae-53 에 `--parts` 질문(답 대기)
- [x] 메모리(새 작업 기록 · 옛 줄 정정) · 결정 기록 마감
- [x] 사용자 보고 — 고친 것 · 안 고친 것과 이유, 결정 셋을 물었다(push · 배포 / strain 이름표 / 타깃 색 범위)

## 7. push · 배포
- [x] push(`873a153` + 이 작업의 커밋, af0b301..9b3c081) — 사용자 승인으로
- [x] 판정 꾸러미 `/data/koopark/Post_v53/`(로컬 예행 어긋남 0) · pykoocae-53 에 v53 배포 요청
- [x] v53 배포 확인 — `check_v53.sh <새 SIF> v53` → `cmp_v53.py v52 v53 local` 어긋남 0(헤드리스 8a08d0c2…, VERSION 9b3c081)
- [x] v54(fc9cdb3 · 78573e6 · 문서) — 꾸러미 `/data/koopark/Post_v54/` 로컬 예행 어긋남 0 → push(9b3c081..da81ad3) → pykoocae-53 굽기 요청
- [x] v54 배포 확인 — `check_v54.sh <새 SIF> v54` → `cmp_v54.py v53 v54 local` 어긋남 0(헤드리스 bbaa491b…, VERSION da81ad3)
- [x] 포털 항목 7 — 포털 규칙(c5fa9403)대로 pyKooCAE 굽기 스크립트가 Post 판 해시 · release.json 을 쓴다(package_module.sh 는 그대로), 포털에 주인 알림

## 8. 사용자 결정 뒤 새 작업(v54 감)
- [x] deep `strain` 이름표를 실제 값으로(LS-PrePost 백엔드 = 유효 소성 변형률) — 부제 · field 하나인 폴더도 함께, 시험 · 실보고서로 확인
- [x] 타깃 렌더의 자동 색 범위를 타깃 파트 범위로(전 상태 · 적분점 최대 · fringe 종류별, 렌더 잡 · 파트별 단면 모두) — 시험 39건 · 실렌더 0 ~ 50.21

## 9. 「보고만」 다시 보기 — 없는 시계열을 0 으로 채우던 deep `_aggregate`(11-23)
- [x] 시험 먼저 — 운동만 있는 파트 · 응력만 있는 파트의 변형률 · 주응력 · 주변형률 · 속도 · 가속도가 None, result.json 이 null, 전체 변형률 최대, 보고서 σ₁ · σ₃ 순위 · 상세 카드
- [x] 고침 — `_aggregate` · `PartSummary` · `MotionData` 속도 · 가속도 · 보고서 JS 순위 거르기 · 요약 문구
- [x] deep 시험 전체 · 실덱(DynaAnalysis 파트 2 — 운동만) 보고서 전 · 뒤
- [x] 결정 기록 · 소비자 알림(result.json 의 peak_strain · peak_acc_mag 가 null 이 될 수 있다) — kooremapper-4a · a9

## 10. 「보고만」 다시 보기 — 파트별 단면의 면 없는 파트 · 미끄럼 영상 수(11-23)
- [x] 재현 — ElasticBeam 분석 파트 목록의 빔 파트 4 가 빈 화면 영상, 미끄럼 잡 「Done: 2/1」(배포판 v54 실렌더)
- [x] 고침 — 호출부에서 면 없는 파트를 알리고 뺀다, 기대 수에 미끄럼 영상
- [x] 실렌더 전 · 뒤(파트 1~3 · 미끄럼 영상 화소까지 같음) · C++ 시험 34 · 8
