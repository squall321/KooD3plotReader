# 후처리 갭 대응 — 체크리스트

계획: [plan.md](plan.md) · 결정 기록: [context-notes.md](context-notes.md)

## P0. 진단이 거짓말하지 않게 ★먼저

### P0-1. 배포 tar 패키징 스크립트화 — 완료
- [x] `scripts/verify_package.sh` — 아카이브 독립 검증 도구 (기존 tar 에도 쓸 수 있게 분리)
- [x] `scripts/package_module.sh` — 배포 디렉토리를 묶고 **반드시** 검증, 실패하면 삭제
      → verify: VERSION 없는 디렉토리는 묶기 전에 거부, 아카이브 미생성
- [x] `--version-from <sif>` — SIF 안 `/opt/kood3plot/VERSION` 을 가져와 덮음
      → verify: 디렉토리 VERSION 이 `abc1234` 여도 아카이브는 `4815f55`
- [x] 아카이브 자기검증 6종 → verify: 정상 통과 / `unknown` 버전 / VERSION 누락 /
      lib 누락 / 최상위 2개 / 손상 tar — 6/6 의도대로
- [x] v29~v32 실물 재현 → verify: **v29 통과(eaffe54), v30·v31·v32 실패(VERSION 누락)**
      = 이번 사건의 재현 테스트

### P0-2. `unified_analyzer --capabilities` — 완료
- [x] JSON 출력 (tool/version/built/hotspot.{criteria,element_kinds,plastic_work,
      time_aggregate}/render.{lsprepost,section_view})
- [x] CMake 가 `git describe --tags --always --dirty` 를 빌드 시 주입
      → verify: `v2.4.0-233-gb86fe75-dirty` 출력, git 없으면 `unknown`
- [x] `allHotspotCriteria()` — 이름↔파서 **왕복으로 유도**, 손으로 적지 않음
      → verify: `tests/hotspot/test_capabilities.cpp` 10항목 전부 통과.
      목록 밖 enum 값(3..63)에 숨은 기준이 없음까지 확인
- [x] 광고 목록 == 실제 수용 집합 → verify: 실행 파일 JSON 의 3개 이름을 별도
      바이너리로 파싱해 정규 이름이 그대로 돌아옴 (교차 확인)
- [x] d3plot 없이 동작 → verify: 인자 없이 `--capabilities` exit 0

### P0-3. 산출물 버전 각인 — 완료 (deep 까지)
- [x] `Version::build_commit()` / `build_date()` — `src/Version.cpp` 로 분리
      (헤더 인라인에 매크로를 걸면 ODR 위반)
- [x] `analysis_result.json > metadata.tool_commit` / `tool_built`
      → verify: 실해석에서 `v2.4.0-234-g7d8a75d-dirty` / `2026-09-13T11:31:33Z`,
      `--capabilities` 의 version 과 **일치**
- [x] 기존 `kood3plot_version` 은 그대로 둔다 — 계속 `1.0.0` 이라 구분이 안 되지만
      읽는 쪽(HTML)이 있어 깨지 않는다. 새 필드를 병기
- [x] 없으면 키를 만들지 않는다 → verify: 옛 산출물이면 JSON 키 없음
- [x] deep report 푸터 → verify: 있으면 `빌드 | 커밋 · 시각`, 키를 지우면 줄 자체가
      사라짐, `tool_built` 만 없으면 커밋만 표시 (3경우 확인)
- [x] sphere — 런마다 다른 빌드로 분석됐는지까지 드러낸다
      → verify: 섞임 `⚠ builds: <커밋>(1), 기록 없음(3)` / 전부 같음 `build <커밋>` /
      기록 전무 시 아무것도 적지 않음. 1144각도 기존 리포트 회귀 없음
