# 갭 문서 회신 — A-1 정정과 대응 결과

- **수신**: 박국진 (koo.park)
- **회신일**: 2026-09-16
- **대상 문서**: `SmartPostProcessor — 후처리 분석 기능 갭 정리` (2026-09-13)

---

## 1. A-1 은 갭이 아니었습니다 — 원인은 배포 진단입니다

**핵심 기능은 2026-09-11 에 이미 들어갔고 node001 에도 배포돼 있었습니다.**

| 확인 | 실제 |
|---|---|
| node001 `SmartTwinPostprocessor.sif` | 2026-09-11 18:17 = v32 (`4815f55`) |
| SIF 안 `/opt/kood3plot/VERSION` | `4815f55` / 09-11 — **정확** |
| SIF 안 소스 `HotspotClusterAnalyzer.hpp` | `HotspotCriterion{VonMises, MaxPrincipal, MinPrincipal}` **있음** |
| `--hotspot-criterion C[,C]` CLI | **있음** (`78b9a55`, 09-11) |
| 호스트 `/data/SmartTwinPostprocessor/VERSION` | `eaffe54` / 08-28 — **2주 묵은 거짓** |

문서가 인용한 `HotspotClusterAnalyzer.hpp:33  /// 현재 "von_mises" 만 지원` 은
`6d16634`(2026-09-08) 판입니다. **줄 번호까지 정확히 일치**합니다.

### 왜 옛 소스를 보게 됐나

```
tar tzf …_v29.tar.gz | grep 'SmartTwinPostprocessor/VERSION$'  → 1개
tar tzf …_v30.tar.gz (09-08)                                   → 0개
tar tzf …_v31 / v32                                            → 0개
```

`build_module.sh` 는 `VERSION` 을 정상 생성합니다(SIF 안은 맞았습니다). 그런데
**배포 tar 를 묶는 절차가 리포지토리에 없었습니다.** 손으로 묶다가 v30 에서
`VERSION` 이 빠졌고, tar 를 풀어도 호스트의 옛 `VERSION` 이 덮이지 않아 08-28 에
고착됐습니다.

**즉 도구가 아니라 "무엇이 설치돼 있는지 확인하는 수단" 이 거짓말을 했습니다.**
그래서 이번 대응의 1순위를 기능 추가가 아니라 그 수단을 고치는 데 뒀습니다.

### 지금은 이렇게 확인하실 수 있습니다

```bash
unified_analyzer --capabilities        # 지원 기준량·기능을 실행 파일이 직접 답합니다
verify_deploy.sh /data/SmartTwinPostprocessor <sif>   # VERSION ↔ 바이너리 대조
```

작업 시작 때 이 명령은 **실패 3건**이었고(호스트 `eaffe54` vs SIF `4815f55`),
지금은 호스트·SIF·node001 모두 `d8fe2bb` 로 **전부 일치**합니다.

---

## 2. 항목별 대응

### A. 런 단위

| 항목 | 결과 |
|---|---|
| **A-1** 기준량 복수 | **이미 있었음** + `max_shear`·`x/y/z_tension` 추가 → **7종** |
| **A-2** 시간 집계 | `time_aggregate: {elemmax_then_mean｜mean_then_timemax｜both}` 추가 |
| **A-3** 소성 초과 영역 | `n_yield`/`vol_yield`/`sum_eps_vol`/`max_eps`/`plastic_work_total` — **top_percent 독립** |
| **A-4** elout | **교차 확인으로 구현** (아래 3절) |
| **A-5** 구간 분할 | `campaign_cli --segment-boxes seg.json` (박스 + 극좌표 부채꼴) |
| **A-6** 좌표 변환 | 역추정 유틸 완성, **배선은 보류** (아래 3절) |
| **A-7** 체적 계산 | 지적대로 PP 가 정확합니다(등매개 2×2×2 가우스). `elout_batch.py` 폐기 가능 |

**A-2 실측**: 기존 `mean_e(max_t)` 대비 `max_t(mean_e)` 비율이 최소 0.6648 —
**최대 34% 과대평가**였습니다. "서로 다른 시각의 피크를 합성한다" 는 지적이
실측으로 확인됐습니다.

**A-3 주의**: 지적하신 `volume` 의 `top_percent` 종속 문제는, 저희가 09-13 에 넣은
`energy_total`(소성일)에도 **그대로 있었습니다**. 둘 다 파트 단위 절대량으로
분리했습니다. 3% ↔ 5% 로 바꿔 돌려 **파트 절대량 34/34 동일**을 확인했습니다.

**ε_p 는 마지막 프레임이 아니라 이력 최댓값을 씁니다.** 문서는 "시간 단조증가라
마지막 프레임만 읽으면 된다" 고 했는데, 실덱에서 ε_p 가 감소하는 전이를
확인했습니다(42.9%). 단조를 가정하면 조용히 과소평가됩니다.

