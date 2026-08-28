# 미리보기 캐시(impactor_preview.json)의 stale 판정과 원자적 재생성을 담당하는 모듈
"""자세 미리보기 캐시의 신선도 관리.

이전 구현은 `원본.k mtime > 캐시 mtime` 하나로 판정했는데 세 가지를 놓쳤다.

1. 생성(make_stl/KeywordMeshParser)은 `*INCLUDE` 를 깊이 8까지 따라가 형상을
   만드는데, 판정은 마스터 덱 한 개의 mtime 만 봤다. 실무 LS-DYNA 덱은 형상이
   인클루드 파일에 있고 마스터는 잘 안 바뀌므로 정면으로 어긋난다.
2. mtime 은 생성 **파라미터**(파트 필터·해상도 등)를 담지 못한다.
3. 판정과 실행이 분리돼 있어, "stale 이다" 라고 판정한 뒤 재생성에 실패하면
   그 사실이 아무에게도 전달되지 않았다. 게다가 먼저 지우고 나서 만들었기 때문에
   도구가 없는 환경에서는 미리보기가 통째로 사라졌다.

여기서는 소스 파일 집합 + 파라미터를 함께 담은 **서명(stamp)** 을 캐시 옆에 두고
비교하며, 재생성은 임시 접두로 만든 뒤 검증에 성공했을 때만 원자적으로 바꾼다.
실패하면 기존 캐시를 그대로 두고 사유를 note 로 돌려준다.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

INCLUDE_DEPTH = 8


def keyword_source_files(root: Path, depth: int = INCLUDE_DEPTH) -> list[Path]:
    """`*INCLUDE` 를 따라간 소스 파일 전체 (root 포함, 존재하는 것만).

    make_stl 이 쓰는 KeywordMeshParser 와 같은 규칙 — 상대경로는 자기 파일 기준,
    깊이 제한 8. 순환 참조는 방문 집합으로 끊는다.
    """
    out: list[Path] = []
    seen: set[str] = set()

    def walk(path: Path, d: int) -> None:
        try:
            rp = str(path.resolve())
        except OSError:
            return
        if rp in seen or d > depth:
            return
        seen.add(rp)
        if not path.is_file():
            return
        out.append(path)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        in_include = False
        for line in text.splitlines():
            st = line.strip()
            if not st or st.startswith("$"):
                continue
            if st.startswith("*"):
                in_include = st.upper().startswith("*INCLUDE")
                continue
            if in_include:
                inc = Path(st)
                if not inc.is_absolute():
                    inc = path.parent / inc
                walk(inc, d + 1)

    walk(root, 0)
    return out


def make_stamp(sources: list[Path], params: dict) -> dict:
    """소스 파일별 (mtime, size) + 생성 파라미터로 이루어진 서명."""
    files = {}
    for p in sources:
        try:
            st = p.stat()
            files[str(p)] = [int(st.st_mtime), int(st.st_size)]
        except OSError:
            files[str(p)] = None      # 사라진 소스도 상태 변화로 취급한다
    return {"files": files, "params": params}


def read_stamp(stamp_path: Path) -> dict | None:
    try:
        return json.loads(stamp_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def regenerate(tool: Path, build_args, base: Path, name: str, stamp: dict,
               timeout: int = 300) -> str | None:
    """임시 접두로 생성 → 검증 → 원자 교체. 성공하면 None, 실패하면 사유 문자열.

    실패 시 기존 캐시는 손대지 않는다 — 대체물을 확보하기 전에 파괴하지 않는다.
    """
    tmp_prefix = base / f".{name}.tmp{os.getpid()}"
    tmp_json = Path(str(tmp_prefix) + ".json")
    tmp_stl = Path(str(tmp_prefix) + ".stl")

    def _cleanup() -> None:
        for p in (tmp_json, tmp_stl):
            try:
                p.unlink()
            except OSError:
                pass

    try:
        r = subprocess.run([str(tool)] + build_args(str(tmp_prefix)),
                           capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        _cleanup()
        return f"make_stl 실행 실패 ({type(e).__name__})"
    if r.returncode != 0:
        tail = (r.stdout or b"").decode("utf-8", "replace").strip().splitlines()
        _cleanup()
        return f"make_stl 실패 (exit {r.returncode}): {tail[-1] if tail else '메시지 없음'}"
    if not tmp_json.is_file():
        _cleanup()
        return "make_stl 이 JSON 을 남기지 않음"
    try:
        json.loads(tmp_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        _cleanup()
        return f"생성된 JSON 이 손상됨 ({type(e).__name__})"

    try:
        os.replace(tmp_json, base / f"{name}.json")
        if tmp_stl.is_file():
            os.replace(tmp_stl, base / f"{name}.stl")
        (base / f".{name}.stamp.json").write_text(
            json.dumps(stamp, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        _cleanup()
        return f"캐시 교체 실패 ({type(e).__name__}) — 기존 미리보기를 유지함"
    return None


def ensure_fresh(base: Path, name: str, sources: list[Path], params: dict,
                 tool: Path | None, build_args) -> str | None:
    """캐시를 최신으로 맞춘다. 반환값은 사용자에게 알릴 note (없으면 None).

    - 서명이 일치하면 아무것도 하지 않는다.
    - 다르거나 서명이 없으면 재생성을 시도한다.
    - 재생성 실패 시 기존 캐시를 유지하되 사유를 알린다 (무음 금지).
    """
    cache = base / f"{name}.json"
    stamp_path = base / f".{name}.stamp.json"
    want = make_stamp(sources, params)
    have = read_stamp(stamp_path)

    if cache.is_file() and have == want:
        return None

    if tool is None:
        if cache.is_file():
            return ("미리보기 캐시가 현재 모델과 일치하는지 확인할 수 없습니다 "
                    "(make_stl 없음) — 형상이 옛 리비전일 수 있습니다")
        return "make_stl 을 찾을 수 없어 실형상 미리보기를 만들지 못했습니다"

    err = regenerate(tool, build_args, base, name, want)
    if err is None:
        return None
    if cache.is_file():
        return f"미리보기 갱신 실패 — 기존(옛) 형상을 그대로 표시합니다. 사유: {err}"
    return f"실형상 미리보기를 만들지 못했습니다. 사유: {err}"
