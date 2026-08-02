# rcforc 접촉력 계측 + 물리 검증 — deep/sphere/impact 세 보고서 공용
"""*DATABASE_RCFORC 가 켜진 해석의 접촉력 계측과 검증.

이 모듈이 답하는 것
  계측 — 각 접촉 인터페이스가 언제 얼마나 힘을 전달했는가
         (피크력/피크시각/충격량/접촉 구간/파트쌍)
  검증 — 그 계측을 믿어도 되는가
         ① 뉴턴 3법칙: master 힘과 slave 힘이 같은가
         ② 접촉 동시성: 인터페이스들이 같은 시각에 힘을 받았는가
         ③ 에너지: glstat 의 sliding interface energy 와 sleout 합이 맞는가

정직성 규칙 (프로젝트 공통)
  - **절대 임계값을 발명하지 않는다.** 검증은 상대 오차만 보고하고
    "PASS/FAIL" 을 만들지 않는다. 판정은 사람이 한다.
  - RCFORC 가 꺼져 있으면 조용히 건너뛰지 않고 `available=False` 와 사유를 낸다.
    '측정 안 함' 과 '측정했더니 0' 은 다르다.
  - 파트로 분해되지 않는 접촉(single-surface 등)은 파트쌍인 척하지 않는다.

계측 단위는 해석 덱을 따른다(보통 ton-mm-s → 힘 N, 충격량 N·s).
이 모듈은 단위를 변환하지 않는다 — 변환하면 어느 단위인지 알 수 없어진다.
"""
from __future__ import annotations

from dataclasses import dataclass


def _r(x, nd=6):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return round(v, nd)


def _mag(fx, fy, fz):
    n = min(len(fx), len(fy), len(fz))
    return [(fx[i] ** 2 + fy[i] ** 2 + fz[i] ** 2) ** 0.5 for i in range(n)]


def _trapz(y, x):
    n = min(len(y), len(x))
    s = 0.0
    for i in range(1, n):
        s += 0.5 * (y[i] + y[i - 1]) * (x[i] - x[i - 1])
    return s


def _rel(a, b):
    """|a-b| / max(|a|,|b|). 둘 다 0 이면 0, 기준이 없으면 None."""
    try:
        fa, fb = abs(float(a)), abs(float(b))
    except (TypeError, ValueError):
        return None
    d = max(fa, fb)
    if d == 0.0:
        return 0.0
    return abs(float(a) - float(b)) / d


#: 접촉 '발생' 판정 — 피크의 이 비율을 넘긴 구간을 접촉 구간으로 본다.
#: 절대 임계값이 아니라 그 인터페이스 자신의 피크에 대한 상대값이라 덱/단위에
#: 무관하다. 솔버 잔류력(피크의 0.1% 수준)이 접촉으로 잡히는 것만 막는 목적.
_ENGAGE_REL = 0.01


@dataclass
class InterfaceMetric:
    cid: int
    name: str
    peak_force: float | None = None
    peak_time: float | None = None
    impulse: float | None = None
    engage_t0: float | None = None
    engage_t1: float | None = None
    n_samples: int = 0
    #: master/slave 상대 불일치. 한쪽만 기록됐으면 None (검증 불가).
    balance_rel: float | None = None
    sides: int = 0
    #: 실제로 잰 side (0=slave, 1=master). 큰 쪽을 쓴다.
    side_used: int = -1
    #: 한쪽만 기록된 접촉(SSTYP=5 등) — 3법칙 검증 대상이 아니다.
    one_sided_record: bool = False
    #: contact_map 이 붙여준 파트쌍. 분해 불가면 None.
    src: str | None = None
    dst: str | None = None
    resolved: bool = False


def _by_cid(rcforc):
    out: dict[int, dict[int, object]] = {}
    for r in rcforc or []:
        out.setdefault(int(r.interface_id), {})[int(getattr(r, "side", -1))] = r
    return out


def _peak_of(r) -> float:
    fm = _mag(getattr(r, "fx", []) or [], getattr(r, "fy", []) or [],
              getattr(r, "fz", []) or [])
    return max(fm) if fm else 0.0


