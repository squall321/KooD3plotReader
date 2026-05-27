# koo_impact_report — sample dataset

스마트폰 부분충격 시뮬레이션 — Front (F2) + Back (F1) 충격 각각 25 위치,
총 **50 runs**. 합성(synthetic) DOE 결과 트리로, 실제 pyKooCAE
`drop_weight_impact_multiface` 출력과 동일한 폴더/파일 스키마를 따르지만
LS-DYNA 실측치는 전혀 들어 있지 않다. 모든 수치는
`tests/generate_sample.py`가 만들어 낸 모의 값이다.

## Layout (default smartphone scope)

```
sample_multiface_dataset/
├── scenario.json            # multi-face DOE config (plan §15.5)
├── scenario_cylinder.json   # alternative cylinder impactor variant
├── manifest.json            # flat list of every (face, position) run
├── impactor_spec.json       # §2.3 sphere impactor specification
├── device_layout.json       # §2.4 device bbox + 12 part footprints
├── F1_back/                 # 5×5 grid = 25 runs  (Back impact)
│   ├── face_config.json
│   ├── Run_F1_001/
│   │   ├── analysis_result.json   # per-run peaks + stress_ts (§2.5)
│   │   ├── glstat.csv             # 21-state global energy
│   │   ├── matsum.csv             # per-part IE/KE × 13 parts
│   │   └── rcforc.csv             # 8–15 decomposed contact F(t)
│   └── …
└── F2_front/                # 5×5 grid = 25 runs  (Front impact)
    └── …
```

Total: **50 runs** × (1 JSON + 3 CSV) = 200 files + 5 top-level files
+ 2 face_config.json = **207 files**.

## Regenerate

Default (Front + Back only):

```bash
cd python/koo_impact_report
python3 tests/generate_sample.py --output examples/sample_multiface_dataset --seed 42
```

전체 6-face 모드 (이전 110-runs 버전과 동일):

```bash
python3 tests/generate_sample.py \
    --output examples/sample_multiface_full \
    --seed 42 \
    --faces all
```

특정 면만 선택:

```bash
python3 tests/generate_sample.py \
    --output /tmp/ds_subset \
    --faces F1,F2,F5
```

A different `--seed` produces a different but statistically similar dataset.

## Physics realism

- Per-part `peak_g / stress / strain / disp` follow distance + depth decay
  from the impact point, with multiplicative lognormal noise and per-part
  fragility priors.
- Smartphone vulnerability pattern (programmed into `per_part_response`):
  - **F2 (Front, z=top) 충격** → 전면(near-screen-side) 부품이 직격:
    `PCB\Main`, `Motor`, `PKG\IC1`, `PKG\IC2`.
    특히 `Motor`는 충격점이 디바이스 중심(±15mm)일 때 가장 크게 손상된다.
  - **F1 (Back, z=bottom) 충격** → 후면 부품이 직격:
    `Battery`, `Frame`, `Housing\Back`. `Battery`가 가장 취약하다.
  - `--faces all`로 6-face 모드를 켜면 기존 F5(top) 측 메모리 패턴
    (`PKG\Memory_1/2`)도 활성화된다.
- `glstat / matsum / rcforc` are internally consistent within ~10% (impactor
  KE ↔ device IE ↔ dissipation budget). Conservation should be within ±5%
  for the headline KE→IE transfer.

## 12-part layout (smartphone analogy)

| Stack | Parts |
| ----- | ----- |
| Front-side (z≈11–14) | `PCB\Main`, `Motor`, `PKG\IC1`, `PKG\IC2` |
| Mid stack (z≈6–10)   | `PKG\Memory_1`, `PKG\Memory_2`, `Connector` |
| Back-side (z≈0–5)    | `Battery`, `Frame`, `Housing\Back` |
| Side rims (full z)   | `Front\Wall`, `Housing\Frame` |
