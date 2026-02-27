# agent/api_entry.py
import os
import sys
from pathlib import Path

import uvicorn


def _ensure_userdata_defaults():
    user_dir = os.getenv("SALESTROOPZ_USERDATA_DIR", "").strip()
    if user_dir:
        p = Path(user_dir).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("SQLITE_DB_FILE", str(p / "salestroopz.db"))
        os.environ.setdefault("TOKEN_CACHE_PATH", str(p / "token_cache.json"))
    else:
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

    # ✅ Import the FastAPI app object directly
    from main import app  # main.py in agent/ defines app = FastAPI(...)

    uvicorn.run(
        app,
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
