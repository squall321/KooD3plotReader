"""Basic unit tests for koo_impact_report.models.

Sibling agent owns models.py; we skip gracefully if it has not yet landed.
"""
from __future__ import annotations

import math

import pytest

try:
    from koo_impact_report.models import (
        FaceOrientation,
        ImpactorSpec,
        ImpactReport,
    )
except ImportError as exc:  # pragma: no cover — module not yet available
    pytest.skip(f"koo_impact_report.models not importable: {exc}",
                allow_module_level=True)


G_MM_S2 = 9810.0


def test_impactor_velocity_matches_free_fall():
    """v0 = sqrt(2 g h) for an object dropped from `height` mm."""
    spec = ImpactorSpec(type="Sphere", radius=5.0, height=100.0, density=7850.0)
    expected = math.sqrt(2.0 * G_MM_S2 * 100.0)   # mm/s
    assert spec.velocity == pytest.approx(expected, rel=1e-6)


def test_impactor_kinetic_energy_sphere():
    """KE = 0.5 m v² for the 5mm steel sphere dropped from 100mm.

    For r=5mm steel sphere:
      mass ≈ 4.11 g, v ≈ 1.4 m/s, KE ≈ 4 mJ.
    We accept a wide tolerance because the models module is free to choose any
    consistent unit convention as long as the formula is self-consistent.
    """
    spec = ImpactorSpec(type="Sphere", radius=5.0, height=100.0, density=7850.0)
    ke = spec.kinetic_energy
    # KE must be positive and finite
    assert ke > 0.0
    assert math.isfinite(ke)
    # KE = 0.5 m v² should hold regardless of unit choice
    expected = 0.5 * spec.mass * spec.velocity ** 2
    assert ke == pytest.approx(expected, rel=1e-6)


def test_impactor_zero_height():
    """Height=0 should give v=0 and KE=0."""
    spec = ImpactorSpec(type="Sphere", radius=5.0, height=0.0)
    assert spec.velocity == 0.0
    assert spec.kinetic_energy == 0.0


def test_face_orientation_creation_six_faces():
    """All six cuboid-6 faces can be created with the spec'd angles."""
    cases = [
        ("F1", "Back",    0,    0, 0),
        ("F2", "Front",   180,  0, 0),
        ("F3", "Right",   0,   -90, 0),
        ("F4", "Left",    0,    90, 0),
        ("F5", "Top",     90,   0, 0),
        ("F6", "Bottom", -90,   0, 0),
    ]
    for code, name, roll, pitch, yaw in cases:
        face = FaceOrientation(code=code, name=name, roll=roll, pitch=pitch, yaw=yaw)
        assert face.code == code
        assert face.name == name
        assert face.roll == roll
        assert face.pitch == pitch
        assert face.yaw == yaw


def test_impact_report_default_empty():
    """ImpactReport can be instantiated with no args."""
    rep = ImpactReport()
    assert rep.project_name == ""
    assert rep.faces == []
    assert rep.results == []
    assert isinstance(rep.impactor, ImpactorSpec)
