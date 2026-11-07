# 화면 없는 렌더(pyvista)를 위한 Xvfb — 비어 있는 화면 번호를 골라 띄우고, 끝나면 끈다
"""LS-PrePost 워커가 :10, :11 … 을 쓰므로 여기서는 :140 부터 빈 번호를 찾는다(`/tmp/.X<n>-lock` 이 없는 것).
이미 DISPLAY 가 있고 이 머신의 X 소켓이 살아 있으면 그것을 쓴다(사람이 화면 앞에서 돌릴 때). 원격 DISPLAY(SSH X 포워딩
`localhost:10.0` 등)나 소켓이 없는 낡은 값이면 쓰지 않고 Xvfb 를 띄운다 — 포워딩 위 오프스크린 GL 은 실패하거나 느리다.
"""
from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import time
from pathlib import Path


def local_alive(d: str | None) -> bool:
    """':N' · 'unix:N' 꼴이고 /tmp/.X11-unix/XN 이 있으면 참."""
    m = re.fullmatch(r"(?:unix)?:(\d+)(?:\.\d+)?", d or "")
    return bool(m) and Path(f"/tmp/.X11-unix/X{m.group(1)}").exists()


def xvfb_cmd(exe: str, n: int, size: str) -> list[str]:
    """Xvfb 명령.

    - `-noreset` — 기본 Xvfb 는 마지막 클라이언트가 끊길 때 서버를 리셋한다(약 60 ms). 그림 한 겹마다 Plotter 를 열고 닫으므로
      다음 겹이 1.6~2.0 ms 만에 리셋 도중으로 들어오고, 그 연결이 리셋에 함께 닫히면 VTK 가 「bad X server connection」 으로
      abort() 한다 — 파이썬 예외가 아니라 deep 리포트 전체가 rc 134 로 죽었다(2026-11-07 배포 세션 실측, 부하 높을 때 22판 중 5판).
    - `setpriv --pdeathsig TERM` — 부모(이 파이썬)가 abort · earlyoom 으로 죽어도 Xvfb 가 고아로 남지 않게(남으면 apptainer 마운트를
      붙잡아 squashfuse 종료가 늦어진다). setpriv 가 없으면 그냥 띄운다.
    """
    cmd = [exe, f":{n}", "-screen", "0", size, "-nolisten", "tcp", "-noreset"]
    sp = shutil.which("setpriv")
    return [sp, "--pdeathsig", "TERM", "--", *cmd] if sp else cmd


@contextlib.contextmanager
def display(first: int = 140, last: int = 239, size: str = "2560x1600x24"):
    if local_alive(os.environ.get("DISPLAY")):
        yield os.environ["DISPLAY"]
        return
    exe = shutil.which("Xvfb")
    if exe is None:
        raise RuntimeError("Xvfb 가 없다 — 화면 없이 그림을 그릴 수 없다")
    proc = None
    for n in range(first, last + 1):
        if Path(f"/tmp/.X{n}-lock").exists() or Path(f"/tmp/.X11-unix/X{n}").exists():
            continue
        proc = subprocess.Popen(xvfb_cmd(exe, n, size), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):                                  # 소켓이 생길 때까지(최대 5 s)
            if Path(f"/tmp/.X11-unix/X{n}").exists() or proc.poll() is not None:
                break
            time.sleep(0.1)
        if proc.poll() is None:
            break
        proc = None                                          # 그 번호를 남이 막 잡았다 — 다음 번호
    if proc is None:
        raise RuntimeError(f"Xvfb 를 띄울 빈 화면 번호가 없다(:{first}–:{last})")
    old = os.environ.get("DISPLAY")
    os.environ["DISPLAY"] = f":{n}"
    try:
        yield os.environ["DISPLAY"]
    finally:
        if old is None:
            os.environ.pop("DISPLAY", None)
        else:
            os.environ["DISPLAY"] = old
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
