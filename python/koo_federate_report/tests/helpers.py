# 테스트용 합성 RevisionBundle / sidecar 픽스처 생성기
from __future__ import annotations

from koo_federate_report.models import Cell, RevisionBundle, Trust


def make_impact_bundle(label, cell_specs, parts, part_values=None, unit_labels=None,
                       schema_version=1, findings=None, kpi=None):
    """cell_specs: [(key, x, y, face, g, trust_ok, behavior), ...]"""
    cells = []
    for key, x, y, face, g, ok, behavior in cell_specs:
        cells.append(
            Cell(
                key=key,
                label=key,
                category=face,
                x=x,
                y=y,
                metrics={"g": g, "s": None if g is None else g / 10.0, "e": None, "d": None},
                trust=Trust(ok, "ok" if ok else "gated by fixture"),
                behavior=behavior,
                energy={"ke_retention": 1.0, "diss_pct": None, "max_penetration_depth": None},
            )
        )
    return RevisionBundle(
        label=label,
        kind="impact",
        path=f"/synthetic/{label}.json",
        schema_version=schema_version,
        meta={"project": label},
        unit_labels=unit_labels or {"acc": "mm/s²", "stress": "MPa", "disp": "mm"},
        parts=dict(parts),
        positions=[{"pos_id": c.key, "face": c.category, "x": c.x, "y": c.y} for c in cells],
        cells=cells,
        part_cells=dict(part_values or {}),
        kpi=kpi or {"diss_pct": 10.0},
        trust={"n_cells": len(cells), "n_gated": sum(1 for c in cells if not c.trust.ok)},
        findings=findings or [],
        provenance={"tool": "synthetic", "tool_version": "0"},
    )


def make_sphere_bundle(label, angle_specs, parts, unit_labels=None):
    """angle_specs: [(name, roll, pitch, category, g), ...]"""
    cells = []
    part_cells = {}
    for name, roll, pitch, cat, g in angle_specs:
        cells.append(
            Cell(
                key=name,
                label=name,
                category=cat,
                roll=roll,
                pitch=pitch,
                yaw=0.0,
                metrics={"g": g, "s": g / 10.0, "e": None, "d": None},
                trust=Trust(True, "no gate"),
            )
        )
        for pname in parts.values():
            part_cells[(name, pname)] = {"g": g / 2.0, "s": g / 20.0, "e": None, "d": None}
    return RevisionBundle(
        label=label,
        kind="sphere",
        path=f"/synthetic/{label}.json",
        schema_version=None,
        meta={"project": label},
        unit_labels=unit_labels or {},
        parts=dict(parts),
        angles=[{"name": c.key, "roll": c.roll, "pitch": c.pitch, "yaw": 0.0} for c in cells],
        cells=cells,
        part_cells=part_cells,
        kpi={"n_cells": len(cells)},
        trust={"n_cells": len(cells), "n_gated": 0},
    )


