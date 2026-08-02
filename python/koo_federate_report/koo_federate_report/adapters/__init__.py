# sidecar(JSON) → RevisionBundle 어댑터 진입점 및 kind 자동 판별
"""sidecar 스키마만이 계약이다 — koo_impact_report / koo_sphere_report 를 import 하지 않는다."""
from __future__ import annotations

import json
import os

from . import impact as _impact
from . import sphere as _sphere


class AdapterError(Exception):
    """sidecar 를 RevisionBundle 로 접을 수 없음."""


def load_raw(path: str) -> dict:
    if not os.path.isfile(path):
        raise AdapterError(f"sidecar 파일이 없습니다 — {path}")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"JSON 파싱 실패 — {path}\n{exc}") from exc
    if not isinstance(raw, dict):
        raise AdapterError(f"sidecar 최상위가 객체가 아닙니다 — {path}")
    return raw


def detect_kind(raw: dict, path: str = "") -> str:
    """sidecar 내용으로 impact/sphere 판별."""
    gen = str(raw.get("generated_by") or "")
    if gen == "koo_impact_report":
        return "impact"
    if gen == "koo_sphere_report":
        return "sphere"
    payload = raw.get("payload")
    if isinstance(payload, dict) and "positions" in payload and "results" in payload:
        return "impact"
    if "results_summary" in raw:
        return "sphere"
    raise AdapterError(
        f"sidecar 종류를 판별할 수 없습니다 — {path}\n"
        "impact 는 payload.positions/results, sphere 는 results_summary 가 필요합니다"
    )


def load_bundle(path: str, label: str = "", kind: str = "auto"):
    """sidecar 1개 → RevisionBundle."""
    raw = load_raw(path)
    detected = detect_kind(raw, path)
    if kind not in ("auto", detected):
        raise AdapterError(
            f"kind: {kind} 로 지정했지만 {path} 는 {detected} sidecar 입니다"
        )
    if detected == "impact":
        return _impact.to_bundle(raw, path=path, label=label)
    return _sphere.to_bundle(raw, path=path, label=label)
