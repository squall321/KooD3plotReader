# unified_analyzer 를 sets/set_reports YAML 로 구동하고 산출물을 수집하는 오케스트레이터
"""Custom Report 실행 계층.

무거운 일(세트 파싱·지표·렌더)은 전부 C++ unified_analyzer 가 한다.
여기서는 사용자 설정을 C++ YAML 로 합성해 실행하고, per-set 산출물
(metrics.json / view_*.mp4 / peak_*.png)을 모아 보고서 빌더에 넘긴다.

산출물 규약 (C++ processSetViews / exportResults 와 동일):
    <out>/set_reports/<safe_name>/metrics.json
    <out>/set_reports/<safe_name>/view_<plane>_<field>.mp4
    <out>/set_reports/<safe_name>/peak_<plane>_<field>.png
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# 산출물 스키마 버전 — 형식이 바뀌면 올린다 (deep 의 UA_OUTPUT_SCHEMA 관례)
CUSTOM_REPORT_SCHEMA = 1


# ---------------------------------------------------------------------------
# unified_analyzer 탐색 (koo_deep_report 의 관례를 따르되 의존은 선택적으로)
# ---------------------------------------------------------------------------

def find_unified_analyzer() -> str | None:
    """unified_analyzer 바이너리를 찾는다. 환경변수 > deep 패키지 관례 > PATH."""
    env = os.environ.get("KOOD3PLOT_HOME")
    if env:
        cand = Path(env) / "bin" / "unified_analyzer"
        if cand.is_file():
            return str(cand)

    # koo_deep_report 가 설치돼 있으면 그 탐색 로직 재사용
    try:
        from koo_deep_report.core.d3plot_reader import find_unified_analyzer as _f
        found = _f()
        if found:
            return str(found)
    except Exception:
        pass

    # 저장소 빌드 트리 (이 파일 기준 ../../../../build/examples)
    repo = Path(__file__).resolve().parents[3]
    cand = repo.parent / "build" / "examples" / "unified_analyzer"
    if cand.is_file():
        return str(cand)
    cand = repo / "build" / "examples" / "unified_analyzer"
    if cand.is_file():
        return str(cand)

    return shutil.which("unified_analyzer")


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------

@dataclass
class SetSpec:
    """set_reports 항목 하나 (C++ SetReportSpec 과 1:1)."""
    name: str
    set_type: str = "part"
    set_id: int = 0
    fields: list[str] = field(default_factory=list)
    planes: list[str] = field(default_factory=lambda: ["xy", "yz", "zx"])
    video: bool = True
    peak_snapshot: bool = True
    width: int = 1280
    height: int = 720
    max_frames: int = 0
    # 세트 파일 없이 YAML 에서 직접 고르는 경로 (셋 다 합집합)
    part_ids: list[int] = field(default_factory=list)
    part_patterns: list[str] = field(default_factory=list)
    # 연동 세그먼트 셋 — 렌더 위 하이라이트 + 영역 최대값 라벨
    highlight_segments: list[int] = field(default_factory=list)


@dataclass
class CustomReportConfig:
    sets_file: str = ""            # 비우면 C++ 이 d3plot 옆에서 자동 탐색
    set_reports: list[SetSpec] = field(default_factory=list)
    threads: int = 4


def load_config(path: str | Path) -> CustomReportConfig:
    """사용자 YAML (sets:/set_reports: 만 담은 파일)을 읽는다."""
    import yaml

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    cfg = CustomReportConfig()
    sets = raw.get("sets") or {}
    if isinstance(sets, dict):
        cfg.sets_file = str(sets.get("file") or "")
    elif isinstance(sets, str):
        cfg.sets_file = sets

    for item in raw.get("set_reports") or []:
        if not isinstance(item, dict):
            continue
        spec = SetSpec(
            name=str(item.get("name") or ""),
            set_type=str(item.get("set_type") or item.get("type") or "part"),
            set_id=int(item.get("set_id") or item.get("id") or 0),
            fields=[str(x) for x in (item.get("fields") or [])],
            planes=[str(x) for x in (item.get("planes") or ["xy", "yz", "zx"])],
            video=bool(item.get("video", True)),
            peak_snapshot=bool(item.get("peak_snapshot", True)),
            width=int(item.get("width") or 1280),
            height=int(item.get("height") or 720),
            max_frames=int(item.get("max_frames") or 0),
            part_ids=[int(x) for x in (item.get("parts") or item.get("part_ids") or [])],
            part_patterns=[str(x) for x in (item.get("part_patterns")
                                            or item.get("part_names") or [])],
            highlight_segments=[int(x) for x in (item.get("highlight_segments")
                                                 or item.get("segments") or [])],
        )
        if spec.name:
            cfg.set_reports.append(spec)

    perf = raw.get("performance") or {}
    if isinstance(perf, dict) and perf.get("threads") is not None:
        cfg.threads = int(perf["threads"])

    return cfg


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def _yaml_str(v: str) -> str:
    return '"' + v.replace('"', '') + '"'


def build_ua_yaml(d3plot: str, out_dir: str, cfg: CustomReportConfig) -> str:
    """C++ unified_analyzer 용 YAML 합성.

    주의: C++ 파서는 수제라 리스트는 반드시 인라인([a, b]) 형식,
    set_reports 필드는 indent 4 고정이다 (docs/custom_report/context-notes.md).
    """
    lines: list[str] = []
    lines.append('version: "2.0"')
    lines.append("input:")
    lines.append(f"  d3plot: {_yaml_str(d3plot)}")
    lines.append("output:")
    lines.append(f"  directory: {_yaml_str(out_dir)}")
    lines.append("  json: true")
    lines.append("  csv: true")
    lines.append("performance:")
    lines.append(f"  threads: {cfg.threads}")
    lines.append("  surface_defaults: false")
    if cfg.sets_file:
        lines.append("sets:")
        lines.append(f"  file: {_yaml_str(cfg.sets_file)}")
    lines.append("set_reports:")
    for s in cfg.set_reports:
        lines.append(f"  - name: {_yaml_str(s.name)}")
        lines.append(f"    set_type: {s.set_type}")
        lines.append(f"    set_id: {s.set_id}")
        if s.fields:
            lines.append(f"    fields: [{', '.join(s.fields)}]")
        lines.append(f"    planes: [{', '.join(s.planes)}]")
        lines.append(f"    video: {'true' if s.video else 'false'}")
        lines.append(f"    peak_snapshot: {'true' if s.peak_snapshot else 'false'}")
        lines.append(f"    width: {s.width}")
        lines.append(f"    height: {s.height}")
        lines.append(f"    max_frames: {s.max_frames}")
        if s.part_ids:
            lines.append(f"    parts: [{', '.join(str(x) for x in s.part_ids)}]")
        if s.part_patterns:
            pats = ", ".join('"' + x.replace('"', '') + '"' for x in s.part_patterns)
            lines.append(f"    part_patterns: [{pats}]")
        if s.highlight_segments:
            lines.append(
                f"    highlight_segments: [{', '.join(str(x) for x in s.highlight_segments)}]")
    return "\n".join(lines) + "\n"


@dataclass
class SetResult:
    """수집된 per-set 산출물."""
    name: str
    safe_name: str
    metrics: dict
    media: dict[str, str] = field(default_factory=dict)  # "peak_xy_von_mises" → 상대경로


@dataclass
class RunResult:
    ok: bool
    error: str = ""
    out_dir: str = ""
    sets: list[SetResult] = field(default_factory=list)
    ua_log_tail: str = ""


def run(d3plot: str | Path, out_dir: str | Path, cfg: CustomReportConfig,
        ua_path: str | None = None, verbose: bool = True) -> RunResult:
    """unified_analyzer 실행 후 산출물 수집."""
    d3plot = str(d3plot)
    out_dir = str(out_dir)

    if not cfg.set_reports:
        return RunResult(ok=False, error="set_reports 가 비어 있음 — 설정 YAML 확인")
    if not Path(d3plot).exists():
        return RunResult(ok=False, error=f"d3plot 없음: {d3plot}")

    ua = ua_path or find_unified_analyzer()
    if not ua:
        return RunResult(ok=False, error="unified_analyzer 를 찾지 못함 (KOOD3PLOT_HOME 확인)")

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    yaml_text = build_ua_yaml(d3plot, out_dir, cfg)
    yaml_path = Path(out_dir) / "_custom_report_ua.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = subprocess.run(
        [ua, "--config", str(yaml_path)],
        capture_output=True, text=True,
    )
    tail = "\n".join((proc.stdout or "").splitlines()[-25:])
    if verbose:
        sys.stderr.write(tail + "\n")
    if proc.returncode != 0:
        return RunResult(ok=False, out_dir=out_dir, ua_log_tail=tail,
                         error=f"unified_analyzer 종료 코드 {proc.returncode}")

    # ---- 산출물 수집 ----
    result = RunResult(ok=True, out_dir=out_dir, ua_log_tail=tail)
    root = Path(out_dir) / "set_reports"
    if not root.is_dir():
        result.ok = False
        result.error = "set_reports 산출물이 없음 — 세트 파일/세트 ID 를 확인"
        return result

    for set_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        mj = set_dir / "metrics.json"
        if not mj.is_file():
            continue
        try:
            metrics = json.loads(mj.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            metrics = {"name": set_dir.name, "notes": [f"metrics.json 파싱 실패: {e}"],
                       "fields": []}
        sr = SetResult(name=str(metrics.get("name") or set_dir.name),
                       safe_name=set_dir.name, metrics=metrics)
        for p in sorted(set_dir.iterdir()):
            if p.suffix in (".mp4", ".png"):
                # 보고서 HTML(<out>/custom_report.html) 기준 상대경로
                sr.media[p.stem] = f"set_reports/{set_dir.name}/{p.name}"
        result.sets.append(sr)

    # 스키마 마커 (재실행 신선도 판단용)
    (root / ".custom_report_schema").write_text(str(CUSTOM_REPORT_SCHEMA), encoding="utf-8")
    return result