### B. 캠페인 단위

| 항목 | 결과 |
|---|---|
| **B-0** 캠페인 보고서 | `koo_scatter_report` 신설 — 그림 9종 |
| **B-1** 면 기준 편차각 | `dev_angle`/`dev_roll`/`dev_pitch`/`dev_yaw` |
| **B-2** 런 간 테이블 | `campaign_cli` → 롱포맷 TSV (20MB×N 재파싱 제거) |
| **B-3** 공통 DOE | `common_doe()` — 임계 미달이면 **거부**하고 **범인을 지목** |
| **B-4** 통계 검정 | 평균순위 검정(귀무 **코드 고정**)·Spearman·recall@k·구간 프로파일 |
| **B-5** ground truth | TSV 스키마 + `part_recall()` (선택 열 `x`/`y`/`z` 로 위치 오버레이) |
| **B-6** 메커니즘 판정 | 기준량 7종이 준비됐으므로 판정 규칙만 정하면 됩니다 |

**B-3 이 이렇게 말합니다**:
> 공통 DOE 가 27개로 임계 50개 미만입니다 — 이 표본으로는 리비전 간 수치를
> 비교할 수 없습니다. **'T4_PV1' 를 빼면 185개가 되므로, 그 케이스가 아직 다
> 돌지 않았는지 확인하세요**

교집합이 줄어든 사실 자체는 로그에 있었을 텐데 **누가 줄였는지**가 안 보여
아무도 알아채지 못했습니다. 케이스를 하나씩 빼 보고 회복량으로 범인을 짚습니다.

**B-4 귀무가설은 코드에 고정했고, 산출물에 함께 적습니다.**
`(N+1)/(k+1)` 은 *k개 중 최솟값*의 기대값이라 평균순위와 비교할 수 없습니다.

> 파트 7: 평균순위 1.00 (귀무 4.00) · p=0.0004165 [exact] ★
> 귀무가설: 각 시행의 순위가 1..N 에서 균등·독립 (평균순위 기대값 (N+1)/2)

다만 문서의 **p=0.016 은 재현되지 않았습니다.** N=6·k=4 에서 나머지 한 과제가
3위면 0.0116, 4위면 0.0270 입니다. 조건(면 수·양측 여부)을 알려주시면 맞춰
보겠습니다. 구현 정확성은 전수 열거(1296경우)로 `P(p ≤ v) == v` 오차 0 을
확인했습니다.

### C. 그림 9종

`koo_scatter_report` 가 전부 냅니다 — **외부 라이브러리 없이 SVG** 입니다.
기존 보고서는 Plotly 를 CDN 에서 받는데, 망이 막히면 그림이 통째로 사라지고
화면에 아무 말도 남지 않습니다.

```bash
koo_scatter_report <test_dir> -o scatter.html \
    --ground-truth ng.tsv --segments seg.json
post_analyze <test_dir> --scatter          # 파이프라인에 붙여 쓰실 수도 있습니다
```

---

## 3. 못 한 것과 그 이유

### A-4 는 "소스 전환" 대신 "교차 확인" 으로 했습니다

소스를 elout 으로 바꾸면 요소 선별·군집·기하를 전부 elout 기준으로 다시 맞춰야
하는데, **검증할 덱이 없습니다.** 저희가 가진 실덱 두 개 모두 binout 에 `elout`
분기가 없습니다(`*DATABASE_ELOUT` 미설정).

검증 없이 구현하면 조용히 틀리는 코드가 됩니다. 실제로 이번 작업에서 셸 층
stride 를 추측해 썼다가 **50배 틀린** 적이 있습니다(정의상 참인 부등식으로
잡았습니다).

그래서 문제의 본질("출력 간격이 성기면 피크를 놓친다")만 남겨 풀었습니다 —
`campaign_cli --elout-check` 가 d3plot 피크와 elout 피크를 견주어 **"놓쳤을 수
있다" 를 알립니다.** 파싱부와 계산부를 분리해, 계산부는 합성 데이터로 완전히
검증했습니다.

**elout 을 켠 덱을 하나 주시면** 파싱부까지 실데이터로 맞추고, 필요하면 소스
전환도 진행하겠습니다.

### A-6 은 구현했습니다 (처음 회신의 "보류" 를 정정합니다)

처음에 "원본 덱 경로를 얻을 규약이 없어 보류" 라고 적었는데 **틀렸습니다.**
runner_config.json 의 `model_file` 을 따라가는 규칙이 sphere 리포트에 이미 있었습니다.

```bash
python3 -m koo_deep_report.campaign_cli <test_dir> --coord-transform -o metrics.tsv
```

