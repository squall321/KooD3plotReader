# 데이터 무결성 수정 — 체크리스트

계획: [plan.md](plan.md) · 결정 기록: [context-notes.md](context-notes.md) · 조사 결과: [findings.md](findings.md)

## 1. 면 응력 (질문의 출발점) — 완료
- [x] 내부 순번을 실제 ID 로 조회·셸 면 혼입·퇴화 면·SinglePass vM/σ1/σ3 누락 (36ea5db)
      → verify: lasso 독립 계산 400상태 0 불일치
- [x] 사면체·쐐기·피라미드 면 위상 + 요소 중심 기준 법선 (b04e1ae)
      → verify: 사면체 73% 덱에서 ±Z 400상태 0 불일치, 전 모델 +Z 21,709→14,451면

## 2. lsprepost libgtk — 완료 (SIF 빌드 후 재확인 남음)
- [x] def apt 3종 + %post·%test ldd 검사 (d72adb3)
      → verify: 샌드박스 렌더 22프레임 성공 / 현 SIF exit 127, 검사 통과·실패 확인
- [ ] 새 SIF 안에서 ldd not found 0 + 분석기 경유 렌더 1회

## 3. JSON 시계열 잘림·자릿수 — 완료
- [x] 전 상태 기록 + jnum (63577f5) → verify: 시험 8/8, 실덱 4952/4952점, 피크 472 보존
- [x] 잘림을 요구하던 시험 교체
- [x] 실덱 재실행: JSON 22MB→96MB, 시간 5:58, 최대 메모리 68GB(수정 전과 동일)

## 4. 보고서 차트 — 완료
- [x] 다운샘플 극값 보존·배열 정렬 (b562a2d) → verify: 실덱 92시리즈 극값 손실 0
- [x] matsum [시간][파트] 표 정렬 (6d178ef)

## 5. 요소 ID — 완료
- [x] NARBS 블록 순서(절점→솔리드→빔→셸→두꺼운셸) + 헤더 포인터 (a80dbb5)
      → verify: 원본 .k 와 lasso 양쪽 6/6 일치, 옛 코드는 4건 불일치로 검출

## 6. 전수 조사 확정 56건 — 진행 중
- [x] 조사·검증 (154 에이전트) → findings.md / findings.json
- [ ] G1 C++ 출력(10) · G2 C++ 분석기(4) · G3 deep(11) · G4 impact(16) · G5 sphere·federate·scatter·custom(13) · G6 스크립트(2)
- [ ] 병합 후 전체 시험 + 독립 검토
- [ ] 미검증 낮음 23건 훑어보기

## 7. 내가 따로 발견한 것
- [ ] UnifiedConfigParser 가 인라인 YAML(`surface: { direction: [...] }`)을 조용히 무시 — 기본값으로 돌아 두 잡이 같은 방향이 됐다
- [ ] 로컬 증분 빌드에서 `tool_commit` 이 옛 커밋으로 찍힌다(CMake 설정 시점 값). SIF 빌드는 매번 새 설정이라 영향 없음
- [ ] 4952상태 덱 분석이 68GB 를 쓴다(수정 전부터). 서버 노드 메모리 확인 필요

## 8. 배포
- [ ] 시험 전체 (C++·Python·배포 스크립트)
- [ ] 작은 덱으로 보고서 끝까지 생성 + 브라우저 확인
- [ ] push → SIF 빌드 → deploy_from_sif → verify_deploy → node001 → 패키지