def _measure_one(cid, sides) -> InterfaceMetric:
    """side 0=slave, 1=master, -1=total.

    **큰 쪽을 기준으로 잰다.** SSTYP=5(slave='전체') 같은 정의에서는 한쪽이
    거의 0 으로만 기록된다 — 실측에서 CID 172 는 slave 0.2 / master 36251 이었다.
    slave 를 먼저 고르면 모델 최대 접촉을 0 으로 측정하게 된다.
    """
    cand = [(s, r) for s, r in sides.items() if s in (0, 1)] or list(sides.items())
    side_used, ref = max(cand, key=lambda kv: _peak_of(kv[1]))
    m = InterfaceMetric(cid=cid, name=str(getattr(ref, "name", "") or ""))
    m.side_used = side_used
    t = list(getattr(ref, "t", []) or [])
    fm = _mag(getattr(ref, "fx", []) or [], getattr(ref, "fy", []) or [],
              getattr(ref, "fz", []) or [])
    m.sides = len([s for s in sides if s in (0, 1)])
    if not t or not fm:
        return m
    n = min(len(t), len(fm))
    t, fm = t[:n], fm[:n]
    m.n_samples = n

    pk = 0.0
    pi = 0
    for i, v in enumerate(fm):
        if v > pk:
            pk, pi = v, i
    m.peak_force = _r(pk)
    m.peak_time = _r(t[pi], 9)
    m.impulse = _r(_trapz(fm, t))

    if pk > 0:
        thr = pk * _ENGAGE_REL
        on = [i for i, v in enumerate(fm) if v >= thr]
        if on:
            m.engage_t0 = _r(t[on[0]], 9)
            m.engage_t1 = _r(t[on[-1]], 9)

    # ① 뉴턴 3법칙 — master 와 slave 의 충격량 비교.
    #    순간 힘은 샘플 타이밍 차로 흔들리므로 적분값으로 본다.
    s, mst = sides.get(0), sides.get(1)
    if s is not None and mst is not None:
        p_s, p_m = _peak_of(s), _peak_of(mst)
        # 한쪽만 사실상 기록된 경우(SSTYP=5 등)는 3법칙 위반이 아니라
        # 접촉 정의상 그 면이 'ALL' 이라 반대편이 안 적힌 것이다. 통계에서 빼고
        # 별도로 센다 — 섞으면 max_rel 이 1.0 이 되어 늘 실패처럼 보인다.
        if min(p_s, p_m) < max(p_s, p_m) * _ENGAGE_REL:
            m.one_sided_record = True
        else:
            i_s = _trapz(_mag(s.fx, s.fy, s.fz), s.t)
            i_m = _trapz(_mag(mst.fx, mst.fy, mst.fz), mst.t)
            m.balance_rel = _r(_rel(i_s, i_m), 9)
    return m


