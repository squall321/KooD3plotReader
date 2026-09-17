# findings.json(원본)과 findings.md·checklist.md·groups/ 의 개수·심각도가 어긋나지 않는지 검사하는 도구
"""
사용:
    python3 docs/data_integrity_2026-09/check_docs_consistency.py

findings.json 을 유일한 원본으로 삼고 파생 문서를 대조한다. 어긋나면 종료 1.
  1) groups/confirmed-*.json 의 합과 findings.json['confirmed'] 개수·항목
  2) findings.md 절 제목의 개수와 표의 실제 행 수
  3) findings.md 표의 심각도와 findings.json 의 severity
  4) checklist.md 의 '전수 조사 확정 N건' 과 묶음별 내역

왜 있나 — 2026-09-17 검토에서 checklist 는 56건/10·4·11·16·13·2, findings.md 는
60건/9·7·13·16·13·2 로 어긋났고, findings.md 의 심각도가 원본과 9건 달랐다.
사람이 눈으로 세는 한 같은 어긋남이 다시 난다.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_json():
    return json.loads((HERE / "findings.json").read_text(encoding="utf-8"))


def md_rows(md_text):
    """findings.md 의 절별 표 행. [(절 제목, 선언 개수, [(심각도, 위치, 제목)...])]"""
    out = []
    cur = None
    for line in md_text.splitlines():
        m = re.match(r"^##\s+(\S+)\s*\((\d+)건\)\s*$", line)
        if m:
            cur = (m.group(1), int(m.group(2)), [])
            out.append(cur)
            continue
        if line.startswith("## "):          # 기각 / 미검증(낮음) 절 — 표 대상 아님
            cur = None
            continue
        if cur is None or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0] in ("심각도", "---") or set(cells[0]) <= {"-"}:
            continue
        cur[2].append((cells[0], cells[1], cells[2]))
    return out


def main():
    data = load_json()
    confirmed = data["confirmed"]
    bad = []

    # 1) groups/confirmed-*.json
    grouped = []
    for p in sorted((HERE / "groups").glob("confirmed-*.json")):
        grouped += json.loads(p.read_text(encoding="utf-8"))
    if len(grouped) != len(confirmed):
        bad.append(f"groups/confirmed-* 합 {len(grouped)} ≠ findings.json confirmed {len(confirmed)}")
    key = lambda x: (x["file"], x["line"], x["title"])
    if sorted(map(key, grouped)) != sorted(map(key, confirmed)):
        bad.append("groups/confirmed-* 와 findings.json['confirmed'] 의 항목이 다름")
    print(f"  groups/confirmed-* {len(grouped)}건 / findings.json confirmed {len(confirmed)}건")

    # 2)+3) findings.md
    md = (HERE / "findings.md").read_text(encoding="utf-8")
    m = re.search(r"확정\s+(\d+)건", md)
    if not m:
        bad.append("findings.md 머리말에서 '확정 N건' 을 찾지 못함")
    elif int(m.group(1)) != len(confirmed):
        bad.append(f"findings.md 머리말 확정 {m.group(1)}건 ≠ findings.json {len(confirmed)}건")

    sections = md_rows(md)
    total_rows = 0
    by_title = {x["title"]: x for x in confirmed}
    for name, declared, rows in sections:
        total_rows += len(rows)
        if declared != len(rows):
            bad.append(f"findings.md {name}: 제목 {declared}건 ≠ 표 {len(rows)}행")
        for sev, loc, title in rows:
            src = by_title.get(title)
            if src is None:
                bad.append(f"findings.md {name}: '{title[:30]}…' 가 findings.json 에 없음")
            elif src["severity"] != sev:
                bad.append(f"심각도 불일치 {src['file']}:{src['line']} — md {sev} / json {src['severity']}")
    if total_rows != len(confirmed):
        bad.append(f"findings.md 표 총 {total_rows}행 ≠ findings.json {len(confirmed)}건")
    print(f"  findings.md 절 {len(sections)}개 / 표 {total_rows}행")

    # 4) checklist.md
    cl = (HERE / "checklist.md").read_text(encoding="utf-8")
    m = re.search(r"전수 조사 확정\s+(\d+)건", cl)
    if not m:
        bad.append("checklist.md 에서 '전수 조사 확정 N건' 을 찾지 못함")
    elif int(m.group(1)) != len(confirmed):
        bad.append(f"checklist.md 확정 {m.group(1)}건 ≠ findings.json {len(confirmed)}건")
    per = [int(x) for x in re.findall(r"·?\s*G\d[^(]*\((\d+)\)", cl)]
    if not per:
        bad.append("checklist.md 에서 묶음별 개수를 찾지 못함")
    else:
        want = [len(rows) for _, _, rows in sections]
        if per != want:
            bad.append(f"checklist.md 묶음별 {per} ≠ findings.md 절별 {want}")
        if sum(per) != len(confirmed):
            bad.append(f"checklist.md 묶음별 합 {sum(per)} ≠ findings.json {len(confirmed)}건")
    print(f"  checklist.md 묶음별 {per} (합 {sum(per) if per else 0})")

    if bad:
        print(f"\n[FAIL] 불일치 {len(bad)}건")
        for b in bad:
            print(f"  - {b}")
        return 1
    print("\n[PASS] findings.json 과 파생 문서가 일치합니다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
