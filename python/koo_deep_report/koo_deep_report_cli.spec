# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for koo_deep_report CLI-only executable (no GUI deps)."""

block_cipher = None

a = Analysis(
    ["entry_point.py"],
    pathex=["."],
    binaries=[],
    datas=[],
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib", "numpy", "scipy", "pandas", "PIL", "cv2",
        "customtkinter", "tkinter", "koo_deep_report.gui",
    ],
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
    console=True,
    icon=None,
)
