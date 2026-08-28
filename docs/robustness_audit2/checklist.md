# 2차 강건성 수정 체크리스트 (확정 20건)

## G1. 미리보기 캐시 무효화 재설계
- [ ] H1 `*INCLUDE` 소스 집합 수집기(파이썬, 깊이 8) 신설 → verify: include 만 바꿔도 재생성
- [ ] H2 unlink/권한 실패를 삼키지 않고 note 노출 → verify: chmod 555 에서 경고 확인
- [ ] H3 impact 선삭제 제거·원자 교체 → verify: make_stl 부재 시 옛 캐시 생존
- [ ] L6 sphere 선삭제 제거·원자 교체 → verify: 동일
- [ ] M4 impactor stamp 에 part_id 포함 → verify: part_id 만 바꿔도 재생성
- [ ] impact 안내 note 신설 → verify: 미리보기 없을 때 HTML 에 사유 표기

## G2. make_stl
- [ ] H7 TET10 코너 4개 축퇴 + 경고 → verify: 부피 0.16667 복원
- [ ] H6 쓰기 완결 검증(바이트 수 대조) → verify: 128KB tmpfs 에서 비0 exit
- [ ] L5 parts_csv 미존재 PID 경고 → verify: "1,999" 에 경고
- [ ] L7 strtol 인자 검증 → verify: 99999999999 / 6000xyz 거부

## G3. --from-json 계약
- [ ] H4 impact faces 구조 검증 → verify: faces="garbage" 비0 exit
- [ ] H5 sphere from_json 검증 신설 → verify: 무관 JSON 비0 exit
- [ ] M5 비수치 각도 거부 → verify: roll=null / pitch="abc" 비0 exit
- [ ] M3 사이드카 이름 HTML stem 파생 + 덮어쓰기 경고 → verify: 두 리포트 공존
- [ ] L4 --from-json 의 --format/--json 처리 → verify: json 요청 시 파일 생성

## G4. 지도 JS
- [ ] M1 drawRiskTable/updateMollInfo 비수치 가드 → verify: 오염 payload 로도 표 유지

## G5. 예제 번들
- [ ] H8 set -euo pipefail + 산출물 확인 → verify: 스텁 실패 주입 시 비0 exit
- [ ] M2 impact_report_data 동반 복사 → verify: 미디어 16/16 존재
- [ ] L1 sed → python 치환 → verify: 'R&D' 경로에서 정상
- [ ] L2 배포본 부재 안내 → verify: 없는 경로 지정 시 원인 출력

## G6. SIF
- [ ] L3 def %environment 에 koo_custom_report → verify: 컨테이너 안 import 성공

## 마무리
- [ ] 이전 강건성 11건 회귀 재생 (make_stl 인자 8종 등)
- [ ] 실데이터 3종 산출물 동등성
- [ ] 적대적 재공격 워크플로 (새 결함 유입 확인)
- [ ] 커밋 분할 (G1~G6)
- [ ] SIF 재빌드 → 배포 → standalone 동기화 → tar v29 → 알림
- [ ] 번들 재생성 + RUN_TESTS 실검증
