"""Точка входа CLI приложения."""

import json
import sqlite3
import subprocess
import sys
import io
import time
from datetime import datetime, timezone
from pathlib import Path
import logging
from typing import Any, Optional

import click

# Добавить корень проекта в путь для импортов
sys.path.insert(0, str(Path(__file__).parent))

# Настройка кодировки для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from src.storage.database import VideoStorage, VideoRecord
from src.storage.job_queue import JobQueue, JobRecord
from src.storage.scanner import VideoScanner
from src.title_generators.factory import TitleGeneratorFactory
from src.publisher.vk_publisher import VKPublisher, VKApi1051Error
from src.utils.env_utils import get_env_var
from src.models.video import VideoData
from src.models.content import ContentItem
from src.app_context import get_vk_publisher, FatalUploadError
from src.adapters import VKDestinationAdapter
from src.config.registry import COURSE_TYPES, CHANNEL_TO_TITLE_GENERATOR
from src.config.source_registry import get_export_paths
from src.integrations.content_hub import write_canonical_if_enabled

# Настройка логирования (файл в папке logs, папка в .gitignore)
# Уровень из переменной окружения LOG_LEVEL (DEBUG, INFO, WARNING, ERROR) для пайплайнов
Path("logs").mkdir(exist_ok=True)
_log_level_name = (get_env_var("LOG_LEVEL") or "INFO").upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/publisher.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# Корень проекта (для вызова scripts/refresh_vk_token.py)
_PROJECT_ROOT = Path(__file__).resolve().parent

# Рекомендуемая задержка между загрузками (VK API: лимит частоты, антибот). См. docs/USAGE.md
DEFAULT_UPLOAD_DELAY = 15.0

# Коды выхода (docs/EXIT-CODES-AND-SUMMARY-SPEC.md)
EXIT_SUCCESS = 0
EXIT_FATAL = 1
EXIT_PARTIAL = 2
EXIT_VK_CONTEXT = 3  # VK API 1051: метод недоступен для профиля/токена — прервать batch
EXIT_INTERRUPTED = 130

SUMMARY_FILE = Path("logs/last_summary.json")

# Сообщение об операционной неудаче публикации (publish вернул None) — для upload-one даёт EXIT_PARTIAL, не EXIT_FATAL
UPLOAD_ERROR_PUBLISH_FAILED = "Ошибка загрузки"
# Коды ошибок адаптера и legacy: операционный провал публикации одного элемента → EXIT_PARTIAL (Phase 3 / Phase 1)
PARTIAL_UPLOAD_ERROR_CODES = frozenset({
    "PUBLISH_FAILED", "NO_VIDEO", UPLOAD_ERROR_PUBLISH_FAILED,
})


def write_summary(
    command: str,
    exit_code: int,
    stats: dict[str, Any],
    warnings: list[str],
    errors: list[str],
    duration_sec: Optional[float] = None,
) -> None:
    """Записать итог команды в logs/last_summary.json для пайплайнов."""
    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "command": command,
        "exit_code": exit_code,
        "ts_end": datetime.now(timezone.utc).isoformat(),
        "ok": exit_code == EXIT_SUCCESS,
        "stats": stats,
        "warnings": warnings,
        "errors": errors,
    }
    if duration_sec is not None:
        payload["duration_sec"] = round(duration_sec, 2)
    try:
        SUMMARY_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Не удалось записать summary: %s", e)


def _refresh_vk_token_callback() -> Optional[str]:
    """Запуск обновления VK токена по refresh_token и возврат нового access_token из .env."""
    script = _PROJECT_ROOT / "scripts" / "refresh_vk_token.py"
    if not script.exists():
        logger.warning("Скрипт scripts/refresh_vk_token.py не найден")
        return None
    try:
        subprocess.run(
            [sys.executable, str(script), "--force"],
            cwd=str(_PROJECT_ROOT),
            check=False,
            capture_output=True,
            timeout=30,
        )
    except Exception as e:
        logger.warning("Ошибка при обновлении токена: %s", e)
        return None
    return get_env_var("VK_ACCESS_TOKEN")


def get_storage() -> VideoStorage:
    """Получить экземпляр хранилища."""
    return VideoStorage(Path("videos.db"))


@click.group()
def cli():
    """VK Video Publisher - публикатор видео из Telegram экспорта в VK Video."""
    pass


@cli.group()
def folders():
    """Маппинг папок на тип курса. Управление только через CLI (без изменения кода)."""
    pass


@folders.command("list")
def folders_list():
    """Показать все папки и их тип курса (из БД)."""
    storage = get_storage()
    rows = storage.list_folder_mappings()
    write_summary("folders list", EXIT_SUCCESS, {"count": len(rows)}, [], [])
    if not rows:
        click.echo("Маппинг пуст. Добавьте: folders set <путь> <курс>")
        return
    for folder_path, course_type in rows:
        click.echo(f"  {folder_path}  →  {course_type}")


@folders.command("set")
@click.argument("folder_path", type=click.Path(exists=False))
@click.argument("course_type", type=click.Choice(list(COURSE_TYPES)))
def folders_set(folder_path: str, course_type: str):
    """Установить тип курса для папки (путь сохраняется в БД)."""
    storage = get_storage()
    storage.set_folder_course(folder_path, course_type)
    click.echo(f"Установлено: {folder_path}  →  {course_type}")
    write_summary("folders set", EXIT_SUCCESS, {"action": "set", "folder": folder_path, "course_type": course_type}, [], [])


