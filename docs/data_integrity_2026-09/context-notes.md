# 데이터 무결성 수정 — 결정 기록

계획: [plan.md](plan.md) · 체크리스트: [checklist.md](checklist.md)

## 2026-09-17 원인 분석 (코드 이력)

### JSON 시계열 잘림
| 날짜·커밋 | 일어난 일 |
|---|---|
| 2025-12-05 8f9ea8c | `AnalysisResult.hpp` "Limit output for readability (first 10, last 10 if > 20)". 들여쓰기 플래그 `pretty` 가 잘림까지 결정, 저장 경로는 늘 `toJSON(true)`. 이력 전체에서 `toJSON(false)` 호출 0회. **같은 커밋의 `test_large_dataset_json` 이 "omitted 가 있어야 통과" 로 잘림을 굳힘** |
| 2026-03-08 5c825be | deep report `_parse_series` 가 "unified_analyzer 가 잘라서 문자열을 넣는다, 걸러낸다" 주석과 함께 문자열만 제거 — 잘림을 알고도 크래시만 막음 |
| 2026-03-20 16e234a | 차트 `_downsample(500)` 추가 — 긴 시계열 전제, 입력이 20점인지 확인 안 함 |
| 2026-05-27~29 f2a7f97 | impact 세션이 5/27 그 주석을 읽고(대화 기록) 이틀 뒤 같은 데이터로 시계열 구성 |
| 2026-08-11 7b49fc3 | 바로 옆에 surface_strain JSON 작성기를 새로 넣으며 전체 기록 — 같은 파일 안에서 한쪽만 잘림 |

sphere 보고서는 CSV 를 직접 읽어 전체였다. 두 경로를 비교한 적 없음.

### 면 응력 (36ea5db 에서 수정)
- 8f9ea8c: `SurfaceExtractor.hpp:44` 가 `element_id` 를 "내부 0-based 순번" 으로 문서화했는데 같은 커밋의 응력 계산기는 실제 ID 사전에서 조회, 못 찾으면 0 텐서.
- 7b49fc3: 기능 확장 + 모든 분석에 ±Z 자동 주입. 검증은 "상·하면 값이 갈린다(478 vs 576)" — 옛 바이너리도 그럴듯하게 갈리는 값을 내며 399/400 상태 틀렸다.
- `test_surface_stress` 는 ctest 미등록, d3plot 검사는 개수만, 한 면 시험은 동어반복.

### libgtk
- 6/26 진단의 "libgtk 는 번들에 있음, apt 불필요" 는 **호스트**에서 ldd 를 돌려 호스트 GTK 를 찾은 착각. SIF 안에서는 래퍼 env 로도 not found.

### 공통 원인
실패를 0·자리표시로 위장 / 증상만 막음 / 그럴듯함으로 검증 / 실패할 수 없는(또는 결함을 요구하는) 시험 / 로직 복사 / 앞 세션의 "검증" 을 사실로 받아씀.

## 결정

- **JSON 은 원천(C++)에서 전 상태를 쓴다** (사용자 승인). 대가는 크기 — 992상태·24파트 약 4.6→16.6MB 추정, 4952상태 덱은 실측 예정. 스키마(`data: [{time,max,...}]`)는 유지해 소비처 호환.
- **수치는 jnum(유효숫자 10, defaultfloat, 비유한값 null)** 으로 통일. 핫스팟에서 이미 같은 이유로 바꿨던 방식.
- `vec3ToJSON` (방향 벡터, 설정 되돌려 쓰기)은 6자리 고정 유지 — 데이터가 아니고 기존 시험이 형식을 확인한다.
- **libgtk**: apt 에 `libgtk-3-0 libnotify4 libsecret-1-0`. 빌드 %post·%test 에서 래퍼 env ldd not found 면 실패. `! cmd` 는 `set -e` 에 안 걸려 명시적 exit 1 로 작성(처음 작성본이 누락 SIF 에서도 통과해 발견).
- 검증은 현 SIF 를 샌드박스로 풀어 3개만 설치 → 분석기와 같은 cfile·명령으로 렌더(22프레임 MP4). 같은 명령을 현 SIF 로는 exit 127.

## 작업 중 사고

- 점검 스크립트를 `inspect.py` 로 지어 그 폴더에서 돈 배포본 파이썬이 표준 `inspect` 대신 이 파일을 import → 즉시 죽음. 배포본 결함 아님. 이름 변경.
- `deep_report_timetest` 는 원본 Output(d3plot 250개) 중 21개만 심볼릭 링크 — unified_analyzer 직접 실행은 400상태, deep report 는 실제 경로를 따라 4952상태. 면 응력 대조는 lasso·C++ 가 같은 21개를 읽어 유효.