- [x] impact — `provenance.analysis_builds` + topbar 표시
      → 런별 `metadata.tool_commit` 을 집계해 provenance 에 싣고, 상단 바에
        단일이면 `BUILD <커밋>`, 혼재면 `⚠ BUILDS a(20), b(3), 기록없음(2)`
      → verify: 세 경우(기록 없음/단일/혼재) 모두 의도대로. 골든 `skeleton` 만
        바뀌고 `data` 는 그대로여서 변경 범위도 확인됨
      - federate/custom 은 analysis_result.json 을 직접 읽지 않아(전자는 sidecar,
        후자는 *SET_ 기반) 같은 방식이 성립하지 않는다 — 대상 아님

### P0-4. 배포 검증 스크립트 — 완료
- [x] `scripts/verify_deploy.sh <경로|sif> [...]` — VERSION ↔ `--capabilities` 대조
- [x] 디렉토리와 SIF 를 둘 다 받고, **대상 간에도** 대조 (호스트 vs SIF 가 이번 사건 형태)
- [x] 재현 테스트 → verify: 현재 배포본에서 **실패 3건** —
      호스트 `eaffe54` / SIF `4815f55` 불일치가 자동으로 드러남
- [x] 통과·실패 5경우 → verify: 일치 0 / VERSION 만 낡음 1 / VERSION 없음 1 /
      경로 없음 1 / 두 대상 같은 판 0
- [x] `set -u` 빈 배열 참조 버그 수정 (카운터로 대체)

### P0-5. 배포 — 완료 (2026-09-13)
- [x] main 에 push (SIF def 가 GitHub main 을 clone 하므로 필수) — `d8fe2bb`
- [x] SIF 재빌드 (918MB, 23:03) → `/data/SmartTwinPostprocessor` 배포
      → `/data` 가 NFS 공유이고 inode 가 같아 **node001 에 즉시 반영**된다
      (복사 전 SIF + 호스트 디렉토리 백업)
- [x] SIF `python/*`→`lib/*`, `bin/*`→`bin/*` 매핑. 호스트 고유 파일
      (`env.sh`/`lsprepost`/`analyze_and_report`)은 보존
- [x] **VERSION 배치** — 이번 사건의 핵심
- [x] `verify_deploy.sh` → verify: 호스트·SIF 모두 `d8fe2bb`, **전부 일치 (exit 0)**
      (이전에는 실패 3건 — 호스트 `eaffe54` vs SIF `4815f55`)
- [x] node001 확인 → verify: VERSION `d8fe2bb`, `--capabilities` 도 `d8fe2bb`
- [x] `package_module.sh` 로 v33 tar 생성 → `verify_package.sh` 통과
      → verify: **522MB** (v32 550MB 와 같은 규모), 구조는 v32 와 동일한
      `bin`/`lib`/`env.sh` 에 **`VERSION` 이 추가**됨 (1017 → 1046 항목)
      → 첫 시도는 **22GB** 였다. 배포 디렉토리를 통째로 묶어 그 안에 쌓인 지난
      tar 33개와 SIF 4개를 삼켰고, 검증기는 "빠진 것" 만 보느라 통과시켰다.
      담을 것을 명시하고(`VERSION env.sh bin lib`), 검증기가 `*.tar.gz`/`*.sif`
      자기포함을 잡도록 고쳤다

## P1. 조용히 틀리는 물리 경로

### P1-1. top_percent 독립 절대량 — 완료
- [x] `SinglePassAnalyzer::plasticStrainMax()` — 요소별 ε_p **이력 최댓값**
      (솔리드·셸·두꺼운 셸). 소성일과 조건이 달라 상태 1개짜리 덱에서도 기록
- [x] 파트 단위 `n_yield` / `vol_yield` / `vol_total` / `sum_eps_vol` / `max_eps` /
      `plastic_work_total` — **상위 백분위로 자르기 전에** 파트 전체로 집계
- [x] `yield_eps_threshold` 설정 (기본 0 = ε_p>0 이면 소성)
- [x] 없으면 키를 만들지 않는다 (`plastic_zone_available` / `plastic_work_available`)
- [x] 셸이 면적 가중이면 `plastic_work_total` 을 내지 않는다 (단위 불일치)
- [x] top_percent 독립성 → verify: `3%` vs `5%` 에서 **파트 절대량 34/34 동일**,
      선별 요소 수 30/34·클러스터 volume 합 21/34 달라짐
