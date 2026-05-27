"""Smoke tests for the synthetic dataset produced by ``generate_sample.py``.

Generates a fresh dataset into a temporary directory and verifies that:
  * default smartphone-scope DOE produces 50 runs (F1×25 + F2×25)
  * only F1_back and F2_front face directories exist
  * each ``analysis_result.json`` has 12 parts and 21 timesteps
  * glstat / matsum / rcforc CSVs are valid with the expected columns
  * ``--faces F1,F2,F5`` correctly switches to 3 face dirs
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

# Default smartphone scope: F1 Back (5x5=25) + F2 Front (5x5=25) = 50 runs.
EXPECTED_DEFAULT_TOTAL = 25 + 25
EXPECTED_DEFAULT_FACES = ["F1_back", "F2_front"]


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
    for f in EXPECTED_DEFAULT_FACES:
        assert (dataset / f).is_dir(), f"missing face dir {f}"
        assert (dataset / f / "face_config.json").exists()
    # Non-default faces must not exist in default run.
    for f in ("F3_right", "F4_left", "F5_top", "F6_bottom"):
        assert not (dataset / f).exists(), f"unexpected face dir {f}"


def test_manifest_has_default_50_runs(dataset: Path):
    manifest = json.loads((dataset / "manifest.json").read_text())
    assert manifest["total_runs"] == EXPECTED_DEFAULT_TOTAL
    assert len(manifest["runs"]) == EXPECTED_DEFAULT_TOTAL


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


def test_face_choice_cli(tmp_path: Path):
    """`--faces F1,F2,F5` should produce exactly 3 face directories."""
    out = tmp_path / "ds_3faces"
    subprocess.run(
        [sys.executable, str(GEN_SCRIPT), "--output", str(out),
         "--seed", "42", "--faces", "F1,F2,F5"],
        check=True,
    )
    expected = {"F1_back", "F2_front", "F5_top"}
    actual = {p.name for p in out.iterdir() if p.is_dir()}
    assert actual == expected, f"face dirs mismatch: {actual} != {expected}"
    # 5x5 + 5x5 + 5x3 = 65 runs
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["total_runs"] == 25 + 25 + 15
