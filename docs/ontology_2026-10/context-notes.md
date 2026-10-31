# 컨텍스트 노트 — 해석 결과 온톨로지화

## 출발 (10-31)
- 사용자 질문 「전각도 낙하 · 전위치 충격 결과가 파트 간 힘 · 에너지 전달을 온톨로지처럼 네트워크로 볼 수 있나」 → 런 하나의 네트워크는
  있으나(energy_flow_builder) 온톨로지는 아니다(관계 타입 빈약, 캠페인 집계 · 질의 저장소 없음, 일은 대리값). 사용자 지시: 전각도 낙하 결과를
  온톨로지화해 DynaForge 에 그 꼴로 넣고, 구조 · 충격해석 용어를 DynaForge 온톨로지 모듈의 DynaForge 전용 용어로 만든다.
  덧붙여 deep · sphere · impact 후처리가 온톨로지 연동 결과를 함께 내면 좋겠다.

## 어휘를 이렇게 정한 까닭
- **DynaForge 꼴 그대로** — SP import 꼴, slug 영문 snake_case, 이름 · 설명 한국어, 열거값은 문자열 목록. DynaForge 검증기
  (`platform/backend/app/runner/ontology_def.py`, 순수 파이썬)를 그대로 불러 검증했다(결함 0 · 주의 0, core 와 합쳐도 0).
- **`cae_` 접두 · 그룹 `cae`** — SP 관례(도메인 묶음은 그룹코드 접두). 허브의 `sim_*` 초안과 이름이 겹치지 않게 했다.
- **파트를 캠페인 범위로** — 각도마다 기기 절점이 바이트까지 같고(DynaForge 확인) 자세는 바닥 · 속도로 건다. 같은 파트를
  1,000번 만들 까닭이 없고, 전 방향 포락은 파트의 성질이다.
- **런별 전달을 객체로** — onto_relations 는 (관계 · src · dst)가 유일해 같은 두 파트 사이 런별 값을 관계 줄로 담을 수 없다.
- **양의 정의를 help 에** — 이름이 같은데 뜻이 다른 사례가 실제로 있었다: peak_disp(절점 최대) vs disp_ts(평균), peak_vm_strain
  (탄성 포함) vs peak_plastic_strain, total_work(평균 강체속도 차 대리값). DynaForge 요청 때도 키 이름 오독이 문제였다
  (dynaforge-export 메모).
- **단위** — DynaForge 의 unit 은 표시용 글자뿐이라 값 쪽에서 맞춰야 한다. 정규화 안(권장)은 결정 대기.

## 조사에서 나온 덤 (고칠 거리)
- sphere JS 안전율이 `DATA.yield_stress / peak_stress` — 파트별 항복값(part_yields)과 단위를 무시한다(html_report.py 2494–2499, 4449–4467).
  Python analyzer 는 yield_map 으로 맞게 셈한다 → 화면과 소견이 갈릴 수 있다. a9(koo_sphere_report)에 알릴 것.
- sphere 에너지 흐름이 `impactor_pid=None` 으로 빌더를 불러 맞닿음 판정이 `peak_force > 0` 으로 떨어진다 — 솔버 잔류 접촉력이 엣지가 될 수 있다.
- 각도 이름 → 방향이 두 갈래(Python to_spherical 은 lat=roll · lon=pitch, JS 는 Rᵀ(0,0,−1)). 꾸러미는 JS 와 같은 물리 방향을 쓴다.
- contact_map 이 접촉 카드 종류(TIED 등)를 버린다 · *INCLUDE 를 안 따른다.

## 구현하며 정한 것 (10-31)
- **결정 4건은 권장안으로 진행** — 대화가 이어지는 중에 질문으로 멈추지 않으려고. 모두 되돌리기 쉽다(단위 배수는 머리에
  남고, 기본 산출은 꾸러미 단계만 빼면 된다). 사용자 확인 대기.
- **단위를 바꿔 싣는 까닭** — 이 저장소의 원칙은 「응력을 환산하지 않는다」(yield_map docstring)지만, 그건 리포트 · 사이드카
  안에서 라벨과 함께 다니는 값 이야기다. DynaForge 속성은 단위 글자가 하나로 고정이라 SI 덱 값을 그대로 넣으면
  MPa 칸에 Pa 가 앉는다(1e6 배, 조용히 틀린다). 그래서 바꾸되 배수 · 덱 라벨을 머리에 남기고, 모르면 바꾸지 않는다.
  안전율은 덱 단위끼리 셈해서 단위와 무관하다.
- **참조 속성 + 관계 둘 다** — DynaForge 자체 어휘(dev_revision.task + revision_of)가 그렇다. 손으로 두 번 쓰다 어긋나지
  않게 작성기가 속성에서 관계 줄을 긋는다(REF_RELATIONS).
