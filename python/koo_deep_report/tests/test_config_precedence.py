# --config 설정 파일과 CLI 인수가 겹칠 때 CLI 가 이기는지(도움말 문구 포함) 보는 시험
"""koo_deep_report --config 우선순위 시험.

설정 파일은 CLI 가 주지 않은 값만 채운다(_apply_config_to_args). 그런데
  - 도움말은 「CLI 인수보다 우선」 이라고 반대로 적었고,
  - render_jobs: 가 없는 설정 파일은 「렌더 없음」 을 켜서, CLI 로 준 --section-view 를 말없이 껐다
    (단면 영상을 달라고 했는데 아무 영상도 나오지 않는다).
"""
import argparse

from koo_deep_report import __main__ as M


def _parser():
    p = argparse.ArgumentParser()
    M._add_single_args(p)
    return p


def _args(argv):
    return _parser().parse_args(argv)


def test_cli_section_view_survives_config_without_render_jobs(tmp_path):
    cfg = tmp_path / "a.yaml"
    cfg.write_text("render_threads: 2\n")              # render_jobs: 가 없는 설정 파일
    a = _args(["x", "--config", str(cfg), "--section-view"])
    M._apply_config_to_args(a)
    assert a.section_view is True
    assert not a.no_render, "CLI 로 준 --section-view 를 설정 파일의 「렌더 없음」 이 끄면 안 된다"


def test_config_without_render_jobs_still_turns_render_off(tmp_path):
    cfg = tmp_path / "a.yaml"
    cfg.write_text("render_threads: 2\n")
    a = _args(["x", "--config", str(cfg)])
    M._apply_config_to_args(a)
    assert a.no_render, "CLI 가 렌더를 달라고 하지 않으면 종전대로 설정 파일을 따른다"


def test_cli_value_beats_config(tmp_path):
    cfg = tmp_path / "a.yaml"
    cfg.write_text("render_threads: 2\n")
    a = _args(["x", "--config", str(cfg), "--render-threads", "3"])
    M._apply_config_to_args(a)
    assert a.render_threads == 3


def test_config_help_says_cli_wins():
    h = next(act.help for act in _parser()._actions if "--config" in act.option_strings)
    assert "CLI 인수보다 우선" not in h
    assert "CLI 인수가 우선" in h
