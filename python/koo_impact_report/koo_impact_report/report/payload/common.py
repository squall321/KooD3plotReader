# payload 공용 헬퍼: _esc/_Encoder/_safe/_pct/_r4/_sparse_matrix (기계적 분할, 바이트 불변)
from __future__ import annotations

import html
import json
import math
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


