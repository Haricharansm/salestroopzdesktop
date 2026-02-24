# agent/pyinstaller/salestroopz_runner.spec
# Build: salestroopz_runner.exe
# Purpose: background worker loop (job queue / scheduler) - no Python required.

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

ROOT = Path(SPECPATH).resolve().parent.parent  # -> agent/

hiddenimports = []
hiddenimports += collect_submodules("sqlalchemy")
hiddenimports += collect_submodules("pydantic")
hiddenimports += collect_submodules("requests")

hiddenimports += collect_submodules("app.workers")
hiddenimports += collect_submodules("app.queue")
hiddenimports += collect_submodules("app.m365")
hiddenimports += collect_submodules("app.db")

datas = []
datas += collect_data_files("app", include_py_files=True)

a = Analysis(
    ["runner_entry.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="salestroopz_runner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="salestroopz_runner",
)
