# 계약 C-3 — S1 경량 추출본 초안 (KooD3plotReader → DynaForge · SceneForge · StepForge)

**판** 초안 2 (2026-10-30 — 1단계 구현 실측 반영: §1 warnings 예, §5 발산 덱, §7 정밀도·실측) · **스키마** `kood3plot.s1` 판 1
**요청** KooRemapper `docs/requests/kood3plotreader-s1-extractor-request-2026-10-28.md` (§1–§8, 3481788 · 7818cbc)
**성격** 꼴을 먼저 맞추려는 초안입니다. 이름·뜻에 이견이 있으면 구현 전에 말씀해 주십시오. 바뀌면 판을 올립니다.

## 0. 한눈에

| 항목 | 정한 것 |
|---|---|
| 도구 | `s1_extract` — KooD3plotReader 의 C++ 도구. d3plot 을 이 저장소 리더로 **상태 하나씩 두 번** 읽는다(메모리 상한, 리더 하나) |
| 둘 자리 | 각도 run 폴더의 `Output/s1.h5` (d3plot · 리포트와 같은 폴더). `--output` 으로 바꿀 수 있다 |
| 배열 | 상태별 그룹이 아니라 **촘촘한 배열** `[상태, 항목, …]` — 원형의 메타데이터 43.8 MB 는 그룹 수천 개 탓이었다 |
| 인코딩 | 이름 붙은 두 가지 — `float32`, `linear_q16`(파트 묶음별 스케일). **시간 델타는 판 1 에 없다** → 넘침·예외 목록이 생기지 않는다. 복원 식은 파일 속성에 적는다 |
| 상태 솎기 | 보폭 · 시간 창. 고른 상태의 **원래 번호와 시각**을 함께 싣는다 |
| 게이트 | 파트마다 겉면 최대 · 전 요소 최대 · 「최대 요소가 겉면인가」 — **솎기와 무관하게 전 상태**로 셈 |
| 자세 | 초기 속도 · 바닥 평면(점 · 단위 법선 · 평평함 · 틈) · `first_contact_s = gap_over_speed` |
| 기준 단면 | 축마다 t=0 형상에서 자른 조각(재료와 함께 움직이는 절단) + 복원 식 — **2단계**(D-8 확정 뒤, 아래 §8) |
| 성패 | rc 0 = 파일 완성(경고는 속성 `warnings` 와 stderr), rc 1 = 실패(반쯤 쓴 파일은 남기지 않는다) |

## 1. 루트 속성

| 이름 | 꼴 | 뜻 |
|---|---|---|
| `schema` | str | `"kood3plot.s1"` |
| `schema_version` | int | 1 |
| `tool`, `tool_version` | str | `"s1_extract"`, 빌드 커밋(이미지 VERSION 과 같은 값) |
| `created_utc` | str | ISO 8601 |
| `source_d3plot` | str | 원본 d3plot 절대 경로 |
| `source_fingerprint` | str | 가족 파일 수 · 각 크기 · 제어부 앞 4 KiB 의 sha256 — 18 GB 전체 해시는 하지 않는다(값싸고 바뀌면 갈린다) |
| `deck_path`, `deck_sha256` | str | 같은 폴더의 키워드 덱(`*.k` 등, 리포트와 같은 찾기 규칙). 못 찾으면 빈 문자열 + 경고 |
| `units` | str | 예 `"mm, t, s, MPa"`. d3plot 은 단위를 싣지 않으므로 **잡이 `--units` 로 준다**. 안 주면 `"deck_units"`(미상) + 경고 |
| `surface_rule_id`, `surface_rule` | str | §3 규칙의 이름(`"deck-surface/stepforge-2026-10"`)과 전문 |
| `excluded_parts` | int[] | 겉면 · 게이트에서 뺀 환경 파트(예 바닥 23) |
| `selection_step`, `selection_window_s` | int, float[2] | 상태 솎기 설정(§4). 창이 없으면 `[-inf, inf]` |
| `warnings` | str[] | 경고 문장들(없으면 빈 배열). 예 — 마지막 가족 파일 끝의 덜 써진 상태, 발산 의심(§5), 덱 · 단위 · 바닥 미지정 |

압축은 deflate 6 + shuffle, 파일은 `libver = latest`(HDF5 1.10 꼴)로 만든다.

