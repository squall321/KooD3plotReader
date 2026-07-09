# payload 공용 헬퍼: _esc/_Encoder/_safe/_pct/_r4/_sparse_matrix (기계적 분할, 바이트 불변)
from __future__ import annotations

import dataclasses
import html
import json
import math
from enum import Enum
from typing import Any


def _esc(s: Any) -> str:
    """Escape a value for safe HTML interpolation."""
    return html.escape(str(s))


class _Encoder(json.JSONEncoder):
    """JSON encoder that knows about dataclasses, Enums, Paths and NaN/Inf."""

    def default(self, obj: Any) -> Any:  # type: ignore[override]
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return 0.0
        if hasattr(obj, "__fspath__"):
            return str(obj)
        return super().default(obj)


def _safe(v: float, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        if math.isnan(v) or math.isinf(v):
            return default
    except (TypeError, ValueError):
        return default
    return float(v)


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0.0, min(1.0, q)) * (len(s) - 1)
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return float(s[lo])
    f = k - lo
    return float(s[lo] * (1 - f) + s[hi] * f)


def _r4(v):
    """Round numeric value to <=4 significant figures, dropping trailing zeros.

    Preserves None / non-finite / non-numeric inputs unchanged. Uses the ``%.4g``
    format which respects magnitude (works equally for 0.000123 and 1234567).
    """
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    if math.isnan(f) or math.isinf(f):
        return 0.0
    if f == 0.0:
        return 0.0
    return float(f"{f:.4g}")


def _sparse_matrix(d, thresh_ratio=0.01):
    """Encode a dict-of-dict numeric matrix sparsely when >=30% of entries are
    zero (or below ``thresh_ratio * max_abs``).

    Returns either the original dense dict or
    ``{"_sparse": True, "rows": [[row_key, col_key, value], ...]}``.
    Non-numeric values are always kept (treated as significant).
    """
    if not isinstance(d, dict) or not d:
        return d
    # Gather all numeric magnitudes to compute threshold
    max_abs = 0.0
    total = 0
    for _rk, row in d.items():
        if not isinstance(row, dict):
            return d
        for _ck, v in row.items():
            total += 1
            try:
                f = abs(float(v))
                if f > max_abs:
                    max_abs = f
            except (TypeError, ValueError):
                pass
    if total == 0:
        return d
    thresh = max_abs * thresh_ratio
    # Count significant entries
    sig_rows = []
    n_drop = 0
    for rk, row in d.items():
        for ck, v in row.items():
            try:
                f = float(v)
                if abs(f) <= thresh:
                    n_drop += 1
                    continue
            except (TypeError, ValueError):
                pass
            sig_rows.append([rk, ck, v])
    if n_drop / total < 0.30:
        return d
    return {"_sparse": True, "rows": sig_rows}


def _pid_cast(pid):
    """Cast pos_id to int when possible, else keep original (e.g. DOE string IDs)."""
    try:
        return int(pid)
    except (ValueError, TypeError):
        return pid


def _downsample_indices(n: int, max_pts: int, peak_idx: int | None = None) -> list[int]:
    """스트라이드 다운샘플 인덱스 — 마지막 샘플과 peak 샘플을 항상 보존한다.

    true-peak-before-downsample 불변식 (SOTA P4): peak "스칼라"는 호출부가
    풀해상도에서 선계산하고, 여기서는 peak "샘플"이 곡선에서 사라지지 않도록
    splice 한다. step 은 ceil(n/max_pts) — 과거 ``n // 600`` 은 992//600=1 이라
    다운샘플이 사실상 미작동이었다 (임계값 설계 오류).
    """
    if max_pts <= 0 or n <= max_pts:
        return list(range(n))
    step = -(-n // max_pts)  # ceil
    keep = set(range(0, n, step))
    keep.add(n - 1)
    if peak_idx is not None and 0 <= peak_idx < n:
        keep.add(int(peak_idx))
    return sorted(keep)


def _argmax(values) -> int | None:
    """유한 값 기준 argmax 인덱스. 비어있거나 전부 비유한이면 None."""
    best_i, best_v = None, None
    for i, v in enumerate(values):
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(fv):
            continue
        if best_v is None or fv > best_v:
            best_i, best_v = i, fv
    return best_i
