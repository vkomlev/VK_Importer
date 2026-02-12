"""Сканер для добавления видео в хранилище."""

from pathlib import Path
from typing import List, Optional
import logging

from ..parsers.html_parser import HTMLParser
from ..parsers.json_parser import JSONParser
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
    
    def scan_and_add(self, export_paths: List[Path], skip_duplicates: bool = True) -> dict:
        """Сканировать экспорты и добавить видео в хранилище.
        
        Args:
            export_paths: Список путей к экспортам.
            skip_duplicates: Пропускать дубликаты.
            
        Returns:
            Словарь со статистикой: {"added": int, "duplicates": int, "updated": int}
        """
        stats = {"added": 0, "duplicates": 0, "updated": 0}
        
        # Парсим все экспорты
        all_videos = []
        for export_path in export_paths:
            export_path = Path(export_path)
            
            if not export_path.exists():
                logger.warning(f"Путь не существует: {export_path}")
                continue
            
            # Определяем формат экспорта
            parser = None
            if HTMLParser(export_path).detect_format():
                parser = HTMLParser(export_path)
            elif JSONParser(export_path).detect_format():
                parser = JSONParser(export_path)
            else:
                logger.warning(f"Не удалось определить формат экспорта: {export_path}")
                continue
            
            if parser:
                try:
                    videos = parser.parse()
                    # Определяем канал по пути
                    if "ЕГЭ" in str(export_path) or "ЕГЭ" in str(export_path.parent):
                        channel = "ЕГЭ"
                    elif "Python" in str(export_path) or "Python" in str(export_path.parent):
                        channel = "Python"
                    else:
                        channel = None
                    
                    for video in videos:
                        video.channel = channel
                        all_videos.append((video, export_path))
                    
                    logger.info(f"Обработано {len(videos)} видео из {export_path}")
                except Exception as e:
                    logger.error(f"Ошибка при парсинге {export_path}: {e}", exc_info=True)
        
        # Генерируем заголовки
        ege_generator = TitleGeneratorFactory.create("ege_auto")
        python_generator = TitleGeneratorFactory.create("python_auto")
        
        for video_data, source_folder in all_videos:
            # Генерируем заголовок
            if video_data.channel == "ЕГЭ":
                generator = ege_generator
            elif video_data.channel == "Python":
                generator = python_generator
            else:
                generator = TitleGeneratorFactory.create("simple")
            
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
            
            # Проверяем на дубликаты
            if skip_duplicates and file_hash:
                existing = self.storage.find_by_hash(file_hash)
                if existing:
                    logger.debug(f"Дубликат найден: {video_data.file_path} (существующий: {existing.file_path})")
                    stats["duplicates"] += 1
                    continue
            
            # Создаем запись
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
