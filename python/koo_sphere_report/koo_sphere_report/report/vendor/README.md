# vendor — Plotly.js 부분 번들 (오프라인용)

리포트는 **단일 HTML 파일**이고 사내망·폐쇄망에서도 열려야 한다. `cdn.plot.ly`
를 쓰면 네트워크가 없을 때 차트가 **조용히** 빈 칸이 된다. 그래서 여기 둔 번들을
HTML 안에 그대로 넣는다.

| 파일 | 크기 | 들어 있는 트레이스 | 쓰는 곳 |
|---|---|---|---|
| `plotly-gl3d.min.js` | 1.6 MB | scatter · scatter3d · surface · mesh3d | `html_report.py` (핫스팟 3D 뷰어 `--viewer plotly`) |

**부분 번들을 바꿀 때 주의.** `gl3d` 에는 `bar` 가 없고 `basic` 에는 `mesh3d` 가
없다. 쓰는 쪽의 트레이스를 먼저 확인하고 고를 것 — 없는 트레이스는 예외 없이
**빈 차트**로 나온다.

출처: plotly.js v3.1.0 공식 dist (MIT, `LICENSE-plotly.txt`).
