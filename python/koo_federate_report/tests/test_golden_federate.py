# 결정적 골든 — 합성 2·3리비전 연합 결과의 구조/수치를 고정해 회귀를 잡는다
"""federate 골든.

수치 골든(payload 정규화 SHA)과 **구조 불변식**을 함께 건다. 값이 의도적으로
바뀌면 `KOO_GOLDEN_UPDATE=1` 로 재기록하되, 불변식은 재기록으로 넘어가지 않는다
(부재를 0 으로 채우지 않는다 같은 규칙은 값과 무관하게 항상 참이어야 한다).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from koo_federate_report.compare import build_comparison
from koo_federate_report.config import Options
from koo_federate_report.matching import build_matching
from koo_federate_report.resample import align
from koo_federate_report.report.html_report import generate_html
from tests.helpers import make_impact_bundle

GOLDEN_DIR = Path(__file__).parent / "golden"
UPDATE = os.environ.get("KOO_GOLDEN_UPDATE") == "1"

COORDS = [("P1", -10.0, 0.0), ("P2", 10.0, 0.0), ("P3", 0.0, 20.0)]
PARTS = {1: "Display", 2: "PCB"}


def _bundles(n_rev: int):
    """리비전 n개 — 리비전 순번에 대해 단조 개선(결정적)."""
    out = []
    for i in range(n_rev):
        scale = 1.0 - 0.2 * i          # RevB=0.8, RevC=0.6
        specs, pv = [], {}
        for j, (key, x, y) in enumerate(COORDS):
            g = 1000.0 * scale * (1 + 0.1 * j)
            specs.append((key, x, y, "F5", g, True, "bounce"))
            pv[(key, "Display")] = {"g": g, "s": g / 10.0, "e": None, "d": None}
            pv[(key, "PCB")] = {"g": g * 0.8, "s": g / 12.0, "e": None, "d": None}
        out.append(make_impact_bundle(f"Rev{chr(65 + i)}", specs, PARTS,
                                      part_values=pv))
    return out


def _compare(n_rev: int) -> dict:
    bundles = _bundles(n_rev)
    options = Options()
    match = build_matching(bundles, {}, options)
    aligned = align(bundles, 0, "impact", options.resample)
    return build_comparison(bundles, 0, "impact", match, aligned, options, metric="g")


def _sha(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _load_or_record(name: str, value: str) -> str | None:
    GOLDEN_DIR.mkdir(exist_ok=True)
    path = GOLDEN_DIR / f"{name}.sha256"
    if UPDATE or not path.exists():
        path.write_text(value + "\n", encoding="utf-8")
        return None
    return path.read_text(encoding="utf-8").strip()


def _volatile_stripped(cmp_: dict) -> dict:
    """골든 해시 전 휘발성 필드 제거 (경로/시각/버전)."""
    d = copy.deepcopy(cmp_)
    d.pop("provenance", None)
    for r in d.get("revisions") or []:
        for k in ("path", "project", "schema_version"):
            r.pop(k, None)
    return d


@pytest.mark.parametrize("n_rev", [2, 3])
def test_compare_payload_golden(n_rev):
    cmp_ = _compare(n_rev)
    got = _sha(_volatile_stripped(cmp_))
    base = _load_or_record(f"federate_compare_n{n_rev}", got)
    if base is not None:
        assert got == base, (
            f"n_rev={n_rev} 비교 payload 골든 변경 — 의도라면 KOO_GOLDEN_UPDATE=1")


@pytest.mark.parametrize("n_rev", [2, 3])
def test_compare_invariants(n_rev):
    """값과 무관하게 항상 참이어야 하는 규칙 (재기록으로 넘어가지 않는다)."""
    cmp_ = _compare(n_rev)
    cells = cmp_["cells"]
    assert len(cells) == len(COORDS)
    for c in cells:
        assert len(c["per_rev"]) == n_rev, "리비전 수만큼 값이 있어야 한다"
        # baseline 자신의 Δ 는 0
        assert c["delta_pct"][0] in (0.0, None)
        # 미판정이면 판정값이 전부 None (0 으로 위장 금지)
        if not c.get("trust_ok", True):
            assert c["winner"] is None and c["trend"] is None
    # 단조 개선 데이터이므로 baseline(RevA)이 항상 최악
    assert all(c["winner"] == 0 for c in cells), "단조 개선이면 winner=baseline"
    # 파트 추이도 리비전 수와 일치
    for p in cmp_["parts"]:
        assert len(p["worst"]) == n_rev


@pytest.mark.parametrize("n_rev", [2, 3])
def test_html_renders_and_is_deterministic(n_rev):
    cmp_ = _compare(n_rev)
    h1 = generate_html(cmp_)
    h2 = generate_html(_compare(n_rev))
    assert h1 == h2, "같은 입력이면 같은 HTML (결정성)"
    assert h1.startswith("<!DOCTYPE html>")
    # N=2 면 TREND 는 Δ 와 동일하므로 강등된다
    if n_rev == 2:
        assert "N=2" in h1 or "fed-map-trend" not in h1 or "강등" in h1
