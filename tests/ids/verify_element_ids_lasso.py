# d3plot 요소 실제 ID(NARBS)를 원본 .k 덱 및 lasso 와 대조해 순서 어긋남을 잡는 검증 도구
"""
사용:
    g++ -std=c++17 -O2 -I include tests/ids/dump_element_ids.cpp build/libkood3plot.a \\
        -fopenmp -lz -o /tmp/dump_ids
    python3 tests/ids/verify_element_ids_lasso.py <d3plot> /tmp/dump_ids [원본.k ...]

대조 기준은 둘이고 하나만 있어도 판정한다.
  1) 원본 키워드 덱의 *ELEMENT_SOLID/BEAM/SHELL/TSHELL 카드 (외부 라이브러리 불요)
  2) lasso-python 의 element_*_ids

2026-09-17: NARBS 블록을 절점→솔리드→**두꺼운셸**→빔→셸 순으로 읽어, 셸과 두꺼운 셸이
함께 있는 덱에서 두 ID 배열이 통째로 어긋나 있었다. 규격 순서는
절점→솔리드→빔→셸→두꺼운셸 이다 (ls-dyna_database.txt:728-732).
"""
import json
import subprocess
import sys
from pathlib import Path

KINDS = ("solid", "beam", "shell", "tshell")
CARD = {"*ELEMENT_SOLID": "solid", "*ELEMENT_BEAM": "beam",
        "*ELEMENT_SHELL": "shell", "*ELEMENT_TSHELL": "tshell"}


def from_deck(paths):
    """원본 .k 에서 요소 종류별 ID 집합. 빈 dict 면 덱을 못 읽은 것."""
    ids = {k: set() for k in KINDS}
    seen_any = False
    for p in paths:
        kind = None
        for line in Path(p).read_text(errors="ignore").splitlines():
            if line.startswith("*"):
                key = line.strip().upper().split()[0]
                kind = next((v for k, v in CARD.items() if key.startswith(k)), None)
                continue
            if kind is None or not line.strip() or line.startswith("$"):
                continue
            tok = line.split()
            if not tok or not tok[0].lstrip("-").isdigit():
                continue
            ids[kind].add(int(tok[0]))
            seen_any = True
    return ids if seen_any else {}


def from_lasso(d3plot):
    try:
        from lasso.dyna import D3plot, ArrayType as A
    except Exception as e:  # noqa: BLE001
        print(f"  (lasso 없음: {e})")
        return {}
    keys = {"solid": A.element_solid_ids, "beam": A.element_beam_ids,
            "shell": A.element_shell_ids, "tshell": A.element_tshell_ids}
    d = D3plot(str(d3plot), state_array_filter=[A.global_timesteps])
    return {k: set(d.arrays[v].tolist()) for k, v in keys.items() if v in d.arrays}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    d3plot, dump_bin = sys.argv[1], sys.argv[2]
    decks = sys.argv[3:] or sorted(Path(d3plot).parent.glob("*.k"))
    got = json.loads(subprocess.run([dump_bin, d3plot], capture_output=True, text=True, check=True).stdout)
    mine = {k: set(got.get(k) or []) for k in KINDS}
    print(f"리더: " + ", ".join(f"{k} {len(mine[k])}개" for k in KINDS if mine[k]))

    bad = 0
    for label, ref in (("원본 덱", from_deck(decks)), ("lasso", from_lasso(d3plot))):
        if not ref:
            print(f"  {label}: 대조 자료 없음 — 건너뜀")
            continue
        for k in KINDS:
            if not mine[k] and not ref.get(k):
                continue
            if mine[k] != ref.get(k, set()):
                bad += 1
                only_mine = sorted(mine[k] - ref.get(k, set()))[:3]
                only_ref = sorted(ref.get(k, set()) - mine[k])[:3]
                print(f"  [FAIL] {label} {k}: 리더 {len(mine[k])}개 / 기준 {len(ref.get(k, set()))}개, "
                      f"리더에만 {only_mine}, 기준에만 {only_ref}")
            else:
                print(f"  [OK  ] {label} {k}: {len(mine[k])}개 일치")
    print("[PASS]" if bad == 0 else f"[FAIL] 불일치 {bad}건")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