## 2. `/mesh` — 겉면 (각도마다 같다)

| 데이터셋 | 꼴 | 뜻 |
|---|---|---|
| `node_ids` | uint32 [Ns] | 겉면 절점의 **실제 절점 ID**, 오름차순 |
| `coords0` | float32 [Ns,3] | 초기 좌표 |
| `node_group` | uint16 [Ns] | 절점의 스케일 묶음 번호(§5) — 그 절점을 쓰는 첫 겉면의 파트 순번 |
| `faces` | int32 [Nf,4] | `node_ids` 의 순번. 넷째가 −1 이면 삼각형. **바깥 방향**(요소 기준 바깥, 부호 부피로 확인) |
| `face_part_id` | int32 [Nf] | 면의 파트 ID |
| `face_elem_index` | int32 [Nf] | `elem_ids` 의 순번 |
| `elem_ids` | uint32 [Ne] | 겉면을 가진 요소의 **실제 요소 ID** |
| `elem_part_id` | int32 [Ne] | 그 요소의 파트 ID |

속성: `n_device_nodes`, `n_device_elems`(제외 파트를 뺀 솔리드), `n_inter_part_shared_faces`(§3), `n_shell_elems_skipped`.

원형과의 차이 — `face_part_id` · `elem_part_id` 를 int32 로(파트 ID 255 초과 대비), `face_elem_id` 는 `elem_ids[face_elem_index]` 로 같은 값을 얻을 수 있어 뺐다.

## 3. 겉면 규칙 (StepForge `core/deck_surface.py` 와 같은 꼴)

1. 대상 — 제외 파트를 뺀 **솔리드** 요소. 셸 · 두꺼운 셸은 판 1 에 넣지 않고 수를 `n_shell_elems_skipped` 에 적는다(있으면 경고).
2. 요소 꼴 — 고유 절점 8 = 육면체, 4 = 사면체(어떤 칸 배치든), 6 = 쐐기, 5 = 피라미드. 그 밖은 육면체 6면의 고리에서 연달아 겹친 절점(감김 포함)을 지운 뒤 고리 크기로 가리고, 가릴 수 없으면 **실패**(StepForge 의 `Unsupported` 와 같다).
3. 면 순서 — 육면체 `(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)`, 사면체 `(0,3,2),(0,2,1),(0,1,3),(1,2,3)`(첫 등장 순). 둘 다 양의 야코비안에서 바깥 방향. 고유 절점 3개 미만인 고리는 버린다. 부호 부피가 음수인 요소는 면을 뒤집는다.
4. 겉면 — 정렬한 고유 절점 튜플을 열쇠로, 대상 솔리드 **전체에서** 한 번만 나온 면. 셋 이상 나오면 **실패**(비다양체).
   - StepForge 는 파트별로 센다. 두 파트가 면을 공유하지 않으면(묶인 파트는 절점이 따로라 공유가 없다) 결과가 같다. 공유 면 수를 `n_inter_part_shared_faces` 에 적어, 0 이 아니면 받는 쪽이 알 수 있게 한다.
5. 열쇠는 64비트 정수 셋 이상의 튜플이라 원형의 「순번 65535 넘으면 겹침」 이 없다.

## 4. `/states` — 고른 상태

| 데이터셋 | 꼴 | 뜻 |
|---|---|---|
| `state_index` | int32 [T] | 고른 상태의 **원래 번호**(d3plot 상태 0 부터) |
| `time` | float64 [T] | 그 시각(초 — 덱 시간 단위) |
| `displacement` | §5 [T,Ns,3] | 겉면 절점 변위 = 현재 좌표 − `coords0` |
| `von_mises` | §5 [T,Ne] | 겉면 요소 von Mises (적분점 0 층, `√(½Σ(σi−σj)² + 3Στ²)`) |
| `alive` | uint8 [T,Ne] | 1 = 살아 있음, 0 = 삭제. 삭제표가 없는 덱(MDLOPT≠2)은 전부 1 + 속성 `deletion_available=0` |

속성: `n_states`(= T, 원형 리더 호환), `n_states_source`(d3plot 전체 상태 수).

**솎기.** `--state-step N`(기본 1) · `--time-window t0,t1`(초). 창 안의 첫 상태부터 N 개마다 고르고, **창의 마지막 상태는 늘 넣는다**(SceneForge 의 「보폭 + 마지막」 과 같다). 고른 결과는 `state_index` · `time` 이 그대로 말한다.

