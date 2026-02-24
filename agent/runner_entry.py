# agent/runner_entry.py
import os
import sys
import time
from pathlib import Path


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

    # Preferred: call your existing worker entry if it exists.
    # This is what Electron runs in dev: python -u agent/worker_main.py
    try:
        import worker_main  # noqa: F401
        if hasattr(worker_main, "main"):
            print("[salestroopz_runner] starting worker_main.main()")
            worker_main.main()
            return
        if hasattr(worker_main, "run"):
            print("[salestroopz_runner] starting worker_main.run()")
            worker_main.run()
            return
        print("[salestroopz_runner] worker_main imported but no main()/run() found; falling back to idle loop")
    except Exception as e:
        print(f"[salestroopz_runner] worker_main not available ({e}); falling back to idle loop")

    # Fallback: keep process alive (so Electron doesn't constantly respawn it)
    print("[salestroopz_runner] idle loop running (no worker_main wired).")
    while True:
        time.sleep(10)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[salestroopz_runner] stopped")
    except Exception as e:
        print(f"[salestroopz_runner] fatal: {e}", file=sys.stderr)
        raise
