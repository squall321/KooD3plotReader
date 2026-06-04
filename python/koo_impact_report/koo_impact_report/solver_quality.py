"""solver_quality — LSDYNA glstat 파싱 + energy-balance / termination audit.

glstat 은 LSDYNA 의 global state 시계열 파일. 시뮬레이션 정확성/안정성의 1차
관문 — energy conservation, hourglass fraction, sliding energy 등.

본 모듈은:
    1. parse_glstat() — glstat 텍스트를 시계열 dict 로
    2. assess_energy_balance() — 정량적 게이트 판정 (PASS / WARN / FAIL)

ImpactReport 의 후속 sub-run loader 가 각 DOE 의 glstat 를 호출해 결과를
``solver_quality`` 필드에 보관. HTML 측에서 진짜 diss_pct, energy badge, 안정성
경고 등을 이 데이터에서 가져온다.

호출자 책임: glstat 경로 (보통 `<run_dir>/Output/glstat`) 만 전달.

본 모듈은 외부 의존성 없음 (math, re 만). loader 와 마찬가지로 numpy 없이도
동작.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Recognized glstat keys (full line up to dots) → canonical short name.
# 한 cycle block 안에 한 번씩 등장. 값은 항상 마지막 단어 (Fortran exp 형식).
_KEY_MAP = {
    "time":                              "t",
    "time step":                         "dt",
    "kinetic energy":                    "ke",
    "internal energy":                   "ie",
    "spring and damper energy":          "sd",
    "hourglass energy":                  "hg",
    "system damping energy":             "sys_damp",
    "sliding interface energy":          "sl",
    "external work":                     "ext",
    "eroded kinetic energy":             "er_ke",
    "eroded internal energy":            "er_ie",
    "eroded hourglass energy":           "er_hg",
    "total energy":                      "te",
    "total energy / initial energy":     "te_ratio",
    "energy ratio w/o eroded energy":    "te_ratio_no_erode",
    "global x velocity":                 "vx",
    "global y velocity":                 "vy",
    "global z velocity":                 "vz",
    "dissipated kinetic energy":         "diss_ke",
    "dissipated internal energy":        "diss_ie",
    "drilling energy":                   "drill",
}


# Energy keys we expose as time-series in the parsed dict.
_TS_KEYS = ("t", "dt", "ke", "ie", "sd", "hg", "sl", "ext", "te",
            "te_ratio", "te_ratio_no_erode", "er_ke", "er_ie", "er_hg",
            "diss_ke", "diss_ie", "vx", "vy", "vz", "drill", "sys_damp")


@dataclass
class GlstatTimeSeries:
    """Parsed glstat content — per-key time-series + summary stats."""
    cycles: list[dict[str, float]] = field(default_factory=list)
    summary: dict[str, float] = field(default_factory=dict)
    n_cycles: int = 0
    t_start: float = 0.0
    t_end: float = 0.0

    @property
    def empty(self) -> bool:
        return self.n_cycles == 0

    def series(self, key: str) -> list[float]:
        """Extract a single time-series. Missing values become NaN."""
        return [c.get(key, math.nan) for c in self.cycles]


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------

def _fortran_float(tok: str) -> float | None:
    """Parse '2.01486E+02' / '-3.20974E-05' / '0.00000E+00' style numbers."""
    try:
        return float(tok)
    except (ValueError, TypeError):
        return None


def parse_glstat(path: str | Path) -> GlstatTimeSeries:
    """Parse a glstat file into a time-series of per-key values.

    Robust to:
      - leading banner lines (ls-dyna version etc)
      - 'dt of cycle ... is controlled by ...' block headers
      - blank lines between cycles
      - unrecognized keys (silently skipped)
    """
    out = GlstatTimeSeries()
    p = Path(path)
    if not p.exists():
        return out
    try:
        text = p.read_text(errors="replace")
    except Exception:
        return out

    # split into cycle blocks via the "dt of cycle ..." header lines
    # (the very first block can be without that header — handle separately)
    blocks = re.split(r"\n\s*dt of cycle\s+\d+", text)
    # blocks[0] is whatever came before the first header (may contain banner
    # + the very first block without explicit header).
    cycles: list[dict[str, float]] = []

    def _process_block(b: str) -> dict[str, float] | None:
        rec: dict[str, float] = {}
        for line in b.splitlines():
            # key lines have lots of '.' between key and value, e.g.:
            #   "kinetic energy.................   2.01486E+02"
            m = re.match(r"\s*(.+?)\.{3,}\s*(\S+)\s*$", line)
            if not m:
                continue
            key_raw = m.group(1).strip().lower()
            # strip trailing dots from key (e.g. 'time...' → 'time')
            key_raw = key_raw.rstrip(".").strip()
            tok = m.group(2)
            v = _fortran_float(tok)
            if v is None:
                continue
            canon = _KEY_MAP.get(key_raw)
            if canon is None:
                continue
            rec[canon] = v
        return rec if "t" in rec else None

    for b in blocks:
        rec = _process_block(b)
        if rec is not None:
            cycles.append(rec)

    out.cycles = cycles
    out.n_cycles = len(cycles)
    if cycles:
        out.t_start = cycles[0].get("t", 0.0)
        out.t_end = cycles[-1].get("t", 0.0)
        # compute summary
        out.summary = _summary(cycles)
    return out


def _summary(cycles: list[dict[str, float]]) -> dict[str, float]:
    """Derive summary stats from cycle list."""
    if not cycles:
        return {}

    def _last(key: str) -> float:
        for c in reversed(cycles):
            v = c.get(key)
            if v is not None and math.isfinite(v):
                return v
        return math.nan

    def _max_abs(key: str) -> float:
        mx = 0.0
        for c in cycles:
            v = c.get(key)
            if v is not None and math.isfinite(v):
                mx = max(mx, abs(v))
        return mx

    def _peak(key: str) -> float:
        mx = -math.inf
        for c in cycles:
            v = c.get(key)
            if v is not None and math.isfinite(v):
                mx = max(mx, v)
        return mx if math.isfinite(mx) else math.nan

    ke0 = cycles[0].get("ke", math.nan)
    ke_final = _last("ke")
    te0 = cycles[0].get("te", math.nan)
    te_final = _last("te")

    # Dissipation: 초기 KE 중 얼마나 빠져나갔는지 (IE + HG + SL 흡수 또는 변환).
    diss_pct = math.nan
    if math.isfinite(ke0) and ke0 > 0 and math.isfinite(ke_final):
        diss_pct = max(0.0, 100.0 * (ke0 - ke_final) / ke0)

    # Conservation ratio drift: TE_final / TE_initial 의 절대 편차.
    te_drift_pct = math.nan
    if math.isfinite(te0) and te0 > 0 and math.isfinite(te_final):
        te_drift_pct = abs(te_final - te0) / te0 * 100.0

    hg_peak = _peak("hg")
    sl_peak_abs = _max_abs("sl")
    ie_peak = _peak("ie")

    # Hourglass fraction of internal energy.
    hg_frac = math.nan
    if math.isfinite(ie_peak) and ie_peak > 0 and math.isfinite(hg_peak):
        hg_frac = 100.0 * hg_peak / ie_peak

    # Sliding fraction relative to initial KE.
    sl_frac = math.nan
    if math.isfinite(ke0) and ke0 > 0 and math.isfinite(sl_peak_abs):
        sl_frac = 100.0 * sl_peak_abs / ke0

    return {
        "ke_initial":       ke0,
        "ke_final":         ke_final,
        "te_initial":       te0,
        "te_final":         te_final,
        "ie_peak":          ie_peak,
        "hg_peak":          hg_peak,
        "sl_peak_abs":      sl_peak_abs,
        "diss_pct":         round(diss_pct, 2) if math.isfinite(diss_pct) else None,
        "te_drift_pct":     round(te_drift_pct, 4) if math.isfinite(te_drift_pct) else None,
        "hg_fraction_pct":  round(hg_frac, 2) if math.isfinite(hg_frac) else None,
        "sl_fraction_pct":  round(sl_frac, 2) if math.isfinite(sl_frac) else None,
    }


# ---------------------------------------------------------------------------
# audit / verdict
# ---------------------------------------------------------------------------

@dataclass
class EnergyBalanceVerdict:
    """Energy-balance audit verdict for one run."""
    pass_fail: str = "UNKNOWN"      # PASS / WARN / FAIL / UNKNOWN
    flags: list[str] = field(default_factory=list)
    summary: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "pass_fail": self.pass_fail,
            "flags": list(self.flags),
            **{k: v for k, v in self.summary.items()},
        }


# Thresholds (industry rule-of-thumb for explicit dynamics).
TE_DRIFT_WARN = 2.0    # %
TE_DRIFT_FAIL = 5.0
HG_FRAC_WARN  = 10.0   # of internal energy
HG_FRAC_FAIL  = 20.0
SL_FRAC_WARN  = 5.0    # of initial KE
SL_FRAC_FAIL  = 10.0


def assess_energy_balance(ts: GlstatTimeSeries) -> EnergyBalanceVerdict:
    """Apply industry-standard gates to glstat summary."""
    v = EnergyBalanceVerdict()
    if ts.empty:
        return v

    s = ts.summary
    flags: list[str] = []

    def _check(value: float | None, warn: float, fail: float, name: str):
        if value is None or not math.isfinite(value):
            return None
        if value >= fail:
            flags.append(f"{name}>={fail}%")
            return "FAIL"
        if value >= warn:
            flags.append(f"{name}>={warn}%")
            return "WARN"
        return "PASS"

    rsts = [
        _check(s.get("te_drift_pct"),    TE_DRIFT_WARN, TE_DRIFT_FAIL, "TE_drift"),
        _check(s.get("hg_fraction_pct"), HG_FRAC_WARN,  HG_FRAC_FAIL,  "HG_frac"),
        _check(s.get("sl_fraction_pct"), SL_FRAC_WARN,  SL_FRAC_FAIL,  "SL_frac"),
    ]
    rsts = [r for r in rsts if r is not None]
    if not rsts:
        v.pass_fail = "UNKNOWN"
    elif any(r == "FAIL" for r in rsts):
        v.pass_fail = "FAIL"
    elif any(r == "WARN" for r in rsts):
        v.pass_fail = "WARN"
    else:
        v.pass_fail = "PASS"

    v.flags = flags
    v.summary = s
    return v


# ---------------------------------------------------------------------------
# convenience: parse + assess in one call
# ---------------------------------------------------------------------------

def audit_run(glstat_path: str | Path) -> dict:
    """Parse glstat + assess in one call. Returns serializable dict."""
    ts = parse_glstat(glstat_path)
    if ts.empty:
        return {
            "available": False,
            "pass_fail": "UNKNOWN",
            "n_cycles": 0,
            "t_start": 0.0,
            "t_end": 0.0,
            "summary": {},
            "flags": ["glstat-missing"],
        }
    verdict = assess_energy_balance(ts)
    return {
        "available": True,
        "pass_fail": verdict.pass_fail,
        "n_cycles": ts.n_cycles,
        "t_start": ts.t_start,
        "t_end": ts.t_end,
        "summary": verdict.summary,
        "flags": verdict.flags,
    }


def audit_runs(runs: Iterable[tuple[str, str | Path]]) -> dict[str, dict]:
    """Audit multiple runs. runs = iterable of (pos_id, glstat_path)."""
    out: dict[str, dict] = {}
    for pos_id, gp in runs:
        out[pos_id] = audit_run(gp)
    return out
