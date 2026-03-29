# Radioss → D3plot Converter

OpenRadioss animation 파일(A001~)을 LS-DYNA d3plot 포맷으로 직접 변환합니다.
VTK 중간 단계 없이 바이너리 직접 매핑하여 고속 변환합니다.

## 설치 경로

```
installed/bin/converter_radioss_to_d3plot
```

## 사용법

```bash
converter_radioss_to_d3plot <A001_file> [output_d3plot] [--verbose]
```

### 인자

| 인자 | 설명 | 기본값 |
|------|------|--------|
| `<A001_file>` | Radioss A001 파일 경로 (geometry + 첫 state) | 필수 |
| `[output_d3plot]` | 출력 d3plot 경로 | `d3plot` |
| `--verbose` | 상세 출력 | off |

### 예시

```bash
# 기본 사용
converter_radioss_to_d3plot simA001 output.d3plot

# 상세 출력
converter_radioss_to_d3plot /path/to/tube_crushA001 /path/to/tube_crush.d3plot --verbose
```

## 지원 요소/데이터

| 항목 | 지원 |
|------|------|
| Solid (8-node hex) | O |
| Shell (4-node quad) | O |
| Beam (2-node) | O |
| Node displacement | O (좌표 차분으로 계산) |
| Node velocity | O |
| Node acceleration | O |
| Solid stress tensor (6-comp Voigt) | O |
| Shell stress tensor (3-comp plane) | O |
| Plastic strain | O |
| Endian auto-detect | O (big/little) |
| Multi-file output (>2GB) | O |

## 파일 구조

OpenRadioss animation 파일은 각 파일이 독립적인 full format입니다:

```
A001: magic + time + texts + flags + 2D geometry + 3D geometry + 1D geometry + state data
A002: magic + time + texts + flags + 2D geometry + 3D geometry + 1D geometry + state data
...
```

- A001 = geometry (초기 좌표) + 첫 번째 시간 데이터
- A002~ = 이후 state (변형 좌표 + 결과값)

## OpenRadioss 후처리 연동

`KooOpenRadioss/DynaExamples/runAll.sh` 등에서 시뮬레이션 후 자동으로 d3plot 생성:

```bash
#!/bin/bash
# OpenRadioss 시뮬레이션 후 d3plot 자동 변환

STEM="tube_crush"
CASE_DIR="case01"

# 1. Radioss 실행
cd $CASE_DIR
../../bin/starter_linux64_gf -i ${STEM}_0000.rad
../../bin/engine_linux64_gf_ompi -i ${STEM}_0001.rad

# 2. Radioss → d3plot 변환
converter_radioss_to_d3plot ${STEM}A001 ${STEM}.d3plot

# 3. (Optional) koo_deep_report로 분석
koo_deep_report ${CASE_DIR} --output report
```

### Python 연동

```python
import subprocess

def radioss_to_d3plot(a001_path: str, d3plot_path: str) -> bool:
    """Convert Radioss animation to d3plot format."""
    result = subprocess.run(
        ["converter_radioss_to_d3plot", a001_path, d3plot_path],
        capture_output=True, text=True
    )
    return result.returncode == 0
```

## 성능

| 모델 | Nodes | Elements | States | d3plot | 변환 시간 |
|------|-------|----------|--------|--------|-----------|
| TubeCompress | 178 | 78 | 100 | 861KB | 0.006s |
| BallBounce | 73 | 36 | 35 | 129KB | 0.002s |
| PlateImpact | 269 | 108 | 99 | 1.3MB | 0.012s |
| SimpleDrop | 3,715 | 2,592 | 500 | 103MB | 0.63s |

VTK 경유 대비 약 3~5배 빠름 (중간 파일 I/O 제거).

## 빌드

```bash
cd KooD3plotReader/build
cmake .. -DCMAKE_BUILD_TYPE=Release
make converter_radioss_to_d3plot
# 바이너리: build/examples/converter_radioss_to_d3plot
```

## 제한사항

- SPH 요소 미지원
- Thick shell 미지원
- 3D tensor 데이터가 없는 모델에서는 stress=0으로 출력
- 요소 삭제(deletion) 정보는 현재 미전달
