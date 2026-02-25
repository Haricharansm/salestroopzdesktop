# agent/pyinstaller/salestroopz_api.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = Path(SPECPATH).resolve()              # ...\agent\pyinstaller
AGENT_DIR = SPEC_DIR.parent                      # ...\agent
ENTRY = AGENT_DIR / "api_entry.py"               # ...\agent\api_entry.py

print(">>> SPEC_DIR:", SPEC_DIR)
print(">>> AGENT_DIR:", AGENT_DIR)
print(">>> ENTRY:", ENTRY, "exists:", ENTRY.exists())

hiddenimports = []
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("starlette")
hiddenimports += collect_submodules("pydantic")
hiddenimports += collect_submodules("sqlalchemy")
hiddenimports += collect_submodules("msal")
hiddenimports += collect_submodules("requests")
hiddenimports += collect_submodules("app")

a = Analysis(
    [str(ENTRY)],               # ✅ absolute path
    pathex=[str(AGENT_DIR)],    # ✅ agent/ on sys.path
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
    strip=False,
    upx=True,
    console=True
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="salestroopz_api",
)
