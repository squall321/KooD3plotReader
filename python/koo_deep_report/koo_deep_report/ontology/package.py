# 온톨로지 꾸러미(dynaforge.onto_package)를 어휘로 검증하며 짓고 단위를 맞춰 쓰는 작성기
"""꾸러미 = 어휘(`vocabulary.py`)로 쓴 객체·관계 묶음. DynaForge 가 리포트와 함께 받아
`onto_objects`·`onto_relations` 에 올린다.

꼴 (format_version 1)::

    {"format": "dynaforge.onto_package", "format_version": 1,
     "vocabulary": {"group", "version", "sha256"},
     "producer":   {"tool", "adapter", "version", "created_utc"},
     "source":     {"kind", "file", "sha256"},
     "scope":      {"scenario_kind", "campaign_key"},
     "units":      {"system", "normalized", "factors", "deck_labels", "note"},
     "counts":     {"objects": {타입: 수}, "relations": {관계: 수}},
     "ref_relations": [{"type", "property", "relation"}],
     "objects":    [{"type", "key", "label", "properties"}],
     "relations":  [{"relation", "src": [타입, 키], "dst": [타입, 키], "properties"}]}

**키는 캠페인 안 상대 키**다(`run/Run_…`). DynaForge 가 적재할 때 `<리포트 키>/` 를 붙이고,
`object_ref` 값(역시 상대 키)도 같은 규칙으로 바꾼다. 바깥 타입(`impact_report` 등)을 가리키는
칸·관계는 만드는 쪽이 비워 두고 DynaForge 가 채운다(`vocabulary.FILLED_AT_INGEST`).

**다대일 관계는 줄로 싣지 않는다** — 참조 속성(`cae_run.campaign` 등)이 곧 그 관계다(`ref_relations` 가
어느 속성이 어느 관계인지 적는다). 줄로 싣는 것은 속성으로 정해지지 않는 다대다(`contact_side` ·
`path_between` · `finding_about`)뿐이다. 같은 사실을 두 번 쓰면 v14 에서 관계의 96% 가 중복이었고,
DynaForge 도 다대일은 줄로 쓰지 않기로 했다(검토 답신 2026-10-31).

지키는 것
- 어휘에 없는 타입·속성·관계·열거값, 빠진 필수값, 가리킬 곳 없는 참조는 **쓰지 않고 실패**한다.
  반쯤 맞는 꾸러미를 내보내면 받는 쪽이 어디가 틀렸는지 모른다.
- 값이 없으면 키를 뺀다. 0 이나 null 로 채우지 않는다(리포트 결측 규약과 같다).
- 수치는 속성의 `unit` 글자의 단위로 바꿔 싣는다. 단위계를 모르면 바꾸지 않고
  `units.normalized=false` 로 그 사실을 적는다(지어내지 않는다).
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

from . import vocabulary as V

FORMAT = "dynaforge.onto_package"
FORMAT_VERSION = 1

# 덱 단위 → 어휘 단위 배수. 어휘 단위는 MPa·mm·s·mJ·N·N·s·mm/s.
# ton-mm-s 는 어휘 단위 그 자체다. SI(kg·m·s) 는 Pa·m·J. g-mm-ms 는 시각만 ms.
# ton-mm-ms 는 넣지 않는다 — 일관 단위계가 아니라(힘이 MN) 라벨 프리셋부터 의심스럽다.
_FACTORS = {
    "ton_mm_s": {"stress": 1.0, "length": 1.0, "time": 1.0, "energy": 1.0, "force": 1.0, "impulse": 1.0,
                 "velocity": 1.0},
    "si": {"stress": 1e-6, "length": 1e3, "time": 1.0, "energy": 1e3, "force": 1.0, "impulse": 1.0,
           "velocity": 1e3},
    "g_mm_ms": {"stress": 1.0, "length": 1.0, "time": 1e-3, "energy": 1.0, "force": 1.0, "impulse": 1e-3,
                "velocity": 1e3},
}

#: 리포트들이 쓰는 단위계 이름 → 어휘 열거값.
_SYSTEM_IDS = {"SI": "si", "si": "si", "ton-mm-s": "ton_mm_s", "ton-mm-ms": "ton_mm_ms",
               "g-mm-ms": "g_mm_ms"}


class PackageError(ValueError):
    """어휘와 맞지 않는 꾸러미. `faults` 에 흠을 다 모아 둔다(첫 흠에서 멈추지 않는다)."""

    def __init__(self, faults: list[str]):
        self.faults = list(faults)
        head = "; ".join(self.faults[:5])
        more = f" (외 {len(self.faults) - 5}건)" if len(self.faults) > 5 else ""
        super().__init__(f"온톨로지 꾸러미가 어휘와 맞지 않습니다 — {head}{more}")


class Units:
    """덱 단위계와 환산 계수. `normalized` 가 거짓이면 값을 그대로 싣는다."""

    def __init__(self, system_id: str | None, *, deck_labels: dict | None = None, note: str = ""):
        self.system = _SYSTEM_IDS.get(str(system_id or ""), "unknown")
        self.factors = _FACTORS.get(self.system)
        self.normalized = self.factors is not None
        self.deck_labels = dict(deck_labels or {})
        self.note = str(note or "")
        if self.system == "ton_mm_ms" and not self.note:
            self.note = "ton-mm-ms 는 일관 단위계가 아니어서(힘 단위가 MN) 값을 바꾸지 않았습니다."

    def convert(self, unit: str | None, value: float) -> float:
        kind = V.UNIT_KINDS.get(unit or "")
        if kind is None or not self.normalized:
            return value
        f = self.factors[kind]
        return value if f == 1.0 else float(f"{value * f:.9g}")

    def header(self) -> dict:
        return {"system": self.system, "normalized": self.normalized,
                "factors": dict(self.factors or {}), "deck_labels": self.deck_labels,
                "note": self.note}


def module_version() -> str:
    """배포 모듈의 판 (SIF 의 /opt/kood3plot/VERSION). 개발 호스트면 빈 문자열."""
    cands = []
    home = os.environ.get("KOOD3PLOT_HOME")
    if home:
        cands.append(Path(home) / "VERSION")
    cands.append(Path("/opt/kood3plot/VERSION"))
    for vf in cands:
        try:
            for line in vf.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("Version:"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            continue
    return ""


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


class Package:
    """객체·관계를 모으며 바로 어휘로 검사하고, `finish()` 에서 참조를 맞춰 본다."""

    def __init__(self, *, scenario_kind: str, units: Units, adapter: str,
                 source_kind: str = "", source_file: str = "", source_sha256: str = ""):
        self.units = units
        self.adapter = adapter
        self.scenario_kind = scenario_kind
        self.source = {"kind": source_kind, "file": source_file, "sha256": source_sha256}
        self._types = V.types_by_slug()
        self._rels = V.relations_by_slug()
        self._props = {slug: {p["key"]: p for p in t["properties"]} for slug, t in self._types.items()}
        self.objects: list[dict] = []
        self.relations: list[dict] = []
        self._obj_index: dict[tuple[str, str], dict] = {}
        self._rel_seen: set[tuple] = set()
        self.faults: list[str] = []

    # ── 객체 ────────────────────────────────────────────────────────────
    def has(self, type_slug: str, key: str) -> bool:
        return (type_slug, key) in self._obj_index

    def add(self, type_slug: str, key: str, label: str, props: dict) -> dict | None:
        """객체 하나. 값이 None 인 칸은 뺀다. 수치는 단위를 맞춘다."""
        where = f"{type_slug} {key!r}"
        if type_slug not in self._types:
            self.faults.append(f"{where}: 어휘에 없는 타입")
            return None
        if not key:
            self.faults.append(f"{where}: 키가 비었다")
            return None
        if (type_slug, key) in self._obj_index:
            self.faults.append(f"{where}: 같은 키가 두 번")
            return None
        spec = self._props[type_slug]
        out = {}
        for k, v in props.items():
            if v is None:
                continue
            p = spec.get(k)
            if p is None:
                self.faults.append(f"{where}: 어휘에 없는 속성 {k!r}")
                continue
            cv = self._check_value(where, p, v)
            if cv is not None:
                out[k] = cv
        obj = {"type": type_slug, "key": key, "label": str(label or key), "properties": out}
        self.objects.append(obj)
        self._obj_index[(type_slug, key)] = obj
        return obj

    def _check_value(self, where: str, p: dict, v):
        dt = p["data_type"]
        k = p["key"]
        if dt == "number":
            if not _is_number(v):
                self.faults.append(f"{where}.{k}: 수가 아니다({v!r})")
                return None
            v = self.units.convert(p.get("unit"), v)
            # 셈한 통계의 이진 잡음(0.60436000000000005)만 걷는다 — 12자리는 원값(float32·6자리)보다 넉넉하다
            return float(f"{v:.12g}") if isinstance(v, float) else v
        if dt == "bool":
            if not isinstance(v, bool):
                self.faults.append(f"{where}.{k}: 참/거짓이 아니다({v!r})")
                return None
            return v
        if dt == "enum":
            if v not in p.get("enum_options", []):
                self.faults.append(f"{where}.{k}: 열거값 밖({v!r})")
                return None
            return v
        if dt in ("text", "text_long", "url", "object_ref"):
            if not isinstance(v, str) or not v:
                self.faults.append(f"{where}.{k}: 글자가 아니거나 비었다({v!r})")
                return None
            return v
        if dt in ("date", "datetime"):
            try:
                datetime.fromisoformat(str(v))
            except ValueError:
                self.faults.append(f"{where}.{k}: ISO 시각이 아니다({v!r})")
                return None
            return str(v)
        self.faults.append(f"{where}.{k}: 만드는 쪽이 다루지 않는 종류 {dt}")
        return None

    # ── 관계 ────────────────────────────────────────────────────────────
    def relate(self, relation: str, src: tuple[str, str], dst: tuple[str, str],
               props: dict | None = None) -> None:
        r = self._rels.get(relation)
        where = f"{relation} {src}→{dst}"
        if r is None:
            self.faults.append(f"{where}: 어휘에 없는 관계")
            return
        if relation in set(V.REF_RELATIONS.values()):
            self.faults.append(f"{where}: 참조 속성이 곧 이 관계다 — 줄로 싣지 않는다")
            return
        if src[0] not in r["src_type_slugs"] or dst[0] not in r["dst_type_slugs"]:
            self.faults.append(f"{where}: 이 관계가 잇지 않는 타입")
            return
        ident = (relation, src[0], src[1], dst[0], dst[1])
        if ident in self._rel_seen:
            self.faults.append(f"{where}: 같은 관계가 두 번")
            return
        self._rel_seen.add(ident)
        self.relations.append({"relation": relation, "src": [src[0], src[1]],
                               "dst": [dst[0], dst[1]], "properties": dict(props or {})})

    # ── 마무리 ──────────────────────────────────────────────────────────
    def finish(self) -> dict:
        """필수값·참조·관계 끝점을 맞춰 보고 꾸러미 dict 를 돌려준다. 흠이 있으면 PackageError."""
        faults = list(self.faults)
        for obj in self.objects:
            t, key, props = obj["type"], obj["key"], obj["properties"]
            for p in self._types[t]["properties"]:
                k = p["key"]
                if (t, k) in V.FILLED_AT_INGEST:
                    continue
                if p.get("required") and k not in props:
                    faults.append(f"{t} {key!r}: 필수 속성 {k!r} 가 없다")
                if p["data_type"] == "object_ref" and k in props:
                    to = p["ref_type_slug"]
                    if (to, props[k]) not in self._obj_index:
                        faults.append(f"{t} {key!r}.{k}: 가리키는 {to} {props[k]!r} 가 꾸러미에 없다")
        for r in self.relations:
            for end in (r["src"], r["dst"]):
                if tuple(end) not in self._obj_index:
                    faults.append(f"{r['relation']}: 끝 {end} 가 꾸러미에 없다")
        if faults:
            raise PackageError(faults)

        counts_o: dict[str, int] = {}
        for o in self.objects:
            counts_o[o["type"]] = counts_o.get(o["type"], 0) + 1
        counts_r: dict[str, int] = {}
        for r in self.relations:
            counts_r[r["relation"]] = counts_r.get(r["relation"], 0) + 1
        return {
            "format": FORMAT, "format_version": FORMAT_VERSION,
            "vocabulary": {"group": V.GROUP, "version": V.VERSION, "sha256": V.sha256()},
            "producer": {"tool": "koo_deep_report.ontology", "adapter": self.adapter,
                         "version": module_version(),
                         "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")},
            "source": self.source,
            "scope": {"scenario_kind": self.scenario_kind, "campaign_key": "campaign"},
            "units": self.units.header(),
            "counts": {"objects": counts_o, "relations": counts_r},
            "ref_relations": [{"type": t, "property": k, "relation": r}
                              for (t, k), r in V.REF_RELATIONS.items()],
            "objects": self.objects,
            "relations": self.relations,
        }


def write(doc: dict, path: str | Path) -> Path:
    """꾸러미를 쓴다 — 임시 파일에 쓰고 바꿔 끼워, 반쯤 쓴 파일이 남지 않게 한다."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    os.replace(tmp, path)
    return path
