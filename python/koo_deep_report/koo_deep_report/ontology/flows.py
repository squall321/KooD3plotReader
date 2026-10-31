# 런별 에너지 흐름 그래프(접촉 엣지)를 접촉 정의·하중 전달·하중 경로 객체로 옮기는 공용 부분
"""에너지 흐름은 `koo_deep_report.core.energy_flow_builder.build_flow_graph` 의 중립 dict 다
(sphere 는 전 런을 스칼라만 남긴 slim 판, 상위 런만 시계열이 있는 원판). 엣지 하나가
「한 런에서 접촉 인터페이스 하나를 건너간 하중」 이고, 방향(src→dst)은 빌더가 BFS 깊이로
정한 전파 순서다.

노드 이름이 숫자면 실제 파트(PID), 아니면 `iface:`/`set:` 유령 노드다 — 접촉 한쪽을 파트로
못 푼 것이다. 유령 쪽은 파트 참조를 비우고 그 이름을 `unresolved_side` 에 남긴다
(파트인 척하지 않는다).
"""
from __future__ import annotations

import statistics


def _pid(node) -> int | None:
    s = str(node)
    return int(s) if s.isdigit() else None


def _percentile(sorted_vals: list[float], q: float) -> float:
    """선형 보간 백분위(numpy 의 기본과 같다)."""
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def add_contacts(pkg, contact_map, part_keys: dict[int, str]) -> dict[int, str]:
    """덱에서 푼 접촉 정의 → cae_contact + contact_side. {CID: 키} 를 돌려준다."""
    keys: dict[int, str] = {}
    if contact_map is None:
        return keys
    for cid in sorted(contact_map.endpoints):
        ep = contact_map.endpoints[cid]
        key = f"contact/{cid}"
        pkg.add("cae_contact", key, ep.name or f"Contact_{cid}", {
            "campaign": "campaign", "contact_id": cid, "name": ep.name or None,
            "contact_card": getattr(ep, "keyword", "") or None,
            "resolution_confidence": float(ep.confidence),
        })
        keys[cid] = key
        for role, side in (("slave", ep.slave), ("master", ep.master)):
            pid = side.part_id if side.kind == "part" else None
            if pid is not None and pid in part_keys:
                pkg.relate("contact_side", ("cae_contact", key), ("cae_part", part_keys[pid]),
                           {"role": role})
    return keys


def add_transfers(pkg, flows: dict, run_keys: dict[str, str], part_keys: dict[int, str],
                  contact_keys: dict[int, str]) -> None:
    """런별 흐름 엣지 → cae_load_transfer, 그리고 파트 쌍마다 전 런 집계 → cae_load_path.

    덱에서 못 푼 접촉(카드가 _ID 가 아니거나 덱이 없음)은 엣지가 말하는 번호·이름으로
    접촉 정의를 세운다 — 하중이 건너간 사실은 남아야 한다.
    """
    pairs: dict[tuple[int, int], dict] = {}
    n_flow_runs = 0
    for folder in sorted(flows):
        run_key = run_keys.get(folder)
        g = flows[folder] or {}
        edges = g.get("edges") or []
        if run_key is None or not g:
            continue
        n_flow_runs += 1
        depth = g.get("depth_map") or {}
        per_pair: dict[tuple[int, int], dict] = {}
        for e in edges:
            cid = int(e.get("contact_id", -1))
            ckey = contact_keys.get(cid)
            if ckey is None and cid >= 0:
                ckey = f"contact/{cid}"
                if not pkg.has("cae_contact", ckey):
                    pkg.add("cae_contact", ckey, e.get("name") or f"Contact_{cid}",
                            {"campaign": "campaign", "contact_id": cid, "name": e.get("name") or None})
                contact_keys[cid] = ckey
            src, dst = str(e.get("src")), str(e.get("dst"))
            sp, dp = _pid(src), _pid(dst)
            sk = part_keys.get(sp) if sp is not None else None
            dk = part_keys.get(dp) if dp is not None else None
            unresolved = [n for n, k in ((src, sk), (dst, dk)) if k is None]
            xkey = f"xfer/{folder}/{cid}"
            if pkg.has("cae_load_transfer", xkey):
                continue          # 같은 런에 같은 인터페이스가 둘이면 빌더가 이미 하나로 줄였다
            d = depth.get(dst)
            pkg.add("cae_load_transfer", xkey, f"{e.get('name') or cid} @ {folder}", {
                "run": run_key, "contact": ckey, "from_part": sk, "to_part": dk,
                "peak_force": e.get("peak_force"),
                "total_impulse": e.get("total_impulse"),
                # 일은 양 끝이 실제 파트일 때만 셈한다 — 아니면 빌더가 0 을 넣는다. 0 을 싣지 않는다.
                "total_work": e.get("total_work") if (sk and dk) else None,
                "first_engage_time": e.get("first_engage_t"),
                "propagation_depth": int(d) if isinstance(d, int) else None,
                "confidence": e.get("confidence"),
                "unresolved_side": ", ".join(unresolved) or None,
            })
            if sk is None or dk is None or sp == dp:
                continue          # 파트 쌍이 아니면 경로 집계에서 뺀다(자기 접촉 포함)
            a, b = min(sp, dp), max(sp, dp)
            cur = per_pair.setdefault((a, b), {"impulse": 0.0, "force": 0.0, "work": None,
                                               "lead": (-1.0, sp < dp)})
            imp = float(e.get("total_impulse") or 0.0)
            cur["impulse"] += imp
            cur["force"] = max(cur["force"], float(e.get("peak_force") or 0.0))
            if e.get("total_work") is not None:
                cur["work"] = (cur["work"] or 0.0) + float(e["total_work"])
            if imp > cur["lead"][0]:
                cur["lead"] = (imp, sp < dp)      # 이 쌍의 방향은 충격량이 큰 접촉을 따른다
        for ab, v in per_pair.items():
            acc = pairs.setdefault(ab, {"runs": [], "a_to_b": 0, "b_to_a": 0})
            acc["runs"].append((folder, v["impulse"], v["force"], v["work"]))
            if v["lead"][1]:
                acc["a_to_b"] += 1
            else:
                acc["b_to_a"] += 1

    for (a, b) in sorted(pairs):
        acc = pairs[(a, b)]
        runs = acc["runs"]
        imps = sorted(r[1] for r in runs)
        top = max(runs, key=lambda r: r[1])
        works = [r[3] for r in runs if r[3] is not None]
        pkg.add("cae_load_path", f"path/{a}-{b}", f"{a} ↔ {b}", {
            "campaign": "campaign", "part_a": part_keys[a], "part_b": part_keys[b],
            "n_runs_engaged": len(runs),
            "engage_ratio": len(runs) / n_flow_runs if n_flow_runs else None,
            "n_runs_a_to_b": acc["a_to_b"], "n_runs_b_to_a": acc["b_to_a"],
            "impulse_max": top[1], "impulse_max_run": run_keys[top[0]],
            "impulse_median": statistics.median(imps),
            "impulse_p90": _percentile(imps, 0.9),
            "peak_force_max": max(r[2] for r in runs),
            "work_max": max(works) if works else None,
        })
