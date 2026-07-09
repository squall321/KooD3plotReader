# 골든 회귀 테스트: 모듈 분할(P3) 전후 generate_html 출력 불변을 보장하는 안전판
"""Golden regression tests for the impact HTML report.

Two golden layers (see docs/impact-sota-checklist.md P0/P3):

1. **Byte golden** — SHA-256 of the full HTML string. Guards the *mechanical*
   split phase, where every commit must keep the output byte-identical.
2. **Normalized golden** — three content hashes that survive intentional
   byte-level reshuffling (JS regroup phase):
     * canonical DATA payload (extracted JSON, ``sort_keys`` re-dump)
     * script-stripped HTML skeleton
     * sorted set of top-level JS function names

Baselines live in ``tests/golden/``. To (re)record after an INTENTIONAL
behavior change::

    KOO_GOLDEN_UPDATE=1 python -m pytest tests/test_golden_html.py

Determinism notes:
- dataset from ``generate_sample.py --seed 42`` (deterministic rng).
- sklearn KMeans is env-dependent → the fixture blocks ``sklearn.cluster``
  so ``compute_trajectory_clusters`` always uses the in-repo Lloyd path.
- html_report.py has no datetime/random on the Python side (verified).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
GEN_SCRIPT = HERE / "generate_sample.py"
GOLDEN_DIR = HERE / "golden"

UPDATE = os.environ.get("KOO_GOLDEN_UPDATE") == "1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def dataset(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("golden_dataset") / "sample"
    subprocess.run(
        [sys.executable, str(GEN_SCRIPT), "--output", str(out), "--seed", "42"],
        check=True,
        capture_output=True,
    )
    return out


@pytest.fixture(scope="session")
def golden_html(dataset: Path) -> str:
    """Load → analyze → generate_html, pinned to the env-independent paths.

    The returned HTML is path-scrubbed: the (per-session tmp) dataset dir is
    embedded in the payload (``meta.test_dir`` etc.), so every occurrence is
    replaced with the stable token ``<DATASET>`` before hashing.
    """
    # Force compute_trajectory_clusters onto the in-repo Lloyd implementation:
    # the function does a lazy ``from sklearn.cluster import KMeans`` inside a
    # try/except — poisoning the module entry makes that import raise.
    saved = sys.modules.get("sklearn.cluster")
    sys.modules["sklearn.cluster"] = None  # type: ignore[assignment]
    try:
        from koo_impact_report import analyzer
        from koo_impact_report.loader import load_impact_report
        from koo_impact_report.report.html_report import generate_html

        report = load_impact_report(dataset)
        analyzer.analyze(report)
        html = generate_html(report)
    finally:
        if saved is not None:
            sys.modules["sklearn.cluster"] = saved
        else:
            sys.modules.pop("sklearn.cluster", None)

    for p in {str(dataset.resolve()), str(dataset)}:
        html = html.replace(p, "<DATASET>")
    return html


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_data_payload(html: str) -> dict:
    """Pull the embedded ``const DATA = {...};`` JSON out of the HTML."""
    marker = "const DATA = "
    idx = html.index(marker) + len(marker)
    payload, _end = json.JSONDecoder().raw_decode(html, idx)
    return payload


_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL)
_FN_RE = re.compile(r"function\s+([A-Za-z_$][\w$]*)\s*\(")


def _normalized_hashes(html: str) -> dict[str, str]:
    payload = _extract_data_payload(html)
    canon_data = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    skeleton = _SCRIPT_RE.sub("<script/>", html)
    scripts = "\n".join(m.group(0) for m in _SCRIPT_RE.finditer(html))
    fn_names = "\n".join(sorted(set(_FN_RE.findall(scripts))))
    return {
        "data": _sha(canon_data),
        "skeleton": _sha(skeleton),
        "js_functions": _sha(fn_names),
    }


def _load_or_record(name: str, value: str) -> str | None:
    """Return the baseline for *name*, recording it when updating/missing."""
    GOLDEN_DIR.mkdir(exist_ok=True)
    path = GOLDEN_DIR / f"{name}.sha256"
    if UPDATE or not path.exists():
        path.write_text(value + "\n", encoding="utf-8")
        return None  # freshly recorded → caller skips
    return path.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_golden_byte_sha256(golden_html: str) -> None:
    """Mechanical-split guard: full HTML must stay byte-identical."""
    actual = _sha(golden_html)
    baseline = _load_or_record("html_bytes", actual)
    if baseline is None:
        pytest.skip("byte golden recorded — rerun to compare")
    assert actual == baseline, (
        "generate_html output changed at byte level. If intentional, rerun "
        "with KOO_GOLDEN_UPDATE=1 to re-record."
    )


def test_golden_normalized(golden_html: str) -> None:
    """Content guard: DATA payload / HTML skeleton / JS function set."""
    hashes = _normalized_hashes(golden_html)
    recorded_any = False
    for name, actual in hashes.items():
        baseline = _load_or_record(f"norm_{name}", actual)
        if baseline is None:
            recorded_any = True
            continue
        assert actual == baseline, (
            f"normalized golden '{name}' changed. If intentional, rerun with "
            "KOO_GOLDEN_UPDATE=1."
        )
    if recorded_any:
        pytest.skip("normalized golden recorded — rerun to compare")


def test_payload_extractable_and_sane(golden_html: str) -> None:
    """The DATA blob parses and carries the stable top-level contract keys."""
    payload = _extract_data_payload(golden_html)
    for key in ("meta", "kpi", "results", "findings"):
        assert key in payload, f"payload missing contract key: {key}"
    assert isinstance(payload["results"], list) and payload["results"], (
        "payload.results empty — sample dataset should yield real results"
    )
