# 컨텍스트 노트 — 단면 영상 · 상태 읽기 (2026-10-28)

결정과 그 까닭. 실험물은 `.work/k1_lspp/`(LS-PrePost 단독), `.work/k1_ua/`(작은 덱 실렌더),
`.work/k1_t005/`(운영 덱), `.work/k2_family/`(가족 파일 꼬리 점검 도구·수정 전 빌드).

## K-1 — 원인을 LS-PrePost 안에서 찾았다

- LS-PrePost 출력에는 아무 단서가 없다(정상·결함 런 로그가 같다). 바이너리가 strip 되지 않아 역어셈블로 따라갔다.
  - `CheckMemory`(0x9fbdd0): `max_memory = wxGetFreeMemory() / 10 * 8`.
  - `wxGetFreeMemory`(0x6283e20): /proc/meminfo 를 fgets 두 번 → `MemFree: %lu`, 다음 줄 `Buffers: %lu`, 다음 `Cached: %lu`.
    3.14 이후 커널은 셋째 줄이 MemAvailable 이라 두 sscanf 가 실패하고 지역 변수가 초기화되지 않은 채 더해진다.
  - `AllocStateMemory`(0x9fa1d0): `max_memory != 0 && 상태번호 > 0 && total + size > max_memory` 이면 그 상태에 NULL.
    `AllocModelMemory` 는 `max_memory_input == 0`(설정 없음)일 때만 예산을 다시 잰다.
  - `ProcessConfigMaxMemory`: lsppconf `max_physical_memory` 값을 G/M/K 접미사로 읽고 `max_memory_input = 1`.
  - `LSPP_STATE_MEMORY=off` 는 `nalloc_statememory = 1` — 시험해 보니 작은 예산과 함께면 여전히 0. 처방 아님.
- 예산 초과는 단조다(총량이 줄지 않으니 k 번째부터 끝까지). 그래서 「어느 프레임부터 끝까지」 모양이 나온다.
- 재현: `$HOME/LSTC/LS-PrePost4.12/lsppconf` 에 `max_physical_memory = 20M` → 465 상태 덱 마지막 프레임 0(매번).
  한 줄짜리 lsppconf 도 읽는다(종료 때 전체 설정으로 다시 쓴다).
- **예산을 낮게(예: MemAvailable 기준) 잡는 안을 버린 까닭**: 넘는 순간 0 이 된다. 안전한 낮은 값이 없다.
  크게 주면 「운 좋은」 기존 정상 런과 같은 동작이고(운영 덱 RSS 4.5 GB), 진짜 메모리 부족은 abort(134)로 드러난다
  (주소 공간 1.6–1.8 GB 에서 abort, 1.9 GB 이상 정상 — 조용한 0 경계는 찾지 못했다).
- **색 기반 0 프레임 검출을 버린 까닭**: B1 결함 프레임은 순청색, 20M 재현은 연청색(59,59,253)으로 서로 다르고,
  정상 전체 모델 프레임도 98.6% 가 최저색이다. 오탐·누락이 모두 난다. 대신 종료 코드 + ffprobe 로 abort 를 잡는다.
- 실행 명령의 종료 코드가 `wait $XVFB_PID` 것이었다 → LS-PrePost abort 도 성공. `LSPP_RC=$?; …; exit $LSPP_RC`.
- 작업자 HOME 준비를 fork 전으로 옮겼다(렌더 스레드가 여럿일 때 fork 자식의 파일 입출력은 위험).
- lsppconf 경로는 판(4.12)에 묶인다. 이미 있는 `LSTC/LS-PrePost*` 디렉터리에도 같이 적어 판이 바뀌어도 둘째 실행부터는 덮인다.
- 공용 `/tmp/lspp_worker_*` 는 지우지 않는다(다른 렌더가 쓴다 — auto mode 도 막았다). 시험은 컨테이너 /tmp 를 `.work` 로 묶었다.

## K-2 — 판정 규칙

- 실제 상태 크기는 삭제 테이블(DELNN)을 포함한다. `find_states`·`test_family_file` 예제는 DELNN 을 빼서 틀린 값을 낸다(이번 범위 밖).
- 실덱: 운영 덱 249 가족 파일 전부 상태 뒤 EOF 표지, 꼬리 310–424 워드. Test_Cum26x3 은 중간 파일 EOF 표지·꼬리 476,
  마지막 파일만 덜 써진 상태(683,626 워드, 시간 0.000469648). D3plotWriter 는 표지 없이 경계에서 끊는다(꼬리 0).
- 파서가 EOF 표지를 크기 검사보다 **먼저** 보게 바꿨다. 예전 순서면 표지+패딩이 상태 하나보다 짧을 때 「데이터 모자람」 으로 기록돼
  패딩이 512 를 넘는 덱에서 오탐할 수 있었다.
- 규칙: 중간 가족 파일이 「데이터 모자람」 으로 끝났고 꼬리 ≥ 512 워드 → 예외. 마지막 파일이면 경고. 기본 파일은 판정 안 함
  (상태 시작 위치 계산이 덱마다 달라 오탐 위험).
