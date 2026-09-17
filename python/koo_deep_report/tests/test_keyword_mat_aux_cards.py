# 보조 MAT 카드가 같은 MID 의 베이스 재료를 덮어쓰지 않는지 검증하는 시험
"""`koo_deep_report.core.keyword_parser` 의 보조 *MAT_ 카드 시험.

*MAT_ADD_EROSION 은 이미 정의된 MID 에 파단 기준을 덧붙이는 보조 카드고,
카드 1 이 'MID EXCL MXPRES MNEPS …' 라 베이스 재료의 RO/E/PR/SIGY 자리와
전혀 다르다. *MAT_THERMAL_* 은 TMID 네임스페이스의 열물성이라 카드 1 이
'TMID TRO TGRLC TGMULT …' 다. 이것들을 베이스 재료로 취급해
materials[mid] 에 덮어쓰면, 같은 MID 의 항복응력·밀도·탄성계수가 통째로
0 이 되어 안전율과 경고색이 사라진다.

카드 배치는 LS-DYNA R16 키워드 매뉴얼 Vol.II 로 확인했다.
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


def _parse(text: str):
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "deck.k"
        p.write_text(text, encoding="utf-8")
        return parse_keyword_file(p)


# ---------------------------------------------------------------------------
print("[1] *MAT_ADD_EROSION 이 같은 MID 의 Johnson-Cook 을 덮지 않는다")

DECK = """*KEYWORD
*PART
Al_CC
         1         1         1
*PART
Cu_CC
         2         2         2
*MAT_JOHNSON_COOK
$      MID        RO         G         E        PR       DTF        VP    RATEOP
         1 2.700E-09   26315.8   70000.0      0.33       0.0       0.0       0.0
$        A         B         N         C         M        TM        TR      EPS0
      30.0     500.0      0.22     0.014       1.0     933.0    298.15       1.0
*MAT_JOHNSON_COOK
$      MID        RO         G         E        PR       DTF        VP    RATEOP
         2 8.960E-09   44776.1  120000.0      0.34       0.0       0.0       0.0
$        A         B         N         C         M        TM        TR      EPS0
     200.0     292.0      0.31     0.025       1.1    1356.0    298.15       1.0
$
$ 보조 카드 — 베이스 재료보다 뒤에 온다 (실덱 04_materials.k 와 같은 순서)
*MAT_ADD_EROSION
$      MID      EXCL    MXPRES     MNEPS    EFFEPS    VOLEPS    NUMFIP       NCS
         1       0.0       0.0       0.0       0.3       0.0       1.0       1.0
*MAT_ADD_EROSION
         2       0.0       0.0       0.0       0.4       0.0       1.0       1.0
*END
"""

kw = _parse(DECK)
m1 = kw.materials.get(1)
m2 = kw.materials.get(2)
chkb("MID 1 재료가 있다", m1 is not None)
if m1:
    chk("MID 1 종류는 JOHNSON_COOK", m1.mat_type, "JOHNSON_COOK")
    chk("MID 1 SIGY = A = 30", m1.yield_stress, 30.0)
    chk("MID 1 밀도가 남아 있다", m1.density, 2.700e-9)
if m2:
    chk("MID 2 종류는 JOHNSON_COOK", m2.mat_type, "JOHNSON_COOK")
    chk("MID 2 SIGY = A = 200", m2.yield_stress, 200.0)

dc = kw.get_design_criteria()
chk("Part 1 stress_limit", dc[1].stress_limit if 1 in dc else None, 30.0)
chk("Part 1 출처", dc[1].stress_source if 1 in dc else None, "mat_card")
chk("Part 2 stress_limit", dc[2].stress_limit if 2 in dc else None, 200.0)

print()

# ---------------------------------------------------------------------------
print("[2] *MAT_THERMAL_ISOTROPIC 이 같은 번호의 구조 재료를 덮지 않는다")

THERMAL = """*KEYWORD
*PART
Shell
         1         1         5
*MAT_PIECEWISE_LINEAR_PLASTICITY
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
         5 7.850E-09  210000.0      0.30     250.0       0.0       0.3       0.0
*MAT_THERMAL_ISOTROPIC
$     TMID       TRO     TGRLC    TGMULT      TLAT      HLAT
         5 7.850E-09       0.0       0.0       0.0       0.0
$       HC        TC
     460.0      45.0
*END
"""

kwt = _parse(THERMAL)
m5 = kwt.materials.get(5)
chkb("MID 5 재료가 있다", m5 is not None)
if m5:
    chk("MID 5 종류는 PIECEWISE_LINEAR_PLASTICITY", m5.mat_type,
        "PIECEWISE_LINEAR_PLASTICITY")
    chk("MID 5 SIGY = 250", m5.yield_stress, 250.0)
    chk("MID 5 E 가 TGRLC(0) 로 덮이지 않았다", m5.youngs_modulus, 210000.0)

print()

# ---------------------------------------------------------------------------
print("[3] 실덱 — battery case_01 의 04_materials.k")

REAL = Path("/data/battery_study/case_01_phase1_stacked_tier-1/04_materials.k")
if not REAL.exists():
    print(f"  -- 실덱 없음 — 건너뜀 ({REAL})")
else:
    kwr = parse_keyword_file(REAL)
    r1 = kwr.materials.get(1)
    r2 = kwr.materials.get(2)
    chkb("MID 1 (Al_CC) 재료가 있다", r1 is not None)
    if r1:
        chk("MID 1 종류", r1.mat_type, "JOHNSON_COOK")
        chk("MID 1 SIGY = A = 30 MPa", r1.yield_stress, 30.0)
    if r2:
        chk("MID 2 종류", r2.mat_type, "JOHNSON_COOK")
        chk("MID 2 SIGY = A = 200 MPa", r2.yield_stress, 200.0)

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
