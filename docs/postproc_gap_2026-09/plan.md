# 후처리 갭 대응 계획 — 2026-09-13

## 0. 무엇이 실제로 일어났나

`SmartPostProcessor — 후처리 분석 기능 갭 정리`(박국진, 2026-09-13)의 **A-1
"핫스팟 선별 기준량이 von Mises 하나뿐"** 은 사실이 아니다. 기능은 2026-09-11 에
들어갔고 서버에도 배포돼 있었다.

| 확인 대상 | 실제 |
|---|---|
| node001 `SmartTwinPostprocessor.sif` | 2026-09-11 18:17 = v32 (`4815f55`) |
| SIF 안 `/opt/kood3plot/VERSION` | `4815f55` / 2026-09-11 — **정확** |
| SIF 안 `/opt/KooD3plotReader` 소스 | `HotspotCriterion{VonMises, MaxPrincipal, MinPrincipal}` **있음** |
| `--hotspot-criterion C[,C]` CLI | **있음** (`78b9a55`, 2026-09-11) |
| 호스트 `/data/SmartTwinPostprocessor/VERSION` | **`eaffe54` / 2026-08-28 — 2주 묵은 거짓** |
| 갭 문서가 인용한 `HotspotClusterAnalyzer.hpp:33` | `6d16634` (2026-09-08) 판. 줄 번호까지 일치 |

### 인과 사슬

1. `scripts/build_module.sh` 는 `${PREFIX}/VERSION` 을 **정상 생성**한다.
2. 그러나 배포 tar 를 만드는 절차가 **리포지토리에 없다**(수동 추정).
3. `v29`(8/28) tar 에는 `VERSION` 이 있었고, **`v30`(9/8)·`v31`·`v32` 에는 없다.**
   → `tar tzf … | grep 'SmartTwinPostprocessor/VERSION$'` 이 v29 만 1개, 나머지 0개.
4. tar 를 풀면 `bin/`·`lib/` 만 덮어써지고 호스트 `VERSION` 은 8/28 판이 남는다.
5. 후처리 담당이 그 `VERSION` 을 신뢰해 **9/8 판 소스**를 근거로 판단했다.
6. **이미 있는 기능을 "없다" 고 결론내고 임시 스크립트로 다시 만들었다.**

### 그래서 무엇을 고쳐야 하나

"기준량을 추가" 가 아니다. **진단 수단이 거짓말을 하지 않게** 만드는 것이 먼저다.
이걸 안 고치면 P1~P4 를 아무리 구현해도 다음 과제에서 또 "없다" 고 판단된다.
이번에 쓴 임시코드 9,090줄 중 일부는 그 오판의 산물이다.

덧붙여, 2026-09-13 에 넣은 소성일(`energy_*`)은 **아직 서버에 없다.** 이건 정상적인
미배포다(어제 작업). P0 에 배포를 포함한다.

---

## 1. 우선순위

갭 문서의 우선순위를 **"피해 크기 ÷ 구현 비용"** 으로 재배치했다.

| 순위 | 묶음 | 왜 여기인가 |
|---|---|---|
| **P0** | 진단이 거짓말하지 않게 | 이번 오판의 직접 원인. 이게 없으면 나머지가 무의미 |
| **P1** | 조용히 틀리는 물리 경로 (A-3 / A-2 / A-1 잔여) | 값이 틀려도 아무도 모른다 |
| **P2** | 오보를 낸 통계 경로 (B-3 / B-4) | **철회까지 간 잘못된 보고 2건의 직접 원인.** 구현은 작다 |
| **P3** | 캠페인 그릇 (B-0 / B-2) | P1·P2 가 들어갈 곳. 크다 |
| **P4** | A-4 / A-5 / A-6 / B-1 / B-5 / C | 갭 문서 판단 유지 |

