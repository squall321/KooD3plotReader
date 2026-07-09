"""Statistical analysis for multi-face DWI DOE results.

Implements §8 (core algorithms) and §18 (multi-face risk-score logic) of
``docs/PartialImpactReport_Plan.md``.
"""
from __future__ import annotations
import math
from typing import Iterable

import numpy as np

from .models import (
    Finding, ImpactReport, PairResult, Severity, TrajectoryClusters,
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

# Severity scoring is opt-in. Callers must supply explicit weights (e.g. via
# the ``--severity-weight`` CLI argument). The previous module-level
# ``DEFAULT_WEIGHTS`` was a hidden assumption that biased every report
# towards a fixed g/s/e ratio; removing it forces the caller to think about
# which metrics matter for their specific test.


def compute_severity_score(
    part_result: PairResult,
    weights: dict[str, float] | None = None,
    max_vals: dict[str, float] | None = None,
    score_scale: float = 1.0,
) -> float | None:
    """Weighted severity score in the unit chosen by ``score_scale``.

    Returns ``None`` if no weights are supplied — callers should then omit
    the severity column from their report rather than substitute a fake
    "0" score. ``score_scale`` is the output rescale (default 1.0 keeps the
    natural [0, 1] range; pass 10 for a 0–10 dial, 100 for percent).
    """
    if not weights or not max_vals:
        return None

    def _n(v: float, k: str) -> float:
        m = max_vals.get(k, 0.0)
        return (v / m) if m > 0 else 0.0

    g = _n(part_result.peak_g,      "peak_g")
    s = _n(part_result.peak_stress, "peak_stress")
    e = _n(part_result.peak_strain, "peak_strain")
    score = (weights.get("g", 0) * g + weights.get("s", 0) * s + weights.get("e", 0) * e)
    return float(min(score_scale, max(0.0, score * score_scale)))


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
    threshold_critical: float | None = None,
    threshold_warning: float | None = None,
    yield_stress_by_part: dict[int, float] | None = None,
) -> list[Finding]:
    """Auto-derive CRITICAL/WARNING/INFO findings from results.

    All thresholds are caller-supplied: there is no implicit unit-dependent
    default. If the caller wants automatic severity, they should derive the
    thresholds from material data (e.g. per-part yield stress) and/or
    statistical percentiles of the result distribution.

    Args:
        threshold_critical: peak_g level (in the dataset's native units)
            above which a finding is CRITICAL. ``None`` disables.
        threshold_warning: similar, lower bound. ``None`` disables.
        yield_stress_by_part: optional ``{part_id: yield_stress}`` mapping
            (units must match ``peak_stress``). Stress exceedance findings
            are only emitted for parts that supply a non-zero yield value.
    """
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
            f"impactor={report.impactor.type or 'unknown'} h={report.impactor.height:.0f} mm"
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
    yields = yield_stress_by_part or {}
    for pid, worst in by_part.items():
        pi = part_lookup.get(pid)
        name = pi.part_name if pi else f"Part {pid}"

        if threshold_critical is not None and worst.peak_g >= threshold_critical:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                title=f"{name}: peak_g {worst.peak_g:.3e} at {worst.position.pos_id}",
                detail=(
                    f"face={worst.face} (x,y)=({worst.position.x:.1f},{worst.position.y:.1f}) "
                    f"σ={worst.peak_stress:.3e}, ε={worst.peak_strain:.4f}"
                ),
                recommendation="Verify component shock tolerance; consider reinforcement.",
            ))
        elif threshold_warning is not None and worst.peak_g >= threshold_warning:
            findings.append(Finding(
                severity=Severity.WARNING,
                title=f"{name}: peak_g {worst.peak_g:.3e} at {worst.position.pos_id}",
                detail=(
                    f"face={worst.face} (x,y)=({worst.position.x:.1f},{worst.position.y:.1f})"
                ),
                recommendation="Monitor — close to critical threshold.",
            ))

        # Per-part yield-stress check uses the part's OWN yield stress (from
        # *MAT_ card), not a global one. Skipped when not supplied.
        sy = float(yields.get(pid, 0.0) or 0.0)
        if sy > 0 and worst.peak_stress > sy:
            sf = sy / worst.peak_stress if worst.peak_stress > 0 else float("inf")
            findings.append(Finding(
                severity=Severity.CRITICAL,
                title=f"{name}: stress exceeds yield ({worst.peak_stress:.3e} > {sy:.3e})",
                detail=f"Safety Factor = {sf:.2f} at {worst.position.pos_id}",
                recommendation="Material review or design change required.",
            ))

    findings.append(Finding(
        severity=Severity.INFO,
        title="Global peaks",
        detail=(
            f"peak_g={gmax['peak_g']:.3e}, σ={gmax['peak_stress']:.3e}, "
            f"ε={gmax['peak_strain']:.4f}, d={gmax['peak_disp']:.3e}"
        ),
        recommendation="",
    ))

    # 구조화 로드 진단 → 집계 Finding (P1d — stdout 소멸 금지의 마지막 단).
    findings.extend(_findings_from_load_issues(report))
    # CLI 임계값 없이도 동작하는 통계 outlier 게이트 (절대 임계값 발명 금지).
    findings.extend(_statistical_outlier_findings(report))

    return findings