청크는 `[64 상태, 256 항목, …]` — 시간 쪽으로 길게 잡아 deflate 가 이웃 상태의 중복을 보게 했다(운영 덱 변위 581 → 344 MB).
상태 하나만 읽으면 청크 여러 개(64 상태분)를 풀어야 하므로, 순차 재생 · 일괄 변환은 64 상태씩 읽거나 청크 캐시를 넉넉히
잡으십시오(h5py `rdcc_nbytes` 64 MiB 이상).

## 5. 인코딩 — 이름과 복원 식 (파일 안에 그대로 적는다)

인코딩이 붙는 데이터셋마다 속성 셋을 둔다.

| 속성 | 뜻 |
|---|---|
| `encoding` | `"float32"` 또는 `"linear_q16"` |
| `decode` | 사람이 읽는 복원 식 문장 (아래 그대로) |
| `scale_table`, `offset_table` | `linear_q16` 일 때 스케일 · 오프셋 데이터셋 경로 |

- **`float32`** — 값 그대로. `decode = "value = stored"`.
- **`linear_q16`** — 저장은 uint16. 묶음 g 의 스케일 표로
  `value = offset[g, c] + scale[g, c] × q` (c 는 성분, von Mises 는 c 없이 `[g]`).
  - 변위의 g 는 `/mesh/node_group[i]`, von Mises 의 g 는 요소의 파트 순번(`/parts` 표의 줄).
  - 표: `/states/displacement_offset` · `displacement_scale` float64 [G,3], `/states/von_mises_offset` · `von_mises_scale` float64 [P].
  - 스케일은 **1차 읽기에서 전 상태(솎기 전)의 묶음별 최소 · 최대**로 정한다: `offset = min`, `scale = (max − min) / 65535`(범위 0 이면 1). 그래서 넘침이 없고, 최대 오차는 `scale / 2`.
  - 피크 보존 — 묶음의 최댓값은 q = 65535 에서 정확히(반올림 오차 내로) 되돌아온다.
- **시간 델타는 판 1 에 없다.** 원형에서 델타 하나만 넘쳐도 단계를 통째로 저장해 델타가 거의 쓰이지 않았다. 시간 축 중복은 청크(16 상태) + shuffle + deflate 가 줄인다. 크기가 모자라면 판 2 에서 이름 붙은 델타 인코딩을 더한다.
- 기본은 `linear_q16`, `--precision float32` 로 바꾼다. SceneForge 리더가 지금 float32 만 읽는 것을 압니다 — 그 동안은 float32 + 솎기로 시작하실 수 있습니다.
- **발산한 덱 (구현 중 실측).** 해석이 발산해 절점이 날아가면(작은 시험 덱 Test_Cum26x3 마지막 상태 — 절점 283개가 약 5e9 mm)
  그 파트 묶음의 범위가 커져 q16 오차 한계(scale/2)가 함께 커진다(그 덱 파트 8 은 1.3e5 mm). 값은 계약대로지만 쓸모가 없다.
  그래서 묶음 변위 범위가 장치 크기의 10배를 넘으면 `warnings` 에 파트 · 범위 · 오차 한계를 적고 float32 를 권한다.
  넘친 값만 따로 적는 예외 목록은 판 2 후보로 둔다(정상 덱에서는 필요가 없었다).

## 6. `/parts` — 파트 표와 게이트

| 데이터셋 | 꼴 | 뜻 |
|---|---|---|
| `part_id` | int32 [P] | 장치 파트 ID (제외 파트 빼고) |
| `name` | str [P] | 덱의 파트 이름(못 찾으면 빈 문자열) |
| `n_surface_elems` | int32 [P] | |
| `vm_max_all`, `vm_max_all_elem_id`, `vm_max_all_time` | float64, uint32, float64 [P] | 그 파트 **전 요소 · 전 상태** 최대 |
| `vm_max_surface`, `vm_max_surface_elem_id`, `vm_max_surface_time` | 〃 | 겉면 요소만 |
| `max_elem_on_surface` | uint8 [P] | 전 요소 최대가 겉면 요소인가 |

게이트 판정(같음/이하)은 DynaForge 가 이 값으로 합니다. 값은 솎기 · 양자화 전 원값입니다.

