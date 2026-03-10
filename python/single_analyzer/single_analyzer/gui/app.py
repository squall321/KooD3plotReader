"""
single_analyzer GUI launcher — CustomTkinter edition.

Modern dark/light themed interface for:
  1. Folder / d3plot file selection
  2. Analysis & render configuration (generates YAML)
  3. One-click analysis execution with live log output

Designed to be buildable independently via PyInstaller.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_ACCENT = "#3B8ED0"
_ACCENT_HOVER = "#2B7BBF"
_GREEN = "#2FA572"
_GREEN_HOVER = "#248F61"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_FRINGE_CHOICES = ["von_mises", "eff_plastic_strain"]
_FORMAT_CHOICES = ["mp4", "png", "jpg", "gif"]
_SECTION_POSITIONS = ["center", "min", "max", "25%", "75%"]
_ANALYSIS_TYPES = [
    ("von_mises",           "Von Mises Stress",        True),
    ("eff_plastic_strain",  "Effective Plastic Strain", True),
    ("part_motion",         "Part Motion",              True),
    ("element_quality",     "Element Quality",          False),
    ("surface_stress",      "Surface Stress",           False),
    ("surface_strain",      "Surface Strain",           False),
]


# ---------------------------------------------------------------------------
# Helper: build YAML string (no PyYAML dependency)
# ---------------------------------------------------------------------------
def _yaml_val(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        inner = ", ".join(_yaml_val(x) for x in v)
        return f"[{inner}]"
    return f'"{v}"'


def build_yaml(cfg: dict) -> str:
    lines: list[str] = ['version: "2.0"', ""]
    lines += ["input:", f'  d3plot: "{cfg["d3plot"]}"', ""]
    lines += [
        "output:",
        f'  directory: "{cfg["output_dir"]}"',
        "  json: true",
        "  csv: true",
        "",
    ]
    lines += [
        "performance:",
        f"  threads: {cfg['threads']}",
        f"  render_threads: {cfg['render_threads']}",
        f"  verbose: {_yaml_val(cfg['verbose'])}",
        "  cache_geometry: true",
    ]
    if cfg.get("lsprepost_path") and cfg["lsprepost_path"] != "auto":
        lines.append(f'  lsprepost_path: "{cfg["lsprepost_path"]}"')
    lines.append("")

    # Design criteria section
    dc = cfg.get("design_criteria", {})
    stress_g = dc.get("global_stress_limit", 0.0)
    strain_g = dc.get("global_strain_limit", 0.002)
    mat_overrides = dc.get("material_overrides", {})
    overrides = dc.get("overrides", {})
    lines += [
        "# ── Design Criteria ──────────────────────────────────────",
        "# Priority: per-part > per-material > keyword auto > global fallback",
        "# Yield stress & failure strain are auto-extracted from keyword",
        "# file (*MAT_ cards). Values below override or supplement them.",
        "design_criteria:",
        f"  global_stress_limit: {stress_g}    # MPa (0 = keyword auto)",
        f"  global_strain_limit: {strain_g}    # (default 0.2% = 0.002)",
    ]
    if mat_overrides:
        lines.append("  material_overrides:               # by MID number or MAT type name")
        for key, mov in sorted(mat_overrides.items(), key=lambda x: x[0]):
            sl = mov.get("stress_limit", 0.0)
            el = mov.get("strain_limit", 0.0)
            parts_list = []
            if sl > 0:
                parts_list.append(f"stress_limit: {sl}")
            if el > 0:
                parts_list.append(f"strain_limit: {el}")
            if parts_list:
                lines.append(f"    {key}:")
                for p in parts_list:
                    lines.append(f"      {p}")
    if overrides:
        lines.append("  overrides:                        # per-part overrides (highest priority)")
        for pid, ov in sorted(overrides.items()):
            sl = ov.get("stress_limit", 0.0)
            el = ov.get("strain_limit", 0.0)
            parts_list = []
            if sl > 0:
                parts_list.append(f"stress_limit: {sl}")
            if el > 0:
                parts_list.append(f"strain_limit: {el}")
            if parts_list:
                lines.append(f"    {pid}:")
                for p in parts_list:
                    lines.append(f"      {p}")
    lines.append("")

    if cfg.get("analysis_jobs"):
        lines.append("analysis_jobs:")
        for job in cfg["analysis_jobs"]:
            lines.append(f'  - name: "{job["name"]}"')
            lines.append(f'    type: {job["type"]}')
            if job.get("parts"):
                lines.append(f'    parts: {_yaml_val(job["parts"])}')
            if job.get("part_pattern"):
                lines.append(f'    part_pattern: "{job["part_pattern"]}"')
            if job.get("output_prefix"):
                lines.append(f'    output_prefix: "{job["output_prefix"]}"')
            if job["type"] in ("surface_stress", "surface_strain"):
                d = job.get("surface_direction", [0, 0, -1])
                a = job.get("surface_angle", 45.0)
                lines += ["    surface:", f"      direction: {_yaml_val(d)}", f"      angle: {a}"]
            lines.append("")

    if cfg.get("render_enabled") and cfg.get("render_jobs"):
        lines.append("render_jobs:")
        for rj in cfg["render_jobs"]:
            lines.append(f'  - name: "{rj["name"]}"')
            lines.append(f'    type: {rj.get("type", "section_view")}')
            lines.append(f'    fringe: {rj.get("fringe", "von_mises")}')
            if rj.get("parts"):
                lines.append(f'    parts: {_yaml_val(rj["parts"])}')
            if rj.get("part_pattern"):
                lines.append(f'    part_pattern: "{rj["part_pattern"]}"')
            if rj.get("section"):
                sec = rj["section"]
                lines += ["    section:", f'      axis: {sec["axis"]}', f'      position: {sec["position"]}']
            lines.append(f'    states: {_yaml_val(rj.get("states", "all"))}')
            out = rj.get("output", {})
            lines.append("    output:")
            lines.append(f'      format: {out.get("format", "mp4")}')
            if out.get("filename"):
                lines.append(f'      filename: "{out["filename"]}"')
            lines.append(f'      fps: {out.get("fps", 30)}')
            lines.append(f'      resolution: {_yaml_val(out.get("resolution", [1920, 1080]))}')
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reusable widgets
# ---------------------------------------------------------------------------
class LabeledEntry(ctk.CTkFrame):
    """Label + Entry in a row."""

    def __init__(self, master, label: str, default: str = "", width: int = 280,
                 browse: str | None = None, **kw):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text=label, width=110, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.var = ctk.StringVar(value=default)
        self.entry = ctk.CTkEntry(self, textvariable=self.var, width=width, placeholder_text=default)
        self.entry.grid(row=0, column=1, sticky="ew")

        if browse:
            self._browse_mode = browse
            ctk.CTkButton(self, text="...", width=36, command=self._browse).grid(
                row=0, column=2, padx=(4, 0))

    def _browse(self) -> None:
        if self._browse_mode == "file":
            path = filedialog.askopenfilename(
                title="d3plot 파일 선택",
                filetypes=[("d3plot files", "d3plot*"), ("All files", "*")],
            )
            if not path:
                path = filedialog.askdirectory(title="시뮬레이션 디렉토리 선택")
        else:
            path = filedialog.askdirectory(title="디렉토리 선택")
        if path:
            self.var.set(path)

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, val: str) -> None:
        self.var.set(val)


class SectionCard(ctk.CTkFrame):
    """A card-style section with title bar."""

    def __init__(self, master, title: str, **kw):
        super().__init__(master, corner_radius=10, **kw)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color=("gray82", "gray25"), corner_radius=8, height=32)
        header.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w", padx=10, pady=4)

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 8))
        self.body.grid_columnconfigure(0, weight=1)


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------
class SingleAnalyzerApp(ctk.CTk):

    def __init__(self) -> None:
        super().__init__()
        self.title("KooD3plotReader — Single Analyzer")
        self.geometry("820x920")
        self.minsize(700, 700)
        self._running = False
        self._create_widgets()

    def _create_widgets(self) -> None:
        # Scrollable main area
        scroll = ctk.CTkScrollableFrame(self, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=0, pady=0)
        scroll.grid_columnconfigure(0, weight=1)

        row = 0

        # ── Header ──
        hdr = ctk.CTkFrame(scroll, fg_color="transparent")
        hdr.grid(row=row, column=0, sticky="ew", padx=16, pady=(12, 4))
        ctk.CTkLabel(hdr, text="Single Analyzer",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        ctk.CTkLabel(hdr, text="LS-DYNA Post-Processing",
                     font=ctk.CTkFont(size=12), text_color="gray50").pack(side="left", padx=(10, 0), pady=(6, 0))

        # Theme toggle
        self._theme_var = ctk.StringVar(value="dark")
        ctk.CTkSegmentedButton(hdr, values=["Light", "Dark"],
                               command=self._toggle_theme, width=120).pack(side="right")
        row += 1

        # ━━ 1. Input / Output ━━
        sec = SectionCard(scroll, "Input / Output")
        sec.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        self.inp_d3plot = LabeledEntry(sec.body, "D3plot Path", browse="file")
        self.inp_d3plot.pack(fill="x", pady=2)
        # Auto-fill label when d3plot path changes
        self.inp_d3plot.var.trace_add("write", self._on_d3plot_changed)

        self.inp_output = LabeledEntry(sec.body, "Output Dir", default="./single_report", browse="dir")
        self.inp_output.pack(fill="x", pady=2)

        row2 = ctk.CTkFrame(sec.body, fg_color="transparent")
        row2.pack(fill="x", pady=2)
        row2.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row2, text="Report Title", width=110, anchor="w").grid(row=0, column=0, sticky="w")
        self.var_label = ctk.StringVar()
        ctk.CTkEntry(row2, textvariable=self.var_label,
                     placeholder_text="Auto-filled from folder name").grid(row=0, column=1, sticky="ew")

        # ━━ 2. Analysis ━━
        sec = SectionCard(scroll, "Analysis")
        sec.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        # Checkbox grid
        cb_frame = ctk.CTkFrame(sec.body, fg_color="transparent")
        cb_frame.pack(fill="x", pady=(0, 6))
        cb_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.analysis_vars: dict[str, ctk.BooleanVar] = {}
        for i, (key, label, default) in enumerate(_ANALYSIS_TYPES):
            var = ctk.BooleanVar(value=default)
            self.analysis_vars[key] = var
            r, c = divmod(i, 3)
            ctk.CTkCheckBox(cb_frame, text=label, variable=var, corner_radius=6).grid(
                row=r, column=c, sticky="w", padx=6, pady=3)

        # Part filter row
        params = ctk.CTkFrame(sec.body, fg_color=("gray90", "gray17"), corner_radius=8)
        params.pack(fill="x", pady=4)

        pf = ctk.CTkFrame(params, fg_color="transparent")
        pf.pack(fill="x", padx=8, pady=6)

        ctk.CTkLabel(pf, text="Part IDs:").pack(side="left")
        self.var_parts = ctk.StringVar()
        ctk.CTkEntry(pf, textvariable=self.var_parts, width=120,
                     placeholder_text="e.g. 1,2,5").pack(side="left", padx=(4, 16))

        ctk.CTkLabel(pf, text="Pattern:").pack(side="left")
        self.var_part_pattern = ctk.StringVar()
        ctk.CTkEntry(pf, textvariable=self.var_part_pattern, width=120,
                     placeholder_text="e.g. PKG*").pack(side="left", padx=4)

        # Surface params
        surf = ctk.CTkFrame(sec.body, fg_color="transparent")
        surf.pack(fill="x", pady=2)
        ctk.CTkLabel(surf, text="Surface Dir (x,y,z):").pack(side="left", padx=(0, 4))
        self.var_surface_dir = ctk.StringVar(value="0, 0, -1")
        ctk.CTkEntry(surf, textvariable=self.var_surface_dir, width=100).pack(side="left", padx=2)
        ctk.CTkLabel(surf, text="Angle (deg):").pack(side="left", padx=(12, 4))
        self.var_surface_angle = ctk.StringVar(value="45.0")
        ctk.CTkEntry(surf, textvariable=self.var_surface_angle, width=60).pack(side="left", padx=2)

        # ━━ 2b. Design Criteria ━━
        sec = SectionCard(scroll, "Design Criteria")
        sec.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        # Info label
        info = ctk.CTkFrame(sec.body, fg_color="transparent")
        info.pack(fill="x", pady=2)
        ctk.CTkLabel(info, text="Auto-extracted from *MAT_ cards in keyword file. Override below if needed.",
                     font=ctk.CTkFont(size=11), text_color="gray50", anchor="w").pack(fill="x")

        # Global fallback
        ov = ctk.CTkFrame(sec.body, fg_color=("gray90", "gray17"), corner_radius=8)
        ov.pack(fill="x", pady=4)
        ctk.CTkLabel(ov, text="Global Fallback  (applied when keyword data unavailable)",
                     font=ctk.CTkFont(size=11, weight="bold"), anchor="w").pack(
            fill="x", padx=10, pady=(6, 2))
        of = ctk.CTkFrame(ov, fg_color="transparent")
        of.pack(fill="x", padx=10, pady=(0, 8))
        of.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(of, text="Stress Limit (MPa):").grid(row=0, column=0, sticky="w")
        self.var_yield = ctk.StringVar(value="0.0")
        ctk.CTkEntry(of, textvariable=self.var_yield, width=100,
                     placeholder_text="0 = auto").grid(row=0, column=1, sticky="w", padx=(4, 16))
        ctk.CTkLabel(of, text="Strain Limit:").grid(row=0, column=2, sticky="w")
        self.var_strain_limit = ctk.StringVar(value="0.002")
        ctk.CTkEntry(of, textvariable=self.var_strain_limit, width=100,
                     placeholder_text="0.002").grid(row=0, column=3, sticky="w", padx=4)

        # Per-material override table
        mt = ctk.CTkFrame(sec.body, fg_color=("gray90", "gray17"), corner_radius=8)
        mt.pack(fill="x", pady=4)
        mt.grid_columnconfigure(0, weight=1)

        mt_hdr = ctk.CTkFrame(mt, fg_color="transparent")
        mt_hdr.pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkLabel(mt_hdr, text="Per-Material Overrides  (applies to all parts using same material)",
                     font=ctk.CTkFont(size=11, weight="bold"), anchor="w").pack(side="left")
        ctk.CTkButton(mt_hdr, text="+ Add", width=60, height=24,
                      font=ctk.CTkFont(size=11),
                      fg_color=_ACCENT, hover_color=_ACCENT_HOVER,
                      command=self._add_mat_override_row).pack(side="right")

        col_hdr_m = ctk.CTkFrame(mt, fg_color="transparent")
        col_hdr_m.pack(fill="x", padx=10, pady=(2, 0))
        col_hdr_m.grid_columnconfigure((0, 1, 2, 3), weight=1)
        for ci, txt in enumerate(["MID or MAT Type", "Stress Limit (MPa)", "Strain Limit", ""]):
            ctk.CTkLabel(col_hdr_m, text=txt, font=ctk.CTkFont(size=10), text_color="gray50",
                         anchor="w").grid(row=0, column=ci, sticky="w", padx=4)

        self._mat_override_frame = ctk.CTkFrame(mt, fg_color="transparent")
        self._mat_override_frame.pack(fill="x", padx=10, pady=(0, 8))
        self._mat_override_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self._mat_override_rows: list[dict[str, Any]] = []

        # Per-part override table
        pt = ctk.CTkFrame(sec.body, fg_color=("gray90", "gray17"), corner_radius=8)
        pt.pack(fill="x", pady=4)
        pt.grid_columnconfigure(0, weight=1)

        pt_hdr = ctk.CTkFrame(pt, fg_color="transparent")
        pt_hdr.pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkLabel(pt_hdr, text="Per-Part Overrides  (highest priority, overrides material & keyword)",
                     font=ctk.CTkFont(size=11, weight="bold"), anchor="w").pack(side="left")
        ctk.CTkButton(pt_hdr, text="+ Add", width=60, height=24,
                      font=ctk.CTkFont(size=11),
                      fg_color=_ACCENT, hover_color=_ACCENT_HOVER,
                      command=self._add_override_row).pack(side="right")

        # Column headers
        col_hdr = ctk.CTkFrame(pt, fg_color="transparent")
        col_hdr.pack(fill="x", padx=10, pady=(2, 0))
        col_hdr.grid_columnconfigure((0, 1, 2, 3), weight=1)
        for ci, txt in enumerate(["Part ID", "Stress Limit (MPa)", "Strain Limit", ""]):
            ctk.CTkLabel(col_hdr, text=txt, font=ctk.CTkFont(size=10), text_color="gray50",
                         anchor="w").grid(row=0, column=ci, sticky="w", padx=4)

        # Scrollable override rows
        self._override_frame = ctk.CTkFrame(pt, fg_color="transparent")
        self._override_frame.pack(fill="x", padx=10, pady=(0, 8))
        self._override_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self._override_rows: list[dict[str, Any]] = []  # [{pid_var, stress_var, strain_var, frame}]

        # ━━ 3. Rendering ━━
        sec = SectionCard(scroll, "Rendering")
        sec.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        # Top toggles
        tog = ctk.CTkFrame(sec.body, fg_color="transparent")
        tog.pack(fill="x", pady=2)
        self.var_render = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(tog, text="Enable Rendering", variable=self.var_render).pack(side="left")
        self.var_per_part = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(tog, text="Per-Part Render", variable=self.var_per_part).pack(side="left", padx=(24, 0))

        # Render params grid
        rg = ctk.CTkFrame(sec.body, fg_color=("gray90", "gray17"), corner_radius=8)
        rg.pack(fill="x", pady=4)

        # Row 0: Section axes + Fringe
        r0 = ctk.CTkFrame(rg, fg_color="transparent")
        r0.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(r0, text="Section Axes:").pack(side="left")
        self.var_ax_x = ctk.BooleanVar(value=True)
        self.var_ax_y = ctk.BooleanVar(value=True)
        self.var_ax_z = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(r0, text="X", variable=self.var_ax_x, width=50).pack(side="left", padx=4)
        ctk.CTkCheckBox(r0, text="Y", variable=self.var_ax_y, width=50).pack(side="left", padx=4)
        ctk.CTkCheckBox(r0, text="Z", variable=self.var_ax_z, width=50).pack(side="left", padx=4)

        ctk.CTkLabel(r0, text="Fringe:").pack(side="left", padx=(20, 4))
        self.var_fringe = ctk.StringVar(value="von_mises")
        ctk.CTkComboBox(r0, variable=self.var_fringe, values=_FRINGE_CHOICES, width=180).pack(side="left")

        # Row 1: Format + FPS + Resolution + Position
        r1 = ctk.CTkFrame(rg, fg_color="transparent")
        r1.pack(fill="x", padx=8, pady=(2, 6))

        ctk.CTkLabel(r1, text="Format:").pack(side="left")
        self.var_format = ctk.StringVar(value="mp4")
        ctk.CTkComboBox(r1, variable=self.var_format, values=_FORMAT_CHOICES, width=80).pack(side="left", padx=4)

        ctk.CTkLabel(r1, text="FPS:").pack(side="left", padx=(12, 2))
        self.var_fps = ctk.StringVar(value="30")
        ctk.CTkEntry(r1, textvariable=self.var_fps, width=50).pack(side="left", padx=2)

        ctk.CTkLabel(r1, text="Resolution:").pack(side="left", padx=(12, 2))
        self.var_res_w = ctk.StringVar(value="1920")
        ctk.CTkEntry(r1, textvariable=self.var_res_w, width=60).pack(side="left", padx=2)
        ctk.CTkLabel(r1, text="x").pack(side="left")
        self.var_res_h = ctk.StringVar(value="1080")
        ctk.CTkEntry(r1, textvariable=self.var_res_h, width=60).pack(side="left", padx=2)

        ctk.CTkLabel(r1, text="Position:").pack(side="left", padx=(12, 2))
        self.var_sec_pos = ctk.StringVar(value="center")
        ctk.CTkComboBox(r1, variable=self.var_sec_pos, values=_SECTION_POSITIONS, width=90).pack(side="left")

        # ━━ 4. Performance ━━
        sec = SectionCard(scroll, "Performance")
        sec.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        pf = ctk.CTkFrame(sec.body, fg_color="transparent")
        pf.pack(fill="x", pady=2)
        ctk.CTkLabel(pf, text="Analysis Threads:").pack(side="left")
        self.var_threads = ctk.StringVar(value="0")
        ctk.CTkEntry(pf, textvariable=self.var_threads, width=60).pack(side="left", padx=(4, 16))
        ctk.CTkLabel(pf, text="(0 = auto)").pack(side="left")

        ctk.CTkLabel(pf, text="Render Threads:").pack(side="left", padx=(24, 0))
        self.var_render_threads = ctk.StringVar(value="1")
        ctk.CTkEntry(pf, textvariable=self.var_render_threads, width=60).pack(side="left", padx=4)

        self.var_verbose = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(pf, text="Verbose", variable=self.var_verbose).pack(side="right")

        # ━━ 5. Action bar ━━
        bar = ctk.CTkFrame(scroll, fg_color="transparent")
        bar.grid(row=row, column=0, sticky="ew", padx=16, pady=8)
        row += 1

        ctk.CTkButton(bar, text="YAML Preview", width=120, fg_color=("gray70", "gray30"),
                      hover_color=("gray60", "gray40"), command=self._preview_yaml).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Save YAML", width=100, fg_color=("gray70", "gray30"),
                      hover_color=("gray60", "gray40"), command=self._save_yaml).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Load YAML", width=100, fg_color=("gray70", "gray30"),
                      hover_color=("gray60", "gray40"), command=self._load_yaml).pack(side="left", padx=4)

        self.btn_run = ctk.CTkButton(bar, text="   Run Analysis   ", height=38,
                                     font=ctk.CTkFont(size=14, weight="bold"),
                                     fg_color=_GREEN, hover_color=_GREEN_HOVER,
                                     command=self._run_analysis)
        self.btn_run.pack(side="right", padx=4)

        # ━━ 6. Log ━━
        log_card = SectionCard(scroll, "Log Output")
        log_card.grid(row=row, column=0, sticky="nsew", padx=12, pady=(4, 12))
        scroll.grid_rowconfigure(row, weight=1)
        row += 1

        self.log_text = ctk.CTkTextbox(log_card.body, height=180,
                                       font=ctk.CTkFont(family="Courier", size=11),
                                       state="disabled", wrap="word",
                                       corner_radius=6)
        self.log_text.pack(fill="both", expand=True)

        # Status bar
        self.status_var = ctk.StringVar(value="Ready")
        status = ctk.CTkLabel(self, textvariable=self.status_var,
                              font=ctk.CTkFont(size=11), text_color="gray50",
                              anchor="w", height=24)
        status.pack(fill="x", side="bottom", padx=12, pady=(0, 4))

    # ── Theme toggle ──────────────────────────────────────────────────

    def _toggle_theme(self, choice: str) -> None:
        ctk.set_appearance_mode(choice.lower())

    def _on_d3plot_changed(self, *_args) -> None:
        path = self.inp_d3plot.get()
        if path and not self.var_label.get():
            p = Path(path)
            if p.is_file():
                p = p.parent
            self.var_label.set(p.name)

    # ── Per-part override rows ────────────────────────────────────────

    def _add_override_row(self, pid: str = "", stress: str = "", strain: str = "") -> None:
        idx = len(self._override_rows)
        f = ctk.CTkFrame(self._override_frame, fg_color="transparent")
        f.grid(row=idx, column=0, columnspan=4, sticky="ew", pady=1)
        f.grid_columnconfigure((0, 1, 2), weight=1)

        pid_var = ctk.StringVar(value=pid)
        stress_var = ctk.StringVar(value=stress)
        strain_var = ctk.StringVar(value=strain)

        ctk.CTkEntry(f, textvariable=pid_var, width=80,
                     placeholder_text="e.g. 1").grid(row=0, column=0, sticky="w", padx=4)
        ctk.CTkEntry(f, textvariable=stress_var, width=120,
                     placeholder_text="MPa").grid(row=0, column=1, sticky="w", padx=4)
        ctk.CTkEntry(f, textvariable=strain_var, width=120,
                     placeholder_text="e.g. 0.05").grid(row=0, column=2, sticky="w", padx=4)

        row_data = {"pid_var": pid_var, "stress_var": stress_var, "strain_var": strain_var, "frame": f}
        ctk.CTkButton(f, text="X", width=28, height=24,
                      fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
                      font=ctk.CTkFont(size=11),
                      command=lambda rd=row_data: self._remove_override_row(rd)).grid(
            row=0, column=3, padx=4)
        self._override_rows.append(row_data)

    def _remove_override_row(self, row_data: dict) -> None:
        row_data["frame"].destroy()
        self._override_rows.remove(row_data)

    # ── Per-material override rows ───────────────────────────────────

    def _add_mat_override_row(self, key: str = "", stress: str = "", strain: str = "") -> None:
        idx = len(self._mat_override_rows)
        f = ctk.CTkFrame(self._mat_override_frame, fg_color="transparent")
        f.grid(row=idx, column=0, columnspan=4, sticky="ew", pady=1)
        f.grid_columnconfigure((0, 1, 2), weight=1)

        key_var = ctk.StringVar(value=key)
        stress_var = ctk.StringVar(value=stress)
        strain_var = ctk.StringVar(value=strain)

        ctk.CTkEntry(f, textvariable=key_var, width=140,
                     placeholder_text="e.g. ELASTIC or 2").grid(row=0, column=0, sticky="w", padx=4)
        ctk.CTkEntry(f, textvariable=stress_var, width=120,
                     placeholder_text="MPa").grid(row=0, column=1, sticky="w", padx=4)
        ctk.CTkEntry(f, textvariable=strain_var, width=120,
                     placeholder_text="e.g. 0.001").grid(row=0, column=2, sticky="w", padx=4)

        row_data = {"key_var": key_var, "stress_var": stress_var, "strain_var": strain_var, "frame": f}
        ctk.CTkButton(f, text="X", width=28, height=24,
                      fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
                      font=ctk.CTkFont(size=11),
                      command=lambda rd=row_data: self._remove_mat_override_row(rd)).grid(
            row=0, column=3, padx=4)
        self._mat_override_rows.append(row_data)

    def _remove_mat_override_row(self, row_data: dict) -> None:
        row_data["frame"].destroy()
        self._mat_override_rows.remove(row_data)

    def _get_mat_overrides(self) -> dict[str, dict]:
        """Collect per-material overrides from GUI table."""
        result: dict[str, dict] = {}
        for rd in self._mat_override_rows:
            key = rd["key_var"].get().strip()
            if not key:
                continue
            ov: dict[str, float] = {}
            try:
                sl = float(rd["stress_var"].get() or 0)
                if sl > 0:
                    ov["stress_limit"] = sl
            except ValueError:
                pass
            try:
                el = float(rd["strain_var"].get() or 0)
                if el > 0:
                    ov["strain_limit"] = el
            except ValueError:
                pass
            if ov:
                result[key] = ov
        return result

    def _get_overrides(self) -> dict[int, dict]:
        """Collect per-part overrides from GUI table."""
        result: dict[int, dict] = {}
        for rd in self._override_rows:
            pid_s = rd["pid_var"].get().strip()
            if not pid_s:
                continue
            try:
                pid = int(pid_s)
            except ValueError:
                continue
            ov: dict[str, float] = {}
            try:
                sl = float(rd["stress_var"].get() or 0)
                if sl > 0:
                    ov["stress_limit"] = sl
            except ValueError:
                pass
            try:
                el = float(rd["strain_var"].get() or 0)
                if el > 0:
                    ov["strain_limit"] = el
            except ValueError:
                pass
            if ov:
                result[pid] = ov
        return result

    # ── Browse (auto label) ───────────────────────────────────────────

    # The LabeledEntry handles its own browse; we just hook into d3plot
    # selection to auto-fill label.
    def _get_d3plot_with_autolabel(self) -> str:
        path = self.inp_d3plot.get()
        if path and not self.var_label.get():
            p = Path(path)
            if p.is_file():
                p = p.parent
            self.var_label.set(p.name)
        return path

    # ── Collect config ────────────────────────────────────────────────

    def _collect_config(self) -> dict:
        d3plot_path = self._get_d3plot_with_autolabel()
        if not d3plot_path:
            raise ValueError("D3plot 경로를 지정하세요.")

        p = Path(d3plot_path)
        if p.is_dir():
            candidates = sorted(p.glob("d3plot"))
            if not candidates:
                candidates = sorted(p.glob("d3plot*"))
            if candidates:
                d3plot_path = str(candidates[0])

        parts_str = self.var_parts.get().strip()
        parts: list[int] = []
        if parts_str:
            parts = [int(x.strip()) for x in parts_str.split(",") if x.strip()]

        type_to_name = {
            "von_mises": "Von Mises Stress", "eff_plastic_strain": "Effective Plastic Strain",
            "part_motion": "Part Motion", "element_quality": "Element Quality",
            "surface_stress": "Surface Stress", "surface_strain": "Surface Strain",
        }
        type_to_prefix = {
            "von_mises": "stress", "eff_plastic_strain": "strain",
            "part_motion": "motion", "element_quality": "quality",
            "surface_stress": "surface_stress", "surface_strain": "surface_strain",
        }

        analysis_jobs: list[dict] = []
        for key, var in self.analysis_vars.items():
            if var.get():
                job: dict[str, Any] = {
                    "name": type_to_name[key], "type": key, "output_prefix": type_to_prefix[key],
                }
                if parts:
                    job["parts"] = parts
                if self.var_part_pattern.get().strip():
                    job["part_pattern"] = self.var_part_pattern.get().strip()
                if key in ("surface_stress", "surface_strain"):
                    try:
                        d = [float(x) for x in self.var_surface_dir.get().split(",")]
                    except ValueError:
                        d = [0, 0, -1]
                    job["surface_direction"] = d
                    try:
                        job["surface_angle"] = float(self.var_surface_angle.get())
                    except ValueError:
                        job["surface_angle"] = 45.0
                analysis_jobs.append(job)

        if not analysis_jobs:
            raise ValueError("최소 한 개의 분석 타입을 선택하세요.")

        render_enabled = self.var_render.get()
        render_jobs: list[dict] = []
        if render_enabled:
            axes = []
            if self.var_ax_x.get(): axes.append("x")
            if self.var_ax_y.get(): axes.append("y")
            if self.var_ax_z.get(): axes.append("z")
            fringe = self.var_fringe.get()
            fmt = self.var_format.get()
            try: fps = int(self.var_fps.get())
            except ValueError: fps = 30
            try: res = [int(self.var_res_w.get()), int(self.var_res_h.get())]
            except ValueError: res = [1920, 1080]
            sec_pos = self.var_sec_pos.get() or "center"
            axis_label = {"x": "X", "y": "Y", "z": "Z"}

            for ax in axes:
                ext = fmt
                rj: dict[str, Any] = {
                    "name": f"{axis_label[ax]}-Section {fringe}", "type": "section_view",
                    "fringe": fringe, "section": {"axis": ax, "position": sec_pos},
                    "states": "all",
                    "output": {"format": fmt, "filename": f"section_{ax}_{fringe}.{ext}",
                               "fps": fps, "resolution": res},
                }
                if parts: rj["parts"] = parts
                if self.var_part_pattern.get().strip():
                    rj["part_pattern"] = self.var_part_pattern.get().strip()
                render_jobs.append(rj)

            if self.var_per_part.get():
                for ax in axes:
                    rj = {
                        "name": f"Per-Part {axis_label[ax]}-Section", "type": "section_view",
                        "fringe": fringe, "section": {"axis": ax, "position": sec_pos},
                        "states": "all",
                        "output": {"format": fmt, "filename": f"per_part_{ax}_{fringe}.{ext}",
                                   "fps": fps, "resolution": res},
                    }
                    if self.var_part_pattern.get().strip():
                        rj["part_pattern"] = self.var_part_pattern.get().strip()
                    render_jobs.append(rj)

        try:
            stress_g = float(self.var_yield.get() or 0)
        except ValueError:
            stress_g = 0.0
        try:
            strain_g = float(self.var_strain_limit.get() or 0.002)
        except ValueError:
            strain_g = 0.002

        return {
            "d3plot": d3plot_path,
            "output_dir": self.inp_output.get() or "./single_report",
            "label": self.var_label.get().strip(),
            "yield_stress": stress_g,
            "strain_limit": strain_g,
            "threads": int(self.var_threads.get() or 0),
            "render_threads": int(self.var_render_threads.get() or 1),
            "verbose": self.var_verbose.get(),
            "lsprepost_path": "",
            "analysis_jobs": analysis_jobs,
            "render_enabled": render_enabled,
            "render_jobs": render_jobs,
            "design_criteria": {
                "global_stress_limit": stress_g,
                "global_strain_limit": strain_g,
                "material_overrides": self._get_mat_overrides(),
                "overrides": self._get_overrides(),
            },
        }

    # ── YAML actions ──────────────────────────────────────────────────

    def _preview_yaml(self) -> None:
        try:
            cfg = self._collect_config()
        except ValueError as e:
            messagebox.showwarning("Input Error", str(e))
            return
        yaml_str = build_yaml(cfg)

        win = ctk.CTkToplevel(self)
        win.title("YAML Preview")
        win.geometry("640x520")
        win.transient(self)

        txt = ctk.CTkTextbox(win, font=ctk.CTkFont(family="Courier", size=11), wrap="none",
                             corner_radius=8)
        txt.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        txt.insert("0.0", yaml_str)

        bf = ctk.CTkFrame(win, fg_color="transparent")
        bf.pack(fill="x", padx=10, pady=(4, 10))

        def _copy():
            win.clipboard_clear()
            win.clipboard_append(txt.get("0.0", "end"))
            self.status_var.set("Copied to clipboard")

        ctk.CTkButton(bf, text="Copy", width=80, command=_copy).pack(side="left")
        ctk.CTkButton(bf, text="Close", width=80, fg_color=("gray70", "gray30"),
                      hover_color=("gray60", "gray40"), command=win.destroy).pack(side="right")

    def _save_yaml(self) -> None:
        try:
            cfg = self._collect_config()
        except ValueError as e:
            messagebox.showwarning("Input Error", str(e))
            return
        yaml_str = build_yaml(cfg)
        path = filedialog.asksaveasfilename(
            title="Save YAML", defaultextension=".yaml",
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*")],
        )
        if path:
            Path(path).write_text(yaml_str, encoding="utf-8")
            self._log(f"YAML saved: {path}")
            self.status_var.set(f"YAML saved: {path}")

    def _load_yaml(self) -> None:
        path = filedialog.askopenfilename(
            title="Load YAML",
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*")],
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
            self._parse_yaml_into_gui(text)
            self._log(f"YAML loaded: {path}")
            self.status_var.set(f"YAML loaded: {path}")
        except Exception as e:
            messagebox.showerror("YAML Parse Error", str(e))

    def _parse_yaml_into_gui(self, text: str) -> None:
        m = re.search(r'd3plot:\s*["\']?([^"\'#\n]+)', text)
        if m:
            self.inp_d3plot.set(m.group(1).strip())

        m = re.search(r'output:.*?directory:\s*["\']?([^"\'#\n]+)', text, re.DOTALL)
        if m:
            self.inp_output.set(m.group(1).strip())

        m = re.search(r'(?<!\w)threads:\s*(\d+)', text)
        if m:
            self.var_threads.set(m.group(1))

        m = re.search(r'render_threads:\s*(\d+)', text)
        if m:
            self.var_render_threads.set(m.group(1))

        m = re.search(r'verbose:\s*(true|false)', text, re.IGNORECASE)
        if m:
            self.var_verbose.set(m.group(1).lower() == "true")

        # Design criteria
        m = re.search(r'global_stress_limit:\s*([\d.eE+\-]+)', text)
        if m:
            self.var_yield.set(m.group(1))
        m = re.search(r'global_strain_limit:\s*([\d.eE+\-]+)', text)
        if m:
            self.var_strain_limit.set(m.group(1))

        # Per-material overrides
        for rd in list(self._mat_override_rows):
            self._remove_mat_override_row(rd)
        mo_start = text.find("material_overrides:")
        if mo_start >= 0:
            mo_block = text[mo_start:]
            # Truncate at next sibling key (2-space indented)
            sib = re.search(r'\n  \w', mo_block[len("material_overrides:"):])
            if sib:
                mo_block = mo_block[:len("material_overrides:") + sib.start()]
            for key_m in re.finditer(r'^\s{4,}(\w+):\s*$', mo_block, re.MULTILINE):
                key = key_m.group(1)
                after = mo_block[key_m.end():key_m.end() + 300]
                after = re.split(r'\n\s{4}\w+:|^\S', after, maxsplit=1, flags=re.MULTILINE)[0]
                sl = re.search(r'stress_limit:\s*([\d.eE+\-]+)', after)
                el = re.search(r'strain_limit:\s*([\d.eE+\-]+)', after)
                self._add_mat_override_row(
                    key=key,
                    stress=sl.group(1) if sl else "",
                    strain=el.group(1) if el else "",
                )

        # Per-part overrides
        for rd in list(self._override_rows):
            self._remove_override_row(rd)
        # Find "overrides:" that is NOT "material_overrides:"
        for ov_m in re.finditer(r'(?<!material_)overrides:', text):
            ov_block = text[ov_m.start():]
            for pid_m in re.finditer(r'^\s{4,}(\d+):\s*$', ov_block, re.MULTILINE):
                pid = pid_m.group(1)
                after = ov_block[pid_m.end():pid_m.end() + 300]
                after = re.split(r'\n\s{4}\d+:|^\S', after, maxsplit=1, flags=re.MULTILINE)[0]
                sl = re.search(r'stress_limit:\s*([\d.eE+\-]+)', after)
                el = re.search(r'strain_limit:\s*([\d.eE+\-]+)', after)
                self._add_override_row(
                    pid=pid,
                    stress=sl.group(1) if sl else "",
                    strain=el.group(1) if el else "",
                )
            break

        for key, var in self.analysis_vars.items():
            var.set(bool(re.search(rf'type:\s*{key}\b', text)))

        self.var_render.set(bool(re.search(r'render_jobs:', text)))

        m = re.search(r'fringe:\s*(\w+)', text)
        if m:
            self.var_fringe.set(m.group(1))

    # ── Run analysis ──────────────────────────────────────────────────

    def _run_analysis(self) -> None:
        if self._running:
            messagebox.showinfo("Running", "Analysis is already running.")
            return

        try:
            cfg = self._collect_config()
        except ValueError as e:
            messagebox.showwarning("Input Error", str(e))
            return

        import tempfile
        yaml_str = build_yaml(cfg)
        tmp_yaml = Path(tempfile.mkdtemp()) / "single_analyzer_config.yaml"
        tmp_yaml.write_text(yaml_str, encoding="utf-8")

        cmd = [sys.executable, "-m", "single_analyzer"]
        cmd.append(cfg["d3plot"])
        cmd.extend(["--output", cfg["output_dir"]])

        if cfg["label"]:
            cmd.extend(["--label", cfg["label"]])
        if cfg.get("yield_stress", 0.0) > 0:
            cmd.extend(["--yield-stress", str(cfg["yield_stress"])])
        if cfg.get("strain_limit", 0.0) > 0:
            cmd.extend(["--strain-limit", str(cfg["strain_limit"])])
        # Per-material design overrides via JSON file
        mat_overrides = cfg.get("design_criteria", {}).get("material_overrides", {})
        if mat_overrides:
            import json
            mo_path = Path(tempfile.mkdtemp()) / "material_overrides.json"
            mo_path.write_text(json.dumps(mat_overrides, indent=2), encoding="utf-8")
            cmd.extend(["--material-overrides", str(mo_path)])
        # Per-part design overrides via JSON file
        overrides = cfg.get("design_criteria", {}).get("overrides", {})
        if overrides:
            import json
            ov_path = Path(tempfile.mkdtemp()) / "design_overrides.json"
            ov_path.write_text(json.dumps(overrides, indent=2), encoding="utf-8")
            cmd.extend(["--design-overrides", str(ov_path)])
        if cfg.get("threads", 0) > 0:
            cmd.extend(["--ua-threads", str(cfg["threads"])])
        if cfg.get("render_threads", 1) > 1:
            cmd.extend(["--render-threads", str(cfg["render_threads"])])
        if not cfg.get("render_enabled"):
            cmd.append("--no-render")
        if self.var_per_part.get():
            cmd.append("--per-part-render")
        if self.var_part_pattern.get().strip():
            cmd.extend(["--part-pattern", self.var_part_pattern.get().strip()])
        parts_str = self.var_parts.get().strip()
        if parts_str:
            cmd.extend(["--parts"] + [x.strip() for x in parts_str.split(",") if x.strip()])
        if self.analysis_vars.get("element_quality", ctk.BooleanVar()).get():
            cmd.append("--element-quality")
        if cfg.get("verbose"):
            cmd.append("--verbose")

        self._log(f"Command: {' '.join(cmd)}\n")
        self.status_var.set("Running analysis...")
        self._running = True
        self.btn_run.configure(state="disabled", text="   Running...   ")

        thread = threading.Thread(target=self._run_subprocess, args=(cmd,), daemon=True)
        thread.start()

    def _run_subprocess(self, cmd: list[str]) -> None:
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            for line in proc.stdout:  # type: ignore[union-attr]
                self._log(line.rstrip("\n"))
            proc.wait()
            rc = proc.returncode
            if rc == 0:
                self._log("\nAnalysis completed successfully!")
                self.after(0, lambda: self.status_var.set("Analysis completed"))
                self.after(0, lambda: messagebox.showinfo("Done", "Analysis completed successfully."))
            else:
                self._log(f"\nAnalysis failed (exit code {rc})")
                self.after(0, lambda: self.status_var.set(f"Analysis failed (exit {rc})"))
                self.after(0, lambda: messagebox.showerror("Error", f"Analysis failed (exit code {rc})"))
        except Exception as e:
            self._log(f"\nExecution error: {e}")
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self._running = False
            self.after(0, lambda: self.btn_run.configure(state="normal", text="   Run Analysis   "))

    # ── Logging ───────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        def _append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        if threading.current_thread() is threading.main_thread():
            _append()
        else:
            self.after(0, _append)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def launch() -> None:
    app = SingleAnalyzerApp()
    app.mainloop()


if __name__ == "__main__":
    launch()