def minimal_impact_sidecar():
    """어댑터 검증용 최소 impact_payload.json 구조."""
    return {
        "schema_version": 1,
        "generated_by": "koo_impact_report",
        "payload": {
            "positions": [
                {"pos_id": "P1", "face": "F5", "x": -10.0, "y": 0.0},
                {"pos_id": "P2", "face": "F5", "x": 10.0, "y": 0.0},
            ],
            "results": [
                {"pos_id": "P1", "part_id": 1, "part_name": "Display\\Display",
                 "g": 100.0, "s": 10.0, "e": 1e-3, "d": 0.2},
                {"pos_id": "P1", "part_id": 2, "part_name": "PCB\\PCB",
                 "g": 80.0, "s": 8.0, "e": 8e-4, "d": 0.1},
                {"pos_id": "P2", "part_id": 1, "part_name": "Display\\Display",
                 "g": 200.0, "s": 20.0, "e": 2e-3, "d": 0.4},
                {"pos_id": "P2", "part_id": 2, "part_name": "PCB\\PCB",
                 "g": 160.0, "s": 16.0, "e": 1.6e-3, "d": 0.3},
            ],
            "parts": [
                {"id": 1, "name": "Display\\Display"},
                {"id": 2, "name": "PCB\\PCB"},
            ],
            "doe_analysis": {
                "position_metrics": {
                    "P1": {"peak_g_max": 100.0, "peak_stress_max": 10.0,
                           "peak_strain_max": 1e-3, "peak_disp_max": 0.2,
                           "worst_part_id_g": 1},
                    "P2": {"peak_g_max": 200.0, "peak_stress_max": 20.0,
                           "peak_strain_max": 2e-3, "peak_disp_max": 0.4,
                           "worst_part_id_g": 1},
                },
                "trajectory_summary": {
                    "P1": {"ke_retention": 1.0, "behavior_class": "no-contact",
                           "max_penetration_depth": 0.0},
                    "P2": {"ke_retention": 0.3, "behavior_class": "bounce",
                           "max_penetration_depth": 1.5},
                },
                "behavior_class_counts": {"no-contact": 1, "bounce": 1},
            },
            "solver_quality": {
                "per_position": {
                    "P1": {"pass_fail": "PASS", "summary": {"impact_visible": False,
                                                            "diss_pct": None}},
                    "P2": {"pass_fail": "PASS", "summary": {"impact_visible": True,
                                                            "diss_pct": 41.2}},
                },
                "summary": {"pass": 2, "fail": 0},
            },
            "kpi": {"worst_g": 200.0, "worst_s": 20.0, "n_positions": 2, "diss_pct": 41.2,
                    "crit_basis": "p95"},
            "unit_labels": {"acc": "mm/s²", "stress": "MPa", "disp": "mm"},
            "findings": [{"severity": "CRITICAL", "title": "접촉 미발생 1/2",
                          "detail": "d", "recommendation": "r"}],
            "faces": [{"code": "F5", "name": "Top"}],
            "meta": {
                "project": "SYN",
                "test_dir": "/synthetic",
                "sim_params": {"units": "ton-mm-s", "grid": {"nx": 2, "ny": 1}},
                "provenance": {"tool": "koo_impact_report", "tool_version": "0.1.0",
                               "generated_utc": "2026-08-02T00:00:00+00:00"},
            },
        },
    }


def minimal_sphere_sidecar():
    """어댑터 검증용 최소 sphere report.json 구조."""
    return {
        "project_name": "SYN_SPHERE",
        "test_dir": "/synthetic/sphere",
        "doe_strategy": "fibonacci",
        "total_runs": 2,
        "successful_runs": 2,
        "failed_runs": 0,
        "angular_spacing_deg": 30.0,
        "sphere_coverage": 0.5,
        "simulation_params": {"t_final": 0.001, "drop_height": 1500.0},
        "findings": [{"severity": "WARNING", "title": "코너 낙하 응력 집중",
                      "detail": "d", "recommendation": "r"}],
        "parts": {
            "1": {"part_name": "Display\\Display", "group": "Display"},
            "2": {"part_name": "PCB\\PCB", "group": "PCB"},
        },
        "results_summary": [
            {
                "run_folder": "run_0001",
                "angle": {"name": "F1_Back", "roll": 0.0, "pitch": 0.0, "yaw": 0.0,
                          "category": "face"},
                "num_states": 100,
                "parts": {
                    "1": {"peak_stress": 12.0, "peak_strain": 0.001, "peak_g": 900.0,
                          "peak_disp": 0.5},
                    "2": {"peak_stress": 8.0, "peak_strain": 0.0008, "peak_g": 700.0,
                          "peak_disp": 0.3},
                },
            },
            {
                "run_folder": "run_0002",
                "angle": {"name": "C1_Corner", "roll": 45.0, "pitch": 45.0, "yaw": 0.0,
                          "category": "corner"},
                "num_states": 100,
                "parts": {
                    "1": {"peak_stress": 30.0, "peak_strain": 0.003, "peak_g": 1500.0,
                          "peak_disp": 1.2},
                    "2": {"peak_stress": 25.0, "peak_strain": 0.002, "peak_g": 1300.0,
                          "peak_disp": 0.9},
                },
            },
        ],
    }
