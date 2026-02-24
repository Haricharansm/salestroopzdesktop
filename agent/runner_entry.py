# agent/runner_entry.py
import os
import sys
from pathlib import Path


def _ensure_userdata_defaults():
    """
    Electron packaged mode sets:
      - SALESTROOPZ_USERDATA_DIR
      - SQLITE_DB_FILE
      - TOKEN_CACHE_PATH

    Provide safe fallbacks for CLI/dev.
    """
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

    # Run the same entrypoint Electron uses in dev mode.
    from worker_main import main as worker_main

    worker_main()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[salestroopz_runner] stopped")
    except Exception as e:
        print(f"[salestroopz_runner] fatal: {e}", file=sys.stderr)
        raise
