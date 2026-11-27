# LS-DYNA 키워드 카드 한 줄을 필드로 나누는 공용 함수 — 쉼표 자유형 · 고정폭 10칸 · 공백 구분을 한 규칙으로
"""LS-DYNA 카드 필드 읽기.

규칙(LS-DYNA 와 같다)
  1. 쉼표가 있으면 자유형 — 쉼표로 나눈다.
  2. 없으면 고정폭 — 10칸씩 자른다. 칸 사이에 공백이 없어도 된다(LS-PrePost 는 `0.0000e+000.0000e+00` 처럼 붙여 쓴다).
     빈 칸은 "" 로 자리를 지킨다(카드의 몇 번째 필드인지가 뜻이다).
  3. 칸 안에 공백 · 탭이 든 줄은 칸에 맞지 않게 나눈 꼴이다 — 공백으로 나눈다.
LS-DYNA 는 80칸(필드 8개) 뒤를 읽지 않는다. 그 뒤에 붙은 글은 판별에도 쓰지 않는다.
요소 카드처럼 8칸 카드는 width 를 바꿔 부른다. 이 함수를 deep 키워드 파서 · 접촉 지도가 쓰고,
C++ 세트 파서(KeywordSetParser)와 sphere 밀도 읽기도 같은 규칙을 따른다.
"""
from __future__ import annotations


def card_fields(line: str, width: int = 10, max_fields: int = 8) -> list[str]:
    """카드 한 줄의 필드 문자열. 빈 줄이면 []."""
    raw = line.rstrip("\r\n").rstrip()
    stripped = raw.strip()
    if not stripped:
        return []
    if "," in stripped:
        return [p.strip() for p in stripped.split(",")]
    head = raw[:width * max_fields]
    cols = [head[i:i + width].strip() for i in range(0, len(head), width)]
    if not any(" " in c or "\t" in c for c in cols):
        while cols and not cols[-1]:
            cols.pop()
        return cols
    return stripped.split()
