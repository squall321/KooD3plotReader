# LS-DYNA 키워드 카드 한 줄을 필드로 나누는 공용 함수(card_fields)의 규칙을 보는 시험
"""규칙 — 쉼표가 있으면 자유형(쉼표로 나눈다), 없으면 LS-DYNA 고정폭 10칸(빈 칸은 "" 로 자리를 지킨다),
칸 안에 공백 · 탭이 든 줄(칸에 맞지 않게 나눈 꼴)은 공백으로 나눈다. LS-DYNA 는 80칸(필드 8개) 뒤를 읽지 않는다 —
그 뒤에 붙은 글은 판별에도 쓰지 않는다. deep 키워드 파서 · 접촉 지도가 이 함수 하나를 쓴다.
"""
from koo_deep_report.core.contact_map import _card_fields
from koo_deep_report.core.keyword_fields import card_fields
from koo_deep_report.core.keyword_parser import _read_fields


def test_packed_fixed_fields():
    assert card_fields("         17.8500e-09210000.000      0.30") == ["1", "7.8500e-09", "210000.000", "0.30"]
    assert card_fields("         10.0000e+000.0000e+000.0000e+000.0000e+00      MECH         0") == \
        ["1", "0.0000e+00", "0.0000e+00", "0.0000e+00", "0.0000e+00", "MECH", "0"]


def test_blank_columns_keep_positions():
    assert card_fields("         2                   3") == ["2", "", "3"]
    assert _card_fields("         2                   3") == [2, None, 3]


def test_short_fixed_line():
    # 20칸이 안 되는 줄도 고정폭이다 — 공백으로 나누면 "2310" 한 덩어리가 된다
    assert card_fields("        2310") == ["23", "10"]


def test_comma_and_whitespace_forms():
    assert card_fields("1, 7.85e-9, 210000, 0.3") == ["1", "7.85e-9", "210000", "0.3"]
    assert card_fields("1 2 3 4") == ["1", "2", "3", "4"]
    assert card_fields("5\t6\t7") == ["5", "6", "7"]
    assert card_fields("") == [] and card_fields("   \n") == []


def test_text_past_column_80_is_ignored():
    line = "".join(f"{i:10d}" for i in range(1, 9)) + "   trailing note with spaces"
    assert card_fields(line) == [str(i) for i in range(1, 9)]


def test_wrappers_keep_their_shapes():
    assert _read_fields("         17.8500e-09210000.000      0.30", 5) == ["1", "7.8500e-09", "210000.000", "0.30", ""]
    assert _read_fields("1, 2", 3) == ["1", "2", ""]
    assert _card_fields("        11        12        13        13     0.000") == [11, 12, 13, 13, 0]
