# 리포트 도구(sphere·impact)가 끝에 부르는 꾸러미 출력 — HTML 곁에 <줄기>.ontology.json, 실패해도 도구는 죽지 않는다
"""리포트 도구가 스스로 꾸러미를 낸다(사용자 결정 10-31 「세 리포트가 늘 함께 낸다」, DynaForge 검토의 (A)).

post_analyze 를 거치지 않는 길(stcx 후처리 예약 7-1 — 셸이 `koo_sphere_report -o …/sphere_report.html
--json …/sphere_report.json` 을 바로 부른다)에서도 꾸러미가 생기게, 도구가 JSON·HTML 을 다 쓴 뒤 이것을
부른다. 그러면 두 길이 같은 코드로 같은 파일을 낸다.

- 결과: HTML 곁에 `<HTML 줄기>.ontology.json` (HTML 이 없으면 JSON 곁 · JSON 줄기). 머리 `source.html` 에
  HTML 지문 — DynaForge 는 HTML 을 반입하고 그 지문으로 짝을 짓는다.
- **리포트가 정본이다** — 꾸러미를 못 지으면 이유를 stderr 에 말하고 None 을 돌려줄 뿐, 예외를 올리지 않는다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .package import PackageError, write


def beside(kind: str, json_path, html_path=None, **kw) -> Path | None:
    """이미 쓴 리포트 JSON 으로 꾸러미를 지어 HTML 곁에 쓴다. kind = "sphere" | "impact".

    `kw` 는 어댑터로 그대로 간다(sphere: test_dir · yield_map_path · yield_stress).
    """
    try:
        jp = Path(json_path)
        hp = Path(html_path) if html_path else None
        if hp is not None and not hp.is_file():
            hp = None
        base = hp if hp is not None else jp
        out = base.with_name(base.stem + ".ontology.json")
        report = json.loads(jp.read_text(encoding="utf-8"))
        if kind == "sphere":
            from . import sphere
            doc = sphere.build(report, report_path=jp, html_path=hp, **kw)
        elif kind == "impact":
            from . import impact
            # impact_payload.json 은 HTML 곁에 생긴다(report/emit.py) — HTML 이 없으면 JSON 곁을 본다
            doc = impact.build(report, report_path=jp, html_path=hp,
                               payload=impact.load_payload(hp or jp), **kw)
        else:
            raise ValueError(f"모르는 리포트 종류 {kind!r}")
        write(doc, out)
        n_o = sum(doc["counts"]["objects"].values())
        print(f"[ontology] 꾸러미 저장: {out} (객체 {n_o}, 단위 {doc['units']['system']})")
        return out
    except PackageError as e:
        print(f"[ontology] 꾸러미가 어휘와 맞지 않아 쓰지 않았다 — 리포트는 그대로: {e}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001 — 리포트가 정본, 꾸러미 실패로 도구를 죽이지 않는다
        print(f"[ontology] 꾸러미를 만들지 못했다 — 리포트는 그대로 ({type(e).__name__}: {e})", file=sys.stderr)
    return None
