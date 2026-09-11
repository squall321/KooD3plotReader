# 셸 지원 + 리포트 — 체크리스트

계획: [hotspot-shell-report-plan.md](hotspot-shell-report-plan.md)

## A. 조사
- [x] 규격서 셸/두꺼운 셸 배치
- [x] 강체 압축(DCOMP=2, NDIM 5·7) 규칙 — 저장소 미처리 확인, 우리 덱은 NDIM=4
- [x] 시험 덱 선정 (case_shell PCB 탄성 · case_01 셸+두꺼운셸+변형률 · case_dent)
- [x] 독립 검증 근거 (입력 덱 두께, 탄성 층 선형성)

## B. C++
- [x] 셸 기하 함수 (면적·도심) + 두꺼운 셸 면내 크기
- [x] 누적 패스 — 종류×기준, 층 최대, 짝 변형률, 두께
- [x] 군집 — 종류별 기하·가중·대표 크기, bbox, 출력 필드
- [x] UnifiedAnalyzer 루프 · JSON 직렬화

## C. 리포트
- [x] d3plot_reader 파싱 · 모델
- [x] HTML 탭 (표 + 3D)

## D. 검증
- [x] 셸 기하 단위 시험
- [x] 셸 군집 합성 시험
- [x] 두께 워드 = 입력 덱
- [x] 탄성 PCB 층 선형성
- [x] numpy 층별 대조 (case_01 · case_dent)
- [x] 솔리드 골든 불변
- [x] 기존 시험 전부
- [x] 리포트 브라우저 확인

## E. 마감
- [x] 문서 · 커밋 · SIF v32 · node001 배포 + 배포 SIF e2e (case_01 102 항목, HTML 탭 9·보기 5·기준 3 오류 0)

## 작업 중 추가로 발견·처리
- [x] NEL8 음수(10절점 솔리드) → size_t 오버플로 (기존 결함, 7b96430)
- [x] 얇은 솔리드 판 핫스팟 흩어짐 (기존 결함, c905f25)
- [x] 평탄 분포를 핫스팟으로 오독 — `uniform`·`cut_ties_unselected`
- [x] Overview 피크 응력이 솔리드만 집계함을 표시 (집계 자체의 셸 확장은 미착수)
