"""Очередь задач (Phase 4). SQLite backend, контракт API для возможной замены на Redis."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import logging

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


@dataclass
class JobRecord:
    """Запись о задаче в очереди."""
    id: int
    type: str
    payload_json: str
    status: str
    attempt: int
    run_after: Optional[datetime]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime

    def payload(self) -> dict:
        return json.loads(self.payload_json) if self.payload_json else {}


class JobQueue:
    """Очередь задач в SQLite. Контракт: enqueue, claim_next, complete, fail_retry."""

    def __init__(self, db_path: Path = Path("videos.db")):
        self.db_path = Path(db_path)
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempt INTEGER NOT NULL DEFAULT 0,
                run_after TEXT,
                error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_type ON jobs(status, type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_run_after ON jobs(run_after)")
        try:
            cursor.execute("ALTER TABLE jobs ADD COLUMN result_json TEXT")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        conn.close()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def enqueue(
        self,
        job_type: str,
        payload: dict,
        run_after: Optional[datetime] = None,
    ) -> int:
        """Добавить задачу в очередь. Возвращает id задачи."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        payload_json = json.dumps(payload, ensure_ascii=False)
        run_after_str = run_after.isoformat() if run_after else None
        now = self._now_iso()
        cursor.execute(
            """
            INSERT INTO jobs (type, payload_json, status, attempt, run_after, created_at, updated_at)
            VALUES (?, ?, ?, 0, ?, ?, ?)
            """,
            (job_type, payload_json, STATUS_PENDING, run_after_str, now, now),
        )
        job_id = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.debug("enqueue job id=%s type=%s", job_id, job_type)
        return job_id or 0

    def claim_next(
        self,
        job_types: Optional[list[str]] = None,
    ) -> Optional[JobRecord]:
        """Атомарно взять следующую задачу (pending, run_after <= now). Возвращает запись после перевода в running (attempt уже увеличен)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE")
            now = self._now_iso()
            if job_types:
                placeholders = ",".join("?" * len(job_types))
                cursor.execute(
                    f"""
                    SELECT id, type, payload_json, status, attempt, run_after, error, created_at, updated_at
                    FROM jobs
                    WHERE status = ? AND (run_after IS NULL OR run_after <= ?)
                      AND type IN ({placeholders})
                    ORDER BY id LIMIT 1
                    """,
                    [STATUS_PENDING, now] + list(job_types),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, type, payload_json, status, attempt, run_after, error, created_at, updated_at
                    FROM jobs
                    WHERE status = ? AND (run_after IS NULL OR run_after <= ?)
                    ORDER BY id LIMIT 1
                    """,
                    (STATUS_PENDING, now),
                )
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return None
            job_id = row["id"]
            now = self._now_iso()
            cursor.execute(
                "UPDATE jobs SET status = ?, attempt = attempt + 1, updated_at = ? WHERE id = ?",
                (STATUS_RUNNING, now, job_id),
            )
            cursor.execute(
                "SELECT id, type, payload_json, status, attempt, run_after, error, created_at, updated_at FROM jobs WHERE id = ?",
                (job_id,),
            )
            updated_row = cursor.fetchone()
            conn.commit()
            return self._row_to_record(updated_row) if updated_row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _row_to_record(self, row: sqlite3.Row) -> JobRecord:
        def parse_dt(s: Optional[str]) -> Optional[datetime]:
            if not s:
                return None
            try:
                return datetime.fromisoformat(s.replace("Z", "+00:00"))
            except Exception:
                return None

        return JobRecord(
            id=row["id"],
            type=row["type"],
            payload_json=row["payload_json"] or "{}",
            status=row["status"],
            attempt=row["attempt"],
            run_after=parse_dt(row["run_after"]),
            error=row["error"],
            created_at=parse_dt(row["created_at"]) or datetime.now(timezone.utc),
            updated_at=parse_dt(row["updated_at"]) or datetime.now(timezone.utc),
        )

    def complete(self, job_id: int, result: Optional[dict] = None) -> None:
        """Отметить задачу выполненной. result при наличии сохраняется в result_json."""
        now = self._now_iso()
        result_json = json.dumps(result, ensure_ascii=False) if result is not None else None
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE jobs SET status = ?, error = NULL, result_json = ?, updated_at = ? WHERE id = ?",
            (STATUS_DONE, result_json, now, job_id),
        )
        conn.commit()
        conn.close()
        logger.debug("complete job id=%s", job_id)

    def fail_retry(
        self,
        job_id: int,
        error: str,
        run_after: Optional[datetime] = None,
    ) -> None:
        """Отметить задачу неудачной и поставить на повтор (status=pending, run_after)."""
        now = self._now_iso()
        run_after_str = run_after.isoformat() if run_after else now
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE jobs SET status = ?, error = ?, run_after = ?, updated_at = ? WHERE id = ?",
            (STATUS_PENDING, error[:1024] if error else None, run_after_str, now, job_id),
        )
        conn.commit()
        conn.close()
        logger.debug("fail_retry job id=%s error=%s", job_id, error[:100])

    def fail(self, job_id: int, error: str) -> None:
        """Отметить задачу окончательно неудачной (без повтора)."""
        now = self._now_iso()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE jobs SET status = ?, error = ?, updated_at = ? WHERE id = ?",
            (STATUS_FAILED, error[:1024] if error else None, now, job_id),
        )
        conn.commit()
        conn.close()
        logger.debug("fail job id=%s", job_id)

    def get_job(self, job_id: int) -> Optional[JobRecord]:
        """Прочитать задачу по id (для тестов и отладки)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, type, payload_json, status, attempt, run_after, error, created_at, updated_at FROM jobs WHERE id = ?",
            (job_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return self._row_to_record(row) if row else None
