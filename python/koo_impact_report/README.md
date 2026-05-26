# koo_impact_report

Multi-face partial impact (drop-weight) simulation report generator.

Post-processes a pyKooCAE DOE consisting of multiple face orientations
(F1~F6) × XY-grid impact positions × parts, and produces a single-file
HTML report covering:

- Page 1 — METHODOLOGY + OVERVIEW (cube net, face KPI, impactor spec)
- Page 2 — TRANSFER MAPS (face × position × part heatmaps)
- Page 3 — PAIR DYNAMICS + VERDICT (severity scores, energy flow)

## Install

```bash
cd python/koo_impact_report
pip install -e .
```

## CLI

```bash
koo_impact_report \
    --test-dir Tests/ImpactTest_004_MultiFace \
    --output report.html \
    --metric peak_g \
    --threshold-critical 500000 \
    --threshold-warning 100000 \
    --yield-stress 800 \
    --faces F1,F2,F5 \
    --compare-faces \
    --severity-weight g=0.5,s=0.3,e=0.2
```

Alternative input:

```bash
koo_impact_report --from-json report.json
```

## Expected test directory layout

```
test_dir/
    scenario.json
    manifest.json
    F1_back/Run_xxx/analysis_result.json
    F2_front/Run_xxx/analysis_result.json
    ...
```

## Reference

See `docs/PartialImpactReport_Plan.md` (sections 14–22) for the full
design specification.
