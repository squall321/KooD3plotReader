"""Statistical analysis for multi-face DWI DOE results.

Implements §8 (core algorithms) and §18 (multi-face risk-score logic) of
``docs/PartialImpactReport_Plan.md``.
"""
from __future__ import annotations
from typing import Iterable

import numpy as np

from .models import (
    Finding, ImpactReport, PairResult, Severity,
)


# ---------------------------------------------------------------------------
# Per-part / per-face statistics
# ---------------------------------------------------------------------------

def _metric_values(results: Iterable[PairResult], metric: str) -> list[float]:
    out: list[float] = []
    for r in results:
        v = getattr(r, metric, 0.0)
        if v is not None:
            out.append(float(v))
    return out


def _stats(values: list[float]) -> dict:
    """Return max/p95/p50/p25/mean/cov for a 1-D array. Safe on empty."""
    if not values:
        return {"n": 0, "max": 0.0, "p95": 0.0, "p50": 0.0, "p25": 0.0,
                "mean": 0.0, "std": 0.0, "cov": 0.0}
    arr = np.asarray(values, dtype=float)
    mean = float(arr.mean())
    std = float(arr.std(ddof=0))
    return {
        "n": int(arr.size),
        "max": float(arr.max()),
        "p95": float(np.percentile(arr, 95)),
        "p50": float(np.percentile(arr, 50)),
        "p25": float(np.percentile(arr, 25)),
        "mean": mean,
        "std": std,
        "cov": (std / mean) if mean > 0 else 0.0,
    }


def compute_per_part_stats(results: list[PairResult]) -> dict[int, dict]:
    """For each part, aggregate stats across all (face, position) pairs.

    Returns ``{part_id: {metric: stats_dict}}`` for the 4 standard metrics.
    """
    by_part: dict[int, list[PairResult]] = {}
    for r in results:
        by_part.setdefault(r.part_id, []).append(r)

    out: dict[int, dict] = {}
    for pid, rs in by_part.items():
        out[pid] = {
            "peak_g":      _stats(_metric_values(rs, "peak_g")),
            "peak_stress": _stats(_metric_values(rs, "peak_stress")),
            "peak_strain": _stats(_metric_values(rs, "peak_strain")),
            "peak_disp":   _stats(_metric_values(rs, "peak_disp")),
        }
    return out


def compute_per_face_stats(results: list[PairResult]) -> dict[str, dict]:
    """Aggregate stats per face (across all positions and parts)."""
    by_face: dict[str, list[PairResult]] = {}
    for r in results:
        by_face.setdefault(r.face, []).append(r)

    out: dict[str, dict] = {}
    for face, rs in by_face.items():
        out[face] = {
            "peak_g":      _stats(_metric_values(rs, "peak_g")),
            "peak_stress": _stats(_metric_values(rs, "peak_stress")),
            "peak_strain": _stats(_metric_values(rs, "peak_strain")),
            "peak_disp":   _stats(_metric_values(rs, "peak_disp")),
            "n_results":   len(rs),
        }
    return out


# ---------------------------------------------------------------------------
# Pair-level severity score (§8.6)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS = {"g": 0.5, "s": 0.3, "e": 0.2}


def compute_severity_score(
    part_result: PairResult,
    weights: dict[str, float] | None = None,
    max_vals: dict[str, float] | None = None,
) -> float:
    """Standardized 0~10 severity score from per-pair peaks.

    Each metric is normalized by its global ``max_vals`` to put them on the
    same 0~1 scale, weighted, and rescaled to 0~10.
    """
    w = weights or DEFAULT_WEIGHTS
    if not max_vals:
        return 0.0

    def _n(v: float, k: str) -> float:
        m = max_vals.get(k, 0.0)
        return (v / m) if m > 0 else 0.0

    g = _n(part_result.peak_g,      "peak_g")
    s = _n(part_result.peak_stress, "peak_stress")
    e = _n(part_result.peak_strain, "peak_strain")
    score = (w.get("g", 0) * g + w.get("s", 0) * s + w.get("e", 0) * e)
    return float(min(10.0, max(0.0, score * 10.0)))


# ---------------------------------------------------------------------------
# Spatial metrics (§8.3, §8.4)
# ---------------------------------------------------------------------------

def compute_influence_area(part_id: int, results: list[PairResult],
                            threshold: float, metric: str = "peak_g") -> int:
    """Count positions where ``part_id``'s ``metric`` exceeds ``threshold``."""
    count = 0
    for r in results:
        if r.part_id != part_id:
            continue
        if float(getattr(r, metric, 0.0)) > threshold:
            count += 1
    return count


