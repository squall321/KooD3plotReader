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


def _findings(i: int) -> list:
    """리비전별 findings — 차분의 4가지 경로를 전부 태운다.

    ① 수치만 변동(유지+변동) ② 완전 동일(유지) ③ 리비전마다 신규 ④ 해소.
    골든이 findings 를 비워두면 diff 코드가 통째로 잠기지 않는다(실측 공백).
    """
    out = [
        {"severity": "WARNING", "title": f"접촉 미발생 런 {6 - 2 * i}/{len(COORDS)} — 배치 검토"},
        {"severity": "INFO", "title": "단위계 자동 검출 — mm/ms/kg"},
        {"severity": "WARNING", "title": f"P{i + 1}: statistical outlier for peak_g (|z|={4.1 + i})"},
    ]
    if i == 0:
        out.append({"severity": "CRITICAL", "title": "Display 파트 소성변형 한계 초과"})
    return out


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
                                      part_values=pv, findings=_findings(i)))
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
    # winner = 값이 가장 큰(= 가장 나쁜) 리비전의 인덱스. 단조 개선 데이터라
    # baseline(RevA)이 항상 최악이어야 한다 — '최고'로 뒤집혀 읽히면 실패한다.
    assert all(c["winner"] == 0 for c in cells), "winner 는 최악 리비전 인덱스여야 한다"
    # 파트 추이도 리비전 수와 일치
    for p in cmp_["parts"]:
        assert len(p["worst"]) == n_rev

    # 참피크는 리샘플 이전 실측 최대값 — 격자 worst 가 이걸 넘으면 보간이
    # 없는 값을 만들어낸 것이다 (IDW 는 이웃 가중평균이라 구조상 불가능)
    kpi = cmp_["kpi"]
    for gw, tp in zip(kpi["worst_per_rev"], kpi["true_peak_per_rev"]):
        assert tp is not None, "참피크가 비었다 — 실측 원본에서 뽑지 못했다"
        assert gw <= tp + 1e-9, f"격자 worst({gw}) 가 참피크({tp}) 를 넘었다"
    assert kpi["true_peak_delta_pct"][cmp_["baseline_idx"]] in (0.0, None)

    # findings diff 가 실제로 데이터를 태우고 있어야 한다 (골든이 빈 채로
    # 통과하면 diff 코드는 잠기지 않는다 — 실측 공백이었다)
    fds = [f for f in cmp_["findings_diff"] if not f["is_baseline"]]
    assert len(fds) == n_rev - 1
    for fd in fds:
        assert fd["n_total"] > 0, "골든 픽스처에 findings 가 비어 있다"
        # 정체 키 충돌이 없으면 신규+유지 = 전체 (조용한 소실 금지)
        assert len(fd["new"]) + len(fd["kept"]) == fd["n_total"]
        # 수치만 바뀐 '접촉 미발생 런 n/3' 은 신규/해소가 아니라 변동으로 잡혀야 한다
        assert any("접촉 미발생" in c["after"]["title"] for c in fd["changed"]), (
            "수치만 변한 이슈가 변동으로 잡히지 않았다 (이중 계상 회귀)")
        assert not any("접촉 미발생" in f["title"] for f in fd["new"])
        # baseline 에만 있던 CRITICAL 은 해소로 잡힌다
        assert any(f["severity"] == "CRITICAL" for f in fd["resolved"])


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
