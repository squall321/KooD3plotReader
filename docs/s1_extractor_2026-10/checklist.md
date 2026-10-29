# 체크리스트 — S1 경량 추출기

## 설계
- [x] 조사: 원형(s1.py · 파일 구조) · StepForge deck_surface · SceneForge s1.py · 이 저장소 HDF5/표면/절단/스트리밍 자산
- [x] 계약 초안 `contract-c3-s1-draft.md` → DynaForge 에 보냄
- [ ] 받는 쪽 의견 반영(판 올림)

## 구현
- [ ] D3plotReader::for_each_state (가족 파일 검사 공유, 상태 하나씩)
- [ ] 겉면 규칙(StepForge 꼴) + 원형 · StepForge 집합 대조
- [ ] /mesh · /parts 게이트 · /posture
- [ ] /states 두 번 읽기 · float32 · linear_q16 · 솎기
- [ ] /sections
- [ ] CMake HDF5(C) · SIF def libhdf5-dev · build_module.sh
- [ ] 시험(합성 덱 · 운영 덱) · h5py 복원 확인
- [ ] 후처리 잡 연결 · 배포(상류) · DynaForge 통보
