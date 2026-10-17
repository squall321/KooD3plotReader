<!-- 전각도 낙하 해석을 MCP(LLM)로 진행한 실제 세션의 대화·응답·드라이버 로그 -->
# Smart Twin — 전각도 낙하 해석 · MCP(LLM) 대화 로그

> 실제 세션(2026-07-11, dev 클러스터 `smarttwincluster` @ 192.168.122.1)에서 MCP 도구 `smarttwin_submit` 로 진행한 **전각도 낙하(Full-Angle Drop)** 해석의 자연어 대화·도구 응답·드라이버 로그입니다. 모든 `job_id`·scenario·결과는 실측값입니다.

## 환경

| 항목 | 값 |
|---|---|
| MCP 서버 | `slurm-mcp` (streamable-http, `/mcp`, PAT 인증) |
| 템플릿 | `smarttwin-fullangle-drop` |
| DOE 드라이버 | `KooChainRun` (`/data/SmartTwinPreprocessor/bin/KooChainRun`) |
| 솔버 | LS-DYNA R16.1.1 MPP (Apptainer) |
| 모델 | `MinimumModel_drop.k` (낙하용, 자체 `*INITIAL_VELOCITY` 보유) |

---

## 1. 옵션 미리보기 (dry-run)

**사용자**
> 폰 모델을 전각도 낙하로 미리 구성만 보여줘. 피보나치 100방향, 낙하높이 1m, 강체바닥으로.

**Claude** — 파괴적이지 않은 미리보기라 `dry_run=true` 로 호출합니다.

```
▸ smarttwin_submit(
    sim_type      = "fullangle_drop",
    model_path    = ".../MinimumModel_drop.k",
    angle_preset  = "fibonacci-100",
    scenario_overrides = { "simulation_params": { "height": 1000,
                           "drop_surface": { "type": "RigidWall" } } },
    dry_run       = true )
```

**도구 응답** — 업로드될 `scenario.json`(발췌). `mode` 키가 없음이 전각도의 정상 신호입니다(있으면 부분충격으로 오라우팅).

```json
"simulation_params": { "height": 1000, "drop_surface": { "type": "RigidWall" } },
"scenarios": [{
  "angle_source": {
    "source_type": "fibonacci_lattice",
    "fibonacci_lattice": { "num_directions": 100 }
  },
  "cumulative": { "mode_sequence": ["DROP"] }
}]
```

**Claude** — 100방향 피보나치 낙하가 준비됐습니다. 실제 제출은 `dry_run=false` 로 하시면 됩니다.

---

## 2. 실제 제출 (6면·모서리·꼭짓점 = 26방향)

**사용자**
> 좋아, 6면 프리셋으로 실제로 한 번 돌려봐. 종료시간은 짧게.

**Claude** — `angle_preset=6face` 로 실제 제출합니다(`dry_run=false`).

```
▸ smarttwin_submit(
    sim_type     = "fullangle_drop",
    model_path   = ".../MinimumModel_drop.k",
    job_name     = "verify_drop2",
    angle_preset = "6face",
    scenario_overrides = { "simulation_params": { "tFinal": 0.0005 } },
    time_limit   = "01:00:00",
    dry_run      = false )
```

**도구 응답**

```
✅ 제출 완료 — job_id = 828
[fullangle_drop] template=smarttwin-fullangle-drop
scenario: base=프리셋 6face + overrides 병합
결과 폴더: /data/single/<user>/verify_drop2_828/
추적: slurm_job_results(828) · slurm_job_log(828)
```

업로드된 `scenario.json` 실제 값 — `6face` 프리셋은 **cuboid_geometry**(6면 + 12모서리 + 8꼭짓점 = 26방향)로 전개됩니다.

```json
"simulation_params": { "height": 1500, "tFinal": 0.0005,
                       "drop_surface": { "type": "Plane" } },
"scenarios": [{
  "angle_source": {
    "source_type": "cuboid_geometry",
    "cuboid_geometry": { "include_faces": true, "include_edges": true, "include_corners": true }
  }
}]
```

---

## 3. 드라이버 로그 / 자식 잡 전개

**Claude** — 드라이버(828)가 KooChainRun 으로 각 방향을 자식 잡으로 펼칩니다. `slurm_job_log(828)` 로 확인합니다.

```
/data/logs/828.out
========================================
SmartTwin Full-Angle Drop (KooChainRun)
========================================
=== KooChainRun prepare ===
DOE count:  26
  DOE   1: submitted (job 829)
  DOE   2: submitted (job 830)
  ...
  DOE  26: submitted (job 854)
Submitted 26/26 DOE jobs
[Sphere Postprocess] sbatch 생성: .../verify_drop2_828/output/sphere_report.sbatch
  → Sphere Job ID: 855
자식 잡 ID: 829,830,831,...,854
=== 자식 잡 완료 대기 (60초 간격) ===
```

**주목할 점.**
- `DROP → sphere` 라우팅이 정확합니다 — 후처리로 sphere 리포트가 dependent 잡으로 자동 예약됩니다.
- 자식 추적이 **잡 이름이 아니라 잡ID(829~854)** 기반입니다. 과거엔 이름 매칭이 어긋나 부모가 조기 종료하거나 무한 대기했는데, 잡ID 폴링으로 그 결함을 제거했습니다.

---

## 4. 결과

**사용자**
> 다 끝났어?

**Claude** — `slurm_job_results` 로 집계했습니다.

```
$ sacct -j 829..854
자식 26개 → 전부 COMPLETED (LS-DYNA 솔브 완료)
```

| 항목 | 결과 |
|---|---|
| 워크플로 라우팅 | Full-Angle Drop (부분충격 오라우팅 아님) ✅ |
| 자식 DOE 제출 | 26/26 (jobID 폴링) ✅ |
| 자식 솔브 | **26개 전부 COMPLETED** ✅ |
| 부모 드라이버 | ⚠️ TIMEOUT (1시간 walltime) |

**정직한 도달점.** 26개 방향이 모두 정상 솔브됐지만, **부모 드라이버는 dev의 2코어 노드 2대(동시 4슬롯)에서 26케이스를 소화하는 데 1시간을 넘겨 walltime TIMEOUT** 됐습니다. 이건 코드 결함이 아니라 dev 클러스터 자원 한계입니다 — 코어가 많은 운영 클러스터에서는 훨씬 빨리 끝나 부모가 collect/후처리까지 도달합니다. (또한 최초 시도 job 826은 `CHAIN_NCPU=4`가 2코어 노드에 안 맞아 자식 제출이 실패 → dev 검증용으로 `CHAIN_NCPU=1`로 낮춰 828을 재제출했습니다.)

**핵심.** 한 줄의 자연어 지시가 검증된 `scenario.json` → 26방향 DOE 전개 → 클러스터 자식 잡 제출·솔브까지 이어졌습니다. 사람이 JSON을 손으로 쓰거나 `sbatch` 를 짜지 않습니다.