- 한계: 상태 경계에서 정확히 잘린 중간 파일은 꼬리로 못 잡는다. 상태 크기 < 512 워드인 아주 작은 모델은 잘림과 패딩을 못 가른다.
- 번호 구멍: FileFamily 가 첫 누락에서 멈출 때 디렉터리를 한 번 훑어 뒤 번호가 있으면 기록, 읽는 쪽이 예외.
- `init_state_cache`(get_num_states·get_time_values)도 같은 규칙 — 건너뛰면 상태 수가 전체 읽기와 갈린다.
- 운영 덱을 12 GiB 아래 분석하면 이제 20.8 초에 rc 1 「d3plot67: 메모리 부족(std::bad_alloc)」. 이 덱은 상태를 다 올리면
  약 33 GB 라 이 상한으로는 원래 분석이 안 된다 — 스트리밍 분석은 별도 설계 과제.

## K-3

- 작업자 풀 = min(num_threads, 가족 파일 수 − 1), 호출 스레드도 작업자. `pool.emplace_back` 의 std::system_error 를 잡고
  띄운 만큼으로 계속. RLIMIT_NPROC=1 자식 프로세스 시험으로 확인(수정 전: std::async 가 system_error 를 던짐).
- 첫 실패에서 남은 파일을 집지 않는다(efd6c6c).

## K-4

- rc 3 = 분석 결과는 썼지만 렌더류 실패. 재귀 모드의 rc 2(스캔 불완전)와 겹치면 1 > 3 > 2.
- post_analyze.sh Step 1 은 `if unified_analyzer …` 로 0 아니면 FAIL — rc 3 도 FAIL 로 센다(분석 전용 설정이라 실제로는 안 남).
- koo_deep_report 는 rc 3 을 성공으로 보고 FAILED 줄을 `render_warnings` 에. 진행 출력(FAILED …)은 stdout 으로 나와 둘 다 훑는다.
- GUI(gui/app.py)는 koo_deep_report 를 감싸므로 rc 3 을 직접 보지 않는다.

## 커밋을 나눈 방법

- K-2 와 K-4 가 `UnifiedAnalyzer.cpp` 에, K-4 와 P-1 이 `d3plot_reader.py` 에 섞여 헝크 단위 패치(`git apply --cached`)와
  `git hash-object` + `update-index` 로 나눴다. 다른 세션이 koo_sphere_report 를 고치는 중이라 `git stash`·`reset --hard` 금지.
- K-4 커밋 메시지의 「수정 전 3건 FAIL」 을 2건으로 바로잡을 때 `commit-tree` + `update-ref` 로 작업 트리를 건드리지 않았다.

## 부수 발견 (고치지 않음)

- `cmake --build build`(대상 없이)는 추적되는 `vis-app-net/native/linux-x64/libkood3plot_net.so.1.0.0` 를 덮어쓴다 — 되돌렸다.
  build/ 는 대상 지정 빌드만 할 것.
- 시험 켠 빌드에서 `test_section_center_mode` 가 꺼진 `kood3plot_section_render` 를 링크해 실패한다(기존 문제).
- 호스트 빌드 바이너리는 glibc 2.39 라 SIF(2.35) 안에서 못 돈다 — SIF 안에서 `.work/build_sif` 로 빌드해 시험했다.

## P-3 · P-4 (10-29, 사용자 결정 「기본값 유지, 내부 개선만」)

- **P-3 반영(aa5883f).** LS-PrePost `anim incr N` — 465 상태 → 보폭 5 → 93 프레임(렌더 잡·파트 단면, SIF 실렌더).
  보폭은 세션 안에서 유지된다. 시간 창 `anim first/last` 는 넣지 않았다 — 함께 주면 첫 프레임이 현재 화면(상태 0)이고
  그 뒤가 first+N(1-based)부터라 어긋난다(100–300 · 보폭 5 → 프레임 0, 104, 109 … 294, 시각으로 대조).
- **P-4 되돌림 — 한 세션에 이어 찍으면 둘째 영상부터 출력이 바뀐다.** 파트 하나(x·z 단면 + 등각 클립)를 옛 방식(보기마다
  세션)과 새 방식(파트당 세션 하나)으로 찍어 PSNR 로 견줬다(`.work/p4_verify/`): section_x 동일(inf), section_z 16.6 dB,
  iso_clip_x 32.4 dB, iso_clip_z 29.9 dB. 둘째부터 범례 범위(옛 5.514e10 → 새 8,138 — 대상 파트만)와 확대·보는 범위가
  달라진다. 앞 보기의 선택·범위·확대 상태가 샌다. `movie` 자체는 늘 첫 상태부터 찍는다(되감기 불필요 — 시각으로 확인).
  새 판이 더 읽기 좋아 보여도 운영 영상 모양을 말없이 바꾸는 일이라 하지 않았다. 하려면 보기 사이에 범위·선택·카메라를
  초기화하는 명령을 찾아 PSNR inf 를 맞추거나, 모양 변화를 사용자가 받아들여야 한다. DynaForge 실측 이득은 NVMe 7–10%.