@folders.command("remove")
@click.argument("folder_path", type=click.Path(exists=False))
def folders_remove(folder_path: str):
    """Удалить маппинг для папки."""
    storage = get_storage()
    if storage.delete_folder_mapping(folder_path):
        click.echo(f"Удалён маппинг для: {folder_path}")
        write_summary("folders remove", EXIT_SUCCESS, {"action": "remove", "folder": folder_path}, [], [])
    else:
        click.echo(f"Маппинг для папки не найден: {folder_path}", err=True)
        write_summary("folders remove", EXIT_FATAL, {}, [], [f"Маппинг не найден: {folder_path}"])
        sys.exit(EXIT_FATAL)


def _parse_date_option(value: Optional[str]):
    """Парсинг даты из строки YYYY-MM-DD."""
    if not value:
        return None
    try:
        from datetime import datetime
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@cli.command()
@click.option(
    "--source", "-s",
    default="all",
    help="Источник: 'all', 'all_channels', 'ege', 'python', 'oge', 'mapped' или путь к папке"
)
@click.option("--since", help="Добавлять только видео с датой >= YYYY-MM-DD (инкременты)")
@click.option("--until", help="Добавлять только видео с датой <= YYYY-MM-DD")
def scan(source: str, since: Optional[str], until: Optional[str]):
    """Сканировать экспорты и добавить видео в хранилище."""
    t0 = time.time()
    click.echo("=" * 80)
    click.echo("Сканирование экспортов")
    click.echo("=" * 80)

    storage = get_storage()
    if source.lower() == "mapped":
        export_paths = [Path(p) for p, _ in storage.list_folder_mappings() if Path(p).exists()]
    else:
        export_paths = get_export_paths(source)
    if not export_paths:
        if source and source.lower() not in ("all", "all_channels", "ege", "python", "oge", "mapped", "tg_parser"):
            click.echo(f"ОШИБКА: Путь не существует: {Path(source)}", err=True)
        click.echo("Не найдено экспортов для сканирования", err=True)
        write_summary("scan", EXIT_FATAL, {"export_paths": 0}, [], ["Не найдено экспортов для сканирования"])
        sys.exit(EXIT_FATAL)

    date_since = _parse_date_option(since)
    date_until = _parse_date_option(until)
    if since and not date_since:
        click.echo(f"Неверный формат --since (ожидается YYYY-MM-DD): {since}", err=True)
        write_summary("scan", EXIT_FATAL, {}, [], [f"Неверный формат --since: {since}"])
        sys.exit(EXIT_FATAL)
    if until and not date_until:
        click.echo(f"Неверный формат --until (ожидается YYYY-MM-DD): {until}", err=True)
        write_summary("scan", EXIT_FATAL, {}, [], [f"Неверный формат --until: {until}"])
        sys.exit(EXIT_FATAL)

    click.echo(f"Найдено экспортов: {len(export_paths)}")
    if date_since or date_until:
        click.echo(f"Фильтр по дате: с {date_since or '—'} по {date_until or '—'}")

    scanner = VideoScanner(storage)
    stats = scanner.scan_and_add(
        export_paths,
        skip_duplicates=True,
        date_since=date_since,
        date_until=date_until,
    )

    click.echo("\n" + "=" * 80)
    click.echo("РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    click.echo("=" * 80)
    click.echo(f"Добавлено новых: {stats['added']}")
    click.echo(f"Дубликатов пропущено: {stats['duplicates']}")
    click.echo(f"Обновлено существующих: {stats['updated']}")
    if stats.get("skipped_date", 0):
        click.echo(f"Пропущено по дате: {stats['skipped_date']}")

    # Показываем статистику
    db_stats = storage.get_statistics()
    click.echo(f"\nВсего в базе: {db_stats['total']}")
    click.echo(f"Загружено: {db_stats['uploaded']}")
    click.echo(f"Не загружено: {db_stats['not_uploaded']}")

    stats_out = {**stats, "export_paths": len(export_paths)}
    write_summary("scan", EXIT_SUCCESS, stats_out, [], [], duration_sec=time.time() - t0)


@cli.command()
def stats():
    """Показать статистику по видео."""
    storage = get_storage()
    st = storage.get_statistics()
    write_summary("stats", EXIT_SUCCESS, dict(st), [], [])
    click.echo("=" * 80)
    click.echo("СТАТИСТИКА")
    click.echo("=" * 80)
    click.echo(f"Всего видео: {st['total']}")
    click.echo(f"Загружено: {st['uploaded']}")
    click.echo(f"Не загружено: {st['not_uploaded']}")
    if st.get("skipped", 0):
        click.echo(f"Помечено для пропуска: {st['skipped']}")
    click.echo(f"Каналов: {st['channels']}")
    click.echo(f"Папок источников: {st['source_folders']}")


@cli.command("export-excel")
@click.option("--db", default="videos.db", type=click.Path(path_type=Path, exists=False), help="Путь к файлу БД")
@click.option("--output", "-o", "output_path", type=click.Path(path_type=Path, exists=False), help="Путь к выходному Excel (по умолчанию: videos_export_YYYYMMDD_HHMMSS.xlsx)")
def export_excel(db: Path, output_path: Optional[Path]):
    """Выгрузить таблицу videos из БД в Excel (.xlsx)."""
    try:
        import pandas as pd
    except ImportError:
        click.echo("Установите зависимости: pip install pandas openpyxl", err=True)
        write_summary("export-excel", EXIT_FATAL, {}, [], ["Нет модуля pandas"])
        sys.exit(EXIT_FATAL)

    db_path = Path(db)
    if not db_path.exists():
        click.echo(f"Файл БД не найден: {db_path}", err=True)
        write_summary("export-excel", EXIT_FATAL, {}, [], [f"Файл БД не найден: {db_path}"])
        sys.exit(EXIT_FATAL)

    if output_path is None:
        output_path = Path(f"videos_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
    output_path = Path(output_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM videos ORDER BY id")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        click.echo("Таблица videos пуста. Файл не создан.")
        write_summary("export-excel", EXIT_SUCCESS, {"rows": 0}, [], [])
        return

    data = []
    for row in rows:
        data.append({
            "ID": row["id"],
            "Путь к файлу": row["file_path"],
            "Хеш файла": row["file_hash"] or "",
            "Заголовок": row["title"],
            "Описание": (row["description"] or "")[:500],
            "Канал": row["channel"] or "",
            "Папка источника": row["source_folder"],
            "Дата видео": row["date"] or "",
            "Загружено": "Да" if row["uploaded"] else "Нет",
            "Пропуск загрузки": "Да" if row["skip_upload"] else "Нет",
            "Дата загрузки": row["upload_date"] or "",
            "URL видео": row["video_url"] or "",
            "URL поста": row["post_url"] or "",
            "Ошибка": row["error_message"] or "",
            "Создано": row["created_at"] or "",
        })

    df = pd.DataFrame(data)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Видео", index=False)
        ws = writer.sheets["Видео"]
        widths = {"A": 8, "B": 50, "C": 20, "D": 60, "E": 50, "F": 10, "G": 40, "H": 20, "I": 10, "J": 14, "K": 20, "L": 50, "M": 50, "N": 50, "O": 20}
        for col, w in widths.items():
            ws.column_dimensions[col].width = w
        ws.freeze_panes = "A2"

    storage = VideoStorage(db_path)
    st = storage.get_statistics()
    click.echo(f"Экспортировано {len(data)} записей в {output_path}")
    click.echo(f"Всего: {st['total']}, загружено: {st['uploaded']}, не загружено: {st['not_uploaded']}, каналов: {st['channels']}")
    write_summary("export-excel", EXIT_SUCCESS, {"rows": len(data), "path": str(output_path), **st}, [], [])


def _read_filenames_from_file(path: Path) -> list[str]:
    """Прочитать имена файлов из UTF-8 файла (по одному на строку)."""
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


@cli.command()
@click.option("--id", "ids", type=int, multiple=True, help="ID записей для пометки")
@click.option("--file", "files", type=str, multiple=True, help="Имя файла или путь (совпадение по окончанию file_path)")
@click.option("--file-from", "file_from", type=click.Path(path_type=Path, exists=True), help="Файл UTF-8 со списком имён (по одному на строку) — обход проблем кодировки в терминале")
def skip(ids: tuple, files: tuple, file_from: Optional[Path]):
    """Пометить видео для пропуска загрузки (не загружать)."""
    file_list = list(files) if files else []
    if file_from:
        file_list.extend(_read_filenames_from_file(file_from))
    if not ids and not file_list:
        click.echo("Укажите хотя бы один --id, --file или --file-from.", err=True)
        write_summary("skip", EXIT_FATAL, {}, [], ["Укажите хотя бы один --id, --file или --file-from"])
        sys.exit(EXIT_FATAL)
    storage = get_storage()
    n = storage.set_skip_upload(ids=list(ids) if ids else None, filenames=file_list or None, skip=True)
    click.echo(f"Помечено для пропуска: {n} записей.")
    write_summary("skip", EXIT_SUCCESS, {"marked": n}, [], [])


@cli.command()
@click.option("--id", "ids", type=int, multiple=True, help="ID записей для снятия пометки")
@click.option("--file", "files", type=str, multiple=True, help="Имя файла или путь")
@click.option("--file-from", "file_from", type=click.Path(path_type=Path, exists=True), help="Файл UTF-8 со списком имён (по одному на строку)")
def unskip(ids: tuple, files: tuple, file_from: Optional[Path]):
    """Снять пометку «пропускать загрузку» с видео."""
    file_list = list(files) if files else []
    if file_from:
        file_list.extend(_read_filenames_from_file(file_from))
    if not ids and not file_list:
        click.echo("Укажите хотя бы один --id, --file или --file-from.", err=True)
        write_summary("unskip", EXIT_FATAL, {}, [], ["Укажите хотя бы один --id, --file или --file-from"])
        sys.exit(EXIT_FATAL)
    storage = get_storage()
    n = storage.set_skip_upload(ids=list(ids) if ids else None, filenames=file_list or None, skip=False)
    click.echo(f"Снята пометка пропуска: {n} записей.")
    write_summary("unskip", EXIT_SUCCESS, {"marked": n}, [], [])


@cli.command("delete-skipped-from-vk")
@click.option("--delay", "-d", type=float, default=DEFAULT_UPLOAD_DELAY, help="Пауза между запросами к VK (сек)")
@click.option("--dry-run", is_flag=True, help="Только показать, что будет удалено, не вызывать API")
def delete_skipped_from_vk(delay: float, dry_run: bool):
    """Удалить из VK ролики по URL записей с skip=1 (удобный отбор по пометке; удаление всё равно по URL)."""
    storage = get_storage()
    records = storage.get_skipped_with_video_url()
    if not records:
        click.echo("Нет записей с пометкой skip и заполненным video_url.")
        write_summary("delete-skipped-from-vk", EXIT_SUCCESS, {"requested": 0, "deleted": 0, "failed": 0}, [], [])
        return
    url_list = [r.video_url for r in records if r.video_url]
    click.echo(f"Найдено записей с skip=1 и URL: {len(url_list)}. Удаление по URL.")
    try:
        publisher = get_vk_publisher(delay, max_retries=3, group_id_required=False, on_token_expired=_refresh_vk_token_callback)
    except FatalUploadError as e:
        click.echo(f"ОШИБКА: {e.message}", err=True)
        write_summary("delete-skipped-from-vk", EXIT_FATAL, {}, [], [e.message])
        sys.exit(EXIT_FATAL)
    requested, deleted, failed = _delete_from_vk_by_urls(url_list, storage, publisher, delay, dry_run)
    if requested == 0 and url_list:
        write_summary("delete-skipped-from-vk", EXIT_FATAL, {"requested": 0, "deleted": 0, "failed": 0}, [], ["Ни один URL не удалось разобрать"])
        sys.exit(EXIT_FATAL)
    write_summary("delete-skipped-from-vk", EXIT_PARTIAL if failed else EXIT_SUCCESS, {"requested": requested, "deleted": deleted, "failed": failed}, [], [])
    if failed:
        sys.exit(EXIT_PARTIAL)


@cli.command("clear-skip-upload-state")
def clear_skip_upload_state():
    """Сбросить данные загрузки у всех записей с пометкой skip (только локально). Используйте после delete-skipped-from-vk или если ролики с skip в VK не загружались."""
    storage = get_storage()
    n = storage.clear_upload_state_for_skipped()
    click.echo(f"Сброшены данные загрузки у {n} записей с пометкой skip.")
    write_summary("clear-skip-upload-state", EXIT_SUCCESS, {"cleared": n}, [], [])


def _delete_from_vk_by_urls(
    urls: list[str],
    storage: VideoStorage,
    publisher: VKPublisher,
    delay: float,
    dry_run: bool,
) -> tuple[int, int, int]:
    """Удалить в VK видео по списку URL; при наличии записи в БД с таким video_url — сбросить данные загрузки. Возвращает (requested, deleted, failed)."""
    parsed = []
    for url in urls:
        url = url.strip()
        if not url or url.startswith("#"):
            continue
        pair = VKPublisher.parse_video_url(url)
        if pair:
            parsed.append((pair[0], pair[1], url))
        else:
            click.echo(f"  Не удалось разобрать URL: {url!r}", err=True)
    if not parsed:
        return (0, 0, 0)
    if dry_run:
        for oid, vid, url in parsed:
            click.echo(f"  {url} -> video.delete(owner_id={oid}, video_id={vid})")
        click.echo(f"Всего к удалению в VK: {len(parsed)}. Запустите без --dry-run.")
        return (len(parsed), 0, 0)
    ok = 0
    for idx, (owner_id, video_id, url) in enumerate(parsed):
        if publisher.delete_video(owner_id, video_id):
            rec = storage.get_record_by_video_url(url)
            if rec:
                storage.clear_upload_state(rec.id)
                click.echo(f"  {url} — удалено в VK, данные в БД (ID {rec.id}) сброшены")
            else:
                click.echo(f"  {url} — удалено в VK")
            ok += 1
        else:
            click.echo(f"  {url} — ошибка удаления в VK")
        if idx < len(parsed) - 1 and delay > 0:
            time.sleep(delay)
    failed = len(parsed) - ok
    click.echo(f"Готово: удалено в VK — {ok} из {len(parsed)}.")
    return (len(parsed), ok, failed)


@cli.command("delete-from-vk")
@click.option("--url", "urls", type=str, multiple=True, help="URL видео в VK (например https://vk.com/video-123_456)")
@click.option("--urls-file", type=click.Path(path_type=Path, exists=True), help="Файл со списком URL (по одному на строку)")
@click.option("--delay", "-d", type=float, default=DEFAULT_UPLOAD_DELAY, help="Пауза между запросами к VK (сек)")
@click.option("--dry-run", is_flag=True, help="Только показать, что будет удалено, не вызывать API")
def delete_from_vk(urls: tuple, urls_file: Optional[Path], delay: float, dry_run: bool):
    """Удалить видео в VK по URL (video.delete). Можно удалить любое видео. Если в БД есть запись с этим video_url — сбросить данные загрузки."""
    url_list = list(urls) if urls else []
    if urls_file:
        with open(urls_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    url_list.append(line)
    if not url_list:
        click.echo("Укажите --url или --urls-file.", err=True)
        write_summary("delete-from-vk", EXIT_FATAL, {}, [], ["Укажите --url или --urls-file"])
        sys.exit(EXIT_FATAL)
    storage = get_storage()
    try:
        publisher = get_vk_publisher(delay, max_retries=3, group_id_required=False, on_token_expired=_refresh_vk_token_callback)
    except FatalUploadError as e:
        click.echo(f"ОШИБКА: {e.message}", err=True)
        write_summary("delete-from-vk", EXIT_FATAL, {}, [], [e.message])
        sys.exit(EXIT_FATAL)
    requested, deleted, failed = _delete_from_vk_by_urls(url_list, storage, publisher, delay, dry_run)
    if requested == 0 and url_list:
        write_summary("delete-from-vk", EXIT_FATAL, {"requested": 0, "deleted": 0, "failed": 0}, [], ["Ни один URL не удалось разобрать"])
        sys.exit(EXIT_FATAL)
    write_summary("delete-from-vk", EXIT_PARTIAL if failed else EXIT_SUCCESS, {"requested": requested, "deleted": deleted, "failed": failed}, [], [])
    if failed:
        sys.exit(EXIT_PARTIAL)


@cli.command()
@click.argument("video_id", type=int)
@click.option("--delay", "-d", type=float, default=DEFAULT_UPLOAD_DELAY, help="Задержка между загрузками (сек); по умолчанию с учётом лимитов VK API")
@click.option("--max-retries", "-r", type=int, default=3, help="Максимальное количество повторных попыток")
def upload_one(video_id: int, delay: float, max_retries: int):
    """Загрузить конкретное видео по ID."""
    storage = get_storage()
    record = storage.get_video(video_id)

    if not record:
        click.echo(f"Видео с ID {video_id} не найдено", err=True)
        write_summary("upload-one", EXIT_FATAL, {}, [], [f"Видео с ID {video_id} не найдено"])
        sys.exit(EXIT_FATAL)

    if record.uploaded:
        click.echo(f"Видео {video_id} уже загружено: {record.video_url}")
        write_summary("upload-one", EXIT_SUCCESS, {"uploaded": True, "video_id": video_id, "video_url": record.video_url or ""}, [], [])
        return

    if getattr(record, "skip_upload", False):
        click.echo("Видео помечено для пропуска загрузки. Снимите пометку: python main.py unskip --id " + str(video_id))
        write_summary("upload-one", EXIT_SUCCESS, {"uploaded": False, "video_id": video_id, "video_url": ""}, [], [])
        return

    ok, err = _upload_video(record, storage, delay, max_retries)
    record = storage.get_video(video_id)
    uploaded = bool(record and record.video_url)
    stats = {"uploaded": uploaded, "video_id": video_id, "video_url": (record.video_url or "") if record else ""}
    if not ok and err:
        if err == "VK_API_1051":
            write_summary("upload-one", EXIT_VK_CONTEXT, stats, [], [err])
            sys.exit(EXIT_VK_CONTEXT)
        exit_code = EXIT_PARTIAL if err in PARTIAL_UPLOAD_ERROR_CODES else EXIT_FATAL
        write_summary("upload-one", exit_code, stats, [], [err])
        sys.exit(exit_code)
    write_summary("upload-one", EXIT_SUCCESS, stats, [], [])


@cli.command()
@click.option("--channel", "-c", help="Фильтр по каналу (ЕГЭ, Python)")
@click.option("--source", "-s", help="Фильтр по папке источника")
@click.option("--delay", "-d", type=float, default=DEFAULT_UPLOAD_DELAY, help="Задержка между загрузками (сек); по умолчанию с учётом лимитов VK API")
@click.option("--max-retries", "-r", type=int, default=3, help="Максимальное количество повторных попыток")
def upload_next(channel: Optional[str], source: Optional[str], delay: float, max_retries: int):
    """Загрузить следующее не загруженное видео."""
    storage = get_storage()
    record = storage.get_next_unuploaded(channel=channel, source_folder=source)

    if not record:
        click.echo("Не найдено не загруженных видео")
        write_summary("upload-next", EXIT_SUCCESS, {"total": 0, "successful": 0, "failed": 0, "skipped": 0}, [], [])
        return

    click.echo(f"Загрузка видео ID {record.id}: {Path(record.file_path).name}")
    try:
        successful, failed, skipped = _upload_batch([record], storage, delay, max_retries)
    except FatalUploadError as e:
        write_summary("upload-next", EXIT_FATAL, {}, [], [e.message])
        sys.exit(EXIT_FATAL)
    write_summary("upload-next", EXIT_PARTIAL if failed else EXIT_SUCCESS, {"total": 1, "successful": successful, "failed": failed, "skipped": skipped}, [], [])
    if failed:
        sys.exit(EXIT_PARTIAL)


@cli.command()
@click.argument("start_id", type=int)
@click.option("--count", "-n", type=int, default=None, help="Количество видео (по умолчанию все до конца)")
@click.option("--channel", "-c", help="Фильтр по каналу")
@click.option("--source", "-s", help="Фильтр по папке источника")
@click.option("--delay", "-d", type=float, default=DEFAULT_UPLOAD_DELAY, help="Задержка между загрузками (сек); по умолчанию с учётом лимитов VK API")
@click.option("--max-retries", "-r", type=int, default=3, help="Максимальное количество повторных попыток")
def upload_range(start_id: int, count: Optional[int], channel: Optional[str], source: Optional[str], 
                 delay: float, max_retries: int):
    """Загрузить видео, начиная с указанного ID."""
    storage = get_storage()
    records = storage.get_videos_range(start_id, count=count, channel=channel, source_folder=source)
    
    if not records:
        click.echo(f"Не найдено видео начиная с ID {start_id}")
        write_summary("upload-range", EXIT_SUCCESS, {"total": 0, "successful": 0, "failed": 0, "skipped": 0}, [], [])
        return

    click.echo(f"Найдено видео для загрузки: {len(records)}")
    try:
        successful, failed, skipped = _upload_batch(records, storage, delay, max_retries)
    except FatalUploadError as e:
        write_summary("upload-range", EXIT_FATAL, {}, [], [e.message])
        sys.exit(EXIT_FATAL)
    write_summary("upload-range", EXIT_PARTIAL if failed else EXIT_SUCCESS, {"total": len(records), "successful": successful, "failed": failed, "skipped": skipped}, [], [])
    if failed:
        sys.exit(EXIT_PARTIAL)


@cli.command()
@click.option("--count", "-n", type=int, default=None, help="Количество видео")
@click.option("--channel", "-c", help="Фильтр по каналу")
@click.option("--source", "-s", help="Фильтр по папке источника")
@click.option("--delay", "-d", type=float, default=DEFAULT_UPLOAD_DELAY, help="Задержка между загрузками (сек); по умолчанию с учётом лимитов VK API")
@click.option("--max-retries", "-r", type=int, default=3, help="Максимальное количество повторных попыток")
def upload_many(count: Optional[int], channel: Optional[str], source: Optional[str], 
                delay: float, max_retries: int):
    """Загрузить несколько не загруженных видео."""
    storage = get_storage()
    all_records = storage.get_all_unuploaded(channel=channel, source_folder=source)
    
    if not all_records:
        click.echo("Не найдено не загруженных видео")
        write_summary("upload-many", EXIT_SUCCESS, {"total": 0, "successful": 0, "failed": 0, "skipped": 0}, [], [])
        return

    records = all_records[:count] if count else all_records

    click.echo(f"Будет загружено видео: {len(records)}")
    try:
        successful, failed, skipped = _upload_batch(records, storage, delay, max_retries)
    except FatalUploadError as e:
        write_summary("upload-many", EXIT_FATAL, {}, [], [e.message])
        sys.exit(EXIT_FATAL)
    write_summary("upload-many", EXIT_PARTIAL if failed else EXIT_SUCCESS, {"total": len(records), "successful": successful, "failed": failed, "skipped": skipped}, [], [])
    if failed:
        sys.exit(EXIT_PARTIAL)


@cli.command()
@click.option("--channel", "-c", help="Фильтр по каналу")
@click.option("--source", "-s", help="Фильтр по папке источника")
@click.option("--delay", "-d", type=float, default=DEFAULT_UPLOAD_DELAY, help="Задержка между загрузками (сек); по умолчанию с учётом лимитов VK API")
@click.option("--max-retries", "-r", type=int, default=3, help="Максимальное количество повторных попыток")
def upload_all(channel: Optional[str], source: Optional[str], delay: float, max_retries: int):
    """Загрузить все не загруженные видео с самого начала."""
    storage = get_storage()
    records = storage.get_all_unuploaded(channel=channel, source_folder=source)
    
    if not records:
        click.echo("Не найдено не загруженных видео")
        write_summary("upload-all", EXIT_SUCCESS, {"total": 0, "successful": 0, "failed": 0, "skipped": 0}, [], [])
        return

    click.echo(f"Будет загружено видео: {len(records)}")
    try:
        successful, failed, skipped = _upload_batch(records, storage, delay, max_retries)
    except FatalUploadError as e:
        write_summary("upload-all", EXIT_FATAL, {}, [], [e.message])
        sys.exit(EXIT_FATAL)
    write_summary("upload-all", EXIT_PARTIAL if failed else EXIT_SUCCESS, {"total": len(records), "successful": successful, "failed": failed, "skipped": skipped}, [], [])
    if failed:
        sys.exit(EXIT_PARTIAL)


def _get_title_generator_for_channel(channel: Optional[str]):
    """Генератор заголовков по каналу (маппинг из config.registry)."""
    name = CHANNEL_TO_TITLE_GENERATOR.get((channel or "").strip()) if channel else None
    return TitleGeneratorFactory.create(name) if name else TitleGeneratorFactory.create("simple")


@cli.command("recalc-titles")
@click.option("--channel", "-c", help="Пересчитать только для канала (например Excel, Комлев, Аналитика данных)")
def recalc_titles(channel: Optional[str]):
    """Пересчитать заголовки по правилам курса и обновить БД."""
    storage = get_storage()
    records = storage.get_videos_range(0, 500000, channel=channel)
    if not records:
        click.echo("Нет записей для пересчёта.")
        write_summary("recalc-titles", EXIT_SUCCESS, {"processed": 0, "updated": 0, "skipped": 0}, [], [])
        return
    updated = 0
    skipped = 0
    for rec in records:
        gen = _get_title_generator_for_channel(rec.channel)
        if not gen:
            continue
        try:
            v = VideoData(
                file_path=Path(rec.file_path),
                title=rec.title or "",
                description=rec.description or "",
                date=rec.date,
                channel=rec.channel,
            )
        except ValueError:
            skipped += 1
            continue
        new_title = gen.generate(v)
        if new_title != (rec.title or ""):
            rec.title = new_title
            storage.add_video(rec)
            updated += 1
    click.echo(f"Обработано: {len(records)}, обновлено заголовков: {updated}, пропущено (файл не найден): {skipped}")
    write_summary("recalc-titles", EXIT_SUCCESS, {"processed": len(records), "updated": updated, "skipped": skipped}, [], [])


@cli.command("update-vk-titles")
@click.option(
    "--ids-file",
    type=click.Path(exists=True),
    default="logs/titles_recalc_affected_ids.txt",
    help="Файл со списком ID (через запятую) — по умолчанию те, у кого пересчитывали заголовки",
)
@click.option("--delay", "-d", type=float, default=15.0, help="Пауза между запросами к VK (сек)")
def update_vk_titles(ids_file: str, delay: float):
    """Обновить заголовки в VK у уже загруженных видео (по списку ID с исправленными заголовками)."""
    ids_path = Path(ids_file)
    if not ids_path.exists():
        click.echo(f"Файл не найден: {ids_path}", err=True)
        write_summary("update-vk-titles", EXIT_FATAL, {}, [], [f"Файл не найден: {ids_path}"])
        sys.exit(EXIT_FATAL)
    raw = ids_path.read_text(encoding="utf-8").strip()
    try:
        ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
    except ValueError as e:
        click.echo(f"Неверный формат ID в файле (ожидаются числа через запятую): {e}", err=True)
        write_summary("update-vk-titles", EXIT_FATAL, {}, [], [f"Неверный формат ID в файле: {e}"])
        sys.exit(EXIT_FATAL)
    if not ids:
        click.echo("Список ID пуст.")
        write_summary("update-vk-titles", EXIT_SUCCESS, {"total": 0, "updated": 0, "failed": 0}, [], [])
        return
    storage = get_storage()
    records = storage.get_videos_by_ids(ids)
    uploaded = [r for r in records if r.video_url]
    if not uploaded:
        click.echo("Среди указанных ID нет загруженных в VK видео.")
        write_summary("update-vk-titles", EXIT_SUCCESS, {"total": 0, "updated": 0, "failed": 0}, [], [])
        return
    try:
        publisher = get_vk_publisher(delay, max_retries=3, group_id_required=False, on_token_expired=_refresh_vk_token_callback)
    except FatalUploadError as e:
        click.echo(f"Ошибка инициализации VK API: {e.message}", err=True)
        write_summary("update-vk-titles", EXIT_FATAL, {}, [], [e.message])
        sys.exit(EXIT_FATAL)
    click.echo(f"Будет обновлено заголовков в VK: {len(uploaded)} (пауза {delay} сек)")
    ok = 0
    for i, rec in enumerate(uploaded, 1):
        parsed = VKPublisher.parse_video_url(rec.video_url or "")
        if not parsed:
            click.echo(f"  [{i}/{len(uploaded)}] ID {rec.id}: не удалось разобрать URL {rec.video_url!r}")
            continue
        owner_id, video_id = parsed
        if publisher.edit_video_title(owner_id, video_id, rec.title or ""):
            ok += 1
            click.echo(f"  [{i}/{len(uploaded)}] ID {rec.id}: OK — { (rec.title or '')[:50]}...")
        else:
            click.echo(f"  [{i}/{len(uploaded)}] ID {rec.id}: ошибка")
        if i < len(uploaded):
            time.sleep(delay)
    failed = len(uploaded) - ok
    click.echo(f"Готово: обновлено {ok} из {len(uploaded)}.")
    write_summary("update-vk-titles", EXIT_PARTIAL if failed else EXIT_SUCCESS, {"total": len(uploaded), "updated": ok, "failed": failed}, [], [])
    if failed:
        sys.exit(EXIT_PARTIAL)


@cli.command("vk-preflight")
def vk_preflight():
    """Проверить, что токен и группа позволяют вызывать video API (перед batch upload). При 1051 — выход с ошибкой."""
    try:
        publisher = get_vk_publisher(0, 1, group_id_required=True, on_token_expired=_refresh_vk_token_callback)
        publisher.check_video_access()
    except FatalUploadError as e:
        click.echo(f"ОШИБКА: {e.message}", err=True)
        write_summary("vk-preflight", EXIT_FATAL, {}, [], [e.message])
        sys.exit(EXIT_FATAL)
    except VKApi1051Error as e:
        click.echo(f"ОШИБКА VK 1051: {e}", err=True)
        write_summary("vk-preflight", EXIT_FATAL, {}, [], [str(e)])
        sys.exit(EXIT_FATAL)
    write_summary("vk-preflight", EXIT_SUCCESS, {"ok": True}, [], [])
    click.echo("VK video preflight OK.")


def _upload_video(record: VideoRecord, storage: VideoStorage, delay: float, max_retries: int) -> tuple[bool, Optional[str]]:
    """Загрузить одно видео через DestinationAdapter. Возвращает (успех, сообщение_об_ошибке или None). При skip_upload загрузка не выполняется — (False, None)."""
    if getattr(record, "skip_upload", False):
        click.echo("Пропуск: запись помечена для пропуска загрузки (skip).")
        return (False, None)
    try:
        publisher = get_vk_publisher(delay, max_retries, group_id_required=True, on_token_expired=_refresh_vk_token_callback)
    except FatalUploadError as e:
        click.echo(f"ОШИБКА: {e.message}", err=True)
        return (False, e.message)

    adapter = VKDestinationAdapter(publisher)
    item = ContentItem.from_video_record(
        file_path=record.file_path,
        title=record.title,
        description=record.description or "",
        channel=record.channel,
        source_folder=record.source_folder,
        date=record.date,
        record_id=record.id,
    )
    result = adapter.publish(item)

    write_canonical_if_enabled(record, result)

    if result.ok and result.remote_url:
        storage.mark_uploaded(record.id, result.remote_url, post_url=None)
        click.echo(f"✓ Видео {record.id} успешно загружено: {result.remote_url}")
        return (True, None)
    storage.mark_uploaded(record.id, "", error=result.error_code or UPLOAD_ERROR_PUBLISH_FAILED)
    click.echo(f"✗ Ошибка загрузки видео {record.id}")
    return (False, result.error_code or UPLOAD_ERROR_PUBLISH_FAILED)


def _upload_batch(records: list[VideoRecord], storage: VideoStorage, delay: float, max_retries: int) -> tuple[int, int, int]:
    """Загрузить пакет видео через DestinationAdapter. Возвращает (successful, failed, skipped). При ошибке окружения выбрасывает FatalUploadError."""
    publisher = get_vk_publisher(delay, max_retries, group_id_required=True, on_token_expired=_refresh_vk_token_callback)
    adapter = VKDestinationAdapter(publisher)
    successful = 0
    failed = 0
    skipped = 0

    for idx, record in enumerate(records, 1):
        if getattr(record, "skip_upload", False):
            click.echo(f"\n[{idx}/{len(records)}] Пропуск ID {record.id} (помечено для пропуска загрузки)")
            skipped += 1
            continue
        click.echo(f"\n[{idx}/{len(records)}] Загрузка видео ID {record.id}: {Path(record.file_path).name}")

        item = ContentItem.from_video_record(
            file_path=record.file_path,
            title=record.title,
            description=record.description or "",
            channel=record.channel,
            source_folder=record.source_folder,
            date=record.date,
            record_id=record.id,
        )
        result = adapter.publish(item)

        write_canonical_if_enabled(record, result)

        if result.ok and result.remote_url:
            storage.mark_uploaded(record.id, result.remote_url, post_url=None)
            successful += 1
            click.echo(f"✓ Успешно: {result.remote_url}")
        else:
            storage.mark_uploaded(record.id, "", error=result.error_code or UPLOAD_ERROR_PUBLISH_FAILED)
            failed += 1
            click.echo(f"✗ Ошибка загрузки")

        # Задержка между загрузками (кроме последнего видео)
        if idx < len(records):
            click.echo(f"Ожидание {delay} сек перед следующей загрузкой...")
            time.sleep(delay)
    
    click.echo("\n" + "=" * 80)
    click.echo("РЕЗУЛЬТАТЫ")
    click.echo("=" * 80)
    click.echo(f"Успешно: {successful}")
    click.echo(f"Ошибок: {failed}")
    if skipped:
        click.echo(f"Пропущено (skip): {skipped}")
    click.echo(f"Всего: {len(records)}")
    return (successful, failed, skipped)


# --- Phase 4: worker для очереди задач ---

JOB_TYPE_UPLOAD_VIDEO = "upload_video"


def _run_job(job: JobRecord, queue: JobQueue, storage: VideoStorage) -> None:
    """Выполнить одну задачу; по результату вызвать complete/fail_retry/fail."""
    if job.type == JOB_TYPE_UPLOAD_VIDEO:
        payload = job.payload()
        video_id = payload.get("video_id")
        if video_id is None:
            queue.fail(job.id, "payload.video_id отсутствует")
            return
        record = storage.get_video(video_id)
        if not record:
            queue.fail(job.id, f"Видео с ID {video_id} не найдено")
            return
        if record.uploaded:
            queue.complete(job.id, {"uploaded": True, "video_url": record.video_url})
            return
        try:
            ok, err = _upload_video(record, storage, DEFAULT_UPLOAD_DELAY, 3)
            if ok:
                queue.complete(job.id, {"uploaded": True})
            elif err and err in PARTIAL_UPLOAD_ERROR_CODES:
                from datetime import timedelta
                run_after = datetime.now(timezone.utc) + timedelta(minutes=5)
                queue.fail_retry(job.id, err or "publish failed", run_after=run_after)
            else:
                queue.fail(job.id, err or "unknown")
        except FatalUploadError as e:
            queue.fail(job.id, e.message)
    else:
        queue.fail(job.id, f"Неизвестный тип задачи: {job.type}")


@cli.command()
@click.option("--once", is_flag=True, help="Взять одну задачу и выйти")
@click.option("--loop", is_flag=True, help="Цикл: брать задачи с паузой до прерывания")
@click.option("--interval", "-i", type=float, default=10.0, help="Пауза между опросами очереди (сек) в --loop")
@click.option("--types", "-t", multiple=True, default=[JOB_TYPE_UPLOAD_VIDEO], help="Типы задач (можно несколько)")
def worker(once: bool, loop: bool, interval: float, types: tuple):
    """Воркер очереди задач: обрабатывает задачи из таблицы jobs (Phase 4)."""
    if not once and not loop:
        click.echo("Укажите --once или --loop.", err=True)
        write_summary("worker", EXIT_FATAL, {}, [], ["Укажите --once или --loop"])
        sys.exit(EXIT_FATAL)
    queue = JobQueue(Path("videos.db"))
    types_list = list(types) if types else [JOB_TYPE_UPLOAD_VIDEO]
    processed = 0
    try:
        while True:
            job = queue.claim_next(job_types=types_list)
            if not job:
                if once:
                    break
                time.sleep(interval)
                continue
            storage = get_storage()
            _run_job(job, queue, storage)
            processed += 1
            if once:
                break
    except (KeyboardInterrupt, click.Abort):
        click.echo("\nВоркер прерван.", err=True)
        write_summary("worker", EXIT_INTERRUPTED, {"processed": processed}, [], [])
        sys.exit(EXIT_INTERRUPTED)
    write_summary("worker", EXIT_SUCCESS, {"processed": processed}, [], [])
    click.echo(f"Обработано задач: {processed}")


if __name__ == "__main__":
    try:
        cli()
    except (KeyboardInterrupt, click.Abort):
        click.echo("\nПрервано пользователем (Ctrl+C).", err=True)
        write_summary("interrupted", EXIT_INTERRUPTED, {}, [], ["Прервано пользователем (Ctrl+C)"])
        sys.exit(EXIT_INTERRUPTED)
