# 데이터 무결성 수정 — 체크리스트

계획: [plan.md](plan.md) · 결정 기록: [context-notes.md](context-notes.md)

## 1. 면 응력 — 완료 (36ea5db)
- [x] 내부 순번 조회·셸 면 혼입·퇴화 면·SinglePass vM/σ1/σ3 누락
      → verify: lasso 독립 계산 400상태 0 불일치, C++ 시험 3종

## 2. lsprepost libgtk — 완료 (d72adb3), SIF 빌드 후 재확인 남음
- [x] def apt 에 libgtk-3-0 libnotify4 libsecret-1-0
- [x] %post·%test ldd 검사 → verify: 샌드박스 통과 / 현 SIF exit 1
- [x] 샌드박스 렌더 → verify: 22프레임 MP4, 현 SIF 는 exit 127
- [ ] 새 SIF 안에서 ldd not found 0 + 분석기 경유 렌더 1회

## 3. JSON 시계열 잘림·자릿수 — C++ 완료 (63577f5)
- [x] 잘림을 요구하던 시험 교체 + 자릿수 시험 → verify: 수정 전 2건 실패 확인
- [x] partStatsToJSON·surfaceStatsToJSON 전 상태, 수치 jnum → verify: 8/8
- [ ] 실덱(4952상태) 새 실행: len(data)==num_points, JSON 크기·시간 실측

## 4. 전수 조사 확정 항목 (워크플로 결과로 채움)
- [ ] (조사 진행 중)

## 5. Python 소비처
- [ ] 차트 다운샘플이 피크·최소를 보존
- [ ] 옛 잘린 JSON 을 조용히 20점으로 쓰지 않음 (재분석 또는 CSV 복원 또는 사유)

## 6. 배포
- [ ] 시험 전체 (C++·Python·배포 스크립트)
- [ ] push → SIF 빌드 → deploy_from_sif → verify_deploy → node001 → 패키지
