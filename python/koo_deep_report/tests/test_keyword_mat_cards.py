# *MAT_ 카드에서 항복응력·파단변형률을 제자리에서 읽는지 검증하는 시험
"""`koo_deep_report.core.keyword_parser` 의 MAT 카드 지도 시험.

MAT 종류마다 카드 1 의 배치가 다르다. MAT_024 배치(MID RO E PR SIGY ETAN
FAIL TDEL)를 모든 종류에 그대로 쓰면 포아송비·경화규칙 플래그·
Cowper-Symonds 계수를 '항복응력' 으로 읽는다. 그 값이 설계기준
(stress_limit, source='mat_card')이 되어 안전율과 경고 색을 좌우한다.

카드 번호는 LS-DYNA R16 키워드 매뉴얼 Vol.II 로 확인했다.
"""
import sys
import tempfile
from pathlib import Path

from koo_deep_report.core.keyword_parser import parse_keyword_file

fails = []


def chk(name, got, want, tol=0.0):
    ok = (got == want) if tol == 0 else (
        got is not None and want is not None and abs(got - want) <= tol)
    if not ok:
        fails.append(f"{name}: got={got!r} want={want!r}")
    print(f"  {'OK ' if ok else 'NG '} {name}")


def chkb(name, cond):
    if not cond:
        fails.append(name)
    print(f"  {'OK ' if cond else 'NG '} {name}")


# LS-PrePost 가 카드 사이에 넣는 '$#' 주석 줄을 일부러 섞었다.
DECK = """\
*KEYWORD
*PART
Housing
         1         1         1
*PART
Screen
         2         2         2
*PART
Bracket
         3         3         3
*PART
Case
         4         4         4
*PART
Spring
         5         5         5
*PART
Clip
         6         6         6
*PART
Frame
         7         7         7
$# MAT_015: MID RO G E PR DTF VP RATEOP / A B N C M TM TR EPS0
*MAT_JOHNSON_COOK
$#     mid        ro         g         e        pr       dtf        vp    rateop
         1  7.85E-09     81000    210000      0.33       0.0       0.0       0.0
$#       a         b         n         c         m        tm        tr      eps0
       320       100       0.3      0.02       1.0      1800       293       1.0
$#      cp        pc     spall        it        d1        d2        d3        d4
       452       0.0       2.0       0.0       0.0       0.0       0.0       0.0
$# MAT_003: MID RO E PR SIGY ETAN BETA / SRC SRP FS VP
*MAT_PLASTIC_KINEMATIC
         2  7.85E-09    210000       0.3       250      1000       1.0
$#     src       srp        fs        vp
       0.0       0.0      0.25       0.0
$# MAT_036: MID RO E PR HR P1 P2 ITER — 카드 1 에 스칼라 항복응력이 없다
*MAT_3-PARAMETER_BARLAT
         3  7.85E-09    210000       0.3       3.0       0.0       0.0       0.0
       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0
$# MAT_124: MID RO E PR C P FAIL TDEL — 카드 1 에 스칼라 항복응력이 없다
*MAT_PLASTICITY_COMPRESSION_TENSION
         4  7.85E-09    210000       0.3      40.0       5.0       0.3       0.0
       101       102         0         0         0         0       0.0       0.0
$# MAT_098: MID RO E PR VP / A B N C PSFAIL SIGMAX SIGSAT EPSO
*MAT_SIMPLIFIED_JOHNSON_COOK
         5  7.85E-09    210000       0.3       0.0
       320       100       0.3      0.02       0.5       0.0       0.0       1.0
$# MAT_018: MID RO E PR K N SRC SRP / SIGY VP EPSF
*MAT_POWER_LAW_PLASTICITY
         6  7.85E-09    210000       0.3       600      0.25       0.0       0.0
       200       0.0       0.4
$# MAT_024: MID RO E PR SIGY ETAN FAIL TDEL — 원래 맞던 것 (회귀 확인)
*MAT_PIECEWISE_LINEAR_PLASTICITY
         7  7.85E-09    210000       0.3       300      1200       0.2       0.0
       0.0       0.0       0.0       0.0
*END
"""

with tempfile.TemporaryDirectory() as td:
    kfile = Path(td) / "deck.k"
    kfile.write_text(DECK, encoding="utf-8")
    kw = parse_keyword_file(kfile)

mats = kw.materials

# ---------------------------------------------------------------------------
print("[1] 항복응력을 이웃 필드에서 주워오지 않는다")

chkb("MAT_015 를 읽었다", 1 in mats)
chk("MAT_015 항복응력 = 카드2 의 A = 320 (PR 0.33 아님)",
    mats[1].yield_stress if 1 in mats else None, 320.0)
chk("MAT_003 항복응력 = SIGY 250", mats[2].yield_stress if 2 in mats else None, 250.0)
chk("MAT_036 은 스칼라 항복응력 없음 (HR 3.0 아님)",
    mats[3].yield_stress if 3 in mats else None, 0.0)
chk("MAT_124 는 스칼라 항복응력 없음 (C 40.0 아님)",
    mats[4].yield_stress if 4 in mats else None, 0.0)
chk("MAT_098 항복응력 = 카드2 의 A = 320 (VP 0.0 아님)",
    mats[5].yield_stress if 5 in mats else None, 320.0)
chk("MAT_018 항복응력 = 카드2 의 SIGY = 200 (K 600 아님)",
    mats[6].yield_stress if 6 in mats else None, 200.0)
chk("MAT_024 항복응력 = SIGY 300 (회귀)",
    mats[7].yield_stress if 7 in mats else None, 300.0)

print()

# ---------------------------------------------------------------------------
print("[2] 파단변형률도 제자리에서 읽는다")

chk("MAT_003 파단 = 카드2 의 FS = 0.25 (BETA 1.0 아님)",
    mats[2].failure_strain if 2 in mats else None, 0.25)
chk("MAT_098 파단 = 카드2 의 PSFAIL = 0.5 (EPSO/NUMINT 아님)",
    mats[5].failure_strain if 5 in mats else None, 0.5)
chk("MAT_124 파단 = 카드1 의 FAIL = 0.3 (원래 맞던 것)",
    mats[4].failure_strain if 4 in mats else None, 0.3)
chk("MAT_024 파단 = FAIL 0.2 (회귀)",
    mats[7].failure_strain if 7 in mats else None, 0.2)

print()

# ---------------------------------------------------------------------------
print("[3] 설계기준으로 흘러가는 값이 물리적으로 말이 되는가")

dc = kw.get_design_criteria()
# 300 MPa 를 받은 JC 파트: 옛 코드는 stress_limit 0.33 → 안전율 0.0011, 'crit'
chk("Part 1 (JC) stress_limit", dc[1].stress_limit if 1 in dc else None, 320.0)
chk("Part 1 출처", dc[1].stress_source if 1 in dc else None, "mat_card")
chk("Part 3 (Barlat) 은 기준 없음", dc[3].stress_limit if 3 in dc else None, 0.0)
chk("Part 3 출처는 none", dc[3].stress_source if 3 in dc else None, "none")
chk("Part 2 (PK) strain_limit = FS", dc[2].strain_limit if 2 in dc else None, 0.25)
chk("Part 2 strain 출처", dc[2].strain_source if 2 in dc else None, "mat_card")

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