def build_contact_metrics(binout, contact_map=None, part_names=None) -> dict:
    """rcforc → 계측 + 검증 dict. 세 보고서가 그대로 소비하는 계약이다.

    반환 키
      available / reason / n_interfaces / interfaces[] / checks{} / note
    """
    part_names = part_names or {}
    rcforc = list(getattr(binout, "rcforc", None) or []) if binout is not None else []
    if not rcforc:
        return {
            "available": False,
            "reason": ("binout 에 rcforc 가 없습니다 — 덱에 *DATABASE_RCFORC 가 "
                       "없거나 해석이 접촉력을 기록하지 않았습니다. "
                       "접촉력 항목은 계측하지 않은 것이며 0 이 아닙니다."),
            "n_interfaces": 0, "interfaces": [], "checks": {}, "note": "",
        }

    grouped = _by_cid(rcforc)
    eps = getattr(contact_map, "endpoints", None) if contact_map is not None else None

    mets: list[InterfaceMetric] = []
    for cid in sorted(grouped):
        m = _measure_one(cid, grouped[cid])
        ep = (eps or {}).get(cid)
        if ep is not None:
            sl, ms = getattr(ep, "slave", None), getattr(ep, "master", None)
            m.src = getattr(sl, "node_id", None)
            m.dst = getattr(ms, "node_id", None)
            m.resolved = (getattr(sl, "kind", "") == "part"
                          and getattr(ms, "kind", "") == "part")
        mets.append(m)

    def _nm(nid):
        if nid is None:
            return None
        return part_names.get(int(nid), f"Part_{nid}") if str(nid).isdigit() else str(nid)

    interfaces = [{
        "cid": m.cid, "name": m.name,
        "peak_force": m.peak_force, "peak_time": m.peak_time,
        "impulse": m.impulse,
        "engage_t0": m.engage_t0, "engage_t1": m.engage_t1,
        "n_samples": m.n_samples, "sides": m.sides,
        "side_used": m.side_used,
        "balance_rel": m.balance_rel,
        "one_sided_record": m.one_sided_record,
        "src": m.src, "dst": m.dst, "resolved": m.resolved,
        "src_name": _nm(m.src), "dst_name": _nm(m.dst),
    } for m in mets]

    # --- 검증 ① 뉴턴 3법칙 -------------------------------------------------
    bal = [m.balance_rel for m in mets if m.balance_rel is not None]
    # 한쪽만 기록된 접촉 = 반대편이 'ALL' 이라 안 적힌 것. 3법칙 대상이 아니다.
    one_sided = sum(1 for m in mets if m.one_sided_record or m.sides < 2)
    checks: dict = {"newton3": {
        "n_checked": len(bal),
        "n_one_sided": one_sided,
        "max_rel": _r(max(bal), 9) if bal else None,
        "median_rel": _r(sorted(bal)[len(bal) // 2], 9) if bal else None,
        "desc": ("master 힘과 slave 힘의 충격량 상대차. 접촉이 제대로 정의됐다면 "
                 "0 에 가깝다. 절대 기준은 두지 않는다 — 값만 보고한다. "
                 "한쪽만 기록된 접촉(반대편이 'ALL' 인 정의)은 검증 대상이 "
                 "아니므로 통계에서 빼고 개수만 센다."),
    }}

    # --- 검증 ② 접촉 동시성 -----------------------------------------------
    # 충격량 대 운동량 비교는 **의도적으로 넣지 않았다.** rcforc 는 master/slave
    # 를 같은 부호로 기록해 내부 접촉쌍이 상쇄되지 않고, ∫|F|dt 는 방향을 버린다.
    # 실측에서 내부 TIED 25개 합이 Δp 의 280배로 나와 늘 '불일치' 로 보였다.
    # 늘 실패처럼 보이는 지표는 사람을 검증에서 멀어지게 하므로 싣지 않는다.
    pts = [m.peak_time for m in mets if m.peak_time is not None and (m.peak_force or 0) > 0]
    t0s = [m.engage_t0 for m in mets if m.engage_t0 is not None]
    checks["timing"] = {
        "n_engaged": len(t0s),
        "first_engage": _r(min(t0s), 9) if t0s else None,
        "peak_time_min": _r(min(pts), 9) if pts else None,
        "peak_time_max": _r(max(pts), 9) if pts else None,
        "peak_spread": _r(max(pts) - min(pts), 9) if len(pts) > 1 else None,
        "desc": ("인터페이스별 접촉 시작·피크 시각의 분포. 하중 경로가 순차적으로 "
                 "전달됐는지 본다. 값만 보고하며 기준은 두지 않는다."),
    }

    # --- 검증 ③ 에너지 (glstat sliding vs sleout 합) ------------------------
    gl = getattr(binout, "glstat", None)
    sle = list(getattr(binout, "sleout", None) or [])
    gl_sie = None
    if gl is not None and getattr(gl, "sliding_interface_energy", None):
        try:
            gl_sie = float(gl.sliding_interface_energy[-1])
        except (IndexError, TypeError, ValueError):
            gl_sie = None
    sle_sum = None
    if sle:
        tot = 0.0
        ok = False
        for s in sle:
            arr = getattr(s, "total_energy", None) or []
            if arr:
                try:
                    tot += float(arr[-1])
                    ok = True
                except (TypeError, ValueError):
                    pass
        sle_sum = tot if ok else None
    checks["sliding_energy"] = {
        "glstat_sliding": _r(gl_sie) if gl_sie is not None else None,
        "sleout_sum": _r(sle_sum) if sle_sum is not None else None,
        "rel": (_r(_rel(gl_sie, sle_sum), 9)
                if (gl_sie is not None and sle_sum is not None) else None),
        "desc": ("glstat 의 sliding interface energy 와 sleout 인터페이스별 "
                 "에너지 합의 상대차. 같은 양을 다른 파일이 기록한 것이라 "
                 "어긋나면 출력 주기(dt)나 인터페이스 누락을 의심한다."),
    }

    n_res = sum(1 for m in mets if m.resolved)
    note = ""
    if n_res < len(mets):
        note = (f"인터페이스 {len(mets)}개 중 {len(mets) - n_res}개는 파트쌍으로 "
                f"분해되지 않았습니다(single-surface 등). 그 항목은 파트쌍이 아니라 "
                f"인터페이스 단위 합력입니다.")

    return {
        "available": True,
        "reason": "",
        "n_interfaces": len(mets),
        "n_resolved": n_res,
        "interfaces": interfaces,
        "checks": checks,
        "note": note,
    }
