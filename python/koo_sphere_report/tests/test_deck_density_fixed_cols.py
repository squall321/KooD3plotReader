# 붙은 LS-DYNA 고정폭 *MAT 카드에서 밀도를 제대로 읽는지 — 단위계 판정의 입력이다
"""`_deck_density` 가 10칸 고정폭 카드를 읽는가.

배경. LS-PrePost 로 다시 저장한 덱은 10칸 필드 사이에 공백이 없다.
`         17.8500e-09210000.000      0.30` 에서 MID `1` 과 RO `7.85e-09` 가
`17.8500e-09210000.000` 한 덩어리가 되어, 공백으로만 나누면 두 번째 토큰이
**포아송비 0.30** 이 된다. 그 값으로는 단위계가 판정되지 않아
(`_detect_unit_system(0.3) → id=''`) 보고서가 미검출로 떨어진다.

규칙은 deep 의 `core/keyword_parser.py` `_read_fields` 와 같아야 한다 —
같은 덱을 두 도구가 다르게 읽으면 안 된다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from koo_sphere_report.loader import _deck_density   # noqa: E402


def _deck(tmp_path: Path, body: str) -> Path:
    (tmp_path / "DropSet.k").write_text(body, encoding="utf-8")
    return tmp_path


def test_fixed_columns_glued(tmp_path):
    """칸 사이 공백이 없는 고정폭 카드 — 붙어도 RO 를 읽는다."""
    d = _deck(tmp_path, "*MAT_ELASTIC\n"
                        "         17.8500e-09210000.000      0.30\n")
    assert _deck_density(d) == 7.85e-09


def test_fixed_columns_spaced(tmp_path):
    """현행 캠페인 덱(pyKooCAE) 꼴 — 종전과 같아야 한다."""
    d = _deck(tmp_path, "*MAT_ELASTIC\n"
                        "        23 2.330e-09 1.660e+05 3.300e-01\n")
    assert _deck_density(d) == 2.33e-09


def test_comma_free_format(tmp_path):
    """쉼표 자유형."""
    d = _deck(tmp_path, "*MAT_ELASTIC\n1,7.85e-9,210000.0,0.30\n")
    assert _deck_density(d) == 7.85e-09


def test_title_line_skipped(tmp_path):
    """`_TITLE` 의 제목 줄은 건너뛰고 다음 줄을 읽는다."""
    d = _deck(tmp_path, "*MAT_ELASTIC_TITLE\n"
                        "Steel AISI 1018\n"
                        "         17.8500e-09210000.000      0.30\n")
    assert _deck_density(d) == 7.85e-09


def test_median_of_many(tmp_path):
    """여러 *MAT 이면 중앙값."""
    d = _deck(tmp_path, "*MAT_ELASTIC\n         17.8500e-09210000.000      0.30\n"
                        "*MAT_ELASTIC\n         22.7000e-09 70000.000      0.33\n"
                        "*MAT_ELASTIC\n         31.2000e-09  3000.000      0.40\n")
    assert _deck_density(d) == 2.70e-09