# ---------------------------------------------------------------------------
# Load-issue promotion + statistical outliers (P1d)
# ---------------------------------------------------------------------------

def _findings_from_load_issues(report: ImpactReport) -> list[Finding]:
    """report.load_issues + impactor 상태를 집계 Finding 으로 승격.

    하드 룰: Finding 은 kind 당 **집계 1건** (run 목록은 detail 에) — 300+ 위치
    에서 Finding 폭발 방지 (docs/impact-sota-checklist.md P1d).
    """
    findings: list[Finding] = []
    issues = list(getattr(report, "load_issues", []) or [])

    by_kind: dict[str, list[dict]] = {}
    for it in issues:
        by_kind.setdefault(it.get("kind", "unknown"), []).append(it)

    def _names(items: list[dict], cap: int = 12) -> str:
        names = [str(i.get("pos_name") or "?") for i in items]
        head = ", ".join(names[:cap])
        return head + (f" 외 {len(names) - cap}건" if len(names) > cap else "")

    n_runs = int(report.doe_config.get("n_runs", 0) or 0) or max(
        1, sum(len(v) for v in report.positions_by_face.values()))

    # 1) 런 로드 실패 — 2% 초과면 CRITICAL
    failed = by_kind.get("run-load-failed", [])
    if failed:
        sev = Severity.CRITICAL if len(failed) > 0.02 * n_runs else Severity.WARNING
        findings.append(Finding(
            severity=sev,
            title=f"Runs failed to load ({len(failed)}/{n_runs})",
            detail=_names(failed) + " — " + "; ".join(
                sorted({f"{i.get('exc_class')}" for i in failed if i.get('exc_class')})),
            recommendation="해당 run 의 로그/데이터를 확인하세요. 리포트는 나머지 run 만 반영합니다.",
        ))

    # 2) impactor 불일치 — loader 의 severity_hint 로 승격
    mism = by_kind.get("impactor-mismatch", [])
    if mism:
        crit = any(i.get("severity_hint") == "critical" for i in mism)
        findings.append(Finding(
            severity=Severity.CRITICAL if crit else Severity.WARNING,
            title=f"Impactor inconsistency across runs ({len(mism)}/{n_runs})",
            detail=_names(mism) + " — 예: " + str(mism[0].get("msg", ""))[:160],
            recommendation="DOE run 들이 동일 impactor 로 생성됐는지 확인 (혼입 의심).",
        ))

    # 3) binout 에너지 — 파일 부재(INFO, 솔버 출력 설정)와 파싱 실패(WARNING) 구분
    binout = by_kind.get("binout", [])
    if binout:
        missing = [i for i in binout if i.get("exc_class") == "binout-missing"]
        broken = [i for i in binout if i.get("exc_class") != "binout-missing"]
        if broken:
            findings.append(Finding(
                severity=Severity.WARNING,
                title=f"Binout energy parse failed ({len(broken)}/{n_runs})",
                detail=_names(broken) + " — " + "; ".join(
                    sorted({str(i.get('exc_class')) for i in broken})),
                recommendation="matsum/rcforc 기반 질량·접촉·에너지 지표가 해당 run 에서 빠집니다.",
            ))
        if missing:
            findings.append(Finding(
                severity=Severity.INFO,
                title=f"Binout not written ({len(missing)}/{n_runs})",
                detail=_names(missing),
                recommendation="에너지 지표가 필요하면 deck 의 *DATABASE_BINARY 출력 설정을 확인하세요.",
            ))

    # 4) DOE 인덱스 fallback
    doe_fb = by_kind.get("doe-index-fallback", [])
    if doe_fb:
        findings.append(Finding(
            severity=Severity.INFO,
            title=f"DOE index fallback naming ({len(doe_fb)}/{n_runs})",
            detail=_names(doe_fb),
            recommendation="step_config *Description 의 DOE### 토큰을 확인하세요.",
        ))

    # 5) impactor geometry / mass 상태 (report.impactor 직접 판정)
    imp = report.impactor
    if getattr(imp, "geometry_source", "") == "motion-bbox":
        findings.append(Finding(
            severity=Severity.WARNING,
            title="Impactor geometry estimated from motion bbox",
            detail=(f"radius={imp.radius:.4g} (bbox 과대평가 가능) — "
                    "step_config.txt 부재 시 fallback 경로"),
            recommendation="step_config.txt 또는 scenario.json 에 impactor geometry 를 명시하세요.",
        ))
    if imp.mass_override is None and (imp.mass or 0.0) <= 0.0:
        findings.append(Finding(
            severity=Severity.WARNING,
            title="Impactor mass unknown",
            detail="matsum/keyword 어느 쪽에서도 질량을 유도하지 못함 — KE 지표 무효.",
            recommendation="binout(matsum) 출력 또는 impactor geometry+density 를 확인하세요.",
        ))

    return findings


