# federate.yaml (계획서 §0 스키마) 로드/검증 — 친절한 에러 메시지 담당
"""federate.yaml 파서.

검증 실패는 전부 ConfigError 로, "어느 키가 왜 틀렸는지 + 1-based 순번"을 담아
던진다. 조용한 기본값 대체는 하지 않는다 (무음 실패 금지).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    import yaml
except ImportError as exc:  # pragma: no cover - 환경 문제
    raise ImportError("koo_federate_report 는 PyYAML 이 필요합니다 (pip install pyyaml)") from exc


class ConfigError(Exception):
    """federate.yaml 스키마 위반."""


KINDS = ("auto", "sphere", "impact")
UNMATCHED_MODES = ("show", "hide", "error")
RESAMPLE_MODES = ("idw", "nearest", "off")
UNIT_POLICIES = ("error", "convert")

_TOP_KEYS = {"kind", "baseline", "output", "reports", "options", "parts"}
_REPORT_KEYS = {"path", "label"}
_OPTION_DEFAULTS = {
    "auto_match_identical": True,
    "name_normalize": True,
    "unmatched": "show",
    # nearest = 좌표 완전일치 우선, 실패 시 격자 40% 반경 최근접. 보간이 아니므로
    # 기본값으로 안전하다. 구면 보간이 필요하면 idw 를 명시하라.
    "resample": "nearest",
    "trust_gate": True,
    "unit_policy": "error",
}


@dataclass
class ReportEntry:
    path: str
    label: str = ""


@dataclass
class Options:
    auto_match_identical: bool = True
    name_normalize: bool = True
    unmatched: str = "show"
    resample: str = "nearest"
    trust_gate: bool = True
    unit_policy: str = "error"


@dataclass
class FederateConfig:
    kind: str = "auto"
    baseline: int = 1  # 1-based (YAML 표기 그대로 보존)
    output: str = "federate_report.html"
    reports: list = field(default_factory=list)  # list[ReportEntry]
    options: Options = field(default_factory=Options)
    parts: dict = field(default_factory=dict)  # canonical → list[str|None] (리비전 순)
    source_path: str = ""

    @property
    def baseline_idx(self) -> int:
        """0-based 색인."""
        return self.baseline - 1

    @property
    def n_revisions(self) -> int:
        return len(self.reports)


def _ordinal(i: int) -> str:
    return f"{i + 1}번째"


def _require_mapping(node, where: str) -> dict:
    if node is None:
        return {}
    if not isinstance(node, dict):
        raise ConfigError(f"{where} 는 매핑(key: value)이어야 합니다 — 현재 {type(node).__name__}")
    return node


def _parse_reports(raw) -> list:
    if raw is None:
        raise ConfigError("reports 키가 없습니다 — 비교할 sidecar 경로 목록이 필요합니다")
    if not isinstance(raw, list):
        raise ConfigError(f"reports 는 목록이어야 합니다 — 현재 {type(raw).__name__}")
    if len(raw) < 2:
        raise ConfigError(
            f"reports 는 최소 2개여야 합니다 (연합 비교) — 현재 {len(raw)}개"
        )

    out = []
    for i, item in enumerate(raw):
        if isinstance(item, str):
            item = {"path": item}
        if not isinstance(item, dict):
            raise ConfigError(
                f"reports 의 {_ordinal(i)} 항목은 매핑 또는 경로 문자열이어야 합니다 "
                f"— 현재 {type(item).__name__}"
            )
        unknown = set(item) - _REPORT_KEYS
        if unknown:
            raise ConfigError(
                f"reports 의 {_ordinal(i)} 항목에 알 수 없는 키 {sorted(unknown)} "
                f"— 허용: {sorted(_REPORT_KEYS)}"
            )
        path = item.get("path")
        if not path or not isinstance(path, str):
            raise ConfigError(f"reports 의 {_ordinal(i)} 항목에 path 문자열이 필요합니다")
        label = item.get("label") or ""
        if label is not None and not isinstance(label, str):
            raise ConfigError(f"reports 의 {_ordinal(i)} 항목 label 은 문자열이어야 합니다")
        out.append(ReportEntry(path=path, label=label))
    return out


def _parse_options(raw) -> Options:
    node = _require_mapping(raw, "options")
    unknown = set(node) - set(_OPTION_DEFAULTS)
    if unknown:
        raise ConfigError(
            f"options 에 알 수 없는 키 {sorted(unknown)} — 허용: {sorted(_OPTION_DEFAULTS)}"
        )
    merged = dict(_OPTION_DEFAULTS)
    merged.update(node)

    for key in ("auto_match_identical", "name_normalize", "trust_gate"):
        if not isinstance(merged[key], bool):
            raise ConfigError(f"options.{key} 는 true/false 여야 합니다 — 현재 {merged[key]!r}")
    for key, allowed in (
        ("unmatched", UNMATCHED_MODES),
        ("resample", RESAMPLE_MODES),
        ("unit_policy", UNIT_POLICIES),
    ):
        if merged[key] not in allowed:
            raise ConfigError(
                f"options.{key} 는 {list(allowed)} 중 하나여야 합니다 — 현재 {merged[key]!r}"
            )
    return Options(**merged)


def _parse_parts(raw, n_rev: int) -> dict:
    node = _require_mapping(raw, "parts")
    out = {}
    for canonical, value in node.items():
        if not isinstance(canonical, str) or not canonical.strip():
            raise ConfigError(f"parts 의 canonical 이름이 비어 있습니다 — {canonical!r}")
        if isinstance(value, str):
            names = [v.strip() for v in value.split(",")]
        elif isinstance(value, list):
            names = [("" if v is None else str(v).strip()) for v in value]
        elif value is None:
            raise ConfigError(
                f"parts['{canonical}'] 값이 비었습니다 — 리비전 {n_rev}개 순서대로 "
                f"콤마 구분 이름이 필요합니다 (없으면 ~)"
            )
        else:
            raise ConfigError(
                f"parts['{canonical}'] 는 콤마 구분 문자열 또는 목록이어야 합니다 "
                f"— 현재 {type(value).__name__}"
            )
        if len(names) != n_rev:
            raise ConfigError(
                f"parts['{canonical}'] 의 이름 개수가 {len(names)}개인데 reports 는 "
                f"{n_rev}개입니다 — 리비전 순서대로 {n_rev}개를 주십시오 "
                f"(그 리비전에 없으면 ~)"
            )
        out[canonical] = [None if (nm in ("", "~", "-")) else nm for nm in names]
    return out


def parse_config(raw: dict, source_path: str = "") -> FederateConfig:
    """이미 로드된 dict 를 검증해 FederateConfig 로."""
    node = _require_mapping(raw, "federate.yaml 최상위")
    if not node:
        raise ConfigError("federate.yaml 이 비어 있습니다")
    unknown = set(node) - _TOP_KEYS
    if unknown:
        raise ConfigError(
            f"최상위에 알 수 없는 키 {sorted(unknown)} — 허용: {sorted(_TOP_KEYS)}"
        )

    kind = node.get("kind", "auto")
    if kind not in KINDS:
        raise ConfigError(f"kind 는 {list(KINDS)} 중 하나여야 합니다 — 현재 {kind!r}")

    reports = _parse_reports(node.get("reports"))
    n = len(reports)

    baseline = node.get("baseline", 1)
    if isinstance(baseline, bool) or not isinstance(baseline, int):
        raise ConfigError(f"baseline 은 1-based 정수여야 합니다 — 현재 {baseline!r}")
    if not (1 <= baseline <= n):
        raise ConfigError(
            f"baseline 은 1..{n} 범위여야 합니다 (reports 가 {n}개) — 현재 {baseline}"
        )

    output = node.get("output", "federate_report.html")
    if not isinstance(output, str) or not output.strip():
        raise ConfigError(f"output 은 파일 경로 문자열이어야 합니다 — 현재 {output!r}")

    options = _parse_options(node.get("options"))
    parts = _parse_parts(node.get("parts"), n)

    return FederateConfig(
        kind=kind,
        baseline=baseline,
        output=output,
        reports=reports,
        options=options,
        parts=parts,
        source_path=source_path,
    )


def load_config(path: str) -> FederateConfig:
    """federate.yaml 파일을 읽어 검증까지."""
    if not os.path.isfile(path):
        raise ConfigError(f"설정 파일을 찾을 수 없습니다 — {path}")
    with open(path, "r", encoding="utf-8") as fh:
        try:
            raw = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise ConfigError(f"YAML 문법 오류 — {path}\n{exc}") from exc

    cfg = parse_config(raw, source_path=path)

    base_dir = os.path.dirname(os.path.abspath(path))
    for i, rep in enumerate(cfg.reports):
        if not os.path.isabs(rep.path):
            rep.path = os.path.normpath(os.path.join(base_dir, rep.path))
        if not os.path.isfile(rep.path):
            raise ConfigError(
                f"reports 의 {_ordinal(i)} sidecar 파일이 없습니다 — {rep.path}"
            )
        if not rep.label:
            rep.label = _fallback_label(rep.path)
    if not os.path.isabs(cfg.output):
        cfg.output = os.path.normpath(os.path.join(base_dir, cfg.output))
    return cfg


def _fallback_label(path: str) -> str:
    """label 미지정 시 디렉터리명 fallback."""
    d = os.path.basename(os.path.dirname(os.path.abspath(path)))
    return d or os.path.basename(path)
