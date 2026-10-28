# sphere_report 자동화 — 체크리스트

계획: [design.md](design.md) · 결정 이력: [context-notes.md](context-notes.md)
사용자 승인 2026-10-28 ("ㄱ" = 전체 착수). 순서 (2) → (4) → (3).

## (2) 로딩 실패를 조용히 넘기지 않는다
- [ ] `load_simulation_result` 가 탈락 사유를 보고한다 (선택 인자로 수집 — 호출부
      중복 금지, `__main__.py:903` 이 경고하는 복제 함정 회피)
- [ ] 사유 종류: `DropSet.json` 없음 / `DropSet.json` 깨짐 / `analysis_result.json` 없음
- [ ] `load_dropset` 의 `json.load` 가 깨진 파일에 터지지 않게 — 한 파일 때문에
      979런 적재가 통째로 죽는 걸 막고, 사유로 센다
- [ ] `successful_runs == 0` 이고 `Run_*` 가 있으면 → stderr 에 사유별 건수 + **exit 3**
- [ ] 부분 손실(적재 < `Run_*` 수) → 경고 한 줄 + 사유별 건수
- [ ] 🔴 `Loaded N results` 줄은 **exit 3 보다 먼저** 찍는다 (상류 셸이 이 줄을 본다)
- [ ] verify: 사유별 가짜 캠페인으로 exit 3·경고·정상 셋 다 확인
- [ ] 시험 — 수정 전 코드로 FAIL 확인

## (4) 파트별 항복응력 + 기존 단위 결함
- [ ] 🔴 **기존 결함 먼저**: `analyzer.py:105-141` 의 `--yield-stress`(MPa) ↔ 덱 단위
      응력 비교, `"{:.1f} MPa"` 하드코딩. SI 덱에서 지금도 무의미하다
- [ ] `model.part_yield` 를 첫 DropSet.json 에서 읽기 (`unit`/`parts`/`limits`/`criterion`)
- [ ] `--yield-map FILE` (metavar=FILE) — **덱 단위**, 명시적 덮어쓰기
- [ ] `limits` 우선, `yield` 는 `limits` 없을 때 폴백 (옛 맵 = KMM v126 이전)
- [ ] 한계마다 안전율 → **작은 쪽** 채택 (`von_mises`→`peak_stress`,
      `max_principal`→`peak_principal`)
- [ ] 🔴 측도 부재로 건너뛴 한계가 있으면 **"불완전"** 표시 + CRITICAL 단정 금지
      (놓치는 방향이 위험한 쪽이다)
- [ ] 모르는 `criterion` 문자열은 추측 금지 — 건너뛰고 사유 표기
- [ ] `--yield-stress` 폴백: MPa 유지, 단위 검출되면 환산, **미검출이면 비교 생략** + 사유
- [ ] `unit` 힌트와 내 검출이 어긋나면 경고 + 덱 쪽(내 검출) 채택
- [ ] 맵 위생 검사 — 관측 peak_stress 와 자릿수 대조 (EPS/ES 뒤바뀜류를 잡되
      재료 지식은 박지 않는다)
- [ ] 보고서에 파트별 **사용된 값 + 출처 + 기준**, 기본값 쓴 파트 수 명시
- [ ] `source` 글은 **파싱 금지, 표시만** (상류가 문구를 또 바꾼다)
- [ ] verify: pyKooCAE `test_sphere_automation.py::test_part_yield` 파트 10~12
      (MAT_017 SIGY 45 · FS 30/60/0) 와 같은 수로 대조
- [ ] 시험 — 수정 전 FAIL 확인

## (3) `--parallel-runs` + 2패스 메모리 축약 (같은 릴리스)
- [ ] `--parallel-runs N` (metavar=N, 기본 1 = 현행, 0 = auto
      `SLURM_CPUS_PER_TASK` 또는 `cpu_count`) — koo_impact_report 와 같은 꼴
- [ ] 1패스: ProcessPoolExecutor 로 흐름 생성 → 캐시 기록 → **스칼라만 남기고 폐기**
      (워커는 큰 것을 반환하지 않는다)
- [ ] 스칼라: `contact_metrics`, 파트쌍 pf/ti/tw, 파트별 IE/KE, 순위키
      `max(edge.peak_force)`
- [ ] 2패스: 순위 상위 `_FLOW_DETAIL_LIMIT`(60)만 캐시에서 재적재
- [ ] verify: 같은 캠페인에서 보고서 산출물이 **현행과 동일**한지 (무회귀)
- [ ] verify: 피크 RSS 가 실제로 내려가는지 측정
- [ ] 🔴 **워커 RSS + 1패스 run 당 시간 실측 → 상류 전달**
      (상류가 `SPHERE_NEW_MEM_PER_WORKER_GB` 2 GB 를 그 값으로 낮춘다)
- [ ] 시험 — 수정 전 FAIL 확인

## 마감
- [ ] 전 패키지 시험 통과
- [ ] 커밋·push
- [ ] v42 릴리스 — 상류 표준 스크립트, 내가 `verify_deck.sh` 로 검증
