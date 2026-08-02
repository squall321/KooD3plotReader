# 리비전 비교 엔진 — Δ/winner/trend/spread + 파트추이 + behavior 전이 + findings diff
"""비교 엔진.

반환값은 순수 dict(FederatedComparison) 이며, 이것이 HTML 보고서가 소비하는
**payload 계약**이다. 계약 키는 아래 build_comparison() 마지막 return 참조.

정직성 규칙 (계획서 §2)
  - 절대 임계값을 발명하지 않는다. 개선/악화는 Δ 부호와 크기만 쓴다.
  - trust_gate: 한 리비전이라도 신뢰 불가면 그 셀의 Δ/trend/spread/winner 는 None
    이고 gate_reason 이 붙는다 (오염된 Δ 를 개선/악화로 오독하는 것을 차단).
  - 단위계/스키마 불일치는 조용히 넘기지 않는다 (error 또는 구조화된 warning).
"""
from __future__ import annotations

from statistics import median, pstdev

from .models import METRIC_KEYS, METRIC_UNIT_AXIS, METRIC_LABELS
from .tiers import build_tier_plan


class CompareError(Exception):
    """비교 자체가 성립하지 않는 경우 (단위계/스키마 불일치 등)."""


#: 알려진 단위 → SI 환산 계수 (unit_policy: convert 에서만 사용)
_TO_SI = {
    "acc": {"m/s²": 1.0, "m/s^2": 1.0, "mm/s²": 1e-3, "mm/s^2": 1e-3, "g": 9.80665},
    "stress": {"Pa": 1.0, "kPa": 1e3, "MPa": 1e6, "GPa": 1e9},
    "disp": {"m": 1.0, "mm": 1e-3, "cm": 1e-2},
    "vel": {"m/s": 1.0, "mm/s": 1e-3},
    "energy": {"J": 1.0, "mJ": 1e-3, "kJ": 1e3},
}


# --------------------------------------------------------------------------
# 수치 유틸
# --------------------------------------------------------------------------
def _slope(values: list):
    """리비전 순번(x=0,1,2,…)에 대한 최소제곱 기울기."""
    n = len(values)
    if n < 2:
        return None
    xm = (n - 1) / 2.0
    ym = sum(values) / n
    num = sum((i - xm) * (v - ym) for i, v in enumerate(values))
    den = sum((i - xm) ** 2 for i in range(n))
    return num / den if den else None


def _spread(values: list) -> dict:
    lo, hi = min(values), max(values)
    mean = sum(values) / len(values)
    sd = pstdev(values) if len(values) > 1 else 0.0
    return {
        "min": lo,
        "max": hi,
        "range": hi - lo,
        "cv": (sd / abs(mean)) if mean else None,
        "stdev": sd,
    }


def _pct(new, base):
    if base in (None, 0) or new is None:
        return None
    return (new - base) / abs(base) * 100.0


#: cell.category 가 비어 있는 셀의 표시 이름 (버리지 않고 정직하게 한 칸으로 모은다)
UNCATEGORIZED = "(미지정)"


