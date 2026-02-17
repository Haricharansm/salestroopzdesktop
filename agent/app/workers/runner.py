import time
import json
import signal
import traceback
import socket
import os
from datetime import datetime, timedelta

from app.queue.job_queue import claim_next_job, mark_done, mark_failed
from app.db.sqlite import log_event

from dotenv import load_dotenv
load_dotenv()


# Import handlers
from app.workers.handlers.generate_copy import handle_generate_copy
from app.workers.handlers.send_email import handle_send_email
from app.workers.handlers.poll_replies import handle_poll_replies
from app.workers.handlers.tick import handle_tick
from app.workers.handlers.decide_next import handle_decide_next

HANDLERS = {
    "tick": handle_tick,
    "generate_copy": handle_generate_copy,
    "send_email": handle_send_email,
    "poll_replies": handle_poll_replies,
    "decide_next": handle_decide_next
}

# ----------------------------
# Runner identity + shutdown
# ----------------------------
RUNNER_ID = f"{socket.gethostname()}:{os.getpid()}"
_STOP = False

def _handle_stop(signum, frame):
    global _STOP
    _STOP = True

# Best-effort: handle Ctrl+C and termination
signal.signal(signal.SIGINT, _handle_stop)
try:
    signal.signal(signal.SIGTERM, _handle_stop)
except Exception:
    # SIGTERM may not exist on some Windows Python builds
    pass


def backoff_seconds(attempt: int) -> int:
    # 1,2,4,8,16,30,60...
    return min(60, 2 ** max(0, attempt - 1))


def run_forever(poll_interval: float = 0.5, heartbeat_seconds: int = 15):
    """
    Durable worker loop:
    - claims jobs with leases
    - executes handlers
    - retries with exponential backoff
    - emits operational events
    - supports clean shutdown (Electron quit)
    """
    log_event("runner.started", message="Runner loop started", data={"runner_id": RUNNER_ID})

    last_heartbeat = 0.0

    while not _STOP:
        now = time.time()
        if now - last_heartbeat >= heartbeat_seconds:
            last_heartbeat = now
            try:
                log_event("runner.heartbeat", message="alive", data={"runner_id": RUNNER_ID})
            except Exception:
                pass

        job = claim_next_job()
        if not job:
            time.sleep(poll_interval)
            continue

        job_id = getattr(job, "id", None)
        job_type = getattr(job, "job_type", None)

        try:
            payload = json.loads(job.payload_json or "{}")
        except Exception:
            payload = {}
            # If payload is corrupt, fail the job permanently
            err = "Invalid payload_json (not parseable JSON)"
            mark_failed(job_id, err=err, retry_at=None)
            log_event(
                "job.payload_invalid",
                level="ERROR",
                job_id=job_id,
                message=err,
                data={"job_type": job_type, "payload_json": job.payload_json},
            )
            continue

        handler = HANDLERS.get(job_type)
        if not handler:
            err = f"No handler for job_type={job_type}"
            mark_failed(job_id, err=err, retry_at=None)
            log_event("job.no_handler", level="ERROR", job_id=job_id, message=err, data={"payload": payload})
            continue

        log_event("job.start", job_id=job_id, message=f"Executing {job_type}", data={"payload": payload})

        try:
            # Handlers should be idempotent.
            handler(payload)
            mark_done(job_id)
            log_event("job.success", job_id=job_id, message=f"Completed {job_type}")

        except Exception as e:
            attempt_next = (job.attempts or 0) + 1
            retry_at = datetime.utcnow() + timedelta(seconds=backoff_seconds(attempt_next))

            # include traceback to make debugging easier
            tb = traceback.format_exc(limit=12)
            err = f"{type(e).__name__}: {str(e)}"

            mark_failed(job_id, err=err, retry_at=retry_at)

            log_event(
                "job.error",
                level="ERROR",
                job_id=job_id,
                message=err,
                data={
                    "job_type": job_type,
                    "payload": payload,
                    "attempt_next": attempt_next,
                    "retry_at": retry_at.isoformat(),
                    "traceback": tb,
                },
            )

        # small yield so we don't spin too hard in tight loops
        time.sleep(0.01)

    # clean shutdown
    log_event("runner.stopped", level="WARN", message="Runner loop stopped", data={"runner_id": RUNNER_ID})


if __name__ == "__main__":
    run_forever()
