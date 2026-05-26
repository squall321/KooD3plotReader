"""JSON serialization of ImpactReport."""
from __future__ import annotations
import dataclasses
import json
from enum import Enum
from pathlib import Path

from ..models import ImpactReport


class ImpactReportEncoder(json.JSONEncoder):
    """Encoder that handles dataclasses, Enums, and Paths."""

    def default(self, obj):  # noqa: D401 - inherited
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, tuple):
            return list(obj)
        return super().default(obj)


def save_json(report: ImpactReport, path: str) -> None:
    """Serialize ``report`` to ``path`` as JSON.

    Includes scalar peaks for every PairResult plus high-level metadata.
    """
    summary = {
        "project_name": report.project_name,
        "test_dir": report.test_dir,
        "impactor": dataclasses.asdict(report.impactor),
        "generation_mode": report.generation_mode,
        "boundary_distance": report.boundary_distance,
        "offset_distance": report.offset_distance,
        "faces": [dataclasses.asdict(f) for f in report.faces],
        "positions_by_face": {
            face: [
                {
                    "pos_id": p.pos_id, "face": p.face,
                    "x": p.x, "y": p.y, "run_dir": str(p.run_dir),
                }
                for p in positions
            ]
            for face, positions in report.positions_by_face.items()
        },
        "parts": [dataclasses.asdict(p) for p in report.parts],
        "results": [
            {
                "face": r.face,
                "pos_id": r.position.pos_id,
                "x": r.position.x, "y": r.position.y,
                "part_id": r.part_id,
                "peak_g": round(r.peak_g, 2),
                "peak_stress": round(r.peak_stress, 3),
                "peak_strain": round(r.peak_strain, 6),
                "peak_disp": round(r.peak_disp, 4),
            }
            for r in report.results
        ],
        "findings": [
            {
                "severity": f.severity.value,
                "title": f.title,
                "detail": f.detail,
                "recommendation": f.recommendation,
            }
            for f in report.findings
        ],
        "sim_params": report.sim_params,
        "doe_config": report.doe_config,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, cls=ImpactReportEncoder, ensure_ascii=False, indent=2)
