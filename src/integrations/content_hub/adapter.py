"""Доменный адаптер: маппинг PublicationResult + VideoRecord -> payload content_hub_client и вызов клиента.

Весь canonical write выполняется только через content_hub_client (ContentBackbone).
Прямого SQL и локального DAO в VK_Importer нет.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.storage.database import VideoRecord
from src.models.content import PublicationResult
from src.utils.env_utils import get_env_var

logger = logging.getLogger(__name__)

# Импорт клиента — опционален; при отсутствии модуля canonical write отключается
try:
    from content_hub_client.client import ContentHubClient
    from content_hub_client.contracts import LinkMapPayload, PublicationPayload
    _CLIENT_AVAILABLE = True
except ImportError:
    ContentHubClient = None  # type: ignore
    LinkMapPayload = None  # type: ignore
    PublicationPayload = None  # type: ignore
    _CLIENT_AVAILABLE = False


def _config_from_env(env_path: Optional[Path] = None) -> tuple[bool, bool, bool, Optional[str]]:
    """(enabled, dry_run, strict, dsn)."""
    enabled = (get_env_var("CONTENT_HUB_WRITE_ENABLED", "0", env_path) or "0").strip() == "1"
    dry_run = (get_env_var("CONTENT_HUB_WRITE_DRY_RUN", "0", env_path) or "0").strip() == "1"
    strict = (get_env_var("CONTENT_HUB_WRITE_STRICT", "0", env_path) or "0").strip() == "1"
    dsn = get_env_var("CONTENT_HUB_PG_DSN", env_path=env_path)
    if not dsn and (get_env_var("PGHOST", env_path=env_path) or os.getenv("PGHOST")):
        host = get_env_var("PGHOST", env_path=env_path) or os.getenv("PGHOST", "")
        port = get_env_var("PGPORT", env_path=env_path) or os.getenv("PGPORT", "5432")
        dbname = get_env_var("PGDATABASE", env_path=env_path) or os.getenv("PGDATABASE", "Learn")
        user = get_env_var("PGUSER", env_path=env_path) or os.getenv("PGUSER", "")
        password = get_env_var("PGPASSWORD", env_path=env_path) or os.getenv("PGPASSWORD", "")
        if user and password:
            dsn = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        else:
            dsn = f"postgresql://{host}:{port}/{dbname}" if host else None
    return enabled, dry_run, strict, dsn


def _global_uid(record: VideoRecord) -> str:
    """Стабильный source key: vk_importer:video_record:<id> или vk_importer:path:<path>."""
    if getattr(record, "id", None) is not None:
        return f"vk_importer:video_record:{record.id}"
    path = (record.file_path or "").replace("\\", "/").strip()
    if path:
        return f"vk_importer:path:{path}"
    return "vk_importer:path:unknown"


def _remote_id_from_vk_url(remote_url: Optional[str]) -> Optional[str]:
    """Формат owner_id_video_id (например -12345_67890)."""
    if not remote_url:
        return None
    from src.publisher.vk_publisher import VKPublisher
    pair = VKPublisher.parse_video_url(remote_url)
    if not pair:
        return None
    oid, vid = pair
    return f"{oid}_{vid}"


def write_canonical_if_enabled(record: VideoRecord, result: PublicationResult) -> None:
    """Post-publish: при CONTENT_HUB_WRITE_ENABLED=1 вызвать content_hub_client (upsert publication + link_map).

    При сбое: лог и при CONTENT_HUB_WRITE_STRICT=1 — проброс исключения.
    Если модуль content_hub_client недоступен — warning и выход без записи.
    """
    enabled, dry_run, strict, dsn = _config_from_env()
    if not enabled:
        return

    if not _CLIENT_AVAILABLE:
        logger.warning(
            "content_hub_client недоступен (PYTHONPATH?): canonical write пропущен. "
            "Добавьте корень ContentBackbone в PYTHONPATH."
        )
        if strict:
            raise RuntimeError("content_hub_client недоступен при CONTENT_HUB_WRITE_STRICT=1")
        return

    if not dsn:
        logger.warning("CONTENT_HUB_PG_DSN не задан: canonical write пропущен.")
        if strict:
            raise ValueError("CONTENT_HUB_PG_DSN не задан при CONTENT_HUB_WRITE_STRICT=1")
        return

    global_uid = _global_uid(record)
    destination = result.destination or "vk"
    status = "published" if result.ok else "failed"
    error = result.error_code if not result.ok else None
    remote_url = result.remote_url if result.ok else None
    remote_id = _remote_id_from_vk_url(remote_url) if remote_url else None
    published_at: Optional[str] = None
    if result.ok:
        published_at = datetime.now(timezone.utc).isoformat()

    pub = PublicationPayload(
        global_uid=global_uid,
        destination=destination,
        remote_id=remote_id,
        remote_url=remote_url,
        published_at=published_at,
        status=status,
        error=error,
    )
    run_id = str(uuid.uuid4())[:8]
    client = ContentHubClient(dsn, dry_run=dry_run, logger=logger, run_id=run_id)

    # Structured log до операций (run_id, global_uid, destination, status, dry_run)
    logger.info(
        "content_hub canonical write start",
        extra={
            "run_id": run_id,
            "global_uid": global_uid,
            "destination": destination,
            "status": status,
            "error_class": None,
            "dry_run": dry_run,
        },
    )

    try:
        r1 = client.upsert_publication(pub)
        logger.info(
            "content_hub canonical write publication",
            extra={
                "run_id": run_id,
                "global_uid": global_uid,
                "destination": destination,
                "status": r1.status,
                "error_class": r1.error_class,
                "dry_run": dry_run,
                "ok": r1.ok,
            },
        )
        if not r1.ok and strict:
            raise RuntimeError(f"content_hub_client upsert_publication failed: {r1.error_message}")
        if not r1.ok:
            logger.warning("content_hub_client upsert_publication failed: %s", r1.error_message)

        # link_map пишем только если publication записалась (r1.ok) и публикация в VK успешна (result.ok), иначе возможна частичная запись link_map при неуспешной publication
        if r1.ok and result.ok and (remote_url or remote_id):
            link = LinkMapPayload(
                source_global_uid=global_uid,
                destination=destination,
                remote_id=remote_id,
                remote_url=remote_url,
            )
            r2 = client.upsert_link_map(link)
            logger.info(
                "content_hub canonical write link_map",
                extra={
                    "run_id": run_id,
                    "global_uid": global_uid,
                    "destination": destination,
                    "status": r2.status,
                    "error_class": r2.error_class,
                    "dry_run": dry_run,
                    "ok": r2.ok,
                },
            )
            if not r2.ok and strict:
                raise RuntimeError(f"content_hub_client upsert_link_map failed: {r2.error_message}")
            if not r2.ok:
                logger.warning("content_hub_client upsert_link_map failed: %s", r2.error_message)
    except Exception as e:
        logger.warning(
            "Content Hub canonical write failed (upload не отменён): %s", e,
            exc_info=True,
            extra={"run_id": run_id, "global_uid": global_uid, "destination": destination, "dry_run": dry_run},
        )
        if strict:
            raise
