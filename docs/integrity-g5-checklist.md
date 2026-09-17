# 무결성 전수조사 G5-others 체크리스트

2026-09-17 전수조사에서 확정된 결함 13건(koo_sphere_report 7 · koo_federate_report 5 ·
koo_scatter_report 1). 항목마다 **실패하는 시험을 먼저** 쓰고, 고치고, 패키지 전체
시험으로 회귀를 확인한 뒤 커밋한다.

## koo_sphere_report
- [x] S1 σ3/ε3 최소값·peak_vel 이 다운샘플된 배열에서 나온다 (models.py:235)
- [x] S2 시계열이 두 번 stride 다운샘플되어 JS KPI(peak G·펄스·CAI·핫스팟 요소)가 깎인다 (html_report.py:194)
- [x] S3 payload 가 고정 소수점으로 반올림돼 작은 값이 0 으로 붕괴한다 (html_report.py:146)
- [x] S4 report.json 사이드카도 같은 고정 소수점 반올림 (json_report.py:76)
- [x] S5 CSV 부재를 계측된 0 으로 보고한다 (models.py:207)
- [x] S6 --from-json 이 2점 파형을 지어내고 σ1/σ3/에너지를 버린다 (from_json.py:15)
- [x] S7 ms 기반 덱을 전부 ton-mm-s 로 판정한다 (loader.py:171)

## koo_federate_report
- [x] F1 σ3/ε3 를 max 로 골라 '최악' 이 가장 약한 압축이 된다 (adapters/sphere.py:93)
- [x] F2 HTML 이 모든 지표를 G 제수로 나누고 0 자리로 찍는다 (report/html_report.py:1209)
- [x] F3 resample 이 각도 이름만 보고 '실측 일치' 로 짝짓는다 (resample.py:373)
- [x] F4 IDW 가 g/s/e/d 만 보간해 나머지 5종이 '값 없음' 이 된다 (resample.py:279)
- [x] F5 sphere 사이드카에 단위 라벨을 지어내 단위 불일치 경고가 못 뜬다 (adapters/sphere.py:137)

## koo_scatter_report
- [x] C1 방향도 pitch 축이 ±90° 고정이라 실캠페인 40% 가 화면 밖으로 나간다 (charts.py:169)

## 결과 (2026-09-17)
13건 전부 수정. 신규 시험 파일 10개(sphere 6 · federate 5 · scatter 1 — 시험 51건),
규칙이 뒤집혀 갱신한 기존 시험 3건. 패키지 시험: sphere 70/70 · federate 202/202 ·
scatter 7/7. 실데이터 확인: Test_001(26런) 전체 보고서 생성 + --from-json 재생성,
덱 14종 단위 판정, Test_006 방향도 좌표.
