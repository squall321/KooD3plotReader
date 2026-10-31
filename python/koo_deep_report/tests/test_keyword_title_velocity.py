# 키워드 파서가 *MAT_…_TITLE 제목과 첫 *INITIAL_VELOCITY 를 읽는지 — 온톨로지 파트 재질·충돌 속도가 쓴다
from koo_deep_report.core.keyword_parser import parse_keyword_file

_DECK = """*KEYWORD
*MAT_ELASTIC_TITLE
RigidWall
$#     mid        ro         e        pr
        28  7.85E-09  210000.0       0.3
*MAT_ELASTIC
        25  2.70E-09   70000.0      0.33
*PART
Front\\\\Metal
         1         1        25
*INITIAL_VELOCITY
         1         0         0         0         0
-3.278e+03 2.423e+03 3.579e+03 0.000e+00 0.000e+00 0.000e+00
*INITIAL_VELOCITY
         2         0         0         0         0
       1.0       2.0       3.0
*END
"""


def test_title_and_first_initial_velocity(tmp_path):
    p = tmp_path / "d.k"
    p.write_text(_DECK)
    kw = parse_keyword_file(p)
    assert kw.materials[28].title == "RigidWall" and kw.materials[28].mat_type == "ELASTIC"
    assert kw.materials[25].title == ""                      # _TITLE 이 아니면 제목 없음
    assert kw.materials[28].density == 7.85e-09              # 제목 줄을 카드 1 로 읽지 않는다
    assert kw.initial_velocity == (-3278.0, 2423.0, 3579.0)  # 첫 카드만


def test_no_initial_velocity_is_none(tmp_path):
    p = tmp_path / "d.k"
    p.write_text("*KEYWORD\n*END\n")
    assert parse_keyword_file(p).initial_velocity is None
