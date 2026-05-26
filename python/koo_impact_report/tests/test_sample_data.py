"""Smoke tests for the synthetic dataset produced by ``generate_sample.py``.

Generates a fresh dataset into a temporary directory and verifies that:
  * all 110 runs exist (sum of face grids: 5×5×2 + 3×5×2 + 5×3×2)
  * each ``analysis_result.json`` has 12 parts and 21 timesteps
  * glstat / matsum / rcforc CSVs are valid with the expected columns
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
GEN_SCRIPT = HERE / "generate_sample.py"

EXPECTED_TOTAL = 25 + 25 + 15 + 15 + 15 + 15   # 110
EXPECTED_FACES = ["F1_back", "F2_front", "F3_right", "F4_left", "F5_top", "F6_bottom"]


@pytest.fixture(scope="module")
def dataset(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("sample_test") / "ds"
    subprocess.run(
        [sys.executable, str(GEN_SCRIPT), "--output", str(out), "--seed", "42"],
        check=True,
    )
    return out


def test_top_level_files_present(dataset: Path):
    for fname in ("scenario.json", "scenario_cylinder.json",
                   "manifest.json", "device_layout.json", "impactor_spec.json"):
        assert (dataset / fname).exists(), f"missing {fname}"


def test_all_face_dirs_present(dataset: Path):
    for f in EXPECTED_FACES:
        assert (dataset / f).is_dir(), f"missing face dir {f}"
        assert (dataset / f / "face_config.json").exists()


def test_manifest_has_110_runs(dataset: Path):
    manifest = json.loads((dataset / "manifest.json").read_text())
    assert manifest["total_runs"] == EXPECTED_TOTAL
    assert len(manifest["runs"]) == EXPECTED_TOTAL


def test_each_run_has_12_parts_and_21_states(dataset: Path):
    manifest = json.loads((dataset / "manifest.json").read_text())
    for entry in manifest["runs"]:
        ar = json.loads((dataset / entry["analysis_json"]).read_text())
        assert ar["num_states"] == 21
        assert len(ar["parts"]) == 12
        # spot-check shape of stress_ts
        any_part = next(iter(ar["parts"].values()))
        assert len(any_part["stress_ts"]["t"]) == 21
        assert len(any_part["stress_ts"]["max"]) == 21


def test_csv_columns(dataset: Path):
    manifest = json.loads((dataset / "manifest.json").read_text())
    entry = manifest["runs"][0]
    expected = {
        "glstat_csv": ["time", "kinetic_energy", "internal_energy",
                        "sliding_energy", "hourglass_energy", "total_energy"],
        "matsum_csv": ["time", "part_id", "internal_energy", "kinetic_energy"],
        "rcforc_csv": ["time", "contact_id", "slave_pid", "master_pid",
                        "force_x", "force_y", "force_z"],
    }
    for key, cols in expected.items():
        with (dataset / entry[key]).open() as fh:
            reader = csv.reader(fh)
            header = next(reader)
            assert header == cols, f"{key}: header {header} != {cols}"
            # at least one data row
            assert next(reader, None) is not None