갭 문서는 A 구간을 1순위로 봤지만, **철회까지 간 오보 두 건은 전부 B-3·B-4** 에서
나왔다. A 구간 오류(min_principal 을 항복과 직접 비교)는 작성자가 스스로 잡았고,
B 구간 오류는 보고된 뒤에 잡혔다. 그리고 B-3·B-4 는 A-3 보다 훨씬 싸다.

---

## 2. P0 — 진단이 거짓말하지 않게

### P0-1. 배포 tar 패키징을 스크립트화하고 VERSION 을 강제한다
지금은 절차가 리포지토리에 없어 사람이 손으로 묶는다. 그래서 v30 에서 파일 하나가
조용히 빠졌고 아무도 몰랐다.
- `scripts/package_module.sh` 신설 — `build_module.sh` 산출물을 tar 로 묶는다
- 묶은 직후 **자기검증**: `VERSION`·`env.sh`·`bin/unified_analyzer`·`lib/koo_*`
  가 아카이브 안에 있는지 확인하고, 하나라도 없으면 **실패로 끝낸다**
- verify: `v29` 는 통과, `VERSION` 을 일부러 뺀 아카이브는 exit≠0

### P0-2. `unified_analyzer --capabilities` (JSON)
소스를 읽어야만 지원 여부를 알 수 있는 구조가 문제였다. 실행 파일이 스스로 답하게
한다.
```
{"version":"4815f55","built":"...","hotspot":{"criteria":["von_mises","max_principal",
 "min_principal"],"element_kinds":["solid","thick_shell","shell"],
 "energy":true,"time_aggregate":["elemmax_then_mean"]}, ...}
```
- 목록은 **enum·파서에서 유도**한다. 손으로 적은 목록은 또 어긋난다
- verify: `parseHotspotCriteria` 가 받아들이는 이름 집합 == 출력 목록 (테스트로 고정)

### P0-3. 산출물에 도구 버전을 각인한다
결과 파일만 보고도 어느 판으로 돌렸는지 알 수 있어야 한다.
- `analysis_result.json > metadata.tool_version = {version, built, capabilities_hash}`
- deep/sphere/impact HTML 푸터에 같은 값
- verify: 서로 다른 두 빌드의 산출물에서 값이 다르게 나온다

### P0-4. 배포 후 검증 스크립트
- `scripts/verify_deploy.sh <배포경로>` — `VERSION` 의 커밋과
  `unified_analyzer --capabilities` 의 `version` 이 **일치하는지** 대조.
  불일치면 실패. 호스트 경로와 SIF 안을 **둘 다** 본다
- verify: 지금의 `/data/SmartTwinPostprocessor` 에 돌리면 **실패해야 한다**
  (VERSION `eaffe54` vs 바이너리 `4815f55`) — 이게 이번 사건의 재현 테스트다

### P0-5. 9/13 소성일(`energy_*`)을 배포한다
- SIF 재빌드 → node001 배포 → P0-4 로 검증

---

## 3. P1 — 조용히 틀리는 물리 경로

### P1-1. `top_percent` 에 독립인 절대량 ★
현재 클러스터의 `volume` 은 **상위 `top_percent` 개수컷으로 잘린 요소들의 체적**이라
물리량이 아니다. `want = floor(rank.size() × frac)` 이므로 3→5% 로 바꾸면 그대로 변한다.

**2026-09-13 에 넣은 `energy_total` 도 같은 병을 앓는다.** 클러스터 안에서만
합산하므로 역시 `top_percent` 종속이다. 이것도 같이 고친다.

- 파트 단위 절대량을 새로 낸다 — `n_yield`(ε_p>0 요소수), `vol_yield`(그 체적합),
  `sum_eps_vol`(Σ ε_p·V), `max_eps`, `plastic_work_total`(Σ w_p·V, 파트 전체)
