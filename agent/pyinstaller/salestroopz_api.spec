# agent/pyinstaller/salestroopz_api.spec
# Build: salestroopz_api.exe
# Purpose: runs FastAPI via uvicorn, no Python required on target machine.

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

ROOT = Path(__file__).resolve().parents[1]  # agent/
APP_DIR = ROOT / "app"

hiddenimports = []
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("starlette")
hiddenimports += collect_submodules("pydantic")
hiddenimports += collect_submodules("sqlalchemy")
hiddenimports += collect_submodules("msal")
hiddenimports += collect_submodules("requests")

# Include your app package + any non-py assets (templates, etc.)
datas = []
datas += collect_data_files("app", include_py_files=True)

a = Analysis(
    ["api_entry.py"],  # we will add this entry script next
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
    console=True,   # keep console ON for v1 so we can diagnose startup issues in packaged builds
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
