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

## 커밋 로그 (진행하며 기록)

(작업 진행하며 여기에 추가)