def _category_summary(cells, baseline_idx, n_rev, metric) -> dict:
    """카테고리별 소계 — sphere 의 face/edge/corner, impact 의 face code.

    "코너 낙하만 나빠졌다" 같은 구조적 회귀를 한 눈에 잡는 뷰다.
    카테고리마다 리비전별 {n, worst, median, mean} 과 baseline 대비 Δ% 를 낸다.

    규칙
      - **미판정(gated) 셀은 제외**한다. 리비전마다 다른 셀 집합으로 집계하면
        소계 Δ 가 오염되기 때문이다 (파트 추이와 같은 규칙).
      - 카테고리가 1종 이하이면 빈 dict — 비교할 것이 없는 막대를 그리지 않는다
        (예: DOE 전체가 fibonacci 한 종류인 경우).
      - 절대 임계값은 쓰지 않는다. Δ% 의 부호와 크기만 보고한다.
    """
    buckets: dict = {}
    n_excluded = 0
    for c in cells:
        if c["gated"]:
            n_excluded += 1
            continue
        buckets.setdefault(c["category"] or UNCATEGORIZED, []).append(c)
    if len(buckets) <= 1:
        return {}

    cats = []
    for name, group in buckets.items():
        per_rev = []
        for i in range(n_rev):
            vals = [
                c["per_rev"][i]["value"]
                for c in group
                if c["per_rev"][i]["value"] is not None
            ]
            per_rev.append(
                {
                    "n": len(vals),
                    "worst": max(vals) if vals else None,
                    "median": float(median(vals)) if vals else None,
                    "mean": (sum(vals) / len(vals)) if vals else None,
                }
            )
        base_row = per_rev[baseline_idx] if baseline_idx < len(per_rev) else {}
        for row in per_rev:
            for stat in ("worst", "median", "mean"):
                row[f"{stat}_delta_pct"] = _pct(row[stat], base_row.get(stat))
        cats.append(
            {
                "name": name,
                "n_cells": len(group),
                "cells": [c["key"] for c in group],
                "per_rev": per_rev,
            }
        )

    # baseline worst 내림차순 (값 없으면 뒤로), 동점은 이름순 — 결정적 정렬
    cats.sort(
        key=lambda ct: (
            -(
                ct["per_rev"][baseline_idx]["worst"]
                if baseline_idx < len(ct["per_rev"])
                and ct["per_rev"][baseline_idx]["worst"] is not None
                else float("-inf")
            ),
            ct["name"],
        )
    )
    return {
        "metric": metric,
        "metric_label": METRIC_LABELS[metric],
        "baseline_idx": baseline_idx,
        "n_categories": len(cats),
        "n_excluded_gated": n_excluded,
        "categories": cats,
    }


# --------------------------------------------------------------------------
# 가드
# --------------------------------------------------------------------------
def _guard_schema(bundles):
    versions = [b.schema_version for b in bundles]
    if len(set(map(str, versions))) > 1:
        raise CompareError(
            "sidecar schema_version 이 리비전마다 다릅니다 — "
            + ", ".join(f"{b.label}={b.schema_version}" for b in bundles)
            + " (조용한 오비교를 막기 위해 중단합니다)"
        )
    return versions[0] if versions else None


def _unit_factors(bundles, baseline_idx, policy, warnings) -> list:
    """리비전별 {metric: 곱할 계수}. 불일치가 없으면 전부 1.0."""
    base_labels = bundles[baseline_idx].unit_labels or {}
    factors = [{k: 1.0 for k in METRIC_KEYS} for _ in bundles]
    mismatches = []

    for i, b in enumerate(bundles):
        if i == baseline_idx:
            continue
        labels = b.unit_labels or {}
        for mk in METRIC_KEYS:
            axis = METRIC_UNIT_AXIS[mk]
            lb, li = base_labels.get(axis), labels.get(axis)
            if not lb or not li or lb == li:
                continue
            mismatches.append((i, axis, li, lb))
            table = _TO_SI.get(axis) or {}
            if li in table and lb in table:
                factors[i][mk] = table[li] / table[lb]
            else:
                factors[i][mk] = 1.0
                warnings.append(
                    {
                        "code": "unit_unknown",
                        "severity": "ERROR",
                        "message": (
                            f"'{b.label}' 의 {axis} 단위 '{li}' 를 baseline '{lb}' 로 환산할 "
                            "방법이 없습니다 — 환산 없이 비교하므로 수치를 신뢰하지 마십시오"
                        ),
                    }
                )

    if mismatches:
        detail = "; ".join(
            f"{bundles[i].label}.{axis}='{li}' vs baseline '{lb}'"
            for i, axis, li, lb in mismatches
        )
        if policy == "error":
            raise CompareError(
                f"리비전 간 단위계가 다릅니다 — {detail}\n"
                "options.unit_policy: convert 로 환산하거나 sidecar 를 통일하십시오"
            )
        warnings.append(
            {
                "code": "unit_converted",
                "severity": "WARN",
                "message": f"단위계 불일치를 baseline 기준으로 환산했습니다 — {detail}",
            }
        )
    return factors


