<!-- 전위치 부분충격 해석을 MCP(LLM)로 진행한 실제 세션의 대화·응답·드라이버 로그 -->
# Smart Twin — 전위치 부분충격 해석 · MCP(LLM) 대화 로그

> 실제 세션(2026-07-10~11, dev 클러스터 `smarttwincluster` @ 192.168.122.1)에서 MCP 도구 `smarttwin_submit` 로 진행한 **전위치 부분충격(All-Position Partial Impact / Drop-Weight Impact)** 해석의 자연어 대화·도구 응답·드라이버 로그입니다. 모든 `job_id`·scenario·결과는 실측값입니다.

## 환경

| 항목 | 값 |
|---|---|
| MCP 서버 | `slurm-mcp` (streamable-http, `/mcp`, PAT 인증) |
| 템플릿 | `smarttwin-partial-impact` |
| 전처리 | `KooMeshModifier` (Apptainer, OpenCASCADE 내장) — 위치마다 임팩터+바닥 자동 삽입 |
| DOE 드라이버 | `KooChainRun` (drop_weight_impact 모드) |
| 솔버 | LS-DYNA R16.1.1 MPP (Apptainer) |
| 모델 | `MinimumModel.k` (정지 모델) |

> **모델 주의.** 부분충격은 **정지 모델**이 필요합니다. `MinimumModel_drop.k`는 자체 `*INITIAL_VELOCITY`가 있어 임팩터의 `*INITIAL_VELOCITY_GENERATION`과 혼용 금지(LS-DYNA KEY+387)로 즉시 에러 종료합니다.

---

## 1. 안전 가드 — 잘못된 구성은 즉시 차단

**사용자**
> 부분충격으로 돌리는데 전각도 scenario 파일을 실수로 올렸어. 어떻게 돼?

**Claude** — 템플릿에 **유형 가드**가 있어, 부분충격 잡에 `mode=drop_weight_impact`가 없는 scenario가 오면 솔브 전에 차단됩니다.

```
▸ (부분충격 템플릿 + 전각도 scenario 제출) → job_id = 805

/data/logs/805.out
ERROR: 부분충격 잡인데 scenario.json 에 mode=drop_weight_impact 가 없습니다.
  → 전각도 낙하는 smarttwin-fullangle-drop 템플릿으로 제출하세요.
$ sacct -j 805 → FAILED (1초 만에, 솔버 진입 전)
```

**Claude** — 잘못된 조합이 조용히 엉뚱한 워크플로로 도는 사고(과거 job 799 계열)를 막습니다. 반대 방향(전각도 잡 ← 부분충격 scenario)도 동일하게 차단합니다.

---

## 2. 실제 제출 — 2개 위치 부분충격

**사용자**
> 이제 제대로. 충격 위치는 (-30,-60), (30,-60) 두 점, 임팩터 반경 5mm, 종료시간 짧게 실제로 돌려줘.

**Claude** — `dry_run=false` 로 실제 제출합니다.

```
▸ smarttwin_submit(
    sim_type   = "partial_impact",
    model_path = ".../MinimumModel.k",
    job_name   = "fixtest_impact4",
    scenario_overrides = {
      "simulation_params": {
        "tFinal": 0.0003,
        "locations": { "mode": "list", "points": [[-30, -60], [30, -60]] }
      } },
    time_limit = "01:00:00",
    dry_run    = false )
```

**도구 응답**

```
✅ 제출 완료 — job_id = 818
[partial_impact] template=smarttwin-partial-impact
scenario: base=기본격자(5x5) + overrides 병합
결과 폴더: /data/single/<user>/fixtest_impact4_818/
```

업로드된 `scenario.json` 실제 값 — 물성 단위가 LS-DYNA 덱과 동일한 **[tonne, mm, s, MPa]** 입니다(SI 숫자 7850/2e11이 아니라 `7.85e-9`/`2.0e5`).

```json
"mode": "drop_weight_impact",
"simulation_params": {
  "tFinal": 0.0003,
  "impactor": { "type": "Sphere", "radius": 5.0, "height": 100,
                "density": 7.85e-9, "youngs_modulus": 2.0e5, "poisson_ratio": 0.3 },
  "locations": { "mode": "list", "points": [[-30, -60], [30, -60]] },
  "generation_mode": "DampingSpring"
}
```

---

## 3. 드라이버 로그 — 전처리(메시) → 자식 솔브

**Claude** — 드라이버(818)가 위치마다 `KooMeshModifier`로 임팩터+바닥을 심은 덱을 만들고, KooChainRun이 자식 array 잡으로 솔브합니다.

```
/data/logs/818.out
========================================
SmartTwin All-Position Partial Impact (KooChainRun/KooMeshModifier)
========================================
=== KooChainRun prepare ===
KooChainRun - Drop Weight Impact (prepare)
  충격 위치: 2개
    [1/2] x=-30.00, y=-60.00
    [2/2] x=30.00, y=-60.00
✅ Drop Weight Impact 준비 완료!  케이스 수: 2
✅ Submitted batch job 819
자식 잡 ID: 819
=== 자식 잡 완료 대기 (60초 간격) ===
...
=== 자식 잡 전체 종료 ===
Drop Weight Impact 결과
  전체: 2, PASS: 2, FAIL: 0, PENDING: 0
```

**전처리 단계.** 각 자식은 컨테이너 안에서 `KooMeshModifier`가 먼저 실행되어 `Run_<ts>_<hash>/Output/DropWeightImpactTestSet.k` 를 생성하고(OpenCASCADE·gmsh 통과), 그 덱을 LS-DYNA가 솔브합니다.

---

## 4. 결과

**사용자**
> 결과는?

**Claude** — `slurm_job_results(818)` 집계입니다.

| 항목 | 결과 |
|---|---|
| 부모 드라이버 | **COMPLETED** (00:10:45) ✅ |
| 자식 819_1 / 819_2 | 둘 다 **COMPLETED** (Normal termination) ✅ |
| 집계 | **PASS 2 / FAIL 0** ✅ |
| d3plot | dwi_0001 **17개**, dwi_0002 **17개** ✅ |

**도달점.** 자연어 지시 → 위치 DOE 전개 → 위치별 KooMeshModifier 전처리 → LS-DYNA 솔브 완주 → 부모 정상 집계까지, **부분충격 파이프라인 e2e 최초 완주**입니다.

**참고 — 여기까지 오는 데 넘은 함정(모두 수정 완료).**
- KooMeshModifier가 만든 `.k`를 run.sh가 못 찾던 경로 불일치(`Run_*/Output` 재귀 탐색으로 수정).
- 자식 잡 이름 `DWI` 하드코딩 → 부모 폴링 불일치(project_name 기반 + 잡ID 폴링으로 수정).
- LSTC 라이선스 서버가 매분 재기동되던 왓치독 버그, dev 프리셋에 운영 IP 잔존(둘 다 수정).
- 임팩터 물성 SI 단위 무변환 기입(덱 단위계로 수정).

---

## 후처리 리포트

자식 완료 후 impact 리포트가 dependent 잡으로 자동 예약됩니다. 리포트 본체(`koo_impact_report`)가 KooChainRun DWI 레이아웃을 읽도록 후처리(KooD3plotReader)쪽에서 로더를 확장 중이며, 드라이버쪽은 각 `Run_*/Output/report/`에 `analysis_result.json`(deep 산출물)을 남기도록 정합을 마쳤습니다. 리포트 HTML 자동 발행은 후처리 sif 배포 후 최종 검증 예정입니다.
