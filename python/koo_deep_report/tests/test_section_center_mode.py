# 단면 자를 자리(center_mode)가 CLI·YAML 에서 엔진까지 배선되는지 검증
"""section_view center_mode 배선.

실측 배경 (2026-10-18). auto_center 는 **형상의 AABB 가운데**를 자른다. 형상
가운데가 응력 피크가 있는 자리라는 보장은 없다. 400상태 실덱에서 AABB 는
z=-10.025, σ_vm 피크(310.4 @state 22)는 z=-2.300 — **7.7mm 비켜 갔고**, AABB
단면 그림은 점 몇 개뿐인 거의 빈 화면이었다. 컬러바는 그대로 310.4 를 띄우니
보는 사람은 "여긴 괜찮네" 로 읽는다.

center_mode: peak 를 쓰면 전 상태를 훑어 절점평균 최대가 난 자리를 지나게
자른다. 같은 프레임이 5.3KB → 31.7KB (실제 구조 단면).

여기서 못박는 것 — **그 선택지가 CLI 에서 보이고, YAML 까지 실제로 간다.**
"""
from __future__ import annotations

import re
import subprocess
import sys

from koo_deep_report.render.job_builder import (
    SectionViewRenderConfig, build_section_view_yaml_entries,
)


def _blocks(center_mode: str) -> str:
    cfg = SectionViewRenderConfig(
        enabled=True, backend="software", axes=["z"], scalar_fields=["von_mises"],
        center_mode=center_mode,
    )
    entries = build_section_view_yaml_entries("/tmp/out", cfg)
    assert entries, "항목이 안 나왔다"
    return "\n".join(b for _, b in entries)


def test_default_is_aabb():
    """기본값은 종전 동작 — 조용히 그림이 바뀌지 않는다."""
    assert SectionViewRenderConfig().center_mode == "aabb"
    assert "center_mode: aabb" in _blocks("aabb")


def test_peak_reaches_yaml():
    """**이 시험이 배선 누락을 잡는다** — 옵션만 있고 YAML 에 안 가면 무음 실패다."""
    body = _blocks("peak")
    assert "center_mode: peak" in body
    # auto_center 가 꺼져 있으면 center_mode 는 아무 일도 안 한다 — 같이 켜져야 한다
    assert "auto_center: true" in body


def test_cli_exposes_choice():
    """--help 에 보여야 쓸 수 있다. 숨은 YAML 키로만 두면 없는 것과 같다."""
    out = subprocess.run([sys.executable, "-m", "koo_deep_report", "--help"],
                         capture_output=True, text=True, timeout=120).stdout
    assert "--section-view-center" in out
    # 고를 수 있는 값이 적혀 있어야 한다
    m = re.search(r"--section-view-center\s+\{([^}]*)\}", out)
    assert m, f"선택지가 안 보인다:\n{out[:400]}"
    assert set(m.group(1).split(",")) == {"aabb", "peak"}