def _statistical_outlier_findings(
    report: ImpactReport,
    z_threshold: float = 3.5,
    min_positions: int = 8,
    max_findings: int = 10,
) -> list[Finding]:
    """위치별 worst 응답의 robust z-score(중앙값/MAD) outlier 를 WARNING 승격.

    절대 임계값을 발명하지 않는 데이터 유도 게이트 — CLI --threshold-* 가
    없어도 이상 위치를 표면화한다. N < min_positions 에서는 MAD 가 불안정해
    스킵. metric 전체 합산 max_findings 로 캡 (Finding 폭발 방지).
    """
    findings: list[Finding] = []
    # 위치별 worst 값 집계
    per_pos: dict[str, dict[str, float]] = {}
    for r in report.results:
        d = per_pos.setdefault(r.position.pos_id, {"peak_g": 0.0, "peak_stress": 0.0})
        d["peak_g"] = max(d["peak_g"], float(r.peak_g or 0.0))
        d["peak_stress"] = max(d["peak_stress"], float(r.peak_stress or 0.0))

    if len(per_pos) < min_positions:
        return findings

    candidates: list[tuple[float, str, str, float]] = []  # (|z|, pos_id, metric, val)
    for metric in ("peak_g", "peak_stress"):
        vals = sorted(v[metric] for v in per_pos.values())
        n = len(vals)
        med = vals[n // 2]
        mad = sorted(abs(v - med) for v in vals)[n // 2]
        if mad <= 0:
            continue  # 퇴화 분포(전부 동일) — z 무의미
        for pos_id, d in per_pos.items():
            z = 0.6745 * (d[metric] - med) / mad
            if abs(z) > z_threshold:
                candidates.append((abs(z), pos_id, metric, d[metric]))

    candidates.sort(reverse=True)
    for absz, pos_id, metric, val in candidates[:max_findings]:
        findings.append(Finding(
            severity=Severity.WARNING,
            title=f"{pos_id}: statistical outlier for {metric} (|z|={absz:.1f})",
            detail=f"{metric}={val:.3e} — robust z-score (median/MAD) 기준",
            recommendation="해당 위치의 deck/결과를 우선 검토 (국소 취약부 또는 해석 이상).",
        ))
    return findings


# ---------------------------------------------------------------------------
# Impactor-trajectory clustering
# ---------------------------------------------------------------------------

# Feature signature used to assign human-readable archetypes to k-means
# centroids. Each row is the expected z-scored shape of:
#   [ke_retention, t_first_contact_norm, max_penetration_depth_norm,
#    rebound_speed_norm, lateral_speed_norm]
# These are *labels*, not physical thresholds — they are the user-supplied
# vocabulary used to give clusters human-readable names. Callers can pass
# their own dict to ``compute_trajectory_clusters`` to use a different
# taxonomy (e.g. domain-specific drop-test categories).
DEFAULT_ARCHETYPE_SIGNATURES = {
    "bounce-back":  np.array([+1.2,  0.0, -0.8, +1.2, -0.5]),
    "embed":        np.array([-1.2,  0.0, +1.2, -1.2, -0.5]),
    "slide":        np.array([ 0.0,  0.0, -0.3, +0.5, +1.5]),
    "slow-decay":   np.array([ 0.0,  0.0,  0.0, -0.3, -0.3]),
    "fast-decay":   np.array([-0.6,  0.0, +0.6, -0.6,  0.0]),
}
# Backwards-compat alias kept for callers; new code should use the public
# DEFAULT_ARCHETYPE_SIGNATURES symbol and pass an explicit override when
# needed.
_ARCHETYPE_SIGNATURES = DEFAULT_ARCHETYPE_SIGNATURES


def _kmeans_lloyd(
    X: np.ndarray,
    k: int,
    max_iter: int = 100,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Tiny numpy-only k-means (Lloyd's algorithm).

    Returns ``(labels, centroids)``. Empty clusters are re-seeded from the
    farthest point.
    """
    rng = np.random.default_rng(seed)
    n = X.shape[0]
    if n == 0:
        return np.zeros(0, dtype=int), np.zeros((0, X.shape[1]))
    k = max(1, min(k, n))

    # k-means++ init
    centers = [X[rng.integers(n)]]
    for _ in range(k - 1):
        d2 = np.min(
            np.linalg.norm(X[:, None, :] - np.array(centers)[None, :, :], axis=2) ** 2,
            axis=1,
        )
        total = d2.sum()
        if total <= 1e-12:
            centers.append(X[rng.integers(n)])
            continue
        probs = d2 / total
        idx = rng.choice(n, p=probs)
        centers.append(X[idx])
    centroids = np.array(centers)

    labels = np.zeros(n, dtype=int)
    for _ in range(max_iter):
        d = np.linalg.norm(X[:, None, :] - centroids[None, :, :], axis=2)
        new_labels = np.argmin(d, axis=1)
        if np.array_equal(new_labels, labels):
            labels = new_labels
            break
        labels = new_labels
        for ci in range(k):
            mask = labels == ci
            if mask.any():
                centroids[ci] = X[mask].mean(axis=0)
            else:
                # Empty cluster — reseed from farthest point.
                far_idx = int(np.argmax(d.min(axis=1)))
                centroids[ci] = X[far_idx]
    return labels, centroids


def _assign_archetypes(
    centroids: np.ndarray,
    signatures: dict | None = None,
) -> list[str]:
    """Pick the closest archetype label for each centroid.

    Distinct labels are preferred — if two centroids share the same closest
    archetype, the second-closest is used for the runner-up. Pass a custom
    ``signatures`` dict to override ``DEFAULT_ARCHETYPE_SIGNATURES``.
    """
    sigs = list((signatures or DEFAULT_ARCHETYPE_SIGNATURES).items())
    sig_names = [name for name, _ in sigs]
    sig_vecs = np.array([v for _, v in sigs])

    # Cost matrix: row=centroid, col=archetype
    dists = np.linalg.norm(centroids[:, None, :] - sig_vecs[None, :, :], axis=2)

    assigned: list[str] = []
    used: set[str] = set()
    for ci in range(centroids.shape[0]):
        order = np.argsort(dists[ci])
        choice = sig_names[order[0]]
        for idx in order:
            cand = sig_names[idx]
            if cand not in used:
                choice = cand
                break
        used.add(choice)
        assigned.append(choice)
    return assigned


def compute_trajectory_clusters(
    report: ImpactReport,
    k: int = 4,
    seed: int = 0,
    archetype_signatures: dict | None = None,
) -> TrajectoryClusters | None:
    """Cluster runs by impactor-trajectory feature vectors (k-means).

    Features (per run):
      ke_retention, t_first_contact_norm, max_penetration_depth_norm,
      rebound_speed_norm, lateral_speed_norm

    Returns ``None`` if fewer than ``k`` runs carry trajectory data. Each entry
    in ``labels`` corresponds (in order) to ``report.results``; runs without
    trajectory data receive label ``-1``.
    """
    features_used = [
        "ke_retention", "t_first_contact_norm",
        "max_penetration_depth_norm", "rebound_speed_norm", "lateral_speed_norm",
    ]

    # Build one feature vector per UNIQUE trajectory (keyed by pos_id).
    pos_ids: list[str] = []
    feats: list[list[float]] = []
    # Normalisers — observed maxima for the per-run scalars.
    max_pen = 1e-6
    max_rebound = 1e-6
    max_lat = 1e-6
    max_tfc = 1e-6
    for pos_id, traj in report.impactor_trajectories.items():
        if not traj.times:
            continue
        lat_speed = math.hypot(traj.vel_x[-1], traj.vel_y[-1])
        tfc = traj.t_first_contact or 0.0
        max_pen = max(max_pen, traj.max_penetration_depth)
        max_rebound = max(max_rebound, traj.rebound_speed)
        max_lat = max(max_lat, lat_speed)
        max_tfc = max(max_tfc, tfc)
        pos_ids.append(pos_id)
        feats.append([
            float(traj.ke_retention),
            float(tfc),
            float(traj.max_penetration_depth),
            float(traj.rebound_speed),
            float(lat_speed),
        ])

    if len(feats) < max(k, 2):
        return None

    X_raw = np.array(feats, dtype=float)
    # Normalize specific raw scales to [0, 1] before z-scoring (matches spec
    # naming: "_norm" features).
    norms = np.array([1.0, max_tfc, max_pen, max_rebound, max_lat])
    X_norm = X_raw / np.where(norms > 0, norms, 1.0)
    # Standardize (z-score) across the sample.
    mu = X_norm.mean(axis=0)
    sd = X_norm.std(axis=0)
    sd[sd < 1e-9] = 1.0
    X = (X_norm - mu) / sd

    # Try sklearn first; fall back to Lloyd's.
    try:
        from sklearn.cluster import KMeans  # type: ignore
        km = KMeans(n_clusters=k, n_init=10, random_state=seed)
        labels_compact = km.fit_predict(X)
        centroids = km.cluster_centers_
    except Exception:
        labels_compact, centroids = _kmeans_lloyd(X, k=k, seed=seed)

    archetypes = _assign_archetypes(centroids, signatures=archetype_signatures)

    # Map back to per-PairResult labels (results order).
    pos2label = {pos_ids[i]: int(labels_compact[i]) for i in range(len(pos_ids))}
    per_result_labels = [
        pos2label.get(r.position.pos_id, -1) for r in report.results
    ]

    return TrajectoryClusters(
        n_clusters=int(centroids.shape[0]),
        labels=per_result_labels,
        centroids=[[float(v) for v in row] for row in centroids],
        archetypes=archetypes,
        features_used=features_used,
    )


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------

def analyze(
    report: ImpactReport,
    threshold_critical: float | None = None,
    threshold_warning: float | None = None,
    yield_stress_by_part: dict[int, float] | None = None,
) -> ImpactReport:
    """Populate ``report.findings`` in-place and return ``report``.

    Thresholds are explicit (no implicit unit-dependent defaults). When the
    caller does not supply them, severity findings are simply omitted.
    """
    report.findings = generate_findings(
        report,
        threshold_critical=threshold_critical,
        threshold_warning=threshold_warning,
        yield_stress_by_part=yield_stress_by_part,
    )
    report.trajectory_clusters = compute_trajectory_clusters(report)
    return report
