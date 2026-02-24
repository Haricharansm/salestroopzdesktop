# agent/api_entry.py
import os
import sys
from pathlib import Path

import uvicorn


def _ensure_userdata_defaults():
    """
    In packaged mode Electron sets:
      - SALESTROOPZ_USERDATA_DIR
      - SQLITE_DB_FILE
      - TOKEN_CACHE_PATH

    For safety (and dev CLI), we provide sane fallbacks.
    """
    user_dir = os.getenv("SALESTROOPZ_USERDATA_DIR", "").strip()
    if user_dir:
        p = Path(user_dir).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("SQLITE_DB_FILE", str(p / "salestroopz.db"))
        os.environ.setdefault("TOKEN_CACHE_PATH", str(p / "token_cache.json"))
    else:
        # dev fallback: local ./data (relative to agent/)
        root = Path(__file__).resolve().parent
        data = (root / "data").resolve()
        data.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("SQLITE_DB_FILE", str(data / "salestroopz.db"))
        os.environ.setdefault("TOKEN_CACHE_PATH", str(data / "token_cache.json"))


def main():
    _ensure_userdata_defaults()

    port_raw = str(os.getenv("SALESTROOPZ_API_PORT", "8715")).strip()
    port_digits = "".join([c for c in port_raw if c.isdigit()]) or "8715"
    port = int(port_digits)

    # Your FastAPI instance is `app` in module `app.api_main`
    # If your file name differs, change only the string below.
    app_path = os.getenv("SALESTROOPZ_FASTAPI_APP", "app.api_main:app")

    uvicorn.run(
        app_path,
        host="127.0.0.1",
        port=port,
        log_level=os.getenv("SALESTROOPZ_LOG_LEVEL", "info"),
        access_log=True,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[salestroopz_api] fatal: {e}", file=sys.stderr)
        raise
