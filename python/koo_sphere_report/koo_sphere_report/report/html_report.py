"""Single-file interactive HTML report generator. No external dependencies."""
import dataclasses
import html
import json
import math
from enum import Enum

from ..models import Report, Severity, SimulationResult


def _esc(s) -> str:
    return html.escape(str(s))


class _Encoder(json.JSONEncoder):
    def default(self, obj):
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return 0.0
        return super().default(obj)


def _build_report_data(report: Report, ts_points: int = 0, test_dir: str = "") -> dict:
    """Build JSON-serializable data object for embedding in HTML."""
    data = {
        "project_name": report.project_name,
        "doe_strategy": report.doe_strategy,
        "test_dir": test_dir,
        "total_runs": report.total_runs,
        "successful_runs": report.successful_runs,
        "failed_runs": report.failed_runs,
        "angular_spacing_deg": report.angular_spacing_deg,
        "sphere_coverage": report.sphere_coverage,
        "yield_stress": report.yield_stress,
        "sim_params": {
            "drop_height": report.simulation_params.drop_height,
            "t_final": report.simulation_params.t_final,
            "dt": report.simulation_params.dt,
            "density": report.simulation_params.density,
            "youngs_modulus": report.simulation_params.youngs_modulus,
        },
        "findings": [],
        "parts": {},
        "results": [],
    }

    for f in report.findings:
        data["findings"].append({
            "severity": f.severity.value,
            "title": f.title,
            "detail": f.detail,
            "recommendation": f.recommendation,
        })

    for pid, pi in report.part_info.items():
        data["parts"][str(pid)] = {"name": pi.part_name, "group": pi.group, "id": pid}

    # Time series resolution: user-specified or adaptive based on dataset size
    n_results = len(report.results)
    if ts_points > 0:
        ts_pts = ts_points
    else:
        ts_pts = 100 if n_results <= 50 else 30 if n_results <= 200 else 20
    comp_pts = max(1, ts_pts // 2)  # XYZ components at half resolution
    include_extras = n_results <= 200  # elem IDs, min values only for smaller datasets

    for sr in report.results:
        rd = {
            "folder": sr.run_folder,
            "angle": {
                "name": sr.angle.angle_name,
                "roll": sr.angle.roll,
                "pitch": sr.angle.pitch,
                "yaw": sr.angle.yaw,
                "category": sr.angle.category,
                "swap": sr.angle.swap_axes,
            },
            "num_states": sr.num_states,
            "parts": {},
        }
        for pid, pr in sr.parts.items():
            pd = {
                "peak_stress": round(pr.peak_stress, 2),
                "peak_strain": round(pr.peak_strain, 6),
                "peak_g": round(pr.peak_g, 1),
                "peak_disp": round(pr.peak_disp, 3),
            }
            if pr.stress and pr.stress.times:
                step = max(1, len(pr.stress.times) // ts_pts)
                pd["stress_ts"] = {
                    "t": [round(pr.stress.times[i], 7) for i in range(0, len(pr.stress.times), step)],
                    "max": [round(pr.stress.max_values[i], 2) for i in range(0, len(pr.stress.max_values), step)],
                    "avg": [round(pr.stress.avg_values[i], 2) for i in range(0, len(pr.stress.avg_values), step)],
                }
                if include_extras and pr.stress.min_values:
                    pd["stress_ts"]["min"] = [round(pr.stress.min_values[i], 2) for i in range(0, len(pr.stress.min_values), step)]
                if include_extras and pr.stress.max_element_ids:
                    pd["stress_ts"]["elem"] = [pr.stress.max_element_ids[i] for i in range(0, len(pr.stress.max_element_ids), step)]
            if pr.strain and pr.strain.times:
                step = max(1, len(pr.strain.times) // ts_pts)
                pd["strain_ts"] = {
                    "t": [round(pr.strain.times[i], 7) for i in range(0, len(pr.strain.times), step)],
                    "max": [round(pr.strain.max_values[i], 6) for i in range(0, len(pr.strain.max_values), step)],
                }
                if pr.strain.avg_values:
                    pd["strain_ts"]["avg"] = [round(pr.strain.avg_values[i], 6) for i in range(0, len(pr.strain.avg_values), step)]
            if pr.motion and pr.motion.times:
                step = max(1, len(pr.motion.times) // ts_pts)
                g_factor = 9810.0
                pd["g_ts"] = {
                    "t": [round(pr.motion.times[i], 7) for i in range(0, len(pr.motion.times), step)],
                    "g": [round(abs(pr.motion.avg_acc_mag[i]) / g_factor, 1) for i in range(0, len(pr.motion.avg_acc_mag), step)],
                }
                pd["disp_ts"] = {
                    "t": [round(pr.motion.times[i], 7) for i in range(0, len(pr.motion.times), step)],
                    "mag": [round(pr.motion.avg_disp_mag[i], 3) for i in range(0, len(pr.motion.avg_disp_mag), step)],
                }
                cs = max(1, len(pr.motion.times) // comp_pts)
                pd["acc_ts"] = {
                    "t": [round(pr.motion.times[i], 7) for i in range(0, len(pr.motion.times), cs)],
                    "x": [round(pr.motion.avg_acc_x[i] / g_factor, 0) for i in range(0, len(pr.motion.avg_acc_x), cs)],
                    "y": [round(pr.motion.avg_acc_y[i] / g_factor, 0) for i in range(0, len(pr.motion.avg_acc_y), cs)],
                    "z": [round(pr.motion.avg_acc_z[i] / g_factor, 0) for i in range(0, len(pr.motion.avg_acc_z), cs)],
                }
                pd["disp_comp_ts"] = {
                    "t": [round(pr.motion.times[i], 7) for i in range(0, len(pr.motion.times), cs)],
                    "x": [round(pr.motion.avg_disp_x[i], 2) for i in range(0, len(pr.motion.avg_disp_x), cs)],
                    "y": [round(pr.motion.avg_disp_y[i], 2) for i in range(0, len(pr.motion.avg_disp_y), cs)],
                    "z": [round(pr.motion.avg_disp_z[i], 2) for i in range(0, len(pr.motion.avg_disp_z), cs)],
                }
                pd["peak_vel"] = round(max(abs(v) for v in pr.motion.avg_vel_mag) if pr.motion.avg_vel_mag else 0.0, 1)
            rd["parts"][str(pid)] = pd
        data["results"].append(rd)

    return data


_CSS = """
:root {
  --bg: #0f1117; --bg2: #1a1b26; --bg3: #24283b;
  --fg: #d5daf0; --fg2: #bcc4e0; --dim: #7982a9;
  --red: #f7768e; --yellow: #e0af68; --blue: #7aa2f7;
  --green: #9ece6a; --cyan: #7dcfff; --magenta: #bb9af7;
  --orange: #ff9e64; --teal: #2ac3de;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--fg); font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace; font-size: 13px; overflow-x: hidden; }
.header { background: var(--bg2); border-bottom: 1px solid var(--bg3); padding: 16px 24px; display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.header h1 { font-size: 18px; color: var(--cyan); white-space: nowrap; }
.header .meta { color: var(--dim); font-size: 12px; word-break: break-word; }
.tabs { display: flex; background: var(--bg2); border-bottom: 2px solid var(--bg3); padding: 0 16px; overflow-x: auto; scrollbar-width: thin; }
.tab { padding: 10px 18px; cursor: pointer; color: var(--dim); border-bottom: 2px solid transparent; white-space: nowrap; user-select: none; transition: all 0.15s; flex-shrink: 0; }
.tab:hover { color: var(--fg); background: var(--bg3); }
.tab.active { color: var(--cyan); border-bottom-color: var(--cyan); }
.content { padding: 20px 24px; max-width: 1600px; overflow-x: hidden; }
.panel { background: var(--bg2); border: 1px solid var(--bg3); border-radius: 6px; padding: 16px; margin-bottom: 16px; overflow: hidden; }
.panel h2 { color: var(--cyan); font-size: 15px; margin-bottom: 12px; word-break: break-word; }
.panel h3 { color: var(--fg2); font-size: 13px; margin: 12px 0 8px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; table-layout: auto; }
th { background: var(--bg3); color: var(--cyan); padding: 6px 10px; text-align: left; position: sticky; top: 0; white-space: nowrap; z-index: 2; }
td { padding: 5px 10px; border-bottom: 1px solid var(--bg3); word-break: break-word; max-width: 250px; overflow-wrap: break-word; }
tr:hover { background: var(--bg3); }
.table-wrap { overflow-x: auto; max-width: 100%; }
.finding { padding: 8px 12px; margin: 4px 0; border-radius: 4px; overflow: hidden; }
.finding.CRITICAL { border-left: 3px solid var(--red); background: rgba(247,118,142,0.08); }
.finding.WARNING { border-left: 3px solid var(--yellow); background: rgba(224,175,104,0.08); }
.finding.INFO { border-left: 3px solid var(--blue); background: rgba(122,162,247,0.08); }
.finding .sev { font-weight: bold; font-size: 11px; }
.finding .sev.CRITICAL { color: var(--red); }
.finding .sev.WARNING { color: var(--yellow); }
.finding .sev.INFO { color: var(--blue); }
.finding .title { color: var(--fg); word-break: break-word; }
.finding .detail { color: var(--dim); font-size: 11px; margin-top: 2px; word-break: break-word; }
.finding .rec { color: var(--fg2); font-size: 11px; font-style: italic; word-break: break-word; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.stat-card { background: var(--bg3); border-radius: 6px; padding: 12px; text-align: center; overflow: hidden; }
.stat-card .value { font-size: 22px; font-weight: bold; color: var(--cyan); word-break: break-all; overflow-wrap: break-word; }
.stat-card .label { font-size: 11px; color: var(--dim); margin-top: 4px; }
select, input { background: var(--bg3); color: var(--fg); border: 1px solid var(--dim); border-radius: 4px; padding: 4px 8px; font-size: 12px; font-family: inherit; max-width: 250px; }
.controls { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.controls label { color: var(--dim); font-size: 11px; white-space: nowrap; }
svg text { font-family: inherit; }
.hidden { display: none !important; }
.mollweide-container { display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap; }
.device-3d { width: 200px; height: 240px; flex-shrink: 0; }
.device-inner { position: relative; transform-style: preserve-3d; transition: transform 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94); }
.device-face { position: absolute; border: 1px solid var(--dim); display: flex; align-items: center; justify-content: center; font-size: 10px; opacity: 0.85; backface-visibility: visible; }
.heatmap-cell { cursor: pointer; transition: opacity 0.15s; }
.heatmap-cell:hover { opacity: 0.8; stroke: white; stroke-width: 1.5; }
.chart-tooltip { position: fixed; background: var(--bg2); border: 1px solid var(--dim); border-radius: 4px; padding: 6px 10px; font-size: 11px; pointer-events: none; z-index: 1000; display: none; }
.small-multiples { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; }
.sm-item { background: var(--bg3); border-radius: 4px; padding: 8px; text-align: center; }
.sm-item .sm-label { font-size: 11px; color: var(--dim); margin-bottom: 4px; }
.view-toggle { display: inline-flex; border: 1px solid var(--dim); border-radius: 4px; overflow: hidden; }
.view-toggle button { background: var(--bg3); color: var(--dim); border: none; padding: 4px 12px; font-size: 11px; cursor: pointer; font-family: inherit; transition: all 0.15s; }
.view-toggle button.active { background: var(--cyan); color: var(--bg); }
.view-toggle button:hover:not(.active) { color: var(--fg); }
.risk-table-row { cursor: pointer; transition: background 0.15s; }
.risk-table-row:hover { background: rgba(125,207,255,0.1) !important; }
.risk-table-row.highlighted { background: rgba(125,207,255,0.15) !important; }
.contour-canvas { border-radius: 4px; }
.globe-canvas { border-radius: 50%; border: 1.5px solid var(--dim); background: var(--bg2); display: block; margin: 0 auto; }
.globe-container { margin-bottom: 10px; text-align: center; }
.envelope-area { opacity: 0.2; }
.chart-mode-toggle { display: inline-flex; border: 1px solid var(--dim); border-radius: 4px; overflow: hidden; margin-left: 12px; }
.chart-mode-toggle button { background: var(--bg3); color: var(--dim); border: none; padding: 3px 10px; font-size: 11px; cursor: pointer; font-family: inherit; }
.chart-mode-toggle button.active { background: var(--blue); color: var(--bg); }
.hotspot-badge { display: inline-block; background: var(--red); color: var(--bg); border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: bold; }
.hotspot-badge.warn { background: var(--yellow); }
.hotspot-badge.ok { background: var(--green); }
.dd-narrative { background: var(--bg3); border-radius: 8px; padding: 20px; margin-bottom: 16px; border-left: 4px solid var(--cyan); line-height: 1.8; color: var(--fg2); font-size: 12.5px; }
.dd-narrative .dd-heading { color: var(--cyan); font-size: 14px; font-weight: bold; margin-bottom: 10px; }
.dd-narrative .dd-para { margin-bottom: 10px; }
.dd-highlight { color: var(--fg); font-weight: bold; }
.dd-good { color: var(--green); font-weight: bold; }
.dd-warn { color: var(--yellow); font-weight: bold; }
.dd-bad { color: var(--red); font-weight: bold; }
.dd-kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 16px; }
.dd-kpi { background: var(--bg3); border-radius: 6px; padding: 10px; text-align: center; }
.dd-kpi .dd-kpi-val { font-size: 20px; font-weight: bold; word-break: break-all; }
.dd-kpi .dd-kpi-lbl { font-size: 10px; color: var(--dim); margin-top: 3px; }
.dd-kpi .dd-kpi-sub { font-size: 10px; color: var(--fg2); margin-top: 2px; }
.dd-section { margin-bottom: 16px; }
.dd-section-title { color: var(--cyan); font-size: 13px; font-weight: bold; margin-bottom: 8px; border-bottom: 1px solid var(--bg3); padding-bottom: 4px; }
.dd-bar { height: 14px; border-radius: 3px; display: inline-block; min-width: 2px; }
.dd-bar-track { background: var(--bg); border-radius: 3px; height: 14px; width: 100%; position: relative; }
.dd-group-compare { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; }
.dd-group-card { background: var(--bg3); border-radius: 6px; padding: 10px; }
.dd-group-card.dd-self { border: 1px solid var(--cyan); }
.re-chip { display: inline-flex; align-items: center; gap: 4px; background: var(--bg3); border: 1px solid var(--dim); border-radius: 12px; padding: 2px 10px 2px 8px; font-size: 11px; color: var(--fg2); margin: 2px; }
.re-chip .x { cursor: pointer; color: var(--dim); font-weight: bold; margin-left: 4px; }
.re-chip .x:hover { color: var(--red); }
.re-chip.selected { border-color: var(--cyan); color: var(--cyan); }
.re-opt-grid { display: grid; grid-template-columns: 120px 1fr; gap: 6px 12px; align-items: center; font-size: 12px; color: var(--fg2); }
.re-opt-grid label { color: var(--dim); text-align: right; }
.re-yaml-pre { background: #1a1b26; border: 1px solid var(--bg3); border-radius: 6px; padding: 12px; font-family: monospace; font-size: 11px; color: #9aa5ce; white-space: pre; overflow-x: auto; max-height: 400px; overflow-y: auto; line-height: 1.5; }
.re-yaml-pre .yk { color: #7aa2f7; } .re-yaml-pre .yv { color: #9ece6a; } .re-yaml-pre .yc { color: #565f89; }
.re-qbtn { background: var(--bg3); border: 1px solid var(--dim); border-radius: 4px; padding: 3px 10px; font-size: 11px; color: var(--fg2); cursor: pointer; }
.re-qbtn:hover { border-color: var(--cyan); color: var(--cyan); }
.re-mini-svg { cursor: crosshair; }
.re-mini-svg circle.sel { stroke: var(--cyan); stroke-width: 2; }
"""

_JS = r"""
let DATA = null;
let currentTab = 0;
let reportLang = 'ko';

const I18N = {
  // Overview
  reportGuideTitle: { en: 'How to Read This Report', ko: '리포트 해석 가이드' },
  tabGuideTitle: { en: 'Tab Guide', ko: '탭 가이드' },
  vonMisesTitle: { en: 'Von Mises Stress (MPa)', ko: 'Von Mises 응력 (MPa)' },
  vonMisesDesc: {
    en: 'The combined equivalent stress at each element. Used to predict yielding under complex loading.',
    ko: '다축 하중 조건에서의 등가 응력으로, 복합 응력 상태를 하나의 스칼라 값으로 환산하여 재료의 항복 여부를 판단하는 데 사용됩니다. 항복응력과 비교하여 안전계수(SF)를 산출합니다.'
  },
  reportMax: { en: "This report's max", ko: '본 분석 최대값' },
  yieldStress: { en: 'Yield stress', ko: '항복응력' },
  safetyFactor: { en: 'Safety Factor', ko: '안전계수' },
  sfSafe: { en: 'Safe', ko: '안전' }, sfMarginal: { en: 'Marginal', ko: '한계' }, sfYielding: { en: 'Yielding expected', ko: '항복 예상' },
  gforceTitle: { en: 'G-Force (MG = 10⁶ × g)', ko: 'G-Force (MG = 10⁶ × g)' },
  gforceDesc: {
    en: 'Peak acceleration in millions of g (1 MG = 1,000,000 × 9.81 m/s²). Represents the shock intensity experienced by each part.',
    ko: '충격 시 각 부품이 받는 가속도를 백만 G 단위(1 MG = 1,000,000 × 9.81 m/s²)로 표현합니다. 충격 강도의 직접적 지표이며, 부품의 내충격 사양과 비교하여 손상 가능성을 평가합니다.'
  },
  gforceTip: {
    en: 'Consumer electronics typically see 0.1–2.0 MG in drop tests. Higher values at smaller, stiffer parts are normal.',
    ko: '일반 소비자 전자기기 낙하 시험: 0.1–2.0 MG 범위. 작고 단단한 부품일수록 높은 가속도를 보입니다.'
  },
  strainTitle: { en: 'Effective Plastic Strain', ko: '유효 소성 변형률 (Eff. Plastic Strain)' },
  strainDesc: {
    en: 'Accumulated permanent deformation. A value of 0 means purely elastic (no permanent damage).',
    ko: '누적된 영구 변형량입니다. 값이 0이면 탄성 범위 내에서 하중을 받아 영구 변형이 없음을 의미합니다. 값이 클수록 재료의 파단 연신율에 근접하여 파괴 위험이 높아집니다.'
  },
  strainTip: {
    en: '> 0: Permanent deformation occurred. High values indicate material failure risk. Compare with material\'s elongation at break.',
    ko: '> 0: 영구 변형 발생. 재료의 파단 연신율과 비교하여 파괴 여유를 확인하세요.'
  },
  velTitle: { en: 'Peak Velocity (mm/s)', ko: '최대 속도 (mm/s)' },
  velDesc: {
    en: 'Maximum velocity of each part during impact. Related to kinetic energy transfer.',
    ko: '충격 중 각 부품의 최대 속도입니다. 운동 에너지 전달량과 직접적으로 관련되며, 자유낙하 충돌 속도를 초과하는 경우 응력파에 의해 부품이 가속된 것을 의미합니다.'
  },
  dispTitle: { en: 'Displacement (mm)', ko: '변위 (mm)' },
  dispDesc: {
    en: "Maximum displacement of a part's center of mass from its initial position.",
    ko: '부품 질량 중심의 초기 위치 대비 최대 이동 거리입니다. 큰 변위는 충격 중 부품이 크게 움직였음을 의미하며, 인접 부품과의 설계 여유(클리어런스)를 초과하면 간섭이 발생할 수 있습니다.'
  },
  dispTip: {
    en: 'Large displacement indicates the part moved significantly during impact. Compare with design clearances between parts.',
    ko: '인접 부품 간 클리어런스와 비교하여 간섭 여부를 판단하세요.'
  },
  doeTitle: { en: 'DOE Strategy & Coverage', ko: '실험계획법 (DOE) 전략' },
  doeTip: {
    en: 'cuboid_26: 6 faces + 12 edges + 8 corners. fibonacci: near-uniform sphere sampling for comprehensive coverage.',
    ko: 'cuboid_26: 면(6) + 모서리(12) + 꼭짓점(8)의 표준 방향. fibonacci: 구 위에 균일하게 분포하여 포괄적 방향 커버리지를 제공합니다.'
  },
  // Tab guide descriptions
  tgMollweide: {
    en: 'Spherical projection showing how each quantity varies across all drop directions. Hover to see per-angle details. The contour shows interpolated field; dots are actual simulation results.',
    ko: '구면 투영도로 모든 낙하 방향에 대한 물리량 분포를 시각화합니다. 등고선은 보간된 필드, 점은 실제 시뮬레이션 결과입니다. 마우스를 올리면 각 방향별 상세 수치를 확인할 수 있습니다.'
  },
  tgTimeHist: {
    en: 'Stress, strain, G-force, displacement waveforms over time. Compare angles side-by-side. Envelope mode shows min/max/avg range. XYZ mode shows directional components.',
    ko: '응력, 변형률, 가속도, 변위의 시간 이력 파형입니다. 여러 방향을 동시에 비교할 수 있으며, Envelope 모드는 전체 방향의 최소/최대/평균 범위, XYZ 모드는 축별 성분을 표시합니다.'
  },
  tgPartRisk: {
    en: 'Per-part worst-case values across all angles. Quickly identify which parts are most at risk and from which direction.',
    ko: '각 부품별로 모든 방향 중 최악의 값을 정리한 위험도 표입니다. 어떤 부품이 어느 방향에서 가장 위험한지 빠르게 파악할 수 있습니다.'
  },
  tgHeatmap: {
    en: 'Color-coded matrix of any quantity (stress, G-force, strain, displacement, velocity): parts × angles. Identifies concentration patterns.',
    ko: '부품 × 방향 행렬로 선택한 물리량(응력, 가속도, 변형률, 변위, 속도)을 색상으로 표시합니다. 집중 패턴과 취약 조합을 한눈에 확인할 수 있습니다.'
  },
  tgDirectional: {
    en: 'Ranks directions by severity. Category comparison (face/edge/corner), symmetry check, and axis dominance (X/Y/Z acceleration ratio) per direction.',
    ko: '방향별 심각도 순위, 카테고리별 비교(면/모서리/꼭짓점), 대칭성 검증, 축 우세도(X/Y/Z 가속도 비율) 분석입니다. 방향 의존성이 큰 부품을 식별합니다.'
  },
  tgFailure: {
    en: 'Safety factors (yield stress / peak stress). SF < 1.0 means yielding is expected under that load.',
    ko: '안전계수(항복응력 / 최대응력) 기반 파손 예측입니다. SF < 1.0이면 해당 하중 조건에서 항복이 예상됩니다.'
  },
  tgStats: {
    en: 'Mean, std dev, min/max per part. Scatter plots show correlations between stress, G-force, and velocity.',
    ko: '부품별 평균, 표준편차, 최소/최대 통계 요약과 응력-가속도-속도 간 상관관계 산점도입니다.'
  },
  tgImpact: {
    en: 'Peak timing analysis (when does maximum G occur), hot-spot elements (which elements are consistently most stressed across angles).',
    ko: '최대 가속도 발생 시점 분석, 반복적으로 높은 응력을 받는 핫스팟 요소 추적입니다.'
  },
  tgPartAnalysis: {
    en: 'Select one part for an in-depth report: KPI summary, auto-generated engineering narrative, stress envelope chart, direction vulnerability breakdown, load path (XYZ axis dominance), group comparison, and time-domain behavior.',
    ko: '하나의 부품을 선택하여 심층 분석합니다. KPI 요약, 자동 생성 엔지니어링 평가문, 응력 분포 차트, 방향별 취약성, 하중 경로 분석, 그룹 비교, 시간 영역 특성을 종합적으로 제공합니다.'
  },
  // Part Deep Dive
  engAssessment: { en: 'Engineering Assessment', ko: '엔지니어링 평가' },
  partDeepDive: { en: 'Part Deep Dive', ko: '부품 심층 분석' },
  selectPart: { en: 'Select Part:', ko: '부품 선택:' },
  stressEnvTitle: { en: 'Stress Envelope (All Angles, Sorted by Severity)', ko: '응력 분포도 (전체 방향, 심각도 순 정렬)' },
  stressEnvLegend: { en: 'Dashed cyan = mean | Shaded band = ±1σ', ko: '파선(시안) = 평균 | 음영 = ±1σ 범위' },
  yieldLine: { en: 'Dashed red = yield stress', ko: '파선(빨강) = 항복응력' },
  dirVulnTitle: { en: 'Direction Category Vulnerability', ko: '방향 카테고리별 취약성 분석' },
  dirVulnLegend: { en: 'Solid bar = max stress; faded bar = avg stress within category', ko: '진한 막대 = 최대 응력, 연한 막대 = 카테고리 내 평균 응력' },
  loadPathTitle: { en: 'Load Path Analysis (Acceleration Axis Dominance)', ko: '하중 경로 분석 (가속도 축 우세도)' },
  loadPathDesc: { en: 'X = lateral, Y = vertical, Z = longitudinal (averaged across all angles)', ko: 'X = 횡방향, Y = 수직방향, Z = 종방향 (전체 방향 평균)' },
  groupCompTitle: { en: 'Group Comparison', ko: '그룹 내 비교' },
  timeDomTitle: { en: 'Time-Domain Behavior', ko: '시간 영역 특성 분석' },
  avgTimeToPeak: { en: 'Avg Time to Peak (ms)', ko: '평균 최대값 도달 시간 (ms)' },
  avgNumPeaks: { en: 'Avg # Peaks (rebounds)', ko: '평균 피크 수 (리바운드)' },
  direction: { en: 'Direction', ko: '방향' },
  category: { en: 'Category', ko: '카테고리' },
  timeToPeak: { en: 'Time to Peak', ko: '최대값 도달 시간' },
  numPeaks: { en: '# Peaks', ko: '피크 수' },
  peakStress: { en: 'Peak Stress (MPa)', ko: '최대 응력 (MPa)' },
  peakG: { en: 'Peak G (MG)', ko: '최대 가속도 (MG)' },
  peakStrain: { en: 'Peak Strain', ko: '최대 변형률' },
  peakVel: { en: 'Peak Velocity (mm/s)', ko: '최대 속도 (mm/s)' },
  peakDisp: { en: 'Peak Disp (mm)', ko: '최대 변위 (mm)' },
  globalRank: { en: 'Global Stress Rank', ko: '전체 응력 순위' },
  stressCoV: { en: 'Stress CoV', ko: '응력 변동계수' },
  setYieldStress: { en: 'Set --yield-stress', ko: '--yield-stress 옵션 설정 필요' },
  thisPart: { en: '(this part)', ko: '(현재 부품)' },
  parts: { en: 'parts', ko: '개 부품' },
  angles: { en: 'angles', ko: '개 방향' },
  face: { en: 'face', ko: '면(face)' }, edge: { en: 'edge', ko: '모서리(edge)' }, corner: { en: 'corner', ko: '꼭짓점(corner)' },
  lateral: { en: 'lateral', ko: '횡방향' }, vertical: { en: 'vertical', ko: '수직방향' }, longitudinal: { en: 'longitudinal', ko: '종방향' },
  // Tab 10: Advanced Analysis
  tgAdvanced: {
    en: 'Seven advanced analysis modules: impact pulse characterization (half-sine equivalent), critical element tracking (hot-spot frequency), energy absorption (deformation work), rebound quantification (decay rate), cross-quantity correlation matrix, and crack arrest susceptibility (CAI index based on stress duration, loading rate, concentration, and energy dissipation).',
    ko: '7개 고급 분석 모듈: 충격 펄스 특성화(반파사인 등가), 크리티컬 요소 추적(핫스팟 빈도), 에너지 흡수(변형 일), 리바운드 정량화(감쇠율), 물리량 간 상관관계 매트릭스, 균열 정지 감수성(CAI — 응력 지속비, 하중속도, 응력 집중, 에너지 소산 기반)을 제공합니다.'
  },
  advTitle: { en: 'Advanced Analysis', ko: '고급 분석' },
  advSelectPart: { en: 'Analysis Part:', ko: '분석 부품:' },
  // Impact Pulse
  ipTitle: { en: 'Impact Pulse Characterization', ko: '충격 펄스 특성화' },
  ipDesc: {
    en: 'Extracts pulse width, peak acceleration, impulse area, and half-sine equivalent parameters from each impact direction. These are key parameters for shock specification (e.g., MIL-STD-810G Method 516.7, IEC 60068-2-27).',
    ko: '각 충격 방향에서 펄스폭, 최대 가속도, 임펄스 면적, 반파사인 등가 파라미터를 추출합니다. MIL-STD-810G Method 516.7, IEC 60068-2-27 등 충격 시험 규격의 핵심 파라미터입니다.'
  },
  ipGuide: {
    en: '<b>Pulse Width</b> — Duration of the primary impact pulse (10% threshold crossing). Shorter pulses excite higher-frequency modes. MIL-STD-810G typical: 0.5–3 ms for functional shock, 6–20 ms for transit drop.<br><b>Peak Acc</b> — Maximum deceleration in MG (10⁶×g). Determines whether components survive the shock. Compare with component shock ratings (e.g., HDD: 250G@2ms, SSD: 1500G@0.5ms).<br><b>Impulse</b> — Area under the |acceleration|×time curve (MG·ms). Represents total momentum transfer. Same peak with longer pulse = more damage potential.<br><b>Half-Sine Equivalent</b> — Industry-standard representation: a half-sine pulse with matching impulse. Used in shock test specifications to define equivalent test parameters. Duration & peak define the equivalent SRS (Shock Response Spectrum).',
    ko: '<b>펄스폭 (Pulse Width)</b> — 1차 충격 펄스의 지속 시간(10% 임계값 기준). 짧은 펄스는 고주파 모드를 여기시킵니다. MIL-STD-810G 참고: 기능 충격 0.5–3 ms, 수송 낙하 6–20 ms.<br><b>최대 가속도 (Peak Acc)</b> — MG 단위(10⁶×g) 최대 감속도. 부품의 내충격 사양과 비교하여 생존 여부를 판단합니다. 참고: HDD 250G@2ms, SSD 1500G@0.5ms.<br><b>임펄스 (Impulse)</b> — |가속도|×시간 곡선 아래 면적(MG·ms). 총 운동량 전달량을 나타냅니다. 동일 피크라도 펄스가 길면 손상 가능성이 높아집니다.<br><b>반파사인 등가 (Half-Sine Equiv.)</b> — 동일 임펄스를 갖는 반파사인 펄스로 변환한 산업 표준 표현. 충격 시험 규격에서 SRS(충격응답스펙트럼) 정의에 사용됩니다. 지속시간과 피크가 등가 시험 조건을 결정합니다.'
  },
  ipPulseWidth: { en: 'Pulse Width (ms)', ko: '펄스폭 (ms)' },
  ipPeakAcc: { en: 'Peak Acc (MG)', ko: '최대 가속도 (MG)' },
  ipImpulse: { en: 'Impulse (MG·ms)', ko: '임펄스 (MG·ms)' },
  ipHalfSine: { en: 'Half-Sine Equiv.', ko: '반파사인 등가' },
  ipHsDuration: { en: 'Duration (ms)', ko: '지속시간 (ms)' },
  ipHsPeak: { en: 'Peak (MG)', ko: '피크 (MG)' },
  ipEnvelope: { en: 'Shock Pulse Envelope', ko: '충격 펄스 엔벨로프' },
  // Critical Element
  ceTitle: { en: 'Critical Element Tracking', ko: '크리티컬 요소 추적' },
  ceDesc: {
    en: 'Identifies elements that are repeatedly most-stressed across multiple impact directions. High-frequency elements are fatigue/failure hot-spots requiring design attention.',
    ko: '여러 충격 방향에서 반복적으로 최대 응력을 받는 요소를 식별합니다. 빈도가 높은 요소는 피로/파손 핫스팟으로 설계 개선이 필요합니다.'
  },
  ceGuide: {
    en: '<b>Frequency</b> — How many impact directions produce peak stress at this element. An element appearing in >70% of directions is a <em>geometry-driven</em> stress concentration (fillet, notch, contact edge) — it will fail first regardless of impact angle.<br><b># Angles</b> — Number of distinct impact directions where this element is the most-stressed. High count = direction-independent vulnerability = geometric hot-spot.<br><b>Max vs Avg Stress</b> — If max >> avg, the element experiences occasional extreme loads (direction-dependent). If max ≈ avg, it is consistently highly stressed (geometry-driven).<br><b>Design implication</b> — Frequent hot-spot elements typically indicate: (1) insufficient fillet radius, (2) abrupt thickness transition, (3) stress-concentrating features (holes, notches), or (4) inadequate contact/bonding area. Consider local reinforcement, fillet enlargement, or material upgrade at these locations.',
    ko: '<b>빈도 (Frequency)</b> — 해당 요소가 최대 응력점으로 나타나는 충격 방향 수. 70% 이상의 방향에서 나타나면 <em>형상 기인</em> 응력 집중(필렛, 노치, 접촉 엣지)으로, 충격 방향에 관계없이 가장 먼저 파손됩니다.<br><b>방향 수 (# Angles)</b> — 해당 요소가 최대 응력을 받는 서로 다른 충격 방향의 수. 높으면 방향 독립적 취약점 = 기하학적 핫스팟.<br><b>최대 vs 평균 응력</b> — max >> avg이면 특정 방향에서만 극단적 하중(방향 의존적), max ≈ avg이면 일관되게 높은 응력(형상 기인).<br><b>설계 개선 지침</b> — 빈출 핫스팟 요소의 전형적 원인: (1) 부족한 필렛 반경, (2) 급격한 두께 변화, (3) 응력 집중 형상(구멍, 노치), (4) 불충분한 접촉/접합 면적. 해당 위치의 국부 보강, 필렛 확대, 재료 업그레이드를 고려하세요.'
  },
  ceElemId: { en: 'Element ID', ko: '요소 ID' },
  ceFrequency: { en: 'Frequency', ko: '빈도' },
  ceAngles: { en: '# Angles', ko: '방향 수' },
  cePeakStress: { en: 'Max Stress (MPa)', ko: '최대 응력 (MPa)' },
  // Energy Absorption
  eaTitle: { en: 'Energy Absorption Analysis', ko: '에너지 흡수 분석' },
  eaDesc: {
    en: 'Estimates deformation energy (stress × strain integration) per part per direction. Parts absorbing the most energy are primary shock absorbers or damage sites.',
    ko: '부품별/방향별 변형 에너지(응력 × 변형률 적분)를 추정합니다. 에너지 흡수가 큰 부품은 주요 충격 흡수 역할을 하거나 손상이 집중되는 부위입니다.'
  },
  eaGuide: {
    en: '<b>Deformation Energy (W = ∫σ·dε)</b> — The work done by stress through plastic strain increment. This is the physical energy absorbed as permanent deformation. Units are relative (MPa, energy density proxy without volume).<br><b>Interpretation</b> — High energy absorption can mean two things: (1) <em>Intended energy absorber</em>: design feature that protects other parts by absorbing impact (e.g., bumper, foam liner) — this is desirable. (2) <em>Damage indicator</em>: unintended plastic deformation concentrating energy in a critical part — this is dangerous.<br><b>Part Energy Share</b> — Fraction of total deformation energy absorbed by each part in the worst-case direction. A single part absorbing >50% indicates either (a) effective shock isolation or (b) a severe damage concentration. Compare with intended load path design.<br><b>Direction dependence</b> — Large variation across angles means the energy flow path changes with impact direction. Uniform distribution suggests robust energy management.',
    ko: '<b>변형 에너지 (W = ∫σ·dε)</b> — 소성 변형률 증분에 대한 응력의 일(work). 영구 변형으로 흡수된 물리적 에너지입니다. 단위는 상대값(MPa, 부피 미포함 에너지 밀도 프록시).<br><b>해석 방법</b> — 높은 에너지 흡수는 두 가지 의미: (1) <em>의도된 에너지 흡수체</em>: 범퍼, 폼 라이너 등 다른 부품 보호 목적의 설계 — 바람직함. (2) <em>손상 지표</em>: 의도하지 않은 소성 변형이 중요 부품에 집중 — 위험.<br><b>부품별 에너지 비율</b> — 최악 방향에서 각 부품이 흡수한 총 변형 에너지의 비율. 단일 부품이 50% 이상이면 (a) 효과적 충격 흡수 또는 (b) 심각한 손상 집중을 의미. 의도된 하중 경로 설계와 비교하세요.<br><b>방향 의존성</b> — 각도별 편차가 크면 에너지 흐름 경로가 충격 방향에 따라 변화. 균일하면 견고한 에너지 관리 설계.'
  },
  eaDeformEnergy: { en: 'Deformation Energy (Relative)', ko: '변형 에너지 (상대값)' },
  eaPartShare: { en: 'Part Energy Share', ko: '부품별 에너지 비율' },
  // Rebound
  rbTitle: { en: 'Rebound Quantification', ko: '리바운드 정량화' },
  rbDesc: {
    en: 'Measures secondary impacts, energy decay between bounces, and damping characteristics. Multiple rebounds can cause cumulative fatigue damage.',
    ko: '2차 충격, 바운스 간 에너지 감쇠, 감쇠 특성을 측정합니다. 반복 리바운드는 누적 피로 손상을 야기할 수 있습니다.'
  },
  rbGuide: {
    en: '<b># Bounces</b> — Number of significant acceleration peaks detected per direction. Each bounce is a separate impact event. From peak detection with threshold 15% of max, minimum separation 3 samples.<br><b>2nd/1st Ratio (COR proxy)</b> — Ratio of 2nd peak to 1st peak acceleration, approximating the Coefficient of Restitution (COR). COR = √(h₂/h₁) for free drops. Typical values: steel-on-steel 0.6–0.8, plastic 0.3–0.5, rubber 0.7–0.9. Higher ratio = more elastic = more bounce energy retained.<br><b>Decay Rate</b> — Exponential decay constant λ where peak_n ∝ e^(-λt). Higher values indicate faster energy dissipation (more damping). Relates to system damping ratio ζ ≈ λ/(2πf) where f is the natural bounce frequency.<br><b>Multi-bounce risk</b> — Multiple rebounds cause: (1) cumulative fatigue damage at stress concentrations, (2) repeated shock loading that can exceed static failure even if each individual pulse is below yield, (3) resonance excitation if bounce frequency matches component natural frequency. JEDEC JESD22-B111 (drop test for handheld devices) considers secondary impacts in qualification.',
    ko: '<b>바운스 횟수 (# Bounces)</b> — 방향별 검출된 유의한 가속도 피크 수. 각 바운스는 별도의 충격 이벤트입니다. 검출 기준: 최대값의 15% 임계값, 최소 3샘플 간격.<br><b>2차/1차 비율 (COR 근사)</b> — 2차 피크 대 1차 피크 가속도 비율로, 반발계수(COR)를 근사합니다. 자유낙하: COR = √(h₂/h₁). 참고값: 강-강 0.6–0.8, 플라스틱 0.3–0.5, 고무 0.7–0.9. 높을수록 탄성적 = 바운스 에너지 유지.<br><b>감쇠율 (Decay Rate)</b> — 지수 감쇠 상수 λ (peak_n ∝ e^(-λt)). 높을수록 빠른 에너지 소산(높은 감쇠). 시스템 감쇠비 ζ ≈ λ/(2πf)와 관련 (f: 고유 바운스 주파수).<br><b>다중 바운스 위험</b> — 반복 리바운드의 위험: (1) 응력 집중부의 누적 피로 손상, (2) 개별 펄스가 항복 이하라도 반복 충격으로 정적 파괴 초과 가능, (3) 바운스 주파수가 부품 고유진동수와 일치 시 공진 여기. JEDEC JESD22-B111(휴대기기 낙하시험)은 2차 충격을 자격 평가에 포함합니다.'
  },
  rbDecayRate: { en: 'Decay Rate', ko: '감쇠율' },
  rbSecondaryRatio: { en: '2nd/1st Ratio', ko: '2차/1차 비율' },
  rbNumBounces: { en: '# Bounces', ko: '바운스 횟수' },
  // Correlation Matrix
  cmTitle: { en: 'Cross-Quantity Correlation Matrix', ko: '물리량 간 상관관계 매트릭스' },
  cmDesc: {
    en: 'Pearson correlation between stress, G-force, strain, displacement, and velocity across all angles. Strong correlations reveal coupled failure modes.',
    ko: '전체 방향에 걸쳐 응력, 가속도, 변형률, 변위, 속도 간 피어슨 상관계수를 계산합니다. 강한 상관관계는 결합된 파손 모드를 나타냅니다.'
  },
  cmGuide: {
    en: '<b>Pearson r</b> — Linear correlation coefficient (-1 to +1). |r| > 0.7: strong, 0.3–0.7: moderate, < 0.3: weak. Computed across all impact directions for the selected part.<br><b>Stress ↔ G-force</b> — Strong positive (r > 0.7) is expected in rigid structures: higher deceleration → higher inertial stress. Weak correlation suggests stress is dominated by local contact/bending rather than global deceleration.<br><b>Stress ↔ Strain</b> — Strong positive means proportional loading (linear hardening). Weak correlation may indicate nonlinear material behavior, buckling, or contact-dominated response.<br><b>G-force ↔ Displacement</b> — Negative correlation is physically expected: stiffer impact (high G) → less displacement. Positive correlation suggests resonant amplification or secondary impacts.<br><b>Velocity ↔ G-force</b> — Strong positive expected: velocity at impact → peak deceleration. Low correlation suggests complex energy transfer paths (multi-body dynamics, wave propagation).<br><b>Practical use</b> — If stress and G-force are uncorrelated, you cannot use G-force alone as a damage proxy — explicit stress analysis is required for each direction.',
    ko: '<b>피어슨 r</b> — 선형 상관계수 (-1 ~ +1). |r| > 0.7: 강함, 0.3–0.7: 보통, < 0.3: 약함. 선택 부품에 대해 전체 충격 방향에 걸쳐 계산.<br><b>응력 ↔ 가속도</b> — 강한 양의 상관(r > 0.7)은 강체 구조에서 예상됨: 높은 감속 → 높은 관성 응력. 약한 상관은 응력이 전체 감속이 아닌 국부 접촉/굽힘에 지배됨을 의미.<br><b>응력 ↔ 변형률</b> — 강한 양의 상관은 비례 하중(선형 경화). 약한 상관은 비선형 재료 거동, 좌굴, 접촉 지배 응답을 시사.<br><b>가속도 ↔ 변위</b> — 음의 상관이 물리적으로 예상됨: 강성 충격(높은 G) → 적은 변위. 양의 상관은 공진 증폭 또는 2차 충격을 시사.<br><b>속도 ↔ 가속도</b> — 강한 양의 상관 예상: 충격 시 속도 → 최대 감속도. 낮은 상관은 복잡한 에너지 전달 경로(다물체 동역학, 파동 전파)를 시사.<br><b>실무 활용</b> — 응력과 가속도가 비상관이면 가속도만으로 손상을 대리 평가할 수 없으며, 각 방향별 명시적 응력 분석이 필요합니다.'
  },
  cmStress: { en: 'Stress', ko: '응력' },
  cmGforce: { en: 'G-force', ko: '가속도' },
  cmStrain: { en: 'Strain', ko: '변형률' },
  cmDisp: { en: 'Disp', ko: '변위' },
  cmVel: { en: 'Velocity', ko: '속도' },
  // Crack Arrest
  caTitle: { en: 'Crack Arrest Susceptibility', ko: '균열 정지 감수성 분석' },
  caDesc: {
    en: 'Evaluates crack arrest likelihood using four physically-motivated indicators derived from available time-series data. The Crack Arrest Index (CAI) combines: (1) stress duration ratio — fraction of time stress exceeds a threshold (shorter = more likely to arrest), (2) loading rate — dσ/dt at onset (high rate → brittle response → arrest-unfavorable), (3) stress concentration factor — max/avg stress ratio (high concentration → small plastic zone → arrest-unfavorable), (4) energy dissipation rate — how quickly deformation energy is released after peak (fast dissipation → arrest-favorable). CAI > 0.6: arrest likely, 0.3–0.6: marginal, < 0.3: arrest unlikely.',
    ko: '시계열 데이터로부터 도출한 4개의 물리적 지표를 활용하여 균열 정지 가능성을 평가합니다. 균열 정지 지수(CAI)는 다음을 조합합니다: (1) 응력 지속비 — 임계값 초과 시간 비율 (짧을수록 정지 유리), (2) 하중속도 — 충격 시작 시 dσ/dt (높으면 취성 거동 → 정지 불리), (3) 응력 집중 계수 — 최대/평균 응력 비 (높으면 소성 영역 작음 → 정지 불리), (4) 에너지 소산율 — 피크 후 변형 에너지 해방 속도 (빠르면 정지 유리). CAI > 0.6: 정지 가능, 0.3–0.6: 한계, < 0.3: 정지 불가.'
  },
  caiIndex: { en: 'Crack Arrest Index (CAI)', ko: '균열 정지 지수 (CAI)' },
  caiDuration: { en: 'Stress Duration Ratio', ko: '응력 지속비' },
  caiLoadRate: { en: 'Loading Rate Score', ko: '하중속도 점수' },
  caiSCF: { en: 'Stress Concentration Score', ko: '응력 집중 점수' },
  caiDissipation: { en: 'Energy Dissipation Score', ko: '에너지 소산 점수' },
  caiArrestLikely: { en: 'Arrest Likely', ko: '정지 가능' },
  caiMarginal: { en: 'Marginal', ko: '한계' },
  caiArrestUnlikely: { en: 'Arrest Unlikely', ko: '정지 불가' },
  // Render Export
  reTitle: { en: 'Render Config Export', ko: '렌더 설정 내보내기' },
  reAngleSelect: { en: 'Angle Selection', ko: '각도 선택' },
  reOptions: { en: 'Render Options', ko: '렌더링 옵션' },
  rePreview: { en: 'YAML Preview', ko: 'YAML 미리보기' },
  reAxis: { en: 'Section Axis', ko: '단면 축' },
  rePositions: { en: 'Section Positions', ko: '단면 위치' },
  reFringe: { en: 'Contour Quantity', ko: '컨투어 물리량' },
  rePartFilter: { en: 'Part Filter', ko: '부품 필터' },
  reFormat: { en: 'Output Format', ko: '출력 형식' },
  reResolution: { en: 'Resolution', ko: '해상도' },
  reFPS: { en: 'FPS', ko: 'FPS' },
  reDownload: { en: 'Download YAML', ko: 'YAML 다운로드' },
  reCopy: { en: 'Copy to Clipboard', ko: '클립보드 복사' },
  reSelected: { en: 'selected', ko: '개 선택됨' },
  reTopStress: { en: 'Top 5 Stress', ko: '응력 상위5' },
  reTopG: { en: 'Top 5 G', ko: 'G 상위5' },
  reClear: { en: 'Clear', ko: '초기화' },
  reRunGuide: { en: 'Run with:', ko: '실행 방법:' },
  reRefPart: { en: 'Ref Part:', ko: '기준 부품:' },
  reCustomPos: { en: 'Custom', ko: '커스텀' },
  caGuide: {
    en: '<b>Standard reference</b> — Crack arrest assessment follows concepts from BS 7910 (Guide to methods for assessing the acceptability of flaws in metallic structures), ASTM E1221 (Standard Test Method for K_Ia), and API 579-1/ASME FFS-1 (Fitness-For-Service). These standards define crack arrest toughness K_Ia and arrest criteria based on stress intensity vs. material resistance.<br><b>Stress Duration Ratio (w=30%)</b> — Fraction of event time where stress exceeds threshold. In crack mechanics, sustained tension keeps the crack open (Mode I). Short-duration pulses allow crack closure and arrest via compressive stress waves. Analogous to the concept of "arrest segment" in dynamic fracture mechanics where K_I drops below K_Ia.<br><b>Loading Rate (w=20%)</b> — dσ/dt at onset. Per ASTM E399/E1820, dynamic fracture toughness K_Id can be 30–70% lower than static K_Ic at high loading rates (>10⁶ MPa/s). Lower K_Id means cracks propagate more easily and arrest requires a larger toughness margin.<br><b>Stress Concentration (w=25%)</b> — σ_max/σ_avg ratio. The Irwin plastic zone size r_p ∝ (K/σ_y)². When SCF is high (localized stress), the plastic zone is small relative to the crack, reducing energy absorption and blunting. BS 7910 Annex M addresses stress concentration effects on flaw assessment.<br><b>Energy Dissipation (w=25%)</b> — Rate of post-peak stress decay. In dynamic fracture, the energy release rate G must exceed the material resistance R for crack propagation. Rapid stress decay means G drops quickly below R → arrest condition. Relates to the concept of crack arrest toughness where the running crack decelerates as the driving force diminishes.<br><b>Limitation</b> — CAI is a continuum-mechanics proxy. For rigorous crack arrest assessment per BS 7910 Level 3, explicit fracture mechanics modeling (CTOD, J-integral, K_I vs K_Ia curve) with actual crack geometry is required.',
    ko: '<b>참조 규격</b> — 균열 정지 평가는 BS 7910 (금속 구조물 결함 평가 지침), ASTM E1221 (K_Ia 시험법), API 579-1/ASME FFS-1 (적합성 평가)의 개념을 따릅니다. 이들 규격은 응력확대계수 대 재료 저항의 균열 정지 인성 K_Ia 및 정지 기준을 정의합니다.<br><b>응력 지속비 (w=30%)</b> — 임계 응력 초과 시간 비율. 균열역학에서 지속적 인장은 균열을 개방 상태로 유지(Mode I). 짧은 펄스는 압축 응력파에 의한 균열 닫힘과 정지를 허용합니다. 동적 파괴역학에서 K_I가 K_Ia 이하로 떨어지는 "정지 구간" 개념과 유사.<br><b>하중속도 (w=20%)</b> — 충격 시작 시 dσ/dt. ASTM E399/E1820에 따르면 동적 파괴인성 K_Id는 높은 하중속도(>10⁶ MPa/s)에서 정적 K_Ic의 30–70% 수준으로 저하. 낮은 K_Id는 균열 전파가 용이하여 정지에 더 큰 인성 여유가 필요.<br><b>응력 집중 (w=25%)</b> — σ_max/σ_avg 비율. Irwin 소성 영역 크기 r_p ∝ (K/σ_y)². SCF가 높으면(국부 응력) 균열 대비 소성 영역이 작아 에너지 흡수와 둔화 효과가 감소. BS 7910 부속서 M은 응력 집중이 결함 평가에 미치는 영향을 다룹니다.<br><b>에너지 소산 (w=25%)</b> — 피크 후 응력 감쇠 속도. 동적 파괴에서 에너지 해방률 G가 재료 저항 R을 초과해야 균열이 전파. 빠른 응력 감쇠는 G가 R 이하로 급감 → 정지 조건 성립. 구동력 감소에 따른 주행 균열 감속 개념과 관련.<br><b>한계</b> — CAI는 연속체 역학 프록시입니다. BS 7910 Level 3 수준의 엄밀한 평가에는 실제 균열 형상을 반영한 명시적 파괴역학 모델링(CTOD, J-적분, K_I vs K_Ia 곡선)이 필요합니다.'
  },
};
function L(key) { return (I18N[key] && I18N[key][reportLang]) || (I18N[key] && I18N[key]['en']) || key; }

function toggleLang() {
  reportLang = reportLang === 'ko' ? 'en' : 'ko';
  document.getElementById('lang-toggle-btn').textContent = reportLang === 'ko' ? 'EN' : '한';
  // Re-render current tab to apply language change
  const tabs = ['overview-stats','mollweide-content','timehistory-content','partrisk-content','gforce-content','directional-content','failure-content','statistics-content','impact-content','deepdive-content','advanced-content','render-export-content'];
  tabs.forEach(id => { const el = document.getElementById(id); if (el) el.dataset.done = ''; });
  renderTab(currentTab);
}

function init(data) {
  DATA = data;
  setupTabs();
  renderTab(0);
}

function setupTabs() {
  document.querySelectorAll('.tab').forEach((tab, i) => {
    tab.onclick = () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
      document.getElementById('tab-' + i).classList.remove('hidden');
      currentTab = i;
      renderTab(i);
    };
  });
}

function renderTab(i) {
  // Show/hide fixed sidebar only on Mollweide tab
  const sb = document.getElementById('moll-sidebar');
  if (sb) sb.style.display = (i === 1) ? '' : 'none';

  switch(i) {
    case 0: renderOverview(); break;
    case 1: renderMollweide(); break;
    case 2: renderTimeHistory(); break;
    case 3: renderPartRisk(); break;
    case 4: renderGForce(); break;
    case 5: renderDirectional(); break;
    case 6: renderFailure(); break;
    case 7: renderStatistics(); break;
    case 8: renderImpactAnalysis(); break;
    case 9: renderPartDeepDive(); break;
    case 10: renderAdvancedAnalysis(); break;
    case 11: renderRenderExport(); break;
  }
}

// ============ Tab 0: Overview ============
function renderOverview() {
  const el = document.getElementById('overview-stats');
  if (!el || el.dataset.done) return;
  el.dataset.done = '1';

  el.innerHTML = `
    <div class="stat-grid">
      <div class="stat-card"><div class="value">${DATA.successful_runs}/${DATA.total_runs}</div><div class="label">Simulations</div></div>
      <div class="stat-card"><div class="value">${DATA.doe_strategy}</div><div class="label">DOE Strategy</div></div>
      <div class="stat-card"><div class="value">${DATA.angular_spacing_deg.toFixed(1)}°</div><div class="label">Avg Spacing</div></div>
      <div class="stat-card"><div class="value">${(DATA.sphere_coverage*100).toFixed(0)}%</div><div class="label">Coverage</div></div>
      <div class="stat-card"><div class="value">${DATA.sim_params.drop_height.toFixed(0)} mm</div><div class="label">Drop Height</div></div>
      <div class="stat-card"><div class="value">${(DATA.sim_params.t_final*1000).toFixed(2)} ms</div><div class="label">Duration</div></div>
    </div>`;

  // Compute worst-case values for the guide
  const pids = getAllPartIds();
  let globalMaxStress = 0, globalMaxG = 0, globalMaxStrain = 0, globalMaxVel = 0;
  for (const r of DATA.results) {
    for (const pd of Object.values(r.parts)) {
      if (pd.peak_stress > globalMaxStress) globalMaxStress = pd.peak_stress;
      if (pd.peak_g > globalMaxG) globalMaxG = pd.peak_g;
      if (pd.peak_strain > globalMaxStrain) globalMaxStrain = pd.peak_strain;
      if ((pd.peak_vel||0) > globalMaxVel) globalMaxVel = pd.peak_vel;
    }
  }
  const ys = DATA.yield_stress;
  const globalSF = ys > 0 ? (ys / globalMaxStress) : 0;

  const guide = document.getElementById('overview-guide');
  if (guide) guide.innerHTML = `
    <div class="panel" style="margin-top:16px">
      <h2>${L('reportGuideTitle')}</h2>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;margin-top:8px">

        <div style="background:var(--bg3);border-radius:6px;padding:12px">
          <div style="color:var(--cyan);font-weight:bold;margin-bottom:6px">${L('vonMisesTitle')}</div>
          <div style="color:var(--fg2);font-size:12px;line-height:1.7">
            ${L('vonMisesDesc')}<br>
            <b>${L('reportMax')}: ${globalMaxStress.toFixed(1)} MPa</b><br>
            ${ys > 0 ? `${L('yieldStress')}: ${ys.toFixed(0)} MPa → ${L('safetyFactor')}: <span style="color:${globalSF<1?'var(--red)':globalSF<1.5?'var(--yellow)':'var(--green)'};font-weight:bold">${globalSF.toFixed(2)}</span><br>` : ''}
            <span style="color:var(--dim)">SF &gt; 1.5: ${L('sfSafe')} | SF 1.0–1.5: ${L('sfMarginal')} | SF &lt; 1.0: ${L('sfYielding')}</span>
          </div>
        </div>

        <div style="background:var(--bg3);border-radius:6px;padding:12px">
          <div style="color:var(--cyan);font-weight:bold;margin-bottom:6px">${L('gforceTitle')}</div>
          <div style="color:var(--fg2);font-size:12px;line-height:1.7">
            ${L('gforceDesc')}<br>
            <b>${L('reportMax')}: ${(globalMaxG/1e6).toFixed(2)} MG</b><br>
            <span style="color:var(--dim)">${L('gforceTip')}</span>
          </div>
        </div>

        <div style="background:var(--bg3);border-radius:6px;padding:12px">
          <div style="color:var(--cyan);font-weight:bold;margin-bottom:6px">${L('strainTitle')}</div>
          <div style="color:var(--fg2);font-size:12px;line-height:1.7">
            ${L('strainDesc')}<br>
            <b>${L('reportMax')}: ${globalMaxStrain.toFixed(4)}</b><br>
            <span style="color:var(--dim)">${L('strainTip')}</span>
          </div>
        </div>

        <div style="background:var(--bg3);border-radius:6px;padding:12px">
          <div style="color:var(--cyan);font-weight:bold;margin-bottom:6px">${L('velTitle')}</div>
          <div style="color:var(--fg2);font-size:12px;line-height:1.7">
            ${L('velDesc')}<br>
            <b>${L('reportMax')}: ${globalMaxVel.toFixed(1)} mm/s</b><br>
            <span style="color:var(--dim)">${reportLang==='ko' ?
              '자유낙하('+DATA.sim_params.drop_height.toFixed(0)+' mm) 충돌 속도 ≈ '+(Math.sqrt(2*9.81*DATA.sim_params.drop_height/1000)*1000).toFixed(0)+' mm/s. 이를 초과하면 응력파 가속 효과입니다.' :
              'Free-fall from '+DATA.sim_params.drop_height.toFixed(0)+' mm ≈ '+(Math.sqrt(2*9.81*DATA.sim_params.drop_height/1000)*1000).toFixed(0)+' mm/s impact velocity. Parts exceeding this were accelerated by stress waves.'}</span>
          </div>
        </div>

        <div style="background:var(--bg3);border-radius:6px;padding:12px">
          <div style="color:var(--cyan);font-weight:bold;margin-bottom:6px">${L('dispTitle')}</div>
          <div style="color:var(--fg2);font-size:12px;line-height:1.7">
            ${L('dispDesc')}<br>
            <span style="color:var(--dim)">${L('dispTip')}</span>
          </div>
        </div>

        <div style="background:var(--bg3);border-radius:6px;padding:12px">
          <div style="color:var(--cyan);font-weight:bold;margin-bottom:6px">${L('doeTitle')}</div>
          <div style="color:var(--fg2);font-size:12px;line-height:1.7">
            <b>${DATA.doe_strategy}</b> — ${DATA.total_runs}${reportLang==='ko'?'개 방향':' directions'}, ${reportLang==='ko'?'평균 간격':'avg spacing'} ${DATA.angular_spacing_deg.toFixed(1)}°.<br>
            <span style="color:var(--dim)">${L('doeTip')}</span>
          </div>
        </div>

      </div>
    </div>

    <div class="panel" style="margin-top:16px">
      <h2>${L('tabGuideTitle')}</h2>
      <div style="color:var(--fg2);font-size:12px;line-height:1.8">
        <b style="color:var(--cyan)">Mollweide Map</b> — ${L('tgMollweide')}<br>
        <b style="color:var(--cyan)">Time History</b> — ${L('tgTimeHist')}<br>
        <b style="color:var(--cyan)">Part Risk</b> — ${L('tgPartRisk')}<br>
        <b style="color:var(--cyan)">Heatmap</b> — ${L('tgHeatmap')}<br>
        <b style="color:var(--cyan)">Directional Sensitivity</b> — ${L('tgDirectional')}<br>
        <b style="color:var(--cyan)">Failure Prediction</b> — ${L('tgFailure')}<br>
        <b style="color:var(--cyan)">Statistics</b> — ${L('tgStats')}<br>
        <b style="color:var(--cyan)">Impact Analysis</b> — ${L('tgImpact')}<br>
        <b style="color:var(--cyan)">Part Analysis</b> — ${L('tgPartAnalysis')}<br>
        <b style="color:var(--cyan)">Advanced</b> — ${L('tgAdvanced')}
      </div>
    </div>`;
}

// ============ Tab 1: Mollweide ============
function mollweideProject(lonDeg, latDeg) {
  const lon = lonDeg * Math.PI / 180;
  const lat = latDeg * Math.PI / 180;
  // Poles: theta = ±π/2 exactly
  if (Math.abs(lat) > Math.PI/2 - 1e-10) {
    return [0, lat > 0 ? Math.SQRT2 : -Math.SQRT2];
  }
  // Solve 2θ + sin(2θ) = π·sin(φ) via damped Newton-Raphson
  const target = Math.PI * Math.sin(lat);
  let theta = lat;
  for (let i = 0; i < 100; i++) {
    const f = 2*theta + Math.sin(2*theta) - target;
    const fp = 2 + 2*Math.cos(2*theta);
    if (Math.abs(fp) < 1e-12) { theta += (lat > 0 ? -0.1 : 0.1); continue; }
    let dt = f / fp;
    if (Math.abs(dt) > 0.3) dt = dt > 0 ? 0.3 : -0.3;
    theta -= dt;
    theta = Math.max(-Math.PI/2 + 1e-10, Math.min(Math.PI/2 - 1e-10, theta));
    if (Math.abs(dt) < 1e-7) break;
  }
  const x = (2*Math.SQRT2/Math.PI) * lon * Math.cos(theta);
  const y = Math.SQRT2 * Math.sin(theta);
  return [x, y];
}

function mollweideXY(lonDeg, latDeg, cx, cy, rx, ry) {
  const [x, y] = mollweideProject(lonDeg, latDeg);
  const scale = rx / (2*Math.SQRT2);
  return [cx + x*scale, cy - y*scale];
}

function mollweideInverse(x, y) {
  // Inverse Mollweide: pixel coords -> (lon, lat) in degrees
  const theta = Math.asin(Math.max(-1, Math.min(1, y / Math.SQRT2)));
  const lat = Math.asin(Math.max(-1, Math.min(1, (2*theta + Math.sin(2*theta)) / Math.PI)));
  const cosTheta = Math.cos(theta);
  if (Math.abs(cosTheta) < 1e-10) {
    // At poles: lon is undefined, return lon=0 with clamped lat
    return [0, lat >= 0 ? 89.99999 : -89.99999];
  }
  const lon = (Math.PI * x) / (2*Math.SQRT2 * cosTheta);
  if (Math.abs(lon) > Math.PI) return null;
  return [lon * 180 / Math.PI, lat * 180 / Math.PI];
}

function isInsideMollweide(px, py, cx, cy, scale) {
  const mx = (px - cx) / scale;
  const my = (cy - py) / scale;
  const rx = 2*Math.SQRT2, ry = Math.SQRT2;
  return (mx*mx)/(rx*rx) + (my*my)/(ry*ry) <= 1;
}

function angleNameToDirection(name) {
  // Parse impact direction from angle name (e.g., "C1_Back_Right_Top")
  // Returns unit vector [x, y, z] representing which face/edge/corner hits ground
  // Convention: Back=-Z, Front=+Z, Right=+X, Left=-X, Top=+Y, Bottom=-Y
  let x = 0, y = 0, z = 0;
  const n = name.toUpperCase();
  if (n.includes('RIGHT')) x = 1;
  if (n.includes('LEFT')) x = -1;
  if (n.includes('TOP')) y = 1;
  if (n.includes('BOTTOM')) y = -1;
  if (n.includes('BACK')) z = -1;
  if (n.includes('FRONT')) z = 1;
  const mag = Math.sqrt(x*x + y*y + z*z);
  if (mag > 0) { x /= mag; y /= mag; z /= mag; }
  return [x, y, z];
}

function directionToLonLat(dir) {
  // Convert 3D direction vector to (lon, lat) for Mollweide projection
  // Convention: Center(0,0)=Back(-Z), North pole=Top(+Y), Right(+X)=East
  // Clamp lat to ±85 so poles stay visible inside the ellipse
  const [x, y, z] = dir;
  // At poles (x≈0,z≈0), atan2(0,-0) gives ±180 instead of 0; force lon=0
  const lon = (Math.abs(x) < 1e-10 && Math.abs(z) < 1e-10) ? 0 : Math.atan2(x, -z) * 180 / Math.PI;
  const lat = Math.asin(Math.max(-1, Math.min(1, y))) * 180 / Math.PI;
  return [lon, Math.max(-85, Math.min(85, lat))];
}

function eulerToLonLat(rollDeg, pitchDeg, yawDeg, angleName, swap) {
  // Use angle name to determine exact impact direction for Mollweide projection
  // Name-based decoding produces correct cube geometry (faces/edges/corners)
  // Euler angles alone cannot produce true cube corner directions (math limitation)
  if (angleName) {
    const dir = angleNameToDirection(angleName);
    if (dir[0] !== 0 || dir[1] !== 0 || dir[2] !== 0) {
      return directionToLonLat(dir);
    }
  }
  // Physical impact direction: Ry(pitch) * Rx(roll) * [0, 0, -1]
  // This gives consistent mapping regardless of DOE generator convention:
  //   roll → latitude (vertical), pitch → longitude (horizontal)
  // Preserves fibonacci lattice uniformity (CoV ~3%)
  if (mollweideState.swapRP) {
    // User toggled swap: treat pitchDeg as roll, rollDeg as pitch
    const tmp = rollDeg; rollDeg = pitchDeg; pitchDeg = tmp;
  }
  const r = rollDeg * Math.PI / 180;
  const p = pitchDeg * Math.PI / 180;
  // Rx(roll) * [0, 0, -1]
  const x1 = 0, y1 = Math.sin(r), z1 = -Math.cos(r);
  // Ry(pitch) * above
  const x2 = x1 * Math.cos(p) + z1 * Math.sin(p);
  const y2 = y1;
  const z2 = -x1 * Math.sin(p) + z1 * Math.cos(p);
  const lon = Math.atan2(x2, -z2) * 180 / Math.PI;
  const lat = Math.asin(Math.max(-1, Math.min(1, y2))) * 180 / Math.PI;
  return [lon, Math.max(-85, Math.min(85, lat))];
}

function getPartGroups() {
  const groups = {};
  for (const [pid, p] of Object.entries(DATA.parts)) {
    const g = p.group || 'Other';
    if (!groups[g]) groups[g] = [];
    groups[g].push(parseInt(pid));
  }
  return groups;
}

function getAllPartIds() {
  return Object.keys(DATA.parts).map(Number).sort((a,b)=>a-b);
}

let mollweideState = { quantity: 'peak_stress', partId: 0, hoveredAngle: null, viewMode: 'contour', showPoints: true, manualScale: false, scaleMin: 0, scaleMax: 0, swapRP: false };
let globeState = {
  viewLon: 0, viewLat: 0, targetLon: 0, targetLat: 0,
  rotating: false, animStart: 0, startLon: 0, startLat: 0,
  canvas: null, ctx: null, dataPoints: [], hoveredRi: -1,
  recording: false
};

function projectGlobe(lon, lat, vLon, vLat, R) {
  const lr = lon*Math.PI/180, la = lat*Math.PI/180;
  const vl = vLon*Math.PI/180, va = vLat*Math.PI/180;
  let x = Math.cos(la)*Math.sin(lr), y = Math.sin(la), z = Math.cos(la)*Math.cos(lr);
  // Y-rotation by -vLon to bring viewLon to center
  const cl = Math.cos(vl), sl = Math.sin(vl);
  const x1 = x*cl - z*sl, z1 = x*sl + z*cl;
  // X-rotation by +vLat to bring viewLat to center
  const ca = Math.cos(va), sa = Math.sin(va);
  return { x: x1*R, y: (y*ca - z1*sa)*R, z: y*sa + z1*ca };
}

function initGlobe() {
  const c = document.getElementById('globe-canvas');
  if (!c) return;
  globeState.canvas = c;
  globeState.ctx = c.getContext('2d');
  updateGlobeData();
  renderGlobe();
}

function updateGlobeData() {
  const qty = mollweideState.quantity, pid = String(mollweideState.partId);
  const pts = [];
  let vmin = Infinity, vmax = -Infinity;
  for (let ri = 0; ri < DATA.results.length; ri++) {
    const r = DATA.results[ri], pd = r.parts[pid];
    const v = getQtyValue(pd, qty);
    if (v < vmin) vmin = v; if (v > vmax) vmax = v;
    const [lon, lat] = eulerToLonLat(r.angle.roll, r.angle.pitch, r.angle.yaw, r.angle.name, r.angle.swap);
    pts.push({ lon, lat, v, ri });
  }
  if (mollweideState.manualScale && mollweideState.scaleMax > mollweideState.scaleMin) {
    vmin = mollweideState.scaleMin;
    vmax = mollweideState.scaleMax;
  }
  const vrange = vmax - vmin || 1;
  const invertColor = qty === 'safety_factor';
  globeState.dataPoints = pts.map(p => {
    const norm = Math.max(0, Math.min(1, (p.v - vmin) / vrange));
    return { lon: p.lon, lat: p.lat, ri: p.ri,
      rgb: valueToColorRGB(invertColor ? 1 - norm : norm) };
  });
}

function renderGlobe() {
  const cv = globeState.canvas, ctx = globeState.ctx;
  if (!cv || !ctx) return;
  const W = cv.width, H = cv.height, cx = W/2, cy = H/2, R = 115;
  const vLon = globeState.viewLon, vLat = globeState.viewLat;

  ctx.fillStyle = '#1a1b26';
  ctx.fillRect(0, 0, W, H);

  // Grid lines (front hemisphere only)
  ctx.strokeStyle = 'rgba(255,255,255,0.07)';
  ctx.lineWidth = 0.5;
  for (let lon = -180; lon <= 150; lon += 30) {
    ctx.beginPath(); let first = true;
    for (let lat = -90; lat <= 90; lat += 3) {
      const p = projectGlobe(lon, lat, vLon, vLat, R);
      if (p.z > 0) { const sx=cx+p.x, sy=cy-p.y; first ? ctx.moveTo(sx,sy) : ctx.lineTo(sx,sy); first=false; }
      else if (!first) { ctx.stroke(); ctx.beginPath(); first=true; }
    }
    if (!first) ctx.stroke();
  }
  for (let lat = -60; lat <= 60; lat += 30) {
    ctx.beginPath(); let first = true;
    for (let lon = -180; lon <= 180; lon += 3) {
      const p = projectGlobe(lon, lat, vLon, vLat, R);
      if (p.z > 0) { const sx=cx+p.x, sy=cy-p.y; first ? ctx.moveTo(sx,sy) : ctx.lineTo(sx,sy); first=false; }
      else if (!first) { ctx.stroke(); ctx.beginPath(); first=true; }
    }
    if (!first) ctx.stroke();
  }

  // Data points sorted back-to-front
  if (mollweideState.showPoints) {
    const proj = globeState.dataPoints.map(pt => {
      const p = projectGlobe(pt.lon, pt.lat, vLon, vLat, R);
      return { x: p.x, y: p.y, z: p.z, rgb: pt.rgb, ri: pt.ri };
    }).sort((a,b) => a.z - b.z);

    const nPts = proj.length;
    const gBaseR = nPts > 500 ? 2 : nPts > 200 ? 3 : 4;
    const gHoverR = gBaseR + 3;
    const gBackR = nPts > 500 ? 1.5 : 2.5;
    for (const pt of proj) {
      const sx = cx+pt.x, sy = cy-pt.y;
      const isHovered = pt.ri === globeState.hoveredRi;
      if (pt.z > 0) {
        const r = isHovered ? gHoverR : gBaseR;
        ctx.beginPath(); ctx.arc(sx, sy, r, 0, 2*Math.PI);
        ctx.fillStyle = `rgb(${pt.rgb[0]},${pt.rgb[1]},${pt.rgb[2]})`;
        ctx.fill();
        ctx.strokeStyle = isHovered ? '#fff' : 'rgba(255,255,255,0.25)';
        ctx.lineWidth = isHovered ? 2 : 0.8;
        ctx.stroke();
      } else {
        const r = isHovered ? gBackR + 1.5 : gBackR;
        ctx.beginPath(); ctx.arc(sx, sy, r, 0, 2*Math.PI);
        const d = pt.rgb.map(c => Math.floor(c*0.25));
        ctx.fillStyle = `rgb(${d[0]},${d[1]},${d[2]})`;
        ctx.fill();
      }
    }
  }

  // Outline
  ctx.strokeStyle = '#7982a9';
  ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.arc(cx, cy, R, 0, 2*Math.PI); ctx.stroke();
}

function rotateGlobeTo(lon, lat) {
  globeState.startLon = globeState.viewLon;
  globeState.startLat = globeState.viewLat;
  globeState.targetLon = lon;
  globeState.targetLat = lat;
  globeState.rotating = true;
  globeState.animStart = performance.now();
  requestAnimationFrame(animGlobe);
}

function animGlobe(ts) {
  if (!globeState.rotating) return;
  const t = Math.min(1, (ts - globeState.animStart) / 300);
  const e = 1 - Math.pow(1-t, 3); // ease-out cubic
  let dLon = globeState.targetLon - globeState.startLon;
  if (dLon > 180) dLon -= 360; if (dLon < -180) dLon += 360;
  globeState.viewLon = globeState.startLon + dLon * e;
  globeState.viewLat = globeState.startLat + (globeState.targetLat - globeState.startLat) * e;
  renderGlobe();
  if (t < 1) requestAnimationFrame(animGlobe);
  else globeState.rotating = false;
}

// High-resolution globe rendering for recording
function renderGlobeHR(ctx, W, vLon, vLat) {
  const cx = W/2, cy = W/2, R = W*0.46;
  ctx.fillStyle = '#1a1b26';
  ctx.fillRect(0, 0, W, W);
  // Grid lines
  ctx.strokeStyle = 'rgba(255,255,255,0.07)';
  ctx.lineWidth = 1;
  for (let lon = -180; lon <= 150; lon += 30) {
    ctx.beginPath(); let first = true;
    for (let lat = -90; lat <= 90; lat += 2) {
      const p = projectGlobe(lon, lat, vLon, vLat, R);
      if (p.z > 0) { const sx=cx+p.x, sy=cy-p.y; first ? ctx.moveTo(sx,sy) : ctx.lineTo(sx,sy); first=false; }
      else if (!first) { ctx.stroke(); ctx.beginPath(); first=true; }
    }
    if (!first) ctx.stroke();
  }
  for (let lat = -60; lat <= 60; lat += 30) {
    ctx.beginPath(); let first = true;
    for (let lon = -180; lon <= 180; lon += 2) {
      const p = projectGlobe(lon, lat, vLon, vLat, R);
      if (p.z > 0) { const sx=cx+p.x, sy=cy-p.y; first ? ctx.moveTo(sx,sy) : ctx.lineTo(sx,sy); first=false; }
      else if (!first) { ctx.stroke(); ctx.beginPath(); first=true; }
    }
    if (!first) ctx.stroke();
  }
  // Data points
  if (mollweideState.showPoints) {
    const proj = globeState.dataPoints.map(pt => {
      const p = projectGlobe(pt.lon, pt.lat, vLon, vLat, R);
      return { x: p.x, y: p.y, z: p.z, rgb: pt.rgb };
    }).sort((a,b) => a.z - b.z);
    const nPts = proj.length;
    const gR = nPts > 500 ? W/125 : nPts > 200 ? W/83 : W/62;
    const gBackR = nPts > 500 ? W/166 : W/100;
    for (const pt of proj) {
      const sx = cx+pt.x, sy = cy-pt.y;
      if (pt.z > 0) {
        ctx.beginPath(); ctx.arc(sx, sy, gR, 0, 2*Math.PI);
        ctx.fillStyle = `rgb(${pt.rgb[0]},${pt.rgb[1]},${pt.rgb[2]})`;
        ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,0.25)';
        ctx.lineWidth = W/250;
        ctx.stroke();
      } else {
        ctx.beginPath(); ctx.arc(sx, sy, gBackR, 0, 2*Math.PI);
        const d = pt.rgb.map(c => Math.floor(c*0.25));
        ctx.fillStyle = `rgb(${d[0]},${d[1]},${d[2]})`;
        ctx.fill();
      }
    }
  }
  // Outline
  ctx.strokeStyle = '#7982a9';
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.arc(cx, cy, R, 0, 2*Math.PI); ctx.stroke();
  // Quantity & part label
  const qty = mollweideState.quantity;
  const qLbl = qty==='peak_stress'?'Von Mises (MPa)':qty==='peak_strain'?'Eff. Plastic Strain':qty==='peak_g'?'Peak G (MG)':qty==='peak_disp'?'Disp (mm)':qty==='peak_vel'?'Vel (mm/s)':'Safety Factor';
  const pName = DATA.parts[String(mollweideState.partId)]?.name || '';
  ctx.fillStyle = '#c0caf5'; ctx.font = `${W/25}px sans-serif`; ctx.textAlign = 'center';
  ctx.fillText(pName + ' - ' + qLbl, cx, W - W/30);
}

function recordGlobe() {
  const btn = document.getElementById('btn-rec-globe');
  if (!btn) return;
  if (globeState.recording) {
    globeState.recording = false;
    btn.textContent = 'Rec';
    btn.style.background = '#24283b';
    btn.style.color = '#565f89';
    return;
  }
  const W = 600;
  const offCanvas = document.createElement('canvas');
  offCanvas.width = W; offCanvas.height = W;
  const ctx = offCanvas.getContext('2d');
  const stream = offCanvas.captureStream(30);
  const chunks = [];
  // Prefer MP4 (H.264) for PPT compatibility, fallback to WebM
  let mimeType = 'video/webm';
  let fileExt = 'webm';
  const mp4Types = ['video/mp4;codecs=avc1', 'video/mp4;codecs=h264', 'video/mp4'];
  for (const mt of mp4Types) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(mt)) {
      mimeType = mt; fileExt = 'mp4'; break;
    }
  }
  if (fileExt === 'webm') {
    if (MediaRecorder.isTypeSupported('video/webm;codecs=vp9')) mimeType = 'video/webm;codecs=vp9';
  }
  const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 5000000 });
  recorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
  recorder.onstop = () => {
    const blob = new Blob(chunks, { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (DATA.project_name || 'globe') + '_globe_360.' + fileExt;
    a.click();
    URL.revokeObjectURL(url);
    btn.textContent = 'Rec';
    btn.style.background = '#24283b';
    btn.style.color = '#565f89';
    if (fileExt === 'webm') {
      alert('WebM format saved.\\nPPT uses MP4 — convert with:\\nffmpeg -i input.webm -c:v libx264 -pix_fmt yuv420p output.mp4');
    }
  };

  btn.textContent = 'Stop';
  btn.style.background = '#7f1d1d';
  btn.style.color = '#fca5a5';
  globeState.recording = true;
  recorder.start();

  const startLon = globeState.viewLon;
  const fixedLat = globeState.viewLat;
  const totalFrames = 360;  // 360 frames = 12s at 30fps
  let frame = 0;

  function tick() {
    if (!globeState.recording || frame >= totalFrames) {
      globeState.recording = false;
      recorder.stop();
      return;
    }
    const lon = startLon + (frame / totalFrames) * 360;
    renderGlobeHR(ctx, W, lon, fixedLat);
    // Also update the small globe preview
    globeState.viewLon = lon;
    renderGlobe();
    frame++;
    requestAnimationFrame(tick);
  }
  tick();
}

function renderMollweide() {
  const container = document.getElementById('mollweide-content');
  if (!container) return;

  const parts = getAllPartIds();
  if (mollweideState.partId === 0 && parts.length > 0) mollweideState.partId = parts[0];

  let controlsHtml = `<div class="controls">
    <label>Quantity:</label>
    <select id="moll-qty" onchange="mollweideState.quantity=this.value;drawMollweideAll()">
      <option value="peak_stress"${mollweideState.quantity==='peak_stress'?' selected':''}>Von Mises Stress (MPa)</option>
      <option value="peak_strain"${mollweideState.quantity==='peak_strain'?' selected':''}>Eff. Plastic Strain</option>
      <option value="peak_g"${mollweideState.quantity==='peak_g'?' selected':''}>Peak G-Force (MG)</option>
      <option value="peak_disp"${mollweideState.quantity==='peak_disp'?' selected':''}>Max Displacement (mm)</option>
      <option value="peak_vel"${mollweideState.quantity==='peak_vel'?' selected':''}>Peak Velocity (mm/s)</option>
      <option value="safety_factor"${mollweideState.quantity==='safety_factor'?' selected':''}>Safety Factor</option>
    </select>
    <label>Part:</label>
    <select id="moll-part" onchange="mollweideState.partId=parseInt(this.value);drawMollweideAll()">`;
  for (const pid of parts) {
    const p = DATA.parts[String(pid)];
    controlsHtml += `<option value="${pid}"${pid===mollweideState.partId?' selected':''}>${p.name} (ID:${pid})</option>`;
  }
  controlsHtml += `</select>
    <div class="view-toggle">
      <button id="btn-contour" class="${mollweideState.viewMode==='contour'?'active':''}" onclick="mollweideState.viewMode='contour';drawMollweideAll()">Contour</button>
      <button id="btn-points" class="${mollweideState.viewMode==='points'?'active':''}" onclick="mollweideState.viewMode='points';drawMollweideAll()">Data Points</button>
    </div>
    <label style="margin-left:12px;display:inline-flex;align-items:center;gap:4px;cursor:pointer;">
      <input type="checkbox" id="moll-show-pts" ${mollweideState.showPoints?'checked':''} onchange="mollweideState.showPoints=this.checked;drawMollweideAll()"> Markers
    </label>
    <span style="margin-left:16px;border-left:1px solid #3b3d57;padding-left:12px;display:inline-flex;align-items:center;gap:6px;">
      <label style="display:inline-flex;align-items:center;gap:4px;cursor:pointer;">
        <input type="checkbox" id="moll-manual-scale" ${mollweideState.manualScale?'checked':''} onchange="mollweideState.manualScale=this.checked;if(!this.checked){drawMollweideAll();}"> Scale:
      </label>
      <input type="number" id="moll-scale-min" style="width:72px;background:#1a1b26;color:#c0caf5;border:1px solid #3b3d57;border-radius:3px;padding:2px 4px;font-size:11px;" placeholder="Min" step="any" onchange="mollweideState.scaleMin=parseFloat(this.value)||0">
      <span style="color:#565f89">~</span>
      <input type="number" id="moll-scale-max" style="width:72px;background:#1a1b26;color:#c0caf5;border:1px solid #3b3d57;border-radius:3px;padding:2px 4px;font-size:11px;" placeholder="Max" step="any" onchange="mollweideState.scaleMax=parseFloat(this.value)||0">
      <button style="padding:2px 8px;font-size:11px;background:#24283b;color:#7aa2f7;border:1px solid #3b3d57;border-radius:3px;cursor:pointer;" onclick="mollweideState.manualScale=true;document.getElementById('moll-manual-scale').checked=true;mollweideState.scaleMin=parseFloat(document.getElementById('moll-scale-min').value)||0;mollweideState.scaleMax=parseFloat(document.getElementById('moll-scale-max').value)||0;drawMollweideAll()">Apply</button>
    </span>
    <button id="btn-swap-rp" style="margin-left:12px;padding:2px 8px;font-size:11px;background:${mollweideState.swapRP?'#364a82':'#24283b'};color:${mollweideState.swapRP?'#7dcfff':'#565f89'};border:1px solid #3b3d57;border-radius:3px;cursor:pointer;" onclick="mollweideState.swapRP=!mollweideState.swapRP;drawMollweideAll();renderMollweide();" title="Swap Roll and Pitch axes (use when DOE generator uses opposite convention)">Swap R/P</button>
  </div>`;

  container.innerHTML = controlsHtml +
    `<div id="moll-map-wrap" style="margin-right:280px;"></div>
    <div class="panel" style="margin-top:16px;margin-right:280px;">
      <h2>Risk Ranking</h2>
      <div id="moll-risk-table" style="max-height:500px;overflow-y:auto;"></div>
    </div>
    <div id="moll-sidebar" style="position:fixed;right:max(24px, calc((100vw - 1600px)/2 + 24px));top:120px;width:260px;z-index:10;">
      <div class="globe-container" style="position:relative;">
        <canvas id="globe-canvas" class="globe-canvas" width="250" height="250"></canvas>
        <button id="btn-rec-globe" onclick="recordGlobe()" style="position:absolute;top:4px;right:4px;padding:2px 8px;font-size:10px;background:#24283b;color:#565f89;border:1px solid #3b3d57;border-radius:3px;cursor:pointer;" title="Record 360° rotation (WebM)">Rec</button>
      </div>
      <div id="moll-3d" class="device-3d"></div>
      <div id="moll-info" class="panel" style="width:240px;font-size:12px;margin-top:8px;"></div>
    </div>`;

  init3DDevice();
  initGlobe();
  drawMollweideAll();
}

function drawMollweideAll() {
  // Update toggle button states
  document.querySelectorAll('.view-toggle button').forEach(b => b.classList.remove('active'));
  const activeBtn = document.getElementById(mollweideState.viewMode === 'contour' ? 'btn-contour' : 'btn-points');
  if (activeBtn) activeBtn.classList.add('active');

  if (mollweideState.viewMode === 'contour') {
    drawMollweideContour();
  } else {
    drawMollweidePoints();
  }
  drawRiskTable();
  updateGlobeData();
  renderGlobe();
  updateMollInfo(null);
}

// Shared contour data for mouse interaction
let _contourDataPoints = [];

// Spherical (great-circle) distance in radians between two (lon,lat) points in degrees
function sphericalDist(lon1d, lat1d, lon2d, lat2d) {
  const toR = Math.PI / 180;
  const lat1 = lat1d * toR, lat2 = lat2d * toR;
  const dlon = (lon2d - lon1d) * toR;
  const dlat = lat2 - lat1;
  const a = Math.sin(dlat/2)**2 + Math.cos(lat1)*Math.cos(lat2)*Math.sin(dlon/2)**2;
  return 2 * Math.asin(Math.sqrt(Math.min(1, a)));
}

// Measure available width for the Mollweide map
function getMollweideSize() {
  const wrap = document.getElementById('moll-map-wrap');
  if (!wrap || wrap.clientWidth < 100) return { W: 800, H: 420, scale: 130 };
  const cbW = 90;  // colorbar width
  const axisMargin = 60;  // axis labels
  const mapAvail = wrap.clientWidth - cbW - axisMargin;
  // Map width = 2 * rx = 2 * 2*sqrt(2)*scale = 4*sqrt(2)*scale
  const scale = Math.max(80, Math.floor(mapAvail / (4 * Math.SQRT2)));
  const rx = 2 * Math.SQRT2 * scale, ry = Math.SQRT2 * scale;
  const W = Math.ceil(rx * 2 + axisMargin);
  const H = Math.ceil(ry * 2 + 50);
  return { W, H, scale, cx: W / 2, cy: H / 2, rx, ry };
}

// Build colorbar HTML (shared between contour and points views)
function buildColorBar(vmin, vmax, vrange, qty, mapH) {
  const cbW = 90, bx = 20, barW = 16, by = 10, bh = Math.max(100, mapH - 40);
  let svg = `<svg width="${cbW}" height="${mapH}" viewBox="0 0 ${cbW} ${mapH}">`;
  for (let i = 0; i < bh; i++) {
    const norm = 1 - i / bh;
    svg += `<rect x="${bx}" y="${by+i}" width="${barW}" height="1.5" fill="${valueToColor(norm)}"/>`;
  }
  const labels = [{n:1,y:by+4},{n:.75,y:by+bh*.25+4},{n:.5,y:by+bh*.5+4},{n:.25,y:by+bh*.75+4},{n:0,y:by+bh+4}];
  labels.forEach(lb => {
    svg += `<text x="${bx+barW+6}" y="${lb.y}" fill="#c0caf5" font-size="10" dominant-baseline="middle">${formatValue(vmin+lb.n*vrange, qty)}</text>`;
  });
  svg += '</svg>';
  return svg;
}

// IDW interpolation for contour view using spherical distance
function drawMollweideContour() {
  const wrap = document.getElementById('moll-map-wrap');
  if (!wrap) return;

  const { W, H, scale, cx, cy, rx, ry } = getMollweideSize();
  const qty = mollweideState.quantity;
  const pid = String(mollweideState.partId);

  // Collect data points with both Mollweide coords and spherical (lon,lat)
  const dataPoints = [];
  let vmin = Infinity, vmax = -Infinity;
  for (let ri = 0; ri < DATA.results.length; ri++) {
    const r = DATA.results[ri];
    const pd = r.parts[pid];
    const v = getQtyValue(pd, qty);
    vmin = Math.min(vmin, v);
    vmax = Math.max(vmax, v);
    const [lon, lat] = eulerToLonLat(r.angle.roll, r.angle.pitch, r.angle.yaw, r.angle.name, r.angle.swap);
    const [mx, my] = mollweideProject(lon, lat);
    dataPoints.push({ mx, my, lon, lat, v, ri });
  }
  // Apply manual scale if enabled
  if (mollweideState.manualScale && mollweideState.scaleMax > mollweideState.scaleMin) {
    vmin = mollweideState.scaleMin;
    vmax = mollweideState.scaleMax;
  }
  const vrange = vmax - vmin || 1;
  const invertContour = qty === 'safety_factor';
  _contourDataPoints = dataPoints;

  // Step 1: Compute IDW on coarse grid using spherical distance
  const gridStep = 3;
  const gW = Math.ceil(W / gridStep) + 1, gH = Math.ceil(H / gridStep) + 1;
  const gridVals = new Float32Array(gW * gH);
  const pw = 3.5;  // higher power = sharper peaks, max stays at data points

  for (let gy = 0; gy < gH; gy++) {
    for (let gx = 0; gx < gW; gx++) {
      const ppx = gx * gridStep, ppy = gy * gridStep;
      const qx = (ppx - cx) / scale;
      const qy = (cy - ppy) / scale;
      const ll = mollweideInverse(qx, qy);
      if (!ll) { gridVals[gy * gW + gx] = 0; continue; }
      const [plon, plat] = ll;
      let wsum = 0, vsum = 0;
      for (const dp of dataPoints) {
        const dist = sphericalDist(plon, plat, dp.lon, dp.lat);
        if (dist < 0.02) { vsum = dp.v; wsum = 1; break; }  // ~1.1° snap radius
        const w = 1 / Math.pow(dist, pw);
        wsum += w;
        vsum += w * dp.v;
      }
      gridVals[gy * gW + gx] = wsum > 0 ? Math.max(0, Math.min(1, (vsum / wsum - vmin) / vrange)) : 0;
    }
  }

  // Step 2: Render to offscreen canvas
  const offCanvas = document.createElement('canvas');
  offCanvas.width = W; offCanvas.height = H;
  const ctx = offCanvas.getContext('2d');
  const imgData = ctx.createImageData(W, H);
  const bgR = 15, bgG = 17, bgB = 23;

  for (let py = 0; py < H; py++) {
    for (let px = 0; px < W; px++) {
      const idx = (py * W + px) * 4;
      if (!isInsideMollweide(px, py, cx, cy, scale)) {
        imgData.data[idx] = bgR; imgData.data[idx+1] = bgG;
        imgData.data[idx+2] = bgB; imgData.data[idx+3] = 255;
        continue;
      }
      const gxf = px / gridStep, gyf = py / gridStep;
      const gx0 = Math.min(Math.floor(gxf), gW-1), gy0 = Math.min(Math.floor(gyf), gH-1);
      const gx1 = Math.min(gx0+1, gW-1), gy1 = Math.min(gy0+1, gH-1);
      const fx = gxf - gx0, fy = gyf - gy0;
      const norm = gridVals[gy0*gW+gx0]*(1-fx)*(1-fy) + gridVals[gy0*gW+gx1]*fx*(1-fy) +
                   gridVals[gy1*gW+gx0]*(1-fx)*fy + gridVals[gy1*gW+gx1]*fx*fy;
      const finalNorm = invertContour ? 1 - Math.max(0, Math.min(1, norm)) : Math.max(0, Math.min(1, norm));
      const c = valueToColorRGB(finalNorm);
      imgData.data[idx] = c[0]; imgData.data[idx+1] = c[1];
      imgData.data[idx+2] = c[2]; imgData.data[idx+3] = 255;
    }
  }
  ctx.putImageData(imgData, 0, 0);

  // Grid lines
  ctx.strokeStyle = 'rgba(255,255,255,0.12)';
  ctx.lineWidth = 0.7;
  for (let lat = -60; lat <= 60; lat += 30) {
    ctx.beginPath();
    for (let lon = -180; lon <= 180; lon += 3) {
      const [x, y] = mollweideProject(lon, lat);
      const sx = cx + x*scale, sy = cy - y*scale;
      lon === -180 ? ctx.moveTo(sx, sy) : ctx.lineTo(sx, sy);
    }
    ctx.stroke();
  }
  for (let lon = -150; lon <= 150; lon += 30) {
    ctx.beginPath();
    for (let lat = -90; lat <= 90; lat += 2) {
      const [x, y] = mollweideProject(lon, lat);
      const sx = cx + x*scale, sy = cy - y*scale;
      lat === -90 ? ctx.moveTo(sx, sy) : ctx.lineTo(sx, sy);
    }
    ctx.stroke();
  }

  // Outline
  ctx.strokeStyle = '#a9b1d6'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, 0, 2*Math.PI); ctx.stroke();

  // Data point markers (clipped to ellipse) - togglable
  if (mollweideState.showPoints) {
    ctx.save();
    ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, 0, 2*Math.PI); ctx.clip();
    const n = dataPoints.length;
    const mrkR = n > 500 ? 2 : n > 200 ? 3 : 5;
    const dotR = n > 500 ? 1 : n > 200 ? 1.5 : 2;
    for (const dp of dataPoints) {
      const sx = cx + dp.mx*scale, sy = cy - dp.my*scale;
      ctx.beginPath(); ctx.arc(sx, sy, mrkR, 0, 2*Math.PI);
      ctx.strokeStyle = '#ffffff'; ctx.lineWidth = n > 500 ? 0.8 : 1.5; ctx.stroke();
      ctx.beginPath(); ctx.arc(sx, sy, dotR, 0, 2*Math.PI);
      ctx.fillStyle = '#ffffff'; ctx.fill();
    }
    ctx.restore();
  }

  const dataUrl = offCanvas.toDataURL();

  // Build SVG overlay for labels and hover zones
  let svg = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" id="contour-svg">`;
  svg += `<image href="${dataUrl}" x="0" y="0" width="${W}" height="${H}"/>`;

  // Axis labels
  svg += `<text x="${cx}" y="${H-2}" text-anchor="middle" fill="#a9b1d6" font-size="10">Longitude (deg)</text>`;
  svg += `<text x="10" y="${cy}" fill="#a9b1d6" font-size="10" transform="rotate(-90,10,${cy})">Latitude (deg)</text>`;
  for (let lon = -180; lon <= 180; lon += 90) {
    const [x] = mollweideProject(lon, 0);
    svg += `<text x="${(cx+x*scale).toFixed(0)}" y="${cy+ry+14}" text-anchor="middle" fill="#a9b1d6" font-size="9">${lon}</text>`;
  }
  for (let lat = -90; lat <= 90; lat += 45) {
    if (lat === 0) continue;
    const [,y] = mollweideProject(0, lat);
    svg += `<text x="${cx-rx-4}" y="${(cy-y*scale+3).toFixed(0)}" text-anchor="end" fill="#a9b1d6" font-size="9">${lat}</text>`;
  }

  // Invisible hover zones
  for (const dp of dataPoints) {
    const sx = cx + dp.mx*scale, sy = cy - dp.my*scale;
    svg += `<circle cx="${sx.toFixed(1)}" cy="${sy.toFixed(1)}" r="18" fill="transparent" style="cursor:pointer" onmouseenter="onMollHover(${dp.ri})" onmouseleave="onMollLeave()"/>`;
  }
  svg += '</svg>';

  const cbSvg = buildColorBar(vmin, vmax, vrange, qty, H);
  wrap.innerHTML = `<div style="display:flex;align-items:flex-start;gap:0;">${svg}${cbSvg}</div>`;

  // Mousemove for smooth hover
  const svgEl = document.getElementById('contour-svg');
  if (svgEl) {
    svgEl.addEventListener('mousemove', function(e) {
      const rect = svgEl.getBoundingClientRect();
      const sx = (e.clientX - rect.left) / rect.width * W;
      const sy = (e.clientY - rect.top) / rect.height * H;
      if (!isInsideMollweide(sx, sy, cx, cy, scale)) return;
      const qx = (sx - cx)/scale, qy = (cy - sy)/scale;
      let minD = Infinity, best = -1;
      for (const dp of _contourDataPoints) {
        const d = (qx-dp.mx)**2 + (qy-dp.my)**2;
        if (d < minD) { minD = d; best = dp.ri; }
      }
      if (best >= 0) onMollHover(best);
    });
  }
}

// Original data-point view
function drawMollweidePoints() {
  const wrap = document.getElementById('moll-map-wrap');
  if (!wrap) return;

  const { W, H, scale, cx, cy, rx, ry } = getMollweideSize();
  const qty = mollweideState.quantity;
  const pid = String(mollweideState.partId);

  const vals = [];
  for (const r of DATA.results) {
    const pd = r.parts[pid];
    if (pd) vals.push(getQtyValue(pd, qty));
  }
  let vmin = Math.min(...vals);
  let vmax = Math.max(...vals);
  if (mollweideState.manualScale && mollweideState.scaleMax > mollweideState.scaleMin) {
    vmin = mollweideState.scaleMin;
    vmax = mollweideState.scaleMax;
  }
  const vrange = vmax - vmin || 1;

  let svg = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`;
  svg += `<defs><clipPath id="moll-clip"><ellipse cx="${cx}" cy="${cy}" rx="${rx+16}" ry="${ry+16}"/></clipPath></defs>`;
  svg += `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="none" stroke="#7982a9" stroke-width="1"/>`;

  // Grid lines
  for (let lat = -60; lat <= 60; lat += 30) {
    let path = '';
    for (let lon = -180; lon <= 180; lon += 5) {
      const [x, y] = mollweideProject(lon, lat);
      const sx = cx + x*scale, sy = cy - y*scale;
      path += (lon === -180 ? 'M' : 'L') + `${sx.toFixed(1)},${sy.toFixed(1)}`;
    }
    svg += `<path d="${path}" fill="none" stroke="#24283b" stroke-width="0.5"/>`;
  }
  for (let lon = -150; lon <= 150; lon += 30) {
    let path = '';
    for (let lat = -90; lat <= 90; lat += 2) {
      const [x, y] = mollweideProject(lon, lat);
      const sx = cx + x*scale, sy = cy - y*scale;
      path += (lat === -90 ? 'M' : 'L') + `${sx.toFixed(1)},${sy.toFixed(1)}`;
    }
    svg += `<path d="${path}" fill="none" stroke="#24283b" stroke-width="0.5"/>`;
  }

  // Data points with size and color (clipped to ellipse)
  svg += `<g clip-path="url(#moll-clip)">`;
  for (let ri = 0; ri < DATA.results.length; ri++) {
    const r = DATA.results[ri];
    const pd = r.parts[pid];
    const v = getQtyValue(pd, qty);
    const norm = Math.max(0, Math.min(1, (v - vmin) / vrange));
    const color = valueToColor(norm);
    const [lon, lat] = eulerToLonLat(r.angle.roll, r.angle.pitch, r.angle.yaw, r.angle.name, r.angle.swap);
    const [x, y] = mollweideProject(lon, lat);
    const sx = cx + x*scale, sy = cy - y*scale;
    const n = DATA.results.length;
    const baseR = n > 500 ? 2 : n > 200 ? 4 : n > 50 ? 6 : 8;
    const radius = baseR + norm * baseR;
    svg += `<circle class="heatmap-cell" cx="${sx.toFixed(1)}" cy="${sy.toFixed(1)}" r="${radius.toFixed(1)}" fill="${color}" data-ri="${ri}"
      onmouseenter="onMollHover(${ri})" onmouseleave="onMollLeave()"/>`;
  }
  svg += `</g>`;

  // Labels
  svg += `<text x="${cx}" y="${H-2}" text-anchor="middle" fill="#a9b1d6" font-size="10">Longitude (deg)</text>`;
  svg += `<text x="10" y="${cy}" fill="#a9b1d6" font-size="10" transform="rotate(-90,10,${cy})">Latitude (deg)</text>`;
  for (let lon = -180; lon <= 180; lon += 90) {
    const [x,] = mollweideProject(lon, 0);
    svg += `<text x="${(cx+x*scale).toFixed(0)}" y="${cy+ry+14}" text-anchor="middle" fill="#a9b1d6" font-size="9">${lon}</text>`;
  }
  for (let lat = -90; lat <= 90; lat += 45) {
    if (lat === 0) continue;
    const [, y] = mollweideProject(0, lat);
    svg += `<text x="${cx-rx-4}" y="${(cy-y*scale+3).toFixed(0)}" text-anchor="end" fill="#a9b1d6" font-size="9">${lat}</text>`;
  }
  svg += '</svg>';

  const cbSvg = buildColorBar(vmin, vmax, vrange, qty, H);
  wrap.innerHTML = `<div style="display:flex;align-items:flex-start;gap:0;">${svg}${cbSvg}</div>`;
}

// Risk-sorted table below the map
function drawRiskTable() {
  const tableEl = document.getElementById('moll-risk-table');
  if (!tableEl) return;

  const qty = mollweideState.quantity;
  const pid = String(mollweideState.partId);
  const qtyLabel = qty === 'peak_stress' ? 'Stress (MPa)' : qty === 'peak_strain' ? 'Strain' : qty === 'peak_g' ? 'G-Force (MG)' : qty === 'peak_vel' ? 'Velocity (mm/s)' : qty === 'safety_factor' ? 'Safety Factor' : 'Disp (mm)';

  // Build sorted list
  const rows = [];
  for (let ri = 0; ri < DATA.results.length; ri++) {
    const r = DATA.results[ri];
    const pd = r.parts[pid];
    const v = getQtyValue(pd, qty);
    rows.push({ ri, name: r.angle.name, roll: r.angle.roll, pitch: r.angle.pitch, yaw: r.angle.yaw, category: r.angle.category, value: v });
  }
  rows.sort((a, b) => b.value - a.value);

  let html = `<table><tr><th>#</th><th>Direction</th><th>Category</th><th>${qtyLabel}</th><th>Roll</th><th>Pitch</th><th>Yaw</th></tr>`;
  rows.forEach((row, i) => {
    html += `<tr class="risk-table-row" data-ri="${row.ri}"
      onmouseenter="onRiskRowHover(this, ${row.ri})" onmouseleave="onRiskRowLeave(this)">
      <td>${i+1}</td>
      <td style="color:var(--cyan)">${row.name}</td>
      <td>${row.category}</td>
      <td style="text-align:right;font-weight:bold">${formatValue(row.value, qty)}</td>
      <td style="text-align:right">${row.roll.toFixed(1)}</td>
      <td style="text-align:right">${row.pitch.toFixed(1)}</td>
      <td style="text-align:right">${row.yaw.toFixed(1)}</td>
    </tr>`;
  });
  html += '</table>';
  tableEl.innerHTML = html;
}

function onRiskRowHover(el, ri) {
  el.classList.add('highlighted');
  onMollHover(ri);
}
function onRiskRowLeave(el) {
  el.classList.remove('highlighted');
  onMollLeave();
}

function valueToColor(norm) {
  norm = Math.max(0, Math.min(1, norm));
  const [cr, cg, cb] = valueToColorRGB(norm);
  return `rgb(${cr},${cg},${cb})`;
}

function valueToColorRGB(norm) {
  // Jet colormap: blue(low) -> cyan -> green -> yellow -> red(high)
  norm = Math.max(0, Math.min(1, norm));
  let cr, cg, cb;
  if (norm < 0.25) {
    const t = norm / 0.25;
    cr = 0; cg = lerp(0, 255, t); cb = 255;
  } else if (norm < 0.5) {
    const t = (norm - 0.25) / 0.25;
    cr = 0; cg = 255; cb = lerp(255, 0, t);
  } else if (norm < 0.75) {
    const t = (norm - 0.5) / 0.25;
    cr = lerp(0, 255, t); cg = 255; cb = 0;
  } else {
    const t = (norm - 0.75) / 0.25;
    cr = 255; cg = lerp(255, 0, t); cb = 0;
  }
  return [Math.round(cr), Math.round(cg), Math.round(cb)];
}

function lerp(a, b, t) { return a + (b - a) * t; }

function getQtyValue(pd, qty) {
  if (!pd) return 0;
  if (qty === 'safety_factor') {
    const ys = DATA.yield_stress || 0;
    return (ys > 0 && pd.peak_stress > 0) ? ys / pd.peak_stress : 0;
  }
  return pd[qty] || 0;
}

function formatValue(v, qty) {
  if (qty === 'peak_stress') return v.toFixed(1) + ' MPa';
  if (qty === 'peak_strain') return v.toFixed(4);
  if (qty === 'peak_g') return (v/1e6).toFixed(2) + ' MG';
  if (qty === 'peak_disp') return v.toFixed(2) + ' mm';
  if (qty === 'peak_vel') return v.toFixed(1) + ' mm/s';
  if (qty === 'safety_factor') return v > 0 ? v.toFixed(2) : 'N/A';
  return v.toFixed(2);
}

function onMollHover(ri) {
  mollweideState.hoveredAngle = ri;
  const r = DATA.results[ri];
  update3DDevice(r.angle.roll, r.angle.pitch, r.angle.yaw, r.angle.name);
  const [lon, lat] = eulerToLonLat(r.angle.roll, r.angle.pitch, r.angle.yaw, r.angle.name, r.angle.swap);
  globeState.hoveredRi = ri;
  rotateGlobeTo(lon, lat);
  updateMollInfo(ri);
}
function onMollLeave() {
  mollweideState.hoveredAngle = null;
  globeState.hoveredRi = -1;
  renderGlobe();
  updateMollInfo(null);
}

function updateMollInfo(ri) {
  const el = document.getElementById('moll-info');
  if (!el) return;
  if (ri === null) { el.innerHTML = '<div style="color:var(--dim)">Hover over a point or table row</div>'; return; }
  const r = DATA.results[ri];
  const pid = String(mollweideState.partId);
  const pd = r.parts[pid] || {};
  el.innerHTML = `
    <div style="color:var(--cyan);font-weight:bold;word-break:break-word;">${r.angle.name}</div>
    <div style="margin-top:4px">Roll: ${r.angle.roll.toFixed(1)} | Pitch: ${r.angle.pitch.toFixed(1)}</div>
    <div style="margin-top:6px;color:var(--fg2)">
      Stress: <b>${(pd.peak_stress||0).toFixed(1)} MPa</b><br>
      Strain: <b>${(pd.peak_strain||0).toFixed(4)}</b><br>
      G-Force: <b>${((pd.peak_g||0)/1e6).toFixed(2)} MG</b><br>
      Disp: <b>${(pd.peak_disp||0).toFixed(2)} mm</b><br>
      Vel: <b>${(pd.peak_vel||0).toFixed(1)} mm/s</b>
    </div>`;
}

// 3D Device - color-coded faces with legend
// Display=red, Back=gray, Right=orange, Left=purple, Top=blue, Bottom=green
const FACE_COLORS = {
  display: {bg:'rgba(247,118,142,0.45)', border:'#f7768e'},
  back:    {bg:'rgba(86,95,137,0.35)',   border:'#7982a9'},
  right:   {bg:'rgba(255,158,100,0.4)',  border:'#ff9e64'},
  left:    {bg:'rgba(187,154,247,0.4)',  border:'#bb9af7'},
  top:     {bg:'rgba(122,162,247,0.45)', border:'#7aa2f7'},
  bottom:  {bg:'rgba(158,206,106,0.4)', border:'#9ece6a'},
};

function init3DDevice() {
  const el = document.getElementById('moll-3d');
  if (!el) return;
  // Galaxy S25 ratio: 70.5 x 146.9 x 7.2 mm -> scaled
  const w=48, h=100, d=8;
  const hw=w/2, hh=h/2, hd=d/2;
  const fc = FACE_COLORS;
  // CSS 3D cuboid: each face centered at container origin via left/top,
  // then rotated and pushed out by half the dimension along that axis.
  const gw = 100; // ground plate width
  // Side faces center: left=(w-d)/2, top=0 (same height as container)
  // Top/Bottom faces center: left=0, top=(h-d)/2
  const sl = (w-d)/2, st = (h-d)/2;
  el.innerHTML = `
    <div style="width:${gw}px;height:200px;margin:0 auto;perspective:400px;position:relative;">
      <div class="device-inner" id="device-inner"
           style="width:${w}px;height:${h}px;position:absolute;left:${(gw-w)/2}px;top:${(160-h)/2}px;">
        <div class="device-face" style="width:${w}px;height:${h}px;background:${fc.display.bg};border-color:${fc.display.border};
          transform:translateZ(${hd}px);"></div>
        <div class="device-face" style="width:${w}px;height:${h}px;background:${fc.back.bg};border-color:${fc.back.border};
          transform:rotateY(180deg) translateZ(${hd}px);"></div>
        <div class="device-face" style="width:${d}px;height:${h}px;left:${sl}px;background:${fc.right.bg};border-color:${fc.right.border};
          transform:rotateY(90deg) translateZ(${hw}px);"></div>
        <div class="device-face" style="width:${d}px;height:${h}px;left:${sl}px;background:${fc.left.bg};border-color:${fc.left.border};
          transform:rotateY(-90deg) translateZ(${hw}px);"></div>
        <div class="device-face" style="width:${w}px;height:${d}px;top:${st}px;background:${fc.top.bg};border-color:${fc.top.border};
          transform:rotateX(90deg) translateZ(${hh}px);"></div>
        <div class="device-face" style="width:${w}px;height:${d}px;top:${st}px;background:${fc.bottom.bg};border-color:${fc.bottom.border};
          transform:rotateX(-90deg) translateZ(${hh}px);"></div>
      </div>
      <div id="device-ground" style="position:absolute;left:0;bottom:0;width:${gw}px;height:18px;
        background:rgba(86,95,137,0.15);border:1px solid var(--dim);border-radius:2px;
        display:flex;align-items:center;justify-content:center;
        font-size:9px;color:var(--dim);letter-spacing:1px;">GROUND</div>
    </div>
    <div id="device-angles" style="text-align:center;color:var(--dim);font-size:10px;margin-top:2px;"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1px 8px;font-size:9px;color:var(--fg2);margin-top:4px;padding:0 10px;">
      <div><span style="display:inline-block;width:8px;height:8px;background:${fc.display.border};border-radius:1px;margin-right:3px;vertical-align:middle;"></span>Display</div>
      <div><span style="display:inline-block;width:8px;height:8px;background:${fc.back.border};border-radius:1px;margin-right:3px;vertical-align:middle;"></span>Back</div>
      <div><span style="display:inline-block;width:8px;height:8px;background:${fc.right.border};border-radius:1px;margin-right:3px;vertical-align:middle;"></span>Right</div>
      <div><span style="display:inline-block;width:8px;height:8px;background:${fc.left.border};border-radius:1px;margin-right:3px;vertical-align:middle;"></span>Left</div>
      <div><span style="display:inline-block;width:8px;height:8px;background:${fc.top.border};border-radius:1px;margin-right:3px;vertical-align:middle;"></span>Top</div>
      <div><span style="display:inline-block;width:8px;height:8px;background:${fc.bottom.border};border-radius:1px;margin-right:3px;vertical-align:middle;"></span>Bottom</div>
    </div>`;
}

function update3DDevice(roll, pitch, yaw, angleName) {
  const inner = document.getElementById('device-inner');
  const anglesEl = document.getElementById('device-angles');
  if (!inner) return;

  // Compute impact direction in device body frame:
  // impact_body = Rx(roll) * Ry(pitch) * Rz(yaw) * [0,0,-1]
  // Device body coords: X=Right, Y=Top(up), Z=Front
  const r = roll * Math.PI / 180;
  const p = pitch * Math.PI / 180;
  const yw = yaw * Math.PI / 180;
  const cr = Math.cos(r), sr = Math.sin(r);
  const cp = Math.cos(p), sp = Math.sin(p);
  // R * [0,0,-1] = -column2 of Rx*Ry*Rz = [-sp, sr*cp, -cr*cp]
  const bx = -sp;         // body X (Right)
  const by = sr * cp;     // body Y (Top/up)
  const bz = -cr * cp;    // body Z (Front)

  // This vector points from device center toward the ground face (in sim body frame).
  // Sim body: Right=+X, Top=+Y, Front=+Z
  // CSS 3D:   Right=+X, Top=-Y(up), Front=+Z, Down=+Y
  // Mapping sim->CSS face normal: (bx, -by, bz)
  // We rotate so this CSS normal points CSS down = (0, +1, 0).
  const nx = bx, ny = -by, nz = bz;
  const mag = Math.sqrt(nx*nx + ny*ny + nz*nz);
  if (mag < 0.001) { inner.style.transform = 'rotateX(10deg)'; return; }
  const ux = nx/mag, uy = ny/mag, uz = nz/mag;

  // Rodrigues: rotate ux,uy,uz -> (0,1,0)
  const dot = uy;
  // cross(u, [0,1,0]) = (uz*1-0, 0-ux*0... wait:
  // cross = (uy*0 - uz*1, uz*0 - ux*0, ux*1 - uy*0) = (-uz, 0, ux)
  const kx = -uz, kz = ux;
  const kmag = Math.sqrt(kx*kx + kz*kz);

  let transform;
  if (kmag < 0.0001) {
    // Impact is parallel to CSS down - face/edge/corner already pointing down
    if (dot > 0) {
      transform = 'none';
    } else {
      // Pointing up - flip 180 around Z
      transform = 'rotateZ(180deg)';
    }
  } else {
    // Rodrigues rotation: impact direction -> CSS down (0,1,0)
    const ax = kx/kmag, az = kz/kmag;
    const angle = Math.acos(Math.max(-1, Math.min(1, dot)));
    const cosA = Math.cos(angle), sinA = Math.sin(angle);
    const t = 1 - cosA;
    // Rodrigues with axis=(ax, 0, az)
    const m00 = t*ax*ax+cosA, m01 = -sinA*az,   m02 = t*ax*az;
    const m10 = sinA*az,      m11 = cosA,        m12 = -sinA*ax;
    const m20 = t*az*ax,      m21 = sinA*ax,     m22 = t*az*az+cosA;

    // Pure orthogonal view - no tilt
    transform = `matrix3d(${m00},${m10},${m20},0, ${m01},${m11},${m21},0, ${m02},${m12},${m22},0, 0,0,0,1)`;
  }

  inner.style.transform = transform;
  if (anglesEl) {
    const label = angleName || `R:${roll.toFixed(0)} P:${pitch.toFixed(0)} Y:${yaw.toFixed(0)}`;
    anglesEl.textContent = label;
  }
}

// ============ Tab 2: Time History ============
let timeHistState = { partId: 0, quantity: 'stress', selectedAngles: [], chartMode: 'lines', component: 'mag' };

function renderTimeHistory() {
  const container = document.getElementById('timehistory-content');
  if (!container) return;

  const parts = getAllPartIds();
  if (timeHistState.partId === 0 && parts.length > 0) timeHistState.partId = parts[0];

  let html = `<div class="controls">
    <label>Part:</label>
    <select id="th-part" onchange="timeHistState.partId=parseInt(this.value);drawTimeHistory()">`;
  for (const pid of parts) {
    const p = DATA.parts[String(pid)];
    html += `<option value="${pid}"${pid===timeHistState.partId?' selected':''}>${p.name} (ID:${pid})</option>`;
  }
  html += `</select>
    <label>Quantity:</label>
    <select id="th-qty" onchange="timeHistState.quantity=this.value;timeHistState.component='mag';renderTimeHistory()">
      <option value="stress"${timeHistState.quantity==='stress'?' selected':''}>Von Mises Stress</option>
      <option value="strain"${timeHistState.quantity==='strain'?' selected':''}>Eff. Plastic Strain</option>
      <option value="g"${timeHistState.quantity==='g'?' selected':''}>G-Force (MG)</option>
      <option value="disp"${timeHistState.quantity==='disp'?' selected':''}>Displacement</option>
    </select>`;
  // Component selector for G-Force and Displacement
  if (timeHistState.quantity === 'g' || timeHistState.quantity === 'disp') {
    html += `<label>Axis:</label>
      <select id="th-comp" onchange="timeHistState.component=this.value;drawTimeHistory()">
        <option value="mag"${timeHistState.component==='mag'?' selected':''}>Magnitude</option>
        <option value="x"${timeHistState.component==='x'?' selected':''}>X</option>
        <option value="y"${timeHistState.component==='y'?' selected':''}>Y</option>
        <option value="z"${timeHistState.component==='z'?' selected':''}>Z</option>
      </select>`;
  }
  // Envelope mode for stress
  if (timeHistState.quantity === 'stress') {
    html += `<div class="chart-mode-toggle">
      <button class="${timeHistState.chartMode==='lines'?'active':''}" onclick="timeHistState.chartMode='lines';drawTimeHistory()">Lines</button>
      <button class="${timeHistState.chartMode==='envelope'?'active':''}" onclick="timeHistState.chartMode='envelope';drawTimeHistory()">Envelope</button>
    </div>`;
  }
  html += `
    <button onclick="timeHistState.selectedAngles=DATA.results.map((_,i)=>i).slice(0,8);renderTimeHistory()"
      style="background:var(--bg3);color:var(--cyan);border:1px solid var(--dim);border-radius:3px;padding:2px 10px;font-size:11px;cursor:pointer;margin-left:8px">Select 8</button>
    <button onclick="timeHistState.selectedAngles=[];renderTimeHistory()"
      style="background:var(--bg3);color:var(--dim);border:1px solid var(--dim);border-radius:3px;padding:2px 10px;font-size:11px;cursor:pointer">Clear</button>
  </div>
  <div id="th-mollweide-map" style="margin-bottom:12px"></div>
  <div id="th-selected-tags" style="margin-bottom:8px;display:flex;flex-wrap:wrap;gap:4px;align-items:center"></div>
  <div id="th-chart" style="overflow-x:auto"></div>`;

  container.innerHTML = html;

  const thColors = ['#f7768e','#e0af68','#7aa2f7','#9ece6a','#bb9af7','#7dcfff','#ff9e64','#2ac3de'];
  if (timeHistState.selectedAngles.length === 0 && DATA.results.length > 0) {
    timeHistState.selectedAngles = [0];
  }

  // Selected angle tags (removable chips)
  const tagEl = document.getElementById('th-selected-tags');
  if (tagEl) {
    timeHistState.selectedAngles.forEach((ri, ci) => {
      const r = DATA.results[ri];
      if (!r) return;
      const col = thColors[ci % thColors.length];
      const tag = document.createElement('span');
      tag.style.cssText = `display:inline-flex;align-items:center;gap:3px;padding:2px 8px;border-radius:3px;font-size:11px;background:${col}22;color:${col};border:1px solid ${col}`;
      tag.innerHTML = `${r.angle.name} <span style="cursor:pointer;font-size:13px;line-height:1" onclick="timeHistState.selectedAngles.splice(${ci},1);renderTimeHistory()">×</span>`;
      tagEl.appendChild(tag);
    });
    if (timeHistState.selectedAngles.length === 0) {
      tagEl.innerHTML = '<span style="color:var(--dim);font-size:11px">Click the map to select angles (max 8)</span>';
    }
  }

  // Full-width Mollweide angle selector map
  const mmEl = document.getElementById('th-mollweide-map');
  if (mmEl) {
    const MW = 700, MH = 260, mcx = MW/2, mcy = 130, msc = 100;
    let msvg = `<svg width="100%" height="${MH}" viewBox="0 0 ${MW} ${MH}" style="display:block;margin:0 auto">`;
    const rx = 2*Math.SQRT2*msc, ry = Math.SQRT2*msc;
    msvg += `<ellipse cx="${mcx}" cy="${mcy}" rx="${rx}" ry="${ry}" fill="var(--bg3)" stroke="var(--dim)" stroke-width="0.5"/>`;
    for (let lon = -150; lon <= 150; lon += 30) {
      let path = '';
      for (let lat = -85; lat <= 85; lat += 5) {
        const [px, py] = mollweideProject(lon, lat);
        path += (lat === -85 ? 'M' : 'L') + (mcx+px*msc).toFixed(1) + ',' + (mcy-py*msc).toFixed(1);
      }
      msvg += `<path d="${path}" fill="none" stroke="var(--dim)" stroke-width="0.3" opacity="0.3"/>`;
    }
    for (let lat = -60; lat <= 60; lat += 30) {
      let path = '';
      for (let lon = -180; lon <= 180; lon += 5) {
        const [px, py] = mollweideProject(lon, lat);
        path += (lon === -180 ? 'M' : 'L') + (mcx+px*msc).toFixed(1) + ',' + (mcy-py*msc).toFixed(1);
      }
      msvg += `<path d="${path}" fill="none" stroke="var(--dim)" stroke-width="0.3" opacity="0.3"/>`;
    }
    // Unselected dots first (below), then selected on top
    DATA.results.forEach((r, i) => {
      if (timeHistState.selectedAngles.includes(i)) return;
      const [lon, lat] = eulerToLonLat(r.angle.roll, r.angle.pitch, r.angle.yaw, r.angle.name, r.angle.swap);
      const [px, py] = mollweideProject(lon, lat);
      msvg += `<circle cx="${(mcx+px*msc).toFixed(1)}" cy="${(mcy-py*msc).toFixed(1)}" r="6" fill="#7982a9" opacity="0.5" style="cursor:pointer" `
        + `onclick="(function(){if(timeHistState.selectedAngles.length<8){timeHistState.selectedAngles.push(${i});renderTimeHistory();}})()"><title>${r.angle.name}</title></circle>`;
    });
    timeHistState.selectedAngles.forEach((ri, ci) => {
      const r = DATA.results[ri];
      if (!r) return;
      const [lon, lat] = eulerToLonLat(r.angle.roll, r.angle.pitch, r.angle.yaw, r.angle.name, r.angle.swap);
      const [px, py] = mollweideProject(lon, lat);
      const col = thColors[ci % thColors.length];
      msvg += `<circle cx="${(mcx+px*msc).toFixed(1)}" cy="${(mcy-py*msc).toFixed(1)}" r="9" fill="${col}" stroke="white" stroke-width="1.5" style="cursor:pointer" `
        + `onclick="(function(){timeHistState.selectedAngles.splice(${ci},1);renderTimeHistory()})()"><title>${r.angle.name} (click to remove)</title></circle>`;
    });
    // Direction labels
    msvg += `<text x="${mcx}" y="${mcy-ry-8}" text-anchor="middle" fill="var(--fg2)" font-size="11">Top</text>`;
    msvg += `<text x="${mcx}" y="${mcy+ry+16}" text-anchor="middle" fill="var(--fg2)" font-size="11">Bottom</text>`;
    msvg += `<text x="${mcx-rx-6}" y="${mcy+4}" text-anchor="end" fill="var(--fg2)" font-size="11">L</text>`;
    msvg += `<text x="${mcx+rx+6}" y="${mcy+4}" text-anchor="start" fill="var(--fg2)" font-size="11">R</text>`;
    // Info text
    msvg += `<text x="${MW-8}" y="16" text-anchor="end" fill="var(--dim)" font-size="10">${DATA.results.length} angles | ${timeHistState.selectedAngles.length}/8 selected · Click to toggle</text>`;
    msvg += '</svg>';
    mmEl.innerHTML = msvg;
  }

  drawTimeHistory();
}

function drawTimeHistory() {
  const chartEl = document.getElementById('th-chart');
  if (!chartEl) return;

  const pid = String(timeHistState.partId);
  const qty = timeHistState.quantity;
  const mode = timeHistState.chartMode;
  const comp = timeHistState.component;
  const W = 800, H = 350, ml = 70, mr = 20, mt = 20, mb = 40;
  const pw = W - ml - mr, ph = H - mt - mb;
  const colors = ['#f7768e','#e0af68','#7aa2f7','#9ece6a','#bb9af7','#7dcfff','#ff9e64','#2ac3de'];

  // Gather data
  const series = [];
  for (const ai of timeHistState.selectedAngles) {
    const r = DATA.results[ai];
    const pd = r.parts[pid];
    if (!pd) continue;
    let ts = null;
    if (qty === 'stress' && pd.stress_ts) {
      if (mode === 'envelope' && pd.stress_ts.min) {
        ts = { t: pd.stress_ts.t, v: pd.stress_ts.avg || pd.stress_ts.max, vmin: pd.stress_ts.min, vmax: pd.stress_ts.max };
      } else {
        ts = { t: pd.stress_ts.t, v: pd.stress_ts.max };
      }
    } else if (qty === 'strain' && pd.strain_ts) {
      ts = { t: pd.strain_ts.t, v: pd.strain_ts.max };
    } else if (qty === 'g') {
      if (comp !== 'mag' && pd.acc_ts && pd.acc_ts[comp]) {
        ts = { t: pd.acc_ts.t, v: pd.acc_ts[comp].map(v => v/1e6) };
      } else if (pd.g_ts) {
        ts = { t: pd.g_ts.t, v: pd.g_ts.g.map(v => v/1e6) };
      }
    } else if (qty === 'disp') {
      if (comp !== 'mag' && pd.disp_comp_ts && pd.disp_comp_ts[comp]) {
        ts = { t: pd.disp_comp_ts.t, v: pd.disp_comp_ts[comp] };
      } else if (pd.disp_ts) {
        ts = { t: pd.disp_ts.t, v: pd.disp_ts.mag };
      }
    }
    if (ts) series.push({ name: r.angle.name, data: ts, color: colors[series.length % colors.length] });
  }

  if (series.length === 0) { chartEl.innerHTML = '<div style="color:var(--dim);padding:20px">No data for selection</div>'; return; }

  // Find ranges (include envelope min/max)
  let tmin = Infinity, tmax = -Infinity, vmin = Infinity, vmax = -Infinity;
  for (const s of series) {
    for (const t of s.data.t) { tmin = Math.min(tmin, t); tmax = Math.max(tmax, t); }
    for (const v of s.data.v) { vmin = Math.min(vmin, v); vmax = Math.max(vmax, v); }
    if (s.data.vmin) for (const v of s.data.vmin) vmin = Math.min(vmin, v);
    if (s.data.vmax) for (const v of s.data.vmax) vmax = Math.max(vmax, v);
  }
  if (vmin === vmax) { vmin -= 1; vmax += 1; }
  const vpad = (vmax - vmin) * 0.05;
  vmin -= vpad; vmax += vpad;

  const mapX = t => ml + ((t - tmin) / (tmax - tmin)) * pw;
  const mapY = v => mt + ph - ((v - vmin) / (vmax - vmin)) * ph;

  let svg = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`;
  svg += `<rect x="${ml}" y="${mt}" width="${pw}" height="${ph}" fill="var(--bg3)" rx="2"/>`;
  const nticks = 5;
  for (let i = 0; i <= nticks; i++) {
    const y = mt + ph - (i/nticks)*ph;
    const v = vmin + (i/nticks)*(vmax-vmin);
    svg += `<line x1="${ml}" y1="${y}" x2="${ml+pw}" y2="${y}" stroke="#24283b" stroke-width="0.5"/>`;
    svg += `<text x="${ml-4}" y="${y+3}" text-anchor="end" fill="#7982a9" font-size="9">${formatAxisVal(v, qty)}</text>`;
  }
  for (let i = 0; i <= 5; i++) {
    const x = ml + (i/5)*pw;
    const t = tmin + (i/5)*(tmax-tmin);
    svg += `<text x="${x}" y="${mt+ph+14}" text-anchor="middle" fill="#7982a9" font-size="9">${(t*1000).toFixed(3)} ms</text>`;
  }

  // Draw series
  for (const s of series) {
    if (s.data.vmin && s.data.vmax) {
      // Envelope: filled area between min and max
      let area = '';
      for (let i = 0; i < s.data.t.length; i++) area += (i===0?'M':'L') + `${mapX(s.data.t[i]).toFixed(1)},${mapY(s.data.vmax[i]).toFixed(1)}`;
      for (let i = s.data.t.length-1; i >= 0; i--) area += `L${mapX(s.data.t[i]).toFixed(1)},${mapY(s.data.vmin[i]).toFixed(1)}`;
      svg += `<path d="${area}Z" fill="${s.color}" class="envelope-area"/>`;
    }
    // Main line (avg in envelope mode, value in lines mode)
    let path = '';
    for (let i = 0; i < s.data.t.length; i++) path += (i===0?'M':'L') + `${mapX(s.data.t[i]).toFixed(1)},${mapY(s.data.v[i]).toFixed(1)}`;
    svg += `<path d="${path}" fill="none" stroke="${s.color}" stroke-width="1.5"/>`;
  }

  // Legend
  let ly = mt + 8;
  for (const s of series) {
    svg += `<rect x="${ml+8}" y="${ly}" width="12" height="3" fill="${s.color}" rx="1"/>`;
    svg += `<text x="${ml+24}" y="${ly+3}" fill="var(--fg2)" font-size="10">${s.name}</text>`;
    ly += 14;
  }

  const compLabel = comp !== 'mag' ? ` (${comp.toUpperCase()})` : '';
  const yLabel = qty === 'stress' ? 'Von Mises (MPa)' : qty === 'strain' ? 'Eff. Plastic Strain' : qty === 'g' ? `G-Force (MG)${compLabel}` : `Displacement (mm)${compLabel}`;
  svg += `<text x="12" y="${mt+ph/2}" text-anchor="middle" fill="#7982a9" font-size="10" transform="rotate(-90,12,${mt+ph/2})">${yLabel}</text>`;

  svg += '</svg>';
  chartEl.innerHTML = svg;
}

function formatAxisVal(v, qty) {
  if (qty === 'g') return v.toFixed(2);
  if (qty === 'strain') return v.toFixed(4);
  if (Math.abs(v) >= 1000) return (v/1000).toFixed(1) + 'k';
  return v.toFixed(1);
}

// ============ Tab 3: Part Risk ============
function renderPartRisk() {
  const container = document.getElementById('partrisk-content');
  if (!container || container.dataset.done) return;
  container.dataset.done = '1';

  // Worst-case table
  let rows = '';
  const pids = getAllPartIds();
  for (const pid of pids) {
    const p = DATA.parts[String(pid)];
    let ws=0,wa='',wg=0,wga='',wst=0,wsta='',wd=0,wda='';
    for (const r of DATA.results) {
      const pd = r.parts[String(pid)];
      if (!pd) continue;
      if (pd.peak_stress > ws) { ws = pd.peak_stress; wa = r.angle.name; }
      if (pd.peak_g > wg) { wg = pd.peak_g; wga = r.angle.name; }
      if (pd.peak_strain > wst) { wst = pd.peak_strain; wsta = r.angle.name; }
      if (pd.peak_disp > wd) { wd = pd.peak_disp; wda = r.angle.name; }
    }
    if (ws === 0 && wg === 0) continue;
    rows += `<tr>
      <td style="color:var(--cyan)">Part ${pid}</td><td>${p.name}</td><td>${p.group}</td>
      <td style="text-align:right">${ws.toFixed(1)}</td><td style="color:var(--yellow)">${wa}</td>
      <td style="text-align:right">${(wg/1e6).toFixed(2)}</td><td style="color:var(--yellow)">${wga}</td>
      <td style="text-align:right">${wst.toFixed(4)}</td><td style="color:var(--yellow)">${wsta}</td>
    </tr>`;
  }

  // Group summary
  const groups = getPartGroups();
  let groupHtml = '';
  for (const [gname, gpids] of Object.entries(groups)) {
    let gmax_s=0, gmax_g=0, gmax_st=0, count=0;
    const stresses=[], gs=[];
    for (const pid of gpids) {
      for (const r of DATA.results) {
        const pd = r.parts[String(pid)];
        if (!pd) continue;
        count++;
        stresses.push(pd.peak_stress);
        gs.push(pd.peak_g);
        gmax_s = Math.max(gmax_s, pd.peak_stress);
        gmax_g = Math.max(gmax_g, pd.peak_g);
        gmax_st = Math.max(gmax_st, pd.peak_strain);
      }
    }
    if (count === 0) continue;
    const avg_s = stresses.reduce((a,b)=>a+b,0)/stresses.length;
    const avg_g = gs.reduce((a,b)=>a+b,0)/gs.length;
    groupHtml += `<div class="stat-card">
      <div class="value" style="font-size:16px;color:var(--cyan)">${gname}</div>
      <div class="label">${gpids.length} parts</div>
      <div style="margin-top:8px;text-align:left;font-size:11px;color:var(--fg2)">
        Max Stress: <b>${gmax_s.toFixed(1)} MPa</b><br>
        Avg Stress: ${avg_s.toFixed(1)} MPa<br>
        Max G: <b>${(gmax_g/1e6).toFixed(2)} MG</b><br>
        Avg G: ${(avg_g/1e6).toFixed(2)} MG<br>
        Max Strain: <b>${gmax_st.toFixed(4)}</b>
      </div>
    </div>`;
  }

  container.innerHTML = `
    <div class="panel"><h2>Part Group Summary</h2>
      <div class="stat-grid">${groupHtml}</div>
    </div>
    <div class="panel"><h2>Worst-Case Per Part (All Angles)</h2>
      <div class="table-wrap" style="max-height:500px;overflow-y:auto;">
      <table>
        <tr><th>Part</th><th>Name</th><th>Group</th><th>Stress (MPa)</th><th>Angle</th><th>MG</th><th>Angle</th><th>Strain</th><th>Angle</th></tr>
        ${rows}
      </table></div>
    </div>`;
}

// ============ Tab 4: Heatmap ============
let gforceState = { groupFilter: 'ALL', quantity: 'peak_g' };
const HM_QTYS = [
  { key: 'peak_g', label: 'G-Force (MG)', fmt: v => (v/1e6).toFixed(2) + ' MG' },
  { key: 'peak_stress', label: 'Stress (MPa)', fmt: v => v.toFixed(1) + ' MPa' },
  { key: 'peak_strain', label: 'Eff. Plastic Strain', fmt: v => v.toFixed(4) },
  { key: 'peak_disp', label: 'Displacement (mm)', fmt: v => v.toFixed(2) + ' mm' },
  { key: 'peak_vel', label: 'Velocity (mm/s)', fmt: v => v.toFixed(1) + ' mm/s' },
];

function renderGForce() {
  const container = document.getElementById('gforce-content');
  if (!container) return;

  const groups = getPartGroups();
  const qtyInfo = HM_QTYS.find(q => q.key === gforceState.quantity) || HM_QTYS[0];

  let filterHtml = `<div class="controls"><label>Quantity:</label>
    <select id="hm-qty" onchange="gforceState.quantity=this.value;renderGForce()">`;
  for (const q of HM_QTYS) filterHtml += `<option value="${q.key}"${q.key===gforceState.quantity?' selected':''}>${q.label}</option>`;
  filterHtml += `</select><label style="margin-left:12px">Group:</label>
    <select id="gf-group" onchange="gforceState.groupFilter=this.value;renderGForce()">
      <option value="ALL">All Parts</option>`;
  for (const g of Object.keys(groups)) filterHtml += `<option value="${g}"${g===gforceState.groupFilter?' selected':''}>${g}</option>`;
  filterHtml += '</select></div>';

  // Build heatmap data: parts × angles
  const gf = gforceState.groupFilter;
  const qty = gforceState.quantity;
  const pids = gf === 'ALL' ? getAllPartIds() : (groups[gf] || []);

  const cellW = Math.max(16, Math.min(28, 700 / DATA.results.length));
  const cellH = 20;
  const labelW = 100;
  // Measure max angle label length for bottom margin
  const maxLabelLen = Math.max(...DATA.results.map(r => r.angle.name.length));
  const bottomLabelH = Math.min(maxLabelLen * 5.5, 120) + 10;
  const topPad = 10;
  const gridTop = topPad;
  const W = labelW + cellW * DATA.results.length + 20;
  const H = gridTop + cellH * pids.length + bottomLabelH;

  let vmin = Infinity, vmax = -Infinity;
  const matrix = [];
  for (const pid of pids) {
    const row = [];
    for (const r of DATA.results) {
      const pd = r.parts[String(pid)];
      const v = getQtyValue(pd, qty);
      row.push(v);
      if (v < vmin) vmin = v;
      if (v > vmax) vmax = v;
    }
    matrix.push(row);
  }
  const vrange = vmax - vmin || 1;

  let svg = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`;

  // Cells
  pids.forEach((pid, i) => {
    const y = gridTop + i*cellH;
    const p = DATA.parts[String(pid)];
    svg += `<text x="${labelW-4}" y="${y+cellH/2+3}" text-anchor="end" fill="var(--fg2)" font-size="10">${p ? p.name.split('\\\\').pop() : 'P'+pid}</text>`;
    matrix[i].forEach((v, j) => {
      const norm = (v - vmin) / vrange;
      const color = valueToColor(norm);
      svg += `<rect x="${labelW+j*cellW}" y="${y}" width="${cellW-1}" height="${cellH-1}" fill="${color}" rx="2">
        <title>${DATA.results[j].angle.name}: ${qtyInfo.fmt(v)}</title></rect>`;
    });
  });

  // Angle labels below the grid (rotated -60° for readability)
  const labelTop = gridTop + cellH * pids.length + 4;
  DATA.results.forEach((r, j) => {
    const x = labelW + j*cellW + cellW/2;
    svg += `<text x="${x}" y="${labelTop}" text-anchor="end" fill="#7982a9" font-size="9" transform="rotate(-60,${x},${labelTop})">${r.angle.name}</text>`;
  });

  svg += '</svg>';

  // Top values table
  let topRows = '';
  const allVals = [];
  for (const pid of pids) {
    for (const r of DATA.results) {
      const pd = r.parts[String(pid)];
      if (pd) allVals.push({ pid, v: getQtyValue(pd, qty), angle: r.angle.name, part: DATA.parts[String(pid)]?.name || '' });
    }
  }
  allVals.sort((a,b) => b.v - a.v);
  for (const item of allVals.slice(0, 20)) {
    topRows += `<tr><td>${item.part}</td><td style="text-align:right;font-weight:bold;color:var(--red)">${qtyInfo.fmt(item.v)}</td><td>${item.angle}</td></tr>`;
  }

  container.innerHTML = `${filterHtml}
    <div class="panel"><h2>${qtyInfo.label} Heatmap (Part × Angle)</h2>
      <div style="overflow-x:auto">${svg}</div>
    </div>
    <div class="panel"><h2>Top 20 ${qtyInfo.label} Values</h2>
      <table><tr><th>Part</th><th>${qtyInfo.label}</th><th>Angle</th></tr>${topRows}</table>
    </div>`;
}

// ============ Tab 5: Directional Sensitivity ============
function renderDirectional() {
  const container = document.getElementById('directional-content');
  if (!container || container.dataset.done) return;
  container.dataset.done = '1';

  // Rank angles by total risk (sum of normalized stress across all parts)
  const angleScores = DATA.results.map(r => {
    let totalStress = 0, totalG = 0, count = 0;
    for (const [pid, pd] of Object.entries(r.parts)) {
      totalStress += pd.peak_stress;
      totalG += pd.peak_g;
      count++;
    }
    return { name: r.angle.name, category: r.angle.category, roll: r.angle.roll, pitch: r.angle.pitch,
             avgStress: count ? totalStress/count : 0, avgG: count ? totalG/count : 0, totalStress, totalG };
  });

  // Sort by total stress
  const byStress = [...angleScores].sort((a,b) => b.totalStress - a.totalStress);
  let rankRows = '';
  byStress.forEach((a, i) => {
    rankRows += `<tr><td>${i+1}</td><td style="color:var(--cyan)">${a.name}</td><td>${a.category}</td>
      <td style="text-align:right">${a.avgStress.toFixed(1)}</td>
      <td style="text-align:right">${(a.avgG/1e6).toFixed(2)}</td>
      <td>R:${a.roll.toFixed(0)}° P:${a.pitch.toFixed(0)}°</td></tr>`;
  });

  // Category stats
  const cats = {};
  for (const a of angleScores) {
    if (!cats[a.category]) cats[a.category] = { stresses: [], gs: [], count: 0 };
    cats[a.category].stresses.push(a.avgStress);
    cats[a.category].gs.push(a.avgG);
    cats[a.category].count++;
  }
  let catHtml = '';
  for (const [cat, data] of Object.entries(cats)) {
    const avgS = data.stresses.reduce((a,b)=>a+b,0)/data.count;
    const maxS = Math.max(...data.stresses);
    const avgG = data.gs.reduce((a,b)=>a+b,0)/data.count;
    catHtml += `<div class="stat-card">
      <div class="value" style="font-size:16px">${cat}</div>
      <div class="label">${data.count} directions</div>
      <div style="margin-top:6px;text-align:left;font-size:11px;color:var(--fg2)">
        Avg Stress: ${avgS.toFixed(1)} MPa<br>Max: ${maxS.toFixed(1)} MPa<br>Avg G: ${(avgG/1e6).toFixed(2)} MG
      </div></div>`;
  }

  // Symmetry check
  let symHtml = '';
  const pairs = [['F1_Back','F2_Front'],['F3_Right','F4_Left'],['F5_Top','F6_Bottom']];
  for (const [a1, a2] of pairs) {
    const s1 = angleScores.find(a => a.name === a1);
    const s2 = angleScores.find(a => a.name === a2);
    if (s1 && s2) {
      const diff = Math.abs(s1.avgStress - s2.avgStress);
      const pct = s1.avgStress > 0 ? (diff / Math.max(s1.avgStress, s2.avgStress) * 100) : 0;
      symHtml += `<tr><td>${a1}</td><td style="text-align:right">${s1.avgStress.toFixed(1)}</td>
        <td>${a2}</td><td style="text-align:right">${s2.avgStress.toFixed(1)}</td>
        <td style="text-align:right;color:${pct>20?'var(--red)':'var(--green)'}">${pct.toFixed(1)}%</td></tr>`;
    }
  }

  // Axis dominance chart: per-angle X/Y/Z acceleration proportion
  let axisDomSvg = '';
  const adAngles = DATA.results.filter(r => {
    const pd = Object.values(r.parts)[0];
    return pd && pd.acc_ts && pd.acc_ts.x;
  });
  if (adAngles.length > 0) {
    const ADW = 700, ADH = Math.max(200, adAngles.length * 18 + 50);
    const adml = 120, admr = 80, admt = 20, admb = 30;
    const adpw = ADW - adml - admr, adph = ADH - admt - admb;
    const barH = Math.min(14, adph / adAngles.length - 2);
    axisDomSvg = `<svg width="${ADW}" height="${ADH}" viewBox="0 0 ${ADW} ${ADH}">`;
    axisDomSvg += `<rect x="${adml}" y="${admt}" width="${adpw}" height="${adph}" fill="var(--bg3)" rx="2"/>`;
    adAngles.forEach((r, i) => {
      // sum peak absolute acceleration per axis across all parts
      let sx=0, sy=0, sz=0;
      for (const pd of Object.values(r.parts)) {
        if (!pd.acc_ts) continue;
        sx += Math.max(...pd.acc_ts.x.map(Math.abs));
        sy += Math.max(...pd.acc_ts.y.map(Math.abs));
        sz += Math.max(...pd.acc_ts.z.map(Math.abs));
      }
      const total = sx + sy + sz || 1;
      const fx = sx/total, fy = sy/total, fz = sz/total;
      const by = admt + (i / adAngles.length) * adph + 1;
      const wx = fx * adpw, wy = fy * adpw, wz = fz * adpw;
      axisDomSvg += `<rect x="${adml}" y="${by.toFixed(1)}" width="${wx.toFixed(1)}" height="${barH}" fill="#f7768e" opacity="0.8"><title>X: ${(fx*100).toFixed(1)}%</title></rect>`;
      axisDomSvg += `<rect x="${(adml+wx).toFixed(1)}" y="${by.toFixed(1)}" width="${wy.toFixed(1)}" height="${barH}" fill="#9ece6a" opacity="0.8"><title>Y: ${(fy*100).toFixed(1)}%</title></rect>`;
      axisDomSvg += `<rect x="${(adml+wx+wy).toFixed(1)}" y="${by.toFixed(1)}" width="${wz.toFixed(1)}" height="${barH}" fill="#7aa2f7" opacity="0.8"><title>Z: ${(fz*100).toFixed(1)}%</title></rect>`;
      axisDomSvg += `<text x="${adml-4}" y="${(by+barH/2+3).toFixed(1)}" text-anchor="end" fill="var(--fg2)" font-size="9">${r.angle.name}</text>`;
    });
    // Legend
    const lx = ADW - admr + 8;
    axisDomSvg += `<rect x="${lx}" y="${admt}" width="10" height="10" fill="#f7768e"/><text x="${lx+14}" y="${admt+9}" fill="var(--fg2)" font-size="10">X</text>`;
    axisDomSvg += `<rect x="${lx}" y="${admt+16}" width="10" height="10" fill="#9ece6a"/><text x="${lx+14}" y="${admt+25}" fill="var(--fg2)" font-size="10">Y</text>`;
    axisDomSvg += `<rect x="${lx}" y="${admt+32}" width="10" height="10" fill="#7aa2f7"/><text x="${lx+14}" y="${admt+41}" fill="var(--fg2)" font-size="10">Z</text>`;
    axisDomSvg += '</svg>';
  }

  container.innerHTML = `
    <div class="panel"><h2>Direction Category Comparison</h2><div class="stat-grid">${catHtml}</div></div>
    <div class="panel"><h2>Direction Ranking (by Total Stress)</h2>
      <div class="table-wrap" style="max-height:400px;overflow-y:auto;">
      <table><tr><th>#</th><th>Direction</th><th>Category</th><th>Avg Stress</th><th>Avg MG</th><th>Angles</th></tr>${rankRows}</table></div>
    </div>
    ${axisDomSvg ? `<div class="panel"><h2>Axis Dominance (Acceleration X/Y/Z Ratio per Direction)</h2>
      <div style="overflow-x:auto">${axisDomSvg}</div></div>` : ''}
    ${symHtml ? `<div class="panel"><h2>Symmetry Analysis (Face Pairs)</h2>
      <table><tr><th>Direction A</th><th>Stress</th><th>Direction B</th><th>Stress</th><th>Asymmetry</th></tr>${symHtml}</table></div>` : ''}`;
}

// ============ Tab 6: Failure Prediction ============
function renderFailure() {
  const container = document.getElementById('failure-content');
  if (!container || container.dataset.done) return;
  container.dataset.done = '1';

  const ys = DATA.yield_stress;
  let sfRows = '';
  const pids = getAllPartIds();

  // Safety factor table
  for (const pid of pids) {
    const p = DATA.parts[String(pid)];
    let maxStress = 0, worstAngle = '';
    for (const r of DATA.results) {
      const pd = r.parts[String(pid)];
      if (pd && pd.peak_stress > maxStress) { maxStress = pd.peak_stress; worstAngle = r.angle.name; }
    }
    if (maxStress === 0) continue;
    const sf = ys > 0 ? ys / maxStress : 0;
    const sfColor = sf > 0 ? (sf < 1 ? 'var(--red)' : sf < 1.5 ? 'var(--yellow)' : 'var(--green)') : 'var(--dim)';
    sfRows += `<tr><td>Part ${pid}</td><td>${p ? p.name : ''}</td>
      <td style="text-align:right">${maxStress.toFixed(1)}</td>
      <td>${worstAngle}</td>
      <td style="text-align:right;font-weight:bold;color:${sfColor}">${sf > 0 ? sf.toFixed(2) : 'N/A'}</td></tr>`;
  }

  // Energy estimate
  const h = DATA.sim_params.drop_height / 1000; // m
  const KE = 9.81 * h; // J/kg (specific energy)

  container.innerHTML = `
    <div class="panel"><h2>Safety Factor Analysis</h2>
      ${ys > 0 ? `<div style="margin-bottom:8px;color:var(--fg2)">Yield stress: <b>${ys.toFixed(1)} MPa</b> | SF &lt; 1.0 = <span style="color:var(--red)">FAIL</span> | SF &lt; 1.5 = <span style="color:var(--yellow)">WARNING</span></div>` :
        '<div style="color:var(--yellow);margin-bottom:8px">Set --yield-stress to enable safety factor calculation</div>'}
      <div class="table-wrap" style="max-height:500px;overflow-y:auto;">
      <table><tr><th>Part</th><th>Name</th><th>Peak Stress (MPa)</th><th>Worst Angle</th><th>Safety Factor</th></tr>${sfRows}</table></div>
    </div>
    <div class="panel"><h2>Energy Analysis</h2>
      <div class="stat-grid">
        <div class="stat-card"><div class="value">${DATA.sim_params.drop_height.toFixed(0)} mm</div><div class="label">Drop Height</div></div>
        <div class="stat-card"><div class="value">${(Math.sqrt(2*9.81*h)*1000).toFixed(1)} mm/s</div><div class="label">Impact Velocity</div></div>
        <div class="stat-card"><div class="value">${KE.toFixed(2)} J/kg</div><div class="label">Specific KE</div></div>
      </div>
    </div>`;
}

// ============ Tab 7: Statistics ============
function renderStatistics() {
  const container = document.getElementById('statistics-content');
  if (!container || container.dataset.done) return;
  container.dataset.done = '1';

  // Descriptive stats per part
  const pids = getAllPartIds();
  let statsRows = '';
  for (const pid of pids) {
    const p = DATA.parts[String(pid)];
    const stresses = [], gs = [], strains = [];
    for (const r of DATA.results) {
      const pd = r.parts[String(pid)];
      if (!pd) continue;
      stresses.push(pd.peak_stress);
      gs.push(pd.peak_g);
      strains.push(pd.peak_strain);
    }
    if (stresses.length === 0) continue;
    const mean_s = stresses.reduce((a,b)=>a+b,0)/stresses.length;
    const std_s = Math.sqrt(stresses.map(v=>(v-mean_s)**2).reduce((a,b)=>a+b,0)/stresses.length);
    const mean_g = gs.reduce((a,b)=>a+b,0)/gs.length;
    const std_g = Math.sqrt(gs.map(v=>(v-mean_g)**2).reduce((a,b)=>a+b,0)/gs.length);
    statsRows += `<tr><td>Part ${pid}</td><td>${p?p.name:''}</td>
      <td style="text-align:right">${mean_s.toFixed(1)}</td>
      <td style="text-align:right">${std_s.toFixed(1)}</td>
      <td style="text-align:right">${Math.max(...stresses).toFixed(1)}</td>
      <td style="text-align:right">${Math.min(...stresses).toFixed(1)}</td>
      <td style="text-align:right">${(mean_g/1e6).toFixed(2)}</td>
      <td style="text-align:right">${(std_g/1e6).toFixed(2)}</td></tr>`;
  }

  // Correlation: stress vs G scatter
  const scatterData = [];
  for (const r of DATA.results) {
    for (const [pid, pd] of Object.entries(r.parts)) {
      scatterData.push({ s: pd.peak_stress, g: pd.peak_g, angle: r.angle.name, pid });
    }
  }
  // Simple scatter SVG
  const SW = 500, SH = 350, sml = 60, smr = 20, smt = 20, smb = 40;
  const spw = SW - sml - smr, sph = SH - smt - smb;
  let smin = 0, smax = Math.max(...scatterData.map(d=>d.s), 1);
  let gmin2 = 0, gmax2 = Math.max(...scatterData.map(d=>d.g), 1);
  let scatterSvg = `<svg width="${SW}" height="${SH}" viewBox="0 0 ${SW} ${SH}">`;
  scatterSvg += `<rect x="${sml}" y="${smt}" width="${spw}" height="${sph}" fill="var(--bg3)" rx="2"/>`;
  for (const d of scatterData) {
    const x = sml + (d.s / smax) * spw;
    const y = smt + sph - (d.g / gmax2) * sph;
    scatterSvg += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="var(--cyan)" opacity="0.5"><title>P${d.pid} @ ${d.angle}: ${d.s.toFixed(1)} MPa, ${(d.g/1e6).toFixed(2)} MG</title></circle>`;
  }
  scatterSvg += `<text x="${sml+spw/2}" y="${SH-4}" text-anchor="middle" fill="#7982a9" font-size="10">Peak Stress (MPa)</text>`;
  scatterSvg += `<text x="12" y="${smt+sph/2}" text-anchor="middle" fill="#7982a9" font-size="10" transform="rotate(-90,12,${smt+sph/2})">Peak G (MG)</text>`;
  scatterSvg += '</svg>';

  // Velocity-Stress scatter (Step 7)
  const velStressData = [];
  const velGData = [];
  for (const r of DATA.results) {
    for (const [pid, pd] of Object.entries(r.parts)) {
      if (pd.peak_vel !== undefined) {
        velStressData.push({ v: pd.peak_vel, s: pd.peak_stress, angle: r.angle.name, pid });
        velGData.push({ v: pd.peak_vel, g: pd.peak_g, angle: r.angle.name, pid });
      }
    }
  }
  let velStressSvg = '', velGSvg = '';
  if (velStressData.length > 0) {
    const vmax = Math.max(...velStressData.map(d=>d.v), 1);
    // Velocity vs Stress
    velStressSvg = `<svg width="${SW}" height="${SH}" viewBox="0 0 ${SW} ${SH}">`;
    velStressSvg += `<rect x="${sml}" y="${smt}" width="${spw}" height="${sph}" fill="var(--bg3)" rx="2"/>`;
    for (const d of velStressData) {
      const x = sml + (d.v / vmax) * spw;
      const y = smt + sph - (d.s / smax) * sph;
      velStressSvg += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="#bb9af7" opacity="0.5"><title>P${d.pid} @ ${d.angle}: ${d.v.toFixed(1)} mm/s, ${d.s.toFixed(1)} MPa</title></circle>`;
    }
    velStressSvg += `<text x="${sml+spw/2}" y="${SH-4}" text-anchor="middle" fill="#7982a9" font-size="10">Peak Velocity (mm/s)</text>`;
    velStressSvg += `<text x="12" y="${smt+sph/2}" text-anchor="middle" fill="#7982a9" font-size="10" transform="rotate(-90,12,${smt+sph/2})">Peak Stress (MPa)</text>`;
    velStressSvg += '</svg>';
    // Velocity vs G
    velGSvg = `<svg width="${SW}" height="${SH}" viewBox="0 0 ${SW} ${SH}">`;
    velGSvg += `<rect x="${sml}" y="${smt}" width="${spw}" height="${sph}" fill="var(--bg3)" rx="2"/>`;
    for (const d of velGData) {
      const x = sml + (d.v / vmax) * spw;
      const y = smt + sph - (d.g / gmax2) * sph;
      velGSvg += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="#ff9e64" opacity="0.5"><title>P${d.pid} @ ${d.angle}: ${d.v.toFixed(1)} mm/s, ${(d.g/1e6).toFixed(2)} MG</title></circle>`;
    }
    velGSvg += `<text x="${sml+spw/2}" y="${SH-4}" text-anchor="middle" fill="#7982a9" font-size="10">Peak Velocity (mm/s)</text>`;
    velGSvg += `<text x="12" y="${smt+sph/2}" text-anchor="middle" fill="#7982a9" font-size="10" transform="rotate(-90,12,${smt+sph/2})">Peak G (MG)</text>`;
    velGSvg += '</svg>';
  }

  container.innerHTML = `
    <div class="panel"><h2>Descriptive Statistics (Per Part, Across All Angles)</h2>
      <div class="table-wrap" style="max-height:500px;overflow-y:auto;">
      <table><tr><th>Part</th><th>Name</th><th>Mean Stress</th><th>Std Dev</th><th>Max</th><th>Min</th><th>Mean MG</th><th>Std MG</th></tr>${statsRows}</table></div>
    </div>
    <div class="panel"><h2>Stress vs G-Force Correlation</h2>${scatterSvg}</div>
    ${velStressSvg ? `<div class="panel"><h2>Velocity vs Stress Correlation</h2>
      <div style="display:flex;gap:16px;flex-wrap:wrap">
        <div>${velStressSvg}</div><div>${velGSvg}</div>
      </div></div>` : ''}`;
}

// ============ Tab 8: Impact Analysis ============
function detectPeaks(values, threshold, minSep) {
  // Simple local maxima detection
  const absMax = Math.max(...values.map(Math.abs));
  const thresh = absMax * threshold;
  const peaks = [];
  for (let i = 1; i < values.length - 1; i++) {
    const v = Math.abs(values[i]);
    if (v >= thresh && v >= Math.abs(values[i-1]) && v >= Math.abs(values[i+1])) {
      if (peaks.length === 0 || i - peaks[peaks.length-1].idx >= minSep) {
        peaks.push({ idx: i, val: values[i] });
      } else if (v > Math.abs(peaks[peaks.length-1].val)) {
        peaks[peaks.length-1] = { idx: i, val: values[i] };
      }
    }
  }
  return peaks;
}

let impactState = { partId: 0 };

function renderImpactAnalysis() {
  const container = document.getElementById('impact-content');
  if (!container) return;
  const ko = reportLang === 'ko';

  const pids = getAllPartIds();
  if (impactState.partId === 0 && pids.length > 0) impactState.partId = pids[0];
  const selPid = String(impactState.partId);

  // Part selector
  let html = `<div class="controls"><label>${ko?'분석 부품:':'Analysis Part:'}</label>
    <select id="impact-part" onchange="impactState.partId=parseInt(this.value);document.getElementById('impact-content').dataset.done='';renderImpactAnalysis()">`;
  for (const pid of pids) {
    const p = DATA.parts[String(pid)];
    html += `<option value="${pid}"${pid===impactState.partId?' selected':''}>${p?p.name:''} (ID:${pid})</option>`;
  }
  html += '</select></div>';

  // ---- Impact Phase Timing ----
  const catColors = { face: '#f7768e', edge: '#e0af68', corner: '#9ece6a', fibonacci: '#7dcfff', other: '#bb9af7' };
  let phaseRows = '';
  const phaseScatter = [];

  for (const r of DATA.results) {
    const pd = r.parts[selPid];
    if (!pd || !pd.g_ts || !pd.g_ts.g) continue;
    const gvals = pd.g_ts.g;
    const times = pd.g_ts.t;
    const peaks = detectPeaks(gvals, 0.3, 5);
    const peakG = Math.max(...gvals.map(Math.abs));
    const timeToPeak = peakG > 0 ? times[gvals.findIndex(v => Math.abs(v) === peakG)] || 0 : 0;
    const cat = r.angle.category || 'other';
    phaseRows += `<tr>
      <td style="color:var(--cyan)">${r.angle.name}</td>
      <td>${cat}</td>
      <td style="text-align:right">${(timeToPeak*1000).toFixed(3)} ms</td>
      <td style="text-align:right">${peaks.length > 0 ? (times[peaks[0].idx]*1000).toFixed(3) + ' ms' : '-'}</td>
      <td style="text-align:right">${peaks.length}</td>
      <td style="text-align:right">${(peakG/1e6).toFixed(2)} MG</td></tr>`;
    phaseScatter.push({ t: timeToPeak*1000, s: pd.peak_stress, cat, name: r.angle.name });
  }

  html += `<div class="panel"><h2>${ko?'충격 위상 타이밍':'Impact Phase Timing'}</h2>
    <div style="color:var(--fg2);font-size:12px;margin-bottom:8px">${ko
      ?'각 충격 방향에서 최대 가속도(G)가 발생하는 시점과 가속도 피크 수를 분석합니다. 최대 G 도달 시간이 빠를수록 충격이 급격하며, 피크 수가 많을수록 리바운드가 빈번합니다. 피크 검출: 최대값의 30% 임계값, 최소 5샘플 간격.'
      :'Analyzes when peak deceleration (G) occurs and how many acceleration peaks exist per direction. Faster time-to-peak means sharper impact; more peaks indicate frequent rebounds. Peak detection: 30% threshold, min 5-sample separation.'}
    </div>`;

  if (phaseRows) {
    html += `<div class="table-wrap" style="max-height:400px;overflow-y:auto;">
      <table><tr><th>${ko?'방향':'Direction'}</th><th>${ko?'카테고리':'Category'}</th><th>${ko?'최대G 도달시간':'Time to Peak'}</th><th>${ko?'1차 피크 시간':'1st Peak Time'}</th><th>${ko?'피크 수':'# Peaks'}</th><th>${ko?'최대 G':'Peak G'}</th></tr>${phaseRows}</table></div>`;
  } else {
    html += `<div style="color:var(--dim);padding:20px;text-align:center">${ko?'가속도 시계열 데이터가 없습니다.':'No acceleration time-series data available.'}</div>`;
  }
  html += '</div>';

  // Time-to-Peak vs Peak Stress scatter
  if (phaseScatter.length > 0) {
    const PSW = 550, PSH = 380, pml = 60, pmr = 80, pmt = 20, pmb = 40;
    const ppw = PSW - pml - pmr, pph = PSH - pmt - pmb;
    const tmax = Math.max(...phaseScatter.map(d=>d.t), 0.001);
    const smax = Math.max(...phaseScatter.map(d=>d.s), 1);
    let phaseSvg = `<svg width="100%" viewBox="0 0 ${PSW} ${PSH}" style="max-width:${PSW}px">`;
    phaseSvg += `<rect x="${pml}" y="${pmt}" width="${ppw}" height="${pph}" fill="var(--bg3)" rx="2"/>`;
    // Grid
    for (let i = 0; i <= 4; i++) {
      const y = pmt + pph * i / 4;
      phaseSvg += `<line x1="${pml}" y1="${y}" x2="${pml+ppw}" y2="${y}" stroke="rgba(255,255,255,0.06)"/>`;
      phaseSvg += `<text x="${pml-4}" y="${y+4}" text-anchor="end" fill="#7982a9" font-size="9">${(smax*(4-i)/4).toFixed(0)}</text>`;
    }
    for (let i = 0; i <= 4; i++) {
      const x = pml + ppw * i / 4;
      phaseSvg += `<line x1="${x}" y1="${pmt}" x2="${x}" y2="${pmt+pph}" stroke="rgba(255,255,255,0.06)"/>`;
      phaseSvg += `<text x="${x}" y="${pmt+pph+14}" text-anchor="middle" fill="#7982a9" font-size="9">${(tmax*i/4).toFixed(2)}</text>`;
    }
    for (const d of phaseScatter) {
      const x = pml + (d.t / tmax) * ppw;
      const y = pmt + pph - (d.s / smax) * pph;
      const col = catColors[d.cat] || catColors.other;
      phaseSvg += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="5" fill="${col}" opacity="0.7" stroke="rgba(255,255,255,0.3)" stroke-width="0.5"><title>${d.name} (${d.cat}): ${d.t.toFixed(3)} ms, ${d.s.toFixed(1)} MPa</title></circle>`;
    }
    phaseSvg += `<text x="${pml+ppw/2}" y="${PSH-4}" text-anchor="middle" fill="#7982a9" font-size="10">${ko?'최대G 도달시간 (ms)':'Time to Peak (ms)'}</text>`;
    phaseSvg += `<text x="12" y="${pmt+pph/2}" text-anchor="middle" fill="#7982a9" font-size="10" transform="rotate(-90,12,${pmt+pph/2})">${ko?'최대 응력 (MPa)':'Peak Stress (MPa)'}</text>`;
    let ly = pmt;
    for (const [cat, col] of Object.entries(catColors)) {
      phaseSvg += `<rect x="${PSW-pmr+8}" y="${ly}" width="10" height="10" fill="${col}"/><text x="${PSW-pmr+22}" y="${ly+9}" fill="var(--fg2)" font-size="9">${cat}</text>`;
      ly += 16;
    }
    phaseSvg += '</svg>';
    html += `<div class="panel"><h2>${ko?'최대G 도달시간 vs 최대응력 산점도':'Time-to-Peak vs Peak Stress'}</h2>
      <div style="color:var(--fg2);font-size:12px;margin-bottom:8px">${ko
        ?'최대 가속도 도달 시간(X축)과 해당 방향의 최대 응력(Y축)의 상관 관계입니다. 좌측 상단(빠른 도달 + 높은 응력)이 가장 가혹한 조건이며, 카테고리별 색상으로 면/모서리/꼭짓점 방향의 분포 패턴을 확인할 수 있습니다.'
        :'Correlation between time-to-peak-G (X) and peak stress (Y) per direction. Upper-left (fast arrival + high stress) represents the most severe conditions. Category colors show face/edge/corner distribution patterns.'}
      </div>
      <div style="overflow-x:auto">${phaseSvg}</div></div>`;
  }

  // ---- Hot-Spot Element Tracking (Cross-Part) ----
  const elemFreq = {}; // eid -> { count, angles, maxStress, partId, partName }
  const allPids = getAllPartIds();
  for (const r of DATA.results) {
    // Track global peak element across ALL parts for this angle
    let globalMaxStress = 0, globalMaxEid = 0, globalMaxPid = 0;
    for (const pid of allPids) {
      const pd = r.parts[String(pid)];
      if (!pd || !pd.stress_ts || !pd.stress_ts.elem || !pd.stress_ts.max) continue;
      const svals = pd.stress_ts.max;
      const elems = pd.stress_ts.elem;
      if (svals.length === 0 || elems.length === 0) continue;
      let maxIdx = 0;
      for (let i = 1; i < svals.length; i++) { if (svals[i] > svals[maxIdx]) maxIdx = i; }
      const eid = elems[Math.min(maxIdx, elems.length - 1)];
      if (eid === 0) continue;
      if (svals[maxIdx] > globalMaxStress) {
        globalMaxStress = svals[maxIdx]; globalMaxEid = eid; globalMaxPid = pid;
      }
      // Also track per-element across all parts
      const key = eid;
      if (!elemFreq[key]) elemFreq[key] = { count: 0, angles: new Set(), maxStress: 0, partId: pid, partName: '' };
      elemFreq[key].count++;
      elemFreq[key].angles.add(r.angle.name);
      if (svals[maxIdx] > elemFreq[key].maxStress) {
        elemFreq[key].maxStress = svals[maxIdx];
        elemFreq[key].partId = pid;
      }
    }
  }
  // Resolve part names
  for (const d of Object.values(elemFreq)) {
    const pi = DATA.parts[String(d.partId)];
    d.partName = pi ? pi.name : `Part ${d.partId}`;
  }
  const hotspots = Object.entries(elemFreq)
    .map(([eid, d]) => ({ eid, count: d.count, nAngles: d.angles.size, angles: [...d.angles].slice(0, 5), maxStress: d.maxStress, partId: d.partId, partName: d.partName }))
    .sort((a,b) => b.count - a.count)
    .slice(0, 15);

  html += `<div class="panel"><h2>${ko?'핫스팟 요소 추적 — 전체 파트 (상위 15개)':'Hot-Spot Elements — All Parts (Top 15)'}</h2>
    <div style="color:var(--fg2);font-size:12px;margin-bottom:8px">${ko
      ?'모든 부품을 교차 탐색하여, 여러 충격 방향에서 반복적으로 최대 응력점이 되는 요소를 식별합니다. 각 요소가 속한 부품을 함께 표시하여 어떤 부품의 어떤 위치가 구조적 취약점인지 한눈에 파악할 수 있습니다. 빈도가 높은 요소는 형상 기인 응력 집중점(필렛, 코너, 접합부 등)이며, 충격 방향과 무관하게 파손 위험이 높아 설계 개선 우선 대상입니다.'
      :'Scans across ALL parts to identify elements that repeatedly become peak-stress locations across multiple impact directions. Each element is shown with its parent part, making it easy to pinpoint which component and location constitutes a structural weak point. High-frequency elements are geometry-driven stress concentrations (fillets, corners, joints) that are failure-prone regardless of impact direction—prioritize these for design improvement.'}
    </div>`;

  if (hotspots.length > 0) {
    const maxCount = hotspots[0].count;
    // Mini histogram
    const BW = 500, BH = 160, bml = 45, bmr = 5, bmt = 5, bmb = 55;
    const bpw = BW - bml - bmr, bph = BH - bmt - bmb;
    const barW = Math.max(8, Math.min(24, bpw / hotspots.length - 3));
    let hsSvg = `<svg width="100%" viewBox="0 0 ${BW} ${BH}" style="max-width:${BW}px">
      <rect x="${bml}" y="${bmt}" width="${bpw}" height="${bph}" fill="var(--bg3)" rx="2"/>`;
    hotspots.forEach((d, i) => {
      const x = bml + (i + 0.5) * bpw / hotspots.length - barW / 2;
      const h = (d.count / maxCount) * bph;
      const pct = d.count / maxCount;
      const col = pct > 0.7 ? '#f7768e' : pct > 0.4 ? '#e0af68' : '#9ece6a';
      hsSvg += `<rect x="${x.toFixed(1)}" y="${(bmt+bph-h).toFixed(1)}" width="${barW}" height="${h.toFixed(1)}" fill="${col}" rx="2"><title>Elem ${d.eid} (${d.partName}): ${d.count}x, ${d.maxStress.toFixed(1)} MPa</title></rect>`;
      hsSvg += `<text x="${(x+barW/2).toFixed(1)}" y="${BH-bmb+12}" text-anchor="middle" fill="var(--fg2)" font-size="7" transform="rotate(-55,${(x+barW/2).toFixed(1)},${BH-bmb+12})">${d.eid}</text>`;
    });
    hsSvg += '</svg>';
    html += `<div style="overflow-x:auto;margin-bottom:8px">${hsSvg}</div>`;

    let hotspotRows = '';
    for (const h of hotspots) {
      const pct = h.count / maxCount;
      const badge = pct > 0.7 ? 'hotspot-badge' : pct > 0.4 ? 'hotspot-badge warn' : 'hotspot-badge ok';
      hotspotRows += `<tr>
        <td><span class="${badge}">${h.eid}</span></td>
        <td style="color:var(--cyan)">${h.partName} <span style="color:var(--dim);font-size:10px">(${h.partId})</span></td>
        <td style="text-align:right">${h.count}</td>
        <td style="text-align:right">${h.nAngles}</td>
        <td style="text-align:right">${h.maxStress.toFixed(1)}</td>
        <td style="color:var(--dim);font-size:11px">${h.angles.join(', ')}${h.nAngles > 5 ? '...' : ''}</td></tr>`;
    }
    html += `<table><tr><th>${ko?'요소 ID':'Element ID'}</th><th>${ko?'소속 부품':'Part'}</th><th>${ko?'빈도':'Count'}</th><th>${ko?'방향 수':'# Angles'}</th><th>${ko?'최대 응력':'Max Stress'} (MPa)</th><th>${ko?'출현 방향':'Angles'}</th></tr>${hotspotRows}</table>`;

    // Part-aggregated summary
    const partAgg = {};
    for (const h of hotspots) {
      if (!partAgg[h.partId]) partAgg[h.partId] = { name: h.partName, totalCount: 0, nElems: 0, maxStress: 0 };
      partAgg[h.partId].totalCount += h.count;
      partAgg[h.partId].nElems++;
      if (h.maxStress > partAgg[h.partId].maxStress) partAgg[h.partId].maxStress = h.maxStress;
    }
    const partSorted = Object.entries(partAgg).sort((a,b) => b[1].totalCount - a[1].totalCount);
    if (partSorted.length > 1) {
      html += `<div style="margin-top:10px;padding:8px;background:var(--bg3);border-radius:4px;border-left:3px solid var(--cyan)">
        <div style="font-size:11px;font-weight:bold;color:var(--cyan);margin-bottom:4px">${ko?'부품별 핫스팟 집중도':'Hotspot Concentration by Part'}</div>`;
      for (const [pid, pa] of partSorted) {
        const barPct = (pa.totalCount / partSorted[0][1].totalCount * 100).toFixed(0);
        html += `<div style="display:flex;align-items:center;gap:8px;margin:3px 0;font-size:11px">
          <span style="min-width:120px;color:var(--fg)">${pa.name} <span style="color:var(--dim)">(${pa.nElems}${ko?'개 요소':' elems'})</span></span>
          <div style="flex:1;height:12px;background:var(--bg2);border-radius:3px;overflow:hidden">
            <div style="width:${barPct}%;height:100%;background:var(--cyan);border-radius:3px"></div>
          </div>
          <span style="color:var(--fg2);min-width:70px;text-align:right">${pa.maxStress.toFixed(1)} MPa</span></div>`;
      }
      html += '</div>';
    }
  } else {
    html += `<div style="color:var(--dim);padding:20px;text-align:center">${ko?'요소별 응력 데이터(stress_ts.elem)가 없습니다. unified_analyzer에서 요소 ID 출력을 활성화하세요.':'No element-level stress data (stress_ts.elem) available. Enable element ID output in unified_analyzer.'}</div>`;
  }
  html += '</div>';

  container.innerHTML = html;
}

// ============ Tab 9: Part Analysis (Deep Dive) ============
let deepDiveState = { partId: 0 };

function computePartDeepDive(pid) {
  const pidStr = String(pid);
  const partInfo = DATA.parts[pidStr] || { name: 'Part '+pid, group: 'Other' };
  const ys = DATA.yield_stress;
  const perAngle = [];
  let worstStress={val:0,angle:'',ri:-1,category:''}, worstG={val:0,angle:'',ri:-1};
  let worstStrain={val:0,angle:'',ri:-1}, worstDisp={val:0,angle:'',ri:-1}, worstVel={val:0,angle:'',ri:-1};
  const allStress=[], allG=[], allStrain=[], allDisp=[], allVel=[];
  const byCat = {};
  let totalAccX=0, totalAccY=0, totalAccZ=0, accCount=0;
  const timeDomainFeatures = [];

  for (let ri=0; ri<DATA.results.length; ri++) {
    const r = DATA.results[ri];
    const pd = r.parts[pidStr];
    if (!pd) continue;
    const cat = r.angle.category || 'other';
    const entry = { ri, angleName: r.angle.name, category: cat,
      stress: pd.peak_stress, strain: pd.peak_strain, g: pd.peak_g,
      disp: pd.peak_disp, vel: pd.peak_vel||0 };
    perAngle.push(entry);
    if (pd.peak_stress > worstStress.val) worstStress = {val:pd.peak_stress, angle:r.angle.name, ri, category:cat};
    if (pd.peak_g > worstG.val) worstG = {val:pd.peak_g, angle:r.angle.name, ri};
    if (pd.peak_strain > worstStrain.val) worstStrain = {val:pd.peak_strain, angle:r.angle.name, ri};
    if (pd.peak_disp > worstDisp.val) worstDisp = {val:pd.peak_disp, angle:r.angle.name, ri};
    if ((pd.peak_vel||0) > worstVel.val) worstVel = {val:pd.peak_vel||0, angle:r.angle.name, ri};
    allStress.push(pd.peak_stress); allG.push(pd.peak_g);
    allStrain.push(pd.peak_strain); allDisp.push(pd.peak_disp); allVel.push(pd.peak_vel||0);
    if (!byCat[cat]) byCat[cat] = {stresses:[], gs:[], count:0, angles:[]};
    byCat[cat].stresses.push(pd.peak_stress); byCat[cat].gs.push(pd.peak_g);
    byCat[cat].count++; byCat[cat].angles.push(r.angle.name);
    if (pd.acc_ts && pd.acc_ts.x) {
      const px = Math.max(...pd.acc_ts.x.map(Math.abs));
      const py = Math.max(...pd.acc_ts.y.map(Math.abs));
      const pz = Math.max(...pd.acc_ts.z.map(Math.abs));
      totalAccX += px; totalAccY += py; totalAccZ += pz; accCount++;
    }
    if (pd.g_ts && pd.g_ts.g) {
      const gvals = pd.g_ts.g, times = pd.g_ts.t;
      const maxG = Math.max(...gvals.map(Math.abs));
      const peakIdx = gvals.findIndex(v => Math.abs(v) === maxG);
      const timeToPeak = peakIdx >= 0 ? times[peakIdx] : 0;
      const peaks = detectPeaks(gvals, 0.3, 5);
      timeDomainFeatures.push({ angleName: r.angle.name, timeToPeak, numPeaks: peaks.length, category: cat });
    }
  }
  const n = allStress.length;
  const meanStress = n ? allStress.reduce((a,b)=>a+b,0)/n : 0;
  const stdStress = n ? Math.sqrt(allStress.map(v=>(v-meanStress)**2).reduce((a,b)=>a+b,0)/n) : 0;
  const meanG = n ? allG.reduce((a,b)=>a+b,0)/n : 0;
  const cov = meanStress > 0 ? stdStress/meanStress : 0;
  const sf = ys > 0 && worstStress.val > 0 ? ys/worstStress.val : 0;
  const catRanking = Object.entries(byCat).map(([cat,d]) => ({
    cat, avgStress: d.stresses.reduce((a,b)=>a+b,0)/d.count,
    maxStress: Math.max(...d.stresses), avgG: d.gs.reduce((a,b)=>a+b,0)/d.count, count: d.count
  })).sort((a,b) => b.maxStress - a.maxStress);
  const totalAcc = totalAccX+totalAccY+totalAccZ || 1;
  const axisFracs = { x: totalAccX/totalAcc, y: totalAccY/totalAcc, z: totalAccZ/totalAcc };
  const group = partInfo.group || 'Other';
  const groups = getPartGroups();
  const siblings = (groups[group]||[]).filter(p => p !== pid);
  const siblingMetrics = [];
  for (const spid of siblings) {
    let ss=0, sg=0, sst=0;
    for (const r of DATA.results) { const pd=r.parts[String(spid)]; if(pd){ss=Math.max(ss,pd.peak_stress);sg=Math.max(sg,pd.peak_g);sst=Math.max(sst,pd.peak_strain);} }
    siblingMetrics.push({pid:spid, name:DATA.parts[String(spid)]?.name||'P'+spid, maxStress:ss, maxG:sg, maxStrain:sst});
  }
  const avgTimeToPeak = timeDomainFeatures.length > 0 ? timeDomainFeatures.reduce((s,f)=>s+f.timeToPeak,0)/timeDomainFeatures.length : 0;
  const avgNumPeaks = timeDomainFeatures.length > 0 ? timeDomainFeatures.reduce((s,f)=>s+f.numPeaks,0)/timeDomainFeatures.length : 0;
  const allPartWorst = getAllPartIds().map(p => {
    let mx=0; for(const r of DATA.results){const pd=r.parts[String(p)];if(pd)mx=Math.max(mx,pd.peak_stress);} return {pid:p, maxStress:mx};
  }).sort((a,b) => b.maxStress - a.maxStress);
  const globalRank = allPartWorst.findIndex(p => p.pid === pid) + 1;
  const totalParts = allPartWorst.length;
  return {
    pid, partInfo, ys, sf, perAngle, n,
    worstStress, worstG, worstStrain, worstDisp, worstVel,
    allStress, allG, allStrain, allDisp, allVel,
    meanStress, stdStress, meanG, cov,
    stressRange: { min: Math.min(...allStress, 0), max: Math.max(...allStress, 0), mean: meanStress, std: stdStress },
    byCat, catRanking, axisFracs, accCount,
    siblingMetrics, group, timeDomainFeatures, avgTimeToPeak, avgNumPeaks,
    globalRank, totalParts
  };
}

function buildNarrative(m) {
  const sentences = [];
  const H = s => `<span class="dd-highlight">${s}</span>`;
  const G = s => `<span class="dd-good">${s}</span>`;
  const W = s => `<span class="dd-warn">${s}</span>`;
  const B = s => `<span class="dd-bad">${s}</span>`;
  const ko = reportLang === 'ko';

  // 1. Opening
  sentences.push(ko
    ? `${H(m.partInfo.name)} (Part ${m.pid})은(는) ${H(m.group)} 그룹에 속하며, ${H(m.n+'개')} 충격 방향에 대해 평가되었습니다.`
    : `${H(m.partInfo.name)} (Part ${m.pid}) belongs to the ${H(m.group)} group. Evaluated across ${H(m.n)} impact directions.`);

  // 2. Global ranking
  if (m.globalRank <= 3) {
    sentences.push(ko
      ? `본 부품은 전체 ${m.totalParts}개 부품 중 최대 응력 ${B('#'+m.globalRank+'위')}로, 어셈블리에서 가장 높은 하중을 받는 부품 중 하나입니다.`
      : `This part ranks ${B('#'+m.globalRank+' of '+m.totalParts)} in peak stress across all parts, making it one of the most critically loaded components in the assembly.`);
  } else if (m.globalRank <= Math.ceil(m.totalParts*0.25)) {
    sentences.push(ko
      ? `본 부품은 전체 ${m.totalParts}개 부품 중 최대 응력 ${W('#'+m.globalRank+'위')}로, 상위 25% 이내에 해당합니다.`
      : `This part ranks ${W('#'+m.globalRank+' of '+m.totalParts)} in peak stress, placing it in the top quartile of loaded components.`);
  } else if (m.globalRank <= Math.ceil(m.totalParts*0.5)) {
    sentences.push(ko
      ? `본 부품은 전체 ${m.totalParts}개 부품 중 최대 응력 #${m.globalRank}위로, 중간 수준의 하중을 받고 있습니다.`
      : `This part ranks #${m.globalRank} of ${m.totalParts} in peak stress, placing it in the mid-range of loaded components.`);
  } else {
    sentences.push(ko
      ? `본 부품은 전체 ${m.totalParts}개 부품 중 최대 응력 ${G('#'+m.globalRank+'위')}로, 상대적으로 낮은 하중을 받는 부품입니다.`
      : `This part ranks ${G('#'+m.globalRank+' of '+m.totalParts)} in peak stress, indicating it is among the less critically loaded components.`);
  }

  // 3. Safety factor
  if (m.ys > 0) {
    const ov = ((1-m.sf)*100).toFixed(0);
    if (m.sf < 0.8) {
      sentences.push(ko
        ? `안전계수가 ${B(m.sf.toFixed(2))}로 1.0 이하입니다. ${H(m.worstStress.angle)} 방향 하중에서 항복이 강하게 예상됩니다. 최대 응력 ${B(m.worstStress.val.toFixed(1)+' MPa')}가 항복응력(${m.ys.toFixed(0)} MPa)을 ${B(ov+'%')} 초과합니다. 설계 보강 또는 재료 변경을 강력히 권고합니다.`
        : `The safety factor is ${B(m.sf.toFixed(2))}, well below 1.0. Yielding is highly likely under ${H(m.worstStress.angle)} loading. Peak stress ${B(m.worstStress.val.toFixed(1)+' MPa')} exceeds yield (${m.ys.toFixed(0)} MPa) by ${B(ov+'%')}. Design reinforcement or material upgrade is strongly recommended.`);
    } else if (m.sf < 1.0) {
      sentences.push(ko
        ? `안전계수가 ${B(m.sf.toFixed(2))}로 1.0 미만입니다. ${H(m.worstStress.angle)} 방향 최악 하중에서 항복이 예상됩니다. 응력 여유가 ${B(ov+'%')} 부족합니다. 재료 또는 형상 변경을 검토하세요.`
        : `The safety factor is ${B(m.sf.toFixed(2))}, below 1.0. Yielding is expected under worst-case loading from ${H(m.worstStress.angle)}. The stress margin is ${B(ov+'%')} over yield. Consider material or geometry changes.`);
    } else if (m.sf < 1.25) {
      sentences.push(ko
        ? `안전계수가 ${W(m.sf.toFixed(2))}로 1.0 약간 이상입니다. 제조 편차나 재료 산포를 고려하면 여유가 매우 적습니다. 최악 하중: ${H(m.worstStress.val.toFixed(1)+' MPa')} (${H(m.worstStress.angle)} 방향).`
        : `The safety factor is ${W(m.sf.toFixed(2))}, marginally above 1.0. There is very little margin for manufacturing variation or material scatter. Worst load: ${H(m.worstStress.val.toFixed(1)+' MPa')} from ${H(m.worstStress.angle)}.`);
    } else if (m.sf < 1.5) {
      sentences.push(ko
        ? `안전계수가 ${W(m.sf.toFixed(2))}입니다. 공칭 하중에서는 생존하지만 여유는 보통 수준입니다. 최대 응력: ${H(m.worstStress.val.toFixed(1)+' MPa')} (${H(m.worstStress.angle)} 방향).`
        : `The safety factor is ${W(m.sf.toFixed(2))}. The part should survive nominal loading, but the margin is moderate. Peak stress is ${H(m.worstStress.val.toFixed(1)+' MPa')} from ${H(m.worstStress.angle)}.`);
    } else if (m.sf < 2.0) {
      sentences.push(ko
        ? `안전계수가 ${G(m.sf.toFixed(2))}로 충분한 여유가 있습니다. 최대 응력 ${m.worstStress.val.toFixed(1)} MPa (${H(m.worstStress.angle)} 방향)로 항복응력 ${m.ys.toFixed(0)} MPa 대비 충분히 낮습니다.`
        : `The safety factor is ${G(m.sf.toFixed(2))}, indicating an adequate margin. Peak stress is ${m.worstStress.val.toFixed(1)} MPa from ${H(m.worstStress.angle)}, well below the yield stress of ${m.ys.toFixed(0)} MPa.`);
    } else {
      sentences.push(ko
        ? `안전계수가 ${G(m.sf.toFixed(2))}로 넉넉한 여유를 보입니다. 최대 응력이 ${m.worstStress.val.toFixed(1)} MPa(항복의 ${(100/m.sf).toFixed(0)}%)에 불과하여, 본 하중 조건에 대해 과설계일 수 있습니다.`
        : `The safety factor is ${G(m.sf.toFixed(2))}, providing a generous margin. Peak stress is only ${m.worstStress.val.toFixed(1)} MPa (${(100/m.sf).toFixed(0)}% of yield). This part may be over-designed for this load case.`);
    }
  }

  // 4. Worst direction identification
  const wc = m.worstStress.category;
  if (wc === 'face') {
    sentences.push(ko
      ? `최대 응력은 ${H('면(face)')} 충격(${H(m.worstStress.angle)})에서 발생하며, 평면 방향이 본 부품의 주요 하중 경로임을 나타냅니다.`
      : `The highest stress comes from a ${H('face')} impact (${H(m.worstStress.angle)}), suggesting the flat face is the primary load path for this part.`);
  } else if (wc === 'edge') {
    sentences.push(ko
      ? `최대 응력은 ${H('모서리(edge)')} 충격(${H(m.worstStress.angle)})에서 발생합니다. 접촉면적이 줄어드는 모서리 방향 하중에 취약합니다.`
      : `The highest stress comes from an ${H('edge')} impact (${H(m.worstStress.angle)}), indicating the part is vulnerable to edge-on loading where contact area is reduced.`);
  } else if (wc === 'corner') {
    sentences.push(ko
      ? `최대 응력은 ${H('꼭짓점(corner)')} 충격(${H(m.worstStress.angle)})에서 발생합니다. 꼭짓점에서의 집중 하중이 가장 위험한 하중 조건입니다.`
      : `The highest stress comes from a ${H('corner')} impact (${H(m.worstStress.angle)}), meaning concentrated point loads at corners are the critical load case.`);
  } else {
    sentences.push(ko
      ? `최대 응력 ${H(m.worstStress.val.toFixed(1)+' MPa')}가 ${H(m.worstStress.angle)} 방향 하중에서 발생합니다.`
      : `The highest stress of ${H(m.worstStress.val.toFixed(1)+' MPa')} occurs under ${H(m.worstStress.angle)} loading.`);
  }

  // 5. Directional sensitivity
  if (m.catRanking.length >= 2) {
    const top = m.catRanking[0], bot = m.catRanking[m.catRanking.length-1];
    const ratio = top.maxStress / (bot.maxStress || 1);
    if (ratio > 2.0) {
      sentences.push(ko
        ? `${B('강한 방향 민감도')}가 관찰됩니다: ${H(top.cat)} 충격이 ${H(bot.cat)} 충격 대비 ${ratio.toFixed(1)}배 높은 응력을 유발합니다. 충격 방향에 대한 의존도가 매우 높습니다.`
        : `There is a ${B('strong directional sensitivity')}: ${H(top.cat)} impacts produce ${ratio.toFixed(1)}x higher stress than ${H(bot.cat)} impacts. This part is highly orientation-dependent.`);
    } else if (ratio > 1.3) {
      sentences.push(ko
        ? `보통 수준의 방향 민감도가 관찰됩니다: ${H(top.cat)} 충격이 ${H(bot.cat)} 충격 대비 ${ratio.toFixed(1)}배 더 심각합니다.`
        : `Moderate directional sensitivity is observed: ${H(top.cat)} impacts are ${ratio.toFixed(1)}x more severe than ${H(bot.cat)} impacts.`);
    } else {
      sentences.push(ko
        ? `본 부품은 ${G('낮은 방향 민감도')}를 보입니다 — 모든 충격 카테고리에서 응력 수준이 비교적 균일합니다 (${top.cat}: ${top.maxStress.toFixed(1)} MPa vs ${bot.cat}: ${bot.maxStress.toFixed(1)} MPa).`
        : `The part shows ${G('low directional sensitivity')} -- stress levels are relatively uniform across all impact categories (${top.cat}: ${top.maxStress.toFixed(1)} MPa vs ${bot.cat}: ${bot.maxStress.toFixed(1)} MPa).`);
    }
  }

  // 6. Axis dominance
  if (m.accCount > 0) {
    const {x,y,z} = m.axisFracs;
    const axLabelsKo = {lateral:'횡방향',vertical:'수직방향',longitudinal:'종방향'};
    const axes = [{axis:'X',frac:x,label:'lateral'},{axis:'Y',frac:y,label:'vertical'},{axis:'Z',frac:z,label:'longitudinal'}].sort((a,b)=>b.frac-a.frac);
    const dom = axes[0];
    const domLbl = ko ? axLabelsKo[dom.label] : dom.label;
    if (dom.frac > 0.5) {
      sentences.push(ko
        ? `가속도가 ${H(dom.axis+'축')} (${(dom.frac*100).toFixed(0)}%)에 강하게 집중되어 있으며, ${H(domLbl)} 충격에 대한 민감도가 높습니다. 본 부품은 주로 ${domLbl} 방향 충격을 흡수합니다.`
        : `Acceleration is strongly dominated by the ${H(dom.axis+'-axis')} (${(dom.frac*100).toFixed(0)}%), indicating ${H(dom.label)} shock sensitivity. The part primarily absorbs ${dom.label} impacts.`);
    } else if (dom.frac > 0.38) {
      sentences.push(ko
        ? `${H(dom.axis+'축')}이 가장 큰 가속도를 담당(${(dom.frac*100).toFixed(0)}%)하며, ${axes[1].axis}축(${(axes[1].frac*100).toFixed(0)}%)이 그 다음입니다. ${domLbl} 중심의 2축 하중 상태입니다.`
        : `The ${H(dom.axis+'-axis')} carries the most acceleration (${(dom.frac*100).toFixed(0)}%), followed by ${axes[1].axis} (${(axes[1].frac*100).toFixed(0)}%). Loading is biaxial with ${dom.label} emphasis.`);
    } else {
      sentences.push(ko
        ? `가속도가 세 축에 ${G('균등하게 분포')}합니다 (X:${(x*100).toFixed(0)}%, Y:${(y*100).toFixed(0)}%, Z:${(z*100).toFixed(0)}%). 특정 축 우세 없이 다방향 하중에 반응합니다.`
        : `Acceleration is ${G('evenly distributed')} across all three axes (X:${(x*100).toFixed(0)}%, Y:${(y*100).toFixed(0)}%, Z:${(z*100).toFixed(0)}%), suggesting the part responds to multi-directional loading without a dominant axis.`);
    }
  }

  // 7. Stress variability
  if (m.cov > 0.5) {
    sentences.push(ko
      ? `방향별 응력 응답이 ${B('매우 불균일')}합니다 (변동계수 CoV = ${(m.cov*100).toFixed(0)}%). 범위: ${m.stressRange.min.toFixed(1)} ~ ${m.stressRange.max.toFixed(1)} MPa. 충격 방향에 매우 민감한 부품입니다.`
      : `Stress response is ${B('highly variable')} across directions (CoV = ${(m.cov*100).toFixed(0)}%). Range: ${m.stressRange.min.toFixed(1)} to ${m.stressRange.max.toFixed(1)} MPa. This part is very sensitive to impact orientation.`);
  } else if (m.cov > 0.25) {
    sentences.push(ko
      ? `응력 변동성이 보통 수준입니다 (CoV = ${(m.cov*100).toFixed(0)}%). 충격 각도에 따라 ${m.stressRange.min.toFixed(1)} ~ ${m.stressRange.max.toFixed(1)} MPa 범위를 보입니다.`
      : `Stress variability is moderate (CoV = ${(m.cov*100).toFixed(0)}%). The part sees a range of ${m.stressRange.min.toFixed(1)} to ${m.stressRange.max.toFixed(1)} MPa depending on impact angle.`);
  } else {
    sentences.push(ko
      ? `응력 응답이 충격 방향에 관계없이 ${G('일관적')}입니다 (CoV = ${(m.cov*100).toFixed(0)}%, 범위: ${m.stressRange.min.toFixed(1)} ~ ${m.stressRange.max.toFixed(1)} MPa). 방향에 따른 변화가 적은 부품입니다.`
      : `Stress response is ${G('consistent')} across impact directions (CoV = ${(m.cov*100).toFixed(0)}%, range: ${m.stressRange.min.toFixed(1)} - ${m.stressRange.max.toFixed(1)} MPa). The part responds uniformly regardless of orientation.`);
  }

  // 8. Plastic strain
  if (m.worstStrain.val > 0.01) {
    sentences.push(ko
      ? `${H(m.worstStrain.angle)} 방향 하중에서 ${B('상당한 소성 변형률')} (${m.worstStrain.val.toFixed(4)})이 관찰되었습니다. 영구 변형이 예상됩니다. 재료의 파단 연신율과 비교하여 파괴 위험을 평가하세요.`
      : `${B('Significant plastic strain')} (${m.worstStrain.val.toFixed(4)}) was observed under ${H(m.worstStrain.angle)} loading. Permanent deformation is expected. Compare with the material's elongation at break to assess fracture risk.`);
  } else if (m.worstStrain.val > 0.001) {
    sentences.push(ko
      ? `${H(m.worstStrain.angle)} 방향에서 보통 수준의 소성 변형률(${m.worstStrain.val.toFixed(4)})이 감지되었습니다. 경미한 영구 변형 가능성이 있습니다.`
      : `Moderate plastic strain (${m.worstStrain.val.toFixed(4)}) was detected from ${H(m.worstStrain.angle)}. Minor permanent deformation is possible.`);
  } else if (m.worstStrain.val > 0) {
    sentences.push(ko
      ? `미소한 소성 변형률(${m.worstStrain.val.toFixed(4)})이 관찰되었습니다. 사실상 탄성 범위 내 거동입니다.`
      : `Minimal plastic strain (${m.worstStrain.val.toFixed(4)}) was observed. Deformation is essentially elastic for this part.`);
  } else {
    sentences.push(ko
      ? `모든 방향에서 ${G('소성 변형률이 0')}입니다. 본 부품은 모든 시험 하중 조건에서 완전 탄성 상태를 유지합니다.`
      : `${G('No plastic strain')} was detected in any direction. The part remains fully elastic under all tested loading conditions.`);
  }

  // 9. Time domain
  if (m.timeDomainFeatures.length > 0) {
    const avgTP = m.avgTimeToPeak * 1000;
    const avgNP = m.avgNumPeaks;
    if (avgNP > 3) {
      sentences.push(ko
        ? `가속도 파형에서 평균 ${H(avgNP.toFixed(1)+'개 피크')}가 관찰되어 다중 충격/리바운드 사이클이 발생합니다. 최대값 도달 시간은 약 ${H(avgTP.toFixed(3)+' ms')}입니다. 충격 시 부품이 반복적으로 튀거나 공진하는 거동을 보입니다.`
        : `The G-force waveform typically shows ${H(avgNP.toFixed(1)+' peaks')}, indicating multiple impact/rebound cycles. Time to peak is approximately ${H(avgTP.toFixed(3)+' ms')}. This oscillatory behavior suggests the part bounces or resonates during impact.`);
    } else if (avgNP > 1.5) {
      sentences.push(ko
        ? `충격 응답에서 평균 ${avgNP.toFixed(1)}개 피크가 관찰되며, 1차 충격 후 1회 이상의 리바운드가 발생합니다. 평균 최대값 도달 시간: ${avgTP.toFixed(3)} ms.`
        : `The impact response shows an average of ${avgNP.toFixed(1)} peaks, suggesting a primary impact followed by one or more rebounds. Average time to peak: ${avgTP.toFixed(3)} ms.`);
    } else {
      sentences.push(ko
        ? `충격 응답이 ${G('단일 깨끗한 펄스')} 형태이며, 최대값 도달 시간은 ${avgTP.toFixed(3)} ms입니다. 유의미한 리바운드는 관찰되지 않습니다.`
        : `The impact response is a ${G('single clean pulse')} with time to peak of ${avgTP.toFixed(3)} ms. No significant rebounds are observed.`);
    }
  }

  // 10. Group comparison
  if (m.siblingMetrics.length > 0) {
    const selfRank = m.siblingMetrics.filter(s => s.maxStress > m.worstStress.val).length + 1;
    const groupTotal = m.siblingMetrics.length + 1;
    if (selfRank === 1) {
      sentences.push(ko
        ? `${H(m.group)} 그룹(${groupTotal}개 부품) 내에서 본 부품이 ${B('최대 응력 1위')}이며, 그룹 내 가장 위험한 부품입니다.`
        : `Within the ${H(m.group)} group (${groupTotal} parts), this part has the ${B('highest peak stress')}, making it the most critical component in its group.`);
    } else if (selfRank <= Math.ceil(groupTotal*0.25)) {
      sentences.push(ko
        ? `${H(m.group)} 그룹(${groupTotal}개 부품) 내에서 최대 응력 ${W('#'+selfRank+'위')}입니다.`
        : `Within the ${H(m.group)} group (${groupTotal} parts), this part ranks ${W('#'+selfRank)} in peak stress.`);
    } else {
      sentences.push(ko
        ? `${H(m.group)} 그룹(${groupTotal}개 부품) 내에서 최대 응력 ${G('#'+selfRank+'위')}로, 그룹 내 가장 높은 하중을 받는 부품은 아닙니다.`
        : `Within the ${H(m.group)} group (${groupTotal} parts), this part ranks ${G('#'+selfRank)} -- it is not the most stressed member of its group.`);
    }
  }

  // 11. Displacement
  if (m.worstDisp.val > 5.0) {
    sentences.push(ko
      ? `최대 변위가 ${W(m.worstDisp.val.toFixed(2)+' mm')}입니다 (${H(m.worstDisp.angle)} 방향). 큰 이동량이므로 인접 부품과의 클리어런스를 확인하여 간섭을 방지하세요.`
      : `Peak displacement is ${W(m.worstDisp.val.toFixed(2)+' mm')} (from ${H(m.worstDisp.angle)}). This is a large movement -- verify clearances with adjacent parts to prevent interference.`);
  } else if (m.worstDisp.val > 1.0) {
    sentences.push(ko
      ? `최대 변위는 ${m.worstDisp.val.toFixed(2)} mm입니다 (${H(m.worstDisp.angle)} 방향).`
      : `Peak displacement is ${m.worstDisp.val.toFixed(2)} mm from ${H(m.worstDisp.angle)}.`);
  }

  let html = `<div class="dd-narrative"><div class="dd-heading">${L('engAssessment')}</div>`;
  for (const s of sentences) html += `<div class="dd-para">${s}</div>`;
  html += '</div>';
  return html;
}

function buildKPISection(m) {
  const sfColor = m.sf > 0 ? (m.sf < 1 ? 'var(--red)' : m.sf < 1.5 ? 'var(--yellow)' : 'var(--green)') : 'var(--dim)';
  return `<div class="dd-kpi-grid">
    <div class="dd-kpi"><div class="dd-kpi-val" style="color:${sfColor}">${m.sf > 0 ? m.sf.toFixed(2) : 'N/A'}</div>
      <div class="dd-kpi-lbl">${L('safetyFactor')}</div>
      <div class="dd-kpi-sub">${m.ys > 0 ? m.ys.toFixed(0)+' / '+m.worstStress.val.toFixed(1)+' MPa' : L('setYieldStress')}</div></div>
    <div class="dd-kpi"><div class="dd-kpi-val" style="color:var(--red)">${m.worstStress.val.toFixed(1)}</div>
      <div class="dd-kpi-lbl">${L('peakStress')}</div><div class="dd-kpi-sub">${m.worstStress.angle}</div></div>
    <div class="dd-kpi"><div class="dd-kpi-val" style="color:var(--orange)">${(m.worstG.val/1e6).toFixed(2)}</div>
      <div class="dd-kpi-lbl">${L('peakG')}</div><div class="dd-kpi-sub">${m.worstG.angle}</div></div>
    <div class="dd-kpi"><div class="dd-kpi-val">${m.worstStrain.val.toFixed(4)}</div>
      <div class="dd-kpi-lbl">${L('peakStrain')}</div><div class="dd-kpi-sub">${m.worstStrain.angle}</div></div>
    <div class="dd-kpi"><div class="dd-kpi-val">${m.worstVel.val.toFixed(1)}</div>
      <div class="dd-kpi-lbl">${L('peakVel')}</div><div class="dd-kpi-sub">${m.worstVel.angle}</div></div>
    <div class="dd-kpi"><div class="dd-kpi-val">${m.worstDisp.val.toFixed(2)}</div>
      <div class="dd-kpi-lbl">${L('peakDisp')}</div><div class="dd-kpi-sub">${m.worstDisp.angle}</div></div>
    <div class="dd-kpi"><div class="dd-kpi-val">#${m.globalRank}/${m.totalParts}</div>
      <div class="dd-kpi-lbl">${L('globalRank')}</div></div>
    <div class="dd-kpi"><div class="dd-kpi-val">${(m.cov*100).toFixed(0)}%</div>
      <div class="dd-kpi-lbl">${L('stressCoV')}</div><div class="dd-kpi-sub">${reportLang==='ko'?'평균':'mean'} ${m.meanStress.toFixed(1)} ± ${m.stdStress.toFixed(1)}</div></div>
  </div>`;
}

function buildStressEnvelopeSVG(m) {
  if (m.perAngle.length === 0) return '';
  const sorted = [...m.perAngle].sort((a,b) => b.stress - a.stress);
  const W = 700, H_ = 220, ml = 60, mr = 40, mt = 15, mb = 10;
  const pw = W - ml - mr, ph = H_ - mt - mb;
  const barW = Math.max(3, Math.min(12, pw / sorted.length - 1));
  const smax = m.stressRange.max * 1.1 || 1;
  let svg = `<svg width="${W}" height="${H_}" viewBox="0 0 ${W} ${H_}">`;
  svg += `<rect x="${ml}" y="${mt}" width="${pw}" height="${ph}" fill="var(--bg3)" rx="2"/>`;
  // mean ± std band
  const hiY = mt + ph - (Math.min(m.meanStress+m.stdStress, smax)/smax)*ph;
  const loY = mt + ph - (Math.max(m.meanStress-m.stdStress, 0)/smax)*ph;
  svg += `<rect x="${ml}" y="${hiY}" width="${pw}" height="${Math.max(0,loY-hiY)}" fill="var(--cyan)" opacity="0.06"/>`;
  const meanY = mt + ph - (m.meanStress/smax)*ph;
  svg += `<line x1="${ml}" y1="${meanY}" x2="${ml+pw}" y2="${meanY}" stroke="var(--cyan)" stroke-width="1" stroke-dasharray="4,3"/>`;
  svg += `<text x="${ml+pw+4}" y="${meanY+3}" fill="var(--cyan)" font-size="9">mean</text>`;
  if (m.ys > 0 && m.ys <= smax) {
    const yY = mt + ph - (m.ys/smax)*ph;
    svg += `<line x1="${ml}" y1="${yY}" x2="${ml+pw}" y2="${yY}" stroke="var(--red)" stroke-width="1" stroke-dasharray="6,3"/>`;
    svg += `<text x="${ml+pw+4}" y="${yY+3}" fill="var(--red)" font-size="9">yield</text>`;
  }
  sorted.forEach((d, i) => {
    const x = ml + i*(barW+1);
    const h = (d.stress/smax)*ph;
    const y = mt + ph - h;
    const norm = m.stressRange.max > m.stressRange.min ? (d.stress-m.stressRange.min)/(m.stressRange.max-m.stressRange.min) : 0;
    const color = valueToColor(norm);
    svg += `<rect x="${x}" y="${y}" width="${barW}" height="${h}" fill="${color}" rx="1"><title>${d.angleName}: ${d.stress.toFixed(1)} MPa</title></rect>`;
  });
  for (let i=0; i<=4; i++) {
    const v = (i/4)*smax, y = mt + ph - (i/4)*ph;
    svg += `<text x="${ml-4}" y="${y+3}" text-anchor="end" fill="#7982a9" font-size="9">${v.toFixed(0)}</text>`;
  }
  svg += `<text x="10" y="${mt+ph/2}" text-anchor="middle" fill="#7982a9" font-size="9" transform="rotate(-90,10,${mt+ph/2})">Stress (MPa)</text>`;
  svg += '</svg>';
  return `<div class="dd-section"><div class="dd-section-title">${L('stressEnvTitle')}</div>
    <div style="overflow-x:auto">${svg}</div>
    <div style="font-size:10px;color:var(--dim);margin-top:4px">${L('stressEnvLegend')}${m.ys > 0 ? ' | ' + L('yieldLine') : ''}</div></div>`;
}

function buildDirectionVulnerability(m) {
  if (m.catRanking.length === 0) return '';
  const catMax = m.catRanking[0].maxStress || 1;
  const catColors = { face:'#f7768e', edge:'#e0af68', corner:'#9ece6a', fibonacci:'#7dcfff', other:'#bb9af7' };
  let html = '';
  for (const c of m.catRanking) {
    const pct = (c.maxStress/catMax*100).toFixed(1);
    const avgPct = (c.avgStress/catMax*100).toFixed(1);
    const color = catColors[c.cat] || catColors.other;
    html += `<div style="margin-bottom:8px">
      <div style="color:var(--fg2);font-size:11px;margin-bottom:2px">${c.cat} (${c.count} angles) — max: ${c.maxStress.toFixed(1)} MPa, avg: ${c.avgStress.toFixed(1)} MPa</div>
      <div class="dd-bar-track"><div class="dd-bar" style="width:${pct}%;background:${color};opacity:0.8"></div></div>
      <div class="dd-bar-track" style="margin-top:2px"><div class="dd-bar" style="width:${avgPct}%;background:${color};opacity:0.4"></div></div></div>`;
  }
  return `<div class="dd-section"><div class="dd-section-title">${L('dirVulnTitle')}</div>${html}
    <div style="font-size:10px;color:var(--dim);margin-top:4px">${L('dirVulnLegend')}</div></div>`;
}

function buildLoadPathSection(m) {
  if (m.accCount === 0) return '';
  const {x,y,z} = m.axisFracs;
  return `<div class="dd-section"><div class="dd-section-title">${L('loadPathTitle')}</div>
    <div style="display:grid;grid-template-columns:40px 1fr 60px;gap:4px;align-items:center;max-width:400px">
      <div style="color:#f7768e;font-weight:bold">X</div>
      <div class="dd-bar-track"><div class="dd-bar" style="width:${(x*100).toFixed(1)}%;background:#f7768e"></div></div>
      <div style="color:var(--fg2);font-size:11px">${(x*100).toFixed(1)}%</div>
      <div style="color:#9ece6a;font-weight:bold">Y</div>
      <div class="dd-bar-track"><div class="dd-bar" style="width:${(y*100).toFixed(1)}%;background:#9ece6a"></div></div>
      <div style="color:var(--fg2);font-size:11px">${(y*100).toFixed(1)}%</div>
      <div style="color:#7aa2f7;font-weight:bold">Z</div>
      <div class="dd-bar-track"><div class="dd-bar" style="width:${(z*100).toFixed(1)}%;background:#7aa2f7"></div></div>
      <div style="color:var(--fg2);font-size:11px">${(z*100).toFixed(1)}%</div>
    </div>
    <div style="color:var(--dim);font-size:10px;margin-top:6px">${L('loadPathDesc')}</div></div>`;
}

function buildGroupComparison(m) {
  if (m.siblingMetrics.length === 0) return '';
  const allParts = [{pid:m.pid, name:m.partInfo.name, maxStress:m.worstStress.val, maxG:m.worstG.val, maxStrain:m.worstStrain.val, isSelf:true},
    ...m.siblingMetrics.map(s => ({...s, isSelf:false}))].sort((a,b) => b.maxStress - a.maxStress);
  const groupMax = allParts[0].maxStress || 1;
  let html = '<div class="dd-group-compare">';
  for (const p of allParts) {
    const pct = (p.maxStress/groupMax*100).toFixed(1);
    html += `<div class="dd-group-card ${p.isSelf?'dd-self':''}">
      <div style="color:${p.isSelf?'var(--cyan)':'var(--fg2)'};font-size:12px;font-weight:${p.isSelf?'bold':'normal'};margin-bottom:4px">
        ${p.name.split('\\\\').pop()} ${p.isSelf?L('thisPart'):''}</div>
      <div class="dd-bar-track"><div class="dd-bar" style="width:${pct}%;background:${p.isSelf?'var(--cyan)':'var(--dim)'}"></div></div>
      <div style="font-size:10px;color:var(--fg2);margin-top:4px">
        Stress: ${p.maxStress.toFixed(1)} MPa | G: ${(p.maxG/1e6).toFixed(2)} MG | Strain: ${p.maxStrain.toFixed(4)}</div></div>`;
  }
  html += '</div>';
  return `<div class="dd-section"><div class="dd-section-title">${L('groupCompTitle')}: ${m.group} (${allParts.length}${reportLang==='ko'?'개 부품':' parts'})</div>${html}</div>`;
}

function buildTimeDomainAnalysis(m) {
  if (m.timeDomainFeatures.length === 0) return '';
  const sorted = [...m.timeDomainFeatures].sort((a,b) => b.numPeaks - a.numPeaks);
  let rows = '';
  for (const f of sorted.slice(0, 15)) {
    const badge = f.numPeaks >= 4 ? 'hotspot-badge' : f.numPeaks >= 2 ? 'hotspot-badge warn' : 'hotspot-badge ok';
    rows += `<tr><td style="color:var(--cyan)">${f.angleName}</td><td>${f.category}</td>
      <td style="text-align:right">${(f.timeToPeak*1000).toFixed(3)} ms</td>
      <td style="text-align:center"><span class="${badge}">${f.numPeaks}</span></td></tr>`;
  }
  return `<div class="dd-section"><div class="dd-section-title">${L('timeDomTitle')}</div>
    <div class="stat-grid" style="margin-bottom:12px">
      <div class="stat-card"><div class="value">${(m.avgTimeToPeak*1000).toFixed(3)}</div><div class="label">${L('avgTimeToPeak')}</div></div>
      <div class="stat-card"><div class="value">${m.avgNumPeaks.toFixed(1)}</div><div class="label">${L('avgNumPeaks')}</div></div></div>
    <div class="table-wrap" style="max-height:300px;overflow-y:auto">
    <table><tr><th>${L('direction')}</th><th>${L('category')}</th><th>${L('timeToPeak')}</th><th>${L('numPeaks')}</th></tr>${rows}</table></div></div>`;
}

function renderPartDeepDive() {
  const container = document.getElementById('deepdive-content');
  if (!container) return;
  const parts = getAllPartIds();
  if (deepDiveState.partId === 0 && parts.length > 0) deepDiveState.partId = parts[0];

  let html = `<div class="controls"><label>${L('selectPart')}</label>
    <select id="dd-part" onchange="deepDiveState.partId=parseInt(this.value);renderPartDeepDive()">`;
  for (const pid of parts) {
    const p = DATA.parts[String(pid)];
    html += `<option value="${pid}"${pid===deepDiveState.partId?' selected':''}>${p?p.name:''} (ID:${pid})</option>`;
  }
  html += '</select></div>';

  const m = computePartDeepDive(deepDiveState.partId);
  html += `<div class="panel"><h2>${m.partInfo.name} — ${L('partDeepDive')}</h2>${buildKPISection(m)}</div>`;
  html += `<div class="panel">${buildNarrative(m)}</div>`;
  html += `<div class="panel">${buildStressEnvelopeSVG(m)}</div>`;
  html += `<div class="panel">${buildDirectionVulnerability(m)}</div>`;
  html += `<div class="panel">${buildLoadPathSection(m)}</div>`;
  html += `<div class="panel">${buildGroupComparison(m)}</div>`;
  html += `<div class="panel">${buildTimeDomainAnalysis(m)}</div>`;
  container.innerHTML = html;
}

// ============ Tab 10: Advanced Analysis ============
let advState = { partId: 0 };

function computePulseMetrics(gvals, times) {
  // Find primary pulse: region above 10% of peak
  const absMax = Math.max(...gvals.map(Math.abs));
  if (absMax === 0) return null;
  const thresh = absMax * 0.1;
  let startIdx = -1, endIdx = -1, peakIdx = 0;
  for (let i = 0; i < gvals.length; i++) {
    if (Math.abs(gvals[i]) >= thresh && startIdx < 0) startIdx = i;
    if (Math.abs(gvals[i]) >= thresh) endIdx = i;
    if (Math.abs(gvals[i]) > Math.abs(gvals[peakIdx])) peakIdx = i;
  }
  if (startIdx < 0) return null;
  const pulseStart = times[startIdx], pulseEnd = times[endIdx];
  const pulseWidth = (pulseEnd - pulseStart) * 1000; // ms
  const peakAcc = absMax / 1e6; // MG
  // Impulse: trapezoidal integration of |g(t)| in the pulse window (MG·ms)
  let impulse = 0;
  for (let i = startIdx; i < endIdx && i+1 < times.length; i++) {
    const dt = (times[i+1] - times[i]) * 1000;
    impulse += (Math.abs(gvals[i]) + Math.abs(gvals[i+1])) / 2 / 1e6 * dt;
  }
  // Half-sine equivalent: same impulse => A_hs * T_hs * 2/pi = impulse
  // For same peak: T_hs = pi * impulse / (2 * peakAcc)
  const hsDuration = peakAcc > 0 ? Math.PI * impulse / (2 * peakAcc) : 0;
  const hsPeak = hsDuration > 0 ? Math.PI * impulse / (2 * hsDuration) : 0;
  return { pulseWidth, peakAcc, impulse, hsDuration, hsPeak, startIdx, endIdx, peakIdx, times, gvals };
}

function buildImpactPulseSection(pid) {
  const pidStr = String(pid);
  const ko = reportLang === 'ko';
  const pulseData = [];
  for (const r of DATA.results) {
    const pd = r.parts[pidStr];
    if (!pd || !pd.g_ts || !pd.g_ts.g) continue;
    const m = computePulseMetrics(pd.g_ts.g, pd.g_ts.t);
    if (m) pulseData.push({ name: r.angle.name, cat: r.angle.category || 'other', ...m });
  }
  if (pulseData.length === 0) return '';
  pulseData.sort((a,b) => b.peakAcc - a.peakAcc);
  // Summary stats
  const avgPW = pulseData.reduce((s,d) => s+d.pulseWidth, 0) / pulseData.length;
  const avgPeak = pulseData.reduce((s,d) => s+d.peakAcc, 0) / pulseData.length;
  const avgImp = pulseData.reduce((s,d) => s+d.impulse, 0) / pulseData.length;
  const maxPW = Math.max(...pulseData.map(d => d.pulseWidth));
  const maxPeak = Math.max(...pulseData.map(d => d.peakAcc));
  const maxImp = Math.max(...pulseData.map(d => d.impulse));

  // KPI cards
  let html = `<div class="dd-section"><div class="dd-section-title">${L('ipTitle')} <sup style="color:var(--cyan);font-size:9px">[1][2]</sup></div>
    <div style="color:var(--fg2);font-size:12px;margin-bottom:8px">${L('ipDesc')}</div>
    <details style="margin-bottom:12px"><summary style="cursor:pointer;color:var(--cyan);font-size:11px;font-weight:bold">${ko?'▸ 각 지표의 물리적 의미 및 평가 기준':'▸ Physical meaning & evaluation criteria'}</summary>
      <div style="padding:8px 12px;margin-top:4px;background:var(--bg);border-radius:4px;border-left:3px solid var(--cyan);font-size:11px;color:var(--fg2);line-height:1.7">${L('ipGuide')}</div></details>
    <div class="stat-grid" style="margin-bottom:12px">
      <div class="stat-card"><div class="value">${avgPW.toFixed(3)}</div><div class="label">${ko?'평균 펄스폭':'Avg Pulse Width'} (ms)</div></div>
      <div class="stat-card"><div class="value">${avgPeak.toFixed(3)}</div><div class="label">${ko?'평균 피크':'Avg Peak'} (MG)</div></div>
      <div class="stat-card"><div class="value">${avgImp.toFixed(3)}</div><div class="label">${ko?'평균 임펄스':'Avg Impulse'} (MG·ms)</div></div>
      <div class="stat-card"><div class="value">${maxPeak.toFixed(3)}</div><div class="label">${ko?'최대 피크':'Max Peak'} (MG)</div></div>
    </div>`;
  // Auto-interpretation
  const ipNarr = [];
  if (ko) {
    ipNarr.push(`평균 펄스폭 <b>${avgPW.toFixed(3)} ms</b>${avgPW < 1 ? ' — 고주파 충격으로, 작고 단단한 부품에 가혹합니다' : avgPW < 5 ? ' — 일반적인 낙하 충격 범위입니다' : ' — 저주파 충격으로, 구조 전체에 하중이 전달됩니다'}.`);
    ipNarr.push(`최대 피크 가속도 <b>${maxPeak.toFixed(3)} MG</b> (방향: ${pulseData[0].name}). ${maxPeak > 1 ? '소형 전자부품의 일반적 내충격 사양을 초과할 수 있습니다.' : '대부분의 부품 내충격 사양 이내입니다.'}`);
    const pwRange = Math.max(...pulseData.map(d=>d.pulseWidth)) / Math.min(...pulseData.map(d=>d.pulseWidth).filter(v=>v>0));
    if (pwRange > 3) ipNarr.push(`펄스폭이 방향에 따라 <b>${pwRange.toFixed(1)}배</b> 차이나므로, 충격 주파수 성분이 방향 의존적입니다. SRS 분석 시 방향별 별도 평가가 필요합니다.`);
  } else {
    ipNarr.push(`Average pulse width <b>${avgPW.toFixed(3)} ms</b>${avgPW < 1 ? ' — high-frequency shock, harsh on small rigid components' : avgPW < 5 ? ' — typical drop impact range' : ' — low-frequency shock, load transfers through entire structure'}.`);
    ipNarr.push(`Max peak acceleration <b>${maxPeak.toFixed(3)} MG</b> (direction: ${pulseData[0].name}). ${maxPeak > 1 ? 'May exceed typical shock ratings for small electronic components.' : 'Within typical component shock specifications.'}`);
    const pwRange = Math.max(...pulseData.map(d=>d.pulseWidth)) / Math.min(...pulseData.map(d=>d.pulseWidth).filter(v=>v>0));
    if (pwRange > 3) ipNarr.push(`Pulse width varies <b>${pwRange.toFixed(1)}×</b> across directions — frequency content is direction-dependent. SRS analysis should be performed per direction.`);
  }
  html += `<div style="padding:8px;background:var(--bg3);border-radius:4px;border-left:3px solid #e0af68;margin-bottom:12px;font-size:11px;line-height:1.6;color:var(--fg)">${ipNarr.join('<br>')}</div>`;

  // SVG: Pulse envelope — top 10 worst directions superimposed
  const worst = pulseData.slice(0, 10);
  const SW = 600, SH = 260, ml = 55, mr = 120, mt = 20, mb = 35;
  const pw = SW - ml - mr, ph = SH - mt - mb;
  let tmin = Infinity, tmax = 0, gmax = 0;
  for (const d of worst) {
    if (d.times[d.startIdx] < tmin) tmin = d.times[d.startIdx];
    if (d.times[d.endIdx] > tmax) tmax = d.times[d.endIdx];
    if (d.peakAcc > gmax) gmax = d.peakAcc;
  }
  if (tmax <= tmin) tmax = tmin + 0.001;
  gmax *= 1.1;
  const tRange = tmax - tmin;
  const colors = ['#f7768e','#e0af68','#9ece6a','#7dcfff','#bb9af7','#ff9e64','#73daca','#7aa2f7','#c0caf5','#a9b1d6'];
  let svg = `<svg width="100%" viewBox="0 0 ${SW} ${SH}" style="max-width:${SW}px">
    <rect x="${ml}" y="${mt}" width="${pw}" height="${ph}" fill="var(--bg3)" rx="2"/>`;
  // Grid
  for (let i = 0; i <= 4; i++) {
    const y = mt + ph * i / 4, v = (gmax * (4-i) / 4).toFixed(3);
    svg += `<line x1="${ml}" y1="${y}" x2="${ml+pw}" y2="${y}" stroke="rgba(255,255,255,0.08)"/>`;
    svg += `<text x="${ml-4}" y="${y+4}" text-anchor="end" fill="#7982a9" font-size="9">${v}</text>`;
  }
  for (const d of worst) {
    const ci = worst.indexOf(d);
    let path = '';
    for (let i = d.startIdx; i <= d.endIdx && i < d.times.length; i++) {
      const x = ml + ((d.times[i] - tmin) / tRange) * pw;
      const y = mt + ph - (Math.abs(d.gvals[i]) / 1e6 / gmax) * ph;
      path += (i === d.startIdx ? 'M' : 'L') + `${x.toFixed(1)},${y.toFixed(1)}`;
    }
    svg += `<path d="${path}" fill="none" stroke="${colors[ci%colors.length]}" stroke-width="1.5" opacity="0.7"/>`;
  }
  // Legend
  let ly = mt;
  for (let i = 0; i < worst.length; i++) {
    svg += `<rect x="${ml+pw+8}" y="${ly}" width="10" height="10" fill="${colors[i%colors.length]}"/>`;
    svg += `<text x="${ml+pw+22}" y="${ly+9}" fill="var(--fg2)" font-size="8">${worst[i].name}</text>`;
    ly += 14;
  }
  svg += `<text x="${ml+pw/2}" y="${SH-2}" text-anchor="middle" fill="#7982a9" font-size="10">${ko?'시간 (s)':'Time (s)'}</text>`;
  svg += `<text x="10" y="${mt+ph/2}" text-anchor="middle" fill="#7982a9" font-size="10" transform="rotate(-90,10,${mt+ph/2})">${ko?'가속도 (MG)':'Acceleration (MG)'}</text>`;
  svg += '</svg>';
  html += `<div style="margin-bottom:12px;overflow-x:auto"><div style="font-size:11px;color:var(--fg2);margin-bottom:4px">${L('ipEnvelope')} — ${ko?'상위':'Top'} ${worst.length}${ko?'개 방향':' directions'}</div>${svg}</div>`;

  // Table
  let rows = '';
  for (const d of pulseData.slice(0, 20)) {
    rows += `<tr><td style="color:var(--cyan)">${d.name}</td><td>${d.cat}</td>
      <td style="text-align:right">${d.pulseWidth.toFixed(3)}</td>
      <td style="text-align:right">${d.peakAcc.toFixed(3)}</td>
      <td style="text-align:right">${d.impulse.toFixed(4)}</td>
      <td style="text-align:right">${d.hsDuration.toFixed(3)}</td>
      <td style="text-align:right">${d.hsPeak.toFixed(3)}</td></tr>`;
  }
  html += `<div class="table-wrap" style="max-height:350px;overflow-y:auto">
    <table><tr><th>${L('direction')}</th><th>${L('category')}</th><th>${L('ipPulseWidth')}</th><th>${L('ipPeakAcc')}</th><th>${L('ipImpulse')}</th><th>${L('ipHsDuration')}</th><th>${L('ipHsPeak')}</th></tr>${rows}</table></div></div>`;
  return html;
}

function buildCriticalElementSection(pid) {
  const pidStr = String(pid);
  const ko = reportLang === 'ko';
  // Track which elements appear at peak stress most often — cross-part scan
  const elemData = {}; // elemId -> { count, angles, maxStress, stresses, partId }
  const allPids = getAllPartIds();
  for (const r of DATA.results) {
    for (const cpid of allPids) {
      const pd = r.parts[String(cpid)];
      if (!pd || !pd.stress_ts || !pd.stress_ts.elem || !pd.stress_ts.max) continue;
      const svals = pd.stress_ts.max;
      const elems = pd.stress_ts.elem;
      if (svals.length === 0 || elems.length === 0) continue;
      let maxIdx = 0;
      for (let i = 1; i < svals.length; i++) { if (svals[i] > svals[maxIdx]) maxIdx = i; }
      const eid = elems[Math.min(maxIdx, elems.length-1)];
      if (eid === 0) continue;
      if (!elemData[eid]) elemData[eid] = { count: 0, angles: [], maxStress: 0, stresses: [], partId: cpid };
      elemData[eid].count++;
      elemData[eid].angles.push(r.angle.name);
      elemData[eid].stresses.push(svals[maxIdx]);
      if (svals[maxIdx] > elemData[eid].maxStress) {
        elemData[eid].maxStress = svals[maxIdx];
        elemData[eid].partId = cpid;
      }
    }
  }
  // Resolve part names
  for (const d of Object.values(elemData)) {
    const pi = DATA.parts[String(d.partId)];
    d.partName = pi ? pi.name : `Part ${d.partId}`;
  }
  const sorted = Object.entries(elemData)
    .map(([eid, d]) => ({ eid: Number(eid), ...d, avgStress: d.stresses.reduce((a,b)=>a+b,0)/d.stresses.length }))
    .sort((a,b) => b.count - a.count).slice(0, 15);
  if (sorted.length === 0) return '';
  const maxCount = sorted[0].count;

  let html = `<div class="dd-section"><div class="dd-section-title">${L('ceTitle')}</div>
    <div style="color:var(--fg2);font-size:12px;margin-bottom:8px">${L('ceDesc')}</div>
    <details style="margin-bottom:12px"><summary style="cursor:pointer;color:var(--cyan);font-size:11px;font-weight:bold">${ko?'▸ 각 지표의 물리적 의미 및 설계 지침':'▸ Physical meaning & design guidelines'}</summary>
      <div style="padding:8px 12px;margin-top:4px;background:var(--bg);border-radius:4px;border-left:3px solid var(--cyan);font-size:11px;color:var(--fg2);line-height:1.7">${L('ceGuide')}</div></details>`;

  // Histogram SVG
  const BW = 550, BH = 200, bml = 55, bmr = 10, bmt = 10, bmb = 50;
  const bpw = BW - bml - bmr, bph = BH - bmt - bmb;
  const barW = Math.max(8, Math.min(30, bpw / sorted.length - 4));
  let svg = `<svg width="100%" viewBox="0 0 ${BW} ${BH}" style="max-width:${BW}px">
    <rect x="${bml}" y="${bmt}" width="${bpw}" height="${bph}" fill="var(--bg3)" rx="2"/>`;
  for (let i = 0; i <= 4; i++) {
    const y = bmt + bph * i / 4, v = Math.round(maxCount * (4-i) / 4);
    svg += `<line x1="${bml}" y1="${y}" x2="${bml+bpw}" y2="${y}" stroke="rgba(255,255,255,0.08)"/>`;
    svg += `<text x="${bml-4}" y="${y+4}" text-anchor="end" fill="#7982a9" font-size="9">${v}</text>`;
  }
  sorted.forEach((d, i) => {
    const x = bml + (i + 0.5) * bpw / sorted.length - barW / 2;
    const h = (d.count / maxCount) * bph;
    const pct = d.count / maxCount;
    const col = pct > 0.7 ? '#f7768e' : pct > 0.4 ? '#e0af68' : '#9ece6a';
    svg += `<rect x="${x.toFixed(1)}" y="${(bmt+bph-h).toFixed(1)}" width="${barW}" height="${h.toFixed(1)}" fill="${col}" rx="2"><title>Elem ${d.eid} (${d.partName}): ${d.count}x, max ${d.maxStress.toFixed(1)} MPa</title></rect>`;
    svg += `<text x="${(x+barW/2).toFixed(1)}" y="${BH-bmb+12}" text-anchor="middle" fill="var(--fg2)" font-size="8" transform="rotate(-45,${(x+barW/2).toFixed(1)},${BH-bmb+12})">${d.eid}</text>`;
  });
  svg += `<text x="${bml+bpw/2}" y="${BH-2}" text-anchor="middle" fill="#7982a9" font-size="10">${L('ceElemId')}</text>`;
  svg += `<text x="10" y="${bmt+bph/2}" text-anchor="middle" fill="#7982a9" font-size="10" transform="rotate(-90,10,${bmt+bph/2})">${L('ceFrequency')}</text>`;
  svg += '</svg>';
  html += `<div style="overflow-x:auto;margin-bottom:12px">${svg}</div>`;

  // Table — with Part column
  let rows = '';
  for (const d of sorted) {
    const pct = d.count / maxCount;
    const badge = pct > 0.7 ? 'hotspot-badge' : pct > 0.4 ? 'hotspot-badge warn' : 'hotspot-badge ok';
    rows += `<tr><td><span class="${badge}">${d.eid}</span></td>
      <td style="color:var(--cyan)">${d.partName} <span style="color:var(--dim);font-size:10px">(${d.partId})</span></td>
      <td style="text-align:right">${d.count}</td>
      <td style="text-align:right">${d.angles.length}</td>
      <td style="text-align:right">${d.maxStress.toFixed(1)}</td>
      <td style="text-align:right">${d.avgStress.toFixed(1)}</td>
      <td style="color:var(--dim);font-size:11px">${d.angles.slice(0,5).join(', ')}${d.angles.length>5?'...':''}</td></tr>`;
  }
  html += `<div class="table-wrap" style="max-height:300px;overflow-y:auto">
    <table><tr><th>${L('ceElemId')}</th><th>${ko?'소속 부품':'Part'}</th><th>${L('ceFrequency')}</th><th>${L('ceAngles')}</th><th>${L('cePeakStress')}</th><th>${ko?'평균 응력':'Avg Stress'} (MPa)</th><th>${ko?'출현 방향':'Angles'}</th></tr>${rows}</table></div>`;
  // Auto-interpretation
  const ceNarr = [];
  const topElem = sorted[0];
  const topPct = (topElem.count / DATA.results.length * 100).toFixed(0);
  const nGeometric = sorted.filter(d => d.count / DATA.results.length > 0.5).length;
  // Count unique parts in top hotspots
  const hotspotParts = new Set(sorted.map(d => d.partId));
  if (ko) {
    ceNarr.push(`요소 <b>${topElem.eid}</b> (${topElem.partName})가 전체 ${DATA.results.length}개 방향 중 <b>${topElem.count}개(${topPct}%)</b>에서 최대 응력점으로 출현합니다.`);
    if (hotspotParts.size > 1) ceNarr.push(`상위 ${sorted.length}개 핫스팟 요소가 <b>${hotspotParts.size}개 부품</b>에 분산되어 있습니다 — 구조적 취약점이 여러 부품에 걸쳐 있습니다.`);
    else ceNarr.push(`상위 핫스팟 요소가 모두 <b>${topElem.partName}</b>에 집중되어 있어, 이 부품이 구조적 핵심 취약 부품입니다.`);
    if (nGeometric > 0) ceNarr.push(`<span style="color:#f7768e"><b>${nGeometric}개 요소</b></span>가 50% 이상의 방향에서 출현하여 <b>형상 기인 응력 집중</b>으로 판단됩니다. 방향과 무관하게 이 위치가 가장 먼저 파손될 가능성이 높습니다.`);
    else ceNarr.push('50% 이상의 방향에서 반복 출현하는 요소가 없어, 응력 집중이 <b>방향 의존적</b>입니다. 특정 충격 방향에서만 취약한 국부적 현상입니다.');
    if (topElem.maxStress / topElem.avgStress > 1.5) ceNarr.push(`요소 ${topElem.eid}의 최대/평균 응력비: <b>${(topElem.maxStress/topElem.avgStress).toFixed(1)}배</b> — 특정 방향에서 극단적 응력이 발생합니다.`);
  } else {
    ceNarr.push(`Element <b>${topElem.eid}</b> (${topElem.partName}) appears as peak-stress location in <b>${topElem.count}/${DATA.results.length} directions (${topPct}%)</b>.`);
    if (hotspotParts.size > 1) ceNarr.push(`Top ${sorted.length} hotspot elements span across <b>${hotspotParts.size} parts</b> — structural vulnerabilities are distributed across multiple components.`);
    else ceNarr.push(`All top hotspot elements are concentrated in <b>${topElem.partName}</b> — this is the critical structurally vulnerable component.`);
    if (nGeometric > 0) ceNarr.push(`<span style="color:#f7768e"><b>${nGeometric} element(s)</b></span> appear in >50% of directions — classified as <b>geometry-driven stress concentrations</b>. These locations are most likely to fail first regardless of impact direction.`);
    else ceNarr.push('No elements appear in >50% of directions — stress concentration is <b>direction-dependent</b>. Vulnerability is localized to specific impact orientations.');
    if (topElem.maxStress / topElem.avgStress > 1.5) ceNarr.push(`Element ${topElem.eid} max/avg stress ratio: <b>${(topElem.maxStress/topElem.avgStress).toFixed(1)}×</b> — extreme stress occurs only in specific directions.`);
  }
  html += `<div style="padding:8px;background:var(--bg3);border-radius:4px;border-left:3px solid #e0af68;margin-top:8px;font-size:11px;line-height:1.6;color:var(--fg)">${ceNarr.join('<br>')}</div></div>`;
  return html;
}

function buildEnergyAbsorptionSection(pid) {
  const pidStr = String(pid);
  const ko = reportLang === 'ko';
  // Estimate deformation energy: integrate stress * strain_rate dt ≈ Σ (stress_avg * Δstrain) over time
  // Simplified: use peak_stress * peak_strain as proxy for each angle
  const energyPerAngle = [];
  let totalEnergy = 0;
  for (const r of DATA.results) {
    const pd = r.parts[pidStr];
    if (!pd) continue;
    // Better estimate: if we have stress_ts and strain_ts, integrate
    let energy = 0;
    if (pd.stress_ts && pd.strain_ts && pd.stress_ts.avg && pd.strain_ts.max) {
      const st = pd.stress_ts, sn = pd.strain_ts;
      const n = Math.min(st.avg.length, sn.max.length);
      for (let i = 1; i < n; i++) {
        const ds = Math.max(0, sn.max[i] - sn.max[i-1]); // strain increment
        const avgS = (st.avg[i] + st.avg[i-1]) / 2;
        energy += avgS * ds; // MPa * unitless = MPa (energy density proxy)
      }
    } else {
      energy = pd.peak_stress * pd.peak_strain; // fallback proxy
    }
    energyPerAngle.push({ name: r.angle.name, cat: r.angle.category || 'other', energy });
    totalEnergy += energy;
  }
  if (energyPerAngle.length === 0 || totalEnergy === 0) return '';
  energyPerAngle.sort((a,b) => b.energy - a.energy);
  const maxE = energyPerAngle[0].energy;

  // Also compute per-part energy share (across all parts) for the worst angle
  const worstAngle = energyPerAngle[0];
  const partShares = [];
  let worstResult = null;
  for (const r of DATA.results) { if (r.angle.name === worstAngle.name) { worstResult = r; break; } }
  if (worstResult) {
    let totalPartEnergy = 0;
    for (const [p, pd] of Object.entries(worstResult.parts)) {
      let e = 0;
      if (pd.stress_ts && pd.strain_ts && pd.stress_ts.avg && pd.strain_ts.max) {
        const n = Math.min(pd.stress_ts.avg.length, pd.strain_ts.max.length);
        for (let i = 1; i < n; i++) {
          const ds = Math.max(0, pd.strain_ts.max[i] - pd.strain_ts.max[i-1]);
          e += (pd.stress_ts.avg[i] + pd.stress_ts.avg[i-1]) / 2 * ds;
        }
      } else { e = pd.peak_stress * pd.peak_strain; }
      if (e > 0) { partShares.push({ pid: p, name: (DATA.parts[p]||{}).name || 'Part '+p, energy: e }); totalPartEnergy += e; }
    }
    partShares.sort((a,b) => b.energy - a.energy);
    partShares.forEach(p => p.share = totalPartEnergy > 0 ? p.energy / totalPartEnergy : 0);
  }

  let html = `<div class="dd-section"><div class="dd-section-title">${L('eaTitle')}</div>
    <div style="color:var(--fg2);font-size:12px;margin-bottom:8px">${L('eaDesc')}</div>
    <details style="margin-bottom:12px"><summary style="cursor:pointer;color:var(--cyan);font-size:11px;font-weight:bold">${ko?'▸ 에너지 해석 방법 및 설계 관점':'▸ Energy analysis method & design perspective'}</summary>
      <div style="padding:8px 12px;margin-top:4px;background:var(--bg);border-radius:4px;border-left:3px solid var(--cyan);font-size:11px;color:var(--fg2);line-height:1.7">${L('eaGuide')}</div></details>`;

  // Energy bar chart: per angle
  const BW = 600, BH = 200, bml = 55, bmr = 10, bmt = 10, bmb = 50;
  const bpw = BW - bml - bmr, bph = BH - bmt - bmb;
  const top20 = energyPerAngle.slice(0, 20);
  const barW = Math.max(6, Math.min(25, bpw / top20.length - 3));
  const catCol = { face: '#f7768e', edge: '#e0af68', corner: '#9ece6a', fibonacci: '#7dcfff', other: '#bb9af7' };
  let svg = `<svg width="100%" viewBox="0 0 ${BW} ${BH}" style="max-width:${BW}px">
    <rect x="${bml}" y="${bmt}" width="${bpw}" height="${bph}" fill="var(--bg3)" rx="2"/>`;
  top20.forEach((d, i) => {
    const x = bml + (i + 0.5) * bpw / top20.length - barW / 2;
    const h = (d.energy / maxE) * bph;
    svg += `<rect x="${x.toFixed(1)}" y="${(bmt+bph-h).toFixed(1)}" width="${barW}" height="${h.toFixed(1)}" fill="${catCol[d.cat]||catCol.other}" rx="1" opacity="0.8"><title>${d.name}: ${d.energy.toFixed(2)}</title></rect>`;
    svg += `<text x="${(x+barW/2).toFixed(1)}" y="${BH-bmb+12}" text-anchor="middle" fill="var(--fg2)" font-size="7" transform="rotate(-55,${(x+barW/2).toFixed(1)},${BH-bmb+12})">${d.name.substring(0,12)}</text>`;
  });
  svg += `<text x="${bml+bpw/2}" y="${BH-2}" text-anchor="middle" fill="#7982a9" font-size="10">${L('direction')}</text>`;
  svg += `<text x="10" y="${bmt+bph/2}" text-anchor="middle" fill="#7982a9" font-size="10" transform="rotate(-90,10,${bmt+bph/2})">${L('eaDeformEnergy')}</text>`;
  svg += '</svg>';
  html += `<div style="overflow-x:auto;margin-bottom:12px"><div style="font-size:11px;color:var(--fg2);margin-bottom:4px">${L('eaDeformEnergy')} — ${ko?'상위':'Top'} ${top20.length}${ko?'개 방향':' directions'}</div>${svg}</div>`;

  // Part share pie-like horizontal bar
  if (partShares.length > 0) {
    html += `<div style="font-size:11px;color:var(--fg2);margin-bottom:4px">${L('eaPartShare')} (${ko?'최악 방향':'Worst direction'}: ${worstAngle.name})</div>`;
    html += '<div style="margin-bottom:12px">';
    for (const p of partShares.slice(0, 10)) {
      const w = Math.max(2, p.share * 100);
      const isSelf = p.pid === pidStr;
      html += `<div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
        <span style="width:100px;font-size:11px;color:${isSelf?'var(--cyan)':'var(--fg2)'};text-align:right;flex-shrink:0">${p.name.substring(0,15)}</span>
        <div style="flex:1;height:14px;background:var(--bg);border-radius:3px;position:relative">
          <div style="width:${w.toFixed(1)}%;height:100%;background:${isSelf?'var(--cyan)':'#7aa2f7'};border-radius:3px;opacity:0.7"></div>
        </div>
        <span style="font-size:10px;color:var(--dim);width:40px">${(p.share*100).toFixed(1)}%</span></div>`;
    }
    html += '</div>';
  }
  // Auto-interpretation
  const eaNarr = [];
  const eaCoV = energyPerAngle.length > 1 ? Math.sqrt(energyPerAngle.map(d => (d.energy - totalEnergy/energyPerAngle.length)**2).reduce((a,b)=>a+b,0)/energyPerAngle.length) / (totalEnergy/energyPerAngle.length) : 0;
  if (ko) {
    eaNarr.push(`에너지 흡수가 가장 큰 방향: <b>${energyPerAngle[0].name}</b> (${energyPerAngle[0].cat}). 이 방향에서 가장 많은 소성 변형이 발생합니다.`);
    if (eaCoV > 0.5) eaNarr.push(`방향 간 에너지 흡수 변동계수(CoV) <b>${(eaCoV*100).toFixed(0)}%</b> — 에너지 흐름 경로가 충격 방향에 <b>강하게 의존</b>합니다. 특정 방향에서 손상이 집중될 수 있습니다.`);
    else eaNarr.push(`방향 간 에너지 흡수 변동계수(CoV) <b>${(eaCoV*100).toFixed(0)}%</b> — 에너지 흡수가 비교적 <b>균일</b>하여 방향 독립적인 에너지 관리가 이루어지고 있습니다.`);
    if (partShares.length > 0 && partShares[0].share > 0.5) eaNarr.push(`최악 방향에서 <b>${partShares[0].name}</b>이 전체 변형 에너지의 <b>${(partShares[0].share*100).toFixed(0)}%</b>를 흡수합니다. 이 부품이 주요 충격 흡수체 또는 손상 집중 부위입니다.`);
  } else {
    eaNarr.push(`Highest energy absorption direction: <b>${energyPerAngle[0].name}</b> (${energyPerAngle[0].cat}). Maximum plastic deformation occurs from this direction.`);
    if (eaCoV > 0.5) eaNarr.push(`Energy absorption CoV across directions: <b>${(eaCoV*100).toFixed(0)}%</b> — energy flow path is <b>strongly direction-dependent</b>. Damage may concentrate in specific orientations.`);
    else eaNarr.push(`Energy absorption CoV across directions: <b>${(eaCoV*100).toFixed(0)}%</b> — energy absorption is relatively <b>uniform</b>, indicating direction-independent energy management.`);
    if (partShares.length > 0 && partShares[0].share > 0.5) eaNarr.push(`In worst direction, <b>${partShares[0].name}</b> absorbs <b>${(partShares[0].share*100).toFixed(0)}%</b> of total deformation energy — primary shock absorber or damage concentration site.`);
  }
  html += `<div style="padding:8px;background:var(--bg3);border-radius:4px;border-left:3px solid #e0af68;font-size:11px;line-height:1.6;color:var(--fg)">${eaNarr.join('<br>')}</div>`;
  html += '</div>';
  return html;
}

function buildReboundSection(pid) {
  const pidStr = String(pid);
  const ko = reportLang === 'ko';
  const rbData = [];
  for (const r of DATA.results) {
    const pd = r.parts[pidStr];
    if (!pd || !pd.g_ts || !pd.g_ts.g) continue;
    const gvals = pd.g_ts.g, times = pd.g_ts.t;
    const peaks = detectPeaks(gvals, 0.15, 3);
    if (peaks.length === 0) continue;
    const p1 = Math.abs(peaks[0].val);
    const p2 = peaks.length > 1 ? Math.abs(peaks[1].val) : 0;
    const ratio21 = p1 > 0 ? p2 / p1 : 0;
    // Decay rate: exponential fit over peaks
    let decayRate = 0;
    if (peaks.length >= 2) {
      const t1 = times[peaks[0].idx], tn = times[peaks[peaks.length-1].idx];
      const dt = tn - t1;
      if (dt > 0 && p1 > 0) {
        const pLast = Math.abs(peaks[peaks.length-1].val);
        decayRate = pLast > 0 ? -Math.log(pLast / p1) / (dt * 1000) : 0; // per ms
      }
    }
    rbData.push({
      name: r.angle.name, cat: r.angle.category || 'other',
      nBounces: peaks.length, ratio21, decayRate,
      p1: p1/1e6, p2: p2/1e6,
      peakTimes: peaks.map(p => times[p.idx] * 1000)
    });
  }
  if (rbData.length === 0) return '';
  rbData.sort((a,b) => b.nBounces - a.nBounces);

  const avgBounces = rbData.reduce((s,d) => s+d.nBounces, 0) / rbData.length;
  const avgRatio = rbData.filter(d=>d.ratio21>0).reduce((s,d) => s+d.ratio21, 0) / (rbData.filter(d=>d.ratio21>0).length || 1);
  const avgDecay = rbData.filter(d=>d.decayRate>0).reduce((s,d) => s+d.decayRate, 0) / (rbData.filter(d=>d.decayRate>0).length || 1);
  const multiBouncePct = rbData.filter(d => d.nBounces >= 2).length / rbData.length * 100;

  let html = `<div class="dd-section"><div class="dd-section-title">${L('rbTitle')} <sup style="color:var(--cyan);font-size:9px">[3]</sup></div>
    <div style="color:var(--fg2);font-size:12px;margin-bottom:8px">${L('rbDesc')}</div>
    <details style="margin-bottom:12px"><summary style="cursor:pointer;color:var(--cyan);font-size:11px;font-weight:bold">${ko?'▸ 리바운드 물리학 및 평가 기준':'▸ Rebound physics & evaluation criteria'}</summary>
      <div style="padding:8px 12px;margin-top:4px;background:var(--bg);border-radius:4px;border-left:3px solid var(--cyan);font-size:11px;color:var(--fg2);line-height:1.7">${L('rbGuide')}</div></details>
    <div class="stat-grid" style="margin-bottom:12px">
      <div class="stat-card"><div class="value">${avgBounces.toFixed(1)}</div><div class="label">${L('rbNumBounces')} (${ko?'평균':'avg'})</div></div>
      <div class="stat-card"><div class="value">${(avgRatio*100).toFixed(1)}%</div><div class="label">${L('rbSecondaryRatio')} (${ko?'평균':'avg'})</div></div>
      <div class="stat-card"><div class="value">${avgDecay.toFixed(2)}</div><div class="label">${L('rbDecayRate')} (/ms)</div></div>
      <div class="stat-card"><div class="value">${multiBouncePct.toFixed(0)}%</div><div class="label">${ko?'다중 바운스 비율':'Multi-bounce %'}</div></div>
    </div>`;

  // Table
  let rows = '';
  for (const d of rbData.slice(0, 20)) {
    const badge = d.nBounces >= 4 ? 'hotspot-badge' : d.nBounces >= 2 ? 'hotspot-badge warn' : 'hotspot-badge ok';
    rows += `<tr><td style="color:var(--cyan)">${d.name}</td><td>${d.cat}</td>
      <td style="text-align:center"><span class="${badge}">${d.nBounces}</span></td>
      <td style="text-align:right">${d.p1.toFixed(3)}</td>
      <td style="text-align:right">${d.p2.toFixed(3)}</td>
      <td style="text-align:right">${(d.ratio21*100).toFixed(1)}%</td>
      <td style="text-align:right">${d.decayRate.toFixed(3)}</td>
      <td style="color:var(--dim);font-size:10px">${d.peakTimes.map(t=>t.toFixed(2)).join(', ')}</td></tr>`;
  }
  html += `<div class="table-wrap" style="max-height:350px;overflow-y:auto">
    <table><tr><th>${L('direction')}</th><th>${L('category')}</th><th>${L('rbNumBounces')}</th>
      <th>${ko?'1차 피크':'1st Peak'} (MG)</th><th>${ko?'2차 피크':'2nd Peak'} (MG)</th>
      <th>${L('rbSecondaryRatio')}</th><th>${L('rbDecayRate')}</th>
      <th>${ko?'피크 시간 (ms)':'Peak Times (ms)'}</th></tr>${rows}</table></div>`;
  // Auto-interpretation
  const rbNarr = [];
  if (ko) {
    rbNarr.push(`평균 바운스 횟수: <b>${avgBounces.toFixed(1)}</b>회. ${avgBounces >= 3 ? '다중 리바운드가 빈번하여 누적 피로 위험이 있습니다.' : avgBounces >= 2 ? '대부분 1~2회 리바운드로, 일반적인 낙하 충격 패턴입니다.' : '단일 충격이 지배적으로, 리바운드 누적 효과는 미미합니다.'}`);
    rbNarr.push(`평균 2차/1차 비율: <b>${(avgRatio*100).toFixed(1)}%</b>. ${avgRatio > 0.5 ? '높은 탄성 반발(COR 높음)로 2차 충격이 1차의 절반 이상입니다. 2차 충격 후에도 부품 내구성을 확인해야 합니다.' : avgRatio > 0.2 ? '보통 수준의 에너지 감쇠로, 2차 충격이 존재하지만 1차 대비 크게 감소합니다.' : '빠른 에너지 소산으로 2차 충격이 미미합니다.'}`);
    if (multiBouncePct > 70) rbNarr.push(`<span style="color:#f7768e">전체 방향의 <b>${multiBouncePct.toFixed(0)}%</b>에서 다중 바운스가 발생합니다. JEDEC JESD22-B111 기준에 따라 2차 충격을 내구성 평가에 포함해야 합니다.</span>`);
  } else {
    rbNarr.push(`Average bounces: <b>${avgBounces.toFixed(1)}</b>. ${avgBounces >= 3 ? 'Frequent multi-bounce — cumulative fatigue risk.' : avgBounces >= 2 ? 'Typical 1–2 bounces — normal drop impact pattern.' : 'Single impact dominant — minimal rebound accumulation.'}`);
    rbNarr.push(`Average 2nd/1st ratio: <b>${(avgRatio*100).toFixed(1)}%</b>. ${avgRatio > 0.5 ? 'High elastic rebound (high COR) — 2nd impact exceeds half of 1st. Verify component survivability after secondary impacts.' : avgRatio > 0.2 ? 'Moderate energy decay — secondary impact present but significantly reduced.' : 'Rapid energy dissipation — secondary impacts negligible.'}`);
    if (multiBouncePct > 70) rbNarr.push(`<span style="color:#f7768e"><b>${multiBouncePct.toFixed(0)}%</b> of directions show multi-bounce. Per JEDEC JESD22-B111, secondary impacts should be included in durability assessment.</span>`);
  }
  html += `<div style="padding:8px;background:var(--bg3);border-radius:4px;border-left:3px solid #e0af68;margin-top:8px;font-size:11px;line-height:1.6;color:var(--fg)">${rbNarr.join('<br>')}</div></div>`;
  return html;
}

function buildCorrelationMatrix(pid) {
  const pidStr = String(pid);
  const ko = reportLang === 'ko';
  // Collect data vectors across all angles
  const stress=[], gforce=[], strain=[], disp=[], vel=[];
  for (const r of DATA.results) {
    const pd = r.parts[pidStr];
    if (!pd) continue;
    stress.push(pd.peak_stress || 0);
    gforce.push(pd.peak_g || 0);
    strain.push(pd.peak_strain || 0);
    disp.push(pd.peak_disp || 0);
    vel.push(pd.peak_vel || 0);
  }
  const n = stress.length;
  if (n < 3) return '';

  function pearson(a, b) {
    const ma = a.reduce((s,v)=>s+v,0)/n, mb = b.reduce((s,v)=>s+v,0)/n;
    let num = 0, da = 0, db = 0;
    for (let i = 0; i < n; i++) {
      const ai = a[i]-ma, bi = b[i]-mb;
      num += ai*bi; da += ai*ai; db += bi*bi;
    }
    return (da > 0 && db > 0) ? num / Math.sqrt(da*db) : 0;
  }

  const labels = [L('cmStress'), L('cmGforce'), L('cmStrain'), L('cmDisp'), L('cmVel')];
  const vecs = [stress, gforce, strain, disp, vel];
  const matrix = [];
  for (let i = 0; i < 5; i++) {
    matrix[i] = [];
    for (let j = 0; j < 5; j++) {
      matrix[i][j] = i === j ? 1.0 : pearson(vecs[i], vecs[j]);
    }
  }

  // SVG heatmap
  const CS = 60, pad = 80, padTop = 20;
  const SW = pad + 5*CS + 10, SH = padTop + 5*CS + pad;
  let svg = `<svg width="100%" viewBox="0 0 ${SW} ${SH}" style="max-width:${SW}px">`;
  for (let i = 0; i < 5; i++) {
    for (let j = 0; j < 5; j++) {
      const r = matrix[i][j];
      const x = pad + j*CS, y = padTop + i*CS;
      // Color: positive = blue (cyan), negative = red, zero = dark
      let cr, cg, cb;
      if (r >= 0) { cr = Math.round(30*(1-r)); cg = Math.round(80+175*r); cb = Math.round(80+175*r); }
      else { cr = Math.round(80+175*Math.abs(r)); cg = Math.round(30*(1-Math.abs(r))); cb = Math.round(30*(1-Math.abs(r))); }
      svg += `<rect x="${x}" y="${y}" width="${CS}" height="${CS}" fill="rgb(${cr},${cg},${cb})" stroke="var(--bg)" stroke-width="1"/>`;
      svg += `<text x="${x+CS/2}" y="${y+CS/2+4}" text-anchor="middle" fill="${Math.abs(r)>0.5?'#fff':'#a9b1d6'}" font-size="12" font-weight="${Math.abs(r)>0.7?'bold':'normal'}">${r.toFixed(2)}</text>`;
    }
    // Row label
    svg += `<text x="${pad-4}" y="${padTop+i*CS+CS/2+4}" text-anchor="end" fill="var(--fg2)" font-size="11">${labels[i]}</text>`;
    // Col label
    svg += `<text x="${pad+i*CS+CS/2}" y="${padTop+5*CS+16}" text-anchor="middle" fill="var(--fg2)" font-size="11">${labels[i]}</text>`;
  }
  svg += '</svg>';

  let html = `<div class="dd-section"><div class="dd-section-title">${L('cmTitle')}</div>
    <div style="color:var(--fg2);font-size:12px;margin-bottom:8px">${L('cmDesc')}</div>
    <details style="margin-bottom:12px"><summary style="cursor:pointer;color:var(--cyan);font-size:11px;font-weight:bold">${ko?'▸ 상관계수 해석 방법 및 물리적 의미':'▸ Correlation interpretation & physical meaning'}</summary>
      <div style="padding:8px 12px;margin-top:4px;background:var(--bg);border-radius:4px;border-left:3px solid var(--cyan);font-size:11px;color:var(--fg2);line-height:1.7">${L('cmGuide')}</div></details>
    <div style="overflow-x:auto">${svg}</div>`;

  // Key insights
  const insights = [];
  for (let i = 0; i < 5; i++) {
    for (let j = i+1; j < 5; j++) {
      const r = matrix[i][j];
      if (Math.abs(r) > 0.7) {
        const strength = Math.abs(r) > 0.9 ? (ko?'매우 강한':'Very strong') : (ko?'강한':'Strong');
        const dir = r > 0 ? (ko?'양의':'positive') : (ko?'음의':'negative');
        insights.push(`${strength} ${dir} ${ko?'상관':'correlation'}: ${labels[i]} ↔ ${labels[j]} (r=${r.toFixed(2)})`);
      }
    }
  }
  if (insights.length > 0) {
    html += `<div style="margin-top:8px;padding:8px;background:var(--bg);border-radius:4px;border-left:3px solid var(--cyan)">`;
    for (const ins of insights) {
      html += `<div style="font-size:11px;color:var(--fg2);margin-bottom:2px">${ins}</div>`;
    }
    html += '</div>';
  }
  html += '</div>';
  return html;
}

function buildCrackArrestSection(pid) {
  const pidStr = String(pid);
  const ko = reportLang === 'ko';
  const ys = DATA.yield_stress || 0;
  const results = [];

  for (const r of DATA.results) {
    const pd = r.parts[pidStr];
    if (!pd) continue;
    const hasSts = pd.stress_ts && pd.stress_ts.max && pd.stress_ts.t;
    const hasSn = pd.strain_ts && pd.strain_ts.max && pd.strain_ts.t;
    if (!hasSts) continue;

    const sMax = pd.stress_ts.max;
    const sAvg = pd.stress_ts.avg || sMax;
    const times = pd.stress_ts.t;
    const n = sMax.length;
    if (n < 3) continue;
    const totalDuration = times[n-1] - times[0];
    if (totalDuration <= 0) continue;

    const peakStress = Math.max(...sMax);
    if (peakStress <= 0) continue;

    // --- Indicator 1: Stress Duration Ratio (SDR) ---
    // Fraction of time that stress exceeds threshold (yield or 70% peak)
    const threshold = ys > 0 ? Math.min(ys, peakStress * 0.7) : peakStress * 0.7;
    let aboveTime = 0;
    for (let i = 1; i < n; i++) {
      if (sMax[i] >= threshold || sMax[i-1] >= threshold) {
        aboveTime += times[i] - times[i-1];
      }
    }
    const sdr = aboveTime / totalDuration; // 0~1, lower = arrest-favorable
    const sdrScore = 1 - sdr; // Invert: higher = more favorable for arrest

    // --- Indicator 2: Loading Rate Score ---
    // dσ/dt at onset: find steepest rising slope before peak
    const peakIdx = sMax.indexOf(peakStress);
    let maxRate = 0;
    for (let i = 1; i <= peakIdx && i < n; i++) {
      const dt = times[i] - times[i-1];
      if (dt > 0) {
        const rate = (sMax[i] - sMax[i-1]) / dt; // MPa/s
        if (rate > maxRate) maxRate = rate;
      }
    }
    // Normalize: typical drop test range 1e6~1e10 MPa/s
    // Higher rate → more brittle → arrest-unfavorable
    // Use log scale: score = 1 - clamp((log10(rate) - 6) / 4, 0, 1)
    const logRate = maxRate > 0 ? Math.log10(maxRate) : 0;
    const loadRateScore = Math.max(0, Math.min(1, 1 - (logRate - 6) / 4));

    // --- Indicator 3: Stress Concentration Factor Score ---
    // max/avg at peak time: high ratio = localized stress = small plastic zone
    const avgAtPeak = sAvg[Math.min(peakIdx, sAvg.length-1)] || 1;
    const scf = avgAtPeak > 0 ? peakStress / avgAtPeak : 1;
    // SCF ~1 = uniform (good for arrest), SCF > 3 = highly concentrated (bad)
    const scfScore = Math.max(0, Math.min(1, 1 - (scf - 1) / 3));

    // --- Indicator 4: Energy Dissipation Rate ---
    // How quickly stress drops after peak: compare area under curve after peak
    // to hypothetical sustained-peak scenario
    let postPeakArea = 0, sustainedArea = 0;
    for (let i = peakIdx + 1; i < n; i++) {
      const dt = times[i] - times[i-1];
      postPeakArea += sMax[i] * dt;
      sustainedArea += peakStress * dt;
    }
    // Ratio of actual vs sustained: lower = faster dissipation = arrest-favorable
    const dissRatio = sustainedArea > 0 ? postPeakArea / sustainedArea : 1;
    const dissScore = Math.max(0, Math.min(1, 1 - dissRatio));

    // --- Composite: Crack Arrest Index (CAI) ---
    // Weighted combination: SDR 30%, LoadRate 20%, SCF 25%, Dissipation 25%
    const cai = sdrScore * 0.30 + loadRateScore * 0.20 + scfScore * 0.25 + dissScore * 0.25;

    results.push({
      name: r.angle.name, cat: r.angle.category || 'other',
      cai, sdrScore, loadRateScore, scfScore, dissScore,
      sdr, maxRate, scf, dissRatio,
      peakStress, threshold
    });
  }

  if (results.length === 0) return '';
  results.sort((a,b) => a.cai - b.cai); // Worst first (lowest CAI)

  const avgCAI = results.reduce((s,d) => s+d.cai, 0) / results.length;
  const minCAI = results[0].cai;
  const maxCAI = results[results.length-1].cai;
  const nUnlikely = results.filter(d => d.cai < 0.3).length;
  const nMarginal = results.filter(d => d.cai >= 0.3 && d.cai < 0.6).length;
  const nLikely = results.filter(d => d.cai >= 0.6).length;

  // CAI rating color/label
  function caiLabel(v) {
    if (v >= 0.6) return `<span style="color:#9ece6a;font-weight:bold">${L('caiArrestLikely')}</span>`;
    if (v >= 0.3) return `<span style="color:#e0af68;font-weight:bold">${L('caiMarginal')}</span>`;
    return `<span style="color:#f7768e;font-weight:bold">${L('caiArrestUnlikely')}</span>`;
  }
  function caiColor(v) { return v >= 0.6 ? '#9ece6a' : v >= 0.3 ? '#e0af68' : '#f7768e'; }

  let html = `<div class="dd-section"><div class="dd-section-title">${L('caTitle')} <sup style="color:var(--cyan);font-size:9px">[4][5][6][7]</sup></div>
    <div style="color:var(--fg2);font-size:12px;margin-bottom:8px;line-height:1.6">${L('caDesc')}</div>
    <details style="margin-bottom:12px"><summary style="cursor:pointer;color:var(--cyan);font-size:11px;font-weight:bold">${ko?'▸ 규격 기반 근거 및 각 지표의 파괴역학적 의미':'▸ Standards-based rationale & fracture mechanics meaning'}</summary>
      <div style="padding:8px 12px;margin-top:4px;background:var(--bg);border-radius:4px;border-left:3px solid var(--cyan);font-size:11px;color:var(--fg2);line-height:1.7">${L('caGuide')}</div></details>`;

  // KPI cards
  html += `<div class="stat-grid" style="margin-bottom:12px">
    <div class="stat-card"><div class="value" style="color:${caiColor(avgCAI)}">${avgCAI.toFixed(3)}</div><div class="label">${ko?'평균 CAI':'Avg CAI'}</div><div style="font-size:10px;color:var(--dim)">${caiLabel(avgCAI)}</div></div>
    <div class="stat-card"><div class="value" style="color:${caiColor(minCAI)}">${minCAI.toFixed(3)}</div><div class="label">${ko?'최악 CAI (정지 가장 불리)':'Worst CAI'}</div><div style="font-size:10px;color:var(--dim)">${results[0].name}</div></div>
    <div class="stat-card"><div class="value" style="color:#f7768e">${nUnlikely}</div><div class="label">${L('caiArrestUnlikely')} (<0.3)</div></div>
    <div class="stat-card"><div class="value" style="color:#e0af68">${nMarginal}</div><div class="label">${L('caiMarginal')} (0.3–0.6)</div></div>
    <div class="stat-card"><div class="value" style="color:#9ece6a">${nLikely}</div><div class="label">${L('caiArrestLikely')} (>0.6)</div></div>
  </div>`;

  // SVG: CAI strip chart — all directions sorted by CAI
  const SW = 600, SH = 180, ml = 55, mr = 10, mt = 15, mb = 50;
  const spw = SW - ml - mr, sph = SH - mt - mb;
  const barW = Math.max(3, Math.min(20, spw / results.length - 1));
  let svg = `<svg width="100%" viewBox="0 0 ${SW} ${SH}" style="max-width:${SW}px">
    <rect x="${ml}" y="${mt}" width="${spw}" height="${sph}" fill="var(--bg3)" rx="2"/>`;
  // Zone bands
  svg += `<rect x="${ml}" y="${mt}" width="${spw}" height="${(sph*0.4).toFixed(1)}" fill="rgba(158,206,106,0.06)"/>`;
  svg += `<rect x="${ml}" y="${(mt+sph*0.4).toFixed(1)}" width="${spw}" height="${(sph*0.3).toFixed(1)}" fill="rgba(224,175,104,0.06)"/>`;
  svg += `<rect x="${ml}" y="${(mt+sph*0.7).toFixed(1)}" width="${spw}" height="${(sph*0.3).toFixed(1)}" fill="rgba(247,118,142,0.06)"/>`;
  // Zone labels
  svg += `<text x="${ml+spw+2}" y="${mt+12}" fill="#9ece6a" font-size="8" opacity="0.6">${L('caiArrestLikely')}</text>`;
  svg += `<text x="${ml+spw+2}" y="${(mt+sph*0.5).toFixed(0)}" fill="#e0af68" font-size="8" opacity="0.6">${L('caiMarginal')}</text>`;
  svg += `<text x="${ml+spw+2}" y="${(mt+sph*0.85).toFixed(0)}" fill="#f7768e" font-size="8" opacity="0.6">${L('caiArrestUnlikely')}</text>`;
  // Threshold lines
  svg += `<line x1="${ml}" y1="${(mt+sph*0.4).toFixed(1)}" x2="${ml+spw}" y2="${(mt+sph*0.4).toFixed(1)}" stroke="#9ece6a" stroke-dasharray="3,3" opacity="0.3"/>`;
  svg += `<line x1="${ml}" y1="${(mt+sph*0.7).toFixed(1)}" x2="${ml+spw}" y2="${(mt+sph*0.7).toFixed(1)}" stroke="#f7768e" stroke-dasharray="3,3" opacity="0.3"/>`;
  // Y-axis labels
  for (let v = 0; v <= 1; v += 0.2) {
    const y = mt + sph - v * sph;
    svg += `<text x="${ml-4}" y="${y+3}" text-anchor="end" fill="#7982a9" font-size="9">${v.toFixed(1)}</text>`;
  }
  // Bars
  const sorted = [...results].sort((a,b) => a.cai - b.cai);
  sorted.forEach((d, i) => {
    const x = ml + (i + 0.5) * spw / sorted.length - barW / 2;
    const h = Math.max(1, d.cai * sph);
    const y = mt + sph - h;
    svg += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW}" height="${h.toFixed(1)}" fill="${caiColor(d.cai)}" rx="1" opacity="0.8"><title>${d.name}: CAI=${d.cai.toFixed(3)}</title></rect>`;
  });
  svg += `<text x="${ml+spw/2}" y="${SH-2}" text-anchor="middle" fill="#7982a9" font-size="10">${ko?'방향 (CAI 오름차순 정렬)':'Directions (sorted by CAI ascending)'}</text>`;
  svg += `<text x="10" y="${mt+sph/2}" text-anchor="middle" fill="#7982a9" font-size="10" transform="rotate(-90,10,${mt+sph/2})">CAI</text>`;
  svg += '</svg>';
  html += `<div style="overflow-x:auto;margin-bottom:16px">${svg}</div>`;

  // Radar chart for sub-indicators (average across all directions)
  const avgSDR = results.reduce((s,d)=>s+d.sdrScore,0)/results.length;
  const avgLR = results.reduce((s,d)=>s+d.loadRateScore,0)/results.length;
  const avgSCF = results.reduce((s,d)=>s+d.scfScore,0)/results.length;
  const avgDiss = results.reduce((s,d)=>s+d.dissScore,0)/results.length;
  const radarLabels = [L('caiDuration'), L('caiLoadRate'), L('caiSCF'), L('caiDissipation')];
  const radarVals = [avgSDR, avgLR, avgSCF, avgDiss];
  const radarWeights = [0.30, 0.20, 0.25, 0.25];
  const RW = 320, RH = 320, rcx = RW/2, rcy = RH/2, rr = 110;
  let rsvg = `<svg width="100%" viewBox="0 0 ${RW} ${RH}" style="max-width:${RW}px">`;
  // Background rings
  for (let ring = 0.2; ring <= 1.0; ring += 0.2) {
    let ringPath = '';
    for (let a = 0; a < 4; a++) {
      const angle = -Math.PI/2 + a * Math.PI/2;
      const x = rcx + Math.cos(angle) * rr * ring, y = rcy + Math.sin(angle) * rr * ring;
      ringPath += (a===0?'M':'L') + `${x.toFixed(1)},${y.toFixed(1)}`;
    }
    rsvg += `<path d="${ringPath}Z" fill="none" stroke="rgba(255,255,255,0.08)"/>`;
    // Ring value label
    const ry = rcy - rr * ring;
    rsvg += `<text x="${rcx+3}" y="${ry+3}" fill="#7982a9" font-size="8">${ring.toFixed(1)}</text>`;
  }
  // Axes
  for (let a = 0; a < 4; a++) {
    const angle = -Math.PI/2 + a * Math.PI/2;
    const x2 = rcx + Math.cos(angle) * rr, y2 = rcy + Math.sin(angle) * rr;
    rsvg += `<line x1="${rcx}" y1="${rcy}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="rgba(255,255,255,0.12)"/>`;
    const lx = rcx + Math.cos(angle) * (rr + 30), ly = rcy + Math.sin(angle) * (rr + 15);
    const anchor = a===1?'start':a===3?'end':'middle';
    rsvg += `<text x="${lx.toFixed(0)}" y="${ly.toFixed(0)}" text-anchor="${anchor}" fill="var(--fg2)" font-size="9">${radarLabels[a]}</text>`;
    rsvg += `<text x="${lx.toFixed(0)}" y="${(ly+11).toFixed(0)}" text-anchor="${anchor}" fill="var(--dim)" font-size="8">(w=${(radarWeights[a]*100).toFixed(0)}%) ${radarVals[a].toFixed(2)}</text>`;
  }
  // Data polygon
  let dataPath = '';
  for (let a = 0; a < 4; a++) {
    const angle = -Math.PI/2 + a * Math.PI/2;
    const v = radarVals[a];
    const x = rcx + Math.cos(angle) * rr * v, y = rcy + Math.sin(angle) * rr * v;
    dataPath += (a===0?'M':'L') + `${x.toFixed(1)},${y.toFixed(1)}`;
  }
  rsvg += `<path d="${dataPath}Z" fill="rgba(125,207,250,0.15)" stroke="var(--cyan)" stroke-width="2"/>`;
  // Data dots
  for (let a = 0; a < 4; a++) {
    const angle = -Math.PI/2 + a * Math.PI/2;
    const v = radarVals[a];
    const x = rcx + Math.cos(angle) * rr * v, y = rcy + Math.sin(angle) * rr * v;
    rsvg += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4" fill="var(--cyan)"/>`;
  }
  // Center CAI value
  rsvg += `<text x="${rcx}" y="${rcy-5}" text-anchor="middle" fill="${caiColor(avgCAI)}" font-size="20" font-weight="bold">${avgCAI.toFixed(2)}</text>`;
  rsvg += `<text x="${rcx}" y="${rcy+12}" text-anchor="middle" fill="var(--fg2)" font-size="10">CAI</text>`;
  rsvg += '</svg>';

  html += `<div style="display:flex;flex-wrap:wrap;gap:16px;align-items:flex-start;margin-bottom:16px">`;
  html += `<div style="flex:0 0 auto">${rsvg}</div>`;

  // Interpretation narrative
  html += `<div style="flex:1;min-width:250px">`;
  html += `<div class="dd-narrative" style="border-left:3px solid ${caiColor(avgCAI)};padding:12px;background:var(--bg3);border-radius:4px">`;
  html += `<div class="dd-heading" style="font-size:13px;font-weight:bold;margin-bottom:8px;color:${caiColor(avgCAI)}">${ko?'종합 평가':'Overall Assessment'}: ${caiLabel(avgCAI)}</div>`;

  // Generate narrative based on sub-scores
  const sentences = [];
  if (avgSDR > 0.7) sentences.push(ko
    ? `응력 지속비가 낮아(SDR score ${avgSDR.toFixed(2)}) 임계 응력 초과 시간이 짧습니다. 동적 하중이 빠르게 해제되어 균열 구동력이 단시간 내 소멸합니다.`
    : `Low stress duration ratio (SDR score ${avgSDR.toFixed(2)}): stress exceeds threshold only briefly. Dynamic load releases quickly, removing crack driving force.`);
  else if (avgSDR > 0.4) sentences.push(ko
    ? `응력 지속비가 중간 수준(SDR score ${avgSDR.toFixed(2)})으로, 임계 응력 초과 시간이 비교적 길어 균열 전파 구간이 존재합니다.`
    : `Moderate stress duration ratio (SDR score ${avgSDR.toFixed(2)}): stress exceeds threshold for a notable fraction of the event. Some crack propagation window exists.`);
  else sentences.push(ko
    ? `응력 지속비가 높아(SDR score ${avgSDR.toFixed(2)}) 임계 응력 초과 상태가 오래 유지됩니다. 지속적 하중으로 인해 균열 정지 없이 전파가 계속될 가능성이 높습니다.`
    : `High stress duration ratio (SDR score ${avgSDR.toFixed(2)}): stress exceeds threshold for most of the event. Sustained loading makes arrest unlikely — crack may propagate continuously.`);

  if (avgLR > 0.6) sentences.push(ko
    ? `하중속도가 상대적으로 낮아(LR score ${avgLR.toFixed(2)}) 재료가 연성 거동을 보일 가능성이 높습니다. 균열 선단의 소성 둔화(blunting)가 정지에 기여합니다.`
    : `Moderate loading rate (LR score ${avgLR.toFixed(2)}): material likely exhibits ductile behavior. Crack tip blunting contributes to arrest.`);
  else if (avgLR < 0.3) sentences.push(ko
    ? `하중속도가 매우 높아(LR score ${avgLR.toFixed(2)}) 재료가 취성 거동을 보일 수 있습니다. 동적 파괴인성(K_ID)이 정적 값보다 낮아져 균열 정지가 어려워집니다.`
    : `Very high loading rate (LR score ${avgLR.toFixed(2)}): material may exhibit brittle behavior. Dynamic fracture toughness (K_ID) drops below static value, making arrest difficult.`);

  if (avgSCF > 0.7) sentences.push(ko
    ? `응력 분포가 비교적 균일합니다(SCF score ${avgSCF.toFixed(2)}). 넓은 소성 영역이 형성되어 균열 선단 에너지를 흡수하고 정지를 촉진합니다.`
    : `Stress distribution is relatively uniform (SCF score ${avgSCF.toFixed(2)}). Wide plastic zone forms ahead of crack tip, absorbing energy and promoting arrest.`);
  else if (avgSCF < 0.3) sentences.push(ko
    ? `응력이 국부적으로 집중되어 있습니다(SCF score ${avgSCF.toFixed(2)}). 소성 영역이 작아 균열 선단 둔화(blunting)가 충분하지 않으며, 균열이 빠르게 전파될 수 있습니다.`
    : `Stress is highly localized (SCF score ${avgSCF.toFixed(2)}). Small plastic zone means insufficient crack tip blunting — crack may propagate rapidly.`);

  if (avgDiss > 0.6) sentences.push(ko
    ? `피크 후 응력이 빠르게 감소합니다(Diss score ${avgDiss.toFixed(2)}). 변형 에너지가 빠르게 소산되어 균열 구동 에너지가 급격히 감소하므로 정지 조건이 유리합니다.`
    : `Stress drops rapidly after peak (Diss score ${avgDiss.toFixed(2)}). Deformation energy dissipates quickly — crack driving energy decreases sharply, favoring arrest.`);
  else if (avgDiss < 0.3) sentences.push(ko
    ? `피크 후 응력이 천천히 감소합니다(Diss score ${avgDiss.toFixed(2)}). 잔류 에너지가 오래 유지되어 균열 전파가 지속될 수 있습니다.`
    : `Stress decays slowly after peak (Diss score ${avgDiss.toFixed(2)}). Residual energy persists, potentially sustaining crack propagation.`);

  // Worst direction warning
  if (minCAI < 0.3) {
    const worst5 = sorted.slice(0, Math.min(5, sorted.length)).map(d => d.name).join(', ');
    sentences.push(ko
      ? `<span style="color:#f7768e">⚠ 최악 방향 주의:</span> ${worst5} — 이 방향에서 균열이 시작되면 정지 없이 전파될 가능성이 높습니다. 설계 검토가 필요합니다.`
      : `<span style="color:#f7768e">⚠ Critical directions:</span> ${worst5} — if a crack initiates from these directions, arrest is unlikely. Design review recommended.`);
  }

  for (const s of sentences) {
    html += `<div style="font-size:12px;color:var(--fg);margin-bottom:6px;line-height:1.5">${s}</div>`;
  }
  html += '</div></div></div>';

  // Detailed table
  let rows = '';
  for (const d of results.slice(0, 25)) {
    rows += `<tr>
      <td style="color:var(--cyan)">${d.name}</td><td>${d.cat}</td>
      <td style="text-align:center"><span style="color:${caiColor(d.cai)};font-weight:bold">${d.cai.toFixed(3)}</span></td>
      <td style="text-align:right">${d.sdrScore.toFixed(2)}</td>
      <td style="text-align:right">${d.loadRateScore.toFixed(2)}</td>
      <td style="text-align:right">${d.scfScore.toFixed(2)}</td>
      <td style="text-align:right">${d.dissScore.toFixed(2)}</td>
      <td style="text-align:right">${d.peakStress.toFixed(1)}</td>
      <td style="text-align:right;color:var(--dim)">${d.sdr.toFixed(3)}</td>
      <td style="text-align:right;color:var(--dim)">${d.scf.toFixed(2)}</td></tr>`;
  }
  html += `<div class="table-wrap" style="max-height:400px;overflow-y:auto">
    <table><tr>
      <th>${L('direction')}</th><th>${L('category')}</th><th>CAI</th>
      <th>${L('caiDuration')}</th><th>${L('caiLoadRate')}</th><th>${L('caiSCF')}</th><th>${L('caiDissipation')}</th>
      <th>${ko?'피크 응력':'Peak σ'} (MPa)</th>
      <th>${ko?'지속비 (원시)':'SDR (raw)'}</th><th>SCF</th>
    </tr>${rows}</table></div>`;

  // Methodology note
  html += `<div style="margin-top:12px;padding:8px;background:var(--bg);border-radius:4px;border-left:3px solid var(--dim)">
    <div style="font-size:10px;color:var(--dim);line-height:1.5">
      ${ko
        ? '<b>방법론 참고:</b> CAI는 연속체 역학 시계열 데이터로부터 도출한 <em>간접 지표</em>입니다. 명시적 균열 모델링(XFEM, cohesive zone) 없이는 실제 K<sub>IC</sub>/J-integral 기반 평가를 대체할 수 없습니다. SDR: 임계응력 = min(σ<sub>y</sub>, 0.7σ<sub>peak</sub>). Loading rate: log₁₀(dσ/dt) 정규화(6~10 범위). SCF: σ<sub>max</sub>/σ<sub>avg</sub>(시간 평균 아닌 피크 시점). Dissipation: 피크 후 실제 면적 대 유지 면적 비.'
        : '<b>Methodology note:</b> CAI is an <em>indirect proxy</em> derived from continuum mechanics time-series data. It cannot replace explicit K<sub>IC</sub>/J-integral assessment without crack modeling (XFEM, cohesive zone). SDR: threshold = min(σ<sub>y</sub>, 0.7σ<sub>peak</sub>). Loading rate: log₁₀(dσ/dt) normalized over 6–10 range. SCF: σ<sub>max</sub>/σ<sub>avg</sub> at peak time. Dissipation: actual post-peak area vs. sustained-peak area.'}
    </div></div>`;

  html += '</div>';
  return html;
}

function renderAdvancedAnalysis() {
  const container = document.getElementById('advanced-content');
  if (!container) return;
  const parts = getAllPartIds();
  if (advState.partId === 0 && parts.length > 0) advState.partId = parts[0];
  const ko = reportLang === 'ko';

  let html = `<div class="controls"><label>${L('advSelectPart')}</label>
    <select id="adv-part" onchange="advState.partId=parseInt(this.value);document.getElementById('advanced-content').dataset.done='';renderAdvancedAnalysis()">`;
  for (const pid of parts) {
    const p = DATA.parts[String(pid)];
    html += `<option value="${pid}"${pid===advState.partId?' selected':''}>${p?p.name:''} (ID:${pid})</option>`;
  }
  html += '</select></div>';

  const pid = advState.partId;
  html += `<div class="panel"><h2>${L('advTitle')} — ${(DATA.parts[String(pid)]||{}).name||'Part '+pid}</h2>`;
  html += buildImpactPulseSection(pid);
  html += '</div>';
  html += `<div class="panel">${buildCriticalElementSection(pid)}</div>`;
  html += `<div class="panel">${buildEnergyAbsorptionSection(pid)}</div>`;
  html += `<div class="panel">${buildReboundSection(pid)}</div>`;
  html += `<div class="panel">${buildCorrelationMatrix(pid)}</div>`;
  html += `<div class="panel">${buildCrackArrestSection(pid)}</div>`;

  // Reference standards footnote panel
  html += `<div class="panel" style="border-top:2px solid var(--cyan);margin-top:8px">
    <h2 style="font-size:13px">${ko?'참조 규격 및 문헌':'Reference Standards & Literature'}</h2>
    <div style="font-size:11px;color:var(--fg2);line-height:1.8">
      <div style="display:grid;grid-template-columns:auto 1fr;gap:4px 12px;align-items:start">
        <span style="color:var(--cyan);font-weight:bold">[1]</span><span><b>MIL-STD-810G/H, Method 516.7</b> — Shock testing, half-sine pulse specification. ${ko?'충격 시험 표준, 반파사인 펄스 정의. 충격 펄스 특성화 섹션에서 펄스폭, 피크, 임펄스 계산의 기준.':'Basis for pulse width, peak acceleration, and impulse calculations in Impact Pulse Characterization.'}</span>
        <span style="color:var(--cyan);font-weight:bold">[2]</span><span><b>IEC 60068-2-27</b> — Environmental testing, Part 2-27: Shock. ${ko?'환경 시험 규격, 충격. 반파사인 등가 파라미터의 산업 표준 정의.':'Industry standard for half-sine equivalent parameters and shock response spectrum (SRS).'}</span>
        <span style="color:var(--cyan);font-weight:bold">[3]</span><span><b>JEDEC JESD22-B111</b> — Board Level Drop Test Method of Components for Handheld Electronic Products. ${ko?'휴대 전자기기 보드 레벨 낙하 시험. 2차 충격 및 리바운드의 내구성 평가 기준.':'Drop test qualification standard that explicitly considers secondary impacts and rebound in durability assessment.'}</span>
        <span style="color:var(--cyan);font-weight:bold">[4]</span><span><b>BS 7910:2019</b> — Guide to methods for assessing the acceptability of flaws in metallic structures. ${ko?'금속 구조물 결함 허용성 평가. K<sub>I</sub> vs K<sub>Ia</sub> 균열 정지 기준, Level 3 평가에서 소성 영역 및 응력 집중 효과 반영.':'Crack arrest assessment via K<sub>I</sub> vs K<sub>Ia</sub> curves. Level 3 assessment incorporates plastic zone and stress concentration effects.'}</span>
        <span style="color:var(--cyan);font-weight:bold">[5]</span><span><b>ASTM E1221</b> — Standard Test Method for Determining Plane-Strain Crack-Arrest Fracture Toughness (K<sub>Ia</sub>). ${ko?'평면 변형률 균열 정지 파괴인성 시험. CAI의 물리적 근거인 균열 정지 인성 측정 방법.':'Physical basis for crack arrest toughness measurement, underlying the CAI sub-indicators.'}</span>
        <span style="color:var(--cyan);font-weight:bold">[6]</span><span><b>ASTM E399 / E1820</b> — Fracture toughness testing (K<sub>Ic</sub>, J-integral). ${ko?'파괴인성 시험. 동적 하중속도에서 K<sub>Id</sub>가 정적 K<sub>Ic</sub>의 30–70%로 저하 — 하중속도 점수의 근거.':'Dynamic fracture toughness K<sub>Id</sub> reduces to 30–70% of static K<sub>Ic</sub> at high loading rates — basis for loading rate score.'}</span>
        <span style="color:var(--cyan);font-weight:bold">[7]</span><span><b>API 579-1 / ASME FFS-1</b> — Fitness-For-Service. ${ko?'사용 적합성 평가. 균열 포함 구조물의 잔여 수명 평가, 균열 정지 판정에 에너지 해방률(G) 및 재료 저항(R) 비교 적용.':'Remaining life assessment for cracked structures. Crack arrest determination using energy release rate G vs. material resistance R comparison.'}</span>
      </div>
      <div style="margin-top:10px;padding:6px 10px;background:var(--bg);border-radius:4px;color:var(--dim);font-size:10px">
        ${ko
          ? '⚠ 본 분석의 균열 정지 지수(CAI)는 연속체 역학 시계열로부터 도출한 간접 프록시입니다. 규격 수준의 균열 정지 평가(BS 7910 Level 3)를 위해서는 실제 균열 형상에 대한 명시적 파괴역학 해석(XFEM, cohesive zone, J-integral)이 별도로 수행되어야 합니다.'
          : '⚠ The Crack Arrest Index (CAI) in this analysis is an indirect proxy derived from continuum mechanics time series. Standards-level crack arrest assessment (BS 7910 Level 3) requires explicit fracture mechanics analysis (XFEM, cohesive zone, J-integral) with actual crack geometry.'}
      </div>
    </div>
  </div>`;

  container.innerHTML = html;
}

// ============ Tab 11: Render Export ============
let reState = {
  selectedRis: [],        // selected result indices
  refPartId: 0,           // reference part for quick-select ranking
  axis: 'z',
  positions: ['center'],
  customPos: '',
  fringe: 'von_mises',
  partPattern: 'PKG*',
  format: 'mp4',
  fps: 30,
  resolution: [1920, 1080]
};

function reToggleAngle(ri) {
  const idx = reState.selectedRis.indexOf(ri);
  if (idx >= 0) reState.selectedRis.splice(idx, 1);
  else reState.selectedRis.push(ri);
  renderRenderExport();
}

function reQuickSelect(mode) {
  const pid = String(reState.refPartId);
  if (mode === 'clear') { reState.selectedRis = []; renderRenderExport(); return; }
  const scored = [];
  for (let ri = 0; ri < DATA.results.length; ri++) {
    const pd = DATA.results[ri].parts[pid];
    if (!pd) continue;
    if (mode === 'stress') scored.push({ ri, val: pd.peak_stress });
    else if (mode === 'g') scored.push({ ri, val: pd.peak_g });
  }
  scored.sort((a, b) => b.val - a.val);
  reState.selectedRis = scored.slice(0, 5).map(s => s.ri);
  renderRenderExport();
}

function reGenerateYAML() {
  const ko = reportLang === 'ko';
  const now = new Date().toISOString().slice(0, 19);
  const testDir = DATA.test_dir || '/path/to/test_dir';
  const lines = [];
  lines.push(`# Auto-generated by KooReport Render Export`);
  lines.push(`# Test: ${DATA.project_name}`);
  lines.push(`# Generated: ${now}`);
  lines.push(`# Angles: ${reState.selectedRis.length}`);
  lines.push(`version: "2.0"`);
  lines.push(``);
  lines.push(`performance:`);
  lines.push(`  lsprepost_path: "${testDir}/../../installed/lsprepost/lsprepost"`);
  lines.push(``);

  // Collect all positions
  const allPos = [...reState.positions];
  if (reState.customPos.trim()) {
    reState.customPos.split(',').forEach(p => {
      const t = p.trim();
      if (t) allPos.push(t);
    });
  }

  if (reState.selectedRis.length > 0) {
    lines.push(`render_jobs:`);
    for (const ri of reState.selectedRis) {
      const r = DATA.results[ri];
      if (!r) continue;
      const name = (r.angle.name || `angle_${ri}`).replace(/[^a-zA-Z0-9_]/g, '_');
      const folder = r.folder || `Run_${ri}`;
      const d3path = `${testDir}/output/${folder}/d3plot`;
      lines.push(`  - name: "${name}_${reState.axis}_section"`);
      lines.push(`    type: section_view`);
      lines.push(`    input: "${d3path}"`);
      lines.push(`    fringe: ${reState.fringe}`);
      if (reState.partPattern.trim()) {
        lines.push(`    part_pattern: "${reState.partPattern}"`);
      }
      if (allPos.length === 1) {
        lines.push(`    section:`);
        lines.push(`      axis: ${reState.axis}`);
        lines.push(`      position: ${allPos[0]}`);
      } else {
        lines.push(`    sections:`);
        for (const pos of allPos) {
          lines.push(`      - axis: ${reState.axis}`);
          lines.push(`        position: ${pos}`);
        }
      }
      lines.push(`    output:`);
      lines.push(`      format: ${reState.format}`);
      lines.push(`      directory: "./renders"`);
      if (reState.format !== 'png') {
        lines.push(`      fps: ${reState.fps}`);
      }
      lines.push(`      resolution: [${reState.resolution[0]}, ${reState.resolution[1]}]`);
      lines.push(``);
    }
  }
  return lines.join('\n');
}

function reSyntaxHL(yaml) {
  return yaml.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/^(#.*)$/gm, '<span class="yc">$1</span>')
    .replace(/^(\s*[\w_]+):/gm, '<span class="yk">$1</span>:')
    .replace(/: "([^"]*)"/g, ': "<span class="yv">$1</span>"')
    .replace(/: (\d[\d.]*)/g, ': <span class="yv">$1</span>')
    .replace(/: (true|false|null)/g, ': <span class="yv">$1</span>');
}

function reDownloadYAML() {
  const yaml = reGenerateYAML();
  const blob = new Blob([yaml], { type: 'text/yaml' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `render_config_${DATA.project_name.replace(/[^a-zA-Z0-9]/g,'_')}.yaml`;
  a.click();
  URL.revokeObjectURL(url);
}

function reCopyYAML() {
  navigator.clipboard.writeText(reGenerateYAML()).then(() => {
    const btn = document.getElementById('re-copy-btn');
    if (btn) { btn.textContent = 'Copied!'; setTimeout(() => btn.textContent = L('reCopy'), 1500); }
  });
}

function reDrawMiniMollweide() {
  const W = 500, H = 250;
  const cx = W/2, cy = H/2, rx = W/2 - 10, ry = H/2 - 10;
  const pid = String(reState.refPartId);
  const vals = [];
  for (const r of DATA.results) {
    const pd = r.parts[pid];
    vals.push(pd ? pd.peak_stress : 0);
  }
  const vmax = Math.max(...vals, 1);
  let svg = `<svg class="re-mini-svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`;
  // Background ellipse
  svg += `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="var(--bg3)" stroke="var(--dim)" stroke-width="0.5"/>`;
  // Grid lines
  for (let lon = -150; lon <= 150; lon += 30) {
    let path = '';
    for (let lat = -85; lat <= 85; lat += 5) {
      const [mx, my] = mollweideXY(lon, lat, cx, cy, rx, ry);
      path += (lat === -85 ? 'M' : 'L') + mx.toFixed(1) + ',' + my.toFixed(1);
    }
    svg += `<path d="${path}" fill="none" stroke="var(--bg)" stroke-width="0.3"/>`;
  }
  for (let lat = -60; lat <= 60; lat += 30) {
    let path = '';
    for (let lon = -180; lon <= 180; lon += 5) {
      const [mx, my] = mollweideXY(lon, lat, cx, cy, rx, ry);
      path += (lon === -180 ? 'M' : 'L') + mx.toFixed(1) + ',' + my.toFixed(1);
    }
    svg += `<path d="${path}" fill="none" stroke="var(--bg)" stroke-width="0.3"/>`;
  }
  // Data points
  const ptR = DATA.results.length > 200 ? 3 : DATA.results.length > 50 ? 4 : 5;
  for (let ri = 0; ri < DATA.results.length; ri++) {
    const r = DATA.results[ri];
    const swap = r.angle.swap;
    const [lon, lat] = typeof eulerToLonLat === 'function'
      ? eulerToLonLat(r.angle.roll, r.angle.pitch, r.angle.yaw, r.angle.name, swap)
      : [0, 0];
    const [mx, my] = mollweideXY(lon, lat, cx, cy, rx, ry);
    const norm = vals[ri] / vmax;
    const color = typeof valueToColor === 'function' ? valueToColor(norm) : `hsl(${(1-norm)*240},80%,50%)`;
    const isSel = reState.selectedRis.includes(ri);
    svg += `<circle cx="${mx.toFixed(1)}" cy="${my.toFixed(1)}" r="${isSel ? ptR+2 : ptR}" fill="${color}" opacity="${isSel ? 1 : 0.7}" class="${isSel ? 'sel' : ''}" style="cursor:pointer" onclick="reToggleAngle(${ri})"><title>${r.angle.name}: ${vals[ri].toFixed(1)} MPa</title></circle>`;
  }
  svg += '</svg>';
  return svg;
}

function renderRenderExport() {
  const container = document.getElementById('render-export-content');
  if (!container) return;
  const ko = reportLang === 'ko';
  const parts = getAllPartIds();
  if (reState.refPartId === 0 && parts.length > 0) reState.refPartId = parts[0];

  let html = `<div class="panel"><h2>${L('reTitle')}</h2>`;

  // --- Panel 1: Angle Selection ---
  html += `<div class="panel" style="margin-bottom:12px"><h3>${L('reAngleSelect')} (${reState.selectedRis.length} ${L('reSelected')})</h3>`;
  // Reference part + quick buttons
  html += `<div class="controls" style="margin-bottom:8px">`;
  html += `<label>${L('reRefPart')}</label> <select onchange="reState.refPartId=parseInt(this.value);renderRenderExport()">`;
  for (const pid of parts) {
    const p = DATA.parts[String(pid)];
    html += `<option value="${pid}"${pid===reState.refPartId?' selected':''}>${p?p.name:''} (${pid})</option>`;
  }
  html += `</select> `;
  html += `<button class="re-qbtn" onclick="reQuickSelect('stress')">${L('reTopStress')}</button> `;
  html += `<button class="re-qbtn" onclick="reQuickSelect('g')">${L('reTopG')}</button> `;
  html += `<button class="re-qbtn" onclick="reQuickSelect('clear')">${L('reClear')}</button>`;
  html += `</div>`;
  // Mini mollweide
  html += `<div style="overflow-x:auto">${reDrawMiniMollweide()}</div>`;
  // Selected chips
  if (reState.selectedRis.length > 0) {
    html += `<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:2px">`;
    for (const ri of reState.selectedRis) {
      const r = DATA.results[ri];
      html += `<span class="re-chip selected">${r?r.angle.name:'?'}<span class="x" onclick="reToggleAngle(${ri})">x</span></span>`;
    }
    html += `</div>`;
  }
  html += `</div>`;

  // --- Panel 2: Options ---
  html += `<div class="panel" style="margin-bottom:12px"><h3>${L('reOptions')}</h3>`;
  html += `<div class="re-opt-grid">`;
  // Axis
  html += `<label>${L('reAxis')}</label><div>`;
  for (const a of ['x','y','z']) {
    html += `<label style="margin-right:12px;cursor:pointer"><input type="radio" name="re-axis" value="${a}" ${reState.axis===a?'checked':''} onchange="reState.axis=this.value;renderRenderExport()"> ${a.toUpperCase()}</label>`;
  }
  html += `</div>`;
  // Positions
  const posOpts = ['center','25%','50%','75%','min','max'];
  html += `<label>${L('rePositions')}</label><div>`;
  for (const p of posOpts) {
    const ck = reState.positions.includes(p);
    html += `<label style="margin-right:10px;cursor:pointer"><input type="checkbox" ${ck?'checked':''} onchange="if(this.checked){if(!reState.positions.includes('${p}'))reState.positions.push('${p}')}else{reState.positions=reState.positions.filter(x=>x!=='${p}')};renderRenderExport()"> ${p}</label>`;
  }
  html += `</div>`;
  // Custom position
  html += `<label>${L('reCustomPos')}</label><div><input type="text" value="${reState.customPos}" placeholder="30%, 60%" style="width:160px;background:var(--bg);color:var(--fg2);border:1px solid var(--dim);border-radius:3px;padding:2px 6px;font-size:11px" onchange="reState.customPos=this.value;renderRenderExport()"></div>`;
  // Fringe
  const fringeOpts = [
    ['von_mises','Von Mises Stress'],['eff_plastic_strain','Eff. Plastic Strain'],
    ['displacement','Displacement'],['velocity','Velocity'],['acceleration','Acceleration'],
    ['stress_xx','Stress XX'],['stress_yy','Stress YY'],['stress_zz','Stress ZZ'],
    ['principal_stress_1','Principal Stress 1'],['max_shear_stress','Max Shear']
  ];
  html += `<label>${L('reFringe')}</label><div><select onchange="reState.fringe=this.value;renderRenderExport()" style="background:var(--bg);color:var(--fg2);border:1px solid var(--dim);border-radius:3px;padding:2px 6px;font-size:11px">`;
  for (const [v,l] of fringeOpts) html += `<option value="${v}"${reState.fringe===v?' selected':''}>${l}</option>`;
  html += `</select></div>`;
  // Part pattern
  html += `<label>${L('rePartFilter')}</label><div><input type="text" value="${reState.partPattern}" style="width:120px;background:var(--bg);color:var(--fg2);border:1px solid var(--dim);border-radius:3px;padding:2px 6px;font-size:11px" onchange="reState.partPattern=this.value;renderRenderExport()"></div>`;
  // Format
  html += `<label>${L('reFormat')}</label><div>`;
  for (const f of ['mp4','png','gif']) {
    html += `<label style="margin-right:12px;cursor:pointer"><input type="radio" name="re-fmt" value="${f}" ${reState.format===f?'checked':''} onchange="reState.format=this.value;renderRenderExport()"> ${f.toUpperCase()}</label>`;
  }
  html += `</div>`;
  // Resolution
  const resOpts = [[1920,1080,'1920x1080'],[1280,720,'1280x720'],[3840,2160,'4K']];
  html += `<label>${L('reResolution')}</label><div><select onchange="reState.resolution=this.value.split(',').map(Number);renderRenderExport()" style="background:var(--bg);color:var(--fg2);border:1px solid var(--dim);border-radius:3px;padding:2px 6px;font-size:11px">`;
  for (const [w,h,l] of resOpts) html += `<option value="${w},${h}"${reState.resolution[0]===w?' selected':''}>${l}</option>`;
  html += `</select></div>`;
  // FPS
  html += `<label>${L('reFPS')}</label><div><input type="number" value="${reState.fps}" min="1" max="60" style="width:60px;background:var(--bg);color:var(--fg2);border:1px solid var(--dim);border-radius:3px;padding:2px 6px;font-size:11px" onchange="reState.fps=parseInt(this.value)||30;renderRenderExport()"></div>`;
  html += `</div></div>`;

  // --- Panel 3: YAML Preview + Download ---
  html += `<div class="panel"><h3>${L('rePreview')}</h3>`;
  const yaml = reGenerateYAML();
  html += `<div class="re-yaml-pre">${reSyntaxHL(yaml)}</div>`;
  html += `<div style="margin-top:10px;display:flex;gap:8px;align-items:center">`;
  html += `<button class="re-qbtn" style="background:var(--cyan);color:#1a1b26;font-weight:bold;border-color:var(--cyan)" onclick="reDownloadYAML()">${L('reDownload')}</button>`;
  html += `<button class="re-qbtn" id="re-copy-btn" onclick="reCopyYAML()">${L('reCopy')}</button>`;
  html += `</div>`;
  // Run guide
  html += `<div style="margin-top:12px;padding:8px 12px;background:var(--bg);border-radius:4px;font-size:11px;color:var(--dim)">`;
  html += `<div style="color:var(--fg2);margin-bottom:4px">${L('reRunGuide')}</div>`;
  html += `<code style="color:var(--cyan)">analyze_and_report ${DATA.test_dir || '/path/to/test'} --render-config render_config.yaml</code>`;
  html += `</div>`;
  html += `</div>`;

  html += `</div>`;
  container.innerHTML = html;
}
"""


def generate_html(report: Report, path: str, ts_points: int = 0, test_dir: str = "") -> None:
    """Generate standalone interactive HTML report."""
    data = _build_report_data(report, ts_points=ts_points, test_dir=test_dir)
    data_json = json.dumps(data, cls=_Encoder, ensure_ascii=False)

    # Findings HTML
    findings_html = ""
    for f in report.findings:
        sev = f.severity.value
        findings_html += f'<div class="finding {sev}">'
        findings_html += f'<span class="sev {sev}">[{sev}]</span> '
        findings_html += f'<span class="title">{_esc(f.title)}</span>'
        if f.detail:
            findings_html += f'<div class="detail">{_esc(f.detail)}</div>'
        if f.recommendation:
            findings_html += f'<div class="rec">→ {_esc(f.recommendation)}</div>'
        findings_html += '</div>'

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KooReport - {_esc(report.project_name)}</title>
<style>{_CSS}</style>
</head>
<body>

<div class="header" style="display:flex;align-items:center;justify-content:space-between">
  <div>
    <h1>KooReport</h1>
    <div class="meta">{_esc(report.project_name)} | {report.successful_runs}/{report.total_runs} runs | {report.doe_strategy}</div>
  </div>
  <button id="lang-toggle-btn" onclick="toggleLang()"
    style="background:var(--bg3);color:var(--cyan);border:1px solid var(--dim);border-radius:4px;padding:4px 12px;font-size:13px;font-weight:bold;cursor:pointer;white-space:nowrap">EN</button>
</div>

<div class="tabs">
  <div class="tab active" data-tab="0">Overview</div>
  <div class="tab" data-tab="1">Mollweide Map</div>
  <div class="tab" data-tab="2">Time History</div>
  <div class="tab" data-tab="3">Part Risk</div>
  <div class="tab" data-tab="4">Heatmap</div>
  <div class="tab" data-tab="5">Directional</div>
  <div class="tab" data-tab="6">Failure</div>
  <div class="tab" data-tab="7">Statistics</div>
  <div class="tab" data-tab="8">Impact Analysis</div>
  <div class="tab" data-tab="9">Part Analysis</div>
  <div class="tab" data-tab="10">Advanced</div>
  <div class="tab" data-tab="11">Render Export</div>
</div>

<div class="content">
  <!-- Tab 0: Overview -->
  <div class="tab-content" id="tab-0">
    <div id="overview-stats"></div>
    <div class="panel" style="margin-top:16px">
      <h2>Findings</h2>
      {findings_html}
    </div>
    <div id="overview-guide"></div>
  </div>

  <!-- Tab 1: Mollweide -->
  <div class="tab-content hidden" id="tab-1">
    <div id="mollweide-content"></div>
  </div>

  <!-- Tab 2: Time History -->
  <div class="tab-content hidden" id="tab-2">
    <div class="panel"><h2>Time History Comparison</h2>
      <div id="timehistory-content"></div>
    </div>
  </div>

  <!-- Tab 3: Part Risk -->
  <div class="tab-content hidden" id="tab-3">
    <div id="partrisk-content"></div>
  </div>

  <!-- Tab 4: Heatmap -->
  <div class="tab-content hidden" id="tab-4">
    <div id="gforce-content"></div>
  </div>

  <!-- Tab 5: Directional -->
  <div class="tab-content hidden" id="tab-5">
    <div id="directional-content"></div>
  </div>

  <!-- Tab 6: Failure -->
  <div class="tab-content hidden" id="tab-6">
    <div id="failure-content"></div>
  </div>

  <!-- Tab 7: Statistics -->
  <div class="tab-content hidden" id="tab-7">
    <div id="statistics-content"></div>
  </div>

  <!-- Tab 8: Impact Analysis -->
  <div class="tab-content hidden" id="tab-8">
    <div id="impact-content"></div>
  </div>

  <!-- Tab 9: Part Analysis -->
  <div class="tab-content hidden" id="tab-9">
    <div id="deepdive-content"></div>
  </div>

  <!-- Tab 10: Advanced Analysis -->
  <div class="tab-content hidden" id="tab-10">
    <div id="advanced-content"></div>
  </div>

  <!-- Tab 11: Render Export -->
  <div class="tab-content hidden" id="tab-11">
    <div id="render-export-content"></div>
  </div>
</div>

<div id="tooltip" class="chart-tooltip"></div>

<script>
{_JS}

// Embedded data
const REPORT_DATA = {data_json};
init(REPORT_DATA);
</script>
</body>
</html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html_content)