- ε_p 는 word 6 이라 STRFLG 없이도 읽힌다. 시간 단조라고 **가정하지 않는다** —
  실덱에서 ε_p 가 감소하는 전이를 이미 확인했다(소성일 작업 노트 참조).
  마지막 프레임이 아니라 **이력 최댓값**을 쓴다
- verify: `--hotspot-top-percent 3` 과 `5` 로 두 번 돌려 **파트 절대량이 동일**,
  클러스터 종속량은 달라진다

### P1-2. 시간 집계 `max_t(mean_e)` 옵션
현재는 `mean_e(max_t)` 하나뿐이라 서로 다른 시각의 피크를 한 덩어리로 합성한다.
정의상 `mean_e(max_t) ≥ max_t(mean_e)` 이므로 과대평가 쪽이다.
- `--hotspot-time-aggregate {elemmax_then_mean | mean_then_timemax | both}`
- verify: 같은 덱에서 `mean_then_timemax ≤ elemmax_then_mean` 이 **모든 군집에서** 성립

### P1-3. A-1 잔여 — `max_shear`, `x_tension`
볼 전단·보드 굽힘 메커니즘은 아직 못 본다.
- `HotspotCriterion` 에 추가. `max_shear = (σ1−σ3)/2`
- `x_tension` 은 축 선택이 필요하다 → 기준명에 축을 받는 형태로 설계
- verify: 단축 인장 해석덱에서 `max_shear == σ_vm/2`(폰미제스 대비 이론값)

---

## 4. P2 — 오보를 낸 통계 경로

### P2-1. 공통 DOE 교집합 (B-3) ★
진행 중인 과제가 섞여 공통 DOE 가 185→27 로 줄었고, 그 결과
"T4 는 ×1.97~2.49" 라는 **틀린 수치를 보고했다가 철회**했다(올바른 값 ×2.66~4.02).
- `--common-doe-only` **기본 ON**
- 보고서에 표본수 · 제외된 DOE · **미완주 과제**를 명시
- 교집합이 임계 이하면 **비교를 거부**한다 (조용히 적은 표본으로 비교하지 않는다)
- verify: 33런만 끝난 과제를 섞으면 거부되고, 사유에 그 과제명이 나온다

### P2-2. 귀무 기대값을 코드에 고정 (B-4) ★
평균순위를 최소순위 귀무 `(N+1)/(k+1)` 와 비교해 "랜덤 수준" 이라 **잘못 결론**냈다.
올바른 `(N+1)/2` 로 고치니 F1_Back 이 4과제 중 3개 1위, **p=0.016** 으로 뒤집혔다.
귀무가설을 사람이 매번 고르는 구조면 또 틀린다.
- 통계 유틸 모듈 — 평균순위 검정(귀무 `(N+1)/2` **고정**), Spearman ρ,
  recall@k, 편차각 구간 프로파일
- 통계량마다 **어떤 귀무를 썼는지 산출물에 적는다**
- verify: 균일난수 1000회로 p 분포가 균일한지, 알려진 표본으로 Spearman 이
  `scipy.stats.spearmanr` 와 일치하는지

---

## 5. P3 / P4

- **P3**: `koo_scatter_report`(가칭) 신설 + `runner_config.postprocess.auto_scatter`,
  캠페인 롱포맷 `campaign_metrics.parquet` — P1·P2 의 그릇
- **P4**: A-4(elout 소스) / A-5(구간 분할) / A-6(좌표변환 기록) /
  B-1(면 기준 편차각) / B-5(ground truth 스키마) / C(그림 9종)

---

## 6. 진행 중 작업과의 관계

핫스팟 3D 인벨롭(`docs/hotspot_envelope_3d/`)이 G0·G5 까지 닫힌 상태로 열려 있다.
`HotspotClusterAnalyzer` 와 `koo_sphere_report` 를 양쪽이 건드리므로 **동시에
진행하지 않는다.** P0 는 두 작업과 파일이 겹치지 않으므로 **먼저 끼워넣을 수 있다.**
