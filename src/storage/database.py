"""База данных для хранения информации о видео."""

import sqlite3
import hashlib
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class VideoRecord:
    """Запись о видео в хранилище."""
    
    id: Optional[int] = None
    file_path: str = ""
    file_hash: Optional[str] = None  # Хеш файла для определения дубликатов
    title: str = ""
    description: str = ""
    channel: Optional[str] = None
    source_folder: str = ""  # Папка экспорта (например, "input/Экпорты ЕГЭ/Апрель 25")
    date: Optional[datetime] = None
    uploaded: bool = False  # Статус загрузки
    upload_date: Optional[datetime] = None
    video_url: Optional[str] = None  # URL загруженного видео в VK
    post_url: Optional[str] = None  # URL поста на стене
    error_message: Optional[str] = None  # Сообщение об ошибке при загрузке
    
    def to_dict(self) -> dict:
        """Преобразовать в словарь."""
        result = asdict(self)
        if self.date:
            result['date'] = self.date.isoformat()
        if self.upload_date:
            result['upload_date'] = self.upload_date.isoformat()
        return result


class VideoStorage:
    """Хранилище видео в SQLite базе данных."""
    
    def __init__(self, db_path: Path = Path("videos.db")):
        """Инициализировать хранилище.
        
        Args:
            db_path: Путь к файлу базы данных.
        """
        self.db_path = Path(db_path)
        self._init_database()
    
    def _init_database(self):
        """Инициализировать структуру базы данных."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL UNIQUE,
                file_hash TEXT,
                title TEXT NOT NULL,
                description TEXT,
                channel TEXT,
                source_folder TEXT NOT NULL,
                date TEXT,
                uploaded INTEGER DEFAULT 0,
                upload_date TEXT,
                video_url TEXT,
                post_url TEXT,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Индексы для быстрого поиска
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON videos(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON videos(file_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_uploaded ON videos(uploaded)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel ON videos(channel)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_source_folder ON videos(source_folder)")
        
        # Таблица маппинга: папка -> тип курса (Python, ЕГЭ, ОГЭ)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folder_course_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_path TEXT NOT NULL UNIQUE,
                course_type TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_folder_mapping_path ON folder_course_mapping(folder_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_folder_mapping_course ON folder_course_mapping(course_type)")
        
        conn.commit()
        conn.close()
        self._ensure_default_folder_mappings()
        logger.info(f"База данных инициализирована: {self.db_path}")
    
    def _ensure_default_folder_mappings(self) -> None:
        """Заполнить маппинг папок значениями по умолчанию, если таблица пуста."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM folder_course_mapping")
        if cursor.fetchone()[0] == 0:
            defaults = [
                ("input/Экпорты ЕГЭ", "ЕГЭ"),
                ("input/Экспорт Python", "Python"),
                ("input/Экспорт ОГЭ", "ОГЭ"),
                ("input/ОГЭ по информатике", "ОГЭ"),
            ]
            for folder_path, course_type in defaults:
                cursor.execute(
                    "INSERT OR IGNORE INTO folder_course_mapping (folder_path, course_type) VALUES (?, ?)",
                    (folder_path, course_type),
                )
            logger.info("Добавлены маппинги папок по умолчанию")
        optional = [
            ("d:/Work/TG_Parser/out/AlgorithmPythonStruct", "Алгоритмы"),
        ]
        for folder_path, course_type in optional:
            cursor.execute(
                "INSERT OR IGNORE INTO folder_course_mapping (folder_path, course_type) VALUES (?, ?)",
                (folder_path, course_type),
            )
        conn.commit()
        conn.close()
    
    def add_video(self, record: VideoRecord) -> int:
        """Добавить видео в хранилище.
        
        Args:
            record: Запись о видео.
            
        Returns:
            ID добавленной записи.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO videos (
                    file_path, file_hash, title, description, channel,
                    source_folder, date, uploaded, upload_date,
                    video_url, post_url, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.file_path,
                record.file_hash,
                record.title,
                record.description,
                record.channel,
                record.source_folder,
                record.date.isoformat() if record.date else None,
                1 if record.uploaded else 0,
                record.upload_date.isoformat() if record.upload_date else None,
                record.video_url,
                record.post_url,
                record.error_message,
            ))
            
            record_id = cursor.lastrowid
            conn.commit()
            logger.debug(f"Добавлено видео в БД: {record.file_path} (ID: {record_id})")
            return record_id
            
        except sqlite3.IntegrityError:
            # Видео уже существует, обновляем
            logger.debug(f"Видео уже существует, обновляем: {record.file_path}")
            cursor.execute("""
                UPDATE videos SET
                    file_hash = ?,
                    title = ?,
                    description = ?,
                    channel = ?,
                    source_folder = ?,
                    date = ?
                WHERE file_path = ?
            """, (
                record.file_hash,
                record.title,
                record.description,
                record.channel,
                record.source_folder,
                record.date.isoformat() if record.date else None,
                record.file_path,
            ))
            conn.commit()
            
            # Получаем ID существующей записи
            cursor.execute("SELECT id FROM videos WHERE file_path = ?", (record.file_path,))
            record_id = cursor.fetchone()[0]
            return record_id
            
        finally:
            conn.close()
    
    def get_video(self, video_id: int) -> Optional[VideoRecord]:
        """Получить видео по ID.
        
        Args:
            video_id: ID видео.
            
        Returns:
            Запись о видео или None.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._row_to_record(row)
    
    def get_next_unuploaded(self, channel: Optional[str] = None, source_folder: Optional[str] = None) -> Optional[VideoRecord]:
        """Получить следующее не загруженное видео.
        
        Args:
            channel: Фильтр по каналу (опционально).
            source_folder: Фильтр по папке источника (опционально).
            
        Returns:
            Запись о следующем видео или None.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM videos WHERE uploaded = 0"
        params = []
        
        if channel:
            query += " AND channel = ?"
            params.append(channel)
        
        if source_folder:
            query += " AND source_folder = ?"
            params.append(source_folder)
        
        query += " ORDER BY id LIMIT 1"
        
        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._row_to_record(row)
    
    def mark_uploaded(self, video_id: int, video_url: str, post_url: Optional[str] = None, error: Optional[str] = None):
        """Отметить видео как загруженное.
        
        Args:
            video_id: ID видео.
            video_url: URL загруженного видео.
            post_url: URL поста на стене (опционально).
            error: Сообщение об ошибке (если была ошибка).
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if error:
            cursor.execute("""
                UPDATE videos SET
                    error_message = ?,
                    upload_date = ?
                WHERE id = ?
            """, (error, datetime.now().isoformat(), video_id))
        else:
            cursor.execute("""
                UPDATE videos SET
                    uploaded = 1,
                    upload_date = ?,
                    video_url = ?,
                    post_url = ?,
                    error_message = NULL
                WHERE id = ?
            """, (datetime.now().isoformat(), video_url, post_url, video_id))
        
        conn.commit()
        conn.close()
        logger.debug(f"Видео {video_id} отмечено как загруженное")
    
    def get_videos_range(self, start_id: int, count: Optional[int] = None, 
                         channel: Optional[str] = None, source_folder: Optional[str] = None) -> List[VideoRecord]:
        """Получить диапазон видео.
        
        Args:
            start_id: Начальный ID.
            count: Количество видео (None = все до конца).
            channel: Фильтр по каналу (опционально).
            source_folder: Фильтр по папке источника (опционально).
            
        Returns:
            Список записей о видео.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM videos WHERE id >= ?"
        params = [start_id]
        
        if channel:
            query += " AND channel = ?"
            params.append(channel)
        
        if source_folder:
            query += " AND source_folder = ?"
            params.append(source_folder)
        
        query += " ORDER BY id"
        
        if count:
            query += f" LIMIT {count}"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_record(row) for row in rows]
    
    def get_all_unuploaded(self, channel: Optional[str] = None, source_folder: Optional[str] = None) -> List[VideoRecord]:
        """Получить все не загруженные видео.
        
        Args:
            channel: Фильтр по каналу (опционально).
            source_folder: Фильтр по папке источника (опционально).
            
        Returns:
            Список записей о видео.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM videos WHERE uploaded = 0"
        params = []
        
        if channel:
            query += " AND channel = ?"
            params.append(channel)
        
        if source_folder:
            query += " AND source_folder = ?"
            params.append(source_folder)
        
        query += " ORDER BY id"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_record(row) for row in rows]
    
    def find_by_hash(self, file_hash: str) -> Optional[VideoRecord]:
        """Найти видео по хешу файла (для определения дубликатов).
        
        Args:
            file_hash: Хеш файла.
            
        Returns:
            Запись о видео или None.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM videos WHERE file_hash = ? LIMIT 1", (file_hash,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._row_to_record(row)
    
    def get_statistics(self) -> dict:
        """Получить статистику по видео.
        
        Returns:
            Словарь со статистикой.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM videos")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM videos WHERE uploaded = 1")
        uploaded = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM videos WHERE uploaded = 0")
        not_uploaded = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT channel) FROM videos WHERE channel IS NOT NULL")
        channels = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT source_folder) FROM videos")
        folders = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total": total,
            "uploaded": uploaded,
            "not_uploaded": not_uploaded,
            "channels": channels,
            "source_folders": folders,
        }
    
    # --- Маппинг папка -> тип курса ---
    
    VALID_COURSE_TYPES = ("Python", "ЕГЭ", "ОГЭ", "Алгоритмы")
    
    def set_folder_course(self, folder_path: str, course_type: str) -> None:
        """Установить тип курса для папки.
        
        Args:
            folder_path: Путь к папке (нормализованный, например input/Экспорты ЕГЭ).
            course_type: Тип курса: Python, ЕГЭ, ОГЭ.
        """
        if course_type not in self.VALID_COURSE_TYPES:
            raise ValueError(f"Тип курса должен быть один из: {self.VALID_COURSE_TYPES}")
        folder_path = str(Path(folder_path)).replace("\\", "/")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO folder_course_mapping (folder_path, course_type)
            VALUES (?, ?)
            ON CONFLICT(folder_path) DO UPDATE SET course_type = excluded.course_type
            """,
            (folder_path, course_type),
        )
        conn.commit()
        conn.close()
        logger.debug(f"Маппинг: {folder_path} -> {course_type}")
    
    def get_course_for_folder(self, folder_path: str) -> Optional[str]:
        """Получить тип курса для папки.
        
        Ищет запись, где folder_path является префиксом переданного пути
        (или совпадает). Если несколько подходят — возвращается наиболее
        длинное совпадение.
        
        Args:
            folder_path: Путь к папке экспорта.
            
        Returns:
            Тип курса (Python, ЕГЭ, ОГЭ) или None.
        """
        folder_path = str(Path(folder_path)).replace("\\", "/")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT folder_path, course_type FROM folder_course_mapping ORDER BY LENGTH(folder_path) DESC"
        )
        rows = cursor.fetchall()
        conn.close()
        norm = folder_path
        for stored_path, course_type in rows:
            s = stored_path.replace("\\", "/")
            if norm == s:
                return course_type
            if len(norm) > len(s) and norm.startswith(s):
                # Папка/подпапка (path/...) или каталог выгрузки TG Parser (path__YYYY-MM-DD_HH-mm)
                if norm[len(s)] in "/_":
                    return course_type
        return None
    
    def list_folder_mappings(self) -> List[tuple]:
        """Список всех маппингов папка -> тип курса.
        
        Returns:
            Список пар (folder_path, course_type).
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT folder_path, course_type FROM folder_course_mapping ORDER BY folder_path"
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def delete_folder_mapping(self, folder_path: str) -> bool:
        """Удалить маппинг для папки.
        
        Returns:
            True если запись была удалена.
        """
        folder_path = str(Path(folder_path)).replace("\\", "/")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM folder_course_mapping WHERE folder_path = ?", (folder_path,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
    
    def _row_to_record(self, row: sqlite3.Row) -> VideoRecord:
        """Преобразовать строку БД в VideoRecord."""
        return VideoRecord(
            id=row["id"],
            file_path=row["file_path"],
            file_hash=row["file_hash"],
            title=row["title"],
            description=row["description"] or "",
            channel=row["channel"],
            source_folder=row["source_folder"],
            date=datetime.fromisoformat(row["date"]) if row["date"] else None,
            uploaded=bool(row["uploaded"]),
            upload_date=datetime.fromisoformat(row["upload_date"]) if row["upload_date"] else None,
            video_url=row["video_url"],
            post_url=row["post_url"],
            error_message=row["error_message"],
        )
