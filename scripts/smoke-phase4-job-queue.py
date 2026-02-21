#!/usr/bin/env python3
"""Phase 4: смоук-тесты очереди задач (атомарность claim_next, retry run_after, fail_retry)."""

import os
import sys
import tempfile
import time
from pathlib import Path
from multiprocessing import Process, Queue

# Корень проекта в path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.job_queue import JobQueue, JobRecord, STATUS_PENDING, STATUS_RUNNING


def _claim_once(db_path: str, result_queue: Queue) -> None:
    q = JobQueue(Path(db_path))
    job = q.claim_next()
    result_queue.put(job.id if job else None)


def test_1_concurrent_claim() -> bool:
    """Два воркера одновременно на 1 pending job — job забирается ровно один раз."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        q = JobQueue(Path(db_path))
        q.enqueue("upload_video", {"video_id": 1})
        result_queue = Queue()
        p1 = Process(target=_claim_once, args=(db_path, result_queue))
        p2 = Process(target=_claim_once, args=(db_path, result_queue))
        p1.start()
        p2.start()
        p1.join(timeout=5)
        p2.join(timeout=5)
        r1 = result_queue.get_nowait()
        r2 = result_queue.get_nowait()
        claimed = [x for x in (r1, r2) if x is not None]
        return len(claimed) == 1
    finally:
        try:
            os.unlink(db_path)
        except Exception:
            pass


def test_2_retry_run_after() -> bool:
    """fail_retry выставляет run_after; до времени задача не забирается, после — забирается."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        from datetime import datetime, timezone, timedelta
        q = JobQueue(Path(db_path))
        jid = q.enqueue("upload_video", {"video_id": 1})
        job = q.claim_next()
        if not job or job.id != jid:
            return False
        run_after = datetime.now(timezone.utc) + timedelta(seconds=2)
        q.fail_retry(job.id, "retry", run_after=run_after)
        # Сразу не должна забираться
        again = q.claim_next()
        if again is not None:
            return False
        time.sleep(2.5)
        again = q.claim_next()
        return again is not None and again.id == jid
    finally:
        try:
            os.unlink(db_path)
        except Exception:
            pass


def test_3_fail_retry_state() -> bool:
    """После fail_retry: статус pending, attempt+1, error заполнен, run_after в будущем."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        from datetime import datetime, timezone, timedelta
        q = JobQueue(Path(db_path))
        jid = q.enqueue("upload_video", {"video_id": 1})
        job = q.claim_next()
        if not job or job.id != jid:
            return False
        run_after = datetime.now(timezone.utc) + timedelta(minutes=5)
        q.fail_retry(job.id, "PUBLISH_FAILED", run_after=run_after)
        row = q.get_job(jid)
        if not row:
            return False
        return (
            row.status == STATUS_PENDING
            and row.attempt == 1
            and (row.error or "").strip() != ""
            and row.run_after is not None
        )
    finally:
        try:
            os.unlink(db_path)
        except Exception:
            pass


def main() -> int:
    ok = 0
    for name, fn in [
        ("concurrent_claim", test_1_concurrent_claim),
        ("retry_run_after", test_2_retry_run_after),
        ("fail_retry_state", test_3_fail_retry_state),
    ]:
        try:
            if fn():
                print(f"[OK] {name}")
                ok += 1
            else:
                print(f"[FAIL] {name}")
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
    print(f"\n{ok}/3 passed")
    return 0 if ok == 3 else 1


if __name__ == "__main__":
    sys.exit(main())
