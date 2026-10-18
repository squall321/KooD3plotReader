# 후처리 마감 보완 — 체크리스트

## ① null 가드 (sphere 탭 3개)
- [ ] 재현 — 파트 지표가 부분 null 인 캠페인에서 탭 3개 예외 확인
- [ ] `renderStatistics` · `buildStressEnvelopeSVG` · `reDrawMiniMollweide` 가드
- [ ] verify: 같은 캠페인에서 JS 예외 0, 미계측은 '—' 로 표시
- [ ] 시험 — 수정 전 FAIL 확인

## ② batch --config
- [ ] batch 에서 `--config` 를 주면 **무시된다는 경고**를 낸다 (조용한 무시 금지)
- [ ] verify: batch + --config → 경고 1줄, single 은 그대로

## ③ 단면 뷰
- [ ] `output_dir` 상대경로를 **분석 출력 디렉토리 기준**으로 (절대경로는 그대로)
- [ ] 기본 절단면 — 핫스팟을 비켜가는 문제. 최소한 문서·도움말에 명시
- [ ] verify: 출력이 지정한 곳에 떨어진다

## ④ 캔버스 호버
- [ ] 마우스 올린 위치의 최근접 군집 값 표시 (각도·파트·순위·척도값·반경·요소수)
- [ ] verify: 브라우저 실조작, JS 예외 0