# --------------------------------------------------------------------------
# 본체
# --------------------------------------------------------------------------
def _guard_input_sanity(bundles, warnings) -> None:
    """입력 실수 방어 — 조용히 무의미한 보고서를 내지 않는다.

    ① 같은 sidecar 를 두 번 넣으면 Δ 가 전부 0 인 보고서가 나오는데, 경고가
       없으면 사용자는 실수를 모른다(경로/입력 digest 기준).
    ② YAML 순서(=리비전 축)와 생성 시각 순서가 어긋나면 추이(trend) 해석이
       뒤집힌다. 순서를 강제하지는 않고 사실만 알린다.
    """
    # ① 중복 입력 — 경로가 1순위 기준이다. digest 는 서로 다른 파일이 같은
    #    값을 가질 수 있어(원본을 복사·변형한 리비전) 경로가 다르면 중복으로
    #    보지 않는다. 경로까지 같을 때만 확실한 실수로 판정한다.
    seen = {}
    for i, b in enumerate(bundles):
        key = (getattr(b, "path", None) or "").strip() or None
        if not key:
            continue
        if key in seen:
            warnings.append({
                "code": "duplicate_input",
                "severity": "ERROR",
                "message": (f"{bundles[seen[key]].label} 과 {b.label} 이 같은 입력입니다 "
                            f"— Δ 가 0 으로 나오는 것은 개선이 아니라 중복 입력 때문입니다."),
            })
        else:
            seen[key] = i

    # ② 생성 시각 역순
    times = []
    for b in bundles:
        gu = (getattr(b, "provenance", None) or {}).get("generated_utc")
        times.append(str(gu) if gu else None)
    known = [(i, t) for i, t in enumerate(times) if t]
    if len(known) >= 2:
        ordered = all(known[k][1] <= known[k + 1][1] for k in range(len(known) - 1))
        if not ordered:
            warnings.append({
                "code": "revision_order",
                "severity": "INFO",
                "message": ("YAML 의 리비전 순서가 생성 시각 순서와 다릅니다 — "
                            "추이(TREND)는 YAML 순서를 시간 축으로 간주하므로 "
                            "의도한 순서인지 확인하십시오."),
            })


