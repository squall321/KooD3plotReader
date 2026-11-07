# 체크리스트 — 셸 파트 이력 · 핫스팟 소성 기준

## 0. 준비
- [x] mini26 DropSet 24개 복원(사용자 승인, `cp -n`, 26/26)
- [x] 계획 · 체크리스트 · 결정 기록
- [x] 소비자 조사(파이썬 · JS 의 이력 · 기준 이름 사용처) — context-notes 「소비자 조사」

## ② 핫스팟 소성 기준
- [x] enum · 슬롯 9 · 이름 · 파서 · 짝 변형률 이름 · capabilities
- [x] 요소 극값 — plastic_strain(값 · 처음 시각) · plastic_work(값 · 끝 시각), 솔리드 · 셸 · 두꺼운 셸
- [x] 선별에서 소성 없는 요소 제외(ε_p ≤ max(1e-6, 임계)) · 2패스(plastic_strain 만)
- [x] 기본 기준 von_mises + plastic_strain(분석기 · TimeHistory · deep CLI — 옛 엔진이면 빼고)
- [x] 소비자 — deep 이름표 · 색 척도, sphere 3D 뷰어 기준 거르기, 온톨로지(어휘 밖은 싣지 않고 경고), elout 대조는 von_mises 만, 문서
- [x] C++ 시험 · 실덱 대조(Test_006 23/23 독립 일치, v46 대비 회귀 없음) · 커밋

## ① 셸 파트 이력
- [ ] 셸 배치 도우미(accumulateLayeredExtremes 와 공용) — 기존 핫스팟 셸 시험 그대로 통과
- [ ] 요소 → 파트(셸 · 두꺼운 셸) · part_ids_ · element_type
- [ ] 상태별 셸 루프(병렬 · 순차 경로) · 삭제 요소 · solid_data 빈 덱
- [ ] JSON element_type · 시험
- [ ] 실데이터 3개 독립 대조 · Test_006 회귀 · 커밋

## 파이썬 소비자
- [ ] deep 표 「계산 안 됨(셸)」 → 값 · 층 최대 표기
- [ ] 그림 자동 선택 후보에 셸
- [ ] 캠페인 · 온톨로지 · 그 밖(조사 결과)
- [ ] 시험 · 커밋

## 마감
- [ ] 전체 시험(C++ · 파이썬 · post_analyze 셸)
- [ ] 사용자 보고 → push · 배포는 승인 뒤
