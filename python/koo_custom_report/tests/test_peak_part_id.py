# 피크 파트 ID 0 을 '파트 0' 으로 찍지 않는지 검증
"""파트 ID 는 1부터다. 0 은 '파트 0' 이 아니라 **안 매겨졌다**는 뜻이다.

실측 배경 (2026-10-18, pykoocae-53 이 MCP e2e 에서 지적).
세그먼트 세트 산출물의 `peak_part_id` 가 두 필드 모두 0 이었다. 원인은 C++ 쪽
세그먼트 직접 스윕(P6) 경로가 그 값을 채우지 않은 것이었다 — "대표 파트: 그 요소의
파트" 라는 주석과 **빈 if 블록**만 있었다. 지금은 피크 요소의 인덱스로
`mesh.solid_parts` 를 찾아 채운다.

그런데 화면 쪽에도 문제가 있었다. 표가 `f.get("peak_part_id", "")` 로 그대로 찍어서
0 이 **존재하지 않는 파트 번호처럼** 보였다. 노드 세트는 절점이 파트에 속하지 않아
원래 못 매기므로 그쪽은 0 이 정상인데, 그래도 '0' 이라고 쓰면 거짓이다.

여기서 못박는 규칙 — **0/없음은 미계측과 같은 '—' 로 찍는다.**
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_custom_report.report.html_report import build_html  # noqa: E402
from koo_custom_report.runner import RunResult, SetResult  # noqa: E402


def _field(part_id):
    f = {"field": "von_mises", "measured": True, "peak": 269.92447,
         "peak_time": 3.93743067e-05, "peak_element_id": 14886, "note": ""}
    if part_id is not None:
        f["peak_part_id"] = part_id
    return f


def _html(part_id):
    sr = SetResult(
        name="Seg 1",
        safe_name="seg_1",
        metrics={"set_type": "SEGMENT", "set_id": 1, "title": "t",
                 "metric_source": "segments", "resolved_parts": [1],
                 "fields": [_field(part_id)]},
    )
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "custom_report.html"
        build_html(RunResult(ok=True, out_dir=td, sets=[sr]), "/x/d3plot", out)
        return out.read_text(encoding="utf-8")


def test_zero_is_not_shown_as_part_zero():
    """**이 시험이 2026-10-18 의 지적을 잡는다.** 0 을 '0' 으로 찍으면 안 된다."""
    html = _html(0)
    assert ">0</td>" not in html, "peak_part_id 0 을 파트 번호처럼 찍었다"
    assert "—" in html


def test_missing_key_is_not_shown_as_blank_cell():
    """키가 아예 없을 때도 '—' 다 — 빈 칸은 '안 봤다' 로도 읽힌다."""
    assert "—" in _html(None)


def test_real_part_id_is_shown():
    """제대로 매겨진 파트는 그대로 보여야 한다 (과잉 숨김 금지)."""
    html = _html(1)
    assert ">1</td>" in html, "실제 파트 ID 를 숨겼다"


def test_large_part_id_survives():
    html = _html(1012)
    assert ">1012</td>" in html
