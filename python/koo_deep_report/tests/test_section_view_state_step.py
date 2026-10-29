# 단면 영상 프레임 보폭(state_step)이 YAML 로 엔진까지 가는지 검증하는 시험
"""DynaForge 개선 제안 P-3 (2026-10-28).

엔진(C++)은 render_jobs·part_section_renders 의 state_step 을 LS-PrePost
`anim incr N` 으로 바꾼다(465 상태 → 보폭 5 → 93 프레임, SIF 안 실렌더로 확인).
기본 1 일 때는 YAML 이 예전과 같아야 한다 — 옛 엔진에 모르는 키를 보내지 않는다.
"""
from koo_deep_report.core import d3plot_reader as R
from koo_deep_report.render.job_builder import (
    RenderConfig,
    SectionViewRenderConfig,
    build_lsprepost_section_jobs,
    build_part_section_render_yaml_entries,
)


def _sv(step):
    return SectionViewRenderConfig(enabled=True, backend="lsprepost", per_part_render=True,
                                   axes=["z"], state_step=step)


def test_default_step_leaves_yaml_unchanged(tmp_path):
    jobs = build_lsprepost_section_jobs(str(tmp_path), _sv(1), [7])
    assert jobs and all("state_step" not in j for j in jobs)
    body = build_part_section_render_yaml_entries(str(tmp_path), _sv(1), [7])[0][1]
    assert "state_step" not in body


def test_step_reaches_both_job_kinds(tmp_path):
    jobs = build_lsprepost_section_jobs(str(tmp_path), _sv(5), [7])
    assert jobs and all(j["state_step"] == 5 for j in jobs)
    body = build_part_section_render_yaml_entries(str(tmp_path), _sv(5), [7])[0][1]
    assert "  state_step: 5" in body.splitlines()


def test_step_in_built_yaml(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "_resolve_lsprepost", lambda rc, install_dir=None: "/opt/lsprepost")
    y = R._build_yaml(tmp_path / "d3plot", tmp_path / "out", RenderConfig(enabled=True), [7],
                      threads=0, section_view_config=_sv(5))
    assert "state_step: 5" in y
