# koo_federate_report — N개 리비전 sidecar 를 하나의 비교 보고서로 접는 독립 모듈
"""federate 파이프라인 진입점.

    cfg = load_config('federate.yaml')
    comparison = federate(cfg)          # 순수 dict (HTML 이 소비하는 payload 계약)
"""
from __future__ import annotations

from . import adapters, compare, matching, resample
from .config import ConfigError, FederateConfig, load_config, parse_config
from .models import FederatedSet, RevisionBundle

__version__ = "0.1.0"

__all__ = [
    "federate",
    "load_config",
    "parse_config",
    "FederateConfig",
    "ConfigError",
    "FederatedSet",
    "RevisionBundle",
    "__version__",
]


def load_bundles(cfg: FederateConfig) -> FederatedSet:
    """YAML 의 reports 를 순서대로 RevisionBundle 로 로드하고 kind 혼합을 막는다."""
    bundles = []
    for i, rep in enumerate(cfg.reports):
        b = adapters.load_bundle(rep.path, label=rep.label, kind=cfg.kind)
        if not b.label:
            b.label = rep.label or f"rev{i + 1}"
        bundles.append(b)

    kinds = {b.kind for b in bundles}
    if len(kinds) > 1:
        detail = ", ".join(f"{b.label}={b.kind}" for b in bundles)
        raise adapters.AdapterError(
            f"sphere 와 impact 는 물리적으로 다른 시험이라 비교할 수 없습니다 — {detail}"
        )
    return FederatedSet(kind=bundles[0].kind, baseline_idx=cfg.baseline_idx, revisions=bundles)


def federate(cfg: FederateConfig, metric: str = "g") -> dict:
    """설정 → 비교 payload dict."""
    fset = load_bundles(cfg)
    match = matching.build_matching(fset.revisions, cfg.parts, cfg.options)
    aligned = resample.align(
        fset.revisions, fset.baseline_idx, fset.kind, cfg.options.resample
    )
    return compare.build_comparison(
        fset.revisions,
        fset.baseline_idx,
        fset.kind,
        match,
        aligned,
        cfg.options,
        metric=metric,
    )
