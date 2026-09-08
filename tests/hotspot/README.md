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
