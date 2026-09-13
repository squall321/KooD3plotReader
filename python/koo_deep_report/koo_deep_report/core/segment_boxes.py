# 파트를 박스·극좌표 구간으로 쪼개 구간별 통계를 내는 모듈 — 모놀리식 파트 대응
"""파트 내 구간(segment) 분할.

**왜 이 모듈이 있나.**
후처리의 최소 단위는 파트다. 그런데 인터포저 볼이 **파트 하나로 묶인** 과제가
있다(T3/T4/카메라는 인터포저가 1파트, T1 은 12파트). 파트 단위로는 실물 크랙
위치와 대조할 수 없어 따로 스크립트를 돌려 왔다.

여기서는 구간 정의(JSON)를 받아 점을 구간에 배정하고 구간별 통계를 낸다.
정의는 **박스**(축 정렬)와 **극좌표 부채꼴**(중심·반지름·각도) 두 가지다.

**구간 정의 JSON.**
```json
{"part_id": 1234,
 "segments": [
   {"name": "INP_01", "type": "box",
    "min": [0, 0, 0], "max": [10, 10, 5]},
   {"name": "OUT_N",  "type": "sector",
    "center": [50, 50, 0], "r_min": 8, "r_max": 12,
    "theta_min_deg": -22.5, "theta_max_deg": 22.5, "axis": "z"}
 ]}
```

**설계 규칙.** 예외를 던지지 않는다. 정의가 겹치면 **먼저 적은 구간**이 이긴다
(결정적이어야 같은 입력이 같은 답을 낸다). 어디에도 안 들어간 점은 버리지 않고
`unassigned` 로 센다 — 조용히 사라지면 합이 안 맞는 이유를 알 수 없다.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Segment:
    name: str = ""
    kind: str = ""          #: "box" | "sector"
    # box
    lo: tuple = ()
    hi: tuple = ()
    # sector
    center: tuple = ()
    r_min: float = 0.0
    r_max: float = 0.0
    th_min: float = 0.0     #: deg
    th_max: float = 0.0
    axis: str = "z"

    def contains(self, p) -> bool:
        try:
            x, y, z = (float(p[0]), float(p[1]), float(p[2]))
        except (TypeError, ValueError, IndexError):
            return False
        if not all(math.isfinite(v) for v in (x, y, z)):
            return False
        if self.kind == "box":
            return all(self.lo[i] <= (x, y, z)[i] <= self.hi[i] for i in range(3))
        if self.kind == "sector":
            # 축 방향은 무시하고 나머지 두 축으로 극좌표를 잡는다
            if self.axis == "z":
                u, v = x - self.center[0], y - self.center[1]
            elif self.axis == "y":
                u, v = z - self.center[2], x - self.center[0]
            else:
                u, v = y - self.center[1], z - self.center[2]
            r = math.hypot(u, v)
            if not (self.r_min <= r <= self.r_max):
                return False
            th = math.degrees(math.atan2(v, u))
            lo, hi = self.th_min, self.th_max
            # 각도 구간이 ±180 을 넘어 감기는 경우를 함께 처리한다
            if lo <= hi:
                return lo <= th <= hi
            return th >= lo or th <= hi
        return False


@dataclass
class SegmentSet:
    part_id: int | None = None
    segments: list = field(default_factory=list)
    note: str = ""

    def assign(self, point):
        """점이 속한 구간 이름. 어디에도 없으면 None.

        겹치면 **먼저 정의된** 구간이 이긴다.
        """
        for s in self.segments:
            if s.contains(point):
                return s.name
        return None


def load_segments(path) -> SegmentSet:
    """구간 정의 JSON 을 읽는다. 형식이 틀려도 예외를 던지지 않는다."""
    ss = SegmentSet()
    try:
        p = Path(path)
    except TypeError:
        ss.note = "경로를 해석하지 못했습니다"
        return ss
    if not p.is_file():
        ss.note = f"파일이 없습니다: {p}"
        return ss
    try:
        doc = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as e:
        ss.note = f"JSON 을 읽지 못했습니다 ({type(e).__name__})"
        return ss
    if not isinstance(doc, dict):
        ss.note = "최상위가 객체가 아닙니다"
        return ss
    try:
        ss.part_id = int(doc["part_id"])
    except (KeyError, TypeError, ValueError):
        ss.note = "part_id 가 없거나 정수가 아닙니다"
        return ss

    segs = doc.get("segments")
    if not isinstance(segs, list) or not segs:
        ss.note = "segments 배열이 없거나 비어 있습니다"
        return ss

    bad = []
    seen = set()
    for i, d in enumerate(segs):
        if not isinstance(d, dict):
            bad.append(f"[{i}] 객체가 아님")
            continue
        name = str(d.get("name") or f"seg{i}")
        if name in seen:
            bad.append(f"[{i}] 이름 중복: {name}")
            continue
        kind = str(d.get("type") or "box").lower()
        try:
            if kind == "box":
                lo = tuple(float(v) for v in d["min"])
                hi = tuple(float(v) for v in d["max"])
                if len(lo) != 3 or len(hi) != 3:
                    raise ValueError("좌표가 3개가 아님")
                # 뒤집힌 경계는 바로잡는다 (사용자 실수로 구간이 통째로 비지 않게)
                lo, hi = (tuple(min(lo[i], hi[i]) for i in range(3)),
                          tuple(max(lo[i], hi[i]) for i in range(3)))
                ss.segments.append(Segment(name=name, kind="box", lo=lo, hi=hi))
            elif kind == "sector":
                c = tuple(float(v) for v in d["center"])
                if len(c) != 3:
                    raise ValueError("center 가 3개가 아님")
                rmin, rmax = float(d.get("r_min", 0.0)), float(d["r_max"])
                if rmin > rmax:
                    rmin, rmax = rmax, rmin
                ax = str(d.get("axis") or "z").lower()
                if ax not in ("x", "y", "z"):
                    raise ValueError(f"axis 가 x/y/z 가 아님: {ax}")
                ss.segments.append(Segment(
                    name=name, kind="sector", center=c, r_min=rmin, r_max=rmax,
                    th_min=float(d.get("theta_min_deg", -180.0)),
                    th_max=float(d.get("theta_max_deg", 180.0)), axis=ax))
            else:
                raise ValueError(f"알 수 없는 type: {kind}")
        except (KeyError, TypeError, ValueError) as e:
            bad.append(f"[{i}] {name}: {e}")
            continue
        seen.add(name)

    if bad:
        ss.note = f"건너뛴 구간 {len(bad)}개 — " + "; ".join(bad[:3])
    if not ss.segments:
        ss.note = (ss.note + " / 쓸 수 있는 구간이 없습니다").strip(" /")
    return ss


@dataclass
class SegmentStats:
    counts: dict = field(default_factory=dict)      #: 구간 → 점 수
    sums: dict = field(default_factory=dict)        #: 구간 → 값 합
    maxes: dict = field(default_factory=dict)       #: 구간 → 최댓값
    unassigned: int = 0                             #: 어느 구간에도 없는 점 수
    invalid: int = 0                                #: 좌표·값이 해석 불가인 점 수
    note: str = ""

    def means(self) -> dict:
        return {k: (self.sums[k] / self.counts[k]) for k in self.counts
                if self.counts[k]}


def segment_stats(points, values, ss: SegmentSet) -> SegmentStats:
    """점들을 구간에 배정하고 구간별 개수·합·최댓값을 낸다."""
    st = SegmentStats()
    if not isinstance(ss, SegmentSet) or not ss.segments:
        st.note = "구간 정의가 없습니다"
        return st
    try:
        n = len(points)
    except TypeError:
        st.note = "점 목록이 아닙니다"
        return st
    try:
        m = len(values)
    except TypeError:
        st.note = "값 목록이 아닙니다"
        return st
    if n != m:
        st.note = f"점과 값의 개수가 다릅니다 ({n} vs {m})"
        return st
    for s in ss.segments:
        st.counts[s.name] = 0
        st.sums[s.name] = 0.0

    for i in range(n):
        try:
            v = float(values[i])
        except (TypeError, ValueError):
            st.invalid += 1
            continue
        if not math.isfinite(v):
            st.invalid += 1
            continue
        name = ss.assign(points[i])
        if name is None:
            st.unassigned += 1
            continue
        st.counts[name] += 1
        st.sums[name] += v
        if name not in st.maxes or v > st.maxes[name]:
            st.maxes[name] = v
    return st
