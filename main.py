"""Точка входа CLI приложения."""

import subprocess
import sys
import io
import time
from pathlib import Path
import logging
from typing import Optional

import click

# Добавить src в путь для импортов
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Настройка кодировки для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from src.storage.database import VideoStorage, VideoRecord
from src.storage.scanner import VideoScanner
from src.title_generators.factory import TitleGeneratorFactory
from src.publisher.vk_publisher import VKPublisher, VKPublisherError
from src.utils.env_utils import get_env_var
from src.models.video import VideoData

# Типы курсов для маппинга папка → курс (управление через CLI: folders set/list)
COURSE_TYPES = ("Python", "ЕГЭ", "ОГЭ", "Алгоритмы", "Excel", "Комлев", "Аналитика данных")

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


def get_export_paths(source_filter: Optional[str] = None) -> list[Path]:
    """Получить список путей к экспортам.
    
    Args:
        source_filter: Фильтр источника:
            - "all" - все экспорты из всех папок
            - "all_channels" - все экспорты из всех каналов (все папки в input/)
            - "ege" - все экспорты ЕГЭ
            - "python" - все экспорты Python
            - путь к конкретной папке
        
    Returns:
        Список путей к экспортам.
    """
    input_dir = Path("input")
    
    if not source_filter or source_filter == "all":
        # Все экспорты из всех папок
        export_paths = []
        if input_dir.exists():
            for channel_dir in input_dir.iterdir():
                if channel_dir.is_dir():
                    for export_folder in channel_dir.iterdir():
                        if export_folder.is_dir():
                            export_paths.append(export_folder)
                    # Также проверяем корень канала
                    export_paths.append(channel_dir)
        return export_paths
    
    elif source_filter == "all_channels":
        # Все каналы (все папки в input/)
        export_paths = []
        if input_dir.exists():
            for channel_dir in input_dir.iterdir():
                if channel_dir.is_dir():
                    export_paths.append(channel_dir)
        return export_paths
    
    elif source_filter.lower() == "ege":
        # Все экспорты ЕГЭ
        ege_dir = input_dir / "Экпорты ЕГЭ"
        export_paths = []
        if ege_dir.exists():
            for export_folder in ege_dir.iterdir():
                if export_folder.is_dir():
                    export_paths.append(export_folder)
            export_paths.append(ege_dir)
        return export_paths
    
    elif source_filter.lower() == "python":
        # Все экспорты Python
        python_dir = input_dir / "Экспорт Python"
        export_paths = []
        if python_dir.exists():
            export_paths.append(python_dir)
            for export_folder in python_dir.iterdir():
                if export_folder.is_dir():
                    export_paths.append(export_folder)
        return export_paths
    
    elif source_filter.lower() == "oge":
        # Все экспорты ОГЭ
        oge_dir = input_dir / "Экспорт ОГЭ"
        if not oge_dir.exists():
            oge_dir = input_dir / "ОГЭ по информатике"
        export_paths = []
        if oge_dir.exists():
            export_paths.append(oge_dir)
            for export_folder in oge_dir.iterdir():
                if export_folder.is_dir():
                    export_paths.append(export_folder)
        return export_paths

    elif source_filter.lower() == "tg_parser":
        # Выгрузки TG Parser (инкрементные и первоначальные)
        tg_out = Path("d:/Work/TG_Parser/out")
        folders = [
            "cyberguru_ege__2026-02-19_15-11",
            "cyberguru_excel__2026-02-19_18-32",
            "CyberGuruKomlev__2026-02-19_17-04",
            "CyberGuruPython__2026-02-19_16-24",
            "InfOGELihgt__2026-02-19_17-01",
            "SQLPandasBI__2026-02-19_20-52",
        ]
        export_paths = []
        for name in folders:
            p = tg_out / name
            if p.exists() and p.is_dir():
                export_paths.append(p)
        return export_paths
    
    else:
        # Конкретная папка
        export_path = Path(source_filter)
        if export_path.exists():
            return [export_path]
        click.echo(f"ОШИБКА: Путь не существует: {export_path}", err=True)
        return []


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