## 7. `/posture` — 각도별 자세 재료 (§8)

| 이름 | 꼴 | 뜻 |
|---|---|---|
| `initial_velocity` | float64 [3] | 장치 절점 평균 초기 속도(덱 단위, mm-s 면 mm/s) |
| `velocity_source` | str 속성 | `"d3plot_state0"`(절점 속도가 실린 덱 — 운영 덱은 IV=1) · `"deck_initial_velocity"` · `"displacement_difference"`(앞 둘이 없을 때, 상태 0→1 차분) |
| `floor_part` | int 속성 | 바닥 파트 ID(`--floor-part`, 예 23) |
| `floor_point`, `floor_normal` | float64 [3] | 바닥의 **기기 쪽 면** 한 점(그 층 절점 무게중심)과 기기 쪽 단위 법선 |
| `floor_flatness` | float64 | 그 층 절점의 평면 잔차 최대 |
| `gap` | float64 | 기기 절점에서 바닥 평면까지 최소 거리(t=0) |
| `first_contact_s` | float64 | `gap / |initial_velocity|` |
| `first_contact_basis` | str 속성 | `"gap_over_speed"` |
| `velocity_normal_angle_deg` | float64 | `initial_velocity` 와 `−floor_normal` 사이 각 — SceneForge 거절 기준(0.1°)을 미리 볼 수 있게 |

평면은 바닥 절점에 주성분 분석으로 법선을 잡고, 법선 방향 투영으로 층을 나눠 기기에 가장 가까운 층을 쓴다. 바닥 파트를 주지 않으면 `/posture` 를 쓰지 않고 경고한다.

- 좌표는 d3plot 의 것이다. d3plot 은 좌표를 단정밀도로 담아, 100 mm 규모에서 `floor_flatness` 가 약 1e-5 mm 아래로 내려가지 않는다
  (운영 덱 6.5e-6 mm — DynaForge 가 덱 텍스트에서 잰 6e-7 mm 보다 크다). 판정에 그보다 작은 값이 필요하면 덱 값을 쓰십시오.
- 운영 덱 실측: `gap` 0.0500 mm, `|initial_velocity|` 5,424.38 mm/s, `first_contact_s` 9.2 µs, `velocity_normal_angle_deg` 0.0021°
  (DynaForge 의 덱 `*INITIAL_VELOCITY` 기준 0.007° 와 같은 자릿수 — 여기서는 상태 0 의 장치 절점 평균 속도를 쓴다).

## 8. `/sections` — 기준 단면 조각 (D-8) — 2단계

**1단계 파일에는 없다.** DynaForge 계획서에서 D-8 은 권고(미확정)이고, 축 셋을 전 상태로 담으면 파일이 겉면만일 때보다 크게
늘 것으로 어림된다(단면 하나에 절점 · 다각형이 수천 단위). D-8 이 확정되면 아래 꼴로 넣고 크기를 재서 알려 드린다 — 그때
`--section-axes` 기본값(전부 · 끔)도 함께 정한다.

축마다 그룹 하나 — `/sections/x`, `/sections/y`, `/sections/z`(`--section-axes`).

- 평면: `plane_point`(기본 = 제외 파트를 뺀 장치 솔리드 초기 상자 가운데 — 운영 단면 영상의 `position: center` 와 같은 자리, `--section-point` 로 바꿈) · `plane_normal`(축 방향).
- **t=0 형상에서 자른다.** 평면을 가로지르는 요소마다, 평면과 만나는 모서리의 두 끝 절점과 비율 t 로 다각형 꼭짓점을 정한다. 이 절단은 재료와 함께 움직인다 — LS-PrePost 는 매 상태 고정 평면으로 자르므로, 변형이 크면 모양이 조금 다르다(낙하 덱은 변형이 작다).

