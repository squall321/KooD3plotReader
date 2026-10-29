# 기존 단면 영상 점검 — 이 머신 /data (2026-10-29)

**범위** 사용자 결정(10-28): 이 머신 `/data` 만, 읽기 전용, 의심 목록만 보고. 다시 그리기는 하지 않았다.
**도구** `zero_frame_check.py`(이 폴더) — 마지막 프레임 범례로 판정. 결함(LS-PrePost 상태 메모리 예산 초과)은
단조라 영상이 0 이면 마지막 프레임이 반드시 0 이다. 범례 글자 줄을 줄마다 배경을 빼 알파로 바꿔 견주고(같은
글자면 배경과 무관하게 같은 그림), 모든 줄이 같으면 「균일」, 그 줄이 0 프레임 견본(DynaForge R0_seed20M_vm_z,
1280×720)의 `0.000e+00` 과 같으면 「0」. 기준 세트 10장으로 맞췄다(0 프레임 ZERO, 정상 OK, 다른 해상도 0 프레임은
UNIFORM?, abort 영상 ERROR).

🔴 「범례가 모두 같으면 결함」 만으로는 안 된다 — `warpage_study/case_lam_sym` 개관 3개는 범례가 전부 1.360e-01 이고
「at elem# 50」 인 **실제 균일 응력장**이다. 값이 0 이고 `at node# 0` 이어야 결함이다.

## 결과 — 후보 1,242개 (`find /data -name '*.mp4'` 4,148개 중 렌더 산출 이름)

| 판정 | 수 | 내용 |
|---|---|---|
| LS-PrePost 영상 | 3 | `warpage_study/case_lam_sym/report/renders/overview_{x,y,z}.mp4` (2026-03). 균일장(0.136, elem#) — **결함 아님** |
| 소프트웨어 래스터라이저 영상 | 1,239 | 「Smart Twin Cluster」 표식·전 상태 공통 범례. K-1 은 LS-PrePost 결함이라 **해당 없음** |

**K-1(응력 0) 의심 영상: 0개.** 운영 LS-PrePost 단면 영상은 이 머신 /data 에 거의 남아 있지 않다(노드·납품처).

## 덤 — 소프트웨어 영상의 프레임 수 (K-2 계열, 상태가 잘린 채 렌더)

소프트웨어 렌더러는 `max_frames` 로 솎으므로 프레임 수 = 상태 수가 아니다. 같은 캠페인 런끼리 견줬다.

| 캠페인 | 프레임 | 영상 수 |
|---|---|---|
| Test_Postprocess_v14 (4,952 상태 덱) `…/Output/report/` | 4,952 | 480 |
| Test_Postprocess_v14 `…/Output/report_20260522/` | **1,980** | 479 |
| Test_Postprocess_v15_SeparateJob | 497 | 120 |
| single/admin (verify_drop2_828 · RRVerify_ok_828) | 497 | 144 |
| Test_HotspotKeys_v118 | 497 | 15 |

**의심(낡은 산출물): v14 의 `report_20260522` 폴더 20개.** 1,980 = 가족 파일 99개 × 20 상태 — 가족 파일을
d3plot99 까지만 읽던 옛 결함(9f6c4e9 에서 고침) 시절 산출물로, 시간 이력의 40% 만 그렸다. 같은 런의 `report/`
는 4,952 프레임으로 온전하다. 런마다 일정한 값이라 무작위 잘림(K-2 의 bad_alloc 꼴)은 아니다. 지울지는 사용자 판단.

- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_094055_9f4583/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_094238_01adb3/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_100552_e154f5/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_101035_f6d37c/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_103123_7ad7d9/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_103441_ff67d2/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_105916_4cef8b/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_110208_2e6007/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_112129_b3d3f7/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_112947_a728f4/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_114643_d6aa5a/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_115255_42bbae/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_121046_372128/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_121839_681885/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_123610_43521c/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_124415_f45bb9/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_125912_6c4a61/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_130900_57248a/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_132307_0d0978/Output/report_20260522`
- `/data/koopark/Test_Postprocess_v14/output/Run_20260522_133556_0fd5fd/Output/report_20260522`