@folders.command("remove")
@click.argument("folder_path", type=click.Path(exists=False))
def folders_remove(folder_path: str):
    """Удалить маппинг для папки."""
    storage = get_storage()
    if storage.delete_folder_mapping(folder_path):
        click.echo(f"Удалён маппинг для: {folder_path}")
    else:
        click.echo(f"Маппинг для папки не найден: {folder_path}", err=True)


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
    click.echo("=" * 80)
    click.echo("Сканирование экспортов")
    click.echo("=" * 80)

    storage = get_storage()
    if source.lower() == "mapped":
        export_paths = [Path(p) for p, _ in storage.list_folder_mappings() if Path(p).exists()]
    else:
        export_paths = get_export_paths(source)
    if not export_paths:
        click.echo("Не найдено экспортов для сканирования", err=True)
        return

    date_since = _parse_date_option(since)
    date_until = _parse_date_option(until)
    if since and not date_since:
        click.echo(f"Неверный формат --since (ожидается YYYY-MM-DD): {since}", err=True)
        sys.exit(1)
    if until and not date_until:
        click.echo(f"Неверный формат --until (ожидается YYYY-MM-DD): {until}", err=True)
        sys.exit(1)

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


@cli.command()
def stats():
    """Показать статистику по видео."""
    storage = get_storage()
    stats = storage.get_statistics()
    
    click.echo("=" * 80)
    click.echo("СТАТИСТИКА")
    click.echo("=" * 80)
    click.echo(f"Всего видео: {stats['total']}")
    click.echo(f"Загружено: {stats['uploaded']}")
    click.echo(f"Не загружено: {stats['not_uploaded']}")
    if stats.get("skipped", 0):
        click.echo(f"Помечено для пропуска: {stats['skipped']}")
    click.echo(f"Каналов: {stats['channels']}")
    click.echo(f"Папок источников: {stats['source_folders']}")


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
        return
    storage = get_storage()
    n = storage.set_skip_upload(ids=list(ids) if ids else None, filenames=file_list or None, skip=True)
    click.echo(f"Помечено для пропуска: {n} записей.")


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
        return
    storage = get_storage()
    n = storage.set_skip_upload(ids=list(ids) if ids else None, filenames=file_list or None, skip=False)
    click.echo(f"Снята пометка пропуска: {n} записей.")


@cli.command("delete-skipped-from-vk")
@click.option("--delay", "-d", type=float, default=DEFAULT_UPLOAD_DELAY, help="Пауза между запросами к VK (сек)")
@click.option("--dry-run", is_flag=True, help="Только показать, что будет удалено, не вызывать API")
def delete_skipped_from_vk(delay: float, dry_run: bool):
    """Удалить из VK ролики по URL записей с skip=1 (удобный отбор по пометке; удаление всё равно по URL)."""
    storage = get_storage()
    records = storage.get_skipped_with_video_url()
    if not records:
        click.echo("Нет записей с пометкой skip и заполненным video_url.")
        return
    url_list = [r.video_url for r in records if r.video_url]
    click.echo(f"Найдено записей с skip=1 и URL: {len(url_list)}. Удаление по URL.")
    access_token = get_env_var("VK_ACCESS_TOKEN")
    if not access_token:
        click.echo("ОШИБКА: VK_ACCESS_TOKEN не найден в .env", err=True)
        return
    try:
        publisher = VKPublisher(access_token=access_token, group_id=None, on_token_expired=_refresh_vk_token_callback)
    except VKPublisherError as e:
        click.echo(f"ОШИБКА инициализации VK API: {e}", err=True)
        return
    _delete_from_vk_by_urls(url_list, storage, publisher, delay, dry_run)


@cli.command("clear-skip-upload-state")
def clear_skip_upload_state():
    """Сбросить данные загрузки у всех записей с пометкой skip (только локально). Используйте после delete-skipped-from-vk или если ролики с skip в VK не загружались."""
    storage = get_storage()
    n = storage.clear_upload_state_for_skipped()
    click.echo(f"Сброшены данные загрузки у {n} записей с пометкой skip.")


