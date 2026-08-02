# 리비전마다 다른 DOE 격자를 공통 격자로 맞추고 실측/보간 마스크를 남긴다
"""공통 격자 정렬(resample).

정직성 원칙: 보간값을 실측처럼 보이게 하지 않는다.
샘플마다 `source` 와 `measured` 를 남기며, measured=True 는 **그 좌표에서 실제로
계산된 값**일 때만이다.

  source='exact'   실측 — 좌표(또는 각도 이름)가 완전히 일치
  source='nearest' 대체 — 다른 좌표의 실측값을 끌어다 씀 (measured=False, offset 기록)
  source='idw'     보간 — 주변 실측값의 역거리가중 (measured=False)
  source='missing' 없음 — 허용 반경 내 데이터 없음

모드
  impact : 좌표 완전일치 우선 → 'nearest'(허용 반경 = 격자 간격의 40%) / 'off'(교집합)
  sphere : 'idw'(공통 Fibonacci 격자) / 'nearest' / 'off'
  모든 리비전의 격자가 동일하면 모드와 무관하게 'identity' (불필요한 보간 금지)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median

from .models import Cell, Trust

#: 각도 일치 판정 허용치(도). sidecar 가 각도를 소수 4자리로 반올림해 저장하므로
#: 1e-6° 로 보면 사실상 같은 방향도 '보간'으로 강등된다. 실제 DOE 최소 간격(수 도)
#: 보다 3~4자릿수 작아 오검출 위험은 없다.
_ANGLE_EXACT_DEG = 1e-3


@dataclass
class Sample:
    """공통 격자 1노드 × 리비전 1개의 값."""

    source: str = "missing"
    measured: bool = False
    offset: float = None  # nearest/idw: 실측점까지의 거리 (impact=mm, sphere=deg)
    metrics: dict = field(default_factory=dict)
    trust: Trust = field(default_factory=lambda: Trust(False, "no data"))
    behavior: str = None
    energy: dict = field(default_factory=dict)
    cell_key: str = None  # 원본 cell key (part_cells 조회에 필요)


@dataclass
class GridNode:
    key: str
    label: str = ""
    category: str = ""
    x: float = None
    y: float = None
    roll: float = None
    pitch: float = None
    yaw: float = None
    per_rev: list = field(default_factory=list)  # list[Sample]


@dataclass
class AlignResult:
    nodes: list = field(default_factory=list)
    coverage: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


# --------------------------------------------------------------------------
# 공통 헬퍼
# --------------------------------------------------------------------------
def _sample_from_cell(cell: Cell, source: str, measured: bool, offset=None) -> Sample:
    return Sample(
        source=source,
        measured=measured,
        offset=offset,
        metrics=dict(cell.metrics),
        trust=Trust(cell.trust.ok, cell.trust.reason),
        behavior=cell.behavior,
        energy=dict(cell.energy),
        cell_key=cell.key,
    )


def _coverage_row(label: str, samples: list) -> dict:
    n = len(samples)
    counts = {"exact": 0, "nearest": 0, "idw": 0, "missing": 0}
    for s in samples:
        counts[s.source] = counts.get(s.source, 0) + 1
    return {
        "label": label,
        "n_grid": n,
        "exact": counts["exact"],
        "nearest": counts["nearest"],
        "idw": counts["idw"],
        "missing": counts["missing"],
        "measured_pct": round(100.0 * counts["exact"] / n, 1) if n else 0.0,
        "coverage_pct": round(100.0 * (n - counts["missing"]) / n, 1) if n else 0.0,
    }


# --------------------------------------------------------------------------
# impact — XY 격자
# --------------------------------------------------------------------------
def _xy_key(cell: Cell):
    return (cell.category, round(cell.x or 0.0, 6), round(cell.y or 0.0, 6))


def _grid_spacing(cells: list) -> float:
    """같은 face 안에서의 최근접 이웃 거리 중앙값 = 격자 간격."""
    pts = [(c.x, c.y) for c in cells if c.x is not None and c.y is not None]
    if len(pts) < 2:
        return 0.0
    dists = []
    for i, (xi, yi) in enumerate(pts):
        best = None
        for j, (xj, yj) in enumerate(pts):
            if i == j:
                continue
            d = math.hypot(xi - xj, yi - yj)
            if best is None or d < best:
                best = d
        if best:
            dists.append(best)
    return median(dists) if dists else 0.0


def _align_impact(bundles, baseline_idx, mode) -> AlignResult:
    res = AlignResult()
    if mode == "idw":
        res.warnings.append(
            {
                "code": "resample_fallback",
                "severity": "WARN",
                "message": "impact 는 구면 IDW 를 쓰지 않습니다 — resample: nearest 로 대체합니다",
            }
        )
        mode = "nearest"

    indexes = [{_xy_key(c): c for c in b.cells} for b in bundles]
    keysets = [set(ix) for ix in indexes]
    identical = all(ks == keysets[0] for ks in keysets)
    effective = "identity" if identical else mode

    base = bundles[baseline_idx]
    base_faces = {c.category for c in base.cells}
    all_faces = set()
    for b in bundles:
        all_faces |= {c.category for c in b.cells}
    incomparable_faces = sorted(all_faces - base_faces)
    if incomparable_faces:
        res.warnings.append(
            {
                "code": "face_incomparable",
                "severity": "WARN",
                "message": (
                    f"baseline 에 없는 face {incomparable_faces} 는 비교할 수 없습니다 "
                    "(face 별 그룹 비교 — 한쪽에만 있는 face 는 제외)"
                ),
                "detail": {"baseline_faces": sorted(base_faces), "incomparable": incomparable_faces},
            }
        )

    # face 별 허용 반경
    radius_by_face = {}
    for face in base_faces:
        spacing = _grid_spacing([c for c in base.cells if c.category == face])
        radius_by_face[face] = 0.4 * spacing

    nodes = []
    for cell in base.cells:
        node = GridNode(
            key=cell.key,
            label=cell.label,
            category=cell.category,
            x=cell.x,
            y=cell.y,
        )
        gkey = _xy_key(cell)
        radius = radius_by_face.get(cell.category, 0.0)
        for i, b in enumerate(bundles):
            hit = indexes[i].get(gkey)
            if hit is not None:
                node.per_rev.append(_sample_from_cell(hit, "exact", True, 0.0))
                continue
            if effective == "off" or mode == "off":
                node.per_rev.append(Sample(source="missing", trust=Trust(False, "격자 불일치 (resample: off)")))
                continue
            best, best_d = None, None
            for c in b.cells:
                if c.category != cell.category or c.x is None or c.y is None:
                    continue
                d = math.hypot(c.x - (cell.x or 0.0), c.y - (cell.y or 0.0))
                if best_d is None or d < best_d:
                    best, best_d = c, d
            if best is not None and radius > 0 and best_d <= radius:
                node.per_rev.append(_sample_from_cell(best, "nearest", False, round(best_d, 6)))
            else:
                node.per_rev.append(
                    Sample(
                        source="missing",
                        trust=Trust(
                            False,
                            f"허용 반경({radius:g}) 내 데이터 없음"
                            + (f" (최근접 {best_d:g})" if best_d is not None else ""),
                        ),
                    )
                )
        nodes.append(node)

    res.nodes = nodes
    res.coverage = {
        "mode": mode,
        "mode_effective": effective,
        "n_grid": len(nodes),
        "grid_source": f"baseline({base.label})",
        "radius_by_face": {k: round(v, 6) for k, v in radius_by_face.items()},
        "per_rev": [
            _coverage_row(b.label, [n.per_rev[i] for n in nodes]) for i, b in enumerate(bundles)
        ],
        "incomparable_faces": incomparable_faces,
    }
    return res


# --------------------------------------------------------------------------
# sphere — 구면 격자
# --------------------------------------------------------------------------
def _unit_vec(roll, pitch):
    """AngleCondition.to_spherical 기본 규약(lat=roll, lon=pitch) 과 동일."""
    lat = math.radians(roll or 0.0)
    lon = math.radians(pitch or 0.0)
    return (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))


def _ang_dist_deg(v1, v2) -> float:
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(v1, v2))))
    return math.degrees(math.acos(dot))


def _fibonacci_grid(n: int) -> list:
    """단위구 위 n개 준균일 점 → (roll=lat, pitch=lon) 도."""
    out = []
    ga = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(n):
        z = 1.0 - (2.0 * i + 1.0) / n
        r = math.sqrt(max(0.0, 1.0 - z * z))
        theta = ga * i
        x, y = r * math.cos(theta), r * math.sin(theta)
        lat = math.degrees(math.asin(max(-1.0, min(1.0, z))))
        lon = math.degrees(math.atan2(y, x))
        out.append((round(lat, 6), round(lon, 6)))
    return out


def _nn_spacing_deg(cells) -> float:
    vecs = [_unit_vec(c.roll, c.pitch) for c in cells]
    if len(vecs) < 2:
        return 0.0
    dists = []
    for i, vi in enumerate(vecs):
        best = None
        for j, vj in enumerate(vecs):
            if i == j:
                continue
            d = _ang_dist_deg(vi, vj)
            if best is None or d < best:
                best = d
        if best:
            dists.append(best)
    return median(dists) if dists else 0.0


def _idw_sample(target_vec, cells, vecs, power=2.0, k=4) -> Sample:
    """역거리가중 보간 — 가장 가까운 k개 실측점 사용."""
    order = sorted(range(len(cells)), key=lambda i: _ang_dist_deg(target_vec, vecs[i]))[:k]
    if not order:
        return Sample(source="missing", trust=Trust(False, "샘플 없음"))
    near_i = order[0]
    near_d = _ang_dist_deg(target_vec, vecs[near_i])
    metrics = {}
    for mk in ("g", "s", "e", "d"):
        num = den = 0.0
        for i in order:
            v = cells[i].metrics.get(mk)
            if v is None:
                continue
            d = _ang_dist_deg(target_vec, vecs[i])
            w = 1.0 / max(d, 1e-9) ** power
            num += w * v
            den += w
        metrics[mk] = (num / den) if den else None
    ok = all(cells[i].trust.ok for i in order)
    reason = "IDW 보간 (기여 샘플 전부 유효)" if ok else "IDW 기여 샘플 중 미신뢰 포함"
    return Sample(
        source="idw",
        measured=False,
        offset=round(near_d, 6),
        metrics=metrics,
        trust=Trust(ok, reason),
        behavior=cells[near_i].behavior,
        energy=dict(cells[near_i].energy),
        cell_key=cells[near_i].key,
    )


def _align_sphere(bundles, baseline_idx, mode) -> AlignResult:
    res = AlignResult()
    keysets = [{c.key for c in b.cells} for b in bundles]
    identical = all(ks == keysets[0] for ks in keysets)

    if identical:
        base = bundles[baseline_idx]
        indexes = [{c.key: c for c in b.cells} for b in bundles]
        nodes = []
        for cell in base.cells:
            node = GridNode(
                key=cell.key, label=cell.label, category=cell.category,
                roll=cell.roll, pitch=cell.pitch, yaw=cell.yaw,
            )
            node.per_rev = [_sample_from_cell(ix[cell.key], "exact", True, 0.0) for ix in indexes]
            nodes.append(node)
        res.nodes = nodes
        res.coverage = {
            "mode": mode, "mode_effective": "identity", "n_grid": len(nodes),
            "grid_source": f"baseline({base.label})",
            "per_rev": [_coverage_row(b.label, [n.per_rev[i] for n in nodes])
                        for i, b in enumerate(bundles)],
            "incomparable_faces": [],
        }
        return res

    vecs = [[_unit_vec(c.roll, c.pitch) for c in b.cells] for b in bundles]

    if mode == "off":
        common = set.intersection(*keysets) if keysets else set()
        base = bundles[baseline_idx]
        indexes = [{c.key: c for c in b.cells} for b in bundles]
        nodes = []
        for cell in base.cells:
            if cell.key not in common:
                continue
            node = GridNode(key=cell.key, label=cell.label, category=cell.category,
                            roll=cell.roll, pitch=cell.pitch, yaw=cell.yaw)
            node.per_rev = [_sample_from_cell(ix[cell.key], "exact", True, 0.0) for ix in indexes]
            nodes.append(node)
        res.warnings.append(
            {
                "code": "grid_mismatch",
                "severity": "WARN",
                "message": (
                    f"각도 격자가 리비전마다 다릅니다 — 교집합 {len(nodes)}개만 비교합니다 "
                    "(resample: off)"
                ),
            }
        )
        res.nodes = nodes
        res.coverage = {
            "mode": mode, "mode_effective": "off", "n_grid": len(nodes),
            "grid_source": "intersection",
            "per_rev": [_coverage_row(b.label, [n.per_rev[i] for n in nodes])
                        for i, b in enumerate(bundles)],
            "incomparable_faces": [],
        }
        return res

    if mode == "nearest":
        base = bundles[baseline_idx]
        tol = 0.4 * _nn_spacing_deg(base.cells)
        nodes = []
        for cell in base.cells:
            node = GridNode(key=cell.key, label=cell.label, category=cell.category,
                            roll=cell.roll, pitch=cell.pitch, yaw=cell.yaw)
            tv = _unit_vec(cell.roll, cell.pitch)
            for i, b in enumerate(bundles):
                exact = next((c for c in b.cells if c.key == cell.key), None)
                if exact is not None:
                    node.per_rev.append(_sample_from_cell(exact, "exact", True, 0.0))
                    continue
                best, best_d = None, None
                for j, c in enumerate(b.cells):
                    d = _ang_dist_deg(tv, vecs[i][j])
                    if best_d is None or d < best_d:
                        best, best_d = c, d
                if best is not None and best_d <= max(tol, _ANGLE_EXACT_DEG):
                    src = "exact" if best_d <= _ANGLE_EXACT_DEG else "nearest"
                    node.per_rev.append(
                        _sample_from_cell(best, src, src == "exact", round(best_d, 6))
                    )
                else:
                    node.per_rev.append(
                        Sample(source="missing",
                               trust=Trust(False, f"허용 각도({tol:.3f}°) 내 데이터 없음"))
                    )
            nodes.append(node)
        res.nodes = nodes
        res.coverage = {
            "mode": mode, "mode_effective": "nearest", "n_grid": len(nodes),
            "grid_source": f"baseline({base.label})", "tolerance_deg": round(tol, 4),
            "per_rev": [_coverage_row(b.label, [n.per_rev[i] for n in nodes])
                        for i, b in enumerate(bundles)],
            "incomparable_faces": [],
        }
        return res

    # mode == 'idw' — 공통 Fibonacci 격자
    n_grid = min(len(b.cells) for b in bundles)
    grid = _fibonacci_grid(n_grid)
    base = bundles[baseline_idx]
    base_vecs = vecs[baseline_idx]
    nodes = []
    for gi, (lat, lon) in enumerate(grid):
        tv = _unit_vec(lat, lon)
        # 카테고리는 baseline 최근접 실측점에서 추정 (합성 노드에는 원래 없음)
        cat = ""
        if base.cells:
            nearest_base = min(range(len(base.cells)),
                               key=lambda j: _ang_dist_deg(tv, base_vecs[j]))
            cat = base.cells[nearest_base].category
        node = GridNode(
            key=f"G{gi:04d}",
            label=f"G{gi:04d} (r{lat:g}, p{lon:g})",
            category=cat,
            roll=lat,
            pitch=lon,
        )
        for i, b in enumerate(bundles):
            exact = None
            for j, c in enumerate(b.cells):
                if _ang_dist_deg(tv, vecs[i][j]) <= _ANGLE_EXACT_DEG:
                    exact = c
                    break
            if exact is not None:
                node.per_rev.append(_sample_from_cell(exact, "exact", True, 0.0))
            else:
                node.per_rev.append(_idw_sample(tv, b.cells, vecs[i]))
        nodes.append(node)

    res.warnings.append(
        {
            "code": "resample_interpolated",
            "severity": "INFO",
            "message": (
                f"각도 격자가 리비전마다 다릅니다 — 공통 Fibonacci {n_grid}점에 IDW 보간했습니다. "
                "보간 셀은 실측이 아닙니다 (measured=False)."
            ),
        }
    )
    res.nodes = nodes
    res.coverage = {
        "mode": mode, "mode_effective": "idw", "n_grid": len(nodes),
        "grid_source": f"fibonacci({n_grid})",
        "per_rev": [_coverage_row(b.label, [n.per_rev[i] for n in nodes])
                    for i, b in enumerate(bundles)],
        "incomparable_faces": [],
    }
    return res


def align(bundles: list, baseline_idx: int, kind: str, mode: str) -> AlignResult:
    """리비전들을 공통 격자에 정렬한다."""
    if not bundles:
        return AlignResult()
    if kind == "impact":
        return _align_impact(bundles, baseline_idx, mode)
    return _align_sphere(bundles, baseline_idx, mode)
