"""Точка входа CLI приложения."""

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
from src.publisher.vk_publisher import VKPublisher, VKPublisherError
from src.utils.env_utils import get_env_var
from src.models.video import VideoData

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('publisher.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


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
    
    else:
        # Конкретная папка
        export_path = Path(source_filter)
        if export_path.exists():
            return [export_path]
        else:
            click.echo(f"ОШИБКА: Путь не существует: {export_path}", err=True)
            return []


@click.group()
def cli():
    """VK Video Publisher - публикатор видео из Telegram экспорта в VK Video."""
    pass


@cli.command()
@click.option(
    "--source", "-s",
    default="all",
    help="Источник видео: 'all', 'all_channels', 'ege', 'python', 'oge' или путь к папке"
)
def scan(source: str):
    """Сканировать экспорты и добавить видео в хранилище."""
    click.echo("=" * 80)
    click.echo("Сканирование экспортов")
    click.echo("=" * 80)
    
    storage = get_storage()
    scanner = VideoScanner(storage)
    
    export_paths = get_export_paths(source)
    if not export_paths:
        click.echo("Не найдено экспортов для сканирования", err=True)
        return
    
    click.echo(f"Найдено экспортов: {len(export_paths)}")
    
    stats = scanner.scan_and_add(export_paths, skip_duplicates=True)
    
    click.echo("\n" + "=" * 80)
    click.echo("РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
    click.echo("=" * 80)
    click.echo(f"Добавлено новых: {stats['added']}")
    click.echo(f"Дубликатов пропущено: {stats['duplicates']}")
    click.echo(f"Обновлено существующих: {stats['updated']}")
    
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
    click.echo(f"Каналов: {stats['channels']}")
    click.echo(f"Папок источников: {stats['source_folders']}")


@cli.command()
@click.argument("video_id", type=int)
@click.option("--delay", "-d", type=float, default=5.0, help="Задержка между загрузками")
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
    
    _upload_video(record, storage, delay, max_retries)


@cli.command()
@click.option("--channel", "-c", help="Фильтр по каналу (ЕГЭ, Python)")
@click.option("--source", "-s", help="Фильтр по папке источника")
@click.option("--delay", "-d", type=float, default=5.0, help="Задержка между загрузками")
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
@click.option("--delay", "-d", type=float, default=5.0, help="Задержка между загрузками")
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
@click.option("--delay", "-d", type=float, default=5.0, help="Задержка между загрузками")
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
@click.option("--delay", "-d", type=float, default=5.0, help="Задержка между загрузками")
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


def _upload_video(record: VideoRecord, storage: VideoStorage, delay: float, max_retries: int):
    """Загрузить одно видео."""
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
        )
    except VKPublisherError as e:
        click.echo(f"ОШИБКА инициализации публикатора: {e}", err=True)
        return
    
    successful = 0
    failed = 0
    
    for idx, record in enumerate(records, 1):
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
    click.echo(f"Всего: {len(records)}")


if __name__ == "__main__":
    cli()