- [x] 독립 검증 → verify: d3plot 을 직접 읽는 별도 프로그램과 **5/5 항목 상대오차 0**
      (part 100: n_yield 1150, vol_yield 13089.06761, sum_eps_vol 0.01029100171,
      max_eps 8.689126844e-06)
- [x] 항등식 → verify: `vol_yield ≤ vol_total`, `n_yield ≤ element_count_total` 위반 0건
- [x] `--capabilities` 에 `plastic_zone: true` 반영
- [x] **기존 결함 동반 수정** — `jnum` 이 `fixed<<setprecision(8)` 이라 소수점 8자리에서
      잘렸다. ε_p(1e-6)는 유효숫자 3자리만 남고 1e-9 이하는 `0.00000000` 이 되어
      진짜 0 과 구분되지 않았다 → 유효숫자 10자리(defaultfloat)
      → verify: `4.347530478e-07` (이전 `0.00000043`), JSON 파싱 정상, 리포트 회귀 0

### P1-2. 시간 집계 옵션 — 완료
- [x] `HotspotCluster::member_idx/member_vol` — 2패스용 멤버십 (JSON 에는 안 냄)
- [x] `SinglePassAnalyzer::clusterTimeAggregate()` — 상태 루프 **1회**로 모든 덩어리를
      동시에 누적 (덩어리마다 따로 훑지 않는다)
- [x] YAML `hotspot_clusters.time_aggregate` — 모르는 값은 경고 후 기본값
      → verify: `bogus` 지정 시 사유 출력, 조용히 떨어지지 않음
- [x] 부등식 → verify: **17/17 성립** (shell 5·solid 2·thick_shell 10, 위반 0).
      비율 b/a 최소 0.6648 / 중앙 0.9906 / 최대 1.0000 — 기존 값이 최대 34% 과대평가
- [x] 모드별 동작 → verify: `elemmax_then_mean` 0개 / `mean_then_timemax` 17개 /
      `both` 17개 / `bogus` 0개+경고
- [x] `--capabilities` 에 3종 반영
- 주의: `mean_then_timemax` 와 `both` 는 **출력이 같다**. `stress_mean` 은 1패스
  부산물이라 어차피 나온다 — 헤더에 명시

### P1-3. 기준량 잔여
- [x] `max_shear = (σ1−σ3)/2` (별칭 `tau_max`/`tresca`) — 솔리드·셸·두꺼운 셸
- [x] 기준 슬롯을 `kHotspotCritSlots` 로 상수화 (하드코딩 `[3]` 20여 곳 정리)
- [x] 셸은 **같은 층 안에서** τ 를 계산 — 층별 σ1 최대와 σ3 최소를 따로 골라
      빼면 서로 다른 층 값을 섞게 된다
- [x] 2패스 시간집계에도 반영
- [x] 이론 범위 검증 → verify: 실덱 요소·시각 **20,898 표본에서
      τ/σ_vm ∈ [0.5002784, 0.5773503]**, 이론 [0.5, 1/√3=0.5773503], 범위 밖 0건
      (상한에 정확히 닿음 = 순수 전단 상태가 실재)
- [x] 덩어리 수준 → verify: τ_max ≤ (max σ1 − min σ3)/2 위반 0, τ 음수 0건,
      시간집계 부등식 19/19
- [x] `--capabilities` 자동 반영 → verify: 테스트가 `tresca`/`max_shear` 를 잡아
      기존 단언 2건이 깨졌다 (의도대로 기능 추가를 검출)
- [x] `x_tension` / `y_tension` / `z_tension` (별칭 `sxx`/`sigma_yy`/…)
      → 좌표계 확인 완료: `ls-dyna_database.txt` 가 셸 응력도
      "true stress in the **global** system" 으로 규정한다. 요소 좌표계는 굽힘
      모멘트 등 합력에만 해당 — 종류별로 뜻이 갈리지 않는다.
      다만 `*DATABASE_EXTENT_BINARY` CMPFLG=1 덱은 이 리더가 구분하지 못하므로
      enum 주석에 "그런 덱에서는 쓰지 말 것" 을 명시
