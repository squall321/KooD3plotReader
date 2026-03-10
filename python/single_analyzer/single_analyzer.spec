# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for single_analyzer GUI executable."""

import sys
from pathlib import Path

block_cipher = None

# Collect customtkinter data files (themes, assets)
import importlib
ctk_path = Path(importlib.import_module("customtkinter").__file__).parent
ctk_datas = [(str(ctk_path), "customtkinter")]

a = Analysis(
    ["entry_point.py"],
    pathex=["."],
    binaries=[],
    datas=ctk_datas,
    hiddenimports=[
        "single_analyzer",
        "single_analyzer.core",
        "single_analyzer.core.sim_detector",
        "single_analyzer.core.glstat_reader",
        "single_analyzer.core.d3plot_reader",
        "single_analyzer.core.binout_reader",
        "single_analyzer.core.keyword_parser",
        "single_analyzer.render",
        "single_analyzer.render.job_builder",
        "single_analyzer.report",
        "single_analyzer.report.models",
        "single_analyzer.report.html_report",
        "single_analyzer.report.batch_report",
        "single_analyzer.gui",
        "single_analyzer.gui.app",
        "customtkinter",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "scipy", "pandas", "PIL", "cv2"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="single_analyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # console=True so CLI mode also works; GUI launches tkinter window
    icon=None,
)
