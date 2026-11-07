# 체크리스트 — 후처리 후속 4건

## 1. 소프트웨어 단면 상태 간격
- [x] YAML state_step → SectionViewConfig → 렌더러 프레임 목록(2D · 3D · iso)
- [x] [설정] 경고 지우기 · 시험 · 실렌더(992 → 50 프레임, 189 s → 20 s)

## 2. 소프트웨어 단면 메모리
- [x] 쥐는 곳 · 크기 측정 — 단면이 아니라 분석기의 전 상태 읽기(6,680 MB 동일) → 범위 재확인 필요
- [ ] 필요한 상태만 필요할 때 읽기 · 분석 결과 무변 대조 · 실측(v14 급)

## 3. 온톨로지 머리 warnings
- [ ] sphere · impact · deep 읽기 실패 수집 → 머리 warnings
- [ ] 시험 · DynaForge 검사기 통과

## 4. 옛 산출물 그림 + sphere 연결
- [ ] figures pack --update-html
- [ ] post_analyze 건너뛴 산출물 그림 채우기(셸 시험)
- [ ] 캠페인 figures/index.html · sphere HTML 링크(멱등)

## 마감
- [ ] 시험 전부 · 커밋 · v45 끝난 뒤 push · 배포 요청(사용자 승인)