def _delete_from_vk_by_urls(
    urls: list[str],
    storage: VideoStorage,
    publisher: VKPublisher,
    delay: float,
    dry_run: bool,
) -> None:
    """Удалить в VK видео по списку URL; при наличии записи в БД с таким video_url — сбросить данные загрузки."""
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
        return
    if dry_run:
        for oid, vid, url in parsed:
            click.echo(f"  {url} -> video.delete(owner_id={oid}, video_id={vid})")
        click.echo(f"Всего к удалению в VK: {len(parsed)}. Запустите без --dry-run.")
        return
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
    click.echo(f"Готово: удалено в VK — {ok} из {len(parsed)}.")


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
        return
    storage = get_storage()
    access_token = get_env_var("VK_ACCESS_TOKEN")
    if not access_token:
        click.echo("ОШИБКА: VK_ACCESS_TOKEN не найден в .env", err=True)
        return
    try:
        publisher = VKPublisher(access_token=access_token, group_id=None, on_token_expired=_refresh_vk_token_callback)
    except VKPublisherError as e:
        click.echo(f"ОШИБКА инициализации VK API: {e}", err=True)
        return
    _delete_from_vk_by_urls(url_list, storage, publisher, delay, dry_run)


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
        return
    
    if record.uploaded:
        click.echo(f"Видео {video_id} уже загружено: {record.video_url}")
        return

    if getattr(record, "skip_upload", False):
        click.echo("Видео помечено для пропуска загрузки. Снимите пометку: python main.py unskip --id " + str(video_id))
        return

    _upload_video(record, storage, delay, max_retries)


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
        return
    
    click.echo(f"Загрузка видео ID {record.id}: {Path(record.file_path).name}")
    _upload_video(record, storage, delay, max_retries)


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
        return
    
    click.echo(f"Найдено видео для загрузки: {len(records)}")
    _upload_batch(records, storage, delay, max_retries)


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
        return
    
    records = all_records[:count] if count else all_records
    
    click.echo(f"Будет загружено видео: {len(records)}")
    _upload_batch(records, storage, delay, max_retries)


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
        return
    
    click.echo(f"Будет загружено видео: {len(records)}")
    _upload_batch(records, storage, delay, max_retries)


def _get_title_generator_for_channel(channel: Optional[str]):
    """Генератор заголовков по каналу (тот же маппинг, что в сканере)."""
    names = {
        "ЕГЭ": "ege_auto",
        "ОГЭ": "oge_auto",
        "Алгоритмы": "algorithms_auto",
        "Python": "python_auto",
        "Excel": "excel",
        "Аналитика данных": "analytics",
        "Комлев": "komlev",
    }
    name = names.get((channel or "").strip()) if channel else None
    return TitleGeneratorFactory.create(name) if name else TitleGeneratorFactory.create("simple")


@cli.command("recalc-titles")
@click.option("--channel", "-c", help="Пересчитать только для канала (например Excel, Комлев, Аналитика данных)")
def recalc_titles(channel: Optional[str]):
    """Пересчитать заголовки по правилам курса и обновить БД."""
    storage = get_storage()
    records = storage.get_videos_range(0, 500000, channel=channel)
    if not records:
        click.echo("Нет записей для пересчёта.")
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
    access_token = get_env_var("VK_ACCESS_TOKEN")
    if not access_token:
        click.echo("ОШИБКА: VK_ACCESS_TOKEN не найден в .env", err=True)
        sys.exit(1)
    ids_path = Path(ids_file)
    if not ids_path.exists():
        click.echo(f"Файл не найден: {ids_path}", err=True)
        sys.exit(1)
    raw = ids_path.read_text(encoding="utf-8").strip()
    ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
    if not ids:
        click.echo("Список ID пуст.")
        return
    storage = get_storage()
    records = storage.get_videos_by_ids(ids)
    uploaded = [r for r in records if r.video_url]
    if not uploaded:
        click.echo("Среди указанных ID нет загруженных в VK видео.")
        return
    try:
        publisher = VKPublisher(
            access_token=access_token,
            group_id=None,
            delay_between_uploads=delay,
            max_retries=3,
            on_token_expired=_refresh_vk_token_callback,
        )
    except VKPublisherError as e:
        click.echo(f"Ошибка инициализации VK API: {e}", err=True)
        return
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
    click.echo(f"Готово: обновлено {ok} из {len(uploaded)}.")


