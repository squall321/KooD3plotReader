# *PART 블록의 모든 파트와 *INCLUDE 파일까지 빠짐없이 읽는지 검증하는 시험
"""`koo_deep_report.core.keyword_parser` 의 *PART / *INCLUDE 시험.

LS-DYNA 의 *PART 는 다음 '*' 키워드 전까지 (제목, 데이터카드) 세트를
반복할 수 있다. 첫 세트만 읽으면 나머지 파트는 이름도 설계기준도 없이
사라지고, koo_impact_report 는 아예 해석 대상에서 뺀다. *PART_CONTACT·
*PART_COMPOSITE 같은 변형과 *INCLUDE 파일도 통째로 빠졌다.
"""
import sys
import tempfile
from pathlib import Path

from koo_deep_report.core.keyword_parser import parse_keyword_file

fails = []


def chk(name, got, want):
    ok = got == want
    if not ok:
        fails.append(f"{name}: got={got!r} want={want!r}")
    print(f"  {'OK ' if ok else 'NG '} {name}")


def chkb(name, cond):
    if not cond:
        fails.append(name)
    print(f"  {'OK ' if cond else 'NG '} {name}")


MAIN = """\
*KEYWORD
$# 한 블록에 파트 3개 — LS-DYNA 가 허용하는 형식이다
*PART
Housing
        10         1         5
Screen Glass
        11         1         5
Battery
        12         2         6
*PART_CONTACT
Bracket
        13         3         7
       0.1       0.1       0.0       0.0       0.0       0.0       0.0       0.0
*PART_COMPOSITE
FPCB
        14         2       1.0       0.0       0.0         0         0       0.0
         7       0.1       0.0         0         7       0.1       0.0         0
*PART_MOVE
        10       1.0       0.0       0.0
*INCLUDE
sub.k
*END
"""

SUB = """\
*KEYWORD
*PART
Cover
        20         4         8
Gasket
        21         4         9
*MAT_PIECEWISE_LINEAR_PLASTICITY
         8  7.85E-09    210000       0.3       300      1200       0.2       0.0
*END
"""

with tempfile.TemporaryDirectory() as td:
    (Path(td) / "sub.k").write_text(SUB, encoding="utf-8")
    main = Path(td) / "main.k"
    main.write_text(MAIN, encoding="utf-8")
    kw = parse_keyword_file(main)

pids = sorted(kw.parts.keys())

# ---------------------------------------------------------------------------
print("[1] 한 *PART 블록의 파트를 전부 읽는다")

chk("블록 안 3개 파트가 모두 남는다", [p for p in pids if p in (10, 11, 12)], [10, 11, 12])
chk("Part 10 이름", kw.parts[10].name if 10 in kw.parts else None, "Housing")
chk("Part 11 이름", kw.parts[11].name if 11 in kw.parts else None, "Screen Glass")
chk("Part 12 이름", kw.parts[12].name if 12 in kw.parts else None, "Battery")
chk("Part 12 MID", kw.parts[12].mid if 12 in kw.parts else None, 6)

print()

# ---------------------------------------------------------------------------
print("[2] *PART_ 변형도 읽는다")

chk("*PART_CONTACT 의 파트", kw.parts[13].name if 13 in kw.parts else None, "Bracket")
chk("*PART_CONTACT MID", kw.parts[13].mid if 13 in kw.parts else None, 7)
chk("*PART_COMPOSITE 의 파트", kw.parts[14].name if 14 in kw.parts else None, "FPCB")
# COMPOSITE 카드에는 MID 열이 없다 — 3번째 열(SHRF)을 MID 로 읽지 않는다.
chk("*PART_COMPOSITE 는 MID 를 만들어내지 않는다",
    kw.parts[14].mid if 14 in kw.parts else None, 0)
# *PART_MOVE 는 파트를 정의하지 않는다 — 데이터 줄을 이름으로 삼지 않는다.
chkb("*PART_MOVE 로 가짜 파트가 생기지 않는다",
     all(p.name.strip() != "" for p in kw.parts.values()))
chkb("읽지 않은 *PART_ 변형을 사유로 남긴다",
     any("PART_MOVE" in w for w in kw.warnings))

print()

# ---------------------------------------------------------------------------
print("[3] *INCLUDE 파일을 따라간다")

chk("include 안 파트 2개", [p for p in pids if p in (20, 21)], [20, 21])
chk("Part 20 이름", kw.parts[20].name if 20 in kw.parts else None, "Cover")
chk("include 안 MAT 도 읽는다", 8 in kw.materials, True)
chk("그 MAT 의 항복응력", kw.materials[8].yield_stress if 8 in kw.materials else None, 300.0)
chk("총 파트 수", len(kw.parts), 7)

# 없는 include 는 조용히 넘기지 않는다.
with tempfile.TemporaryDirectory() as td:
    m2 = Path(td) / "main.k"
    m2.write_text("*KEYWORD\n*INCLUDE\nmissing.k\n*END\n", encoding="utf-8")
    kw2 = parse_keyword_file(m2)
chkb("없는 include 파일을 사유로 남긴다", any("missing.k" in w for w in kw2.warnings))

# 실덱: 본 파일이 *INCLUDE 만 들고 있는 흔한 구성 (옛 코드는 0 파트였다).
real = Path("/data/battery_study/case_01_phase1_stacked_tier-1/"
            "01_main_phase1_stacked_tier-1.k")
if real.exists():
    kwr = parse_keyword_file(real)
    chkb("실덱: include 를 따라가 파트를 찾는다", len(kwr.parts) > 0)
    chkb("실덱: 재료도 찾는다", len(kwr.materials) > 0)
    print(f"      파트 {len(kwr.parts)}개 · 재료 {len(kwr.materials)}개")
else:
    print("  -- 실덱 없음 — 건너뜀")

print()


def test_all():
    """pytest 진입점."""
    assert not fails, "실패 %d 건:\n  - %s" % (len(fails), "\n  - ".join(fails))


if __name__ == "__main__":
    if fails:
        print(f"[FAIL] 실패 {len(fails)} 건")
        for f in fails:
            print("   -", f)
        sys.exit(1)
    print("[PASS] 실패 0 건")