- [x] 이론 검증 → verify: 고유값 정리상 σ3 ≤ σaa ≤ σ1 —
      실덱 **76,626 표본(요소×시각×3축)에서 위반 0건**
- [x] 덩어리 수준 → verify: σaa_max ≤ σ1_max 성립 14 / 위반 0
- [x] 기준 7종 동시 실행 → verify: 항목 34개씩 균일하게 산출

## P2. 오보를 낸 통계 경로

### P2-1. 공통 DOE 교집합 — 유틸 완료 (배선은 P3)
- [x] `koo_deep_report/core/doe_common.py` — `common_doe()` / `incomplete_cases()`
- [x] 임계 미만이면 **기본 거부** (`reject_below=True`)
- [x] **범인 지목** — 케이스를 하나씩 빼 교집합이 얼마나 회복되는지 계산
      → verify: 실제 사건 재현(T1~T3 은 185, T4_PV1 은 27) 시
      "'T4_PV1' 를 빼면 185개가 되므로, 그 케이스가 아직 다 돌지 않았는지
      확인하세요" 가 사유에 나온다
- [x] 임계값 정규화 → verify: 음수 0 클램프 / 실수 절삭 / 문자열·None 은 기본값
      (예전 판은 "-5" 를 음수 임계로 받아 **항상 통과**시켰다)
- [x] 경계 입력 16종 예외 0 → verify: dict 아님·빈 DOE·해시 불가 키·정렬 불가
      혼합 키 등 전부 거부 객체로 반환
- [x] 배선 완료 — `koo_scatter_report` ⑤b 섹션이 `common_doe()` 로 런 간 공통
      파트를 보고하고, 표본을 줄인 런을 지목한다

### P2-2. 통계 검정 유틸 — 완료 (배선은 P3)
- [x] `koo_deep_report/core/stats_ranking.py` — 평균순위 검정 / Spearman /
      recall@k / 구간 프로파일
- [x] 귀무 `(N+1)/2` **코드 고정** + 산출물에 `null_hypothesis` 문자열로 동봉
- [x] 정확 분포(동적계획법) — 연산량 상한 초과 시에만 정규근사, `method` 에 명시
- [x] 정확성 → verify: **전수 열거(N=6,k=4, 1296경우)에서 `P(p ≤ v) == v` 오차 0**.
      난수 십분위 균일성으로 보면 안 된다(p 값이 21가지뿐인 이산 분포라 멀쩡한
      구현이 떨어진다) — 시험 기준 자체를 바로잡았다
- [x] Spearman → verify: **scipy.stats.spearmanr 와 5케이스 1e-12 일치** (동점 포함)
- [x] recall@k → verify: 경계 동점을 불리하게 처리(회수율을 부풀리지 않음)
- [x] 계산 못 한 값은 `None` + 사유. 0 으로 채우지 않는다
- [x] 경계 입력 18종 예외 0, **numpy 없는 환경**에서도 import·동작
- [x] SIF 환경(다른 python)에서도 두 시험 통과
- [x] 배선 완료 — `koo_scatter_report` ⑤b 섹션에 평균순위 검정(파트별 p값)과
      Spearman 상관. **귀무가설 문구를 산출물에 함께 적는다**
      → verify: 파트 1개면 순위검정을 내지 않고(순위에 정보가 없다), 2개 이상이면
        `파트 7: 평균순위 1.00 (귀무 4.00) · p=0.0004165 [exact] ★`

## P3. 캠페인 그릇
- [x] **B-1 면 기준 편차각** — `core/face_deviation.py`
      → verify: 기준자세 6면 편차 정확히 0, 1e-7° 검출, 경계 15종 예외 0.
      `classify_direction` 이 실캠페인에서 격자 벗어남 8건(9.7356°)을 잡음
