# 리비전 간 파트 매칭 — YAML 매칭표(명시) > auto_match_identical(암묵)
"""파트 매칭.

규칙 (계획서 §0)
  1. YAML `parts` 표가 최우선. `~`/빈칸 = 그 리비전에 없음.
  2. 표에 없고 이름이 (정규화 후) 같은 파트는 auto_match_identical 로 자동 매칭.
  3. 표와 자동 매칭이 충돌하면 표가 이긴다 — 표가 선점한 이름은 자동 풀에서 제외.
  4. 2개 이상 리비전에 나타나야 매칭. 1개 리비전에만 있으면 '미매칭'.
     (파트 추가/삭제 이력도 비교 대상이므로 숨기지 않고 목록으로 남긴다.)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


class MatchingError(Exception):
    """unmatched: error 정책에서 미매칭 파트가 나온 경우."""


def normalize_name(name: str, enabled: bool = True) -> str:
    """대소문자/공백/`\\`·`/` 통일."""
    if not enabled:
        return name
    s = str(name).replace("\\", "/").strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*/\s*", "/", s)
    return s


@dataclass
class MatchResult:
    canonicals: list = field(default_factory=list)  # 표시 순서
    source: dict = field(default_factory=dict)  # canonical → 'table' | 'auto'
    per_rev: dict = field(default_factory=dict)  # canonical → [rev별 파트이름 | None]
    unmatched: list = field(default_factory=list)  # rev별 미매칭 파트 이름 목록
    warnings: list = field(default_factory=list)

    def presence(self, canonical: str) -> list:
        return [nm is not None for nm in self.per_rev.get(canonical, [])]


def _resolve(bundle, wanted: str, normalize: bool):
    """리비전 안에서 실제 파트 이름 찾기 (정확 → 정규화)."""
    names = bundle.part_names()
    if wanted in names:
        return wanted
    if not normalize:
        return None
    target = normalize_name(wanted, True)
    hits = [n for n in names if normalize_name(n, True) == target]
    return hits[0] if len(hits) >= 1 else None


def build_matching(bundles: list, parts_table: dict, options) -> MatchResult:
    n = len(bundles)
    res = MatchResult(per_rev={}, unmatched=[[] for _ in range(n)])
    claimed = [set() for _ in range(n)]

    # --- 1) 명시 매칭표 -------------------------------------------------
    for canonical, wanted_names in (parts_table or {}).items():
        row = []
        for i, wanted in enumerate(wanted_names):
            if wanted is None:
                row.append(None)
                continue
            actual = _resolve(bundles[i], wanted, options.name_normalize)
            if actual is None:
                res.warnings.append(
                    {
                        "code": "part_not_found",
                        "severity": "WARN",
                        "message": (
                            f"매칭표 '{canonical}' 의 {i + 1}번째 이름 '{wanted}' 를 "
                            f"리비전 '{bundles[i].label}' 에서 찾지 못했습니다 — 부재로 처리"
                        ),
                    }
                )
                row.append(None)
                continue
            if actual in claimed[i]:
                res.warnings.append(
                    {
                        "code": "duplicate_claim",
                        "severity": "WARN",
                        "message": (
                            f"리비전 '{bundles[i].label}' 의 파트 '{actual}' 가 매칭표에서 "
                            f"두 번 이상 지정되었습니다 ('{canonical}' 는 부재로 처리)"
                        ),
                    }
                )
                row.append(None)
                continue
            claimed[i].add(actual)
            row.append(actual)
        res.per_rev[canonical] = row
        res.source[canonical] = "table"
        res.canonicals.append(canonical)

    # --- 2) auto_match_identical ---------------------------------------
    groups = {}  # normkey → {rev_idx: name}
    for i, b in enumerate(bundles):
        for name in b.part_names():
            if name in claimed[i]:
                continue
            key = normalize_name(name, options.name_normalize)
            slot = groups.setdefault(key, {})
            if i in slot:
                res.warnings.append(
                    {
                        "code": "ambiguous_normalized",
                        "severity": "WARN",
                        "message": (
                            f"리비전 '{b.label}' 에서 정규화 후 동일한 파트 이름이 둘 이상입니다 "
                            f"('{slot[i]}' vs '{name}') — 앞의 것만 사용"
                        ),
                    }
                )
                continue
            slot[i] = name

    if options.auto_match_identical:
        auto_keys = sorted(groups)
        for key in auto_keys:
            slot = groups[key]
            if len(slot) < 2:
                idx = next(iter(slot))
                res.unmatched[idx].append(slot[idx])
                continue
            display = slot.get(min(slot))
            canonical = display
            suffix = 2
            while canonical in res.per_rev:
                canonical = f"{display} ({suffix})"
                suffix += 1
            res.per_rev[canonical] = [slot.get(i) for i in range(n)]
            res.source[canonical] = "auto"
            res.canonicals.append(canonical)
    else:
        for key in sorted(groups):
            for idx, name in groups[key].items():
                res.unmatched[idx].append(name)

    for lst in res.unmatched:
        lst.sort()

    total_unmatched = sum(len(u) for u in res.unmatched)
    if total_unmatched:
        detail = "; ".join(
            f"{bundles[i].label}: {', '.join(u)}" for i, u in enumerate(res.unmatched) if u
        )
        if options.unmatched == "error":
            raise MatchingError(
                f"매칭되지 않은 파트 {total_unmatched}개 (options.unmatched: error) — {detail}"
            )
        res.warnings.append(
            {
                "code": "unmatched_parts",
                "severity": "WARN",
                "message": f"매칭되지 않은 파트 {total_unmatched}개",
                "detail": detail,
            }
        )
    return res
