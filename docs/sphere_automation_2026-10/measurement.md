# (3) 실측 — 워커 RSS · 메모리 축약 (2026-10-31)

캠페인: `/data/Tests/Test_005_Fibonacci_100` — **100런**, DropSet 100, binout 100.
입력은 심볼릭 링크로 **읽기만** 하고 캐시는 `.work/sphere_auto/fib100/` 안에 썼다
(원본 무수정).

## 1패스 병렬 — 시간과 봉우리

| `-j` | 벽시계 | 부모 MaxRSS |
|---|---|---|
| 1 (순차) | **35.4초** | 309 MB |
| 4 | **16.5초** | 299 MB |
| 8 | **13.6초** | 299 MB |

캐시 적중 시(2회차)는 순차 **9.5초**. 1패스가 끝나면 그 뒤는 캐시라 빠르다.

## 워커 RSS — 상류가 기다리던 값

`-j 8` 실행 중 0.3초 간격으로 자식 프로세스 RSS 를 96회 표집.

- **최대 298 MB / 워커**
- 중앙 255 MB / 워커

### 🔴 이 값을 그대로 큰 덱에 쓰면 안 된다 — 분해 결과
| | |
|---|---|
| 파이썬 기저 + 흐름 의존성 임포트 | **13 MB** |
| 덱 처리 몫 (binout 파싱 + 흐름 조립) | **285 MB** |

즉 워커 RSS 는 **거의 전부 모델 크기에 비례**한다. 비례하지 않는 고정분이
13 MB 밖에 안 된다는 것이 핵심이다.

**이 캠페인은 작다.** 한 런이 binout 5.8 MB · keyword 9.1 MB · 흐름 캐시
0.19 MB, 메모리상 흐름 0.98 MB/run. 상류가 보고한 M3_P2 는 **87 MB/run** —
약 **89배**다. 그러면 워커 하나가 수 GB 를 쓸 수 있고, 16 워커면 그 배수다.

→ 2026-11-04 현재 `SPHERE_NEW_MEM_PER_WORKER_GB` 는 **0.5 GB** 로 라이브인데,
이는 **이 작은 모델 기준으로도 여유가 1.7배뿐**이다. 작은 캠페인은 충분하지만
**큰 덱 첫 잡 전에 반드시 다시 재야 한다.**

재는 법:
```
koo_sphere_report --test-dir <캠페인> -j 2 --terminal-only &
PP=$!; while kill -0 $PP 2>/dev/null; do ps --ppid $PP -o rss=; sleep 0.3; done | sort -n | tail -1
```

## 2패스 축약 효과

같은 캠페인에서 상한만 바꿔 비교(캐시 적중, 2회차).

| | 시계열 보유 | MaxRSS |
|---|---|---|
| 옛 방식 재현 (상한 100 = 전 런 보유) | 100/100 | **236 MB** |
| 지금 (상한 60) | 60/100 | **197 MB** |

차이 39 MB / 40런 = **run 당 0.98 MB** (이 모델).

**구조가 전이된다.** 봉우리의 흐름 몫이
`N × per_run` → `min(N, 60) × per_run` 이 된다.
- 이 모델(0.98 MB/run), 979런: 약 960 MB → **59 MB**
- M3_P2(상류 보고 87 MB/run), 979런: 약 **85 GB → 5.2 GB**
  (측정된 MaxRSS 84.7 GB 와 맞는다)

## 사이징 제안

```
mem ≈ 기저 + 60 × per_run + W × worker_rss
```
`per_run`·`worker_rss` 는 모델에 따라 다르므로, 큰 덱을 처음 돌릴 때 한 번
재서 쓰는 것이 맞다. 이 캠페인 기준으로는
`기저 0.2 GB + 60×0.001 GB + W×0.3 GB` 이다.

## 쓴 방법 (재현용)
```
W=.work/sphere_auto/fib100
ln -s /data/Tests/Test_005_Fibonacci_100/{analysis_results,output} $W/
rm -rf $W/.sphere_flow_cache
/usr/bin/time -f "wall=%e MaxRSS_KB=%M" python3 -m koo_sphere_report --test-dir $W -j 8 --terminal-only
# 워커 RSS 는 실행 중 ps --ppid <부모> -o rss= 를 0.3초 간격 표집
```