def compute_centroid(part_id: int, results: list[PairResult],
                      metric: str = "peak_g") -> tuple[float, float]:
    """Weighted impact centroid for ``part_id`` (§8.4).

    Returns (cx, cy) = Σ(w·x)/Σw averaged over positions for one part.
    """
    xs: list[float] = []
    ys: list[float] = []
    ws: list[float] = []
    for r in results:
        if r.part_id != part_id:
            continue
        w = float(getattr(r, metric, 0.0))
        if w <= 0:
            continue
        xs.append(r.position.x)
        ys.append(r.position.y)
        ws.append(w)
    total = sum(ws)
    if total <= 0 or not xs:
        return (0.0, 0.0)
    cx = sum(x * w for x, w in zip(xs, ws)) / total
    cy = sum(y * w for y, w in zip(ys, ws)) / total
    return (cx, cy)


# ---------------------------------------------------------------------------
# Findings generation
# ---------------------------------------------------------------------------

def _global_max(results: list[PairResult]) -> dict[str, float]:
    return {
        "peak_g":      max((r.peak_g      for r in results), default=0.0),
        "peak_stress": max((r.peak_stress for r in results), default=0.0),
        "peak_strain": max((r.peak_strain for r in results), default=0.0),
        "peak_disp":   max((r.peak_disp   for r in results), default=0.0),
    }


def generate_findings(
    report: ImpactReport,
    threshold_critical: float = 5.0e5,
    threshold_warning: float = 1.0e5,
    yield_stress: float = 0.0,
) -> list[Finding]:
    """Auto-derive CRITICAL/WARNING/INFO findings from results."""
    findings: list[Finding] = []

    if not report.results:
        findings.append(Finding(
            severity=Severity.WARNING,
            title="No pair results found",
            detail="The loader produced zero (face × position × part) results.",
            recommendation="Verify scenario.json and that each F*/Run_* contains analysis_result.json.",
        ))
        return findings

    n_face = len(report.faces)
    n_pos = sum(len(v) for v in report.positions_by_face.values())
    findings.append(Finding(
        severity=Severity.INFO,
        title=f"{n_face} face(s), {n_pos} position(s), {len(report.parts)} part(s)",
        detail=(
            f"Generation mode: {report.generation_mode}, "
            f"boundary={report.boundary_distance:.1f} mm, "
            f"offset={report.offset_distance:.3f} mm, "
            f"impactor={report.impactor.type} h={report.impactor.height:.0f} mm"
        ),
        recommendation="",
    ))

    gmax = _global_max(report.results)

    # Per-part worst pair
    by_part: dict[int, PairResult] = {}
    for r in report.results:
        cur = by_part.get(r.part_id)
        if cur is None or r.peak_g > cur.peak_g:
            by_part[r.part_id] = r

    part_lookup = {p.part_id: p for p in report.parts}
    for pid, worst in by_part.items():
        pi = part_lookup.get(pid)
        name = pi.part_name if pi else f"Part {pid}"

        if worst.peak_g >= threshold_critical:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                title=f"{name}: peak {worst.peak_g/1e6:.2f} MG at {worst.position.pos_id}",
                detail=(
                    f"face={worst.face} (x,y)=({worst.position.x:.1f},{worst.position.y:.1f}) "
                    f"σ={worst.peak_stress:.1f} MPa, ε={worst.peak_strain:.4f}"
                ),
                recommendation="Verify component shock tolerance; consider reinforcement.",
            ))
        elif worst.peak_g >= threshold_warning:
            findings.append(Finding(
                severity=Severity.WARNING,
                title=f"{name}: peak {worst.peak_g/1e6:.2f} MG at {worst.position.pos_id}",
                detail=(
                    f"face={worst.face} (x,y)=({worst.position.x:.1f},{worst.position.y:.1f})"
                ),
                recommendation="Monitor — close to critical threshold.",
            ))

        if yield_stress > 0 and worst.peak_stress > yield_stress:
            sf = yield_stress / worst.peak_stress if worst.peak_stress > 0 else float("inf")
            findings.append(Finding(
                severity=Severity.CRITICAL,
                title=f"{name}: stress exceeds yield ({worst.peak_stress:.1f} > {yield_stress:.1f} MPa)",
                detail=f"Safety Factor = {sf:.2f} at {worst.position.pos_id}",
                recommendation="Material review or design change required.",
            ))

    findings.append(Finding(
        severity=Severity.INFO,
        title="Global peaks",
        detail=(
            f"G={gmax['peak_g']/1e6:.2f} MG, σ={gmax['peak_stress']:.1f} MPa, "
            f"ε={gmax['peak_strain']:.4f}, d={gmax['peak_disp']:.2f} mm"
        ),
        recommendation="",
    ))

    return findings


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------

def analyze(
    report: ImpactReport,
    threshold_critical: float = 5.0e5,
    threshold_warning: float = 1.0e5,
    yield_stress: float = 0.0,
) -> ImpactReport:
    """Populate ``report.findings`` in-place and return ``report``."""
    report.findings = generate_findings(
        report,
        threshold_critical=threshold_critical,
        threshold_warning=threshold_warning,
        yield_stress=yield_stress,
    )
    return report
