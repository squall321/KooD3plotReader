# 핫스팟 고도화 배선 요청서 — 엔진의 기준 7종·시간 집계가 `koo_deep_report` 에서 막혀 있다

**보내는 쪽**: pyKooCAE(KooChainRun 자동 후처리) · SmartTwinMCP(:5013) — 세션 `pykoocae-53`
**받는 쪽**: KooD3plotReader — `python/koo_deep_report`(+`koo_sphere_report`), `docs/hotspot_envelope_3d`
**작성일**: 2026-10-16
**한 줄**: 9월에 엔진(`unified_analyzer`)에 넣은 기준 4종(max_shear·x/y/z_tension)과 시간 집계가
표준 경로인 `koo_deep_report` 에서 거절돼, deep report HTML·KooChainRun 자동 후처리·MCP 어디서도 쓸 수 없다.
그리고 3D 인벨롭을 마무리해 달라(사용자 결정 2026-10-16).
**성격**: 기능 배선 요청 둘(§1·§2). 설계와 우선순위는 이 리포가 정한다 — 아래는 근거와 우리가 먹는 모양이다.

| § | 무엇 | 누가 | 급함 |
|---|---|---|---|
| 1 | `koo_deep_report` 가 기준 7종·시간 집계를 받아 엔진에 넘기기 | KooD3plotReader | 🔴 먼저 |
| 2 | 3D 인벨롭 마무리 (G1~G6) | KooD3plotReader | 다음 |
| 3 | 배포·순서 — 무거운 빌드가 겹치지 않게 | 양쪽 | — |
| 4 | 우리 쪽에서 하는 것 | pyKooCAE·MCP | 참고 |

---

## 1. 🔴 기준 4종·시간 집계가 표준 경로에서 막혀 있다 (배포본 실측)

**엔진은 된다** — 배포본(호스트 `2df44eb`, 노드 3대 Post SIF `3992a94`)에서

```
$ unified_analyzer --capabilities
    "criteria": ["von_mises", "max_principal", "min_principal", "max_shear", "x_tension", "y_tension", "z_tension"],
    "time_aggregate": ["elemmax_then_mean", "mean_then_timemax", "both"]
```

**`koo_deep_report` 는 거절한다**

```
$ koo_deep_report <run>/Output --hotspot-clusters --hotspot-criterion max_shear --no-render --output out
[koo_deep_report] --hotspot-criterion: 알 수 없는 기준량 'max_shear' (허용: von_mises, max_principal, min_principal)
rc=1
```

원인 — `python/koo_deep_report/koo_deep_report/__main__.py`

- `:793` `_HOTSPOT_CRITERIA = ("von_mises", "max_principal", "min_principal")` — 엔진에 기준을 더한 커밋
  (f686483 x/y/z_tension, 81304f8 max_shear)은 C++·C++ 시험만 고쳤고 이 목록은 그대로였다.
- `:826-837` 엔진 설정을 인자 6개(`enabled`·`top_percent`·`distance_factor`·`min_elements`·`max_clusters`·
  `criterion`)로만 만든다 — `time_aggregate` 를 넘기는 길이 없다.
- `:681` YAML 에서는 `hotspot_clusters.criterion`(단수)만 읽는다. 그런데 회신 문서
  `docs/postproc_gap_2026-09/reply-to-gap-report.md:218-221` 은 7종을 쓰는 법으로 **`criteria`(복수)·
  `time_aggregate`** 를 안내했다 — 그 YAML 은 엔진을 직접 부를 때만 통한다.

그래서 지금은 deep report HTML, KooChainRun 자동 후처리(`postprocess.hotspot_*`), MCP `post_deep_report` 어디서도
새 기준을 쓸 수 없다. MCP `post_unified_analyzer`(엔진 직접)로만 되는데 그건 HTML 리포트가 없다.

**요청**

1. `_HOTSPOT_CRITERIA` 를 엔진과 같은 7종으로. 다시 어긋나지 않게 **`unified_analyzer --capabilities` 에서 읽는**
   쪽을 권한다(별칭도 엔진과 같게 — `tau_max`·`tresca`, `sxx`·`sigma_yy` 등).