- KMM 이 노드 ID 를 보존하므로, 원본 모델과 런 덱(`DropSet.k`)의 `*NODE` 를 같은
  ID 끼리 대응시켜 변환을 추정합니다. 런 표(`*_runs.tsv`)에 `ct_dx/ct_dy/ct_dz/
  ct_rot_deg/ct_max_residual` 이 실리고, 덩어리 중심의 **도면 좌표**가
  `c1_center_src_x/y/z` 지표로 실립니다 — 역추적이 필요 없습니다
- Test_001 실측: 평행이동 (−35.5, −73.5, −4.5), 회전 0°, 최대잔차 7.2e-08.
  자세는 모델을 돌리지 않고 중력 방향으로 줍니다
- **원본 모델에 없는 파트(KMM 이 붙인 바닥·벽)는 도면 좌표를 내지 않습니다**
- `DropSet.k` 좌표가 d3plot 초기 형상과 ID 전부·좌표 5.4e-06 이내로 일치함을
  확인했습니다(런 덱 좌표계 = 결과 좌표계)

`analysis_result.json > metadata` 에 직접 넣지 않은 이유 — 그 파일은 C++ 해석기가
쓰고, 키워드 덱 파싱을 C++ 에 넣는 비용에 비해 얻는 게 없습니다. 캠페인 표에 런별로
실리므로 후단이 할 일은 같습니다.

### ⚠ 9/13~9/16 사이 CLI 래퍼 결함 (저희 배포 실수)

9/13 배포에서 호스트의 `koo_*_report` 래퍼를 잘못된 형식으로 덮어써,
**env.sh 를 source 하지 않고 실행하면** `No module named …` 로 실패했습니다
(source 하면 동작했습니다). 9/16 배포로 복구했고, 이제 배포 검증기가 래퍼를
환경변수 없이 실제로 실행해 봅니다. 그 기간에 이상한 실패가 있었다면 이것입니다.
v33 아카이브에도 같은 결함이 있으니 **v34 이상**을 쓰세요.

---

## 4. 덤으로 발견한 것

**이 캠페인의 꼭짓점 8방향이 꼭짓점이 아닙니다.**
`Test_001_Full26_1Step` 을 분류해 보니 면 6 / 모서리 12 / **격자 벗어남 8** 입니다.
꼭짓점이어야 할 방향이 `(±0.707, ±0.5, ±0.5)` 로, 진짜 꼭짓점 `(±0.577)³` 에서
**9.7356°** 벗어나 있습니다. 코너 각도를 45° 로 둔 옛 도구의 결함이고(상류에서
이미 수정·머지됨), 이 캠페인은 2026-02-07 생성이라 수정 전 판입니다.

결과만 봐서는 알 수 없는 종류라, `campaign_cli` 가 기계적으로 잡도록 했습니다.

```
[campaign] ⚠ 26방향 격자에서 벗어난 런 8개 — 코너 각도 결함이 있던 도구로
           만든 캠페인일 수 있습니다
```

**JSON 이 작은 값을 0 으로 만들고 있었습니다.** `analysis_result.json` 이
소수점 8자리 고정이라 ε_p(1e-6)는 유효숫자 3자리만 남고, 1e-9 이하는
`0.00000000` 이 되어 **진짜 0 과 구분되지 않았습니다.** 유효숫자 10자리로
고쳤습니다.

---

## 5. 지금 쓰실 수 있는 것

배포는 끝났습니다(호스트·SIF·node001 모두 같은 판 — `unified_analyzer --capabilities` 로 확인).

```bash
source /data/SmartTwinPostprocessor/env.sh

# 무엇이 설치돼 있는지 — 소스를 읽지 않고 확인
unified_analyzer --capabilities

# 캠페인 점검 + 롱포맷 테이블 (20MB×N 재파싱 없이)
python3 -m koo_deep_report.campaign_cli <test_dir> -o metrics.tsv
python3 -m koo_deep_report.campaign_cli <test_dir> --check-only     # 각도·빌드 건전성
python3 -m koo_deep_report.campaign_cli <test_dir> --segment-boxes seg.json
python3 -m koo_deep_report.campaign_cli <test_dir> --elout-check
python3 -m koo_deep_report.campaign_cli <test_dir> --coord-transform   # 도면 좌표

# 각도 산포 리포트 (그림 9종)
koo_scatter_report <test_dir> -o scatter.html --ground-truth ng.tsv

# 기준량 7종을 쓰려면 (YAML)
#   hotspot_clusters:
#     criteria: [von_mises, max_principal, min_principal, max_shear, x_tension]
#     time_aggregate: both
```

폐기 가능한 임시코드: `elout_batch.py`(344줄, A-3+A-7), `face_core.py`·
`make_face_report.py`의 통계·편차각·공통DOE 부분(B-1/B-3/B-4), `plot_*.py`(C).
`elout_pass2.py`(A-5)는 구간 정의를 JSON 으로 옮기시면 대체됩니다.

문의나 이상한 점이 있으면 알려주세요.
