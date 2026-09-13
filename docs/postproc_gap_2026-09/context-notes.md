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

## 2026-09-13 — P0-1 구현 중 검증기가 스스로 거짓말할 뻔했다

`verify_package.sh` 첫 판이 v29(정상 아카이브)에서도 `bin/unified_analyzer` 가
없다고 했다. 원인은 이것이다.

```bash
set -uo pipefail
echo "$listing" | grep -qxF "$path"    # ← 이게 문제
```

`grep -q` 는 첫 매치에서 **즉시 종료**한다. 그러면 아직 쓰고 있던 `echo` 가
SIGPIPE 로 죽고, `pipefail` 이 파이프라인 종료 상태를 실패로 만든다. 결과적으로
**목록 앞쪽에 있는 항목일수록 "없다" 는 거짓 실패**가 났다. `env.sh` 는 목록
끝 근처라 통과하고 `bin/*` 은 앞쪽이라 실패하는, 재현은 되지만 이유를 모르면
납득이 안 되는 형태였다.

here-string(`grep -q ... <<< "$listing"`)으로 파이프를 없애 해결했다.

검증 도구가 거짓 실패를 내는 것은 거짓 통과보다는 낫지만, 몇 번 겪으면 사람이
검증을 꺼버린다 — 결국 같은 곳으로 간다. 검증기에는 **자기 자신에 대한 테스트**가
필요해서 합성 케이스 6종(정상 / unknown 버전 / VERSION 누락 / lib 누락 /
최상위 2개 / 손상 tar)을 만들어 통과시켰다.

## 2026-09-13 — 패키징에서 구조 변환은 하지 않기로

배포본은 `SmartTwinPostprocessor/{bin,lib,env.sh}` 이고 `build_module.sh` 산출물은
`{bin,python,lsprepost,activate.sh,VERSION}` 이다. 둘 사이 변환 절차는 리포지토리에
없다(사람이 했다). 그 변환까지 추측으로 스크립트에 넣으면 **틀린 절차를 코드로
굳히는 것**이 된다.

그래서 `package_module.sh` 는 `--from-dir` 만 받는다. 이미 만들어진 배포 디렉토리를
그대로 묶고, VERSION 누락만 막는다. 추측이 0이면서 이번 사건은 100% 막힌다.
SIF→디렉토리 변환을 스크립트화하는 것은 별도 과제로 남긴다.

## 2026-09-13 — P0-4 가 첫 실행에서 이번 사건을 못 잡을 뻔했다

`verify_deploy.sh` 첫 판은 "VERSION ↔ 바이너리" 만 봤다. 그런데 현재 배포본은
바이너리가 `--capabilities` 를 모르는 옛 빌드라 대조 자체가 불가능했고, 그 결과
**호스트 `eaffe54` vs SIF `4815f55` 라는 이번 사건의 핵심을 놓쳤다.**

고친 뒤에는 바이너리가 답하지 못해도 VERSION 값을 기록해 두고 **대상 간 대조**를
한다. 그래서 지금 돌리면 불일치가 그 자리에서 드러난다.

교훈 — 검증 도구는 "정상 케이스에서 통과하는가" 보다 **"내가 막으려는 그 사건을
실제로 잡는가"** 로 시험해야 한다. 두 도구(P0-1, P0-4) 모두 그 시험에서 결함이
나왔다. P0-1 은 `echo|grep -q` + pipefail 의 SIGPIPE 로 거짓 실패를, P0-4 는
대상 간 대조 누락으로 거짓 통과에 가까운 상태를 냈다.

`set -u` + 빈 배열 `${#ARR[@]}` 가 unbound 로 죽는 것도 다시 겪었다(bash 5.1).
개수는 카운터로 따로 센다.
