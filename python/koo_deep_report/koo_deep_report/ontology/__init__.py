# 후처리 결과를 DynaForge 해석 어휘(cae_*) 온톨로지 꾸러미로 내보내는 패키지
"""deep·sphere·impact 리포트 산출물 → `dynaforge.onto_package` (객체·관계 JSON).

- `vocabulary` : 어휘(SP import 꼴) — 정본은 DynaForge platform/core/ontology/dynaforge-cae.json,
  여기는 그 바이트 사본 `dynaforge-cae.json` 을 읽는다.
- `package`    : 어휘로 검증하며 짓는 작성기, 단위 정규화.
- `sphere` / `impact` / `deep` : 리포트별 어댑터.

CLI: ``python3 -m koo_deep_report.ontology {sphere|impact|deep|vocab} ...``
"""
from .package import FORMAT, FORMAT_VERSION, PackageError  # noqa: F401