2. 시간 집계를 CLI 와 YAML 양쪽으로 — **제안 이름 `--hotspot-time-aggregate {elemmax_then_mean,mean_then_timemax,both}`**,
   YAML `hotspot_clusters.time_aggregate`. 엔진 설정까지 넘긴다(batch 경로 `_run_one` 도 — `:826` 주석의 복제 함정).
3. YAML `hotspot_clusters.criteria`(목록)도 받기 — 회신 문서가 그 이름으로 안내했다. `criterion` 은 그대로 두고 둘 다.
4. deep report HTML 핫스팟 탭과 sphere 리포트가 새 기준 항목(파트×기준)을 그린다.
5. `--help` 문구 갱신 — MCP 도구 설명이 이 도움말에서 생성된다.

**이름이 정해지면 먼저 알려 달라.** 우리는 그 이름 그대로 KooChainRun 키를 배선한다
(`postprocess.hotspot_criterion` 7종, `postprocess.hotspot_time_aggregate` → `--hotspot-time-aggregate`).
이름을 먼저 박으면 배포 전 deep report 가 모르는 인자로 거절해 자동 후처리가 깨지므로, **귀측 배포 뒤에** 넣는다.

**verify(제안)** — 배포 바이너리로, 작은 d3plot 에서
`koo_deep_report … --hotspot-clusters --hotspot-criterion max_shear,x_tension --hotspot-time-aggregate both`
→ 결과 JSON 의 핫스팟 항목에 두 기준이 있고 HTML 탭에 그려진다. 모르는 이름은 지금처럼 즉시 거절.

## 2. 3D 인벨롭 마무리 (사용자 결정 2026-10-16)

`docs/hotspot_envelope_3d/checklist.md` 기준 17개 완료·19개 남음 — G0(데이터 경로)·G5(소성일·색 척도)는 끝났고,
화면 쪽이 남았다.

- G1 파트 메쉬(`make_stl` 지정 파트, 리포트 임베드)
- G2 자체 캔버스 3D 뷰어(회전·줌, 반투명 메쉬+구 깊이 정렬, 각도+순위 라벨, 각도 on/off)
- G3 Plotly 번들 옵션·**deep report 오프라인화**(`cdn.plot.ly` 제거)
- G4 각도 선택(26방향 프리셋·커스텀·전체)
- G6 컨투어(리스크 맵)
- 마무리(실데이터·회귀·오프라인 검증)

계획(`plan.md`)대로 진행해 달라. **새 CLI 옵션이 생기면 이름을 알려 달라**(예: `--viewer`, 각도 프리셋) —
KooChainRun `postprocess` 키와 MCP 도구가 그것을 따른다.

## 3. 배포·순서

- 귀측 릴리스(호스트 `/data/SmartTwinPostprocessor` + Post SIF + tar + 노드 배포)는 귀측 절차대로.
- **무거운 빌드는 한 번에 하나** — 이 서버에서 OOM 을 낸 적이 있다. Post SIF 빌드를 **시작할 때와 끝날 때**
  `pykoocae-53` 에 알려 달라. 우리 pyKooCAE 빌드(KMM·KooChainRun, 약 1시간)는 귀측 §1 배포 뒤 한 번에 한다.
- §1 배포가 끝나면 → 우리가 KooChainRun 키 배선 → 빌드·SIF → MCP 재생성 → 배포본 e2e 를 하고 결과를 알린다.

## 4. 우리 쪽에서 하는 것 (참고)

- KooChainRun 자동 후처리에 `postprocess.hotspot_part` → `koo_sphere_report --hotspot-part`
  (sphere 리포트는 dc62991 부터 이미 지원. 자동 후처리에만 없었다)
- KooChainRun 도움말(`--help postprocess_json`)에 `hotspot_*` 키 문서화 → MCP 시나리오 도구 설명 재생성
- §1 이름 확정·배포 뒤 — 기준 7종·시간 집계 키
