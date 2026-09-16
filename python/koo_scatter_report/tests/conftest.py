# 시험이 형제 패키지(koo_impact_report 등)를 찾을 수 있게 경로를 잡아 주는 설정
"""pytest 공통 설정.

**왜 필요한가.**
배포본은 `env.sh` 가 PYTHONPATH 에 다섯 패키지를 모두 넣지만, 저장소에서
`python -m pytest` 로 한 패키지만 돌리면 형제 패키지가 안 보인다. 그러면
`_apply_unit_system` 이 "검출기 없음" 으로 조용히 넘어가 단위계 시험이
**환경 때문에** 실패한다 — 진짜 결함이 그 소음에 묻힌다.

여기서는 저장소 레이아웃(`python/<패키지>/`)을 찾아 형제 패키지를 경로에 넣는다.
저장소가 아니면(설치본 등) 아무것도 하지 않는다 — 그 환경에서는 이미 PYTHONPATH
가 잡혀 있거나, 없는 것이 사실이다.
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()

# tests/ → 패키지 루트 → python/ 디렉토리
_PY_DIR = _HERE.parent.parent.parent
if _PY_DIR.name == "python" and _PY_DIR.is_dir():
    for sib in sorted(_PY_DIR.iterdir()):
        # 패키지 디렉토리 안에 같은 이름의 모듈 폴더가 있는 것만 (venv 등 제외)
        if not sib.is_dir() or not (sib / sib.name).is_dir():
            continue
        p = str(sib)
        if p not in sys.path:
            sys.path.insert(0, p)
