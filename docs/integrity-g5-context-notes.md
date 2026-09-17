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
