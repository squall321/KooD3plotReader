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
- [ ] origin push · SIF 재빌드 · 호스트(deploy_from_sif.sh)·node001 배포
- [ ] 이미 나간 운영 영상 0 프레임 일괄 점검 여부 (회신 §5-2)
- [ ] P-2 세션 수 · P-3 state_step · P-4 한 세션 여러 단면
