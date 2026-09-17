# 다중 파일 덱에서 *INCLUDE 마스터 덱을 골라내는지 검증하는 시험
"""`koo_deep_report.core.keyword_parser.find_and_parse_keyword` 시험.

다중 파일 덱은 마스터 덱이 *INCLUDE 로 메시·재료를 끌어온다. 마스터는
몇백 바이트, 메시는 수 MB 다. 후보를 '크기 내림차순 + 첫 성공' 으로 고르면
마스터에는 결코 닿지 못하고 메시 파일에서 멈춘다 — 파트 이름은 나오지만
*MAT_ 카드가 통째로 빠져 전 파트가 stress_source='none' 이 되고, 안전율과
경고색이 아무 표시 없이 사라진다.
"""
import sys
import tempfile
from pathlib import Path

from koo_deep_report.core.keyword_parser import find_and_parse_keyword

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


# 실덱의 마스터와 같은 모양 — 주석 머리말 + *INCLUDE 목록만 (실측 737 B).
MASTER = """*KEYWORD
*TITLE
multi-file deck
$
$ ============================================================
$ Phase 1: Mechanical Only
$   - Impactor lateral impact -> cell deformation
$ ============================================================
$
$---+----1----+----2----+----3----+----4----+----5----+----6----+----7----+----8
$
$ ==================== INCLUDE FILES ====================
$
*INCLUDE
02_mesh.k
$
*INCLUDE
04_materials.k
$
*END
"""

MESH_HEAD = """*KEYWORD
*PART
Al_CC
         1         1         1
*PART
Cu_CC
         2         2         2
*END
"""

MATS = """*KEYWORD
*MAT_PIECEWISE_LINEAR_PLASTICITY
$      MID        RO         E        PR      SIGY      ETAN      FAIL      TDEL
         1 2.700E-09   70000.0      0.33      30.0       0.0       0.3       0.0
*MAT_PIECEWISE_LINEAR_PLASTICITY
         2 8.960E-09  120000.0      0.34     200.0       0.0       0.4       0.0
*END
"""


def _build_deck(case: Path) -> None:
    case.mkdir(parents=True, exist_ok=True)
    (case / "d3plot").write_bytes(b"\0" * 256)
    (case / "01_main.k").write_text(MASTER, encoding="utf-8")
    # 메시 파일은 마스터보다 훨씬 크다 — 실덱에서 마스터 737 B / 메시 1.6 MB.
    pad = "".join(f"$ filler line {i}\n" for i in range(4000))
    (case / "02_mesh.k").write_text(MESH_HEAD + pad, encoding="utf-8")
    (case / "04_materials.k").write_text(MATS, encoding="utf-8")


# ---------------------------------------------------------------------------
print("[1] 마스터 덱이 가장 작아도 *INCLUDE 를 따라간 결과를 고른다")

with tempfile.TemporaryDirectory() as td:
    case = Path(td) / "case_01"
    _build_deck(case)
    kw = find_and_parse_keyword(case / "d3plot")

    chkb("키워드 파일을 찾았다", kw is not None)
    if kw is not None:
        chk("파트 2개", len(kw.parts), 2)
        chk("재료 2개 (메시 파일만 골랐으면 0)", len(kw.materials), 2)
        dc = kw.get_design_criteria()
        chk("Part 1 stress_limit", dc[1].stress_limit if 1 in dc else None, 30.0)
        chk("Part 1 출처", dc[1].stress_source if 1 in dc else None, "mat_card")
        chk("Part 2 stress_limit", dc[2].stress_limit if 2 in dc else None, 200.0)
        chk("Part 2 strain_limit (FAIL)", dc[2].strain_limit if 2 in dc else None, 0.4)

print()

# ---------------------------------------------------------------------------
print("[2] 재료 카드를 하나도 못 찾으면 사유를 남긴다 (조용히 지나가지 않는다)")

with tempfile.TemporaryDirectory() as td:
    case = Path(td) / "case_mesh_only"
    case.mkdir(parents=True)
    (case / "d3plot").write_bytes(b"\0" * 256)
    (case / "02_mesh.k").write_text(MESH_HEAD + "$ pad\n" * 200, encoding="utf-8")
    kw = find_and_parse_keyword(case / "d3plot")

    chkb("파트는 찾았다", kw is not None and len(kw.parts) == 2)
    if kw is not None:
        chk("재료 0개", len(kw.materials), 0)
        chkb("재료가 없다는 사유가 warnings 에 있다",
             any("*MAT_" in w for w in kw.warnings))

print()

# ---------------------------------------------------------------------------
print("[3] 실덱 — battery case_01 (마스터 737 B / 메시 1.6 MB)")

REAL = Path("/data/battery_study/case_01_phase1_stacked_tier-1")
if not (REAL / "d3plot").exists():
    print(f"  -- 실덱 없음 — 건너뜀 ({REAL})")
else:
    kw = find_and_parse_keyword(REAL / "d3plot")
    chkb("키워드 파일을 찾았다", kw is not None)
    if kw is not None:
        chk("파트 34개", len(kw.parts), 34)
        chkb("재료가 비어 있지 않다 (메시 파일만 골랐으면 0)", len(kw.materials) > 0)
        dc = kw.get_design_criteria()
        n_stress = sum(1 for d in dc.values() if d.stress_limit > 0)
        chkb(f"응력 기준을 받은 파트가 있다 (got {n_stress}/34)", n_stress > 0)

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
