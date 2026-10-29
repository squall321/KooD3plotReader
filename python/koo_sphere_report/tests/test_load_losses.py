# 적재에서 빠진 런을 사유별로 세어 말하는지 — 0건 성공을 성공으로 넘기지 않는다
"""적재 손실 보고.

실측 배경 (2026-10, M3_P2 979런). 샤드가 "Loaded 0 results" 만 찍고 **성공으로
끝났다.** 런 폴더는 있는데 `output/<run>/DropSet.json` 이 없어 전부 탈락한
것이었지만, 로더가 `sr is None` 을 조용히 버려 까닭을 아무도 몰랐다. 수동
복구에 9시간이 들었다.

여기서 못박는 규칙.
- 빠진 런은 **사유별로 세어** 말한다.
- 전멸이면 **exit 3** — 0건 성공은 성공이 아니다.
- 깨진 DropSet.json 하나가 **캠페인 전체를 죽이지 않는다** (사유로 세고 계속).
- `Loaded N results` 줄은 **진단보다 먼저** 나간다 (상류 셸이 이 줄을 본다).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_PARTS = {"1": "Front\\Metal", "2": "PCB\\PCB"}
_ANG = [(0.0, 0.0, 0.0), (0.0, 90.0, 0.0), (180.0, 0.0, 0.0),
        (0.0, -90.0, 0.0), (90.0, 0.0, 0.0), (-90.0, 0.0, 0.0)]
_AR = {"analysis_info": {}, "parts": []}


def _campaign(base: Path, n=6, missing=0, broken=0, no_result=0) -> Path:
    """심볼릭 링크 **없는** 실파일 캠페인.

    (링크가 섞이면 시험이 바깥 공유 데이터를 건드릴 수 있다 — 2026-10-28 에
    실제로 그래서 /data 의 원본을 덮어쓴 적이 있다.)
    """
    for i in range(n):
        run = f"Run_{i:03d}"
        ar = base / "analysis_results" / run
        ar.mkdir(parents=True, exist_ok=True)
        if i < n - no_result:
            (ar / "analysis_result.json").write_text(json.dumps(_AR), encoding="utf-8")
        out = base / "output" / run
        out.mkdir(parents=True, exist_ok=True)
        r, p, y = _ANG[i % len(_ANG)]
        if i < missing:
            continue
        if i < missing + broken:
            (out / "DropSet.json").write_text("{ not json", encoding="utf-8")
            continue
        (out / "DropSet.json").write_text(json.dumps(
            {"initial_conditions": {"orientation_euler_deg":
                                    {"roll": r, "pitch": p, "yaw": y}},
             "model": {"parts": _PARTS}}), encoding="utf-8")
    assert not [q for q in base.rglob("*") if q.is_symlink()], "시험 자료에 링크가 있다"
    return base


def _run(d: Path):
    return subprocess.run(
        [sys.executable, "-m", "koo_sphere_report", "--test-dir", str(d),
         "--terminal-only"],
        capture_output=True, text=True, timeout=600,
        cwd=str(Path(__file__).resolve().parents[1]))


def test_all_loaded_is_silent(tmp_path):
    """전부 읽히면 손실 보고를 하지 않는다 — 없는 경고를 만들지 않는다."""
    r = _run(_campaign(tmp_path / "ok"))
    assert r.returncode == 0
    assert "Loaded 6 results" in r.stdout
    assert "읽지 못했습니다" not in r.stderr


def test_total_loss_exits_3_with_reasons(tmp_path):
    """**이 시험이 M3_P2 의 조용한 0건 성공을 잡는다.**"""
    r = _run(_campaign(tmp_path / "none", missing=4, broken=2))
    assert r.returncode == 3, f"0건인데 exit {r.returncode} 로 성공했다"
    assert "Loaded 0 results" in r.stdout, "셸이 보는 줄이 없다"
    assert "하나도 읽지 못했습니다" in r.stderr
    assert "DropSet.json 없음: 4런" in r.stderr
    assert "깨짐/권한): 2런" in r.stderr


def test_partial_loss_warns_and_continues(tmp_path):
    """부분 손실은 보고서를 내되 몇 개가 왜 빠졌는지 적는다."""
    r = _run(_campaign(tmp_path / "part", missing=2, broken=1))
    assert r.returncode == 0
    assert "Loaded 3 results" in r.stdout
    assert "6개 중 3개를 읽지 못했습니다" in r.stderr
    assert "DropSet.json 없음: 2런" in r.stderr


def test_missing_analysis_result_is_a_distinct_reason(tmp_path):
    """사유를 뭉뚱그리지 않는다 — DropSet 부재와 결과 부재는 할 일이 다르다."""
    r = _run(_campaign(tmp_path / "nores", no_result=3))
    assert r.returncode == 0
    assert "analysis_result.json 없음: 3런" in r.stderr
    assert "DropSet.json 없음" not in r.stderr


def test_broken_dropset_does_not_kill_the_campaign(tmp_path):
    """**깨진 파일 하나가 979런을 날리지 않는다.**

    `load_dropset` 와 `load_part_names` 둘 다 맨몸 `json.load` 였다. 한쪽만
    막으면 다른 쪽에서 똑같이 죽는다 — 실제로 그랬다.
    """
    r = _run(_campaign(tmp_path / "brk", broken=1))
    assert r.returncode == 0, f"깨진 1건에 전체가 죽었다:\n{r.stderr[-1500:]}"
    assert "Loaded 5 results" in r.stdout
    assert "Traceback" not in r.stderr


def test_loaded_line_precedes_diagnostics(tmp_path):
    """순서가 뒤집히면 상류 셸이 '줄이 없다' 로 읽어 우리 사유가 묻힌다."""
    import koo_sphere_report.__main__ as M
    src = Path(M.__file__).read_text(encoding="utf-8")
    i_print = src.index('print(f"Loaded {report.successful_runs} results')
    i_diag = src.index("_report_load_losses(report, test_dir)")
    assert i_print < i_diag, "진단이 Loaded 줄보다 앞선다"
    assert "sys.stdout.flush()" in src[i_print:i_diag], \
        "flush 가 없으면 파이프에서 stderr 가 먼저 나간다"
