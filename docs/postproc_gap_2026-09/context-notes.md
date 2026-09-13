# 후처리 갭 대응 — 컨텍스트 노트

## 2026-09-13 — A-1 은 갭이 아니었다

갭 문서의 최우선 항목 A-1("핫스팟 기준량이 von Mises 하나뿐")을 소스로 검증했더니
**이미 구현돼 있고 서버에도 배포돼 있었다.**

확인 경로 (추측 아님, 전부 실물 확인).

- `ssh node001` → `SmartTwinPostprocessor.sif` 는 2026-09-11 18:17 = v32
- `apptainer exec … cat /opt/kood3plot/VERSION` → `4815f55` / 2026-09-11 (정확)
- `apptainer exec … sed -n '25,45p' /opt/KooD3plotReader/include/…/HotspotClusterAnalyzer.hpp`
  → `enum class HotspotCriterion { VonMises, MaxPrincipal, MinPrincipal }`
- `--hotspot-criterion C[,C]` CLI 도 `78b9a55`(9/11)에 있음

**그런데** 호스트 `/data/SmartTwinPostprocessor/VERSION` 은 `eaffe54` / 2026-08-28.
node001 도 동일하게 낡았다.

### 왜 VERSION 만 낡았나

```
tar tzf …_v29.tar.gz | grep 'SmartTwinPostprocessor/VERSION$'  → 1개
tar tzf …_v30.tar.gz → 0개    (2026-09-08)
tar tzf …_v31.tar.gz → 0개
tar tzf …_v32.tar.gz → 0개
```

`scripts/build_module.sh` 는 `${PREFIX}/VERSION` 을 정상 생성한다(SIF 안은 맞다).
**tar 로 묶는 절차가 리포지토리에 없다.** 사람이 손으로 묶다가 v30 에서 VERSION 이
빠졌고, tar 를 풀어도 호스트의 옛 VERSION 이 덮이지 않아 8/28 에 고착됐다.

### 갭 문서가 본 것

인용한 `HotspotClusterAnalyzer.hpp:33 /// 선별 기준량. 현재 "von_mises" 만 지원` 은
`6d16634`(2026-09-08) 판이다. **줄 번호까지 정확히 일치**한다. 즉 9/8 판 소스를
근거로 판단했다.

### 여기서 얻을 교훈

기능을 추가하는 것보다 **"무엇이 있는지 확인하는 수단"** 이 먼저다. 이번에는
확인 수단(VERSION)이 2주 묵은 거짓을 말했고, 그 결과 **이미 있는 기능을 없다고
결론내고 임시 스크립트로 다시 만들었다.** 임시코드 9,090줄 중 일부는 그 산물이다.

그래서 P0 를 신설해 우선순위 맨 위에 뒀다. 파일을 하나 빠뜨려도 아무도 모르는
배포 절차, 소스를 읽어야만 알 수 있는 기능 목록, 산출물에 없는 도구 버전 —
셋 다 같은 병이다.

## 2026-09-13 — 내가 어제 넣은 것도 같은 결함이 있다

소성일 `energy_total = Σ w_p·V` (커밋 `53dc93f`)는 ε_p 기반이라 A-3 이 지적한
"총변형률이라 소성을 못 본다" 는 부분적으로 푼다.

**그러나 클러스터 안에서만 합산하므로 `top_percent` 에 종속이다.** 갭 문서가
`volume` 에 대해 지적한 병을 그대로 앓는다. `want = floor(rank.size() × frac)`
(`HotspotClusterAnalyzer.cpp:744`)이므로 3→5% 로 바꾸면 따라 변한다.
P1-1 에서 파트 단위 절대량과 함께 고친다.

## 2026-09-13 — 우선순위를 갭 문서와 다르게 잡은 이유

갭 문서는 "물리적으로 틀렸던 건 전부 A 구간" 이라며 A 를 1순위로 뒀다. 그러나
**철회까지 간 잘못된 보고 2건은 전부 B-3·B-4** 에서 나왔다.

- B-3: 미완주 과제가 섞여 공통 DOE 185→27, "T4 ×1.97~2.49" 보고 후 철회
  (올바른 값 ×2.66~4.02)
- B-4: 귀무를 `(N+1)/(k+1)` 로 잘못 골라 "랜덤 수준" 결론 → `(N+1)/2` 로 고치니
  F1_Back p=0.016 으로 뒤집힘

A 구간 오류(min_principal 을 항복과 직접 비교)는 작성자가 스스로 잡았다. B 구간은
보고된 뒤에 잡혔다. 그리고 B-3·B-4 는 교집합 계산과 통계 유틸이라 A-3 보다 싸다.
"피해 크기 ÷ 구현 비용" 으로 재배치했다.
