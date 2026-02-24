# agent/pyinstaller/salestroopz_api.spec
# Build: salestroopz_api.exe
# Purpose: runs FastAPI via uvicorn, no Python required on target machine.

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# PyInstaller provides SPECPATH (directory containing this spec file)
ROOT = Path(SPECPATH).resolve().parents[0].parents[0]  # -> agent/pyinstaller/.. = agent/
# Explanation:
#   SPECPATH = <repo>\agent\pyinstaller
#   parents[0] = <repo>\agent\pyinstaller
#   parents[1] = <repo>\agent
ROOT = Path(SPECPATH).resolve().parent  # <repo>\agent\pyinstaller
ROOT = ROOT.parent  # <repo>\agent

hiddenimports = []
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("starlette")
hiddenimports += collect_submodules("pydantic")
hiddenimports += collect_submodules("sqlalchemy")
hiddenimports += collect_submodules("msal")
hiddenimports += collect_submodules("requests")

# include your internal packages (so routers + m365 + llm aren't stripped)
hiddenimports += collect_submodules("app.api")
hiddenimports += collect_submodules("app.m365")
hiddenimports += collect_submodules("app.llm")
hiddenimports += collect_submodules("app.schemas")
hiddenimports += collect_submodules("app.db")
hiddenimports += collect_submodules("app.workers")
hiddenimports += collect_submodules("app.queue")

datas = []
datas += collect_data_files("app", include_py_files=True)

a = Analysis(
    ["api_entry.py"],  # agent/api_entry.py
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
    name="salestroopz_api",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # keep console ON for v1 visibility
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="salestroopz_api",
)
