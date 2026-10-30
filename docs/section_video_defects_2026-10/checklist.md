# 체크리스트 — 단면 영상 · 상태 읽기 (2026-10-28)

## 조사
- [x] 인용 코드 위치 확인(HEAD 176857e) — ROADMAP 1-3·1-5·1-7 과 같은 항목
- [x] K-1 원인: LS-PrePost 상태 메모리 예산(역어셈블) + lsppconf 20M 으로 결정적 재현
- [x] K-1 처방 후보 시험: 1000G 정상, LSPP_STATE_MEMORY=off 무효, 실메모리 부족은 abort(rc 134)
- [x] K-2 가족 파일 끝 규칙: 운영 덱 249 파일·Test_Cum26x3·D3plotWriter

## K-2 상태 읽기
- [x] StateDataParser: 예외 삼키기 제거, 멈춘 이유·남는 워드 기록
- [x] FileFamily: 번호 구멍 뒤 파일 감지
- [x] D3plotReader 순차·병렬: 열기 실패·파싱 예외·중간 잘림·구멍 → 예외, 마지막 잘림 → 경고
- [x] UnifiedAnalyzer::analyze · unified_analyzer 단면 경로: 예외 → 실패(rc 1)
- [x] 합성 덱 시험 (수정 전 FAIL 확인)

## K-3 스레드 상한
- [x] read_all_states_parallel: num_threads 상한 작업자 풀, 생성 실패 내성
- [x] 시험: 병렬 = 순차, num_threads=1·2

## K-4 종료 코드
- [x] unified_analyzer: 렌더·파트 단면·단면 영상 실패 → rc 3 (재귀 모드 포함)
- [x] koo_deep_report `_run_ua`: rc 3 → 경고 기록, 2차 패스 실패도 기록
- [x] 보고서에 렌더 실패 경고 표시
- [x] 시험 (python tests/test_render_failure_reporting.py)

## K-1 LS-PrePost
- [x] 작업자 HOME lsppconf 에 max_physical_memory 기록 (모든 실행 경로)
- [x] LS-PrePost 종료 코드 전달 (Xvfb 종료 코드 아님)
- [x] 산출물 검사: 존재·1 KB 이상·ffprobe 로 열림 (프레임 수 대조는 안 함 — 렌더러가 상태 수를 모른다)
- [x] SIF 안 실렌더 확인

## P-1
- [x] 파트별 2차 패스에서 개관 render_jobs 제외 + 시험

## 마무리
- [x] ctest · 파이썬 시험
- [x] 회신 문서(reply-to-kooremapper.md) — §5 질문 둘 답 포함
- [x] 의미 단위 커밋 (66c9f7b · 6a0d0d1 · c65bf31 · 441cfbd · efd6c6c)

## 남은 것 (사용자 판단)
- [x] origin push (5abbc76, 10-28 사용자 승인)
- [x] v42 빌드·배포 — 상류 pykoocae-53 이 표준 스크립트로(10-29 04:37Z). VERSION 5abbc76, 헤드리스 sha256 1a6e0933…, GUI 4536ea72…, tar `SmartTwinPostprocessor_20261029_v42.tar.gz`. 빌드 원본·/data·compute-node-images·헤드 /opt 4곳 동일
- [x] v42 검증(우리, `.work/v42_verify/`) — 헤드 /opt·/data sha 일치, 12 GiB 분석 rc 1+사유, 1.6 GB 상한 렌더 rc 3, 20M 심은 작업자 설정 덮어씀·영상 정상. DynaForge 도 운영 덱·20M 심기로 새 판 정상·옛 판 0 재현 확인(KooRemapper 7818cbc)
- [ ] node001·node002 노드 로컬 /opt/apptainers — VM 꺼짐, 켜지면 상류가 deploy_apptainers.sh 로 보냄
- [x] 배포 뒤 이미지 VERSION 을 DynaForge(kooremapper 세션)에 알리기 — 그쪽이 같은 덱(Run_20260602_093237_801e2b)으로 단면 영상을 다시 재 0 프레임이 사라졌는지 확인해 준다. 그쪽은 rc 3 을 경고로 다루기로 했다(KooRemapper ca0b6e1)
- [ ] 이미 나간 운영 영상 0 프레임 일괄 점검 여부 (회신 §5-2)
- [x] P-3 state_step (aa5883f, 기본 1)
- [x] P-4 시도 → 되돌림: 둘째 영상부터 출력이 바뀜(PSNR 16.6–32 dB) — context-notes 참고, 사용자 판단 필요
- [ ] P-2 (파트별·iso_clip 기본값) — 사용자 결정으로 하지 않음
