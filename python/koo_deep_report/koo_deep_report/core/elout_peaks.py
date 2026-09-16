# elout(촘촘한 요소 이력)으로 d3plot 이 피크를 놓쳤는지 교차 확인하는 모듈
"""elout 피크 교차 확인.

**왜 이 모듈이 있나.**
핫스팟은 d3plot 상태를 훑는다. d3plot 출력 간격이 성기면 **피크 시각을 통째로
놓친다**. elout(`*DATABASE_ELOUT`)은 훨씬 촘촘하지만 핫스팟 경로에서 쓰지 않는다.

소스를 elout 으로 바꾸는 것은 큰 변경이고, 요소 선별·군집까지 다시 맞춰야 한다.
여기서는 더 작고 안전한 것을 한다 — **d3plot 피크와 elout 피크를 견주어
"놓쳤을 수 있다" 를 알려준다.** 판단은 사람이 한다.

**구조.**
- `read_elout()` : lasso 로 binout 을 읽어 정규화한다. **실덱 없이는 검증 불가**
  이므로 얇게 두고, 못 읽으면 사유를 남긴다.
- `peak_by_part()` / `compare_peaks()` : 순수 함수. 합성 데이터로 완전히 검증한다.

**설계 규칙.** 예외를 던지지 않는다. elout 이 없으면 "없다" 고 말하고 끝낸다 —
없는 것을 추정해 채우지 않는다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

#: elout 에서 von Mises 상당량으로 쓸 변수 이름 후보 (덱·버전마다 다르다).
#: 앞에 있는 것부터 찾고, 하나도 없으면 **추정하지 않고** 사유를 남긴다.
VM_KEYS = ("von_mises", "vonmises", "effective_stress", "sig_eff", "svm")
#: 응력 성분에서 직접 계산할 때 쓰는 이름 후보
COMP_KEYS = (("sig_xx", "sig_yy", "sig_zz", "sig_xy", "sig_yz", "sig_zx"),
             ("sigma_xx", "sigma_yy", "sigma_zz", "sigma_xy", "sigma_yz", "sigma_zx"),
             ("xx", "yy", "zz", "xy", "yz", "zx"))


@dataclass
class EloutData:
    """정규화된 elout — {요소 종류: {"time": [...], "ids": [...], "vm": [[...], ...]}}.

    `vm[t][e]` = 시각 t 에서 요소 e 의 von Mises 상당량.
    """
    kinds: dict = field(default_factory=dict)
    note: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.kinds)


def _close_binout(b) -> None:
    """lasso Binout 을 닫는다.

    Binout 에는 `close()` 가 없고, 내부 `Lsda.__del__` 이 GC 시점에 `flush()` 를
    시도하다 예외를 낸다. 인터프리터가 "Exception ignored in __del__" 경고를
    찍어 로그를 더럽히고, 시험에서는 **엉뚱한 시험에 경고가 달라붙는다**
    (GC 시점이 파일 경계를 넘는다). 여기서 조용히 정리한다.

    🔴 진짜 원인은 lasso 쪽이다. `Lsda.__init__` 은 쓰기 모드에서만 `self.fw` 를
       만드는데 `flush()` 는 모드와 무관하게 `self.fw` 를 읽는다. 읽기 전용으로
       열면 `AttributeError: 'Lsda' object has no attribute 'fw'` 가 난다.
       `fw = None` 을 넣어 주면 flush 가 첫 줄에서 빠져나간다.
    """
    try:
        lsda = getattr(b, "lsda", None)
        if lsda is not None and not hasattr(lsda, "fw"):
            try:
                lsda.fw = None
            except Exception:       # noqa: BLE001
                pass
        for f in (getattr(lsda, "files", None) or []):
            fp = getattr(f, "fp", None)
            if fp is not None and not fp.closed:
                fp.close()
        if lsda is not None:
            # __del__ 이 다시 순회하지 않도록 비운다
            try:
                lsda.files = []
            except Exception:       # noqa: BLE001
                pass
    except Exception:               # noqa: BLE001 — 정리 실패로 결과를 버리지 않는다
        pass


def _vm_from_components(row) -> float:
    xx, yy, zz, xy, yz, zx = row
    return math.sqrt(max(0.0, 0.5 * ((xx - yy) ** 2 + (yy - zz) ** 2 + (zz - xx) ** 2)
                         + 3.0 * (xy * xy + yz * yz + zx * zx)))


def read_elout(binout_path) -> EloutData:
    """binout 에서 elout 분기를 읽어 정규화한다.

    🔴 이 함수는 **실덱 없이 검증할 수 없다**. 가진 덱 두 개 모두 elout 이 없어
       (`*DATABASE_ELOUT` 미설정) 실제 키 이름을 확인하지 못했다. 그래서 여러
       이름을 시도하고, 못 찾으면 **무엇을 찾았는지** 사유에 적는다 — 조용히 빈
       결과를 돌려주면 "elout 이 없다" 와 "이름이 다르다" 가 구분되지 않는다.
    """
    ed = EloutData()
    try:
        from lasso.dyna import Binout
    except ImportError as e:
        ed.note = f"lasso 를 가져오지 못했습니다 ({e}) — elout 을 읽을 수 없습니다"
        return ed
    # 🔴 디렉토리를 넘기면 Binout 생성자가 **부분 성공한 뒤** 예외를 던지고
    #    내부 Lsda 가 정리되지 않은 채 남는다(GC 때 "Exception ignored" 경고).
    #    생성자가 실패하면 우리 손이 닿지 않으므로 넘기기 전에 막는다.
    from pathlib import Path as _P
    try:
        _p = _P(str(binout_path))
    except (TypeError, ValueError):
        ed.note = "binout 경로를 해석하지 못했습니다"
        return ed
    if _p.is_dir():
        ed.note = f"디렉토리입니다: {_p} — binout 파일 경로를 주세요"
        return ed

    b = None
    try:
        b = Binout(str(binout_path))
        branches = list(b.read())
    except Exception as e:      # noqa: BLE001 — lasso 예외 종류가 다양하다
        ed.note = f"binout 을 열지 못했습니다 ({type(e).__name__}: {e})"
        if b is not None:
            _close_binout(b)
        return ed
    if "elout" not in branches:
        _close_binout(b)
        ed.note = (f"binout 에 elout 분기가 없습니다 "
                   f"(*DATABASE_ELOUT 미설정). 있는 분기: {', '.join(branches)}")
        return ed

    try:
        subs = list(b.read("elout"))
    except Exception as e:      # noqa: BLE001
        ed.note = f"elout 분기를 읽지 못했습니다 ({type(e).__name__})"
        _close_binout(b)
        return ed

    seen_vars = {}
    for kind in ("solid", "shell", "thick_shell", "beam"):
        if kind not in subs:
            continue
        try:
            vars_ = list(b.read("elout", kind))
        except Exception:       # noqa: BLE001
            continue
        seen_vars[kind] = vars_
        vm_key = next((k for k in VM_KEYS if k in vars_), None)
        comps = next((c for c in COMP_KEYS if all(k in vars_ for k in c)), None)
        if vm_key is None and comps is None:
            continue
        try:
            time = [float(t) for t in b.read("elout", kind, "time")]
            ids = [int(i) for i in b.read("elout", kind, "ids")]
            if vm_key is not None:
                raw = b.read("elout", kind, vm_key)
                vm = [[float(v) for v in row] for row in raw]
            else:
                cols = [b.read("elout", kind, k) for k in comps]
                vm = [[_vm_from_components([float(c[t][e]) for c in cols])
                       for e in range(len(ids))] for t in range(len(time))]
        except Exception as e:  # noqa: BLE001
            ed.note = (ed.note + f" / {kind}: 값을 읽지 못했습니다 "
                       f"({type(e).__name__})").strip(" /")
            continue
        ed.kinds[kind] = {"time": time, "ids": ids, "vm": vm}

    if not ed.kinds:
        ed.note = (ed.note + f" / elout 에서 응력 변수를 찾지 못했습니다. "
                   f"본 변수: {seen_vars}").strip(" /")
    _close_binout(b)
    return ed


@dataclass
class PeakRow:
    element_id: int = 0
    d3_peak: float | None = None
    d3_time: float | None = None
    elout_peak: float | None = None
    elout_time: float | None = None
    ratio: float | None = None      #: elout / d3plot — 1 보다 크면 d3plot 이 놓친 것
    note: str = ""


@dataclass
class PeakComparison:
    rows: list = field(default_factory=list)
    n_missed: int = 0               #: 임계를 넘겨 놓친 것으로 본 요소 수
    worst_ratio: float | None = None
    threshold: float = 1.05
    note: str = ""

    def summary(self) -> str:
        if self.note and not self.rows:
            return self.note
        if not self.rows:
            return "비교할 요소가 없습니다"
        if not self.n_missed:
            return (f"요소 {len(self.rows)}개 비교 — d3plot 이 놓친 피크 없음 "
                    f"(최대 비율 {self.worst_ratio:.3f})")
        return (f"⚠ 요소 {len(self.rows)}개 중 {self.n_missed}개에서 elout 피크가 "
                f"d3plot 보다 {self.threshold:.0%} 이상 큽니다 "
                f"(최대 {self.worst_ratio:.3f}배) — d3plot 출력 간격이 성겨 "
                f"피크 시각을 놓쳤을 수 있습니다")


def peak_by_element(ed: EloutData, kind: str = "solid") -> dict:
    """{요소 ID: (피크값, 피크시각)}. 없으면 빈 dict."""
    out = {}
    k = (ed.kinds or {}).get(kind)
    if not k:
        return out
    time = k.get("time") or []
    ids = k.get("ids") or []
    vm = k.get("vm") or []
    for e, eid in enumerate(ids):
        best, bt = None, None
        for t, row in enumerate(vm):
            try:
                v = float(row[e])
            except (TypeError, ValueError, IndexError):
                continue
            if math.isnan(v):
                continue
            if best is None or v > best:
                best, bt = v, (time[t] if t < len(time) else None)
        if best is not None:
            out[int(eid)] = (best, bt)
    return out


def compare_peaks(d3_peaks: dict, ed: EloutData, kind: str = "solid",
                  threshold: float = 1.05) -> PeakComparison:
    """d3plot 피크와 elout 피크를 견준다.

    Args:
        d3_peaks: {요소 ID: (피크값, 피크시각)} — 핫스팟 결과에서 뽑은 것
        ed: read_elout() 결과
        threshold: elout/d3plot 이 이 값을 넘으면 "놓쳤다" 로 센다

    Returns:
        PeakComparison. elout 이 없으면 `rows` 가 비고 `note` 에 사유가 있다.
    """
    cmp = PeakComparison()
    try:
        cmp.threshold = float(threshold)
    except (TypeError, ValueError):
        cmp.threshold = 1.05
    if not isinstance(d3_peaks, dict) or not d3_peaks:
        cmp.note = "d3plot 피크가 없습니다"
        return cmp
    if not isinstance(ed, EloutData) or not ed.ok:
        cmp.note = (getattr(ed, "note", "") or "elout 데이터가 없습니다")
        return cmp

    ep = peak_by_element(ed, kind)
    if not ep:
        cmp.note = f"elout 에 '{kind}' 요소 이력이 없습니다"
        return cmp

    worst = None
    for eid, d3 in d3_peaks.items():
        try:
            eid = int(eid)
            d3v = float(d3[0])
            d3t = float(d3[1]) if d3[1] is not None else None
        except (TypeError, ValueError, IndexError):
            continue
        row = PeakRow(element_id=eid, d3_peak=d3v, d3_time=d3t)
        if eid not in ep:
            row.note = "elout 에 이 요소가 없습니다"
            cmp.rows.append(row)
            continue
        ev, et = ep[eid]
        row.elout_peak = ev
        row.elout_time = et
        # d3plot 피크가 0 이면 비율이 무의미하다 — 값을 지어내지 않는다
        if d3v > 0:
            row.ratio = ev / d3v
            if worst is None or row.ratio > worst:
                worst = row.ratio
            if row.ratio >= cmp.threshold:
                cmp.n_missed += 1
        else:
            row.note = "d3plot 피크가 0 이라 비율을 낼 수 없습니다"
        cmp.rows.append(row)

    cmp.worst_ratio = worst
    return cmp
