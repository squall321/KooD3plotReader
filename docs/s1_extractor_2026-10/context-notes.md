# 컨텍스트 노트 — S1 경량 추출기

## 조사로 정한 것 (10-29)
- **기존 HDF5Writer 를 키우지 않는다.** 변위가 아니라 절대 좌표를 첫 상태 범위(+10%)로만 양자화하고, 넘으면 조용히
  잘라 델타 복원이 영구히 어긋난다. 응력 · 삭제 · 실제 ID 가 없고 `*_part_ids` 는 `Element.material_id`(GeometryParser 가
  채우지 않음)를 써서 미정 값이다. 운영 빌드는 `-DKOOD3PLOT_BUILD_HDF5=OFF`, SIF 에 libhdf5-dev 없음(h5py 3.16 은 있음).
- **스트리밍 API 가 없다.** `read_state(i)` 도 전체를 올린다. `for_each_state` 를 새로 둔다.
- **SurfaceExtractor 는 쓰지 않는다** — 셸을 중복 검사 없이 붙이고, 고유 절점 4개 요소를 `n[4..7]==n[3]` 꼴일 때만 사면체로 본다.
  StepForge 는 4개면 배치와 무관하게 사면체, 면 순서는 바깥 방향, 비다양체 · 미지원 꼴은 거절.
- **원형과 StepForge 의 차이** — 원형은 면 열쇠가 16비트(순번 65535 넘으면 겹침), 방향 미정, 전체 집합으로 셈.
  StepForge 는 파트별로 셈. 묶인 파트는 절점이 따로라 공유 면이 0 이면 같다(fd1418 `n_inter_part_shared=0`) → 전체로 세고 공유 수를 적는다.
- **SceneForge 리더는 지금 float32 `timestep_N/displacement` 만 읽는다** → float32 인코딩도 둔다.
- **SectionClipper 는 쓰지 않는다** — 꼭짓점 평균값만 내고 요소 ID 가 없다. t=0 기준 절단을 따로 짠다.
  사면체 고유 절점의 모서리는 6개 — 육면체 12 모서리를 중복 제거하면 (n1,n3) 이 빠진다.
- **운영 덱은 IV=1**(절점 속도), 상태 간격 약 1 µs → 상태 0 속도가 초기 속도.

## 덤으로 발견 (S1 과 별개, 고치지 않음)
- SectionClipper.cpp:148/200/268 · NodalAverager.cpp:388/434/464/507/526/545 가 삭제표의 **요소 순번**을 실제 요소 ID(`elem.id`,
  NARBS 가 덮어씀)와 견준다 → ID 가 연속이 아닌 덱에서 소프트웨어 단면 영상이 삭제 요소를 못 거른다. 별도 수정 과제.

## 1단계 구현·실측 (10-30)
- **운영 덱(Test_005 801e2b, /data HDD)**: rc 0, 4,952/4,952, 경고 0, RSS 52.8 MB, 17.5 분(두 번 읽기, CPU 2% — HDD I/O 대기).
  겉면 면 32,082 · 절점 23,012 · 요소 28,251(원형과 같음), 뒤집은 요소 0. 자세: 틈 0.0500 mm, 속도 5,424.38 mm/s, 법선각 0.0021°,
  평평함 6.5e-6 mm(d3plot 단정밀도 좌표 한계), 첫 접촉 9.2 µs.
- **lasso 독립 대조**(`check_s1_against_lasso.py`): 상태 0·1650·3301·4951 — 시각 일치, 변위 오차 ≤ 4.7e-4 mm(한계 대비 0.967),
  von Mises ≤ 0.018 MPa(0.996), 삭제 불일치 0. lasso 는 이 덱을 `state_filter` 만으로 열면 「negative dimensions」 로 죽는다 —
  원형처럼 `buffered_reading=True` + `state_array_filter` 여야 한다.
- **크기**: [16 상태, 전 항목] 청크로 789.5 MB. deflate 창(32 KB)이 한 상태(138 KB)를 못 넘어 시간 중복을 못 봤다.
  [64, 256, …] 로 바꿔 같은 값을 다시 담으니 변위 581 → 344 MB, von Mises 208 → 198 MB(잡음이 많아 거의 그대로) → 약 543 MB.
- **발산 덱**: 작은 시험 덱(Test_Cum26x3)은 마지막 상태에서 절점 283개가 약 5e9 mm 로 날아간다. q16 묶음 스케일이 그 값에
  묶여 오차 한계가 1.3e5 mm 까지 커진다 → 묶음 범위 > 장치 크기 10배면 경고하고 float32 를 권한다. 우리 리더와 lasso 는
  그 값도 float32 반올림 수준으로 같게 읽는다(버그 아님).
- **P-4 를 되돌린 것**은 단면 영상 작업 노트에 적었다(PSNR 16.6–32 dB).

## 빌드·시험에서 밟은 함정
- `scripts/build_module.sh` 는 `BUILD_DIR="${PROJECT_ROOT}/build"` 로 **공유 build/ 를 못 박는다.** 샌드박스에서 그대로 돌렸다가
  build/ 캐시(설치 경로·CAPI·뷰어·HDF5 경로)를 덮어 되돌렸다(설치 경로 /tmp/kood3plot_nuitka, CAPI·VIEWER ON 은 기존 산출물로 추정).
  이미지 빌드 경로 시험은 `git worktree add .work/wt_bm` 에서 한다.
- FindHDF5 는 CXX 전용 프로젝트에서 try_compile 이 「Unknown extension .c」 로 깨진다 → hdf5/serial 을 직접 찾는다.
- 개발 환경: `apptainer build --sandbox .work/sif_dev <운영 SIF>` 후 `--fakeroot --writable` 로 libhdf5-dev 설치(2.9 GB).
  새 def 와 같은 꼴이라 시험 결과가 운영과 맞는다.
- SIF 안 파이썬은 `PYTHONNOUSERSITE=1` — 아니면 호스트 ~/.local 의 h5py 가 끼어든다.

## DynaForge 이견 1차 반영 (10-30)
- **게이트 정의 = 리포트 정의.** unified_analyzer(SinglePassAnalyzer::extractVonMises)는 S1 과 같은 성분 자리
  (`solid_data[e*NV3D + 0..5]`)·같은 식이고, 상태마다 삭제된 요소를 뺀다(deletedMask, 1-based 순번). S1 게이트도 빼도록 고쳤다
  (양자화 범위에는 넣음). 운영 덱 두 런은 삭제 요소 0개라 결과가 같다.
- **리포트 대조**: 같은 모델의 다른 런(Test_Postprocess_v14 Run_20260522_103123_7ad7d9)에 새 판을 돌려 그 런의 deep 리포트
  `report/analysis_result.json`(5월 22일 판, 4,952 상태)의 `stress_history[].global_max` 와 견줬다 — 22파트 모두 상대차 ≤ 2.2e-10,
  최대 시각도 같다(리포트 23파트 중 23은 바닥이라 S1 에서 뺌). 옛 빌드 산출물이라 정답이 아니라 「같은 정의인가」 확인용.
  이 런에서 543.7 MB(새 청크), 166.6 초(페이지 캐시), 자세 틈 0.0500 mm·법선각 0.0008°.
- 곁파일 s1.json(sha256·bytes·parts·posture) · post_analyze.sh 색인 s1_index.json — DynaForge 가 cae00 에서 s1.h5 를 안 받고
  manifest 를 짓기 위해.
- §7 표를 구현대로 고쳤다 — 데이터셋은 initial_velocity·floor_point·floor_normal 셋, 나머지는 그룹 속성(+floor_layer_nodes).
