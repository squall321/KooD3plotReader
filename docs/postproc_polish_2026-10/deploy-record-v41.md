# v41 배포 기록 (2026-10-25)

소스 `282630b` · RELEASE_RC=0 · 02:56Z 완료.
빌드·배포는 상류(pykoocae-53)가 사용자 승인으로 표준 스크립트
(`serviceApptainers/BuildSmartTwinPostprocessorOnly.sh` → `apptainer/build.sh both`)
로 수행. 우리 쪽은 **검증 담당**.

## 배포 지점 — 4곳 전부 동일 바이트 (직접 sha256 대조)

| 지점 | headless | GUI |
|---|---|---|
| `apptainer/` (빌드 산출) | `6176ff66c5cf325d` | `5ccd0c6f3702cb87` |
| `/data/SmartTwinPostprocessor` (NFS) | `6176ff66c5cf325d` | `5ccd0c6f3702cb87` |
| head `/opt/apptainers` | `6176ff66c5cf325d` | `5ccd0c6f3702cb87` |
| `KooSlurmInstallAutomationRefactory/apptainer/compute-node-images` | `6176ff66c5cf325d` | `5ccd0c6f3702cb87` |

**🔴 node001·node002 의 노드 로컬 `/opt/apptainers` 는 아직 v40(`ec35274`).**
VM 이 10-19 부터 꺼져 있어 못 바꿨다. `deploy_from_sif.sh` 는 NFS 만 갱신하고
KooChainRun(`DEFAULT_SIF_PATH`)·smarttwin-tool(`STMC_POST_SIF`)은 **노드 로컬**을
읽으므로, 켜진 뒤 `.work/deploy_2026-10/deploy_nodes.sh` 로 따로 교체해야 한다.

## 롤백 지점 (v40 = `11901033611cc529`, 둘 다 대조 확인)
- `/opt/apptainers/SmartTwinPostprocessor_backup_20261025_025350.sif` (+ GUI 동일 접미사)
- `/data/SmartTwinPostprocessor/SmartTwinPostprocessor_backup_20261025_024925.sif`
- `/data/SmartTwinPostprocessor/hostdirs_backup_20261025_024925.tar.gz` (551 MB)
- tar: `/data/SmartTwinPostprocessor/SmartTwinPostprocessor_20261025_v41.tar.gz` (551 MB)

## 검증 결과

`.work/deploy_2026-10-25/verify_deck.sh` — **헤드리스 15/15 ✓ · GUI 9/9 ✓**
(같은 스크립트로 v40 은 **15/15 ✗** — known-bad 기준선)

| 항목 | v40 `ec35274` | v41 `282630b` |
|---|---|---|
| VERSION 각인 | ✗ | ✓ |
| ⑤ `python3 -m koo_scatter_report` | ✗ No module | ✓ |
| ③ `--section-view-center` 노출 | ✗ | ✓ |
| 6패키지 import | ✗ scatter 실패 | ✓ 6/6 |
| ② `batch --config` 적용 | ✗ 무시, CWD 로 | ✓ output.directory |
| ② CWD 무오염 | ✗ `single_report` 생성 | ✓ |
| ③b `center_mode=peak` | ✗ 로그 없음 | ✓ state 22 / 310.404 |
| ③b aabb ≠ peak | ✗ 둘 다 `-10.025` | ✓ `-10.025` / `-2.300` |
| ③a 상대 `output_dir` | ✗ | ✓ 출력 폴더로 |
| ③a CWD 무오염 | ✗ `renders` 생성 | ✓ |
| ①④ sphere 헬퍼 5종 | ✗ 전부 없음 | ✓ 전부 |

③b peak 값이 2026-10-18 수기 검증과 정확히 일치 (state 22 / 310.404 / z=-2.300).
상류 병행 점검: 같은 빠른 4건 + 보고서 패키지 120파일이 양쪽 SIF 에서 HEAD 와 동일.

## 이번 릴리스 내용
① `fc875f5` sphere null 가드 — 0 위장 제거, 평균 50% 희석 수정
② `4faaede` deep `batch --config` 무음 무시
③ `9947ab5` 단면뷰 상대 `output_dir` + `center_mode: peak`
④ `4b04c1f` sphere 핫스팟 3D 캔버스 호버
⑤ `4405edc` SIF `%environment` PYTHONPATH 6개 (+ `%test` 6패키지로 강화)
⑥ `282630b` `CMAKE_EXPORT_COMPILE_COMMANDS ON`

## CLI 변화 — MCP 측 통보됨
`koo_deep_report` 에 `--section-view-center {aabb,peak}` 추가.
지난 릴리스("변화 없음 → 재생성 불요")와 다르다. 상류가 smarttwinmcp-c8/-4c 에 전달.
나머지 5개 도구의 `--help` 는 동일.

## 검증 도구에서 나온 결함 2건 (같은 부류 — 기록해 둘 것)
둘 다 **멀쩡한 빌드를 결함으로** 또는 **결함을 합격으로** 보고할 수 있었다.
검사 결과가 상식과 어긋나면 제품보다 **검사를 먼저 의심한다.**

1. **파이프 종료 상태** — `cmd 2>&1 | grep` 의 종료 상태는 grep 것이다.
   출력 없는 성공 → ✗, 에러 뱉는 실패 → ✓ 로 뒤집혔다.
   → 출력용 `run()` / 판정용 `chk()`(파이프 없음) 분리.
2. **상대경로 + `cd`** — SIF 를 상대경로로 받았는데 CWD 오염 검사가 `cd` 를
   해서 경로가 깨졌다. apptainer 가 FATAL 로 죽고 로그가 비니 ✗ 로 보여
   **신규 SIF 가 ✗ 4건으로 보고됐다.** → `readlink -f` + 선검사 가드(exit 3).

추가로, CWD 오염 검사를 홈에서 하게 짜면 known-bad 판에서 그 폴더가 **진짜로
생겨** 사용자 홈을 더럽힌다. 버릴 자리에서 검사할 것.
