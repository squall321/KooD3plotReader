# S1 경량 추출기 (2026-10-29)

**요청** DynaForge(KooRemapper) `docs/requests/kood3plotreader-s1-extractor-request-2026-10-28.md` (§1–§8).
**계약** `contract-c3-s1-draft.md` — 꼴은 받는 쪽(DynaForge · SceneForge · StepForge)과 먼저 맞춘다.
**사용자 결정** 이 세션이 이어서 한다(10-29). koo_sphere_report 는 kood3plotreader-a9 몫이라 건드리지 않는다.

## 무엇을 · 왜
각도마다 d3plot(운영 덱 18 GB)에서 겉면 변위 · 응력 · 삭제 · 기준 단면 · 자세 재료를 담은 HDF5(`Run_*/Output/s1.h5`)를
만드는 C++ 도구 `s1_extract`. DynaForge P1(manifest · 게이트 · 변형 뷰어), StepForge 대조, SceneForge 장면이 이 파일을 쓴다.
리더를 이 저장소 하나로 두어 d3plot 호환 위험을 없앤다.

## 단계
1. 리더에 상태 하나씩 읽는 API(`for_each_state`) — K-2 와 같은 가족 파일 검사를 공유.
2. 겉면(StepForge 규칙) · `/mesh` · `/parts` 게이트 · `/posture`.
3. `/states` 두 번 읽기(1차 스케일 · 게이트, 2차 쓰기), float32 · linear_q16, 솎기.
4. `/sections` (t=0 기준 절단).
5. CMake(HDF5 C) · SIF def 에 libhdf5-dev · 후처리 잡 연결.

## 성공 기준
- 운영 덱(Test_005 Run_20260602_093237_801e2b)에서 rc 0, 메모리 상한(수백 MB) 안, 크기 · 시간 기록.
- 겉면이 원형(23,012 절점 · 32,082 면)·StepForge 집합과 같다(다르면 까닭을 적는다).
- 복원 오차 ≤ scale/2, 게이트 값이 전 상태 독립 계산과 같다, 자세 값이 DynaForge 실측(면 잔차 ≤ 6e-7 mm, 법선↔−v̂ 0.007°, 틈 0.05 mm, 첫 접촉 9.2 µs)과 맞는다.
- h5py(SIF 안)로 읽어 계약대로 되돌려진다.
