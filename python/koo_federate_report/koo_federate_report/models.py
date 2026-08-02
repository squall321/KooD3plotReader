# sphere/impact sidecar 를 종류와 무관하게 같은 형태로 표현하는 정규화 데이터 모델
"""RevisionBundle — 리비전 1개의 정규화 표현.

sphere(전각도 낙하)와 impact(전위치 부분충격)는 물리적으로 다른 시험이지만,
"비교 축 위의 한 지점(cell)에서 측정된 4개 피크 지표"라는 구조는 동일하다.
어댑터는 두 sidecar 를 모두 이 형태로 접어 넣고, matching/resample/compare 는
kind 를 거의 신경 쓰지 않는다.

- cells      : 비교 축 1지점 (impact = 위치, sphere = 각도)
- part_cells : (cell.key, 그 리비전의 파트 이름) → {g,s,e,d}
               파트 이름은 **리비전 고유 이름**이다. canonical 로의 환원은
               matching.py 가 만든 매핑을 compare.py 가 적용한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

#: 비교 대상 4개 지표 (peak acceleration / stress / strain / displacement)
METRIC_KEYS = ("g", "s", "e", "d")

#: 지표 → 단위 축 이름 (unit_labels 의 키)
METRIC_UNIT_AXIS = {"g": "acc", "s": "stress", "e": "strain", "d": "disp"}

METRIC_LABELS = {
    "g": "peak acc",
    "s": "peak stress",
    "e": "peak strain",
    "d": "peak disp",
}


@dataclass
class Trust:
    """이 cell 의 수치를 비교에 써도 되는가 (solver 게이트 결과)."""

    ok: bool = True
    reason: str = "no gate"

    def as_dict(self) -> dict:
        return {"ok": bool(self.ok), "reason": self.reason}


@dataclass
class Cell:
    """비교 축 위의 1지점."""

    key: str
    label: str = ""
    category: str = ""
    # impact 좌표
    x: Optional[float] = None
    y: Optional[float] = None
    # sphere 좌표
    roll: Optional[float] = None
    pitch: Optional[float] = None
    yaw: Optional[float] = None

    metrics: dict = field(default_factory=dict)  # {g,s,e,d}
    trust: Trust = field(default_factory=Trust)
    behavior: Optional[str] = None  # impact: no-contact / bounce / rebound
    energy: dict = field(default_factory=dict)  # ke_retention, diss_pct, ...
    extra: dict = field(default_factory=dict)


@dataclass
class RevisionBundle:
    """리비전 1개 = sidecar 1개."""

    label: str
    kind: str  # 'impact' | 'sphere'
    path: str = ""
    schema_version: Any = None
    meta: dict = field(default_factory=dict)
    unit_labels: dict = field(default_factory=dict)
    parts: dict = field(default_factory=dict)  # pid(int) → name(str)
    positions: list = field(default_factory=list)  # impact 원본 위치 목록
    angles: list = field(default_factory=list)  # sphere 원본 각도 목록
    cells: list = field(default_factory=list)  # list[Cell]
    part_cells: dict = field(default_factory=dict)  # (cell_key, part_name) → metrics
    kpi: dict = field(default_factory=dict)
    trust: dict = field(default_factory=dict)  # 집계 (n_ok / n_gated / basis)
    findings: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)

    def part_names(self) -> list:
        """파트 id 순서대로 정렬된 파트 이름 목록 (중복 제거)."""
        seen, out = set(), []
        for pid in sorted(self.parts):
            name = self.parts[pid]
            if name not in seen:
                seen.add(name)
                out.append(name)
        return out

    def cell_by_key(self, key: str):
        for c in self.cells:
            if c.key == key:
                return c
        return None

    def part_metric(self, cell_key: str, part_name: str, metric: str):
        rec = self.part_cells.get((cell_key, part_name))
        if not rec:
            return None
        return rec.get(metric)


@dataclass
class FederatedSet:
    """비교 대상 리비전 묶음."""

    kind: str
    baseline_idx: int  # 0-based
    revisions: list = field(default_factory=list)  # list[RevisionBundle]
    warnings: list = field(default_factory=list)

    @property
    def baseline(self) -> RevisionBundle:
        return self.revisions[self.baseline_idx]

    def labels(self) -> list:
        return [r.label for r in self.revisions]
