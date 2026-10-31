# DynaForge 해석 결과 어휘(cae_*)의 바이트 사본을 읽는 모듈 — 정본은 DynaForge platform/core/ontology/dynaforge-cae.json
"""해석 결과 어휘 — 구조·충격해석 개념을 DynaForge 온톨로지 타입·관계로 묶은 것.

**정본은 DynaForge 에 있다**(2026-10-31 사용자 결정). 이 패키지는 그 파일의 바이트 사본
(`dynaforge-cae.json`)을 읽고, 꾸러미 머리에 그 바이트의 sha256 을 싣는다. 받는 쪽은 자기 정본과
지문이 다르면 적재하지 않는다 — 그래서 고칠 때는 정본을 고치고 사본을 **바이트 그대로** 옮긴다
(다시 직렬화하면 지문이 바뀐다).

**값의 단위는 속성의 `unit` 글자가 정한다.** DynaForge 는 단위를 바꾸지 않고 글자만 보여 주므로,
꾸러미를 만드는 쪽이 값을 이 글자의 단위로 맞춰 싣는다(`package.py`). 단위 글자가 없는 수는 무차원이다.

여기 남는 파이썬 상수(UNIT_KINDS · FILLED_AT_INGEST · REF_RELATIONS)는 만드는 쪽의 규칙이다 —
SP 꼴에는 그 자리가 없다. 시험이 어휘 파일과 어긋나지 않는지 본다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

_FILE = Path(__file__).with_name("dynaforge-cae.json")
_BYTES = _FILE.read_bytes()
VOCABULARY = json.loads(_BYTES.decode("utf-8"))

#: 어휘 판 — 어휘 파일의 `_version`. 꾸러미 머리에 실린다.
VERSION = str(VOCABULARY.get("_version") or "")
GROUP = VOCABULARY["groups"][0]["slug"]

#: 속성 `unit` 글자 → 양의 종류. 꾸러미 작성기가 이것으로 환산 계수를 고른다.
UNIT_KINDS = {
    "MPa": "stress", "mm": "length", "s": "time", "mJ": "energy",
    "N": "force", "N·s": "impulse", "mm/s": "velocity",
}

#: 만드는 쪽이 채우지 않는 속성 — DynaForge 가 적재할 때 채운다(리포트 키를 모른다).
FILLED_AT_INGEST = {("cae_campaign", "report")}

#: 참조 속성이 곧 관계인 것(다대일). 꾸러미는 이 관계를 **줄로 싣지 않고** 속성으로만 싣는다 —
#: 대응표는 꾸러미 머리 `ref_relations` 에 실린다. 받는 쪽이 줄이 필요하면 거기서 긋는다.
REF_RELATIONS = {
    ("cae_run", "campaign"): "run_of",
    ("cae_part", "campaign"): "part_in_campaign",
    ("cae_part_response", "run"): "response_in",
    ("cae_part_response", "part"): "response_of",
    ("cae_load_transfer", "run"): "transfer_in",
    ("cae_load_transfer", "contact"): "transfer_via",
    ("cae_load_transfer", "from_part"): "transfer_from",
    ("cae_load_transfer", "to_part"): "transfer_to",
    ("cae_hotspot", "response"): "hotspot_of",
}


def dumps() -> str:
    """어휘 파일 그대로(다시 직렬화하지 않는다 — 지문이 바뀐다)."""
    return _BYTES.decode("utf-8")


def sha256() -> str:
    """꾸러미 머리에 싣는 어휘 지문 = 어휘 파일 바이트의 sha256."""
    return hashlib.sha256(_BYTES).hexdigest()


def types_by_slug() -> dict[str, dict]:
    return {t["slug"]: t for t in VOCABULARY["types"]}


def relations_by_slug() -> dict[str, dict]:
    return {r["slug"]: r for r in VOCABULARY["relation_types"]}
