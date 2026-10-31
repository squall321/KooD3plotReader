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
