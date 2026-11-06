# 리포트 그림 꾸러미 — d3plot 한 순간을 깔끔한 PNG · 호버 SVG 로, 표준 그림 묶음과 manifest 를 만드는 패키지
"""- `mesh`   : lasso 로 상태 하나를 읽어 파트별 바깥 면 · 요소 von Mises · 환경(바닥) 파트
- `camera` : 평행 투영 카메라(시점 · 화면 맞춤 · 투영) — PNG 와 SVG 가 같은 값을 쓴다
- `colors` : jet 색 지도 · 강건한 색 범위(p99.5) · 음영
- `scene`  : 타겟 · 주변(반투명) · 숨김 파트, 최대점, 카메라를 한 번 정한다
- `png`    : pyvista(VTK) 오프스크린 렌더(`xvfb.display()` 안에서)
- `svg`    : 벡터 SVG + 호버(파트 이름 · 값) — 외부 라이브러리 없음
"""
