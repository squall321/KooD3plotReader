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

## 6. 전수 조사 확정 60건 — 수정·병합 완료
      (고유 위치는 58개. `examples/unified_analyzer.cpp:49` 의 CSV 자릿수 결함이
       시간열·파트 CSV 값·전체 CSV 로 3번 나뉘어 적혀 있다 — findings.md 머리말 참고)
- [x] 조사·검증 (154 에이전트) → findings.md / findings.json
- [x] G1 cpp-core(9) · G2 cpp-output(7) · G3 deep(13) · G4 impact(16) · G5 sphere 계열(13) · G6 스크립트(2)
      → 6개 작업 트리 47커밋, cherry-pick 으로 병합(SinglePassAnalyzer 충돌 1건은 위임 구조 유지 + 침식 제외를 공용 계산기로 이관)
- [x] 병합본 시험: C++ 14종, Python 420개, 스크립트 2종 통과
- [x] 실덱 재확인: 면 응력 ±Z 400상태 독립 계산 일치, 배터리 덱 보고서 브라우저 오류 0,
      impact 실캠페인 25런 보고서 생성(잘린 옛 산출물은 '잘림·미계측' 으로 표시)
- [x] 2차 낮음 23건 — 4묶음 병합 (C++ 첫 커밋은 1차와 중복이라 건너뜀)
- [x] 적대적 검토(에이전트 130개): 확정 53 / 기각 9 → 51건 수정·병합, 2건은 내가 직접 수정
      (응력 단위 라벨 22b9ac8, FFT 시각 중복 52bbac9)

## 7. 내가 따로 발견한 것
- [x] UnifiedConfigParser 가 인라인 YAML 을 조용히 무시 (2e457c5) → verify: 경고 출력·블록 형식 정상
- [x] 로컬 증분 빌드에서 `tool_commit` 이 옛 커밋으로 찍히던 문제 (16f22b9)
      → 빌드 시점에 git 을 다시 읽는 cmake/GitVersion.cmake, 커밋이 같으면 파일을 안 건드려 헛 재링크 없음.
      verify: tests/version/test_version_stamp.sh 3/3 (수정 전 ②번 실패).
      덤으로 `.gitignore` 의 `*.cmake`·`build` 규칙이 새 파일을 삼켜 **커밋되지 않는** 것도 잡았다
- [x] 큰 덱 분석의 피크 메모리 (e9e51d5) — 상태를 합칠 때 복사해 피크가 2배였다.
      → 이동으로 바꿔 400상태 덱에서 5.5 GB → 2.7 GB, 시간 2.6초 → 1.0초, 산출물 동일.
      4952상태 덱 기준 약 68 GB → 33 GB. verify: tests/version/test_state_merge_memory.sh
      (수정 전 4.0배 FAIL / 수정 후 1.94배 PASS)

## 8. 배포
- [x] 시험 전체 — C++ 22종, Python 532개, 스크립트 2종 통과
- [x] 실덱 재확인 — 면 응력 ±Z 400상태 독립 계산 일치, 요소 ID 순서까지 일치,
      배터리 덱 보고서 브라우저 JS 오류 0·차트 12/12·'MPa' 하드코딩 0
- [x] push origin/main ff6cfc5 (125커밋)
- [x] SIF 빌드 → 안에서 VERSION ff6cfc5 / lsprepost ldd not found 0 /
      분석기와 같은 명령으로 헤드리스 렌더 성공(22프레임 MP4) — 옛 SIF 는 exit 127 이던 그 명령
- [x] deploy_from_sif → verify_deploy: 호스트·SIF VERSION·실행파일 ff6cfc5 일치, 래퍼 6/6 env 없이 실행
- [x] node001 ff6cfc5 (NFS 공유), 배포본으로 실덱 분석 재확인(시계열 22/22, unit deck_units, tool_commit ff6cfc5)
- [x] 패키지 SmartTwinPostprocessor_20260917_v36.tar.gz (523M) — verify_package 통과
