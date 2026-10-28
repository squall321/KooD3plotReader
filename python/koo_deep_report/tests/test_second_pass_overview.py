# 파트별 2차 패스가 전체 모델 개관 영상을 다시 만들지 않는지 검증하는 시험
"""DynaForge 개선 제안 P-1 (2026-10-28).

파트별 2차 패스(render_only)가 1차 패스의 전체 모델 개관 영상을 또 만들어
각도당 LS-PrePost 세션 3개가 헛돌았다(단면 영상 경로·옛 렌더 경로 둘 다).
"""
from koo_deep_report.core import d3plot_reader as R
from koo_deep_report.render.job_builder import (
    RenderConfig,
    SectionViewRenderConfig,
    build_render_jobs,
)


def _sv_yaml(tmp_path, overview: bool) -> str:
    sv = SectionViewRenderConfig(enabled=True, backend="lsprepost", per_part_render=True,
                                 axes=["x", "y", "z"])
    return R._build_yaml(tmp_path / "d3plot", tmp_path / "out", RenderConfig(enabled=True),
                         [7, 8], threads=0, render_only=True,
                         section_view_config=sv, overview=overview)


def test_second_pass_section_yaml_has_no_overview(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "_resolve_lsprepost", lambda rc, install_dir=None: "/opt/lsprepost")
    first = _sv_yaml(tmp_path, overview=True)
    second = _sv_yaml(tmp_path, overview=False)
    assert "render_jobs:" in first
    assert "render_jobs:" not in second
    assert "part_section_renders:" in second, "파트별 단면은 그대로 있어야 한다"


def test_legacy_per_part_jobs_without_overview(tmp_path):
    rc = RenderConfig(enabled=True, per_part_render=True, section_axes=["x", "z"])
    with_ov = build_render_jobs(str(tmp_path / "d3plot"), str(tmp_path), rc, [7])
    without = build_render_jobs(str(tmp_path / "d3plot"), str(tmp_path), rc, [7],
                                include_overview=False)
    assert [j["name"] for j in with_ov] == ["overview_x", "overview_z", "part_7_x", "part_7_z"]
    assert [j["name"] for j in without] == ["part_7_x", "part_7_z"]
