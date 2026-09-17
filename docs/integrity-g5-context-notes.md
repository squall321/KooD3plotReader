# 무결성 전수조사 G5-others 결정 기록

작업 중 내린 판단과 근거를 이어 적는다. 다음 세션이 같은 고민을 반복하지 않게.

## 공통 원칙 (저장소 규약)
- 결측·미계측은 0 이 아니라 None/null + 사유. 사유는 산출물에 실어 사람이 본다.
- 예외를 던져 보고서를 죽이지 않는다. 못 읽었으면 "못 읽었다" 가 값으로 나온다.
- 없는 키를 만들지 않는다.

## S1 σ3/ε3·peak_vel 참극값 (2026-09-17)
- `TimeSeriesData.true_min/true_min_time` 을 추가하고 `trough` 속성으로 노출했다.
  peak 쪽과 대칭이라 규칙이 하나로 읽힌다.
- `MotionData.peak_vel` 은 값이 없으면 0 이 아니라 None 이고, payload 는 그때 키를
  만들지 않는다. JS 는 이미 `pd.peak_vel||0` / `!== undefined` 로 방어한다.

## S2 두 번 솎이던 시계열 (2026-09-17)
- 헬퍼는 `loader.extreme_indices(n, arrays, target)` 하나로 통일했다. deep 쪽
  `_extreme_indices`(b562a2d)와 같은 착상이되, sphere 는 tier 점수가 10~100 으로
  작아 **예산을 넘지 않게** 구간 수를 `(target-2)//(2×배열수)` 로 잡았다.
- 로더 단계는 응력의 max·min 둘 다를 극값 원천으로 쓴다. 같은 함수가 σ3/ε3
  CSV 도 읽기 때문이다. motion 은 가속도·속도·최대변위·평균변위 4개.
- html/json 은 배열마다 목적이 달라 따로 인덱스를 뽑는다(g_ts 는 가속도,
  disp_ts 는 변위). 한 dict 안의 배열들은 같은 인덱스를 쓴다.

## S3·S4 자릿수 (2026-09-17)
- `loader.round_keep_sig(v, decimals, sig=4)` — 기존 소수 자릿수는 그대로 두되
  유효숫자 4자리를 바닥으로 깐다. 큰 값은 한 자리도 늘지 않으므로 payload 크기
  영향이 없고, 작은 값만 살아난다.
- 비유한값은 None 을 돌려준다. 예전에는 _Encoder 가 NaN 을 0.0 으로 바꿔
  '측정된 0' 으로 위장했다.
- JS 는 두 곳만 건드렸다. `tolAngleValue` 가 0 을 미계측으로 버리던 것과
  `formatValue` 의 고정 소수점. safety_factor 만은 계산 불가 시 0 을 주므로
  0 = 미계측 규칙을 유지했다.

## S5 미계측 0 위장 (2026-09-17)
- html payload 는 키를 **null 로 싣고**, report.json 은 **키를 뺀다**. 이유가 다르다.
  · JS 는 `pd[qty] == null` 로 미계측을 이미 구분하지만, 키가 아예 없으면
    `Math.max(a, undefined)`·`total += undefined` 가 NaN 이 되어 집계가 통째로
    깨진다. null 은 0 으로 취급돼 지금 동작과 같다.
  · federate 는 `_num(pdata.get(src))` 로 읽으므로 키가 없으면 no_metric 이 된다.
    이것이 이 결함이 요구한 결과다.
- analyzer·terminal 의 비교는 None 을 만나면 TypeError 로 보고서를 죽인다 —
  `is not None and` 로 막았다.
- 화면 서술 "소성 변형률이 0 = 완전 탄성" 은 미계측일 때 거짓말이라
  `strainMeasured` 카운트를 두고 문장을 분리했다.

## S6 --from-json 재생성 (2026-09-17)
- `_series`/`_motion`/`_energy` 로 저장된 값을 읽는다. 없는 열(avg 등)은 **비운다** —
  사이드카 stress_ts 는 t/max 만 실으므로 avg 는 없는 것이 맞고, 화면은
  `pd.stress_ts.avg &&` 로 에너지 흡수 칸을 스스로 감춘다.
- 이 때문에 payload/사이드카 빌더가 "열 길이는 times 와 같다" 를 가정하던 곳이
  드러났다(IndexError). 길이가 맞는 열만 싣도록 고쳤다 — 실캠페인 재생성에서
  실제로 죽던 경로다.
- σ1/σ3/주변형률은 사이드카에 스칼라만 있으므로 스칼라만 복원한다
  (true_peak/true_min). 시계열이 없으니 그 탭은 비어 있는 것이 정직하다.
