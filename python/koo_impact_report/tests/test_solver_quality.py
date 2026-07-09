# solver_quality significance-floor 회귀 테스트 — 25/25 거짓 FAIL 재발 방지 (V2)
"""Fixture-driven gates for the energy-balance audit.

Three synthetic glstat cases pin the behavior introduced with
``IE_SIGNIFICANCE_FLOOR_FRAC`` / ``KE_FLAT_TOL_FRAC`` (P1(a),
docs/impact-sota-checklist.md):

* tiny-IE  — rigid/elastic impactor: IE is numeric noise, HG/IE is a 0/0
  ratio. Must NOT fail the HG gate; must surface the skip as a flag.
  (June-2026 artifact: 25/25 false FAIL from exactly this.)
* flat-KE  — impact not inside the glstat window: KE flat. Must flag
  ``no-impact-in-glstat-window`` and report ``diss_pct=None`` — never a
  fabricated 0.0.
* genuinely hourglassing — significant IE with high HG must STILL fail.
"""
from __future__ import annotations

import math
from pathlib import Path

from koo_impact_report.solver_quality import audit_run, parse_glstat


def _glstat_text(cycles: list[dict[str, float]]) -> str:
    """Render cycle dicts in the glstat text format parse_glstat expects."""
    name_map = {
        "t": "time",
        "ke": "kinetic energy",
        "ie": "internal energy",
        "hg": "hourglass energy",
        "sl": "sliding interface energy",
        "te": "total energy",
    }
    blocks: list[str] = []
    for i, cyc in enumerate(cycles):
        lines = []
        if i > 0:
            lines.append(f" dt of cycle {i * 100} is controlled by solid element")
        for key, val in cyc.items():
            full = name_map[key]
            lines.append(f" {full}{'.' * (34 - len(full))}   {val:.5E}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def _write(tmp_path: Path, cycles: list[dict[str, float]]) -> Path:
    p = tmp_path / "glstat"
    p.write_text(_glstat_text(cycles), encoding="utf-8")
    return p


def _cycle(t, ke, ie, hg, sl, te):
    return {"t": t, "ke": ke, "ie": ie, "hg": hg, "sl": sl, "te": te}


# ---------------------------------------------------------------------------
# Case A — tiny-IE rigid impactor (the June false-FAIL shape)
# ---------------------------------------------------------------------------

def test_tiny_ie_skips_hg_gate(tmp_path: Path) -> None:
    ke0 = 1.19331e5
    cycles = [
        _cycle(0.0,    ke0,       1.0e-6, 5.0e-7, 0.0,   ke0),
        _cycle(5.0e-4, ke0 * 0.7, 1.6e-5, 8.7e-6, 1.0e1, ke0 * 0.999),
        _cycle(1.0e-3, ke0 * 0.5, 1.2e-5, 6.0e-6, 2.0e1, ke0 * 0.998),
    ]
    result = audit_run(_write(tmp_path, cycles))

    s = result["summary"]
    # hg/ie ratio is huge (54%-ish) but IE is noise → gate must be skipped
    assert s["ie_significant"] is False
    assert result["pass_fail"] != "FAIL", (
        "tiny-IE run must not FAIL on the HG/IE noise ratio"
    )
    assert any(f.startswith("HG_gate_skipped") for f in result["flags"]), (
        "the skip must be surfaced as an informational flag, never silent"
    )
    # KE dropped 50% → impact clearly visible, dissipation honest
    assert s["impact_visible"] is True
    assert s["diss_pct"] is not None and s["diss_pct"] > 0


# ---------------------------------------------------------------------------
# Case B — flat KE: impact not in the glstat window
# ---------------------------------------------------------------------------

def test_flat_ke_flags_no_impact_and_none_diss(tmp_path: Path) -> None:
    ke = 2.01486e2  # June artifact: identical first/last cycle KE
    cycles = [
        _cycle(0.0,    ke, 1.0e-6, 5.0e-7, 0.0, ke),
        _cycle(5.0e-4, ke, 1.2e-6, 6.0e-7, 0.0, ke),
        _cycle(1.0e-3, ke, 1.1e-6, 5.5e-7, 0.0, ke),
    ]
    result = audit_run(_write(tmp_path, cycles))

    s = result["summary"]
    assert s["impact_visible"] is False
    assert "no-impact-in-glstat-window" in result["flags"]
    assert s["diss_pct"] is None, (
        "flat-KE window must report diss_pct=None, not a fabricated 0.0"
    )
    # TE stable + SL zero → the applicable gates pass; flat KE alone is not FAIL
    assert result["pass_fail"] != "FAIL"


# ---------------------------------------------------------------------------
# Case C — genuinely hourglassing run must still FAIL
# ---------------------------------------------------------------------------

def test_genuine_hourglassing_still_fails(tmp_path: Path) -> None:
    ke0 = 1.0e5
    cycles = [
        _cycle(0.0,    ke0,       1.0e3,  1.0e2, 0.0,   ke0),
        _cycle(5.0e-4, ke0 * 0.6, 4.0e4,  1.0e4, 5.0e2, ke0 * 0.99),
        _cycle(1.0e-3, ke0 * 0.4, 3.5e4,  9.0e3, 8.0e2, ke0 * 0.985),
    ]
    result = audit_run(_write(tmp_path, cycles))

    s = result["summary"]
    assert s["ie_significant"] is True  # ie_peak=4e4 >> 0.1% of 1e5
    assert s["impact_visible"] is True
    # hg_frac = 1e4/4e4 = 25% ≥ FAIL(20%) → the real defect still fails
    assert result["pass_fail"] == "FAIL"
    assert any(f.startswith("HG_frac") for f in result["flags"])


# ---------------------------------------------------------------------------
# Parser sanity for the fixture format itself
# ---------------------------------------------------------------------------

def test_fixture_format_parses(tmp_path: Path) -> None:
    cycles = [_cycle(0.0, 1.0, 0.1, 0.01, 0.0, 1.0),
              _cycle(1e-4, 0.9, 0.2, 0.02, 0.0, 1.0)]
    ts = parse_glstat(_write(tmp_path, cycles))
    assert ts.n_cycles == 2
    assert math.isclose(ts.cycles[1]["ke"], 0.9, rel_tol=1e-6)
