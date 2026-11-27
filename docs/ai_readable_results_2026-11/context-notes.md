# AI 가 이해하는 결과 — 결정 · 사실 기록

## 2026-11-27 계획 수립

- **요청** — 「추가로 개발해야 하는, 시뮬 결과를 AI 가 이해할 수 있게끔 하는 것을 개발하는 계획을 더 세워봐」.
- **바탕을 잰 것**
  - 온톨로지 꾸러미(`report.ontology.json`, DynaForge `cae_*` 판 0.5)는 객체(런 · 파트 · 파트 응답 · 접촉 · 핫스팟 · 하중 경로)만 담는다 —
    ElasticBeam deep 꾸러미 4,959 B, 객체 10 · 관계 0. 서술 · 사건 · 품질 장부는 없다.
  - 소견(findings)은 sphere(`analyzer._generate_findings`) · impact(`analyzer.generate_findings`, solver_quality · 적재 문제 · 통계 이상치)에만 있고 deep 에는 없다.
  - `figures/manifest.json` 은 그림마다 값 · 시각 · 카메라 · 색 범위 · 캡션을 기계가 읽는 꼴로 담는다 — 브리프의 그림 색인으로 바로 쓸 수 있다.
  - SmartTwinMCP 도구 48개는 작업 제출 · 상태 · 로그 · 후처리 실행이고 결과를 묻는 도구가 없다(`tools/` 목록).
  - 시계열 솎기 `_extreme_indices`(deep html_report)가 이미 피크를 지킨다.
- **원칙으로 정한 것(plan §2)** — 원장이 정본, 결정적 생성(LLM 은 소비자), 없는 값은 사유 코드와 함께, 키는 DynaForge 정본과 같게.
- **아직 정하지 않은 것** — plan §5 다섯(언어 · 서술 방식 · MCP 범위 · 평가 LLM · DynaForge 계약).
