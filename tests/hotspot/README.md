# 핫스팟 군집 · 기하 계산 단위 시험

의존성 없이 `g++` 만으로 돈다. CMake 빌드 없이 바로 검증할 수 있다.

```bash
cd <repo-root>

# 1) 기하·군집 (13항목)
g++ -std=c++17 -O2 -I include \
    tests/hotspot/test_hotspot_geometry.cpp src/analysis/HotspotClusterAnalyzer.cpp \
    -o /tmp/t1 && /tmp/t1

# 2) computeHexVolume 수정 검증 — 평면 요소 회귀 없음 + 뒤틀림 개선
g++ -std=c++17 -O2 -I include \
    tests/hotspot/test_hex_volume_fix.cpp src/analysis/HotspotClusterAnalyzer.cpp \
    -o /tmp/t2 && /tmp/t2

# 3) principalStresses 감사 — 해석해 · numpy eigvalsh 대조
g++ -std=c++17 -O2 -I include \
    tests/hotspot/test_principal_stress.cpp -o /tmp/t3 && /tmp/t3
```

세 시험 모두 `[PASS] 실패 0 건` 이어야 한다.

## 무엇을 지키는 시험인가

| 시험 | 지키는 것 |
|---|---|
| `test_hotspot_geometry` | 부피·도심이 해석해와 일치. tet 축퇴 패턴 2종, 쐐기, 사각뿔, 완전축퇴. 등가응력·등가변형률. 군집화 4종 |
| `test_hex_volume_fix` | 평면 요소는 5-사면체 분해와 동일(회귀 없음), 뒤틀린 요소만 개선. 부호 보존. 두 계산 경로 일관성 |
| `test_principal_stress` | 특성방정식 잔차 0, numpy 독립 계산 일치, **작은 스케일 텐서에서 주값이 평균으로 붕괴하지 않을 것** |

## 실덱 검증 도구 (라이브러리 링크 필요)

```bash
cmake --build build -j$(nproc)

# 연결성 값이 '내부 인덱스'인지 '사용자 ID'인지 확정
g++ -std=c++17 -O2 -I include tests/hotspot/probe_node_id_convention.cpp \
    build/libkood3plot.a -fopenmp -lz -o /tmp/probe && /tmp/probe <d3plot>

# nid-1 규약 vs real_node_ids 역맵 — 어느 쪽이 요소를 잃는가
g++ -std=c++17 -O2 -I include tests/hotspot/verify_node_id_convention.cpp \
    build/libkood3plot.a -fopenmp -lz -o /tmp/verify && /tmp/verify <d3plot>
```

실측(2026-09-08):

| 덱 | real_node_ids | nid-1 | 역맵 |
|---|---|---|---|
| `results/d3plot` | **비항등** | 실패 0 | **실패 8,000** (요소 1,000 = 2.24%) |
| `case_01_phase1_stacked_tier-1` | 항등 | 실패 0 | 실패 0 |
| `case_shell` | 항등 | 실패 0 | 실패 0 |

**항등인 덱에서는 두 규약이 같은 답을 낸다** — 그래서 역맵 오류가 오래 살아남았다.
