# Section View YAML Examples

`koo_deep_report --config <file.yaml>` 형태로 사용.

| 파일 | 케이스 | per_part | target | backend |
|------|--------|----------|--------|---------|
| `01_per_part_all.yaml` | 모든 파트 일괄 단면뷰 | ✅ | — | lsprepost |
| `02_target_ids.yaml` | 특정 파트 ID만 | ❌ | `[4,5,6,19]` | lsprepost |
| `03_target_patterns.yaml` | 이름 패턴 매칭 | ❌ | `["*PKG*","*CELL*"]` | lsprepost |
| `04_overview_only.yaml` | 전체 모델 단면뷰만 | ❌ | — | lsprepost |
| `05_software_backend.yaml` | LSPrePost 없이 (SW 래스터라이저) | ❌ | — | software |
| `06_disabled.yaml` | 분석만, 단면뷰 OFF | — | — | — |

## 옵션 키 전체

```yaml
section_view:
  enabled: true                   # bool, default=false
  backend: lsprepost              # lsprepost | software, default=lsprepost
  mode: section                   # section | section_3d (software 전용), default=section
  axes: [x, y, z]                 # default=[x,y,z]
  fields: [von_mises, strain]     # von_mises | eps | strain | displacement | pressure | max_shear
  per_part: false                 # 모든 파트 개별 단면뷰
  target_part_ids: []             # 특정 파트 ID 리스트
  target_patterns: []             # 와일드카드 패턴 리스트
  fade: 0.0                       # 0=단색, >0=거리별 반투명
  sv_threads: 2                   # 병렬 단면뷰 렌더러 수
```

## 우선순위

CLI 플래그 > YAML > argparse default

CLI에서 명시한 옵션은 YAML 값을 덮어씁니다. 예:

```bash
# YAML에 axes:[x,y,z]가 있어도 CLI가 우선
koo_deep_report --config 01_per_part_all.yaml --section-view-axes z
```

## 출력 폴더 구조

```
report/
└── renders/
    ├── section_view_z/                       # overview (전체 모델)
    │   └── section_view.mp4
    ├── section_view_von_mises_part_4_z/      # per-part (개별 파트)
    │   └── section_view.mp4
    ├── section_view_von_mises_part_5_z/
    │   └── section_view.mp4
    └── ...
```

per_part=true이면 `_extract_part_ids(result)`가 분석 결과에서 자동으로
파트 ID를 수집해서 2nd render pass를 실행합니다.
