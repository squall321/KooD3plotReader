# tier C/D 스케일 경로 골든 — --grid 합성으로 topk/저해상/청크 로직 회귀 방지
"""tier C(≤300)/D(>300) payload 골든 + 불변식.

기존 골든(test_golden_html)은 tier A(50위치)만 커버 — topk 인라인, 초저해상
trajectory, 청크 방출 등 스케일 경로는 수동 검증뿐이었다. 여기서는
``generate_sample --grid`` 로 결정적 합성 데이터셋을 만들어:

- tier C (121위치, F1 11×11): part_motion topk-40, traj ≤60pt, deferred 모드
- tier D (324위치, F1 18×18): series 인라인 0, traj ≤24pt, chunked 방출 324청크

를 payload 정규화 SHA 골든 + 하드 불변식으로 고정한다. 재기록은
``KOO_GOLDEN_UPDATE=1``.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
GEN_SCRIPT = HERE / "generate_sample.py"
GOLDEN_DIR = HERE / "golden"
UPDATE = os.environ.get("KOO_GOLDEN_UPDATE") == "1"

sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "koo_deep_report"))


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _gen(tmp_path_factory, name: str, faces: str, grid: str) -> Path:
    out = tmp_path_factory.mktemp(name) / "ds"
    subprocess.run(
        [sys.executable, str(GEN_SCRIPT), "--output", str(out),
         "--seed", "42", "--faces", faces, "--grid", grid],
        check=True, capture_output=True,
    )
    return out


def _payload_for(dataset: Path) -> dict:
    from koo_impact_report import loader
    from koo_impact_report.report.payload import _build_payload
    report = loader.load_impact_report(dataset)
    return _build_payload(report)


def _canon_sha(payload: dict, dataset: Path) -> str:
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    canon = canon.replace(str(dataset), "<DATASET>")
    return _sha(canon)


def _load_or_record(name: str, value: str) -> str | None:
    GOLDEN_DIR.mkdir(exist_ok=True)
    path = GOLDEN_DIR / f"{name}.sha256"
    if UPDATE or not path.exists():
        path.write_text(value + "\n", encoding="utf-8")
        return None
    return path.read_text(encoding="utf-8").strip()


@pytest.fixture(scope="session")
def ds_tier_c(tmp_path_factory):
    return _gen(tmp_path_factory, "tier_c", "F1", "11,11")   # 121 위치 → C


@pytest.fixture(scope="session")
def ds_tier_d(tmp_path_factory):
    return _gen(tmp_path_factory, "tier_d", "F1", "18,18")   # 324 위치 → D


def test_tier_c_invariants_and_golden(ds_tier_c):
    p = _payload_for(ds_tier_c)
    assert len(p["positions"]) == 121

    # topk: 인라인 part_motion series 는 최대 40개 위치로 제한
    pm = p["part_motion"]
    inline_pos = {s["pos_id"] for s in pm.get("series", [])}
    assert len(inline_pos) <= 40

    # trajectory 초저해상 (60pt + peak/last splice 여유 2)
    for tr in p["trajectories"].values():
        assert len(tr["t"]) <= 62
        # 시계열 배열은 비우지 않는다 (JS 5패널 생존 조건 — Playwright 실측 교훈)
        assert len(tr["ke"]) > 0

    # stress_ts ≤ 60 + splice 여유
    for r in p["results"]:
        ts = r.get("stress_ts")
        if ts:
            assert len(ts["times"]) <= 62

    baseline = _load_or_record("tier_c_payload", _canon_sha(p, ds_tier_c))
    if baseline is not None:
        assert _canon_sha(p, ds_tier_c) == baseline, (
            "tier C payload 골든 변경 — 의도라면 KOO_GOLDEN_UPDATE=1 로 재기록")


def test_tier_d_invariants_and_golden(ds_tier_d, tmp_path):
    from koo_impact_report import loader
    from koo_impact_report.report.payload import _build_payload
    report = loader.load_impact_report(ds_tier_d)
    p = _build_payload(report)
    assert len(p["positions"]) == 324

    # tier D: part_motion 곡선 인라인 없음 (요약 스칼라만)
    assert p["part_motion"]["series"] == []
    # trajectory 24pt + splice 여유
    for tr in p["trajectories"].values():
        assert len(tr["t"]) <= 26
        assert len(tr["ke"]) > 0
    # stress_ts envelope 만 (시계열 None)
    assert all(r.get("stress_ts") is None for r in p["results"])

    baseline = _load_or_record("tier_d_payload", _canon_sha(p, ds_tier_d))
    if baseline is not None:
        assert _canon_sha(p, ds_tier_d) == baseline, (
            "tier D payload 골든 변경 — 의도라면 KOO_GOLDEN_UPDATE=1 로 재기록")

    # chunked 방출 E2E: report_data/ 청크 수 == 위치 수, manifest 정합
    from koo_impact_report.report.emit import emit_report
    out = tmp_path / "report.html"
    emit_report(report, out)   # 324위치 → tier D → chunked 자동
    data_dir = tmp_path / "report_data"
    assert data_dir.is_dir()
    chunks = sorted(data_dir.glob("pos_*.js"))
    assert len(chunks) == 324
    html = out.read_text(encoding="utf-8")
    assert '"koo-data"' in html          # deferred JSON 블록
    doc = json.loads((tmp_path / "impact_payload.json").read_text(encoding="utf-8"))
    ids = doc["payload"]["chunks"]["ids"]
    assert len(ids) == 324
    assert {f"{i}.js" for i in ids} == {c.name for c in chunks}
