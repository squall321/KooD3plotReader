# KooD3plot CLI 설정 파일 예제

이 폴더에는 `kood3plot_cli`의 각 모드별 예제 설정 파일이 포함되어 있습니다.

## 파일 목록

| 파일 | 모드 | 설명 |
|------|------|------|
| `query_basic.yaml` | query | 데이터 추출 (응력, 변위 등) |
| `render_basic.yaml` | render | 단일 이미지/애니메이션 렌더링 |
| `batch_render.yaml` | batch | 배치 렌더링 |
| `multisection.yaml` | multisection | 다중 단면 렌더링 |
| `autosection.yaml` | autosection | 자동 단면 생성 |
| `multirun_comparison.yaml` | multirun | 다중 실행 비교 (공통 설정) |
| `multirun_single.yaml` | multirun | 개별 실행 설정 |
| `export_deformed.yaml` | export | 변형 노드 내보내기 |
| `export_all_states.yaml` | export | 모든 state 내보내기 |

## 사용법

### 1. Query 모드 (데이터 추출)
```bash
# 설정 파일 사용
kood3plot_cli --mode query --config query_basic.yaml

# 명령줄 직접 지정
kood3plot_cli --mode query -q von_mises -p Hood d3plot -o stress.csv
```

### 2. Render 모드 (단일 렌더링)
```bash
# 설정 파일 사용
kood3plot_cli --mode render --config render_basic.yaml

# 명령줄 직접 지정 (Windows)
kood3plot_cli --mode render --view isometric --fringe von_mises ^
  --lsprepost-path "C:\Program Files\LSTC\lsprepost.exe" ^
  d3plot -o output.png
```

### 3. Batch 모드 (배치 렌더링)
```bash
kood3plot_cli --mode batch --config batch_render.yaml d3plot -o output.png
```

### 4. MultiSection 모드 (다중 단면)
```bash
kood3plot_cli --mode multisection --config multisection.yaml d3plot -o section.png
```

### 5. AutoSection 모드 (자동 단면)
```bash
# 설정 파일 사용
kood3plot_cli --mode autosection --config autosection.yaml d3plot -o auto.png

# 명령줄 직접 지정
kood3plot_cli --mode autosection --animate d3plot -o auto.mp4
```

### 6. MultiRun 모드 (다중 실행 비교)
```bash
kood3plot_cli --mode multirun ^
  --run-config run1.yaml ^
  --run-config run2.yaml ^
  --threads 4 ^
  --comparison-output results/
```

### 7. Export 모드 (LS-DYNA 파일 내보내기)
```bash
# 변형된 노드 좌표
kood3plot_cli --mode export --config export_deformed.yaml

# 명령줄 직접 지정
kood3plot_cli --mode export --export-format displacement d3plot -o disp.k

# 모든 state 내보내기
kood3plot_cli --mode export --export-all d3plot -o states.k
```

## LSPrePost 설정 (Windows)

Windows에서 렌더링 기능을 사용하려면 LSPrePost가 필요합니다:

1. **다운로드**: https://ftp.lstc.com/anonymous/outgoing/lsprepost/
2. **설치 위치**: `C:\Program Files\LSTC\LSPrePost\` 또는 원하는 경로
3. **경로 지정 방법**:
   - 설정 파일: `lsprepost.executable` 항목 수정
   - 명령줄: `--lsprepost-path "경로"` 옵션 사용
   - 환경변수: PATH에 추가

## 팁

- 설정 파일은 YAML 또는 JSON 형식 모두 지원
- `-v` 또는 `--verbose` 옵션으로 상세 로그 확인
- `--help`로 전체 옵션 목록 확인