def _upload_video(record: VideoRecord, storage: VideoStorage, delay: float, max_retries: int):
    """Загрузить одно видео. При skip_upload загрузка не выполняется."""
    if getattr(record, "skip_upload", False):
        click.echo("Пропуск: запись помечена для пропуска загрузки (skip).")
        return
    # Загружаем переменные окружения
    access_token = get_env_var("VK_ACCESS_TOKEN")
    group_id_str = get_env_var("VK_GROUP_ID")
    
    if not access_token:
        click.echo("ОШИБКА: VK_ACCESS_TOKEN не найден в .env файле", err=True)
        return
    
    if not group_id_str:
        click.echo("ОШИБКА: VK_GROUP_ID не найден в .env файле", err=True)
        return
    
    try:
        group_id = int(group_id_str)
    except ValueError:
        click.echo(f"ОШИБКА: Неверный формат VK_GROUP_ID: {group_id_str}", err=True)
        return
    
    # Создаем VideoData из записи
    video_data = VideoData(
        file_path=Path(record.file_path),
        title=record.title,
        description=record.description,
        date=record.date,
        channel=record.channel,
    )
    
    # Инициализируем публикатор
    try:
        publisher = VKPublisher(
            access_token=access_token,
            group_id=group_id,
            delay_between_uploads=delay,
            max_retries=max_retries,
            on_token_expired=_refresh_vk_token_callback,
        )
    except VKPublisherError as e:
        click.echo(f"ОШИБКА инициализации публикатора: {e}", err=True)
        return
    
    # Загружаем видео
    video_url = publisher.publish(video_data)
    post_url = getattr(video_data, '_post_url', None)
    
    if video_url:
        storage.mark_uploaded(record.id, video_url, post_url=post_url)
        click.echo(f"✓ Видео {record.id} успешно загружено: {video_url}")
        if post_url:
            click.echo(f"  Пост на стене: {post_url}")
    else:
        storage.mark_uploaded(record.id, "", error="Ошибка загрузки")
        click.echo(f"✗ Ошибка загрузки видео {record.id}")


def _upload_batch(records: list[VideoRecord], storage: VideoStorage, delay: float, max_retries: int):
    """Загрузить пакет видео."""
    # Загружаем переменные окружения
    access_token = get_env_var("VK_ACCESS_TOKEN")
    group_id_str = get_env_var("VK_GROUP_ID")
    
    if not access_token:
        click.echo("ОШИБКА: VK_ACCESS_TOKEN не найден в .env файле", err=True)
        return
    
    if not group_id_str:
        click.echo("ОШИБКА: VK_GROUP_ID не найден в .env файле", err=True)
        return
    
    try:
        group_id = int(group_id_str)
    except ValueError:
        click.echo(f"ОШИБКА: Неверный формат VK_GROUP_ID: {group_id_str}", err=True)
        return
    
    # Инициализируем публикатор
    try:
        publisher = VKPublisher(
            access_token=access_token,
            group_id=group_id,
            delay_between_uploads=delay,
            max_retries=max_retries,
            on_token_expired=_refresh_vk_token_callback,
        )
    except VKPublisherError as e:
        click.echo(f"ОШИБКА инициализации публикатора: {e}", err=True)
        return
    
    successful = 0
    failed = 0
    skipped = 0

    for idx, record in enumerate(records, 1):
        if getattr(record, "skip_upload", False):
            click.echo(f"\n[{idx}/{len(records)}] Пропуск ID {record.id} (помечено для пропуска загрузки)")
            skipped += 1
            continue
        click.echo(f"\n[{idx}/{len(records)}] Загрузка видео ID {record.id}: {Path(record.file_path).name}")
        
        video_data = VideoData(
            file_path=Path(record.file_path),
            title=record.title,
            description=record.description,
            date=record.date,
            channel=record.channel,
        )
        
        video_url = publisher.publish(video_data)
        post_url = getattr(video_data, '_post_url', None)
        
        if video_url:
            storage.mark_uploaded(record.id, video_url, post_url=post_url)
            successful += 1
            click.echo(f"✓ Успешно: {video_url}")
            if post_url:
                click.echo(f"  Пост: {post_url}")
        else:
            storage.mark_uploaded(record.id, "", error="Ошибка загрузки")
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


if __name__ == "__main__":
    cli()
