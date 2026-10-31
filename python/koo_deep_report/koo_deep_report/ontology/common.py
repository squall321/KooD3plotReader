# 세 리포트 어댑터가 함께 쓰는 조각 — 파트·소견·전 런 포락(최악값·안전율·판정)
"""포락과 판정 규칙은 koo_sphere_report 분석기(`analyzer._generate_findings`)와 **같게** 둔다.
리포트 소견과 온톨로지 판정이 갈리면 어느 쪽을 믿을지 모르게 된다.

- 안전율 = min(한계 ÷ 그 기준의 최대 응력). 한계의 응력을 못 쟀으면 「불완전」 — 실제보다
  클 수 있어 critical 로 단정하지 않고 warning 으로 둔다.
- 안전율 < 1 critical, < 1.5 warning. 가속도 > 200,000 G critical, > 50,000 G warning — 가속도 기준은
  전각도 낙하 분석기의 것이라 그 어댑터만 켠다(부분충격 분석기는 가속도 절대 기준을 일부러 두지 않는다).
- 한계가 없으면 응력 판정을 하지 않는다. 그때 가속도도 걸리지 않으면 ok 가 아니라 unknown —
  응력을 보지 않고 괜찮다고 말하지 않는다.
"""
from __future__ import annotations

import re
import statistics

_RANK = {"ok": 0, "warning": 1, "critical": 2}
_PART_TITLE = re.compile(r"^Part (\d+) \(")


def num(v):
    """숫자만 통과(bool·문자열·NaN 은 None) — 0 으로 바꾸지 않는다. 정수는 정수로 둔다(요소 번호 등)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    if isinstance(v, int):
        return v
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def add_findings(pkg, findings: list, part_keys: dict[int, str]) -> None:
    """리포트 소견 → cae_finding. 제목이 'Part <PID> (' 로 시작하면 그 파트를 가리킨다
    (분석기의 제목 꼴 — 소견에 파트 번호 칸이 따로 없어서다)."""
    for i, f in enumerate(findings or [], start=1):
        if not isinstance(f, dict):
            continue
        sev = str(f.get("severity") or "").lower()
        title = str(f.get("title") or "").strip()
        if sev not in ("critical", "warning", "info") or not title:
            continue
        key = f"finding/{i}"
        pkg.add("cae_finding", key, title, {
            "campaign": "campaign", "severity": sev, "title": title,
            "detail": str(f.get("detail") or "").strip() or None,
            "recommendation": str(f.get("recommendation") or "").strip() or None,
        })
        m = _PART_TITLE.match(title)
        if m and int(m.group(1)) in part_keys:
            pkg.relate("finding_about", ("cae_finding", key), ("cae_part", part_keys[int(m.group(1))]))


def _worst(rows, metric, pick=max):
    vals = [(r[1][metric], r[0]) for r in rows if r[1].get(metric) is not None]
    if not vals:
        return None, None
    v = pick(vals, key=lambda t: t[0])
    return v[0], v[1]


def envelope(rows: list[tuple[str, dict]], limits: list, evaluate, *, g_rule: bool = True) -> dict:
    """한 파트의 런별 응답 [(런 키, {어휘 속성: 덱 단위 값})] → cae_part 포락 속성.

    `limits`·`evaluate` 는 koo_sphere_report.yield_map 의 YieldLimit 목록과 evaluate
    (없으면 빈 목록·None — 안전율을 셈하지 않는다).
    """
    out: dict = {}
    vm, vm_run = _worst(rows, "peak_von_mises")
    mp, _ = _worst(rows, "peak_max_principal")
    mn, _ = _worst(rows, "min_principal", pick=min)
    ep, _ = _worst(rows, "peak_plastic_strain")
    g, g_run = _worst(rows, "peak_g")
    out.update({"worst_von_mises": vm, "worst_von_mises_run": vm_run, "worst_max_principal": mp,
                "worst_min_principal": mn, "worst_plastic_strain": ep, "worst_g": g, "worst_g_run": g_run})
    vms = [r[1]["peak_von_mises"] for r in rows if r[1].get("peak_von_mises") is not None]
    out["n_runs_measured"] = len(vms)
    if len(vms) >= 2 and statistics.fmean(vms) > 0:
        out["von_mises_cov"] = statistics.pstdev(vms) / statistics.fmean(vms)

    stress_sev = None
    if limits and evaluate is not None and vm is not None and vm > 0:
        v = evaluate(limits, {"von_mises": vm, "max_principal": mp})
        if v.sf is not None:
            out["min_safety_factor"] = v.sf
            out["safety_factor_complete"] = bool(v.complete)
            out["yield_limit"] = v.binding.value
            out["yield_criterion"] = v.binding.criterion
            if not v.complete:
                stress_sev = "warning"
            elif v.sf < 1.0:
                stress_sev = "critical"
            elif v.sf < 1.5:
                stress_sev = "warning"
            else:
                stress_sev = "ok"
    g_sev = None
    if g is not None and g_rule:
        g_sev = "critical" if g > 200000 else "warning" if g > 50000 else "ok"
    if stress_sev is None:
        out["severity"] = g_sev if g_sev in ("warning", "critical") else "unknown"
    else:
        out["severity"] = max((stress_sev, g_sev or "ok"), key=_RANK.get)
    return out


def run_safety_factor(resp: dict, limits: list, evaluate):
    """한 런의 안전율 — 그 런의 최대 응력으로 같은 규칙. 못 셈하면 None."""
    if not limits or evaluate is None:
        return None
    vm = resp.get("peak_von_mises")
    if vm is None or not vm > 0:
        return None
    return evaluate(limits, {"von_mises": vm, "max_principal": resp.get("peak_max_principal")}).sf
