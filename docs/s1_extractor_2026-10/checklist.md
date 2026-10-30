# 체크리스트 — S1 경량 추출기

## 설계
- [x] 조사: 원형(s1.py · 파일 구조) · StepForge deck_surface · SceneForge s1.py · 이 저장소 HDF5/표면/절단/스트리밍 자산
- [x] 계약 초안 `contract-c3-s1-draft.md` → DynaForge 에 보냄
- [ ] 받는 쪽 의견 반영(판 올림)

## 구현
- [x] D3plotReader::for_each_state (5f46be2)
- [x] 겉면 규칙(StepForge 꼴) — 운영 덱 면 32,082·절점 23,012·요소 28,251, 원형과 같음
- [x] /mesh · /parts 게이트 · /posture
- [x] /states 두 번 읽기 · float32 · linear_q16 · 솎기 · 청크 [64,256]
- [ ] /sections — 2단계, D-8 확정 뒤
- [x] CMake HDF5(C) · SIF def libhdf5-dev · build_module.sh (격리 작업 트리에서 build_module.sh rc 0)
- [x] 시험: ctest S1Core · 운영 덱 lasso 대조(변위·응력·시각·삭제, 게이트 22파트 일치)
- [x] 후처리 잡 연결 post_analyze.sh --s1 (기본 끔, 시험 [11])
- [ ] 배포(상류, 다음 이미지) · DynaForge 통보
