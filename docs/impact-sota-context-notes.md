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

## P2 완료 (2026-07-09)

- **P2-1/2-2 (638f81c)**: keyword 1회 파싱 + velocity 1-스캔 캐시 +
  `_parse_outputs(parse_motion=False, series={stress,strain})` — 로드 57.6s→7.7s
  (7.5×), payload 바이트 불변.
- **P2-3 (af9037a)**: `--parallel-runs`(0=auto) / `--threads-per-run`.
  auto = SLURM_CPUS_PER_TASK(없으면 cpu_count) // threads_per_run.
  로컬 32코어 → 16워커 → **3.7s** (4워커 7.7s 대비 2×). deep-reuse 모드라
  워커가 unified_analyzer 를 안 돌리므로 워커 수 증가의 OOM 위험 없음.
- **P2-4 (56b3f68)**: solver_quality 감사를 _build_payload 직렬 루프에서 DOE
  워커로 이동. 키 절충: 워커는 generic pos_id("F5_P_0001")로 저장 → merge 가
  trajectories 와 같은 `next(iter(...))` re-key. payload 는
  `report.solver_quality` 우선, 비면 기존 직렬 fallback (face-tree 경로 보존).
  실데이터 per_position 25건 PASS16/FAIL9 — 이전과 동일 확인.
- **P2-5 (d6c6de3)**: provenance 는 **CLI 레이어만** 주입 — loader 를 결정적으로
  유지해 골든 바이트가 타임스탬프에 오염되지 않게 함(빈 dict 면 키 미출력).
  입력 digest 는 내용 해시가 아닌 stat(size:mtime_ns) 기반 — 수백 run ~ms.
  SIF 버전은 $KOOD3PLOT_HOME/VERSION 의 "Version:/Built:" 라인 파싱.

## P3 완료 (2026-07-09) — 14,609줄 → 154줄 + 19모듈, 11커밋 전부 골든 불변

- 이동 도구: AST 기반 move_leaf.py (scratchpad) — 함수 블록 verbatim 이동 +
  미정의 이름 자동 import 생성. **한계 발견**: 모듈 전체를 한 스코프로 보므로
  다른 함수의 지역 정의(`import math`, 지역 `_pct=` Store)가 모듈 필요를
  가림. → **pyflakes 전수 감사**로 3건 교정 (doe:_pct+math, physics:_r4,
  common:dataclasses+Enum). 골든 샘플이 doe 의 p5-percentile 분기를 안 타서
  바이트 골든만으론 안 잡혔음 — 실데이터 재생성이 잡음.
  **교훈: 분할 검증 = 골든 + pyflakes + 실데이터 3종 세트.**
- JS 307KB → 15세그먼트(원본 순서 보존), `_JS="".join(...)` 조립 == 원본
  바이트 assert 후 이동. 세그먼트는 각 섹션 모듈에 HTML 템플릿과 동거.
- FFT 사장본(첫 벌 136줄) 삭제 — 나중 def 가 이기므로 동작 불변.
- **nested _r4 는 dedupe 하지 않음** (계획 수정): restitution 내부본은
  비유한→None, 모듈본은 →0.0 — 의미가 달라 통합 시 payload 변형.
- 실데이터 확증: Test_Impact_A payload 분할 전후 deep-equal (provenance 제외).

## P4–P6 완료 (2026-07-10) — 스케일·파이프라인·UX·인사이트