| 데이터셋 | 꼴 | 뜻 |
|---|---|---|
| `node_ids`, `coords0` | uint32 [Ms], float32 [Ms,3] | 잘린 요소들의 절점 |
| `vertex_edge` | int32 [Mv,2] | 꼭짓점이 놓인 모서리의 두 절점(이 그룹 `node_ids` 순번) |
| `vertex_t` | float32 [Mv] | 꼭짓점 = `(1−t)·x[a] + t·x[b]` |
| `poly_offsets` | int32 [Np+1] | 다각형 k 의 꼭짓점 = `vertex_*[poly_offsets[k] : poly_offsets[k+1]]`(평면 위 각도 순) |
| `poly_elem_id`, `poly_part_id` | uint32, int32 [Np] | 다각형이 나온 요소와 파트 |
| `displacement` | §5 [T,Ms,3] | 그 절점들의 변위(인코딩 · 고른 상태는 `/states` 와 같다) |
| `von_mises`, `alive` | §5 [T,Np], uint8 [T,Np] | 그 요소의 값 |

복원 — 상태 j 의 꼭짓점 위치 = `(1−t)·(coords0[a] + u[j,a]) + t·(coords0[b] + u[j,b])`, 색은 그 다각형 요소의 von Mises.

## 9. 후처리 잡에 얹기 · 성패

- 단독 단계로 둔다: `s1_extract <d3plot> --output <run>/Output/s1.h5 --floor-part 23 --exclude-parts 23 --units "mm, t, s, MPa" [--state-step N] [--time-window a,b] [--precision float32]`. 후처리 잡에서는 `post_analyze.sh --s1-opts "--floor-part 23 --units mm,t,s,MPa"` 로 켠다(기본 끔).
  - deep report 의 읽기에 얹지 않은 까닭: 그 경로는 상태를 전부 메모리에 올린다(이 덱 RSS 34 GB). S1 은 상태를 하나씩 두 번 읽어 수백 MB 안에서 끝난다. 읽기 두 번의 값은 각도당 수 분(원형 2–4 분과 같은 자릿수)이다.
- 종료 코드: 0 = 완성(경고는 `warnings` · stderr 의 `WARNING:` 줄), 1 = 실패. 임시 이름으로 쓰고 끝나면 바꿔 단다 — 실패 때 반쯤 쓴 `s1.h5` 가 남지 않는다.
- 상태를 다 못 읽으면(가족 파일 잘림 · 누락 · 메모리) **실패**다. K-2 수정과 같은 리더 규칙을 쓴다. 마지막 파일 끝의 덜 써진 상태는 경고로 남기고 앞 상태로 만든다.

## 10. 요청 §6 · §8 질문에 대한 답

1. **기존 `HDF5Writer` 를 키울지** — 새 꼴로 갑니다. 기존 꼴은 변위가 아니라 절대 좌표를 첫 상태 범위로만 양자화하고, 범위를 넘으면 조용히 잘라 델타 복원이 영구히 어긋납니다. 응력 · 삭제 · 실제 ID 도 없고, 운영 빌드에서는 꺼져 있습니다.
2. **기준 단면 조각의 꼴** — §8.
3. **일정 · 순서** — 계약 초안(이것) → 구현 1단계(`/mesh` · `/states` · `/parts` · `/posture`, **끝**) → 후처리 잡 연결(`post_analyze.sh --s1`, **끝**) · SIF(libhdf5 추가, 다음 이미지) → 2단계(`/sections`, D-8 확정 뒤). P-3 은 끝났고, P-4 는 한 세션에 이어 찍으면 둘째 영상부터 출력이 바뀌어(PSNR 16.6–32 dB) 기본값 유지 결정에 따라 하지 않았다.
4. **자세 재료를 같은 읽기에서** — 냅니다(§7). 운영 덱은 d3plot 에 절점 속도가 실려 있고(IV=1) 상태 간격이 약 1 µs 라 첫 접촉(약 9 µs) 전 상태 0 속도가 곧 초기 속도입니다.
5. **둘 자리** — `Run_*/Output/s1.h5`. run 과 함께 옮겨지고 지워지며, 리포트(`Output/report/`)와 같은 폴더이고, `<RESULT_DIR>/output` 마운트 확인 범위 안입니다.

## 11. 받는 쪽에 달라지는 것

- SceneForge `s1.py` — `states/timestep_i/displacement` 그룹 대신 `/states/displacement[i]` 배열, 시각은 `/states/time[i]`. `n_states` 속성은 남긴다. `linear_q16` 은 §5 식으로 되돌린다.
- DynaForge 게이트 — `result_*.json` 대신 `/parts` 표.
- StepForge 대조 — `/mesh/node_ids` · `faces` 를 그대로 쓰시면 됩니다(규칙 이름 `surface_rule_id`).
