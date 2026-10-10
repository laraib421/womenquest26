"""Background job runner so the web UI can kick off the full Level 1 + Level 2
pipeline (the actual competition run) and show live progress, instead of only
demoing one bill at a time."""
import threading
import time
import uuid

from .pipeline import run_level1, run_level2

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def _update(job_id, **kwargs):
    with _LOCK:
        _JOBS[job_id].update(kwargs)


def _log(job_id, msg):
    with _LOCK:
        _JOBS[job_id]["log"].append(msg)
        _JOBS[job_id]["log"] = _JOBS[job_id]["log"][-200:]


def _run(job_id, bills_dir, l1_template, l1_out, l2_template, l2_out, cache_dir):
    try:
        _update(job_id, stage="level1", status="running")
        _log(job_id, "Starting Level 1 extraction...")

        def p1(done, total, bill_id, status):
            _update(job_id, l1_done=done, l1_total=total)
            _log(job_id, f"[Level 1] {done}/{total} {bill_id}: {status}")

        run_level1(bills_dir, l1_template, l1_out, cache_dir, on_progress=p1)

        _update(job_id, stage="level2")
        _log(job_id, "Starting Level 2 question answering...")

        def p2(done, total, bill_id, status):
            _update(job_id, l2_done=done, l2_total=total)
            _log(job_id, f"[Level 2] {done}/{total} {bill_id}: {status}")

        run_level2(bills_dir, l2_template, l2_out, cache_dir, on_progress=p2)

        _update(job_id, stage="done", status="done", finished_at=time.time())
        _log(job_id, "Done. Both CSV files written.")
    except Exception as e:
        _update(job_id, stage="error", status="error", error=str(e))
        _log(job_id, f"FAILED: {e}")


def start_job(bills_dir, l1_template, l1_out, l2_template, l2_out, cache_dir="data/.cache") -> str:
    job_id = uuid.uuid4().hex[:8]
    _JOBS[job_id] = {
        "status": "running", "stage": "level1",
        "l1_done": 0, "l1_total": 0, "l2_done": 0, "l2_total": 0,
        "log": [], "started_at": time.time(), "l1_out": l1_out, "l2_out": l2_out,
    }
    t = threading.Thread(target=_run, args=(job_id, bills_dir, l1_template, l1_out, l2_template, l2_out, cache_dir), daemon=True)
    t.start()
    return job_id


def get_status(job_id: str) -> dict | None:
    with _LOCK:
        return dict(_JOBS[job_id]) if job_id in _JOBS else None
