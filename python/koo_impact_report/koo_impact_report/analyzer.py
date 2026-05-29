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
