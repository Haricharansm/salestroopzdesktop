# agent/pyinstaller/salestroopz_api.spec
# Build: salestroopz_api.exe

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent.parent  # -> agent/

# --- Hidden imports (prevent "module not found" at runtime) ---
hiddenimports = []
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("starlette")
hiddenimports += collect_submodules("pydantic")
hiddenimports += collect_submodules("sqlalchemy")
hiddenimports += collect_submodules("msal")
hiddenimports += collect_submodules("requests")

# Your internal packages
hiddenimports += collect_submodules("app")
hiddenimports += collect_submodules("app.api")
hiddenimports += collect_submodules("app.m365")
hiddenimports += collect_submodules("app.llm")
hiddenimports += collect_submodules("app.schemas")
hiddenimports += collect_submodules("app.db")
hiddenimports += collect_submodules("app.workers")
hiddenimports += collect_submodules("app.queue")

a = Analysis(
    [str(ROOT / "api_entry.py")],   # ✅ absolute path
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
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
    console=True,
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