- **판정 규칙** — 응력 안전율 규칙은 공통(<1 critical, <1.5 warning, 불완전 warning). 가속도 기준(5만 · 20만 G)은
  전각도 낙하 분석기의 것이라 거기만. 부분충격 분석기는 「절대 임계값 발명 금지」로 가속도 기준을 일부러 두지 않았고,
  deep 은 응력비 0.8 경고를 쓴다 — 리포트마다 경고 문턱이 다를 수 있음을 어휘 설명에 적었다.
- **sphere 는 사후, deep 은 그 자리에서** — sphere 는 a9 가 고치는 패키지라 report.json 을 사후에 읽는다(post_analyze 마지막
  단계, S1 정보까지 담으려고 S1 뒤). deep 은 analysis_result.json 이 런당 93 MB 라 다시 읽지 않고 리포트가 메모리에 든
  결과에서 바로 쓴다.
- **0 위장 금지** — deep 의 PartSummary · MotionData 는 없을 때 0.0 을 준다(peak_strain, peak_max_principal, peak_acc_mag 등).
  꾸러미는 이력의 global_max · 열을 직접 본다.
- **흐름 그래프 단일 출처** — energy_flow_csv.build_flow 를 꺼내 CSV 와 꾸러미가 같은 그래프를 쓰게 했다.

## 실데이터에서 나온 결함 (10-31)
- **sphere 흐름 캐시가 수정 전 결과를 계속 냈다** — 63bad07(9-17)이 빌더 출력(충격량 자릿수, first_engage_t)을 바꿨는데
  `_FLOW_CACHE_SCHEMA` 는 3 그대로. 지문이 stat 뿐이라 옛 캐시가 맞다고 판정됐다. v14 CID 92: 캐시 0.4151 · 시각 없음 vs
  새로 셈 0.415073 · 1.9998e-05. a9 가 4 로 올림(2eeb7c0).
- **sphere 화면 안전율이 파트별 항복값 · 단위를 무시** — JS 5곳. a9 가 파이썬에서 한 번 환산해 싣는 식으로 고침(2eeb7c0).
- impact 의 ton-mm-ms 라벨 프리셋(MPa · kN · kJ)은 일관 단위계가 아니다(ton·mm/ms² = MN). 꾸러미는 이 단위계를 환산하지
  않는다. impact 담당에 알릴 것.

## DynaForge 검토 답신 반영 (10-31, 계약 초안 2)
- 답신: KooRemapper `docs/requests/kood3plotreader-ontology-review-2026-10-31.md`(7e8252d). 의견이며 채택 · 적재 범위는 사용자 결정.
- **심각도 대문자** — DynaForge 소견 · find_reports · max_severity · 화면이 CRITICAL/WARNING/INFO 다. 같은 개념 두 철자는 질의를
  두 벌로 만든다. 파트 판정 OK/WARNING/CRITICAL/UNKNOWN, 해석 품질도 impact 원문 철자(PASS/WARN/FAIL/UNKNOWN)로 맞췄다.
- **런 키 = impact_cases.case_key** — DynaForge parser 가 전각도는 folder → 방향 이름 → run_<len(cases)>, deep 은 `single`.
  같은 규칙으로 고르면 꾸러미의 런이 그 표 한 줄과 바로 이어진다. 실제 폴더는 run_folder.
- **다대일 줄을 뺐다** — v14 관계의 96% 가 참조 속성과 같은 사실의 두 번째 기록이었다. DynaForge 는 다대일을 줄로 쓰지 않기로
  했고, 「정본 하나」 원칙에도 맞다. 대응표는 머리 `ref_relations`. path_between 은 다대다라 줄로 남긴다(처음에 대응표에 넣어
  같이 빠졌던 것을 시험이 잡았다). v14 0.90 → 0.51 MB.
- **낙하 높이는 검산될 때만** — DropSet.json 의 drop_height 는 단위가 적혀 있지 않다. 덱 *INITIAL_VELOCITY 크기와 √(2gh) 가
  3% 안에서 맞으면 덱 길이 단위로 확인된 것으로 보고 싣는다(v14: 5424.0 vs 5424.5 mm/s). 안 맞으면 빼고 unit_note 에 사유.
- **재질** — keyword_parser 가 *MAT_…_TITLE 제목을 버리고 있었다. title 칸을 더해 material_name 으로 싣는다.
- **짝짓기 = HTML** — DynaForge 는 리포트를 HTML 에서 반입한다(답신 2). 그래서 꾸러미는 짝 HTML 과 같은 이름 줄기로 두고 머리
  `source.html` 에 HTML sha256 을 싣는다. deep 은 `ontology.json` 이던 것을 `report.ontology.json` 으로, HTML 을 다 쓴 뒤에 낸다.
  표본 셋을 어휘 0.2 로 다시 냈다(답신이 짚은 대로 0.1 지문이 남아 있으면 받는 쪽이 적재를 거절한다).