- [x] **B-2 롱포맷 캠페인 테이블** — `core/campaign_metrics.py`
      → verify: 미니 캠페인 4런에서 4,453줄 · 16지표, 파트 필터 동작,
      합성 시험 8절 전부 통과(깨진 런 건너뛰기·사유, TSV 저장 실패도 예외 대신 사유)
- [x] 줄마다 `tool_commit` 을 실어 런별 빌드 혼재를 나중에 알 수 있게
- [x] `koo_scatter_report` CLI 신설 — `python3 -m koo_scatter_report <dir> -o r.html`
      (`--part` / `--criterion` / `--metric` / `--ground-truth` / `--segments`)
- [x] 파이프라인 훅 — `post_analyze.sh --scatter` / `--scatter-opts "..."`
      → `runner_config.postprocess.auto_scatter` 는 **실행 러너 소관**이라 이 저장소에서
        만들 수 없다(그 파일에 `postprocess` 키 자체가 없다). 후처리 오케스트레이터인
        `post_analyze.sh` 에 단계를 붙이는 것이 실질이고, 러너는 이 옵션을 넘기면 된다
      → 모듈이 없으면 **사유를 말하고 건너뛴다**. 산포 리포트 실패가 앞 단계
        산출물(deep/sphere)을 죽이지 않는다
      → verify: 모듈 없을 때 안내 후 계속 / 있을 때 생성, `build_module.sh` 로
        패키지·PYTHONPATH·CLI wrapper 까지 배포본에 들어가는 것 확인

## P4. 나머지
- [x] **A-4 elout — 소스 전환 대신 '피크를 놓쳤는지' 교차 확인으로 구현**
      → `core/elout_peaks.py` + `campaign_cli --elout-check`
      → 소스를 elout 으로 바꾸면 요소 선별·군집까지 다시 맞춰야 하고, 검증할
        덱이 없다(가진 실덱 둘 다 `*DATABASE_ELOUT` 미설정). 더 작고 안전한 것을
        한다 — d3plot 피크와 elout 피크를 견주어 **"놓쳤을 수 있다" 를 알린다**
      → **파싱부와 계산부를 분리**했다. 계산부는 순수 함수라 합성 데이터로 완전히
        검증하고, 파싱부는 얇게 두고 못 읽으면 사유를 남긴다
      → verify: 합성 데이터로 피크 추출·비율·임계·경계 11종 전부 통과.
        실덱에서 "elout 분기가 없습니다 (*DATABASE_ELOUT 미설정). 있는 분기: …"
        를 정확히 말한다. d3plot 피크가 0 이면 비율을 지어내지 않는다
      → 부수 수정: lasso `Lsda.__del__` 이 읽기 모드에서 없는 `self.fw` 를 참조해
        GC 경고를 내던 것과, 디렉토리를 넘기면 Binout 내부 객체가 새던 것을 막았다
- [x] A-5 구간 분할 — `core/segment_boxes.py`
      → 박스(축 정렬) + 부채꼴(중심·반지름·각도·축) 두 형태. 인터포저 볼이 1파트인
      과제(T3/T4/카메라)에서 파트 안을 쪼개 실물 크랙 위치와 대조하기 위한 것
      → 겹치면 먼저 정의된 구간이 이긴다(결정적), 미배정 점은 버리지 않고 센다
      (조용히 사라지면 합이 안 맞는 이유를 알 수 없다)
      → verify: ±180° 감는 각도 구간, 뒤집힌 경계 자동 교정, 잘못된 정의 6종
      건너뛰기+사유, 경계 16종 예외 0
- [x] A-5 CLI 배선 — `campaign_cli --segment-boxes seg.json`
      → verify: 실캠페인에서 Q1~Q4 구간별 군집 수·최댓값 출력, 배정 안 된 군집은
        따로 세어 알린다(구간이 파트를 다 덮는지 확인하라고)