- **P4**: `//600` 버그(992//600=1, 다운샘플 미작동 — payload 12.5MB 주범) ceil+peak-splice
  로 교체, tiers.py 단일 소스(A/B/C/D), t_ref dedup(위치별 공유 시간축), emit 3모드.
  15.38 → 5.50MB(-64%), true-peak 600/600 보존. **tier C/D 의 trajectory 를 0 으로
  비우면 5개 패널이 NaN/TypeError 로 죽는다** (Playwright 실측) → 초저해상(60/24pt)
  인라인이 정답. in-worker tiering 은 C/D 만 (A/B 풀해상 유지).
- **P5**: sidecar+--from-json(0.1s, 왕복 바이트 동일), per-run pickle 캐시
  (fingerprint=stat 기반, cold 4.1s→warm 0.2s, atomic tmp+rename). 캐시 스키마는
  워커 출력 "의미" 변경에도 범프해야 함 (v2: no-contact behavior).
- **P6 s9**: 설계 서브에이전트 산출(s9_design.md) 그대로 구현 — payload 갭이 실제로
  kpi.worst.pos_id 1줄뿐이었음. 내러티브는 슬롯식(S0 신뢰게이트 최우선), FAIL 런
  '순위 비교 용도' 강등 선언이 물리적으로 안전한 프로즈의 핵심.
- **인사이트 리뷰(서브에이전트) 12건 반영** — 최대 발견:
  ① 이 데이터의 진짜 헤드라인은 "유효 접촉 9/25, 그 9개 전부 에너지 게이트 FAIL"
    — 종전 보고서는 이를 hover 배지로만 숨기고 유일하게 물리가 있던 런들을
    outlier 로 지목하는 역전 서사였음. findings/hero/권고 Rule0 로 정면 배치.
  ② 임팩터(part 24)가 부품 집계에 혼입 → 16/25 셀의 "최악 부품"이 임팩터,
    안전지도는 임팩터 자유낙하 변위로 전면 at-risk. 제외 후 16 safe/9 at-risk.
  ③ `getattr(r,"pos_id")` 버그로 Symmetry/auto_recommend 가 조용히 사망 —
    소생 직후 X/Y 미러 페어 10+10·비대칭 98% 가 미접촉 공간 패턴을 자동 검출.
  ④ 미접촉 런이 '탄성 반사(초록)'로 렌더 → no-contact 클래스 신설(회색).
  ⑤ 전파속도 190,400 m/s 같은 불가능 수치 → no-contact 제외+12km/s 상한 게이트
    후 top median 171.7 m/s.
- 골든 재기록 총 4회 (t_ref/s9/배치1/배치3) — 전부 의도 변경, 재기록 전 Playwright
  콘솔 에러 0 확인이 게이트.

## 커밋 로그 (진행하며 기록)

- fdc545c test(impact): 골든 하니스 + generate_sample PYTHONHASHSEED 결정성 fix
- 095e685 fix(impact): solver_quality significance floor (25/25 거짓 FAIL 소멸)
- d701ff4 fix(impact): 배지 3상태 + KPI diss 정직화 (실데이터 PASS16/FAIL9 진짜신호)

## 에너지 흐름 P1-P6 완료 (2026-07-10) — 사용자 요구 "파트간 컨택힘/IE/KE 시계열"

끊긴 곳은 binout→EnergyFlow 조립부 한 곳뿐(설계 에이전트 실측)이었고, 파서·모델·
s3 7패널 JS 는 이미 완성돼 있었다. 서브에이전트 병렬 구현 + 내가 배선·검증.

- **P1 (9e0b788)**: binout_reader 에 matsum rbvelocity/hourglass/eroded + glstat 브랜치.
  ΣmatsumKE0=201.4864=glstat, 접촉런 CID173 peak|F|=1573.6N(계획서 1574 일치),
  glstat energy_ratio=1.131(sliding +49mJ 아티팩트 — 보존은 solver_quality 배지와
  짝지어 표기, 임계값 발명 안 함).
- **P2/P3/P4 (51b5b99)**: contact_map.py(*CONTACT→파트 다수결, 50/50 세트 100%
  단일파트, CID173→part24), energy_flow_builder.py(공용 중립 dict, cumtrapz
  impulse/work, engage 판정을 'peak|F|>0'→'임팩터 운동량 1% 초과'로 — 미접촉런
  솔버잔류력 0.5N 오판 방지), energy_flow.py 배선(dict→EnergyFlow, contact_map
  소프트로드, propagation_order 튜플화). 캐시 v3→v4. 실측 energy_flows 25키,
  **engage 9/25 = FAIL 런 집합과 정확히 일치**, kpi.diss_pct 41.2 소생.
- **P5 (06cf72e)**: _pickFlow 첫키 고정 결함 해소 → _flowFor(worst 접촉 기본).
  종전 F5_DOE_001(미접촉)이 걸려 SANKEY/TFH 빈 패널이던 것 → F5_DOE_024 기본으로
  7패널 채워짐. s9 selectPosition → refreshEnergyFlowForPos 연동. SANKEY
  total_w=0(pseudo) → total_imp fallback. 첫 행 "Impactor→Contact_173".
- **P6 (68c8680)**: ENERGY RESIDENCE TIMELINE 신규 패널 — 파트별 IE stacked +
  임팩터 KE 라인. 사용자 요구의 IE/KE 잔류 축 완성(기존 7패널이 컨택힘 담당).
- **tier (a2cf8bc)**: energy_flows 위치당 ~90KB → C/D 는 dissipated 상위 40만 인라인.

핵심 교훈:
- CONTACT_173/172 는 single-master(임팩터 vs ALL 디바이스)라 rcforc 가 파트별
  분해를 안 준다 → 임팩터→iface:173 pseudo 강등이 물리적으로 정직. 파트별 흡수는
  matsum IE(RESIDENCE 패널)가 담당. "파트 지어내기 금지" 원칙 준수.
- 미접촉 런도 솔버 잔류 접촉력 0.5N 을 가져 peak|F|>0 필터가 오작동 — 운동량 비율
  기준이 물리적으로 옳다(미접촉≤0.5%, 접촉≥100%).
- 최종 종합 검증(2026-07-10): 전 9섹션 Playwright 렌더 콘솔 에러 0, from-json
  왕복 바이트 동일, report.json sq 25/PASS16/FAIL9, impact/deep 스위트 22+17 passed.
