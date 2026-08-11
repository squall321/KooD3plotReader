# unified_analyzer 산출물에서 '값이 전혀 변하지 않는 지표'를 찾아내는 감사 스크립트
"""요소품질 Jacobian(±1 뿐)·뒤틀림(항상 0) 같은 가짜값을 잡아낸 방법을 자동화한다.

발상: 실제로 계산되는 물리량은 파트마다·시간마다 분산이 생긴다.
전 파트·전 스텝이 정확히 같은 값이면 둘 중 하나다.
  (a) 애초에 계산되지 않고 기본값이 그대로 나간다
  (b) 상수로 채워 넣는 가짜 계산이다
둘 다 보고서에서는 '측정된 정상값' 으로 읽히므로 위험하다.

정상적으로 상수인 경우도 있으니(예: 초기 상태의 체적비 1.0, 미계측 플래그가
붙은 칸) 자동 판정이 아니라 **검토 목록**을 뽑는 도구로 쓴다.

사용:
    python3 scripts/audit_constant_metrics.py <analysis_output_dir>
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

# 상수여도 문제가 아닌 컬럼 (식별자·시간축 등)
IGNORE_TOKENS = ("time", "elem", "node", "id", "count", "num", "index")

# 값이 없음을 뜻하는 표식. 이런 필드가 False 면 옆의 값이 상수여도 정상이다.
MEASURED_SUFFIX = "_measured"


def _is_ignorable(name: str) -> bool:
    low = name.lower()
    return any(tok in low for tok in IGNORE_TOKENS)


def _finite(vals):
    out = []
    for v in vals:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


def scan_csv(path: Path) -> tuple[list[str], list[tuple[str, float]]]:
    """(검사한 컬럼 전체, 상수인 컬럼 [(이름, 값)]) 반환."""
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        rows = [r for r in f if not r.startswith("#")]
    if len(rows) < 3:
        return [], []
    reader = csv.DictReader(rows)
    data = list(reader)
    if len(data) < 3:
        return [], []

    checked: list[str] = []
    hits: list[tuple[str, float]] = []
    for col in (reader.fieldnames or []):
        if _is_ignorable(col):
            continue
        vals = _finite(r.get(col) for r in data)
        if len(vals) < 3:
            continue
        checked.append(col)
        if len({round(v, 12) for v in vals}) == 1:
            hits.append((col, vals[0]))
    return checked, hits


def scan_json_records(records: list[dict], label: str) -> list[str]:
    """레코드 배열에서 전 레코드가 동일한 수치 필드를 찾는다."""
    if len(records) < 3:
        return []
    hits = []
    keys = [k for k in records[0] if not _is_ignorable(k)]
    for k in keys:
        # measured 플래그가 붙어 있고 모두 False 면 '미산출' 이 명시된 것 → 정상
        mk = None
        for cand in (k.replace("peak_", "").replace("min_", "").replace("max_", ""),):
            for full in records[0]:
                if full.endswith(MEASURED_SUFFIX) and cand.split("_")[0] in full:
                    mk = full
        if mk and all(r.get(mk) is False for r in records):
            continue

        vals = _finite(r.get(k) for r in records)
        if len(vals) < 3 or len(vals) != len(records):
            continue
        if len({round(v, 12) for v in vals}) == 1:
            hits.append(f"{label}.{k} = {vals[0]}")
    return hits


def main(root: Path) -> int:
    print(f"=== 상수 지표 감사: {root} ===\n")
    n_flag = 0

    # ---- CSV ----
    # 컬럼은 그 그룹의 **모든** 파일에서 상수이고 값도 같을 때만 표시한다.
    # (일부 파일에서만 상수인 것은 정상일 수 있다 — 예: 변형이 없는 파트)
    csvs = sorted(root.rglob("*.csv"))
    seen: dict[str, dict[str, int]] = {}      # group -> col -> 등장 파일 수
    const: dict[str, dict[str, set]] = {}     # group -> col -> 상수값 집합
    n_const: dict[str, dict[str, int]] = {}   # group -> col -> 상수였던 파일 수
    for p in csvs:
        group = p.parent.name
        checked, hits = scan_csv(p)
        for col in checked:
            seen.setdefault(group, {})[col] = seen.setdefault(group, {}).get(col, 0) + 1
        for col, val in hits:
            const.setdefault(group, {}).setdefault(col, set()).add(round(val, 12))
            n_const.setdefault(group, {})[col] = n_const.setdefault(group, {}).get(col, 0) + 1

    for group in sorted(seen):
        rows = []
        for col, n_seen in seen[group].items():
            if n_const.get(group, {}).get(col, 0) != n_seen:
                continue                       # 어떤 파일에서는 변한다 → 정상
            vals = const.get(group, {}).get(col, set())
            if len(vals) == 1:
                rows.append((col, next(iter(vals)), n_seen))
        if not rows:
            continue
        print(f"[CSV] {group}/")
        for col, val, n_seen in sorted(rows):
            print(f"    {col:<34} {n_seen}개 파일 전부에서 {val}")
            n_flag += 1
        print()

    # ---- JSON ----
    jf = root / "analysis_result.json"
    if jf.exists():
        d = json.loads(jf.read_text(encoding="utf-8", errors="replace"))
        for key in ("element_quality", "motion_analysis", "surface_strain_analysis"):
            recs = d.get(key) or []
            if isinstance(recs, list) and recs and isinstance(recs[0], dict):
                for h in scan_json_records(recs, key):
                    print(f"[JSON] {h}")
                    n_flag += 1

    print(f"\n검토 대상 {n_flag}건. 상수인 것이 물리적으로 타당한지 하나씩 확인할 것.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1])))