- [x] A-6 좌표 정합 — `core/coordinate_transform.py` (Kabsch + 잔차 판정)
      → 후처리는 변환을 전달받지 못한다(DropSet.json 에 기록 없음). **추정**하고
      잔차를 함께 낸다. 잔차가 크면 "강체 변환이 아니다" 를 경고
      → verify: 실제 사건 값(Δy≈−73.7, Δz≈+4.9) 복원 오차 1e-9, 회전각이 정확히 0
      (acos 이었다면 1e-6 잡음), 대응 오류 1점에 경고, 회전 결정 불가 시 지어내지 않음
      → 구현 중 IndexError·ValueError 2건을 시험이 잡아 수정
- [ ] A-6 배선 — `metadata.coordinate_transform` 에 싣기.
      유틸(`estimate_transform`)은 완성됐으나 **원본 덱 경로를 얻는 경로가 없다**.
      후처리는 결과 좌표만 보고 원본 도면을 모른다 — 시나리오가 원본 .k 경로를
      넘겨주는 규약이 생기면 그때 연결한다 (추측으로 찾으면 엉뚱한 덱을 문다)
- [x] B-1 완료 — `RUN_COLUMNS` 에 `dev_angle`/`dev_roll`/`dev_pitch`/`dev_yaw`
      → verify: 기준자세는 전부 0, 옛 코너(45,45)는 성분 편차가 0 이 아니다
- [x] B-5 ground truth 스키마 — `core/ground_truth.py`
      → TSV 필수 열 `case`/`face`/`part_id`/`verdict` + 선택 `mechanism`/`location`/`note`
      → `part_recall()` 이 P2 의 recall@k 를 실제로 쓴다 (적중·놓친 파트까지 반환)
      → verify: 열 순서 무관, 소문자 ng 인식, **verdict 를 모르면 줄을 버린다**
      (OK 로 치면 회수율이 부풀려진다), 경계 15종 예외 0
- [x] **C 그림 9종 — `koo_scatter_report` 신설 (B-0 도 함께 충족)**
      → ① 편차각 산포 ② 방향도 ③ 면×편차각 히트맵 ④ 회수율 recall@k
        ⑤ 편차각 구간 프로파일 ⑥ 리스크맵(전 각도 중첩) ⑦ 구간도
        ⑧ 둘레 전개도 ⑨ 실물 불량 오버레이
      → **외부 라이브러리 없이 SVG** 로 그린다. 기존 리포트는 Plotly 를 CDN 에서
        받는데, 망이 막히면 그림이 통째로 사라지고 아무 말도 남지 않는다
      → 있을 때/없을 때: 데이터 없는 그림은 **자리를 남기고 사유를 적는다**.
        섹션을 지우면 "원래 없는 것" 과 "못 그린 것" 이 구분되지 않는다
      → verify: 실캠페인에서 SVG 9개 생성(외부 요청 0), 불량 좌표를 주면 ⑥·⑨ 에
        ✕ 가 뜨거운 자리에 겹침. 차트 시험 60여 항목 + 통합 시험 9절, 예외 0
- [x] B-5 확장: ground truth 스키마에 선택 열 `x`/`y`/`z` — **셋 다** 있을 때만
      위치로 쓴다(두 축만 맞춰 그리면 엉뚱한 자리에 표시된다)

## 마무리
- [x] 검증 도구 자체 시험 — `tests/deploy/test_verify_package.sh` (9항목)
      → 이번 작업에서 검증기가 자기 목적을 못 지킨 사례가 **세 번** 나왔다
      (SIGPIPE 거짓실패 / 대상 간 대조 누락 / 자기포함 미검사). 셋 다 정상
      케이스는 통과했으므로, 시험을 "막으려는 그 사건을 잡는가" 로 짰다
- [x] 회귀 — Python 267개(40+27+31+169) + C++ 8종, 실패 0
- [x] 갭 문서 작성자에게 회신 — `reply-to-gap-report.md`
      → A-1 정정(이미 구현·배포됨 + VERSION 누락이 원인), 항목별 대응 결과,
        못 한 것(A-4 파싱부·A-6 배선)과 그 이유, 폐기 가능한 임시코드 목록
