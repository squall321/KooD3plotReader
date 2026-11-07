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
- [x] 셸 배치 도우미(LayeredLayout — 핫스팟 층별 극값과 공용) — 세 덱에서 핫스팟 출력이 v46 과 같다
- [x] 요소 → 파트(셸 · 두꺼운 셸, 배치가 맞을 때만) · part_ids_ · element_type
- [x] 상태별 셸 루프(병렬 · 순차 경로) · 삭제 요소 · 솔리드 없는 덱(셸 전용)
- [x] JSON element_type(셸 계열만) · 피크 텐서는 솔리드 전용으로 막음
- [x] 실데이터 대조 — 셸 lasso 236/236, 두꺼운 셸 경로 간 33/33, Test_006 · 세 덱 기존 항목 v46 과 동일

## 파이썬 소비자
- [x] deep 표 「솔리드만」 → 「일부 파트 미산출」, 셸 값에 「층 최대」 표식, 사유 문구
- [x] 그림 자동 선택 후보에 셸 — airbag 덱에서 대상 5개가 셸, 그림 값 = 해석기 값
- [x] 캠페인 · 온톨로지 · impact · federate · custom 는 이력을 그대로 읽어 셸이 자연히 든다(행동 변화 — 보고)
- [x] 시험 · 커밋

## 마감
- [x] 전체 시험(C++ 핫스팟 8 · CTest 10 · build_fig 4, 파이썬 6개 패키지 765, post_analyze 셸 시험)
- [ ] 사용자 보고 → push · 배포는 승인 뒤
- [ ] DynaForge 어휘에 plastic_strain · plastic_work 열거값 · 단위 추가 요청(정본은 DynaForge)