def build_comparison(bundles, baseline_idx, kind, match, aligned, options, metric="g") -> dict:
    if metric not in METRIC_KEYS:
        raise CompareError(f"metric 은 {list(METRIC_KEYS)} 중 하나여야 합니다 — 현재 {metric!r}")

    warnings = list(match.warnings) + list(aligned.warnings)
    _guard_input_sanity(bundles, warnings)
    schema_version = _guard_schema(bundles)
    factors = _unit_factors(bundles, baseline_idx, options.unit_policy, warnings)
    n_rev = len(bundles)

    def scaled(sample, mk, rev_idx):
        v = sample.metrics.get(mk)
        return None if v is None else v * factors[rev_idx][mk]

    # ---- cells --------------------------------------------------------
    cells = []
    n_comparable = 0
    n_gated = 0
    for node in aligned.nodes:
        per_rev = []
        values = []
        trust_bad = []
        for i, s in enumerate(node.per_rev):
            v = scaled(s, metric, i)
            values.append(v)
            per_rev.append(
                {
                    "value": v,
                    "values": {mk: scaled(s, mk, i) for mk in METRIC_KEYS},
                    "trust": s.trust.as_dict(),
                    "source": s.source,
                    "measured": bool(s.measured),
                    "offset": s.offset,
                    "behavior": s.behavior,
                    "energy": dict(s.energy),
                    "cell_key": s.cell_key,
                }
            )
            if not s.trust.ok:
                trust_bad.append(f"{bundles[i].label}: {s.trust.reason}")

        complete = all(v is not None for v in values)
        gated = (not complete) or (options.trust_gate and bool(trust_bad))
        reasons = []
        if not complete:
            missing = [bundles[i].label for i, v in enumerate(values) if v is None]
            reasons.append("값 없음: " + ", ".join(missing))
        if options.trust_gate and trust_bad:
            reasons.extend(trust_bad)

        base_v = values[baseline_idx]
        if gated:
            delta = [None] * n_rev
            delta_pct = [None] * n_rev
            winner = None
            trend = None
            trend_abs = None
            spread = None
            n_gated += 1
        else:
            delta = [v - base_v for v in values]
            delta_pct = [_pct(v, base_v) for v in values]
            winner = max(range(n_rev), key=lambda i: values[i])
            trend_abs = _slope(values)
            trend = (trend_abs / abs(base_v)) if (trend_abs is not None and base_v) else None
            spread = _spread(values)
            n_comparable += 1

        energy_keys = ("ke_retention", "diss_pct", "max_penetration_depth")
        energy_per_rev = [
            {k: (s.energy.get(k) if s.energy else None) for k in energy_keys}
            for s in node.per_rev
        ]
        energy_delta = []
        for row in energy_per_rev:
            base_row = energy_per_rev[baseline_idx]
            energy_delta.append(
                {
                    k: (None if (row[k] is None or base_row[k] is None) else row[k] - base_row[k])
                    for k in energy_keys
                }
            )

        cells.append(
            {
                "key": node.key,
                "label": node.label,
                "x": node.x,
                "y": node.y,
                "roll": node.roll,
                "pitch": node.pitch,
                "yaw": node.yaw,
                "category": node.category,
                "per_rev": per_rev,
                "delta": delta,
                "delta_pct": delta_pct,
                "winner": winner,
                "trend": trend,
                "trend_abs": trend_abs,
                "spread": spread,
                "gated": gated,
                # HTML 계약 별칭: 긍정형 trust_ok (gated 의 반대). 리포트 레이어가
                # 셀 강등(점선/빗금)을 판단하는 단일 키.
                "trust_ok": not gated,
                "gate_reason": "; ".join(reasons) if reasons else None,
                "energy": {"per_rev": energy_per_rev, "delta": energy_delta},
            }
        )

    if aligned.nodes and n_comparable == 0:
        warnings.append(
            {
                "code": "no_comparable_cells",
                "severity": "ERROR",
                "message": (
                    f"모든 리비전에서 유효한 셀이 0개입니다 ({len(cells)}개 전부 미판정) — "
                    "Δ/추이 지도는 의미가 없습니다. behavior 전이 매트릭스로 판단하십시오"
                ),
            }
        )

    # ---- tier (프로파일 표시 힌트) / 카테고리 소계 ----------------------
    # tier 는 cells[] 를 줄이지 않는다 — 프로파일이 무엇을 그릴지의 힌트만 준다.
    plan = build_tier_plan(cells, baseline_idx, n_rev)
    category_summary = _category_summary(cells, baseline_idx, n_rev, metric)

    # ---- 파트 추이 / rank bump -----------------------------------------
    parts = []
    for canonical in match.canonicals:
        names = match.per_rev.get(canonical, [None] * n_rev)
        worst = []
        used = []
        worst_cell = []       # 그 worst 가 어느 셀에서 나왔는지 (드릴다운 진입점)
        for i in range(n_rev):
            name = names[i]
            if name is None:
                worst.append(None)
                used.append(0)
                worst_cell.append(None)
                continue
            best_v, n_used, best_cell = None, 0, None
            for node, cell in zip(aligned.nodes, cells):
                # 미판정 셀은 모든 리비전에서 똑같이 뺀다 — 리비전마다 다른 셀 집합으로
                # 집계하면 파트 Δ 가 오염된다.
                if cell["gated"]:
                    continue
                s = node.per_rev[i]
                if s.cell_key is None:
                    continue
                raw = bundles[i].part_metric(s.cell_key, name, metric)
                if raw is None:
                    continue
                n_used += 1
                v = raw * factors[i][metric]
                if best_v is None or v > best_v:
                    best_v = v
                    best_cell = cell["key"]
            worst.append(best_v)
            used.append(n_used)
            worst_cell.append(best_cell)
        parts.append(
            {
                "canonical": canonical,
                "source": match.source.get(canonical, "auto"),
                "names": names,
                "present": [nm is not None for nm in names],
                "worst": worst,
                "n_cells_used": used,
                # "Display 가 나빠졌다" 에서 "어느 위치에서" 까지 답하게 하는 키.
                # 리비전마다 worst 셀이 다르면 그 자체가 신호다(취약점 이동).
                "worst_cell": worst_cell,
            }
        )

    # rank (1 = 가장 나쁨) — 리비전별로 worst 내림차순
    for i in range(n_rev):
        ranked = sorted(
            (p for p in parts if p["worst"][i] is not None),
            key=lambda p: p["worst"][i],
            reverse=True,
        )
        for p in parts:
            p.setdefault("rank", [None] * n_rev)
        for r, p in enumerate(ranked, start=1):
            p["rank"][i] = r

    for p in parts:
        base_v = p["worst"][baseline_idx]
        p["delta"] = [
            None if (v is None or base_v is None) else v - base_v for v in p["worst"]
        ]
        p["delta_pct"] = [
            None if (v is None or base_v is None) else _pct(v, base_v) for v in p["worst"]
        ]
        base_rank = p["rank"][baseline_idx]
        # rank_delta > 0 = worst 순위에서 내려감(덜 나빠짐), < 0 = 올라감(더 나빠짐)
        p["rank_delta"] = [
            None if (r is None or base_rank is None) else r - base_rank for r in p["rank"]
        ]
        vals = [v for v in p["worst"] if v is not None]
        p["trend"] = None
        if len(vals) == n_rev and base_v:
            sl = _slope(p["worst"])
            p["trend"] = sl / abs(base_v) if sl is not None else None

    # ---- (위치×파트) Δ 매트릭스 (impact 전용) --------------------------
    part_matrix = None
    if kind == "impact":
        cell_keys = [c["key"] for c in cells]
        gate_mask = [c["gated"] for c in cells]
        rows = []
        for p in parts:
            per_rev_vals = []
            for i in range(n_rev):
                name = p["names"][i]
                row = []
                for node in aligned.nodes:
                    s = node.per_rev[i]
                    raw = (
                        None
                        if (name is None or s.cell_key is None)
                        else bundles[i].part_metric(s.cell_key, name, metric)
                    )
                    row.append(None if raw is None else raw * factors[i][metric])
                per_rev_vals.append(row)
            base_row = per_rev_vals[baseline_idx]
            delta_pct = [
                [
                    None if (gate_mask[j] or v is None or base_row[j] is None)
                    else _pct(v, base_row[j])
                    for j, v in enumerate(row)
                ]
                for row in per_rev_vals
            ]
            rows.append(
                {"canonical": p["canonical"], "per_rev": per_rev_vals, "delta_pct": delta_pct}
            )
        part_matrix = {
            "metric": metric,
            "cells": cell_keys,
            "gated": gate_mask,
            "rows": rows,
        }

    # ---- behavior 전이 매트릭스 (impact) --------------------------------
    behavior_transitions = None
    if kind == "impact":
        per_rev_tr = []
        changed_cells = set()
        for i in range(n_rev):
            buckets = {}
            for c in cells:
                a = c["per_rev"][baseline_idx]["behavior"]
                b = c["per_rev"][i]["behavior"]
                if a is None and b is None:
                    continue
                buckets.setdefault((a, b), []).append(c["key"])
                if a != b:
                    changed_cells.add(c["key"])
            entries = [
                {"from": a, "to": b, "count": len(keys), "cells": sorted(keys), "changed": a != b}
                for (a, b), keys in sorted(
                    buckets.items(), key=lambda kv: (-len(kv[1]), str(kv[0]))
                )
            ]
            per_rev_tr.append(
                {
                    "label": bundles[i].label,
                    "entries": entries,
                    "n_changed": sum(e["count"] for e in entries if e["changed"]),
                    "counts": dict(bundles[i].trust.get("behavior_counts") or {}),
                }
            )
        headline = any(r["n_changed"] > 0 for r in per_rev_tr)
        behavior_transitions = {
            "baseline_idx": baseline_idx,
            "per_rev": per_rev_tr,
            "n_changed_cells": len(changed_cells),
            "headline": headline,
        }
        if headline:
            warnings.append(
                {
                    "code": "behavior_transition",
                    "severity": "WARN",
                    "message": (
                        f"거동 분류(no-contact/bounce/rebound)가 바뀐 위치 {len(changed_cells)}개 "
                        "— 비교 기준 자체가 달라졌을 수 있습니다. Δ 지도보다 전이 매트릭스를 먼저 보십시오"
                    ),
                }
            )

    # ---- findings diff -------------------------------------------------
    def _fkey(f):
        return str(f.get("title") or "").strip()

    base_findings = {_fkey(f): f for f in bundles[baseline_idx].findings}
    findings_diff = []
    for i, b in enumerate(bundles):
        cur = {_fkey(f): f for f in b.findings}
        new = [cur[k] for k in cur if k not in base_findings]
        resolved = [base_findings[k] for k in base_findings if k not in cur]
        kept = [cur[k] for k in cur if k in base_findings]
        findings_diff.append(
            {
                "label": b.label,
                "is_baseline": i == baseline_idx,
                "new": new,
                "resolved": resolved,
                "kept": kept,
                "n_total": len(b.findings),
            }
        )

    # ---- KPI -----------------------------------------------------------
    n_cells = len(cells)
    matched_parts = sum(1 for p in parts if sum(1 for x in p["present"] if x) >= 2)
    kpi = {
        "metric": metric,
        "metric_label": METRIC_LABELS[metric],
        "n_revisions": n_rev,
        "baseline_label": bundles[baseline_idx].label,
        "n_cells": n_cells,
        "n_comparable": n_comparable,
        "n_gated": n_gated,
        "comparable_pct": round(100.0 * n_comparable / n_cells, 1) if n_cells else 0.0,
        "trust_gate": bool(options.trust_gate),
        "n_parts_canonical": len(parts),
        "n_parts_matched": matched_parts,
        "n_parts_unmatched": [len(u) for u in match.unmatched],
        "worst_per_rev": [
            max((c["per_rev"][i]["value"] for c in cells if c["per_rev"][i]["value"] is not None),
                default=None)
            for i in range(n_rev)
        ],
        "sidecar_kpi": [dict(b.kpi) for b in bundles],
        "energy": {
            "diss_pct": [b.kpi.get("diss_pct") for b in bundles],
            "diss_pct_delta": [
                None
                if (b.kpi.get("diss_pct") is None
                    or bundles[baseline_idx].kpi.get("diss_pct") is None)
                else b.kpi["diss_pct"] - bundles[baseline_idx].kpi["diss_pct"]
                for b in bundles
            ],
        },
    }
    if kind == "impact" and behavior_transitions:
        kpi["n_behavior_changed"] = behavior_transitions["n_changed_cells"]

    revisions = [
        {
            "index": i,
            "label": b.label,
            "path": b.path,
            "kind": b.kind,
            "is_baseline": i == baseline_idx,
            "project": (b.meta or {}).get("project"),
            "schema_version": b.schema_version,
            "unit_labels": dict(b.unit_labels),
            "unit_factor": dict(factors[i]),
            "n_cells": len(b.cells),
            "n_parts": len(b.parts),
            "trust": dict(b.trust),
            "kpi": dict(b.kpi),
            "unmatched_parts": list(match.unmatched[i]),
        }
        for i, b in enumerate(bundles)
    ]

    provenance = [
        {
            "label": b.label,
            "path": b.path,
            "schema_version": b.schema_version,
            "project": (b.meta or {}).get("project"),
            "test_dir": (b.meta or {}).get("test_dir"),
            **{k: v for k, v in (b.provenance or {}).items()},
        }
        for b in bundles
    ]

    # acc 단위계 → G 환산 계수. 본 보고서(impact/sphere)와 동일 규칙으로,
    # 리포트가 1.49e9 mm/s² 같은 못 읽는 수를 151,762 G 로 보여줄 수 있게 한다.
    _acc = (bundles[baseline_idx].unit_labels or {}).get("acc", "")
    g_divisor = 9.81 if _acc in ("m/s²", "mm/ms²") else (9810.0 if _acc == "mm/s²" else None)

    return {
        "g_divisor": g_divisor,
        "kind": kind,
        "baseline_idx": baseline_idx,
        "schema_version": schema_version,
        "metric": metric,
        "unit_labels": dict(bundles[baseline_idx].unit_labels),
        "revisions": revisions,
        "cells": cells,
        "tier": plan["tier"],
        "profile_cells": plan["profile_cells"],
        "profile_aggregate": plan["profile_aggregate"],
        "category_summary": category_summary,
        "parts": parts,
        "part_matrix": part_matrix,
        "behavior_transitions": behavior_transitions,
        "findings_diff": findings_diff,
        "kpi": kpi,
        "coverage": dict(aligned.coverage),
        "unmatched": (
            [] if options.unmatched == "hide"
            else [
                {"label": bundles[i].label, "parts": list(u)}
                for i, u in enumerate(match.unmatched)
            ]
        ),
        "warnings": warnings,
        "provenance": provenance,
    }
