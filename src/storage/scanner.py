"""Сканер для добавления видео в хранилище."""

from pathlib import Path
from typing import List, Optional
from datetime import datetime, date
import logging

from ..parsers.html_parser import HTMLParser
from ..parsers.json_parser import JSONParser
from ..parsers.custom_export_parser import CustomExportParser
from ..title_generators.factory import TitleGeneratorFactory
from ..models.video import VideoData
from .database import VideoStorage, VideoRecord
from .duplicate_detector import DuplicateDetector

logger = logging.getLogger(__name__)


class VideoScanner:
    """Сканер для поиска и добавления видео в хранилище."""
    
    def __init__(self, storage: VideoStorage):
        """Инициализировать сканер.
        
        Args:
            storage: Хранилище видео.
        """
        self.storage = storage
        self.duplicate_detector = DuplicateDetector()
    
    def scan_and_add(
        self,
        export_paths: List[Path],
        skip_duplicates: bool = True,
        date_since: Optional[date] = None,
        date_until: Optional[date] = None,
    ) -> dict:
        """Сканировать экспорты и добавить видео в хранилище.
        
        Args:
            export_paths: Список путей к экспортам.
            skip_duplicates: Пропускать дубликаты.
            date_since: Добавлять только видео с датой >= этой (инкременты).
            date_until: Добавлять только видео с датой <= этой.
            
        Returns:
            Словарь со статистикой: {"added": int, "duplicates": int, "updated": int, "skipped_date": int}
        """
        stats = {"added": 0, "duplicates": 0, "updated": 0, "skipped_date": 0}

        def in_date_range(d: Optional[datetime]) -> bool:
            if d is None:
                return True
            d_date = d.date() if isinstance(d, datetime) else d
            if date_since is not None and d_date < date_since:
                return False
            if date_until is not None and d_date > date_until:
                return False
            return True

        # Парсим все экспорты
        all_videos = []
        for export_path in export_paths:
            export_path = Path(export_path)
            
            if not export_path.exists():
                logger.warning(f"Путь не существует: {export_path}")
                continue
            
            # Определяем формат экспорта (кастомный export.json — до общего JSON)
            parser = None
            if HTMLParser(export_path).detect_format():
                parser = HTMLParser(export_path)
            elif CustomExportParser(export_path).detect_format():
                parser = CustomExportParser(export_path)
            elif JSONParser(export_path).detect_format():
                parser = JSONParser(export_path)
            else:
                logger.warning(f"Не удалось определить формат экспорта: {export_path}")
                continue
            
            if parser:
                try:
                    videos = parser.parse()
                    # Тип курса из маппинга папка -> курс в БД
                    channel = self.storage.get_course_for_folder(str(export_path))
                    for video in videos:
                        video.channel = channel
                        if in_date_range(video.date):
                            all_videos.append((video, export_path))
                        else:
                            stats["skipped_date"] += 1
                    logger.info(f"Обработано {len(videos)} видео из {export_path}")
                except Exception as e:
                    logger.error(f"Ошибка при парсинге {export_path}: {e}", exc_info=True)
        
        # Генерируем заголовки: ЕГЭ/ОГЭ/Алгоритмы — тема/задание; Python/Excel/Аналитика/Комлев — префикс + описание
        channel_generators = {
            "ЕГЭ": TitleGeneratorFactory.create("ege_auto"),
            "ОГЭ": TitleGeneratorFactory.create("oge_auto"),
            "Алгоритмы": TitleGeneratorFactory.create("algorithms_auto"),
            "Python": TitleGeneratorFactory.create("python_auto"),
            "Excel": TitleGeneratorFactory.create("excel"),
            "Аналитика данных": TitleGeneratorFactory.create("analytics"),
            "Комлев": TitleGeneratorFactory.create("komlev"),
        }
        for video_data, source_folder in all_videos:
            generator = channel_generators.get(video_data.channel) or TitleGeneratorFactory.create("simple")
            
            if generator:
                video_data.title = generator.generate(video_data)
            else:
                video_data.title = video_data.file_path.stem
            
            # Вычисляем хеш файла
            try:
                file_hash = self.duplicate_detector.calculate_file_hash(video_data.file_path)
            except Exception as e:
                logger.warning(f"Не удалось вычислить хеш для {video_data.file_path}: {e}")
                file_hash = None
            
            # Проверяем на дубликаты (но всё равно вызываем add_video для обновления заголовка/описания)
            is_duplicate = False
            if skip_duplicates and file_hash:
                existing = self.storage.find_by_hash(file_hash)
                if existing:
                    logger.debug(f"Дубликат по хешу: {video_data.file_path}")
                    stats["duplicates"] += 1
                    is_duplicate = True

            # Создаем запись (для дубликатов add_video сделает UPDATE — обновятся title, description, channel)
            record = VideoRecord(
                file_path=str(video_data.file_path),
                file_hash=file_hash,
                title=video_data.title,
                description=video_data.description,
                channel=video_data.channel,
                source_folder=str(source_folder),
                date=video_data.date,
                uploaded=False,
            )
            
            # Добавляем в хранилище
            try:
                record_id = self.storage.add_video(record)
                stats["added"] += 1
                logger.debug(f"Добавлено видео ID {record_id}: {video_data.file_path.name}")
            except Exception as e:
                logger.error(f"Ошибка добавления видео {video_data.file_path}: {e}")
                stats["updated"] += 1
        
        return stats
