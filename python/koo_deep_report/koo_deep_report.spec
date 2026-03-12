# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for koo_deep_report GUI executable."""

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
        "koo_deep_report",
        "koo_deep_report.core",
        "koo_deep_report.core.sim_detector",
        "koo_deep_report.core.glstat_reader",
        "koo_deep_report.core.d3plot_reader",
        "koo_deep_report.core.binout_reader",
        "koo_deep_report.core.keyword_parser",
        "koo_deep_report.render",
        "koo_deep_report.render.job_builder",
        "koo_deep_report.report",
        "koo_deep_report.report.models",
        "koo_deep_report.report.html_report",
        "koo_deep_report.report.batch_report",
        "koo_deep_report.gui",
        "koo_deep_report.gui.app",
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
    name="koo_deep_report",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # console=True so CLI mode also works; GUI launches tkinter window
    icon=None,
)
