# impact SOTA — 컨텍스트 노트 (결정과 근거, 계속 append)

## 2026-07-09 계획 확정

- **목표 규모 300+ 위치**(사용자), **html_report.py 전면 분할**(사용자). 계획 승인됨.
- 조사로 확정한 결정적 사실들.
  - 15.7MB의 97%가 payload, 그중 part_motion 12.5MB. `:4931 step=max(1,n//600)`은
    992//600=1이라 **다운샘플이 사실상 미작동** — 오타가 아니라 임계값 설계 오류.
  - trajectories는 캡 자체가 없음(:4818-4850).
  - **"pandas circular import" 진단은 stale** — 양 패키지에 pandas import 없음.
    binout_reader는 lasso.dyna를 lazy import(:64), ImportError면 **아무 메시지 없이**
    None 반환(loader.py:123-124는 빈 dict) → 6월 산출물의 energy_flows={} 전량 빈 값의
    유력 원인은 SIF 내 lasso 부재. P0에서 SIF 안 재진단으로 확정할 것.
  - deep의 MotionData에는 vel_x/y/z·acc_x/y/z가 **없어서** impact가 재사용 불가 —
    그래서 motion CSV 2회 파싱 해소는 "_parse_outputs 결과 소비"가 아니라
    **`parse_motion=False` 파라미터**가 정답 (설계 에이전트가 브리핑 오류 교정).
  - `_parse_initial_velocity_any` 전체 readlines가 **3콜사이트**(:621,:757,:771).
  - file://에서 fetch/XHR 불가 → 청크는 `<script src>` JSONP 방식만 가능.
    청크 단위는 per-position 번들(드릴다운 소비 패턴과 1:1).
- 순서 결정: 신뢰 fix(P1)와 로더 성능(P2)을 **분할(P3) 전에** — 분할 중 rebase 고통 회피,
  작은 diff가 큰 파일 이동과 섞이지 않게. 분할은 바이트 골든 → 정규화 골든 2단계.
- Finding 폭발 방지 하드 룰: loader Finding은 **항상 집계 1건 + detail에 run 목록**.
- 절대 임계값 발명 금지: 통계 outlier(robust z) + CLI 명시값만.

## P0 진행 중 발견

- **generate_sample.py 결정성 버그 (골든 하니스가 즉시 잡음)**: `--seed 42`를 줘도
  두 실행의 trajectory 좌표가 달랐음. 원인은 `:1056`의 `abs(hash((face, u, v, seed)))` —
  파이썬 str `hash()`는 PYTHONHASHSEED로 **프로세스마다 salt**가 달라짐. docstring의
  "deterministic per seed" 주장이 거짓이었음. `zlib.crc32`로 교체(프로세스/머신 안정).
  교훈: "seedable" 픽스처도 골든으로 검증 전엔 못 믿는다.
- 골든 해시 전 **dataset 경로 스크럽** 필요: payload의 meta.test_dir 등에 tmp 경로가
  박히므로 `<DATASET>` 토큰으로 치환 후 해시.
- 골든 결정성 확정: pytest 3회 연속 동일(바이트+정규화 3종), 기존 15 테스트 green.

## P0 binout 재진단 결과 (node001, SIF 3b57b46 내부, 2026-07-09)

- `from lasso.dyna import Binout` → **ModuleNotFoundError: No module named 'lasso'**.
- 직렬(부모 프로세스) `load_binout_energy` 도 전부 None → **풀/fork 문제 아님**.
- binout0000 파일은 존재 → 데이터 문제 아님.
- **확정 원인: SIF 에 lasso-python 미설치** + ImportError 무음 소멸(loader.py:131-133).
  과거 "pandas circular import" / "ProcessPoolExecutor" 진단은 모두 오진이었음.
- 결정(1.3-B): SIF .def 에 `pip install lasso-python` 추가 (rcforc contact mask 까지
  확보 — 네이티브 matsum 리더보다 이득). 구조화 에러 캡처(1.3-A)는 그대로 진행해
  향후 재발 시 배지/Finding 으로 표면화.

## P0 기준선 (회귀 비교용)

- 재생성(25 DOE, deep-reuse): ~6s. HTML 15.7MB (payload 15.33MB).
- 배지: ENERGY BALANCE FAIL (25/25) — 거짓. Finding: INFO 2건뿐.
- energy_flows={}, diss_pct=0.0(조작성), impactor mass 는 b24899c 이후 정상(1.68e-5).

## P1(b) 중 결정적 발견 — binout 이중 결함 (2026-07-09)

- SIF: lasso 부재 (P0 진단). **로컬(lasso 있음)에서도 matsum=None** — 두 번째 층 존재.
- 근본: binout 의 matsum 브랜치는 멀쩡(25파트×201스텝 KE/IE 존재)한데,
  `legend`(파트 이름) 디코딩이 lasso 에서 `ValueError: chr() arg not in range` 로
  죽고, `_parse_matsum` 의 포괄 except 가 **이름 하나 때문에 에너지 전체를 폐기**.
  rcforc 도 `side`/`legend` 브랜치 부재로 동일 패턴 전멸(54개 인터페이스 버려짐).
- fix: `_read_opt()` — 옵셔널 필드(legend/side)는 실패 시 default 로 진행,
  필수 시계열은 살림. (koo_deep_report/core/binout_reader.py)
- **교차 검증**: 부활한 matsum KE/v² 질량 = 1.6749e-05 vs step_config ρ·V
  = 1.6836e-05 (0.5% 일치) — 독립 두 경로 상호 확증. KE 201.5 mJ = glstat
  ke 201.486 과 일치 (6월의 "flat KE"가 사실 임팩터 KE 였음도 설명됨).

## 커밋 로그 (진행하며 기록)

- fdc545c test(impact): 골든 하니스 + generate_sample PYTHONHASHSEED 결정성 fix
- 095e685 fix(impact): solver_quality significance floor (25/25 거짓 FAIL 소멸)
- d701ff4 fix(impact): 배지 3상태 + KPI diss 정직화 (실데이터 PASS16/FAIL9 진짜신호)
